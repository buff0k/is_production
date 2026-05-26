import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, add_months, flt, getdate, now_datetime


@frappe.whitelist()
def get_schedule_rule_context(mining_schedule_selection=None, scenario=None):
    if scenario and not mining_schedule_selection:
        scenario_doc = frappe.get_doc("Mining Schedule Scenario", scenario)
        mining_schedule_selection = scenario_doc.mining_schedule_selection

    source = get_valid_selection(mining_schedule_selection)
    stack_sequence = get_material_stack_sequence(source.material_stack)

    materials = []
    seen = set()

    for item in stack_sequence:
        material = item.get("material_seam")
        if material and normalise(material) not in seen:
            seen.add(normalise(material))
            materials.append(material)

    for row in source.materials or []:
        material = row.material_seam
        if material and normalise(material) not in seen:
            seen.add(normalise(material))
            materials.append(material)

    default_rules = []
    for index, material in enumerate(materials, start=1):
        default_rules.append(
            {
                "rule_no": index,
                "material_code": material,
                "rule_note": "",
            }
        )

    return {
        "material_options": materials,
        "default_rules": default_rules,
    }


@frappe.whitelist()
def create_schedule_scenario_from_selection(
    mining_schedule_selection,
    scenario_name,
    period_type="Weekly",
    start_date=None,
    coal_materials=None,
    mining_rule_application="Inside Each Block",
    mining_rules_json=None,
    number_of_teams=1,
    team_capacity_per_hour=0,
    weekday_shifts=0,
    weekday_hours_per_shift=0,
    saturday_shifts=0,
    saturday_hours_per_shift=0,
    sunday_shifts=0,
    sunday_hours_per_shift=0,
    availability_percent=100,
    utilisation_percent=100,
    drilling_required=0,
    drilling_materials=None,
    drilling_hours_per_block_material=0,
    remarks=None,
    **kwargs
):
    source = get_valid_selection(mining_schedule_selection)

    settings = build_settings(
        scenario_name=scenario_name,
        period_type=period_type,
        start_date=start_date,
        coal_materials=coal_materials,
        mining_rule_application=mining_rule_application,
        mining_rules_json=mining_rules_json,
        number_of_teams=number_of_teams,
        team_capacity_per_hour=team_capacity_per_hour,
        weekday_shifts=weekday_shifts,
        weekday_hours_per_shift=weekday_hours_per_shift,
        saturday_shifts=saturday_shifts,
        saturday_hours_per_shift=saturday_hours_per_shift,
        sunday_shifts=sunday_shifts,
        sunday_hours_per_shift=sunday_hours_per_shift,
        availability_percent=availability_percent,
        utilisation_percent=utilisation_percent,
        drilling_required=drilling_required,
        drilling_materials=drilling_materials,
        drilling_hours_per_block_material=drilling_hours_per_block_material,
        remarks=remarks,
    )

    if not settings["scenario_name"]:
        frappe.throw(_("Scenario Name is required."))

    if not settings["start_date"]:
        frappe.throw(_("Start Date is required."))

    generated = generate_schedule_rows(source, settings)

    doc = frappe.get_doc(
        build_scenario_doc_data(
            source=source,
            settings=settings,
            generated=generated,
            existing_doc=None,
        )
    )
    doc.insert()

    return result_dict(doc)


