import frappe

_ALLOWED_GENERATE_KEYS = {
    "scenario_name", "geo_project", "geo_pit_layout", "material_stack",
    "material_seam", "value_type", "start_date", "end_date",
    "shift_hours_weekday", "shift_hours_saturday", "shift_hours_sunday",
    "shifts_per_weekday", "shifts_per_saturday", "shifts_per_sunday",
    "number_of_excavators", "capacity_per_excavator_hour",
    "utilisation_percent", "availability_percent",
    "schedule_method", "overwrite_existing",
}


def _clean_kwargs(kwargs):
    return {k: v for k, v in (kwargs or {}).items() if k in _ALLOWED_GENERATE_KEYS}


@frappe.whitelist()
def generate_schedule(**kwargs):
    from is_production.geo_planning.services.schedule_simulation_service import create_and_generate_schedule
    return create_and_generate_schedule(**_clean_kwargs(kwargs))


@frappe.whitelist()
def get_schedule_summary(schedule_scenario=None):
    from is_production.geo_planning.services.schedule_simulation_service import get_schedule_summary
    return get_schedule_summary(schedule_scenario)


@frappe.whitelist()
def get_animation_payload(schedule_scenario=None):
    from is_production.geo_planning.services.schedule_simulation_service import get_animation_payload
    return get_animation_payload(schedule_scenario)


@frappe.whitelist()
def get_recent_schedule_scenarios(txt="", limit=20):
    txt = txt or ""
    where = "WHERE scenario_name LIKE %(txt)s OR name LIKE %(txt)s" if txt else ""
    return frappe.db.sql(
        f"""
        SELECT
            name AS value,
            CONCAT(COALESCE(scenario_name, name), ' | ', COALESCE(material_seam, ''), ' | ', COALESCE(total_scheduled_blocks, 0), ' completed blocks') AS description
        FROM `tabMine Schedule Scenario`
        {where}
        ORDER BY modified DESC
        LIMIT %(limit)s
        """,
        {"txt": f"%{txt}%", "limit": int(limit or 20)},
        as_dict=True,
    )


@frappe.whitelist()
def get_stack_material_items(material_stack=None):
    if not material_stack:
        return []

    stack = frappe.get_doc("Geo Pit Layout Material Stack", material_stack)
    items = []

    for row in stack.get("item") or []:
        material_seam = (row.material_seam or "").strip()
        value_type = (row.value_type or "").strip()

        if not material_seam:
            continue

        items.append({
            "label": f"{material_seam} | {value_type or ''}",
            "material_seam": material_seam,
            "value_type": value_type,
            "sort_order": row.sort_order,
            "geology_run": row.geology_run,
            "use_for_volume": row.use_for_volume,
            "use_for_tonnes": row.use_for_tonnes,
            "use_for_scheduling": row.use_for_scheduling,
        })

    return sorted(items, key=lambda x: ((x.get("sort_order") or 0), x.get("material_seam") or ""))
