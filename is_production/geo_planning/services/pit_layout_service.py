import frappe

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


def _get_pit_outline_points(geo_project, pit_outline_batch):
    if not geo_project:
        frappe.throw("Geo Project is required.")
    if not pit_outline_batch:
        frappe.throw("Pit Outline Batch is required.")

    points = frappe.get_all(
        "Pit Outline Points",
        filters={"geo_project": geo_project, "geo_import_batch": pit_outline_batch},
        fields=["name", "x", "y", "z", "row_no"],
        order_by="row_no asc",
        limit_page_length=0,
    )

    if not points:
        frappe.throw(f"No Pit Outline Points found for project {geo_project} and pit outline batch {pit_outline_batch}.")

    return points


def _make_layout_code(geo_project, layout_name):
    project_code = frappe.db.get_value("Geo Project", geo_project, "project_code") or geo_project
    base = (layout_name or "PIT-LAYOUT").strip().replace(" ", "-").upper()
    return f"{project_code}-{base}"


def _generate_blocks(
    pit_points,
    block_size_x=100,
    block_size_y=40,
    block_angle_degrees=0,
    minimum_inside_percent=50,
    default_cut_no=1,
    numbering_style=DEFAULT_NUMBERING_STYLE,
):
    return generate_layout_blocks_from_pit(
        pit_points=pit_points,
        block_size_x=_float(block_size_x, 100),
        block_size_y=_float(block_size_y, 40),
        angle_degrees=_float(block_angle_degrees, 0),
        minimum_inside_percent=_float(minimum_inside_percent, 50),
        cut_no=_int(default_cut_no, 1),
        numbering_style=numbering_style or DEFAULT_NUMBERING_STYLE,
    )


def _populate_layout_doc(
    layout,
    layout_name,
    geo_project,
    pit_outline_batch,
    layout_version=DEFAULT_LAYOUT_VERSION,
    layout_type=DEFAULT_LAYOUT_TYPE,
    block_size_x=100,
    block_size_y=40,
    block_angle_degrees=0,
    minimum_inside_percent=50,
    default_cut_no=1,
    numbering_style=DEFAULT_NUMBERING_STYLE,
    remarks=None,
):
    layout.layout_name = layout_name
    layout.layout_code = _make_layout_code(geo_project, layout_name)
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


def _populate_layout_block_doc(doc, layout_name, geo_project, block):
    doc.geo_pit_layout = layout_name
    doc.geo_project = geo_project
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
    doc.block_status = "Draft"


def _mark_layout_doc_final(layout):
    layout.layout_status = "Final"
    layout.is_final_layout = 1
    layout.layout_type = "Final Layout"


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
    pit_points = _get_pit_outline_points(geo_project, pit_outline_batch)

    return _generate_blocks(
        pit_points=pit_points,
        block_size_x=block_size_x,
        block_size_y=block_size_y,
        block_angle_degrees=block_angle_degrees,
        minimum_inside_percent=minimum_inside_percent,
        default_cut_no=default_cut_no,
        numbering_style=numbering_style,
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
    if not layout_name:
        frappe.throw("Layout Name is required.")

    pit_points = _get_pit_outline_points(geo_project, pit_outline_batch)

    blocks = _generate_blocks(
        pit_points=pit_points,
        block_size_x=block_size_x,
        block_size_y=block_size_y,
        block_angle_degrees=block_angle_degrees,
        minimum_inside_percent=minimum_inside_percent,
        default_cut_no=default_cut_no,
        numbering_style=numbering_style,
    )

    if not blocks:
        frappe.throw("No layout blocks were generated. Check pit outline, block size and minimum inside percentage.")

    layout = frappe.new_doc("Geo Pit Layout")
    _populate_layout_doc(
        layout=layout,
        layout_name=layout_name,
        geo_project=geo_project,
        pit_outline_batch=pit_outline_batch,
        layout_version=layout_version,
        layout_type=layout_type,
        block_size_x=block_size_x,
        block_size_y=block_size_y,
        block_angle_degrees=block_angle_degrees,
        minimum_inside_percent=minimum_inside_percent,
        default_cut_no=default_cut_no,
        numbering_style=numbering_style,
        remarks=remarks,
    )
    layout.insert(ignore_permissions=True)

    total_area = 0.0
    effective_area = 0.0
    created = 0

    for block in blocks:
        doc = frappe.new_doc("Geo Pit Layout Block")
        _populate_layout_block_doc(doc, layout.name, geo_project, block)
        doc.insert(ignore_permissions=True)

        total_area += _float(block.get("area"), 0)
        effective_area += _float(block.get("effective_area"), 0)
        created += 1

    layout.block_count = created
    layout.total_area = total_area
    layout.effective_area = effective_area
    layout.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "layout": layout.name,
        "layout_code": layout.layout_code,
        "blocks_created": created,
        "total_area": total_area,
        "effective_area": effective_area,
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
    _mark_layout_doc_final(layout)
    layout.save(ignore_permissions=True)
    frappe.db.commit()

    return {"layout": layout.name, "layout_status": layout.layout_status, "is_final_layout": layout.is_final_layout}