@frappe.whitelist()
def update_schedule_scenario_from_inputs(
    scenario,
    scenario_name,
    period_type="Weekly",
    start_date=None,
    coal_materials=None,
    mining_rule_application="Inside Each Block",
    mining_rules_json=None,
    number_of_teams=1,
    team_capacity_per_hour=0,
    weekday_shifts=0,
    weekday_hours_per_shift=0,
    saturday_shifts=0,
    saturday_hours_per_shift=0,
    sunday_shifts=0,
    sunday_hours_per_shift=0,
    availability_percent=100,
    utilisation_percent=100,
    drilling_required=0,
    drilling_materials=None,
    drilling_hours_per_block_material=0,
    remarks=None,
    **kwargs
):
    if not scenario:
        frappe.throw(_("Mining Schedule Scenario is required."))

    doc = frappe.get_doc("Mining Schedule Scenario", scenario)

    if not doc.mining_schedule_selection:
        frappe.throw(_("Scenario has no Source Selection."))

    source = get_valid_selection(doc.mining_schedule_selection)

    settings = build_settings(
        scenario_name=scenario_name,
        period_type=period_type,
        start_date=start_date,
        coal_materials=coal_materials,
        mining_rule_application=mining_rule_application,
        mining_rules_json=mining_rules_json,
        number_of_teams=number_of_teams,
        team_capacity_per_hour=team_capacity_per_hour,
        weekday_shifts=weekday_shifts,
        weekday_hours_per_shift=weekday_hours_per_shift,
        saturday_shifts=saturday_shifts,
        saturday_hours_per_shift=saturday_hours_per_shift,
        sunday_shifts=sunday_shifts,
        sunday_hours_per_shift=sunday_hours_per_shift,
        availability_percent=availability_percent,
        utilisation_percent=utilisation_percent,
        drilling_required=drilling_required,
        drilling_materials=drilling_materials,
        drilling_hours_per_block_material=drilling_hours_per_block_material,
        remarks=remarks,
    )

    generated = generate_schedule_rows(source, settings)
    data = build_scenario_doc_data(source, settings, generated, existing_doc=doc)

    for key, value in data.items():
        if key in ("doctype", "name"):
            continue
        if key in ("periods", "scheduled_blocks", "period_materials"):
            doc.set(key, value)
        elif doc.meta.has_field(key):
            doc.set(key, value)

    doc.save()
    return result_dict(doc)


@frappe.whitelist()
def get_schedule_scenario_inputs(scenario):
    doc = frappe.get_doc("Mining Schedule Scenario", scenario)

    defaults = {
        "scenario_name": doc.scenario_name,
        "period_type": doc.period_type,
        "start_date": doc.start_date,
        "remarks": doc.remarks,
    }

    if not doc.source_filters_json:
        return defaults

    try:
        source = json.loads(doc.source_filters_json)
    except Exception:
        return defaults

    settings = source.get("settings") or {}
    defaults.update(settings)

    if isinstance(defaults.get("coal_materials"), list):
        defaults["coal_materials"] = ",".join(defaults["coal_materials"])

    if isinstance(defaults.get("drilling_materials"), list):
        defaults["drilling_materials"] = ",".join(defaults["drilling_materials"])

    if isinstance(defaults.get("mining_rules_json"), list):
        defaults["mining_rules_json"] = json.dumps(defaults["mining_rules_json"])

    return defaults


@frappe.whitelist()
def regenerate_schedule_scenario(name):
    defaults = get_schedule_scenario_inputs(name)
    defaults["scenario"] = name
    return update_schedule_scenario_from_inputs(**defaults)


def get_valid_selection(name):
    if not name:
        frappe.throw(_("Mining Schedule Selection is required."))

    source = frappe.get_doc("Mining Schedule Selection", name)

    if not source.blocks:
        frappe.throw(_("Source selection has no selected block rows."))

    if not source.materials:
        frappe.throw(_("Source selection has no material rows."))

    return source


