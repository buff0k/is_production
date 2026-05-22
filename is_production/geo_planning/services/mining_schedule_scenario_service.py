import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, add_months, getdate, now_datetime


@frappe.whitelist()
def create_schedule_scenario_from_selection(
    mining_schedule_selection,
    scenario_name,
    period_type="Weekly",
    start_date=None,
    schedule_basis="Fleet Capacity",
    target_tonnes_per_period=None,
    target_volume_per_period=None,
    number_of_shifts=None,
    hours_per_shift=None,
    fleet_capacity_bcm_per_hour=None,
    fleet_capacity_tonnes_per_hour=None,
    drill_blast_required=0,
    drill_blast_lead_time_days=None,
    remarks=None,
):
    if not mining_schedule_selection:
        frappe.throw(_("Mining Schedule Selection is required."))

    if not scenario_name:
        frappe.throw(_("Scenario Name is required."))

    if not start_date:
        frappe.throw(_("Start Date is required."))

    source = frappe.get_doc("Mining Schedule Selection", mining_schedule_selection)

    validate_selection_source(source)

    settings = {
        "period_type": period_type or "Weekly",
        "start_date": start_date,
        "schedule_basis": schedule_basis or "Fleet Capacity",
        "target_tonnes_per_period": flt_safe(target_tonnes_per_period),
        "target_volume_per_period": flt_safe(target_volume_per_period),
        "number_of_shifts": int_safe(number_of_shifts),
        "hours_per_shift": flt_safe(hours_per_shift),
        "fleet_capacity_bcm_per_hour": flt_safe(fleet_capacity_bcm_per_hour),
        "fleet_capacity_tonnes_per_hour": flt_safe(fleet_capacity_tonnes_per_hour),
        "drill_blast_required": int_safe(drill_blast_required),
        "drill_blast_lead_time_days": int_safe(drill_blast_lead_time_days),
    }

    block_sources = build_source_blocks(source)
    period_allocations = allocate_blocks_to_periods(block_sources, settings)

    period_rows = build_period_rows(period_allocations, settings)
    block_rows = build_scheduled_block_rows(period_allocations)
    material_rows = build_period_material_rows(period_allocations)

    totals = calculate_scenario_totals(period_rows, material_rows)

    doc = frappe.get_doc(
        {
            "doctype": "Mining Schedule Scenario",
            "scenario_name": scenario_name,
            "mining_schedule_selection": source.name,
            "geo_project": source.geo_project,
            "geo_pit_layout": source.geo_pit_layout,
            "material_stack": source.material_stack,
            "schedule_status": "Generated",
            "period_type": settings["period_type"],
            "start_date": settings["start_date"],
            "end_date": totals.get("end_date"),
            "schedule_basis": settings["schedule_basis"],
            "target_tonnes_per_period": settings["target_tonnes_per_period"],
            "target_volume_per_period": settings["target_volume_per_period"],
            "number_of_shifts": settings["number_of_shifts"],
            "hours_per_shift": settings["hours_per_shift"],
            "fleet_capacity_bcm_per_hour": settings["fleet_capacity_bcm_per_hour"],
            "fleet_capacity_tonnes_per_hour": settings["fleet_capacity_tonnes_per_hour"],
            "drill_blast_required": settings["drill_blast_required"],
            "drill_blast_lead_time_days": settings["drill_blast_lead_time_days"],
            "total_periods": totals.get("total_periods"),
            "total_blocks": totals.get("total_blocks"),
            "total_effective_area": totals.get("total_effective_area"),
            "total_volume": totals.get("total_volume"),
            "total_tonnes": totals.get("total_tonnes"),
            "average_density": totals.get("average_density"),
            "average_cv": totals.get("average_cv"),
            "capacity_used_percent": totals.get("capacity_used_percent"),
            "generated_on": now_datetime(),
            "generated_by": frappe.session.user,
            "source_filters_json": json.dumps(
                {
                    "source_selection": source.name,
                    "source_selection_name": source.selection_name,
                    "sequence_basis": "Mining Schedule Selection Block.sequence_no",
                    "planning_cut_basis": "Mining Schedule Selection Block.dependency_group",
                    "settings": settings,
                },
                default=str,
            ),
            "remarks": remarks,
            "periods": period_rows,
            "scheduled_blocks": block_rows,
            "period_materials": material_rows,
        }
    )

    doc.insert()

    return {
        "name": doc.name,
        "scenario_name": doc.scenario_name,
        "total_periods": doc.total_periods,
        "total_blocks": doc.total_blocks,
        "total_volume": doc.total_volume,
        "total_tonnes": doc.total_tonnes,
    }


