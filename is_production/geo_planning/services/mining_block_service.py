import frappe


SOURCE_TYPE_IMPORT_BATCH = "Geo Import Batch"
SOURCE_TYPE_CALCULATION_BATCH = "Geo Calculation Batch"


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


def _doctype_has_field(doctype, fieldname):
    return any(df.fieldname == fieldname for df in frappe.get_meta(doctype).fields)


def _set_if_field(doc, fieldname, value):
    if _doctype_has_field(doc.doctype, fieldname):
        setattr(doc, fieldname, value)


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


def _get_geology_run(geology_run):
    if not geology_run:
        return None

    return frappe.get_doc("Geo Pit Layout Geology Run", geology_run)


def _get_geology_results(geology_run):
    if not geology_run:
        return {}

    rows = frappe.get_all(
        "Geo Pit Layout Geology Result",
        filters={"geology_run": geology_run},
        fields=[
            "name",
            "geology_run",
            "geo_pit_layout",
            "layout_block",
            "geo_project",
            "block_code",
            "source_type",
            "geo_import_batch",
            "geo_calculation_batch",
            "variable_name",
            "avg_value",
            "min_value",
            "max_value",
            "point_count",
            "passes_rule",
            "result_status",
        ],
        limit_page_length=0,
    )

    return {row.layout_block: row for row in rows}


def _material_status_from_result(result_status, passes_rule):
    if result_status == "No Data":
        return "No Data"

    if result_status == "Pass" or _int(passes_rule, 0) == 1:
        return "Mineable"

    if result_status == "Fail":
        return "Excluded"

    return "Review"


def _planning_status_from_results(results_by_layout_block, layout_block_name):
    result = results_by_layout_block.get(layout_block_name)

    if not result:
        return "Not Evaluated"

    if result.result_status == "Pass" or _int(result.passes_rule, 0) == 1:
        return "Mineable"

    if result.result_status == "Fail":
        return "Not Mineable"

    return "Review"


def _assign_mining_block_fields(doc, block, geo_pit_layout, results_by_layout_block):
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
    doc.block_status = "Available"
    doc.planning_status = _planning_status_from_results(results_by_layout_block, block.name)
    doc.remarks = f"Generated from Geo Pit Layout {geo_pit_layout}"


def _make_material_value_duplicate_filters(mining_block, result):
    filters = {
        "mining_block": mining_block,
        "source_type": result.source_type,
        "variable_name": result.variable_name,
    }

    if result.source_type == SOURCE_TYPE_IMPORT_BATCH:
        filters["geo_import_batch"] = result.geo_import_batch

    if result.source_type == SOURCE_TYPE_CALCULATION_BATCH:
        filters["geo_calculation_batch"] = result.geo_calculation_batch

    return filters


def _assign_material_value_fields(value_doc, mining_block, result, run, mb_effective_area):
    value_doc.mining_block = mining_block
    value_doc.geo_project = result.geo_project
    value_doc.material_seam = run.variable_name or result.variable_name
    value_doc.variable_name = result.variable_name
    value_doc.variable_code = None
    value_doc.value_type = run.value_meaning or "Other"
    value_doc.source_type = result.source_type
    value_doc.geo_import_batch = result.geo_import_batch
    value_doc.geo_calculation_batch = result.geo_calculation_batch
    value_doc.avg_value = result.avg_value
    value_doc.min_value = result.min_value
    value_doc.max_value = result.max_value
    value_doc.point_count = result.point_count
    value_doc.effective_area = mb_effective_area
    value_doc.passes_rule = result.passes_rule
    value_doc.material_status = _material_status_from_result(result.result_status, result.passes_rule)

    # Phase 4 will calculate volume/tonnes properly once density rules are defined.
    # For now we only prepare the fields.
    value_doc.volume = None
    value_doc.density = None
    value_doc.tonnes = None