def build_settings(**kwargs):
    period_type = kwargs.get("period_type") or "Weekly"

    availability_factor = flt(kwargs.get("availability_percent")) / 100
    utilisation_factor = flt(kwargs.get("utilisation_percent")) / 100

    hourly_capacity = (
        flt(kwargs.get("number_of_teams"))
        * flt(kwargs.get("team_capacity_per_hour"))
        * availability_factor
        * utilisation_factor
    )

    period_hours = calculate_period_hours(
        period_type=period_type,
        weekday_shifts=kwargs.get("weekday_shifts"),
        weekday_hours_per_shift=kwargs.get("weekday_hours_per_shift"),
        saturday_shifts=kwargs.get("saturday_shifts"),
        saturday_hours_per_shift=kwargs.get("saturday_hours_per_shift"),
        sunday_shifts=kwargs.get("sunday_shifts"),
        sunday_hours_per_shift=kwargs.get("sunday_hours_per_shift"),
    )

    return {
        "scenario_name": kwargs.get("scenario_name"),
        "period_type": period_type,
        "start_date": kwargs.get("start_date"),
        "coal_materials": split_keywords(kwargs.get("coal_materials")) or ["coal", "2u", "2l", "s2u", "s2l"],
        "mining_rule_application": kwargs.get("mining_rule_application") or "Inside Each Block",
        "mining_rules_json": parse_rules(kwargs.get("mining_rules_json")),
        "number_of_teams": flt(kwargs.get("number_of_teams")),
        "team_capacity_per_hour": flt(kwargs.get("team_capacity_per_hour")),
        "weekday_shifts": flt(kwargs.get("weekday_shifts")),
        "weekday_hours_per_shift": flt(kwargs.get("weekday_hours_per_shift")),
        "saturday_shifts": flt(kwargs.get("saturday_shifts")),
        "saturday_hours_per_shift": flt(kwargs.get("saturday_hours_per_shift")),
        "sunday_shifts": flt(kwargs.get("sunday_shifts")),
        "sunday_hours_per_shift": flt(kwargs.get("sunday_hours_per_shift")),
        "availability_percent": flt(kwargs.get("availability_percent")),
        "utilisation_percent": flt(kwargs.get("utilisation_percent")),
        "availability_factor": availability_factor,
        "utilisation_factor": utilisation_factor,
        "effective_period_hours": period_hours,
        "hourly_capacity": hourly_capacity,
        "period_capacity": hourly_capacity * period_hours,
        "drilling_required": int(flt(kwargs.get("drilling_required"))),
        "drilling_materials": split_keywords(kwargs.get("drilling_materials")),
        "drilling_hours_per_block_material": flt(kwargs.get("drilling_hours_per_block_material")),
        "remarks": kwargs.get("remarks"),
    }


def calculate_period_hours(
    period_type,
    weekday_shifts,
    weekday_hours_per_shift,
    saturday_shifts,
    saturday_hours_per_shift,
    sunday_shifts,
    sunday_hours_per_shift,
):
    weekday_hours = flt(weekday_shifts) * flt(weekday_hours_per_shift)
    saturday_hours = flt(saturday_shifts) * flt(saturday_hours_per_shift)
    sunday_hours = flt(sunday_shifts) * flt(sunday_hours_per_shift)

    weekly_hours = weekday_hours * 5 + saturday_hours + sunday_hours

    if period_type == "Daily":
        return weekday_hours

    if period_type == "Monthly":
        return weekly_hours * 4.345

    return weekly_hours


def generate_schedule_rows(source, settings):
    stack_sequence = get_material_stack_sequence(source.material_stack)
    tasks = build_material_tasks_from_selection(source, stack_sequence, settings)

    if not tasks:
        frappe.throw(_("No schedulable material tasks were created."))

    allocations = allocate_tasks_to_periods(tasks, settings)
    period_rows = build_period_rows(allocations)
    scheduled_block_rows = build_scheduled_block_rows(allocations)
    period_material_rows = build_period_material_rows(allocations)
    totals = calculate_scenario_totals(period_rows, period_material_rows)

    return {
        "stack_sequence": stack_sequence,
        "tasks": tasks,
        "allocations": allocations,
        "period_rows": period_rows,
        "scheduled_block_rows": scheduled_block_rows,
        "period_material_rows": period_material_rows,
        "totals": totals,
    }


def build_scenario_doc_data(source, settings, generated, existing_doc=None):
    totals = generated["totals"]

    source_filters = {
        "source_selection": source.name,
        "source_selection_name": source.selection_name,
        "sequence_basis": "Mining Schedule Selection Block.sequence_no",
        "material_order_basis": "Custom rules if provided, otherwise Material Stack mining_sequence_no",
        "unit_rule": "Coal materials are scheduled in tonnes. All other materials are scheduled in BCM.",
        "settings": settings,
        "stack_sequence": generated["stack_sequence"],
    }

    doc_data = {
        "doctype": "Mining Schedule Scenario",
        "scenario_name": settings["scenario_name"],
        "mining_schedule_selection": source.name,
        "geo_project": source.geo_project,
        "geo_pit_layout": source.geo_pit_layout,
        "material_stack": source.material_stack,
        "schedule_status": "Generated",
        "period_type": settings["period_type"],
        "start_date": settings["start_date"],
        "end_date": totals.get("end_date"),
        "schedule_basis": "Fleet Capacity",
        "target_tonnes_per_period": settings["period_capacity"],
        "target_volume_per_period": settings["period_capacity"],
        "number_of_shifts": settings["weekday_shifts"],
        "hours_per_shift": settings["weekday_hours_per_shift"],
        "fleet_capacity_bcm_per_hour": settings["hourly_capacity"],
        "fleet_capacity_tonnes_per_hour": settings["hourly_capacity"],
        "drill_blast_required": settings["drilling_required"],
        "drill_blast_lead_time_days": 0,
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
        "source_filters_json": json.dumps(source_filters, indent=2, default=str),
        "remarks": settings.get("remarks"),
        "periods": generated["period_rows"],
        "scheduled_blocks": generated["scheduled_block_rows"],
        "period_materials": generated["period_material_rows"],
    }

    if existing_doc:
        doc_data["name"] = existing_doc.name

    return filter_parent_fields("Mining Schedule Scenario", doc_data)