@frappe.whitelist()
def regenerate_schedule_scenario(name):
    doc = frappe.get_doc("Mining Schedule Scenario", name)

    if not doc.mining_schedule_selection:
        frappe.throw(_("Source Selection is required."))

    result = create_schedule_scenario_from_selection(
        mining_schedule_selection=doc.mining_schedule_selection,
        scenario_name="{0} Regenerated {1}".format(doc.scenario_name, frappe.utils.now_datetime().strftime("%Y%m%d%H%M%S")),
        period_type=doc.period_type,
        start_date=doc.start_date,
        schedule_basis=doc.schedule_basis,
        target_tonnes_per_period=doc.target_tonnes_per_period,
        target_volume_per_period=doc.target_volume_per_period,
        number_of_shifts=doc.number_of_shifts,
        hours_per_shift=doc.hours_per_shift,
        fleet_capacity_bcm_per_hour=doc.fleet_capacity_bcm_per_hour,
        fleet_capacity_tonnes_per_hour=doc.fleet_capacity_tonnes_per_hour,
        drill_blast_required=doc.drill_blast_required,
        drill_blast_lead_time_days=doc.drill_blast_lead_time_days,
        remarks="Regenerated from {0}".format(doc.name),
    )

    return result


def validate_selection_source(source):
    if not source.blocks:
        frappe.throw(_("Source selection has no selected block rows."))

    if not source.materials:
        frappe.throw(_("Source selection has no material package rows."))


def build_source_blocks(source):
    material_by_block = defaultdict(list)

    for row in source.materials or []:
        if row.mining_block:
            material_by_block[row.mining_block].append(row)

    source_blocks = []

    sorted_blocks = sorted(
        source.blocks or [],
        key=lambda row: (
            int_safe(row.sequence_no) or 999999,
            row.idx or 999999,
            row.mining_block or "",
        ),
    )

    for row in sorted_blocks:
        if not row.mining_block:
            continue

        materials = material_by_block.get(row.mining_block, [])

        totals = calculate_block_totals(row, materials)

        source_blocks.append(
            {
                "selection_block": row,
                "materials": materials,
                "sequence_no": int_safe(row.sequence_no),
                "dependency_group": row.dependency_group,
                "mining_block": row.mining_block,
                "mining_block_code": row.mining_block_code,
                "geo_project": row.geo_project,
                "source_pit_layout": row.source_pit_layout,
                "cut_no": row.cut_no,
                "block_no": row.block_no,
                "row_no": row.row_no,
                "column_no": row.column_no,
                "effective_area": flt_safe(row.effective_area),
                "total_volume": totals["volume"],
                "total_tonnes": totals["tonnes"],
                "average_density": totals["average_density"],
                "average_cv": totals["average_cv"],
            }
        )

    return source_blocks


def calculate_block_totals(block_row, material_rows):
    volume = sum_float(
        row.volume
        for row in material_rows
        if row.value_type in ("Thickness", None, "")
    )

    tonnes = sum_float(
        row.tonnes
        for row in material_rows
        if row.value_type in ("Thickness", None, "")
    )

    if not volume:
        volume = flt_safe(block_row.total_volume)

    if not tonnes:
        tonnes = flt_safe(block_row.total_tonnes)

    average_density = 0
    if volume:
        average_density = tonnes / volume

    cv_values = []

    for row in material_rows:
        variable_code = (row.variable_code or "").upper()
        if row.value_type == "Quality" and "CV" in variable_code and row.avg_value is not None:
            cv_values.append(flt_safe(row.avg_value))

    average_cv = average(cv_values)

    return {
        "volume": volume,
        "tonnes": tonnes,
        "average_density": average_density,
        "average_cv": average_cv,
    }


