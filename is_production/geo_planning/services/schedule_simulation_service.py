import json

import frappe
from frappe.utils import getdate, add_days


def _float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _percent_factor(value, default=100.0):
    value = _float(value, default)
    if value <= 0:
        value = default
    return value / 100.0


def _get_select_options(doctype, fieldname):
    try:
        df = frappe.get_meta(doctype).get_field(fieldname)
        if not df or not df.options:
            return []
        return [x.strip() for x in str(df.options).split("\n") if x.strip()]
    except Exception:
        return []


def _safe_set(doc, fieldname, value):
    try:
        df = frappe.get_meta(doc.doctype).get_field(fieldname)
        if not df:
            return

        if df.fieldtype == "Select":
            options = _get_select_options(doc.doctype, fieldname)
            if options and value not in options:
                return

        setattr(doc, fieldname, value)
    except Exception:
        pass


def _has_field(doctype, fieldname):
    return frappe.get_meta(doctype).has_field(fieldname)


def _set_if_field(doc, fieldname, value):
    if _has_field(doc.doctype, fieldname):
        setattr(doc, fieldname, value)


def _day_type(date_value):
    weekday = getdate(date_value).weekday()
    if weekday == 5:
        return "Saturday"
    if weekday == 6:
        return "Sunday"
    return "Weekday"


def _shifts_for_day(scenario, day_type):
    if day_type == "Saturday":
        return _float(scenario.shifts_per_saturday, 0)
    if day_type == "Sunday":
        return _float(scenario.shifts_per_sunday, 0)
    return _float(scenario.shifts_per_weekday, 0)


def _shift_hours_for_day(scenario, day_type):
    if day_type == "Saturday":
        return _float(scenario.shift_hours_saturday, 0)
    if day_type == "Sunday":
        return _float(scenario.shift_hours_sunday, 0)
    return _float(scenario.shift_hours_weekday, 0)


def _hourly_capacity(scenario):
    excavators = _float(scenario.number_of_excavators, 1)
    capacity_per_hour = _float(scenario.capacity_per_excavator_hour, 0)
    utilisation = _percent_factor(scenario.utilisation_percent, 100)
    availability = _percent_factor(scenario.availability_percent, 100)
    return excavators * capacity_per_hour * utilisation * availability


def _period_capacity(scenario, day_type):
    return _hourly_capacity(scenario) * _shift_hours_for_day(scenario, day_type) * _shifts_for_day(scenario, day_type)


def _clear_existing_schedule(scenario_name):
    for name in frappe.get_all("Mine Schedule Block", filters={"schedule_scenario": scenario_name}, pluck="name", limit_page_length=0):
        frappe.delete_doc("Mine Schedule Block", name, ignore_permissions=True)

    for name in frappe.get_all("Mine Schedule Period", filters={"schedule_scenario": scenario_name}, pluck="name", limit_page_length=0):
        frappe.delete_doc("Mine Schedule Period", name, ignore_permissions=True)


def _create_periods(scenario):
    if not scenario.start_date or not scenario.end_date:
        frappe.throw("Start Date and End Date are required.")

    start = getdate(scenario.start_date)
    end = getdate(scenario.end_date)

    if end < start:
        frappe.throw("End Date cannot be before Start Date.")

    periods = []
    current = start
    period_no = 1

    while current <= end:
        dt = _day_type(current)
        available_shifts = _shifts_for_day(scenario, dt)
        available_hours = available_shifts * _shift_hours_for_day(scenario, dt)
        capacity_volume = _period_capacity(scenario, dt)

        doc = frappe.new_doc("Mine Schedule Period")
        doc.schedule_scenario = scenario.name
        doc.period_no = period_no
        doc.period_name = f"Day {period_no} - {current.isoformat()}"
        doc.period_start = current
        doc.period_end = current
        doc.day_type = dt
        doc.available_shifts = available_shifts
        doc.available_hours = available_hours
        doc.capacity_volume = capacity_volume
        doc.scheduled_volume = 0
        doc.scheduled_tonnes = 0
        doc.scheduled_blocks = 0
        _safe_set(doc, "period_status", "Draft")
        doc.insert(ignore_permissions=True)

        periods.append(doc)
        current = add_days(current, 1)
        period_no += 1

    return periods


