import frappe


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

        items.append({
            "idx": row.idx,
            "sort_order": _int(row.sort_order, row.idx),
            "material_seam": row.material_seam or run.get("material_seam") or run.variable_name,
            "value_type": row.value_type or run.value_meaning or "Other",
            "geology_run": row.geology_run,
            "use_for_volume": _int(row.use_for_volume, 0),
            "use_for_tonnes": _int(row.use_for_tonnes, 0),
            "use_for_scheduling": _int(row.use_for_scheduling, 0),
            "run": run,
        })

    if not items:
        frappe.throw("Material Stack has no valid items with Geology Runs.")

    return sorted(items, key=lambda x: (x["sort_order"], x["idx"]))


def _get_mining_blocks_by_layout_block(geo_pit_layout):
    rows = frappe.get_all(
        "Mining Block",
        filters={"source_pit_layout": geo_pit_layout},
        fields=["name", "source_layout_block", "effective_area", "planning_status"],
        limit_page_length=0,
    )

    return {r.source_layout_block: r for r in rows}


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

    return {r.layout_block: r for r in rows}


def _material_status_from_result(result):
    if not result:
        return "No Data"

    if result.result_status == "No Data" or _int(result.point_count, 0) == 0:
        return "No Data"

    if result.result_status == "Pass" or _int(result.passes_rule, 0) == 1:
        return "Mineable"

    if result.result_status == "Fail":
        return "Excluded"

    return "Review"


def _make_duplicate_filters(mining_block, result, item):
    filters = {
        "mining_block": mining_block,
        "source_type": result.source_type,
        "variable_name": result.variable_name or item["run"].variable_name,
        "value_type": item["value_type"],
        "material_seam": item["material_seam"],
    }

    if result.source_type == "Geo Import Batch":
        filters["geo_import_batch"] = result.geo_import_batch

    if result.source_type == "Geo Calculation Batch":
        filters["geo_calculation_batch"] = result.geo_calculation_batch

    return filters


@frappe.whitelist()
def get_material_stack_summary(material_stack):
    """
    Preview/sanity check before attaching stack items to Mining Blocks.
    """
    stack = _get_stack(material_stack)
    layout = _get_layout(stack)
    items = _get_stack_items(stack)

    mining_block_count = frappe.db.count("Mining Block", {"source_pit_layout": stack.geo_pit_layout})
    layout_block_count = frappe.db.count("Geo Pit Layout Block", {"geo_pit_layout": stack.geo_pit_layout})

    item_summaries = []

    for item in items:
        result_count = frappe.db.count("Geo Pit Layout Geology Result", {"geology_run": item["geology_run"]})

        item_summaries.append({
            "sort_order": item["sort_order"],
            "material_seam": item["material_seam"],
            "value_type": item["value_type"],
            "geology_run": item["geology_run"],
            "run_name": item["run"].run_name,
            "variable_name": item["run"].variable_name,
            "variable_code": item["run"].get("variable_code"),
            "use_for_volume": item["use_for_volume"],
            "use_for_tonnes": item["use_for_tonnes"],
            "use_for_scheduling": item["use_for_scheduling"],
            "result_count": result_count,
        })

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
        "items": item_summaries,
    }


@frappe.whitelist()
def attach_material_stack_to_mining_blocks(
    material_stack,
    create_missing_mining_blocks=1,
    overwrite_existing=0,
):
    """
    PHASE 4B:
    Attach many Geo Pit Layout Geology Runs to the same Mining Blocks.

    Key relationship:
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

            duplicate_filters = _make_duplicate_filters(mb.name, result, item)
            existing = frappe.db.get_value("Mining Block Material Value", duplicate_filters, "name")

            if existing and not _int(overwrite_existing, 0):
                skipped += 1
                item_skipped += 1
                continue

            if existing and _int(overwrite_existing, 0):
                doc = frappe.get_doc("Mining Block Material Value", existing)
                updated += 1
                item_updated += 1
            else:
                doc = frappe.new_doc("Mining Block Material Value")
                created += 1
                item_created += 1

            run = item["run"]

            doc.mining_block = mb.name
            doc.geo_project = result.geo_project or stack.geo_project
            doc.material_seam = item["material_seam"]
            doc.variable_name = result.variable_name or run.variable_name
            doc.variable_code = run.get("variable_code")
            doc.value_type = item["value_type"]
            doc.source_type = result.source_type
            doc.geo_import_batch = result.geo_import_batch
            doc.geo_calculation_batch = result.geo_calculation_batch
            doc.avg_value = result.avg_value
            doc.min_value = result.min_value
            doc.max_value = result.max_value
            doc.point_count = result.point_count
            doc.effective_area = mb.effective_area
            doc.passes_rule = result.passes_rule
            doc.material_status = _material_status_from_result(result)

            # Keep calculation fields blank here.
            # Phase 4 calculation service populates volume/density/tonnes.
            if not existing:
                doc.volume = None
                doc.density = None
                doc.tonnes = None

            if existing and _int(overwrite_existing, 0):
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
    """
    Summarise Mining Block Material Value rows for the stack items.
    """
    stack = _get_stack(material_stack)
    items = _get_stack_items(stack)

    summary = []

    for item in items:
        run = item["run"]

        rows = frappe.db.sql(
            """
            SELECT
                COUNT(mbmv.name) AS record_count,
                SUM(COALESCE(mbmv.volume, 0)) AS total_volume,
                SUM(COALESCE(mbmv.tonnes, 0)) AS total_tonnes,
                SUM(CASE WHEN mbmv.material_status = 'Mineable' THEN 1 ELSE 0 END) AS mineable_count,
                SUM(CASE WHEN mbmv.material_status = 'No Data' THEN 1 ELSE 0 END) AS no_data_count,
                SUM(CASE WHEN mbmv.material_status = 'Excluded' THEN 1 ELSE 0 END) AS excluded_count
            FROM `tabMining Block Material Value` mbmv
            INNER JOIN `tabMining Block` mb
                ON mb.name = mbmv.mining_block
            WHERE mb.source_pit_layout = %(geo_pit_layout)s
              AND mbmv.material_seam = %(material_seam)s
              AND mbmv.value_type = %(value_type)s
              AND mbmv.variable_name = %(variable_name)s
            """,
            {
                "geo_pit_layout": stack.geo_pit_layout,
                "material_seam": item["material_seam"],
                "value_type": item["value_type"],
                "variable_name": run.variable_name,
            },
            as_dict=True,
        )[0]

        summary.append({
            "sort_order": item["sort_order"],
            "material_seam": item["material_seam"],
            "value_type": item["value_type"],
            "geology_run": item["geology_run"],
            "variable_name": run.variable_name,
            "record_count": _int(rows.record_count, 0),
            "mineable_count": _int(rows.mineable_count, 0),
            "excluded_count": _int(rows.excluded_count, 0),
            "no_data_count": _int(rows.no_data_count, 0),
            "total_volume": _float(rows.total_volume, 0),
            "total_tonnes": _float(rows.total_tonnes, 0),
        })

    return {
        "material_stack": stack.name,
        "geo_pit_layout": stack.geo_pit_layout,
        "items": summary,
    }
