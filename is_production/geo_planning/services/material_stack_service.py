import json

import frappe
from frappe.utils import now


SOURCE_IMPORT_BATCH = "Geo Import Batch"
SOURCE_CALCULATION_BATCH = "Geo Calculation Batch"


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


def _get_safe(doc, fieldname, default=None):
    if _has_field(doc.doctype, fieldname):
        return doc.get(fieldname)
    return default


def _set_if_field(doc, fieldname, value):
    if _has_field(doc.doctype, fieldname):
        setattr(doc, fieldname, value)


def _safe_json(value):
    try:
        return json.dumps(value, default=str, indent=2)
    except Exception:
        return "{}"


def _get_stack(material_stack):
    if not material_stack:
        frappe.throw("Geo Pit Layout Material Stack is required.")

    stack = frappe.get_doc("Geo Pit Layout Material Stack", material_stack)

    if not stack.geo_pit_layout:
        frappe.throw("Material Stack must have a Geo Pit Layout.")

    if not stack.geo_project:
        frappe.throw("Material Stack must have a Geo Project.")

    if not stack.get("item"):
        frappe.throw("Material Stack has no items.")

    return stack


def _get_layout(stack):
    return frappe.get_doc("Geo Pit Layout", stack.geo_pit_layout)


def _normalise_density_source(value):
    value = value or "None"

    if value not in ("None", "Manual", "Geology Run"):
        return "None"

    return value


def _get_stack_items(stack):
    items = []

    for row in stack.get("item") or []:
        if not row.geology_run:
            continue

        run = frappe.get_doc("Geo Pit Layout Geology Run", row.geology_run)

        if run.geo_pit_layout != stack.geo_pit_layout:
            frappe.throw(
                f"Geology Run {run.name} belongs to layout {run.geo_pit_layout}, "
                f"but this stack belongs to layout {stack.geo_pit_layout}."
            )

        manual_density = _float(_get_safe(row, "manual_density", None), 0)

        # Backward compatibility with older child table field called density.
        if manual_density <= 0:
            manual_density = _float(_get_safe(row, "density", None), 0)

        item = {
            "name": row.name,
            "idx": row.idx,
            "sort_order": _int(row.sort_order, row.idx),
            "material_seam": row.material_seam or run.get("material_seam") or run.variable_name,
            "value_type": row.value_type or run.value_meaning or "Other",
            "geology_run": row.geology_run,
            "variable_name": run.variable_name,
            "variable_code": run.get("variable_code"),
            "use_for_volume": _int(row.get("use_for_volume"), 0),
            "use_for_density": _int(_get_safe(row, "use_for_density", 0), 0),
            "use_for_tonnes": _int(row.get("use_for_tonnes"), 0),
            "use_for_scheduling": _int(row.get("use_for_scheduling"), 0),
            "density_source": _normalise_density_source(_get_safe(row, "density_source", "None")),
            "manual_density": manual_density,
            "aggregation_method": _get_safe(row, "aggregation_method", "Average") or "Average",
            "required": _int(_get_safe(row, "required", 1), 1),
            "allow_missing_data": _int(_get_safe(row, "allow_missing_data", 0), 0),
            "default_value": _float(_get_safe(row, "default_value", None), None),
            "run": run,
        }

        items.append(item)

    if not items:
        frappe.throw("Material Stack has no valid items with Geology Runs.")

    return sorted(items, key=lambda item: (item["sort_order"], item["idx"]))


def _get_mining_blocks_by_layout_block(geo_pit_layout):
    rows = frappe.get_all(
        "Mining Block",
        filters={"source_pit_layout": geo_pit_layout},
        fields=[
            "name",
            "source_layout_block",
            "geo_project",
            "effective_area",
            "planning_status",
        ],
        limit_page_length=0,
    )

    return {row.source_layout_block: row for row in rows}


def _ensure_mining_blocks_exist(geo_pit_layout):
    existing_count = frappe.db.count("Mining Block", {"source_pit_layout": geo_pit_layout})

    if existing_count:
        return existing_count

    from is_production.geo_planning.services.mining_block_service import generate_mining_blocks_from_layout

    result = generate_mining_blocks_from_layout(
        geo_pit_layout=geo_pit_layout,
        geology_run=None,
        require_final=1,
        overwrite_existing=0,
    )

    return result.get("mining_blocks_created", 0)


def _get_geology_results(geology_run):
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