def _get_schedulable_blocks(scenario):
    return frappe.db.sql(
        """
        SELECT
            mb.name AS mining_block,
            mb.mining_block_code,
            mb.cut_no,
            mb.block_no,
            mb.row_no,
            mb.column_no,
            mb.centroid_x,
            mb.centroid_y,
            mb.polygon_geojson,
            mb.planning_status,
            mbmv.material_seam,
            mbmv.value_type,
            mbmv.volume,
            mbmv.tonnes,
            mbmv.material_status
        FROM `tabMining Block Material Value` mbmv
        INNER JOIN `tabMining Block` mb
            ON mb.name = mbmv.mining_block
        WHERE mb.source_pit_layout = %(geo_pit_layout)s
          AND mbmv.material_seam = %(material_seam)s
          AND mbmv.value_type = %(value_type)s
          AND COALESCE(mbmv.volume, 0) > 0
          AND (mbmv.material_status = 'Mineable' OR mbmv.material_status IS NULL OR mbmv.material_status = '')
        ORDER BY
            COALESCE(mb.cut_no, 0) ASC,
            COALESCE(mb.block_no, 0) ASC,
            COALESCE(mb.row_no, 0) ASC,
            COALESCE(mb.column_no, 0) ASC,
            mb.mining_block_code ASC
        """,
        {
            "geo_pit_layout": scenario.geo_pit_layout,
            "material_seam": scenario.material_seam,
            "value_type": scenario.value_type,
        },
        as_dict=True,
    )


def _assign_blocks_to_periods_partial(scenario, periods, blocks):
    """
    Correct production-capacity scheduler.

    A Mining Block may be split across periods.
    Mine Schedule Block rows represent scheduled portions of a Mining Block.

    planned_volume/scheduled_volume = volume mined in that period row.
    planned_tonnes/scheduled_tonnes = tonnes mined in that period row.
    required_hours = period hours consumed by that row.
    """
    if not periods:
        frappe.throw("No schedule periods were created.")

    hourly_capacity = _hourly_capacity(scenario)
    if hourly_capacity <= 0:
        frappe.throw("Hourly capacity is zero. Check Number of Excavators and Capacity per Excavator Hour.")

    period_index = 0
    period_used_hours = {p.name: 0.0 for p in periods}
    period_volume = {p.name: 0.0 for p in periods}
    period_tonnes = {p.name: 0.0 for p in periods}
    period_block_rows = {p.name: 0 for p in periods}

    total_volume = 0.0
    total_tonnes = 0.0
    scheduled_rows = 0
    completed_blocks = 0
    sequence_no = 1

    for block in blocks:
        block_total_volume = _float(block.volume, 0)
        block_total_tonnes = _float(block.tonnes, 0)

        remaining_volume = block_total_volume
        remaining_tonnes = block_total_tonnes

        if block_total_volume <= 0:
            continue

        while remaining_volume > 0.000001 and period_index < len(periods):
            period = periods[period_index]
            available_hours = _float(period.available_hours, 0)
            used_hours = period_used_hours[period.name]
            remaining_hours = available_hours - used_hours

            if remaining_hours <= 0.000001:
                period_index += 1
                continue

            period_capacity_remaining = remaining_hours * hourly_capacity
            portion_volume = min(remaining_volume, period_capacity_remaining)
            portion_fraction = portion_volume / block_total_volume if block_total_volume else 0
            portion_tonnes = block_total_tonnes * portion_fraction
            portion_hours = portion_volume / hourly_capacity if hourly_capacity else 0

            start_fraction = (block_total_volume - remaining_volume) / block_total_volume
            end_fraction = (block_total_volume - remaining_volume + portion_volume) / block_total_volume
            remaining_after = max(0.0, remaining_volume - portion_volume)

            doc = frappe.new_doc("Mine Schedule Block")
            doc.schedule_scenario = scenario.name
            doc.schedule_period = period.name
            doc.mining_block = block.mining_block
            doc.mining_block_code = block.mining_block_code
            doc.material_seam = scenario.material_seam
            doc.sequence_no = sequence_no

            # Existing fields remain useful and mean "this scheduled portion".
            doc.planned_volume = portion_volume
            doc.planned_tonnes = portion_tonnes
            doc.required_hours = portion_hours

            # New partial-scheduling fields.
            _set_if_field(doc, "block_total_volumes", block_total_volume)  # fieldname currently plural in your DocType
            _set_if_field(doc, "block_total_tonnes", block_total_tonnes)
            _set_if_field(doc, "scheduled_volume", portion_volume)
            _set_if_field(doc, "scheduled_tonnes", portion_tonnes)
            _set_if_field(doc, "remaining_volume_after", remaining_after)
            _set_if_field(doc, "start_fraction", start_fraction)
            _set_if_field(doc, "end_fraction", end_fraction)
            _set_if_field(doc, "is_partial", 1 if portion_volume < block_total_volume else 0)
            _set_if_field(doc, "is_block_complete", 1 if remaining_after <= 0.000001 else 0)

            _safe_set(doc, "schedule_status", "Planned")
            _safe_set(doc, "animation_status", "Pending")
            doc.insert(ignore_permissions=True)

            period_used_hours[period.name] += portion_hours
            period_volume[period.name] += portion_volume
            period_tonnes[period.name] += portion_tonnes
            period_block_rows[period.name] += 1

            total_volume += portion_volume
            total_tonnes += portion_tonnes
            scheduled_rows += 1
            sequence_no += 1

            remaining_volume -= portion_volume
            remaining_tonnes -= portion_tonnes

            if remaining_volume <= 0.000001:
                completed_blocks += 1

            if period_used_hours[period.name] >= available_hours - 0.000001:
                period_index += 1

        if remaining_volume > 0.000001:
            # No more schedule periods. The block is not fully scheduled.
            break

    for period in periods:
        frappe.db.set_value(
            "Mine Schedule Period",
            period.name,
            {
                "scheduled_volume": period_volume[period.name],
                "scheduled_tonnes": period_tonnes[period.name],
                "scheduled_blocks": period_block_rows[period.name],
            },
            update_modified=False,
        )

    scenario.total_volume = total_volume
    scenario.total_tonnes = total_tonnes
    scenario.total_scheduled_blocks = completed_blocks
    _safe_set(scenario, "scenario_status", "Generated")
    scenario.save(ignore_permissions=True)

    return {
        "blocks_checked": len(blocks),
        "blocks_completed": completed_blocks,
        "schedule_rows_created": scheduled_rows,
        "total_volume": total_volume,
        "total_tonnes": total_tonnes,
    }