def build_material_tasks_from_selection(source, stack_sequence, settings):
    material_by_block = defaultdict(list)

    for row in source.materials or []:
        if row.mining_block:
            material_by_block[row.mining_block].append(row)

    selected_blocks = sorted(
        source.blocks or [],
        key=lambda row: (
            int_safe(row.sequence_no) or 999999,
            row.idx or 999999,
            row.mining_block or "",
        ),
    )

    block_packages = []

    for block_row in selected_blocks:
        block_materials = material_by_block.get(block_row.mining_block, [])
        packages = build_material_packages_for_block(block_materials, stack_sequence, settings)

        if packages:
            block_packages.append(
                {
                    "block_row": block_row,
                    "packages": packages,
                }
            )

    ordered_pairs = order_block_material_pairs(block_packages, settings)

    tasks = []
    task_no = 0

    for pair in ordered_pairs:
        task_no += 1

        block_row = pair["block_row"]
        package = pair["package"]

        hourly_capacity = settings["hourly_capacity"]
        duration_hours = package["quantity"] / hourly_capacity if hourly_capacity else 0

        if settings["drilling_required"] and matches_any(package["material_seam"], settings["drilling_materials"]):
            duration_hours += settings["drilling_hours_per_block_material"]

        tasks.append(
            {
                "task_no": task_no,
                "block_sequence_no": int_safe(block_row.sequence_no),
                "dependency_group": block_row.dependency_group,
                "mining_block": block_row.mining_block,
                "mining_block_code": block_row.mining_block_code,
                "geo_project": block_row.geo_project,
                "source_pit_layout": block_row.source_pit_layout,
                "cut_no": block_row.cut_no,
                "block_no": block_row.block_no,
                "row_no": block_row.row_no,
                "column_no": block_row.column_no,
                "effective_area": flt(block_row.effective_area),
                "material_sequence_no": package["material_sequence_no"],
                "material_seam": package["material_seam"],
                "value_type": package["value_type"],
                "variable_code": package["variable_code"],
                "variable_name": package["variable_name"],
                "mining_unit": package["mining_unit"],
                "quantity": package["quantity"],
                "volume": package["volume"],
                "tonnes": package["tonnes"],
                "average_thickness": package["average_thickness"],
                "average_density": package["average_density"],
                "average_value": package["average_value"],
                "min_value": package["min_value"],
                "max_value": package["max_value"],
                "point_count": package["point_count"],
                "hourly_capacity": hourly_capacity,
                "duration_hours": duration_hours,
                "is_coal": package["is_coal"],
                "remarks": package["remarks"],
            }
        )

    return tasks


def order_block_material_pairs(block_packages, settings):
    rules = settings.get("mining_rules_json") or []
    application = settings.get("mining_rule_application") or "Inside Each Block"

    if not rules:
        ordered = []
        for item in block_packages:
            for package in item["packages"]:
                ordered.append({"block_row": item["block_row"], "package": package})
        return ordered

    rule_order = {}
    for index, rule in enumerate(sorted(rules, key=lambda r: int_safe(r.get("rule_no")) or 999999), start=1):
        material_code = normalise(rule.get("material_code"))
        if material_code:
            rule_order[material_code] = index

    def package_sort_key(package):
        material_key = normalise(package["material_seam"])
        return (
            rule_order.get(material_key, 999999),
            int_safe(package.get("material_sequence_no")) or 999999,
            material_key,
        )

    if application == "Across All Blocks Then Next Rule":
        pairs = []
        for item in block_packages:
            for package in item["packages"]:
                pairs.append({"block_row": item["block_row"], "package": package})

        return sorted(
            pairs,
            key=lambda pair: (
                package_sort_key(pair["package"]),
                int_safe(pair["block_row"].sequence_no) or 999999,
                pair["block_row"].idx or 999999,
            ),
        )

    ordered = []

    for item in block_packages:
        packages = sorted(item["packages"], key=package_sort_key)
        for package in packages:
            ordered.append({"block_row": item["block_row"], "package": package})

    return ordered


