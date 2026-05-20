import json

import frappe
from frappe import _


def _flt(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _cint(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _safe_json(value, default=None):
    if default is None:
        default = {}

    if not value:
        return default

    if isinstance(value, (dict, list)):
        return value

    try:
        return json.loads(value)
    except Exception:
        return default


def _doctype_has_field(doctype, fieldname):
    try:
        return frappe.get_meta(doctype).has_field(fieldname)
    except Exception:
        return False


@frappe.whitelist()
def get_material_stacks(geo_project=None, geo_pit_layout=None):
    filters = {}

    if geo_project:
        filters["geo_project"] = geo_project

    if geo_pit_layout:
        filters["geo_pit_layout"] = geo_pit_layout

    rows = frappe.get_all(
        "Geo Pit Layout Material Stack",
        filters=filters,
        fields=[
            "name",
            "stack_name",
            "geo_project",
            "geo_pit_layout",
            "stack_status",
            "calculation_status",
            "attach_status",
            "total_volume",
            "total_tonnes",
        ],
        order_by="modified desc",
        limit_page_length=100,
    )

    output = []

    for row in rows:
        label = row.stack_name or row.name

        if row.calculation_status:
            label = f"{label} - {row.calculation_status}"

        if row.total_volume or row.total_tonnes:
            label = f"{label} | Vol {_flt(row.total_volume):,.0f} | t {_flt(row.total_tonnes):,.0f}"

        output.append(
            {
                "value": row.name,
                "label": label,
                "geo_project": row.geo_project,
                "geo_pit_layout": row.geo_pit_layout,
            }
        )

    return output


@frappe.whitelist()
def load_viewer_data(
    geo_project=None,
    geo_pit_layout=None,
    material_stack=None,
    material_seam=None,
    include_qualities=1,
):
    if not geo_project:
        frappe.throw(_("Geo Project is required."))

    if not geo_pit_layout:
        frappe.throw(_("Geo Pit Layout is required."))

    layout = frappe.get_doc("Geo Pit Layout", geo_pit_layout)

    blocks = _get_mining_blocks(
        geo_project=geo_project,
        geo_pit_layout=geo_pit_layout,
    )

    if not blocks:
        return {
            "layout": _layout_payload(layout),
            "blocks": [],
            "summary": {
                "block_count": 0,
                "material_count": 0,
                "total_volume": 0,
                "total_tonnes": 0,
            },
        }

    block_names = [row["name"] for row in blocks]

    summaries = _get_material_summaries(
        geo_project=geo_project,
        geo_pit_layout=geo_pit_layout,
        material_stack=material_stack,
        material_seam=material_seam,
    )

    qualities = []

    if _cint(include_qualities, 1):
        qualities = _get_quality_values(
            geo_project=geo_project,
            geo_pit_layout=geo_pit_layout,
            material_stack=material_stack,
            material_seam=material_seam,
        )

    summaries_by_block = {}
    qualities_by_block_material = {}

    for row in summaries:
        summaries_by_block.setdefault(row["mining_block"], []).append(row)

    for row in qualities:
        key = (row["mining_block"], row["material_seam"])
        qualities_by_block_material.setdefault(key, []).append(row)

    output_blocks = []
    total_volume = 0
    total_tonnes = 0
    material_count = 0

    for block in blocks:
        block_materials = []
        block_total_volume = 0
        block_total_tonnes = 0

        for summary in summaries_by_block.get(block["name"], []):
            key = (summary["mining_block"], summary["material_seam"])
            quality_rows = qualities_by_block_material.get(key, [])

            material_payload = {
                "summary_record": summary.get("summary_record"),
                "material_stack": summary.get("material_stack"),
                "material_seam": summary.get("material_seam"),
                "thickness_value": _flt(summary.get("thickness_value")),
                "thickness_point_count": _cint(summary.get("thickness_point_count")),
                "density_value": _flt(summary.get("density_value")),
                "density_point_count": _cint(summary.get("density_point_count")),
                "effective_area": _flt(summary.get("effective_area")),
                "volume": _flt(summary.get("volume")),
                "tonnes": _flt(summary.get("tonnes")),
                "material_status": summary.get("material_status"),
                "calculation_status": summary.get("calculation_status"),
                "thickness_value_record": summary.get("thickness_value_record"),
                "density_value_record": summary.get("density_value_record"),
                "qualities": quality_rows,
            }

            block_materials.append(material_payload)

            block_total_volume += _flt(summary.get("volume"))
            block_total_tonnes += _flt(summary.get("tonnes"))
            material_count += 1

        total_volume += block_total_volume
        total_tonnes += block_total_tonnes

        block_payload = dict(block)
        block_payload["materials"] = block_materials
        block_payload["total_volume"] = block_total_volume
        block_payload["total_tonnes"] = block_total_tonnes

        output_blocks.append(block_payload)

    return {
        "layout": _layout_payload(layout),
        "blocks": output_blocks,
        "summary": {
            "block_count": len(block_names),
            "material_count": material_count,
            "total_volume": total_volume,
            "total_tonnes": total_tonnes,
        },
    }


def _layout_payload(layout):
    return {
        "name": layout.name,
        "layout_name": layout.layout_name,
        "layout_code": layout.layout_code,
        "geo_project": layout.geo_project,
        "layout_version": layout.layout_version,
        "layout_type": layout.layout_type,
        "pit_outline_batch": layout.pit_outline_batch,
        "block_size_x": layout.block_size_x,
        "block_size_y": layout.block_size_y,
        "block_angle_degrees": layout.block_angle_degrees,
        "minimum_inside_percent": layout.minimum_inside_percent,
        "default_cut_no": layout.default_cut_no,
        "numbering_style": layout.numbering_style,
        "block_count": layout.block_count,
        "total_area": layout.total_area,
        "effective_area": layout.effective_area,
        "layout_status": layout.layout_status,
        "is_final_layout": layout.is_final_layout,
    }


def _get_mining_blocks(geo_project=None, geo_pit_layout=None):
    conditions = []
    values = {}

    if geo_project:
        conditions.append("mb.geo_project = %(geo_project)s")
        values["geo_project"] = geo_project

    if geo_pit_layout:
        conditions.append("mb.source_pit_layout = %(geo_pit_layout)s")
        values["geo_pit_layout"] = geo_pit_layout

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    polygon_field = "mb.polygon_geojson" if _doctype_has_field("Mining Block", "polygon_geojson") else "NULL"

    rows = frappe.db.sql(
        f"""
        SELECT
            mb.name,
            mb.mining_block_code,
            mb.geo_project,
            mb.source_pit_layout,
            mb.source_layout_block,
            mb.cut_no,
            mb.block_no,
            mb.row_no,
            mb.column_no,
            mb.centroid_x,
            mb.centroid_y,
            mb.area,
            mb.effective_area,
            mb.inside_percent,
            {polygon_field} AS polygon_geojson,
            mb.block_status,
            mb.planning_status
        FROM `tabMining Block` mb
        {where_clause}
        ORDER BY
            COALESCE(mb.block_no, 0),
            COALESCE(mb.row_no, 0),
            COALESCE(mb.column_no, 0),
            mb.name
        """,
        values,
        as_dict=True,
    )

    fixed_rows = []

    for row in rows:
        if not row.get("polygon_geojson") and row.get("source_layout_block"):
            row["polygon_geojson"] = frappe.db.get_value(
                "Geo Pit Layout Block",
                row.source_layout_block,
                "polygon_geojson",
            )

        fixed_rows.append(row)

    return fixed_rows


def _get_material_summaries(
    geo_project=None,
    geo_pit_layout=None,
    material_stack=None,
    material_seam=None,
):
    conditions = []
    values = {}

    if geo_project:
        conditions.append("s.geo_project = %(geo_project)s")
        values["geo_project"] = geo_project

    if geo_pit_layout:
        conditions.append("s.source_pit_layout = %(geo_pit_layout)s")
        values["geo_pit_layout"] = geo_pit_layout

    if material_stack:
        conditions.append("s.material_stack = %(material_stack)s")
        values["material_stack"] = material_stack

    if material_seam:
        conditions.append("s.material_seam LIKE %(material_seam)s")
        values["material_seam"] = f"%{material_seam}%"

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    return frappe.db.sql(
        f"""
        SELECT
            s.name AS summary_record,
            s.mining_block,
            s.geo_project,
            s.source_pit_layout,
            s.material_stack,
            s.material_seam,
            s.thickness_value,
            s.thickness_point_count,
            s.density_value,
            s.density_point_count,
            s.effective_area,
            s.volume,
            s.tonnes,
            s.quality_summary_json,
            s.material_status,
            s.calculation_status,
            s.remarks,
            s.thickness_value_record,
            s.density_value_record
        FROM `tabMining Block Material Summary` s
        {where_clause}
        ORDER BY
            s.material_stack,
            s.material_seam,
            s.mining_block
        """,
        values,
        as_dict=True,
    )


def _get_quality_values(
    geo_project=None,
    geo_pit_layout=None,
    material_stack=None,
    material_seam=None,
):
    conditions = []
    values = {}

    if geo_project:
        conditions.append("v.geo_project = %(geo_project)s")
        values["geo_project"] = geo_project

    if geo_pit_layout:
        conditions.append("mb.source_pit_layout = %(geo_pit_layout)s")
        values["geo_pit_layout"] = geo_pit_layout

    if material_stack:
        conditions.append("v.material_stack = %(material_stack)s")
        values["material_stack"] = material_stack

    if material_seam:
        conditions.append("v.material_seam LIKE %(material_seam)s")
        values["material_seam"] = f"%{material_seam}%"

    conditions.append(
        """
        COALESCE(v.value_type, '') NOT IN ('Thickness', 'Density')
        """
    )

    where_clause = "WHERE " + " AND ".join(conditions)

    return frappe.db.sql(
        f"""
        SELECT
            v.name AS material_value_record,
            v.mining_block,
            v.geo_project,
            mb.source_pit_layout,
            v.material_stack,
            v.material_stack_item,
            v.material_seam,
            v.variable_name,
            v.variable_code,
            v.value_type,
            v.avg_value,
            v.min_value,
            v.max_value,
            v.point_count,
            v.effective_area,
            v.volume,
            v.density,
            v.tonnes,
            v.passes_rule,
            v.material_status,
            v.source_geology_run,
            v.source_geology_result
        FROM `tabMining Block Material Value` v
        INNER JOIN `tabMining Block` mb
            ON mb.name = v.mining_block
        {where_clause}
        ORDER BY
            v.material_seam,
            v.value_type,
            v.variable_code,
            v.variable_name
        """,
        values,
        as_dict=True,
    )


@frappe.whitelist()
def get_block_details(mining_block=None, material_stack=None):
    if not mining_block:
        frappe.throw(_("Mining Block is required."))

    block = frappe.get_doc("Mining Block", mining_block)

    geo_pit_layout = block.source_pit_layout
    geo_project = block.geo_project

    summaries = _get_material_summaries(
        geo_project=geo_project,
        geo_pit_layout=geo_pit_layout,
        material_stack=material_stack,
    )

    summaries = [row for row in summaries if row.get("mining_block") == mining_block]

    qualities = _get_quality_values(
        geo_project=geo_project,
        geo_pit_layout=geo_pit_layout,
        material_stack=material_stack,
    )

    qualities = [row for row in qualities if row.get("mining_block") == mining_block]

    qualities_by_material = {}

    for row in qualities:
        qualities_by_material.setdefault(row.get("material_seam"), []).append(row)

    materials = []

    for summary in summaries:
        material = dict(summary)
        material["qualities"] = qualities_by_material.get(summary.get("material_seam"), [])
        materials.append(material)

    return {
        "block": {
            "name": block.name,
            "mining_block_code": block.mining_block_code,
            "geo_project": block.geo_project,
            "source_pit_layout": block.source_pit_layout,
            "source_layout_block": block.source_layout_block,
            "cut_no": block.cut_no,
            "block_no": block.block_no,
            "row_no": block.row_no,
            "column_no": block.column_no,
            "centroid_x": block.centroid_x,
            "centroid_y": block.centroid_y,
            "area": block.area,
            "effective_area": block.effective_area,
            "inside_percent": block.inside_percent,
            "polygon_geojson": block.polygon_geojson,
            "block_status": block.block_status,
            "planning_status": block.planning_status,
        },
        "materials": materials,
    }