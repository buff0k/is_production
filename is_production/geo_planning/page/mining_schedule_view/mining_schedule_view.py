import json

import frappe
from frappe import _


@frappe.whitelist()
def get_schedule_viewer_data(scenario):
    if not scenario:
        frappe.throw(_("Mining Schedule Scenario is required."))

    doc = frappe.get_doc("Mining Schedule Scenario", scenario)

    block_names = [
        row.mining_block
        for row in doc.scheduled_blocks or []
        if row.mining_block
    ]

    block_geo = {}

    if block_names:
        fields = existing_fields(
            "Mining Block",
            [
                "name",
                "mining_block_code",
                "polygon_geojson",
                "centroid_x",
                "centroid_y",
                "centroid_z",
            ],
        )

        for block in frappe.get_all(
            "Mining Block",
            filters={"name": ["in", block_names]},
            fields=fields,
            limit_page_length=0,
        ):
            block_geo[block.name] = {
                "name": block.name,
                "mining_block_code": safe_get(block, "mining_block_code"),
                "polygon_geojson": parse_json_safely(safe_get(block, "polygon_geojson")),
                "centroid_x": safe_get(block, "centroid_x"),
                "centroid_y": safe_get(block, "centroid_y"),
                "centroid_z": safe_get(block, "centroid_z"),
            }

    return {
        "scenario": {
            "name": doc.name,
            "scenario_name": doc.scenario_name,
            "mining_schedule_selection": doc.mining_schedule_selection,
            "geo_project": doc.geo_project,
            "geo_pit_layout": doc.geo_pit_layout,
            "material_stack": doc.material_stack,
            "period_type": doc.period_type,
            "start_date": doc.start_date,
            "end_date": doc.end_date,
            "schedule_status": doc.schedule_status,
            "total_periods": doc.total_periods,
            "total_blocks": doc.total_blocks,
            "total_effective_area": doc.total_effective_area,
            "total_volume": doc.total_volume,
            "total_tonnes": doc.total_tonnes,
            "average_density": doc.average_density,
            "average_cv": doc.average_cv,
            "capacity_used_percent": doc.capacity_used_percent,
        },
        "periods": [row.as_dict() for row in doc.periods or []],
        "scheduled_blocks": [row.as_dict() for row in doc.scheduled_blocks or []],
        "period_materials": [row.as_dict() for row in doc.period_materials or []],
        "block_geo": block_geo,
    }


def parse_json_safely(value):
    if not value:
        return None

    if isinstance(value, dict):
        return value

    if isinstance(value, list):
        return value

    try:
        return json.loads(value)
    except Exception:
        return None


def existing_fields(doctype, fields):
    meta = frappe.get_meta(doctype)
    clean = []

    for fieldname in fields:
        if fieldname == "name" or meta.has_field(fieldname):
            if fieldname not in clean:
                clean.append(fieldname)

    if "name" not in clean:
        clean.insert(0, "name")

    return clean


def safe_get(row, fieldname, default=None):
    if not row:
        return default

    if hasattr(row, "get"):
        return row.get(fieldname, default)

    return getattr(row, fieldname, default)