def build_material_packages_for_block(material_rows, stack_sequence, settings):
    grouped = {}

    for row in material_rows:
        material_seam = row.material_seam or "No Seam"

        if material_seam not in grouped:
            grouped[material_seam] = {
                "material_seam": material_seam,
                "volume": 0,
                "tonnes": 0,
                "seen_summary_keys": set(),
                "thickness_values": [],
                "density_values": [],
                "quality_values": [],
                "min_values": [],
                "max_values": [],
                "point_count": 0,
                "variable_code": row.variable_code or "",
                "variable_name": row.variable_name or "",
                "value_type": row.value_type or "Thickness",
            }

        item = grouped[material_seam]

        summary_key = safe_get(row, "material_summary") or safe_get(row, "source_geology_result") or row.name

        if summary_key not in item["seen_summary_keys"]:
            item["volume"] += flt(row.volume)
            item["tonnes"] += flt(row.tonnes)
            item["seen_summary_keys"].add(summary_key)

        if row.thickness_value is not None:
            item["thickness_values"].append(flt(row.thickness_value))

        if row.density_value is not None:
            item["density_values"].append(flt(row.density_value))

        if row.avg_value is not None:
            item["quality_values"].append(flt(row.avg_value))

        if row.min_value is not None:
            item["min_values"].append(flt(row.min_value))

        if row.max_value is not None:
            item["max_values"].append(flt(row.max_value))

        item["point_count"] += int_safe(row.point_count)

    packages = []

    for material_seam, item in grouped.items():
        is_coal = matches_any(material_seam, settings["coal_materials"])
        mining_unit = "Tonnes" if is_coal else "BCM"
        quantity = item["tonnes"] if is_coal else item["volume"]

        if quantity <= 0:
            continue

        seq = get_sequence_info(material_seam, stack_sequence)

        packages.append(
            {
                "material_sequence_no": seq["sequence_no"],
                "material_seam": material_seam,
                "value_type": item["value_type"],
                "variable_code": item["variable_code"],
                "variable_name": item["variable_name"],
                "mining_unit": mining_unit,
                "quantity": quantity,
                "volume": item["volume"],
                "tonnes": item["tonnes"],
                "average_thickness": average(item["thickness_values"]),
                "average_density": average(item["density_values"]),
                "average_value": average(item["quality_values"]),
                "min_value": min(item["min_values"]) if item["min_values"] else None,
                "max_value": max(item["max_values"]) if item["max_values"] else None,
                "point_count": item["point_count"],
                "is_coal": is_coal,
                "remarks": "Coal scheduled in tonnes." if is_coal else "Non-coal scheduled in BCM.",
            }
        )

    return sorted(
        packages,
        key=lambda row: (
            int_safe(row["material_sequence_no"]) or 999999,
            row["material_seam"] or "",
        ),
    )


def allocate_tasks_to_periods(tasks, settings):
    period_type = settings["period_type"]
    period_no = 1
    period_start = getdate(settings["start_date"])
    period_end = get_period_end_date(period_start, period_type)

    period_capacity = flt(settings["period_capacity"])
    remaining = {"BCM": period_capacity, "Tonnes": period_capacity}

    allocations = []
    current = make_period(period_no, period_type, period_start, period_end, period_capacity)

    for task in tasks:
        quantity_left = flt(task["quantity"])

        while quantity_left > 0:
            unit = task["mining_unit"]

            if period_capacity > 0 and remaining[unit] <= 0:
                allocations.append(current)
                period_no += 1
                period_start = add_days(period_end, 1)
                period_end = get_period_end_date(period_start, period_type)
                remaining = {"BCM": period_capacity, "Tonnes": period_capacity}
                current = make_period(period_no, period_type, period_start, period_end, period_capacity)

            scheduled_quantity = quantity_left if period_capacity <= 0 else min(quantity_left, remaining[unit])
            fraction = scheduled_quantity / flt(task["quantity"]) if flt(task["quantity"]) else 0

            scheduled_task = dict(task)
            scheduled_task["scheduled_quantity"] = scheduled_quantity
            scheduled_task["scheduled_fraction"] = fraction
            scheduled_task["scheduled_volume"] = flt(task["volume"]) * fraction
            scheduled_task["scheduled_tonnes"] = flt(task["tonnes"]) * fraction
            scheduled_task["scheduled_duration_hours"] = flt(task["duration_hours"]) * fraction
            scheduled_task["period_no"] = current["period_no"]
            scheduled_task["period_label"] = current["period_label"]
            scheduled_task["period_start_date"] = current["period_start_date"]
            scheduled_task["period_end_date"] = current["period_end_date"]

            current["tasks"].append(scheduled_task)
            quantity_left -= scheduled_quantity

            if period_capacity > 0:
                remaining[unit] -= scheduled_quantity
            else:
                break

    allocations.append(current)
    return [period for period in allocations if period["tasks"]]