def allocate_blocks_to_periods(source_blocks, settings):
    period_type = settings.get("period_type") or "Weekly"
    start_date = getdate(settings.get("start_date"))

    period_no = 1
    current_start = start_date
    current_end = get_period_end_date(current_start, period_type)

    capacity = calculate_period_capacity(settings)
    capacity_tonnes = capacity.get("capacity_tonnes")
    capacity_volume = capacity.get("capacity_volume")

    allocations = []
    current_blocks = []
    running_tonnes = 0
    running_volume = 0

    for block in source_blocks:
        block_tonnes = flt_safe(block.get("total_tonnes"))
        block_volume = flt_safe(block.get("total_volume"))

        should_start_new_period = False

        if current_blocks:
            if capacity_tonnes and running_tonnes + block_tonnes > capacity_tonnes:
                should_start_new_period = True

            if capacity_volume and not capacity_tonnes and running_volume + block_volume > capacity_volume:
                should_start_new_period = True

        if should_start_new_period:
            allocations.append(
                make_period_allocation(
                    period_no=period_no,
                    period_type=period_type,
                    start_date=current_start,
                    end_date=current_end,
                    blocks=current_blocks,
                    capacity=capacity,
                )
            )

            period_no += 1
            current_start = add_days(current_end, 1)
            current_end = get_period_end_date(current_start, period_type)
            current_blocks = []
            running_tonnes = 0
            running_volume = 0

        current_blocks.append(block)
        running_tonnes += block_tonnes
        running_volume += block_volume

    if current_blocks:
        allocations.append(
            make_period_allocation(
                period_no=period_no,
                period_type=period_type,
                start_date=current_start,
                end_date=current_end,
                blocks=current_blocks,
                capacity=capacity,
            )
        )

    return allocations


def make_period_allocation(period_no, period_type, start_date, end_date, blocks, capacity):
    return {
        "period_no": period_no,
        "period_label": get_period_label(period_no, period_type),
        "period_start_date": start_date,
        "period_end_date": end_date,
        "blocks": blocks,
        "capacity": capacity,
    }


def calculate_period_capacity(settings):
    shifts = int_safe(settings.get("number_of_shifts"))
    hours = flt_safe(settings.get("hours_per_shift"))

    target_tonnes = flt_safe(settings.get("target_tonnes_per_period"))
    target_volume = flt_safe(settings.get("target_volume_per_period"))

    tonnes_per_hour = flt_safe(settings.get("fleet_capacity_tonnes_per_hour"))
    volume_per_hour = flt_safe(settings.get("fleet_capacity_bcm_per_hour"))

    capacity_tonnes = target_tonnes
    capacity_volume = target_volume

    if not capacity_tonnes and shifts and hours and tonnes_per_hour:
        capacity_tonnes = shifts * hours * tonnes_per_hour

    if not capacity_volume and shifts and hours and volume_per_hour:
        capacity_volume = shifts * hours * volume_per_hour

    return {
        "capacity_tonnes": capacity_tonnes,
        "capacity_volume": capacity_volume,
    }


def build_period_rows(period_allocations, settings):
    rows = []

    for allocation in period_allocations:
        totals = calculate_period_totals(allocation)

        rows.append(
            {
                "period_no": allocation["period_no"],
                "period_label": allocation["period_label"],
                "period_start_date": allocation["period_start_date"],
                "period_end_date": allocation["period_end_date"],
                "planned_block_count": totals["block_count"],
                "planned_effective_area": totals["effective_area"],
                "planned_volume": totals["volume"],
                "planned_tonnes": totals["tonnes"],
                "average_density": totals["average_density"],
                "average_cv": totals["average_cv"],
                "capacity_volume": allocation["capacity"].get("capacity_volume"),
                "capacity_tonnes": allocation["capacity"].get("capacity_tonnes"),
                "capacity_used_percent": totals["capacity_used_percent"],
                "remaining_volume_capacity": totals["remaining_volume_capacity"],
                "remaining_tonnes_capacity": totals["remaining_tonnes_capacity"],
            }
        )

    return rows


