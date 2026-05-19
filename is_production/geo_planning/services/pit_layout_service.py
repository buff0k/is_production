import json

import frappe
from frappe.utils import now

from is_production.geo_planning.services.geometry_service import generate_layout_blocks_from_pit


DEFAULT_LAYOUT_VERSION = "V001"
DEFAULT_LAYOUT_TYPE = "Pit Layout"
DEFAULT_NUMBERING_STYLE = "C1B1"


_LAYOUT_BLOCK_FIELDS = [
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
    "block_size_x",
    "block_size_y",
    "angle_degrees",
    "area",
    "effective_area",
    "inside_percent",
    "polygon_geojson",
    "corners_json",
    "block_status",
    "remarks",
]


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


def _get_pit_outline_batch_field():
    """
    Some setups use geo_import_batch on Pit Outline Points, while older/other
    setups may use import_batch. Keep this service tolerant.
    """
    if _has_field("Pit Outline Points", "geo_import_batch"):
        return "geo_import_batch"
    return "import_batch"


def get_pit_outline_points(geo_project, pit_outline_batch):
    if not geo_project:
        frappe.throw("Geo Project is required.")
    if not pit_outline_batch:
        frappe.throw("Pit Outline Batch is required.")

    batch_field = _get_pit_outline_batch_field()

    points = frappe.get_all(
        "Pit Outline Points",
        filters={
            "geo_project": geo_project,
            batch_field: pit_outline_batch,
        },
        fields=["name", "x", "y", "z", "row_no"],
        order_by="row_no asc",
        limit_page_length=0,
    )

    if not points:
        frappe.throw(
            f"No Pit Outline Points found for project {geo_project} and pit outline batch {pit_outline_batch}."
        )

    return points


def make_layout_code(geo_project, layout_name):
    project_code = frappe.db.get_value("Geo Project", geo_project, "project_code") or geo_project
    base = (layout_name or "PIT-LAYOUT").strip().replace(" ", "-").upper()
    return f"{project_code}-{base}"


def generate_blocks_from_layout_settings(layout):
    pit_points = get_pit_outline_points(layout.geo_project, layout.pit_outline_batch)

    return generate_layout_blocks_from_pit(
        pit_points=pit_points,
        block_size_x=_float(layout.block_size_x, 100),
        block_size_y=_float(layout.block_size_y, 40),
        angle_degrees=_float(layout.block_angle_degrees, 0),
        minimum_inside_percent=_float(layout.minimum_inside_percent, 50),
        cut_no=_int(layout.default_cut_no, 1),
        numbering_style=layout.numbering_style or DEFAULT_NUMBERING_STYLE,
    )


def populate_layout_defaults(layout):
    if not layout.layout_name:
        frappe.throw("Layout Name is required.")
    if not layout.geo_project:
        frappe.throw("Geo Project is required.")
    if not layout.pit_outline_batch:
        frappe.throw("Pit Outline Batch is required.")

    if not layout.layout_code:
        layout.layout_code = make_layout_code(layout.geo_project, layout.layout_name)

    if not layout.layout_version:
        layout.layout_version = DEFAULT_LAYOUT_VERSION

    if not layout.layout_type:
        layout.layout_type = DEFAULT_LAYOUT_TYPE

    if not layout.layout_status:
        layout.layout_status = "Draft"

    if not layout.numbering_style:
        layout.numbering_style = DEFAULT_NUMBERING_STYLE

    if not _float(layout.block_size_x, 0):
        layout.block_size_x = 100

    if not _float(layout.block_size_y, 0):
        layout.block_size_y = 40

    if layout.block_angle_degrees in (None, ""):
        layout.block_angle_degrees = 0

    if layout.minimum_inside_percent in (None, ""):
        layout.minimum_inside_percent = 50

    if not _int(layout.default_cut_no, 0):
        layout.default_cut_no = 1

    _set_if_field(layout, "generation_status", layout.get("generation_status") or "Draft")


def populate_layout_block_doc(doc, layout, block):
    doc.geo_pit_layout = layout.name
    doc.geo_project = layout.geo_project
    doc.block_code = block.get("block_code")
    doc.cut_no = block.get("cut_no")
    doc.block_no = block.get("block_no")
    doc.row_no = block.get("row_no")
    doc.column_no = block.get("column_no")
    doc.centroid_x = block.get("centroid_x")
    doc.centroid_y = block.get("centroid_y")
    doc.block_size_x = block.get("block_size_x")
    doc.block_size_y = block.get("block_size_y")
    doc.angle_degrees = block.get("angle_degrees")
    doc.area = block.get("area")
    doc.effective_area = block.get("effective_area")
    doc.inside_percent = block.get("inside_percent")
    doc.polygon_geojson = block.get("polygon_geojson")
    doc.corners_json = block.get("corners_json")
    doc.block_status = block.get("block_status") or "Draft"