def make_period(period_no, period_type, start_date, end_date, period_capacity):
    return {
        "period_no": period_no,
        "period_label": get_period_label(period_no, period_type),
        "period_start_date": start_date,
        "period_end_date": end_date,
        "capacity_volume": period_capacity,
        "capacity_tonnes": period_capacity,
        "tasks": [],
    }


def build_period_rows(allocations):
    rows = []

    for allocation in allocations:
        total_volume = sum(flt(task["scheduled_volume"]) for task in allocation["tasks"])
        total_tonnes = sum(flt(task["scheduled_tonnes"]) for task in allocation["tasks"])
        bcm_used = sum(flt(task["scheduled_quantity"]) for task in allocation["tasks"] if task["mining_unit"] == "BCM")
        coal_used = sum(flt(task["scheduled_quantity"]) for task in allocation["tasks"] if task["mining_unit"] == "Tonnes")

        capacity_volume = flt(allocation["capacity_volume"])
        capacity_tonnes = flt(allocation["capacity_tonnes"])

        bcm_used_percent = bcm_used / capacity_volume * 100 if capacity_volume else 0
        coal_used_percent = coal_used / capacity_tonnes * 100 if capacity_tonnes else 0

        rows.append(
            filter_child_fields(
                "Mining Schedule Period",
                {
                    "period_no": allocation["period_no"],
                    "period_label": allocation["period_label"],
                    "period_start_date": allocation["period_start_date"],
                    "period_end_date": allocation["period_end_date"],
                    "planned_block_count": len(set(task["mining_block"] for task in allocation["tasks"])),
                    "planned_effective_area": sum_unique_block_area(allocation["tasks"]),
                    "planned_volume": total_volume,
                    "planned_tonnes": total_tonnes,
                    "average_density": total_tonnes / total_volume if total_volume else 0,
                    "average_cv": calculate_average_cv(allocation["tasks"]),
                    "capacity_volume": capacity_volume,
                    "capacity_tonnes": capacity_tonnes,
                    "capacity_used_percent": max(bcm_used_percent, coal_used_percent),
                    "remaining_volume_capacity": capacity_volume - bcm_used if capacity_volume else 0,
                    "remaining_tonnes_capacity": capacity_tonnes - coal_used if capacity_tonnes else 0,
                    "remarks": "BCM used: {0:.2f}%. Coal tonnes used: {1:.2f}%.".format(bcm_used_percent, coal_used_percent),
                },
            )
        )

    return rows