@frappe.whitelist()
def create_and_generate_schedule(
    scenario_name,
    geo_project,
    geo_pit_layout,
    material_stack,
    material_seam,
    value_type,
    start_date,
    end_date,
    shift_hours_weekday=9,
    shift_hours_saturday=7,
    shift_hours_sunday=7,
    shifts_per_weekday=2,
    shifts_per_saturday=2,
    shifts_per_sunday=2,
    number_of_excavators=1,
    capacity_per_excavator_hour=220,
    utilisation_percent=None,
    availability_percent=None,
    schedule_method="Cut Block",
    overwrite_existing=0,
):
    existing = frappe.db.get_value("Mine Schedule Scenario", {"scenario_name": scenario_name}, "name")

    if existing and not _int(overwrite_existing, 0):
        frappe.throw(f"Scenario Name already exists: {scenario_name}. Use overwrite_existing=1 or choose a new name.")

    if existing and _int(overwrite_existing, 0):
        scenario = frappe.get_doc("Mine Schedule Scenario", existing)
        _clear_existing_schedule(scenario.name)
    else:
        scenario = frappe.new_doc("Mine Schedule Scenario")

    scenario.scenario_name = scenario_name
    scenario.geo_project = geo_project
    scenario.geo_pit_layout = geo_pit_layout
    scenario.material_stack = material_stack
    scenario.material_seam = material_seam
    scenario.value_type = value_type
    scenario.start_date = start_date
    scenario.end_date = end_date
    scenario.shift_hours_weekday = _float(shift_hours_weekday, 0)
    scenario.shift_hours_saturday = _float(shift_hours_saturday, 0)
    scenario.shift_hours_sunday = _float(shift_hours_sunday, 0)
    scenario.shifts_per_weekday = _float(shifts_per_weekday, 0)
    scenario.shifts_per_saturday = _float(shifts_per_saturday, 0)
    scenario.shifts_per_sunday = _float(shifts_per_sunday, 0)
    scenario.number_of_excavators = _int(number_of_excavators, 1)
    scenario.capacity_per_excavator_hour = _float(capacity_per_excavator_hour, 0)
    scenario.utilisation_percent = utilisation_percent
    scenario.availability_percent = availability_percent
    scenario.schedule_method = schedule_method
    _safe_set(scenario, "scenario_status", "Draft")

    if existing and _int(overwrite_existing, 0):
        scenario.save(ignore_permissions=True)
    else:
        scenario.insert(ignore_permissions=True)

    periods = _create_periods(scenario)
    blocks = _get_schedulable_blocks(scenario)
    result = _assign_blocks_to_periods_partial(scenario, periods, blocks)

    frappe.db.commit()

    return {
        "schedule_scenario": scenario.name,
        "scenario_name": scenario.scenario_name,
        "periods_created": len(periods),
        "hourly_capacity": _hourly_capacity(scenario),
        "blocks_checked": result["blocks_checked"],
        "blocks_completed": result["blocks_completed"],
        "schedule_rows_created": result["schedule_rows_created"],
        "total_volume": result["total_volume"],
        "total_tonnes": result["total_tonnes"],
    }