def count_downstream_layout_links(geo_pit_layout):
    """
    Check whether the layout already has records that link to Geo Pit Layout Block.

    If these exist, layout blocks must not be deleted because:
    - Frappe will raise LinkExistsError.
    - Deleting blocks would break the planning chain.
    """
    geology_results = frappe.db.count(
        "Geo Pit Layout Geology Result",
        {"geo_pit_layout": geo_pit_layout},
    )

    mining_blocks = frappe.db.count(
        "Mining Block",
        {"source_pit_layout": geo_pit_layout},
    )

    material_values = 0
    summaries = 0

    if mining_blocks:
        material_values = frappe.db.sql(
            """
            SELECT COUNT(mbmv.name)
            FROM `tabMining Block Material Value` mbmv
            INNER JOIN `tabMining Block` mb
                ON mb.name = mbmv.mining_block
            WHERE mb.source_pit_layout = %(geo_pit_layout)s
            """,
            {"geo_pit_layout": geo_pit_layout},
        )[0][0]

        if frappe.db.exists("DocType", "Mining Block Material Summary"):
            summaries = frappe.db.sql(
                """
                SELECT COUNT(name)
                FROM `tabMining Block Material Summary`
                WHERE source_pit_layout = %(geo_pit_layout)s
                """,
                {"geo_pit_layout": geo_pit_layout},
            )[0][0]

    return {
        "geology_results": _int(geology_results, 0),
        "mining_blocks": _int(mining_blocks, 0),
        "material_values": _int(material_values, 0),
        "material_summaries": _int(summaries, 0),
        "has_downstream_links": bool(geology_results or mining_blocks or material_values or summaries),
    }


def clear_layout_blocks(geo_pit_layout, force=0):
    """
    Delete layout blocks only when it is safe.

    If the layout already has geology results, mining blocks, material values,
    or summaries, deleting blocks is unsafe. Use update-in-place instead.
    """
    downstream = count_downstream_layout_links(geo_pit_layout)

    if downstream["has_downstream_links"] and not _int(force, 0):
        frappe.throw(
            "This layout already has downstream records linked to its layout blocks. "
            "Do not clear/delete layout blocks. Regenerate with update-in-place instead, "
            "or create a new Geo Pit Layout version."
        )

    existing = frappe.get_all(
        "Geo Pit Layout Block",
        filters={"geo_pit_layout": geo_pit_layout},
        pluck="name",
        limit_page_length=0,
    )

    for name in existing:
        frappe.delete_doc("Geo Pit Layout Block", name, ignore_permissions=True)

    return len(existing)


def _get_existing_layout_blocks_by_code(geo_pit_layout):
    rows = frappe.get_all(
        "Geo Pit Layout Block",
        filters={"geo_pit_layout": geo_pit_layout},
        fields=["name", "block_code"],
        limit_page_length=0,
    )

    out = {}
    for row in rows:
        if row.block_code:
            out[row.block_code] = row.name

    return out, rows


def _mark_stale_blocks_for_review(existing_blocks, generated_codes):
    stale_count = 0

    for row in existing_blocks:
        if not row.block_code or row.block_code in generated_codes:
            continue

        try:
            doc = frappe.get_doc("Geo Pit Layout Block", row.name)
            doc.block_status = "Review"
            if _has_field(doc.doctype, "remarks"):
                doc.remarks = (
                    "This block was not produced by the latest regeneration, "
                    "but was kept because downstream records are linked to it."
                )
            doc.save(ignore_permissions=True)
            stale_count += 1
        except Exception:
            pass

    return stale_count