def build_scheduled_block_rows(allocations):
    grouped = {}

    for allocation in allocations:
        for task in allocation["tasks"]:
            key = (allocation["period_no"], task["mining_block"])

            if key not in grouped:
                grouped[key] = {
                    "period_no": allocation["period_no"],
                    "period_label": allocation["period_label"],
                    "sequence_no": task["block_sequence_no"],
                    "dependency_group": task["dependency_group"],
                    "mining_block": task["mining_block"],
                    "mining_block_code": task["mining_block_code"],
                    "geo_project": task["geo_project"],
                    "source_pit_layout": task["source_pit_layout"],
                    "cut_no": task["cut_no"],
                    "block_no": task["block_no"],
                    "row_no": task["row_no"],
                    "column_no": task["column_no"],
                    "effective_area": task["effective_area"],
                    "total_volume": 0,
                    "total_tonnes": 0,
                    "planned_start_date": allocation["period_start_date"],
                    "planned_end_date": allocation["period_end_date"],
                    "schedule_status": "Planned",
                    "materials": [],
                }

            item = grouped[key]
            item["total_volume"] += flt(task["scheduled_volume"])
            item["total_tonnes"] += flt(task["scheduled_tonnes"])
            item["materials"].append(
                "{0}: {1:.2f} {2}".format(task["material_seam"], task["scheduled_quantity"], task["mining_unit"])
            )

    rows = []

    for item in grouped.values():
        item["average_density"] = item["total_tonnes"] / item["total_volume"] if item["total_volume"] else 0
        item["remarks"] = "Materials mined: " + "; ".join(item.pop("materials", []))
        rows.append(filter_child_fields("Mining Schedule Block", item))

    return rows


def build_period_material_rows(allocations):
    rows = []
    meta = frappe.get_meta("Mining Schedule Period Material")
    supports_detail = bool(meta.has_field("mining_block"))

    if supports_detail:
        for allocation in allocations:
            for task in allocation["tasks"]:
                rows.append(
                    filter_child_fields(
                        "Mining Schedule Period Material",
                        {
                            "period_no": allocation["period_no"],
                            "period_label": allocation["period_label"],
                            "task_no": task["task_no"],
                            "sequence_no": task["block_sequence_no"],
                            "dependency_group": task["dependency_group"],
                            "mining_block": task["mining_block"],
                            "mining_block_code": task["mining_block_code"],
                            "material_seam": task["material_seam"],
                            "value_type": task["value_type"],
                            "variable_code": task["variable_code"],
                            "variable_name": task["variable_name"],
                            "mining_unit": task["mining_unit"],
                            "scheduled_quantity": task["scheduled_quantity"],
                            "scheduled_fraction": task["scheduled_fraction"],
                            "effective_area": task["effective_area"] * task["scheduled_fraction"],
                            "volume": task["scheduled_volume"],
                            "tonnes": task["scheduled_tonnes"],
                            "average_thickness": task["average_thickness"],
                            "average_density": task["average_density"],
                            "average_value": task["average_value"],
                            "min_value": task["min_value"],
                            "max_value": task["max_value"],
                            "point_count": task["point_count"],
                            "remarks": "{0} scheduled in {1}.".format(task["material_seam"], task["mining_unit"]),
                        },
                    )
                )
        return rows

    grouped = {}

    for allocation in allocations:
        for task in allocation["tasks"]:
            key = (allocation["period_no"], task["material_seam"], task["mining_unit"], task["variable_code"])

            if key not in grouped:
                grouped[key] = {
                    "period_no": allocation["period_no"],
                    "period_label": allocation["period_label"],
                    "material_seam": task["material_seam"],
                    "value_type": task["value_type"],
                    "variable_code": task["variable_code"],
                    "variable_name": task["variable_name"],
                    "block_names": set(),
                    "effective_area": 0,
                    "volume": 0,
                    "tonnes": 0,
                    "thickness_values": [],
                    "density_values": [],
                    "value_values": [],
                    "min_values": [],
                    "max_values": [],
                    "point_count": 0,
                }

            item = grouped[key]
            item["block_names"].add(task["mining_block"])
            item["effective_area"] += flt(task["effective_area"]) * flt(task["scheduled_fraction"])
            item["volume"] += flt(task["scheduled_volume"])
            item["tonnes"] += flt(task["scheduled_tonnes"])
            item["point_count"] += int_safe(task["point_count"])

            for src, dest in [
                ("average_thickness", "thickness_values"),
                ("average_density", "density_values"),
                ("average_value", "value_values"),
                ("min_value", "min_values"),
                ("max_value", "max_values"),
            ]:
                if task.get(src) is not None:
                    item[dest].append(flt(task.get(src)))

    for item in grouped.values():
        rows.append(
            filter_child_fields(
                "Mining Schedule Period Material",
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
                    "average_value": average(item["value_values"]),
                    "min_value": min(item["min_values"]) if item["min_values"] else None,
                    "max_value": max(item["max_values"]) if item["max_values"] else None,
                    "point_count": item["point_count"],
                    "remarks": "Grouped output. Add block-detail fields to see material by block.",
                },
            )
        )

    return rows