def build_scheduled_block_rows(period_allocations):
    rows = []

    for allocation in period_allocations:
        for block in allocation["blocks"]:
            rows.append(
                {
                    "period_no": allocation["period_no"],
                    "period_label": allocation["period_label"],
                    "sequence_no": block.get("sequence_no"),
                    "dependency_group": block.get("dependency_group"),
                    "mining_block": block.get("mining_block"),
                    "mining_block_code": block.get("mining_block_code"),
                    "geo_project": block.get("geo_project"),
                    "source_pit_layout": block.get("source_pit_layout"),
                    "cut_no": block.get("cut_no"),
                    "block_no": block.get("block_no"),
                    "row_no": block.get("row_no"),
                    "column_no": block.get("column_no"),
                    "effective_area": block.get("effective_area"),
                    "total_volume": block.get("total_volume"),
                    "total_tonnes": block.get("total_tonnes"),
                    "average_density": block.get("average_density"),
                    "average_cv": block.get("average_cv"),
                    "planned_start_date": allocation["period_start_date"],
                    "planned_end_date": allocation["period_end_date"],
                    "schedule_status": "Planned",
                }
            )

    return rows


def build_period_material_rows(period_allocations):
    rows = []

    for allocation in period_allocations:
        period_no = allocation["period_no"]
        period_label = allocation["period_label"]

        grouped = {}

        for block in allocation["blocks"]:
            for material in block.get("materials") or []:
                material_seam = material.material_seam or "No Seam"
                value_type = material.value_type or "Other"
                variable_code = material.variable_code or ""
                variable_name = material.variable_name or ""

                key = (period_no, material_seam, value_type, variable_code, variable_name)

                if key not in grouped:
                    grouped[key] = {
                        "period_no": period_no,
                        "period_label": period_label,
                        "material_seam": material_seam,
                        "value_type": value_type,
                        "variable_code": variable_code,
                        "variable_name": variable_name,
                        "block_names": set(),
                        "effective_area": 0,
                        "volume": 0,
                        "tonnes": 0,
                        "thickness_values": [],
                        "density_values": [],
                        "values": [],
                        "min_values": [],
                        "max_values": [],
                        "point_count": 0,
                    }

                item = grouped[key]
                item["block_names"].add(material.mining_block)
                item["effective_area"] += flt_safe(material.effective_area)
                item["volume"] += flt_safe(material.volume)
                item["tonnes"] += flt_safe(material.tonnes)

                if material.thickness_value is not None:
                    item["thickness_values"].append(flt_safe(material.thickness_value))

                if material.density_value is not None:
                    item["density_values"].append(flt_safe(material.density_value))

                if material.avg_value is not None:
                    item["values"].append(flt_safe(material.avg_value))

                if material.min_value is not None:
                    item["min_values"].append(flt_safe(material.min_value))

                if material.max_value is not None:
                    item["max_values"].append(flt_safe(material.max_value))

                item["point_count"] += int_safe(material.point_count)

        for item in grouped.values():
            rows.append(
                {
                    "period_no": item["period_no"],
                    "period_label": item["period_label"],
                    "material_seam": item["material_seam"],
                    "value_type": item["value_type"],
                    "variable_code": item["variable_code"],
                    "variable_name": item["variable_name"],
                    "block_count": len(item["block_names"]),
                    "effective_area": item["effective_area"],
                    "volume": item["volume"],
                    "tonnes": item["tonnes"],
                    "average_thickness": average(item["thickness_values"]),
                    "average_density": average(item["density_values"]),
                    "average_value": average(item["values"]),
                    "min_value": min(item["min_values"]) if item["min_values"] else None,
                    "max_value": max(item["max_values"]) if item["max_values"] else None,
                    "point_count": item["point_count"],
                }
            )

    return rows