def create_or_update_layout_blocks(geo_pit_layout, clear_existing_blocks=0, overwrite_existing=1):
    """
    Heavy worker-safe method.

    Reads Geo Pit Layout settings, generates block geometry, and creates/updates
    Geo Pit Layout Block rows.

    Important:
    - If no downstream records exist, clear_existing_blocks can be used.
    - If downstream records exist, this automatically switches to update-in-place.
      That prevents LinkExistsError and preserves existing layout block document names.
    """
    if not geo_pit_layout:
        frappe.throw("Geo Pit Layout is required.")

    layout = frappe.get_doc("Geo Pit Layout", geo_pit_layout)
    populate_layout_defaults(layout)

    downstream = count_downstream_layout_links(layout.name)
    has_downstream_links = downstream["has_downstream_links"]

    # Never delete blocks when downstream records exist.
    if has_downstream_links:
        clear_existing_blocks = 0
        overwrite_existing = 1

    blocks = generate_blocks_from_layout_settings(layout)

    if not blocks:
        frappe.throw("No layout blocks were generated. Check pit outline, block size and minimum inside percentage.")

    if _int(clear_existing_blocks, 0):
        clear_layout_blocks(layout.name)

    existing_by_code, existing_blocks = _get_existing_layout_blocks_by_code(layout.name)

    created = 0
    updated = 0
    skipped = 0
    total_area = 0.0
    effective_area = 0.0
    generated_codes = set()

    for block in blocks:
        block_code = block.get("block_code")
        generated_codes.add(block_code)

        total_area += _float(block.get("area"), 0)
        effective_area += _float(block.get("effective_area"), 0)

        existing = existing_by_code.get(block_code)

        if existing and not _int(overwrite_existing, 1):
            skipped += 1
            continue

        if existing:
            doc = frappe.get_doc("Geo Pit Layout Block", existing)
            updated += 1
        else:
            doc = frappe.new_doc("Geo Pit Layout Block")
            created += 1

        populate_layout_block_doc(doc, layout, block)

        if existing:
            doc.save(ignore_permissions=True)
        else:
            doc.insert(ignore_permissions=True)

    stale_count = 0
    if has_downstream_links:
        stale_count = _mark_stale_blocks_for_review(existing_blocks, generated_codes)

    layout.block_count = frappe.db.count("Geo Pit Layout Block", {"geo_pit_layout": layout.name})
    layout.total_area = total_area
    layout.effective_area = effective_area

    _set_if_field(layout, "generation_status", "Complete")
    _set_if_field(layout, "generation_completed_on", now())

    if has_downstream_links:
        _set_if_field(
            layout,
            "generation_error",
            (
                "Generation completed in update-in-place mode because downstream "
                f"records exist. Geology Results: {downstream['geology_results']}, "
                f"Mining Blocks: {downstream['mining_blocks']}, "
                f"Material Values: {downstream['material_values']}, "
                f"Material Summaries: {downstream['material_summaries']}. "
                "Rerun geology assignment if geometry changed."
            ),
        )
    else:
        _set_if_field(layout, "generation_error", None)

    layout.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "geo_pit_layout": layout.name,
        "layout_code": layout.layout_code,
        "blocks_generated": len(blocks),
        "blocks_created": created,
        "blocks_updated": updated,
        "blocks_skipped": skipped,
        "stale_blocks_kept": stale_count,
        "downstream_geology_results": downstream["geology_results"],
        "downstream_mining_blocks": downstream["mining_blocks"],
        "downstream_material_values": downstream["material_values"],
        "downstream_material_summaries": downstream["material_summaries"],
        "update_in_place": 1 if has_downstream_links else 0,
        "total_area": total_area,
        "effective_area": effective_area,
    }


@frappe.whitelist()
def preview_layout_blocks(
    geo_project,
    pit_outline_batch,
    block_size_x=100,
    block_size_y=40,
    block_angle_degrees=0,
    minimum_inside_percent=50,
    default_cut_no=1,
    numbering_style="C1B1",
):
    pit_points = get_pit_outline_points(geo_project, pit_outline_batch)

    return generate_layout_blocks_from_pit(
        pit_points=pit_points,
        block_size_x=_float(block_size_x, 100),
        block_size_y=_float(block_size_y, 40),
        angle_degrees=_float(block_angle_degrees, 0),
        minimum_inside_percent=_float(minimum_inside_percent, 50),
        cut_no=_int(default_cut_no, 1),
        numbering_style=numbering_style or DEFAULT_NUMBERING_STYLE,
    )


