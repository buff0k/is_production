import frappe
from frappe import _


@frappe.whitelist()
def get_gant_data(scenario):
    if not scenario:
        frappe.throw(_("Mining Schedule Scenario is required."))

    doc = frappe.get_doc("Mining Schedule Scenario", scenario)

    period_lookup = {}

    for row in doc.periods or []:
        period_lookup[row.period_no] = {
            "period_no": row.period_no,
            "period_label": row.period_label,
            "start": row.period_start_date,
            "end": row.period_end_date,
            "planned_volume": row.planned_volume,
            "planned_tonnes": row.planned_tonnes,
            "planned_block_count": row.planned_block_count,
            "capacity_volume": row.capacity_volume,
            "capacity_tonnes": row.capacity_tonnes,
            "remaining_volume_capacity": row.remaining_volume_capacity,
            "remaining_tonnes_capacity": row.remaining_tonnes_capacity,
            "capacity_used_percent": row.capacity_used_percent,
            "remarks": row.remarks,
        }

    tasks = []

    for row in doc.period_materials or []:
        period = period_lookup.get(row.period_no, {})

        task = {
            "period_no": row.period_no,
            "period_label": row.period_label,
            "start": period.get("start"),
            "end": period.get("end"),
            "task_no": safe_get(row, "task_no"),
            "sequence_no": safe_get(row, "sequence_no"),
            "dependency_group": safe_get(row, "dependency_group"),
            "mining_block": safe_get(row, "mining_block"),
            "mining_block_code": safe_get(row, "mining_block_code"),
            "material_seam": row.material_seam,
            "value_type": row.value_type,
            "variable_code": row.variable_code,
            "variable_name": row.variable_name,
            "mining_unit": safe_get(row, "mining_unit"),
            "scheduled_quantity": safe_get(row, "scheduled_quantity"),
            "scheduled_fraction": safe_get(row, "scheduled_fraction"),
            "effective_area": row.effective_area,
            "volume": row.volume,
            "tonnes": row.tonnes,
            "average_thickness": safe_get(row, "average_thickness"),
            "average_density": safe_get(row, "average_density"),
            "average_value": row.average_value,
            "min_value": row.min_value,
            "max_value": row.max_value,
            "point_count": row.point_count,
            "remarks": row.remarks,
        }

        if not task["mining_unit"]:
            task["mining_unit"] = infer_unit(task)

        if task["scheduled_quantity"] in (None, ""):
            task["scheduled_quantity"] = task["tonnes"] if task["mining_unit"] == "Tonnes" else task["volume"]

        tasks.append(task)

    period_summaries = build_period_summaries(period_lookup, tasks)
    material_summaries = build_material_summaries(tasks)

    return {
        "scenario": {
            "name": doc.name,
            "scenario_name": doc.scenario_name,
            "period_type": doc.period_type,
            "start_date": doc.start_date,
            "end_date": doc.end_date,
            "total_periods": doc.total_periods,
            "total_blocks": doc.total_blocks,
            "total_volume": doc.total_volume,
            "total_tonnes": doc.total_tonnes,
            "average_density": doc.average_density,
            "average_cv": doc.average_cv,
            "capacity_used_percent": doc.capacity_used_percent,
            "source_selection": doc.mining_schedule_selection,
            "geo_project": doc.geo_project,
            "geo_pit_layout": doc.geo_pit_layout,
            "material_stack": doc.material_stack,
        },
        "periods": list(period_lookup.values()),
        "period_summaries": period_summaries,
        "material_summaries": material_summaries,
        "tasks": tasks,
    }


def build_period_summaries(period_lookup, tasks):
    summaries = {}

    for period_no, period in period_lookup.items():
        summaries[period_no] = {
            "period_no": period_no,
            "period_label": period.get("period_label"),
            "start": period.get("start"),
            "end": period.get("end"),
            "capacity_used_percent": period.get("capacity_used_percent"),
            "capacity_volume": period.get("capacity_volume"),
            "capacity_tonnes": period.get("capacity_tonnes"),
            "bcm": 0,
            "tonnes": 0,
            "block_count": 0,
            "material_count": 0,
            "blocks": set(),
            "materials": set(),
        }

    for task in tasks:
        period_no = task.get("period_no")

        if period_no not in summaries:
            summaries[period_no] = {
                "period_no": period_no,
                "period_label": task.get("period_label"),
                "start": task.get("start"),
                "end": task.get("end"),
                "capacity_used_percent": 0,
                "capacity_volume": 0,
                "capacity_tonnes": 0,
                "bcm": 0,
                "tonnes": 0,
                "block_count": 0,
                "material_count": 0,
                "blocks": set(),
                "materials": set(),
            }

        summary = summaries[period_no]
        unit = task.get("mining_unit") or infer_unit(task)
        qty = flt_safe(task.get("scheduled_quantity"))

        if unit == "Tonnes":
            summary["tonnes"] += qty
        else:
            summary["bcm"] += qty

        if task.get("mining_block") or task.get("mining_block_code"):
            summary["blocks"].add(task.get("mining_block") or task.get("mining_block_code"))

        if task.get("material_seam"):
            summary["materials"].add(task.get("material_seam"))

    result = []

    for summary in summaries.values():
        summary["block_count"] = len(summary["blocks"])
        summary["material_count"] = len(summary["materials"])
        summary["blocks"] = sorted(list(summary["blocks"]))
        summary["materials"] = sorted(list(summary["materials"]))
        result.append(summary)

    return sorted(result, key=lambda row: row.get("period_no") or 0)


def build_material_summaries(tasks):
    grouped = {}

    for task in tasks:
        material = task.get("material_seam") or "No Material"
        unit = task.get("mining_unit") or infer_unit(task)
        key = (material, unit)

        if key not in grouped:
            grouped[key] = {
                "material_seam": material,
                "mining_unit": unit,
                "scheduled_quantity": 0,
                "volume": 0,
                "tonnes": 0,
                "periods": set(),
                "blocks": set(),
            }

        item = grouped[key]
        item["scheduled_quantity"] += flt_safe(task.get("scheduled_quantity"))
        item["volume"] += flt_safe(task.get("volume"))
        item["tonnes"] += flt_safe(task.get("tonnes"))

        if task.get("period_label"):
            item["periods"].add(task.get("period_label"))

        if task.get("mining_block") or task.get("mining_block_code"):
            item["blocks"].add(task.get("mining_block") or task.get("mining_block_code"))

    result = []

    for item in grouped.values():
        item["period_count"] = len(item["periods"])
        item["block_count"] = len(item["blocks"])
        item["periods"] = sorted(list(item["periods"]))
        item["blocks"] = sorted(list(item["blocks"]))
        result.append(item)

    return sorted(result, key=lambda row: (row.get("mining_unit") or "", row.get("material_seam") or ""))


def infer_unit(task):
    material = str(task.get("material_seam") or "").lower()

    if any(token in material for token in ["coal", "2u", "2l", "s2u", "s2l"]):
        return "Tonnes"

    if flt_safe(task.get("tonnes")) and not flt_safe(task.get("volume")):
        return "Tonnes"

    return "BCM"


def safe_get(row, fieldname, default=None):
    if not row:
        return default

    if hasattr(row, "get"):
        return row.get(fieldname, default)

    return getattr(row, fieldname, default)


def flt_safe(value):
    try:
        return float(value or 0)
    except Exception:
        return 0