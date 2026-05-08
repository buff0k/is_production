import frappe

from is_production.geo_planning.services.pit_layout_service import (
    preview_layout_blocks,
    create_pit_layout_with_blocks,
    get_pit_layout_blocks,
)


def _doctype_has_field(doctype, fieldname):
    return fieldname in [df.fieldname for df in frappe.get_meta(doctype).fields]


@frappe.whitelist()
def get_pit_outline_batches(geo_project=None):
    """
    Return pit outline import batches that have Pit Outline Points.
    Used by the Geo Pit Layout Viewer.
    """
    conditions = []
    values = {}

    if geo_project:
        conditions.append("pop.geo_project = %(geo_project)s")
        values["geo_project"] = geo_project

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    batch_field = "pop.geo_import_batch" if _doctype_has_field("Pit Outline Points", "geo_import_batch") else "pop.import_batch"

    return frappe.db.sql(
        f"""
        SELECT
            gib.name AS value,
            COALESCE(gib.full_name, gib.variable_name, gib.variable_code, gib.batch_id, gib.name) AS label,
            COUNT(pop.name) AS point_count
        FROM `tabPit Outline Points` pop
        INNER JOIN `tabGeo Import Batch` gib
            ON gib.name = {batch_field}
        {where_clause}
        GROUP BY gib.name
        ORDER BY point_count DESC, gib.modified DESC
        """,
        values,
        as_dict=True,
    )


@frappe.whitelist()
def get_saved_layouts(geo_project=None):
    filters = {}

    if geo_project:
        filters["geo_project"] = geo_project

    return frappe.get_all(
        "Geo Pit Layout",
        filters=filters,
        fields=[
            "name",
            "layout_name",
            "layout_code",
            "geo_project",
            "layout_version",
            "layout_type",
            "pit_outline_batch",
            "block_size_x",
            "block_size_y",
            "block_angle_degrees",
            "minimum_inside_percent",
            "default_cut_no",
            "numbering_style",
            "block_count",
            "total_area",
            "effective_area",
            "layout_status",
            "is_final_layout",
        ],
        order_by="modified desc",
        limit_page_length=100,
    )


@frappe.whitelist()
def preview_blocks(
    geo_project=None,
    pit_outline_batch=None,
    block_size_x=100,
    block_size_y=40,
    block_angle_degrees=0,
    minimum_inside_percent=50,
    default_cut_no=1,
    numbering_style="C1B1",
):
    return preview_layout_blocks(
        geo_project=geo_project,
        pit_outline_batch=pit_outline_batch,
        block_size_x=block_size_x,
        block_size_y=block_size_y,
        block_angle_degrees=block_angle_degrees,
        minimum_inside_percent=minimum_inside_percent,
        default_cut_no=default_cut_no,
        numbering_style=numbering_style,
    )