@frappe.whitelist()
def get_schedule_summary(schedule_scenario):
    scenario = frappe.get_doc("Mine Schedule Scenario", schedule_scenario)

    periods = frappe.get_all(
        "Mine Schedule Period",
        filters={"schedule_scenario": schedule_scenario},
        fields=[
            "name",
            "period_no",
            "period_name",
            "period_start",
            "day_type",
            "available_shifts",
            "available_hours",
            "capacity_volume",
            "scheduled_volume",
            "scheduled_tonnes",
            "scheduled_blocks",
        ],
        order_by="period_no asc",
        limit_page_length=0,
    )

    return {
        "schedule_scenario": scenario.name,
        "scenario_name": scenario.scenario_name,
        "geo_project": scenario.geo_project,
        "geo_pit_layout": scenario.geo_pit_layout,
        "material_stack": scenario.material_stack,
        "material_seam": scenario.material_seam,
        "value_type": scenario.value_type,
        "hourly_capacity": _hourly_capacity(scenario),
        "total_volume": scenario.total_volume,
        "total_tonnes": scenario.total_tonnes,
        "total_scheduled_blocks": scenario.total_scheduled_blocks,
        "period_count": len(periods),
        "periods": periods,
    }


@frappe.whitelist()
def get_animation_payload(schedule_scenario):
    scenario = frappe.get_doc("Mine Schedule Scenario", schedule_scenario)

    rows = frappe.db.sql(
        """
        SELECT
            msb.sequence_no,
            msb.schedule_period,
            msp.period_no,
            msp.period_name,
            msp.period_start,
            msb.mining_block,
            msb.mining_block_code,
            msb.material_seam,
            msb.planned_volume,
            msb.planned_tonnes,
            msb.required_hours,
            msb.block_total_volumes,
            msb.block_total_tonnes,
            msb.scheduled_volume,
            msb.scheduled_tonnes,
            msb.remaining_volume_after,
            msb.start_fraction,
            msb.end_fraction,
            msb.is_partial,
            msb.is_block_complete,
            mb.polygon_geojson,
            mb.centroid_x,
            mb.centroid_y,
            mb.row_no,
            mb.column_no
        FROM `tabMine Schedule Block` msb
        INNER JOIN `tabMine Schedule Period` msp
            ON msp.name = msb.schedule_period
        INNER JOIN `tabMining Block` mb
            ON mb.name = msb.mining_block
        WHERE msb.schedule_scenario = %(schedule_scenario)s
        ORDER BY msb.sequence_no ASC
        """,
        {"schedule_scenario": schedule_scenario},
        as_dict=True,
    )

    blocks = []

    for row in rows:
        polygon = None
        if row.polygon_geojson:
            try:
                polygon = json.loads(row.polygon_geojson)
            except Exception:
                polygon = None

        blocks.append({
            "sequence_no": row.sequence_no,
            "period_no": row.period_no,
            "period_name": row.period_name,
            "period_start": str(row.period_start) if row.period_start else None,
            "mining_block": row.mining_block,
            "mining_block_code": row.mining_block_code,
            "material_seam": row.material_seam,
            "planned_volume": row.planned_volume,
            "planned_tonnes": row.planned_tonnes,
            "required_hours": row.required_hours,
            "block_total_volume": row.block_total_volumes,
            "block_total_tonnes": row.block_total_tonnes,
            "scheduled_volume": row.scheduled_volume,
            "scheduled_tonnes": row.scheduled_tonnes,
            "remaining_volume_after": row.remaining_volume_after,
            "start_fraction": row.start_fraction,
            "end_fraction": row.end_fraction,
            "is_partial": row.is_partial,
            "is_block_complete": row.is_block_complete,
            "centroid_x": row.centroid_x,
            "centroid_y": row.centroid_y,
            "row_no": row.row_no,
            "column_no": row.column_no,
            "polygon_geojson": polygon,
        })

    return {
        "schedule_scenario": scenario.name,
        "scenario_name": scenario.scenario_name,
        "geo_project": scenario.geo_project,
        "geo_pit_layout": scenario.geo_pit_layout,
        "material_stack": scenario.material_stack,
        "material_seam": scenario.material_seam,
        "value_type": scenario.value_type,
        "total_volume": scenario.total_volume,
        "total_tonnes": scenario.total_tonnes,
        "total_scheduled_blocks": scenario.total_scheduled_blocks,
        "blocks": blocks,
    }