def _material_status_from_result(result):
    if not result:
        return "No Data"

    if result.result_status == "No Data" or _int(result.point_count, 0) == 0:
        return "No Data"

    if result.result_status == "Fail":
        return "Excluded"

    if result.result_status == "Pass" or _int(result.passes_rule, 0) == 1:
        return "Mineable"

    # If no rule was applied, result_status is usually Review.
    # For calculation purposes, data exists, so keep it usable but visible.
    return "Review"


def _make_duplicate_filters(mining_block, result, item, stack):
    filters = {
        "mining_block": mining_block,
        "material_seam": item["material_seam"],
        "value_type": item["value_type"],
        "source_geology_run": item["geology_run"],
    }

    if _has_field("Mining Block Material Value", "material_stack"):
        filters["material_stack"] = stack.name

    if _has_field("Mining Block Material Value", "material_stack_item"):
        filters["material_stack_item"] = item["name"]

    return filters


def _set_source_batch_fields(doc, result):
    doc.geo_import_batch = result.geo_import_batch
    doc.geo_calculation_batch = result.geo_calculation_batch


def _set_material_value_fields(doc, mb, result, item, stack):
    run = item["run"]

    doc.mining_block = mb.name
    doc.geo_project = result.geo_project or stack.geo_project
    doc.material_seam = item["material_seam"]
    doc.variable_name = result.variable_name or run.variable_name
    doc.variable_code = item.get("variable_code")
    doc.value_type = item["value_type"]
    doc.source_type = result.source_type
    _set_source_batch_fields(doc, result)
    doc.avg_value = result.avg_value
    doc.min_value = result.min_value
    doc.max_value = result.max_value
    doc.point_count = result.point_count
    doc.effective_area = mb.effective_area
    doc.passes_rule = result.passes_rule
    doc.material_status = _material_status_from_result(result)

    _set_if_field(doc, "material_stack", stack.name)
    _set_if_field(doc, "material_stack_item", item["name"])
    _set_if_field(doc, "source_geology_run", item["geology_run"])
    _set_if_field(doc, "source_geology_result", result.name)


@frappe.whitelist()
def get_material_stack_summary(material_stack):
    stack = _get_stack(material_stack)
    layout = _get_layout(stack)
    items = _get_stack_items(stack)

    mining_block_count = frappe.db.count("Mining Block", {"source_pit_layout": stack.geo_pit_layout})
    layout_block_count = frappe.db.count("Geo Pit Layout Block", {"geo_pit_layout": stack.geo_pit_layout})

    item_summaries = []

    for item in items:
        result_count = frappe.db.count("Geo Pit Layout Geology Result", {"geology_run": item["geology_run"]})
        run = item["run"]

        item_summaries.append({
            "stack_item": item["name"],
            "sort_order": item["sort_order"],
            "material_seam": item["material_seam"],
            "value_type": item["value_type"],
            "geology_run": item["geology_run"],
            "run_name": run.run_name,
            "variable_name": run.variable_name,
            "variable_code": run.get("variable_code"),
            "use_for_volume": item["use_for_volume"],
            "use_for_density": item["use_for_density"],
            "use_for_tonnes": item["use_for_tonnes"],
            "use_for_scheduling": item["use_for_scheduling"],
            "density_source": item["density_source"],
            "manual_density": item["manual_density"],
            "result_count": result_count,
        })

    existing_values = frappe.db.count("Mining Block Material Value", {"material_stack": stack.name}) if _has_field("Mining Block Material Value", "material_stack") else 0

    existing_summaries = 0
    if frappe.db.exists("DocType", "Mining Block Material Summary"):
        existing_summaries = frappe.db.count("Mining Block Material Summary", {"material_stack": stack.name})

    return {
        "material_stack": stack.name,
        "stack_name": stack.stack_name,
        "stack_status": stack.stack_status,
        "geo_project": stack.geo_project,
        "geo_pit_layout": stack.geo_pit_layout,
        "layout_status": layout.layout_status,
        "is_final_layout": layout.is_final_layout,
        "layout_block_count": layout_block_count,
        "existing_mining_block_count": mining_block_count,
        "stack_item_count": len(item_summaries),
        "existing_material_values": existing_values,
        "existing_material_summaries": existing_summaries,
        "items": item_summaries,
    }