@frappe.whitelist()
def create_pit_layout_with_blocks(
    layout_name,
    geo_project,
    pit_outline_batch,
    layout_version="V001",
    layout_type="Pit Layout",
    block_size_x=100,
    block_size_y=40,
    block_angle_degrees=0,
    minimum_inside_percent=50,
    default_cut_no=1,
    numbering_style="C1B1",
    remarks=None,
):
    """
    Compatibility method for older viewer buttons.
    Creates a layout and generates blocks synchronously.

    New workflow should prefer:
        Create Geo Pit Layout
        Click Generate Layout Blocks
    """
    if not layout_name:
        frappe.throw("Layout Name is required.")

    layout = frappe.new_doc("Geo Pit Layout")
    layout.layout_name = layout_name
    layout.layout_code = make_layout_code(geo_project, layout_name)
    layout.geo_project = geo_project
    layout.layout_version = layout_version or DEFAULT_LAYOUT_VERSION
    layout.layout_type = layout_type or DEFAULT_LAYOUT_TYPE
    layout.pit_outline_batch = pit_outline_batch
    layout.block_size_x = _float(block_size_x, 100)
    layout.block_size_y = _float(block_size_y, 40)
    layout.block_angle_degrees = _float(block_angle_degrees, 0)
    layout.minimum_inside_percent = _float(minimum_inside_percent, 50)
    layout.default_cut_no = _int(default_cut_no, 1)
    layout.numbering_style = numbering_style or DEFAULT_NUMBERING_STYLE
    layout.layout_status = "Draft"
    layout.is_final_layout = 0
    layout.remarks = remarks
    _set_if_field(layout, "generation_status", "Draft")
    layout.insert(ignore_permissions=True)

    result = create_or_update_layout_blocks(
        geo_pit_layout=layout.name,
        clear_existing_blocks=0,
        overwrite_existing=1,
    )

    return {
        "layout": layout.name,
        "layout_code": layout.layout_code,
        "blocks_created": result.get("blocks_created", 0),
        "blocks_updated": result.get("blocks_updated", 0),
        "blocks_skipped": result.get("blocks_skipped", 0),
        "stale_blocks_kept": result.get("stale_blocks_kept", 0),
        "update_in_place": result.get("update_in_place", 0),
        "total_area": result.get("total_area", 0),
        "effective_area": result.get("effective_area", 0),
    }


@frappe.whitelist()
def get_pit_layout_blocks(geo_pit_layout):
    if not geo_pit_layout:
        frappe.throw("Geo Pit Layout is required.")

    return frappe.get_all(
        "Geo Pit Layout Block",
        filters={"geo_pit_layout": geo_pit_layout},
        fields=_LAYOUT_BLOCK_FIELDS,
        order_by="block_no asc",
        limit_page_length=0,
    )


@frappe.whitelist()
def mark_layout_final(geo_pit_layout):
    if not geo_pit_layout:
        frappe.throw("Geo Pit Layout is required.")

    layout = frappe.get_doc("Geo Pit Layout", geo_pit_layout)
    layout.layout_status = "Final"
    layout.is_final_layout = 1
    layout.layout_type = "Final Layout"
    layout.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "layout": layout.name,
        "layout_status": layout.layout_status,
        "is_final_layout": layout.is_final_layout,
    }


@frappe.whitelist()
def create_material_stack_from_layout(geo_pit_layout, stack_name=None):
    if not geo_pit_layout:
        frappe.throw("Geo Pit Layout is required.")

    layout = frappe.get_doc("Geo Pit Layout", geo_pit_layout)

    stack = frappe.new_doc("Geo Pit Layout Material Stack")
    stack.stack_name = stack_name or f"{layout.layout_name or layout.name} Stack"
    stack.geo_project = layout.geo_project
    stack.geo_pit_layout = layout.name
    stack.stack_status = "Draft"

    if frappe.get_meta("Geo Pit Layout Material Stack").has_field("attach_status"):
        stack.attach_status = "Not Attached"

    if frappe.get_meta("Geo Pit Layout Material Stack").has_field("calculation_status"):
        stack.calculation_status = "Not Calculated"

    stack.insert(ignore_permissions=True)

    if _has_field("Geo Pit Layout", "active_material_stack"):
        layout.active_material_stack = stack.name
        layout.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "material_stack": stack.name,
        "stack_name": stack.stack_name,
        "geo_pit_layout": layout.name,
    }


@frappe.whitelist()
def get_layout_generation_summary(geo_pit_layout):
    if not geo_pit_layout:
        frappe.throw("Geo Pit Layout is required.")

    layout = frappe.get_doc("Geo Pit Layout", geo_pit_layout)

    block_count = frappe.db.count("Geo Pit Layout Block", {"geo_pit_layout": geo_pit_layout})
    mining_block_count = frappe.db.count("Mining Block", {"source_pit_layout": geo_pit_layout})
    downstream = count_downstream_layout_links(geo_pit_layout)

    latest_batch = None
    if _has_field("Geo Pit Layout", "latest_generation_batch"):
        latest_batch = layout.get("latest_generation_batch")

    return {
        "geo_pit_layout": layout.name,
        "layout_name": layout.layout_name,
        "layout_code": layout.layout_code,
        "layout_status": layout.layout_status,
        "is_final_layout": layout.is_final_layout,
        "generation_status": layout.get("generation_status"),
        "latest_generation_batch": latest_batch,
        "pit_outline_batch": layout.pit_outline_batch,
        "block_count": block_count,
        "mining_block_count": mining_block_count,
        "downstream": downstream,
        "total_area": layout.total_area,
        "effective_area": layout.effective_area,
    }