def calculate_period_totals(allocation):
    blocks = allocation.get("blocks") or []
    capacity = allocation.get("capacity") or {}

    total_effective_area = sum_float(block.get("effective_area") for block in blocks)
    total_volume = sum_float(block.get("total_volume") for block in blocks)
    total_tonnes = sum_float(block.get("total_tonnes") for block in blocks)

    average_density = 0
    if total_volume:
        average_density = total_tonnes / total_volume

    average_cv = average(
        [
            block.get("average_cv")
            for block in blocks
            if block.get("average_cv") is not None
        ]
    )

    capacity_tonnes = flt_safe(capacity.get("capacity_tonnes"))
    capacity_volume = flt_safe(capacity.get("capacity_volume"))

    capacity_used_percent = 0

    if capacity_tonnes:
        capacity_used_percent = (total_tonnes / capacity_tonnes) * 100
    elif capacity_volume:
        capacity_used_percent = (total_volume / capacity_volume) * 100

    remaining_tonnes = capacity_tonnes - total_tonnes if capacity_tonnes else 0
    remaining_volume = capacity_volume - total_volume if capacity_volume else 0

    return {
        "block_count": len(blocks),
        "effective_area": total_effective_area,
        "volume": total_volume,
        "tonnes": total_tonnes,
        "average_density": average_density,
        "average_cv": average_cv,
        "capacity_used_percent": capacity_used_percent,
        "remaining_tonnes_capacity": remaining_tonnes,
        "remaining_volume_capacity": remaining_volume,
    }


def calculate_scenario_totals(period_rows, material_rows):
    total_periods = len(period_rows or [])
    total_blocks = sum_float(row.get("planned_block_count") for row in period_rows or [])
    total_effective_area = sum_float(row.get("planned_effective_area") for row in period_rows or [])
    total_volume = sum_float(row.get("planned_volume") for row in period_rows or [])
    total_tonnes = sum_float(row.get("planned_tonnes") for row in period_rows or [])

    average_density = 0
    if total_volume:
        average_density = total_tonnes / total_volume

    cv_values = [
        row.get("average_value")
        for row in material_rows or []
        if row.get("value_type") == "Quality"
        and row.get("variable_code")
        and "CV" in row.get("variable_code").upper()
        and row.get("average_value") is not None
    ]

    average_cv = average(cv_values)

    capacity_used_values = [
        row.get("capacity_used_percent")
        for row in period_rows or []
        if row.get("capacity_used_percent") is not None
    ]

    end_date = None
    if period_rows:
        end_date = period_rows[-1].get("period_end_date")

    return {
        "total_periods": total_periods,
        "total_blocks": int(total_blocks),
        "total_effective_area": total_effective_area,
        "total_volume": total_volume,
        "total_tonnes": total_tonnes,
        "average_density": average_density,
        "average_cv": average_cv,
        "capacity_used_percent": average(capacity_used_values),
        "end_date": end_date,
    }


def get_period_end_date(start_date, period_type):
    period_type = period_type or "Weekly"

    if period_type == "Daily":
        return getdate(start_date)

    if period_type == "Monthly":
        return add_days(add_months(start_date, 1), -1)

    return add_days(start_date, 6)


def get_period_label(period_no, period_type):
    if period_type == "Daily":
        return "Day {0}".format(period_no)

    if period_type == "Monthly":
        return "Month {0}".format(period_no)

    return "Week {0}".format(period_no)


def sum_float(values):
    total = 0.0

    for value in values:
        total += flt_safe(value)

    return total


def average(values):
    clean = [flt_safe(value) for value in values if value is not None]

    if not clean:
        return 0

    return sum(clean) / len(clean)


def flt_safe(value):
    if value is None or value == "":
        return 0.0

    try:
        return float(value)
    except Exception:
        return 0.0


def int_safe(value):
    if value is None or value == "":
        return 0

    try:
        return int(float(value))
    except Exception:
        return 0