@frappe.whitelist()
def attach_material_stack_to_mining_blocks(
    material_stack,
    create_missing_mining_blocks=1,
    overwrite_existing=0,
):
    """
    Attach many Geo Pit Layout Geology Runs to the same Mining Blocks.

    Relationship:
        Geo Pit Layout Geology Result.layout_block
        -> Mining Block.source_layout_block
        -> Mining Block Material Value.mining_block
    """
    stack = _get_stack(material_stack)
    layout = _get_layout(stack)

    if not _int(layout.is_final_layout, 0):
        frappe.throw("The Geo Pit Layout must be final before attaching a material stack.")

    items = _get_stack_items(stack)

    if _int(create_missing_mining_blocks, 1):
        _ensure_mining_blocks_exist(stack.geo_pit_layout)

    mining_blocks = _get_mining_blocks_by_layout_block(stack.geo_pit_layout)

    if not mining_blocks:
        frappe.throw("No Mining Block records exist for this layout. Generate Mining Blocks first.")

    created = 0
    updated = 0
    skipped = 0
    no_mining_block = 0

    item_results = []
    should_overwrite = _int(overwrite_existing, 0)

    for item in items:
        results_by_layout_block = _get_geology_results(item["geology_run"])

        item_created = 0
        item_updated = 0
        item_skipped = 0
        item_no_block = 0

        for layout_block_name, result in results_by_layout_block.items():
            mb = mining_blocks.get(layout_block_name)

            if not mb:
                no_mining_block += 1
                item_no_block += 1
                continue

            duplicate_filters = _make_duplicate_filters(mb.name, result, item, stack)
            existing = frappe.db.get_value("Mining Block Material Value", duplicate_filters, "name")

            if existing and not should_overwrite:
                skipped += 1
                item_skipped += 1
                continue

            if existing and should_overwrite:
                doc = frappe.get_doc("Mining Block Material Value", existing)
                updated += 1
                item_updated += 1
            else:
                doc = frappe.new_doc("Mining Block Material Value")
                created += 1
                item_created += 1

            _set_material_value_fields(doc, mb, result, item, stack)

            # Calculation service fills these later.
            if not existing:
                doc.volume = None
                doc.density = None
                doc.tonnes = None

            if existing:
                doc.save(ignore_permissions=True)
            else:
                doc.insert(ignore_permissions=True)

        item_results.append({
            "geology_run": item["geology_run"],
            "material_seam": item["material_seam"],
            "value_type": item["value_type"],
            "results_checked": len(results_by_layout_block),
            "created": item_created,
            "updated": item_updated,
            "skipped": item_skipped,
            "missing_mining_block": item_no_block,
        })

    stack.attach_status = "Complete"
    stack.last_attached_on = now()
    stack.error_log = None
    stack.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "material_stack": stack.name,
        "geo_pit_layout": stack.geo_pit_layout,
        "stack_item_count": len(items),
        "mining_block_count": len(mining_blocks),
        "material_values_created": created,
        "material_values_updated": updated,
        "material_values_skipped": skipped,
        "missing_mining_block": no_mining_block,
        "items": item_results,
    }


@frappe.whitelist()
def get_material_value_summary_by_stack(material_stack):
    stack = _get_stack(material_stack)

    if not _has_field("Mining Block Material Value", "material_stack"):
        frappe.throw("Mining Block Material Value.material_stack field is required.")

    rows = frappe.db.sql(
        """
        SELECT
            material_seam,
            value_type,
            COUNT(name) AS record_count,
            SUM(CASE WHEN material_status = 'Mineable' THEN 1 ELSE 0 END) AS mineable_count,
            SUM(CASE WHEN material_status = 'Review' THEN 1 ELSE 0 END) AS review_count,
            SUM(CASE WHEN material_status = 'No Data' THEN 1 ELSE 0 END) AS no_data_count,
            SUM(CASE WHEN material_status = 'Excluded' THEN 1 ELSE 0 END) AS excluded_count,
            SUM(COALESCE(volume, 0)) AS total_volume,
            SUM(COALESCE(tonnes, 0)) AS total_tonnes
        FROM `tabMining Block Material Value`
        WHERE material_stack = %(material_stack)s
        GROUP BY material_seam, value_type
        ORDER BY material_seam, value_type
        """,
        {"material_stack": stack.name},
        as_dict=True,
    )

    return {
        "material_stack": stack.name,
        "geo_pit_layout": stack.geo_pit_layout,
        "items": rows,
    }