def get_material_stack_sequence(material_stack):
    if not material_stack or not frappe.db.exists("Geo Pit Layout Material Stack", material_stack):
        return []

    doc = frappe.get_doc("Geo Pit Layout Material Stack", material_stack)
    table_field = get_first_table_field(doc)

    if not table_field:
        return []

    sequence = []

    for row in doc.get(table_field) or []:
        material_seam = safe_get(row, "material_seam")
        if not material_seam:
            continue

        sequence.append(
            {
                "material_seam": material_seam,
                "sequence_no": int_safe(safe_get(row, "mining_sequence_no")) or 999999,
                "idx": row.idx,
            }
        )

    return sorted(sequence, key=lambda item: (item["sequence_no"], item["idx"]))


def get_sequence_info(material_seam, stack_sequence):
    for item in stack_sequence:
        if normalise(item["material_seam"]) == normalise(material_seam):
            return item

    return {"material_seam": material_seam, "sequence_no": 999999, "idx": 999999}


def calculate_scenario_totals(period_rows, material_rows):
    total_periods = len(period_rows or [])
    total_blocks = sum(flt(row.get("planned_block_count")) for row in period_rows or [])
    total_effective_area = sum(flt(row.get("planned_effective_area")) for row in period_rows or [])
    total_volume = sum(flt(row.get("planned_volume")) for row in period_rows or [])
    total_tonnes = sum(flt(row.get("planned_tonnes")) for row in period_rows or [])

    capacity_values = [
        flt(row.get("capacity_used_percent"))
        for row in period_rows or []
        if row.get("capacity_used_percent") is not None
    ]

    return {
        "total_periods": total_periods,
        "total_blocks": int(total_blocks),
        "total_effective_area": total_effective_area,
        "total_volume": total_volume,
        "total_tonnes": total_tonnes,
        "average_density": total_tonnes / total_volume if total_volume else 0,
        "average_cv": calculate_average_cv(material_rows),
        "capacity_used_percent": average(capacity_values),
        "end_date": period_rows[-1].get("period_end_date") if period_rows else None,
    }


def get_period_end_date(start_date, period_type):
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


def get_first_table_field(doc):
    for field in frappe.get_meta(doc.doctype).fields:
        if field.fieldtype == "Table":
            return field.fieldname
    return None


def filter_parent_fields(doctype, data):
    meta = frappe.get_meta(doctype)
    clean = {"doctype": doctype}

    if data.get("name"):
        clean["name"] = data.get("name")

    for key, value in data.items():
        if key in ("doctype", "name"):
            continue
        if meta.has_field(key):
            clean[key] = value

    return clean


def filter_child_fields(doctype, data):
    meta = frappe.get_meta(doctype)
    return {key: value for key, value in data.items() if meta.has_field(key)}


def parse_rules(value):
    if not value:
        return []

    if isinstance(value, list):
        return value

    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def split_keywords(value):
    if not value:
        return []
    if isinstance(value, list):
        return [normalise(item) for item in value if item]
    return [normalise(item) for item in str(value).split(",") if item.strip()]


def matches_any(value, keywords):
    value = normalise(value)
    return any(keyword and keyword in value for keyword in keywords or [])


def normalise(value):
    return str(value or "").strip().lower()


def safe_get(row, fieldname):
    if hasattr(row, "get"):
        return row.get(fieldname)
    return getattr(row, fieldname, None)


def sum_unique_block_area(tasks):
    seen = {}
    for task in tasks:
        if task["mining_block"] not in seen:
            seen[task["mining_block"]] = flt(task["effective_area"])
    return sum(seen.values())


def calculate_average_cv(rows):
    values = []

    for row in rows or []:
        variable_code = (row.get("variable_code") or "").upper()
        if "CV" in variable_code and row.get("average_value") is not None:
            values.append(flt(row.get("average_value")))

    return average(values)


def average(values):
    clean = [flt(value) for value in values or [] if value is not None]
    return sum(clean) / len(clean) if clean else 0


def int_safe(value):
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def result_dict(doc):
    return {
        "name": doc.name,
        "scenario_name": doc.scenario_name,
        "total_periods": doc.total_periods,
        "total_blocks": doc.total_blocks,
        "total_volume": doc.total_volume,
        "total_tonnes": doc.total_tonnes,
    }