@frappe.whitelist()
def save_layout(
    layout_name=None,
    geo_project=None,
    pit_outline_batch=None,
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
    return create_pit_layout_with_blocks(
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


@frappe.whitelist()
def load_layout_blocks(geo_pit_layout=None):
    if not geo_pit_layout:
        frappe.throw("Geo Pit Layout is required.")

    layout = frappe.get_doc("Geo Pit Layout", geo_pit_layout)
    blocks = get_pit_layout_blocks(geo_pit_layout)

    return {
        "layout": {
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
        },
        "blocks": blocks,
    }


@frappe.whitelist()
def get_geo_import_batches(geo_project=None):
    if not geo_project:
        return []

    return frappe.db.sql(
        """
        SELECT
            gmp.import_batch AS value,
            COALESCE(gib.full_name, gib.variable_name, gib.variable_code, gib.batch_id, gib.name) AS label,
            MAX(gmp.variable_name) AS variable_name,
            COUNT(gmp.name) AS point_count
        FROM `tabGeo Model Points` gmp
        INNER JOIN `tabGeo Import Batch` gib
            ON gib.name = gmp.import_batch
        WHERE gmp.geo_project = %(geo_project)s
        GROUP BY gmp.import_batch
        ORDER BY point_count DESC, gib.modified DESC
        """,
        {"geo_project": geo_project},
        as_dict=True,
    )


@frappe.whitelist()
def get_geo_calculation_batches(geo_project=None):
    """
    Return Geo Calculation Batches that have Geo Calculated Points.

    Kept deliberately safe: your Geo Calculation Batch DocType may not have
    fields like full_name / variable_code, so this query only depends on
    Geo Calculated Points and the calculation batch name.
    """
    if not geo_project:
        return []

    rows = frappe.db.sql(
        """
        SELECT
            gcp.calculation_batch AS value,
            gcp.calculation_batch AS label,
            MAX(gcp.variable_name) AS variable_name,
            COUNT(gcp.name) AS point_count
        FROM `tabGeo Calculated Points` gcp
        WHERE gcp.geo_project = %(geo_project)s
          AND gcp.calculation_batch IS NOT NULL
          AND gcp.calculation_batch != ''
        GROUP BY gcp.calculation_batch
        ORDER BY point_count DESC
        """,
        {"geo_project": geo_project},
        as_dict=True,
    )

    for row in rows:
        if row.get("variable_name"):
            row["label"] = f"{row['label']} - {row['variable_name']}"

    return rows


@frappe.whitelist()
def preview_geology_overlay(
    geo_pit_layout=None,
    source_type=None,
    geo_import_batch=None,
    geo_calculation_batch=None,
    rule_enabled=0,
    rule_operator=None,
    rule_value=None,
    rule_value_to=None,
):
    from is_production.geo_planning.services.layout_geology_service import preview_layout_geology

    return preview_layout_geology(
        geo_pit_layout=geo_pit_layout,
        source_type=source_type,
        geo_import_batch=geo_import_batch,
        geo_calculation_batch=geo_calculation_batch,
        rule_enabled=rule_enabled,
        rule_operator=rule_operator,
        rule_value=rule_value,
        rule_value_to=rule_value_to,
    )


@frappe.whitelist()
def save_geology_run(
    run_name=None,
    geo_pit_layout=None,
    source_type=None,
    geo_import_batch=None,
    geo_calculation_batch=None,
    variable_name=None,
    value_meaning=None,
    rule_enabled=0,
    rule_operator=None,
    rule_value=None,
    rule_value_to=None,
    remarks=None,
):
    from is_production.geo_planning.services.layout_geology_service import create_layout_geology_run

    return create_layout_geology_run(
        run_name=run_name,
        geo_pit_layout=geo_pit_layout,
        source_type=source_type,
        geo_import_batch=geo_import_batch,
        geo_calculation_batch=geo_calculation_batch,
        variable_name=variable_name,
        value_meaning=value_meaning,
        rule_enabled=rule_enabled,
        rule_operator=rule_operator,
        rule_value=rule_value,
        rule_value_to=rule_value_to,
        remarks=remarks,
    )


@frappe.whitelist()
def mark_final_layout(geo_pit_layout=None):
    from is_production.geo_planning.services.mining_block_service import mark_layout_final

    return mark_layout_final(geo_pit_layout)


@frappe.whitelist()
def get_mining_generation_summary(geo_pit_layout=None, geology_run=None):
    from is_production.geo_planning.services.mining_block_service import get_mining_block_generation_summary

    return get_mining_block_generation_summary(
        geo_pit_layout=geo_pit_layout,
        geology_run=geology_run,
    )


@frappe.whitelist()
def generate_mining_blocks(
    geo_pit_layout=None,
    geology_run=None,
    require_final=1,
    overwrite_existing=0,
):
    from is_production.geo_planning.services.mining_block_service import generate_mining_blocks_from_layout

    return generate_mining_blocks_from_layout(
        geo_pit_layout=geo_pit_layout,
        geology_run=geology_run,
        require_final=require_final,
        overwrite_existing=overwrite_existing,
    )


@frappe.whitelist()
def get_planning_summary(source_pit_layout=None, value_type="Thickness", material_seam=None):
    from is_production.geo_planning.services.planning_calculation_service import get_planning_calculation_summary

    return get_planning_calculation_summary(
        source_pit_layout=source_pit_layout,
        value_type=value_type,
        material_seam=material_seam,
    )


@frappe.whitelist()
def calculate_planning_values(
    source_pit_layout=None,
    value_type="Thickness",
    material_seam=None,
    density=1.4,
    mineable_only=1,
    update_block_status=1,
):
    from is_production.geo_planning.services.planning_calculation_service import calculate_volume_and_tonnes

    return calculate_volume_and_tonnes(
        source_pit_layout=source_pit_layout,
        value_type=value_type,
        material_seam=material_seam,
        density=density,
        mineable_only=mineable_only,
        update_block_status=update_block_status,
    )


@frappe.whitelist()
def get_volume_summary(source_pit_layout=None, value_type="Thickness", material_seam=None):
    from is_production.geo_planning.services.planning_calculation_service import get_volume_tonnes_summary

    return get_volume_tonnes_summary(
        source_pit_layout=source_pit_layout,
        value_type=value_type,
        material_seam=material_seam,
    )
