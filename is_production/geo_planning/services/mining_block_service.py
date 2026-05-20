import json

import frappe
from frappe.utils import now


def _int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _has_field(doctype, fieldname):
    try:
        return frappe.get_meta(doctype).has_field(fieldname)
    except Exception:
        return False


def _set_if_field(doc, fieldname, value):
    if _has_field(doc.doctype, fieldname):
        setattr(doc, fieldname, value)


def _safe_json(value):
    try:
        return json.dumps(value, default=str)
    except Exception:
        return "{}"


def _get_layout(geo_pit_layout):
    if not geo_pit_layout:
        frappe.throw("Geo Pit Layout is required.")

    return frappe.get_doc("Geo Pit Layout", geo_pit_layout)


def _get_layout_blocks(geo_pit_layout):
    blocks = frappe.get_all(
        "Geo Pit Layout Block",
        filters={"geo_pit_layout": geo_pit_layout},
        fields=[
            "name",
            "geo_pit_layout",
            "geo_project",
            "block_code",
            "cut_no",
            "block_no",
            "row_no",
            "column_no",
            "centroid_x",
            "centroid_y",
            "area",
            "effective_area",
            "inside_percent",
            "polygon_geojson",
            "block_status",
        ],
        order_by="block_no asc",
        limit_page_length=0,
    )

    if not blocks:
        frappe.throw(f"No Geo Pit Layout Block records found for layout {geo_pit_layout}.")

    return blocks


def _assign_mining_block_fields(doc, block, geo_pit_layout):
    doc.mining_block_code = block.block_code
    doc.geo_project = block.geo_project
    doc.source_pit_layout = geo_pit_layout
    doc.source_layout_block = block.name
    doc.cut_no = block.cut_no
    doc.block_no = block.block_no
    doc.row_no = block.row_no
    doc.column_no = block.column_no
    doc.centroid_x = block.centroid_x
    doc.centroid_y = block.centroid_y
    doc.area = block.area
    doc.effective_area = block.effective_area
    doc.inside_percent = block.inside_percent
    doc.polygon_geojson = block.polygon_geojson

    if not doc.block_status:
        doc.block_status = "Available"

    if not doc.planning_status:
        doc.planning_status = "Not Evaluated"

    if not doc.remarks:
        doc.remarks = f"Generated from Geo Pit Layout {geo_pit_layout}"


@frappe.whitelist()
def mark_layout_final(geo_pit_layout):
    """
    Mark a saved Geo Pit Layout as final.
    """
    layout = _get_layout(geo_pit_layout)

    layout.layout_status = "Final"
    layout.is_final_layout = 1
    layout.layout_type = "Final Layout"
    layout.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "geo_pit_layout": layout.name,
        "layout_status": layout.layout_status,
        "is_final_layout": layout.is_final_layout,
    }


@frappe.whitelist()
def generate_mining_blocks_from_layout(
    geo_pit_layout,
    geology_run=None,
    require_final=1,
    overwrite_existing=0,
):
    """
    Generate official Mining Block records from Geo Pit Layout Block rows.

    Phase 3 rule:
    - This function creates/updates Mining Block only.
    - It does not create Mining Block Material Value records.
    - Material values are created later from Geo Pit Layout Material Stack.
    """
    layout = _get_layout(geo_pit_layout)
    require_final = _int(require_final, 1)
    overwrite_existing = _int(overwrite_existing, 0)

    if require_final and not _int(layout.is_final_layout, 0):
        frappe.throw("This Geo Pit Layout is not final. Mark it as final before generating Mining Block records.")

    blocks = _get_layout_blocks(geo_pit_layout)

    created_blocks = 0
    updated_blocks = 0
    skipped_blocks = 0
    total_area = 0.0
    effective_area = 0.0

    for block in blocks:
        total_area += _float(block.area, 0)
        effective_area += _float(block.effective_area, 0)

        existing = frappe.db.get_value(
            "Mining Block",
            {
                "source_pit_layout": geo_pit_layout,
                "source_layout_block": block.name,
            },
            "name",
        )

        if existing and not overwrite_existing:
            skipped_blocks += 1
            continue

        if existing and overwrite_existing:
            doc = frappe.get_doc("Mining Block", existing)
            updated_blocks += 1
        else:
            doc = frappe.new_doc("Mining Block")
            created_blocks += 1

        _assign_mining_block_fields(doc, block, geo_pit_layout)

        if existing and overwrite_existing:
            doc.save(ignore_permissions=True)
        else:
            doc.insert(ignore_permissions=True)

    frappe.db.commit()

    return {
        "geo_pit_layout": geo_pit_layout,
        "layout_status": layout.layout_status,
        "is_final_layout": layout.is_final_layout,
        "layout_block_count": len(blocks),
        "mining_blocks_created": created_blocks,
        "mining_blocks_updated": updated_blocks,
        "mining_blocks_skipped": skipped_blocks,
        "total_area": total_area,
        "effective_area": effective_area,
    }


@frappe.whitelist()
def get_mining_block_generation_summary(geo_pit_layout, geology_run=None):
    """
    Dry-run style summary before generating official Mining Block records.
    geology_run is accepted only for backward compatibility and is ignored.
    """
    layout = _get_layout(geo_pit_layout)
    blocks = _get_layout_blocks(geo_pit_layout)

    existing_blocks = frappe.db.count(
        "Mining Block",
        {"source_pit_layout": geo_pit_layout},
    )

    existing_material_values = 0

    if existing_blocks and frappe.db.exists("DocType", "Mining Block Material Value"):
        existing_material_values = frappe.db.sql(
            """
            SELECT COUNT(mbmv.name)
            FROM `tabMining Block Material Value` mbmv
            INNER JOIN `tabMining Block` mb
                ON mb.name = mbmv.mining_block
            WHERE mb.source_pit_layout = %(geo_pit_layout)s
            """,
            {"geo_pit_layout": geo_pit_layout},
        )[0][0]

    return {
        "geo_pit_layout": geo_pit_layout,
        "layout_status": layout.layout_status,
        "is_final_layout": layout.is_final_layout,
        "layout_block_count": len(blocks),
        "existing_mining_blocks": existing_blocks,
        "existing_material_values": _int(existing_material_values, 0),
        "ready": 1 if _int(layout.is_final_layout, 0) and len(blocks) else 0,
    }


@frappe.whitelist()
def get_mining_blocks_for_layout(geo_pit_layout):
    if not geo_pit_layout:
        frappe.throw("Geo Pit Layout is required.")

    return frappe.get_all(
        "Mining Block",
        filters={"source_pit_layout": geo_pit_layout},
        fields=[
            "name",
            "mining_block_code",
            "geo_project",
            "source_pit_layout",
            "source_layout_block",
            "cut_no",
            "block_no",
            "row_no",
            "column_no",
            "centroid_x",
            "centroid_y",
            "area",
            "effective_area",
            "inside_percent",
            "block_status",
            "planning_status",
        ],
        order_by="block_no asc",
        limit_page_length=0,
    )