@frappe.whitelist()
def mark_layout_final(geo_pit_layout):
    """
    Phase 3 Step 11:
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
    Phase 3 Steps 12 and 13:
    Generate official Mining Block records from a final Geo Pit Layout.

    If geology_run is supplied, this also creates Mining Block Material Value
    records from Geo Pit Layout Geology Result records.

    This function is intentionally conservative:
    - By default, the layout must be final.
    - Existing Mining Blocks are skipped unless overwrite_existing=1.
    """
    layout = _get_layout(geo_pit_layout)
    require_final = _int(require_final, 1)
    overwrite_existing = _int(overwrite_existing, 0)

    if require_final and not _int(layout.is_final_layout, 0):
        frappe.throw("This Geo Pit Layout is not final. Mark it as final before generating Mining Block records.")

    blocks = _get_layout_blocks(geo_pit_layout)
    run = _get_geology_run(geology_run)
    results_by_layout_block = _get_geology_results(geology_run)

    created_blocks = 0
    updated_blocks = 0
    skipped_blocks = 0
    created_material_values = 0
    skipped_material_values = 0

    source_layout_block_to_mining_block = {}

    for block in blocks:
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
            source_layout_block_to_mining_block[block.name] = existing
            continue

        if existing and overwrite_existing:
            doc = frappe.get_doc("Mining Block", existing)
            updated_blocks += 1
        else:
            doc = frappe.new_doc("Mining Block")
            created_blocks += 1

        _assign_mining_block_fields(doc, block, geo_pit_layout, results_by_layout_block)

        if existing and overwrite_existing:
            doc.save(ignore_permissions=True)
        else:
            doc.insert(ignore_permissions=True)

        source_layout_block_to_mining_block[block.name] = doc.name

    if run and results_by_layout_block:
        for layout_block_name, result in results_by_layout_block.items():
            mining_block = source_layout_block_to_mining_block.get(layout_block_name)

            if not mining_block:
                continue

            existing_value = frappe.db.get_value(
                "Mining Block Material Value",
                _make_material_value_duplicate_filters(mining_block, result),
                "name",
            )

            if existing_value and not overwrite_existing:
                skipped_material_values += 1
                continue

            if existing_value and overwrite_existing:
                value_doc = frappe.get_doc("Mining Block Material Value", existing_value)
            else:
                value_doc = frappe.new_doc("Mining Block Material Value")

            mb_effective_area = frappe.db.get_value("Mining Block", mining_block, "effective_area") or 0
            _assign_material_value_fields(value_doc, mining_block, result, run, mb_effective_area)

            if existing_value and overwrite_existing:
                value_doc.save(ignore_permissions=True)
            else:
                value_doc.insert(ignore_permissions=True)
                created_material_values += 1

    frappe.db.commit()

    return {
        "geo_pit_layout": geo_pit_layout,
        "geology_run": geology_run,
        "layout_block_count": len(blocks),
        "mining_blocks_created": created_blocks,
        "mining_blocks_updated": updated_blocks,
        "mining_blocks_skipped": skipped_blocks,
        "material_values_created": created_material_values,
        "material_values_skipped": skipped_material_values,
    }


@frappe.whitelist()
def get_mining_block_generation_summary(geo_pit_layout, geology_run=None):
    """
    Dry-run style summary for Phase 3 before generating official Mining Block records.
    """
    layout = _get_layout(geo_pit_layout)
    blocks = _get_layout_blocks(geo_pit_layout)
    results_by_layout_block = _get_geology_results(geology_run)

    existing_blocks = frappe.db.count("Mining Block", {"source_pit_layout": geo_pit_layout})

    return {
        "geo_pit_layout": geo_pit_layout,
        "layout_status": layout.layout_status,
        "is_final_layout": layout.is_final_layout,
        "layout_block_count": len(blocks),
        "existing_mining_blocks": existing_blocks,
        "geology_run": geology_run,
        "geology_result_count": len(results_by_layout_block),
    }
