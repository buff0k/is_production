import json

import frappe
from frappe import _
from frappe.utils import now_datetime


def load_selector_data(
    geo_project,
    geo_pit_layout,
    material_stack=None,
    material_seam=None,
):
    if not geo_project:
        frappe.throw(_("Geo Project is required."))

    if not geo_pit_layout:
        frappe.throw(_("Geo Pit Layout is required."))

    block_filters = {
        "geo_project": geo_project,
        "source_pit_layout": geo_pit_layout,
    }

    block_fields = existing_fields(
        "Mining Block",
        [
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
            "centroid_z",
            "area",
            "effective_area",
            "total_volume",
            "volume",
            "total_tonnes",
            "tonnes",
            "block_status",
            "planning_status",
            "polygon_geojson",
        ],
    )

    blocks = frappe.get_all(
        "Mining Block",
        filters=block_filters,
        fields=block_fields,
        order_by=get_block_order_by(),
        limit_page_length=0,
    )

    block_names = [block.name for block in blocks]

    summaries = []
    values = []

    if block_names:
        summaries = get_material_summaries(
            selected_blocks=block_names,
            material_stack=material_stack,
            material_seam=material_seam,
        )

        values = get_material_values(
            selected_blocks=block_names,
            material_seam=material_seam,
        )

    block_payload = build_block_payload_for_page(blocks)
    summary_payload = build_summary_payload_for_page(summaries)
    value_payload = build_value_payload_for_page(values)

    return {
        "blocks": block_payload,
        "material_summaries": summary_payload,
        "material_values": value_payload,
        "totals": calculate_totals_from_blocks(
            blocks=block_payload,
            summaries=summary_payload,
            values=value_payload,
        ),
    }


def create_selection_from_blocks(
    selection_name,
    selection_type,
    geo_project,
    geo_pit_layout,
    material_stack,
    selected_blocks,
    material_seam=None,
    remarks=None,
):
    if not selection_name:
        frappe.throw(_("Selection Name is required."))

    if not selection_type:
        frappe.throw(_("Selection Type is required."))

    if not geo_project:
        frappe.throw(_("Geo Project is required."))

    if not geo_pit_layout:
        frappe.throw(_("Geo Pit Layout is required."))

    if not material_stack:
        frappe.throw(_("Material Stack is required."))

    selection_entries = normalise_selection_entries(selected_blocks)
    selected_block_names = [entry["name"] for entry in selection_entries]

    if not selected_block_names:
        frappe.throw(_("Please select at least one Mining Block."))

    validate_selection(
        geo_project=geo_project,
        geo_pit_layout=geo_pit_layout,
        selected_blocks=selected_block_names,
    )

    block_rows = get_selection_block_payload(selection_entries)

    material_rows = get_selection_material_payload(
        selected_blocks=selected_block_names,
        material_stack=material_stack,
        material_seam=material_seam,
    )

    totals = recalculate_selection_totals(block_rows, material_rows)

    doc = frappe.get_doc(
        {
            "doctype": "Mining Schedule Selection",
            "selection_name": selection_name,
            "geo_project": geo_project,
            "geo_pit_layout": geo_pit_layout,
            "material_stack": material_stack,
            "selection_type": selection_type,
            "selection_status": "Draft",
            "selected_block_count": totals.get("selected_block_count"),
            "total_effective_area": totals.get("total_effective_area"),
            "total_volume": totals.get("total_volume"),
            "total_tonnes": totals.get("total_tonnes"),
            "average_density": totals.get("average_density"),
            "average_cv": totals.get("average_cv"),
            "created_from_page": "Mining Block Selector",
            "source_filters_json": json.dumps(
                {
                    "geo_project": geo_project,
                    "geo_pit_layout": geo_pit_layout,
                    "material_stack": material_stack,
                    "material_seam": material_seam,
                    "selected_blocks": selection_entries,
                    "sequence_basis": "visual_click_order",
                },
                default=str,
            ),
            "selected_on": now_datetime(),
            "selected_by": frappe.session.user,
            "remarks": remarks,
            "blocks": block_rows,
            "materials": material_rows,
        }
    )

    doc.insert()

    return {
        "name": doc.name,
        "selection_name": doc.selection_name,
        "selected_block_count": doc.selected_block_count,
        "total_effective_area": doc.total_effective_area,
        "total_volume": doc.total_volume,
        "total_tonnes": doc.total_tonnes,
        "average_density": doc.average_density,
        "average_cv": doc.average_cv,
    }


def get_selection_block_payload(selected_blocks):
    selection_entries = normalise_selection_entries(selected_blocks)
    selected_block_names = [entry["name"] for entry in selection_entries]

    block_fields = existing_fields(
        "Mining Block",
        [
            "name",
            "mining_block_code",
            "geo_project",
            "source_pit_layout",
            "cut_no",
            "block_no",
            "row_no",
            "column_no",
            "centroid_x",
            "centroid_y",
            "centroid_z",
            "area",
            "effective_area",
            "total_volume",
            "volume",
            "total_tonnes",
            "tonnes",
            "block_status",
            "planning_status",
        ],
    )

    blocks = frappe.get_all(
        "Mining Block",
        filters={"name": ["in", selected_block_names]},
        fields=block_fields,
        limit_page_length=0,
    )

    block_by_name = {block.name: block for block in blocks}

    rows = []

    for idx, entry in enumerate(selection_entries, start=1):
        block_name = entry.get("name")
        block = block_by_name.get(block_name)

        if not block:
            continue

        rows.append(
            {
                "sequence_no": idx,
                "mining_block": block.name,
                "mining_block_code": safe_get(block, "mining_block_code"),
                "geo_project": safe_get(block, "geo_project"),
                "source_pit_layout": safe_get(block, "source_pit_layout"),
                "cut_no": safe_get(block, "cut_no"),
                "block_no": safe_get(block, "block_no"),
                "row_no": safe_get(block, "row_no"),
                "column_no": safe_get(block, "column_no"),
                "centroid_x": safe_get(block, "centroid_x"),
                "centroid_y": safe_get(block, "centroid_y"),
                "area": safe_get(block, "area"),
                "effective_area": safe_get(block, "effective_area"),
                "total_volume": first_number(
                    safe_get(block, "total_volume"),
                    safe_get(block, "volume"),
                ),
                "total_tonnes": first_number(
                    safe_get(block, "total_tonnes"),
                    safe_get(block, "tonnes"),
                ),
                "block_status": safe_get(block, "block_status"),
                "planning_status": safe_get(block, "planning_status") or "Not Evaluated",
                "dependency_group": entry.get("dependency_group"),
                "remarks": entry.get("remarks"),
            }
        )

    return rows


def get_selection_material_payload(selected_blocks, material_stack=None, material_seam=None):
    selected_blocks = normalise_selected_blocks(selected_blocks)

    rows = []

    summaries = get_material_summaries(
        selected_blocks=selected_blocks,
        material_stack=material_stack,
        material_seam=material_seam,
    )

    for summary in summaries:
        rows.append(
            {
                "mining_block": safe_get(summary, "mining_block"),
                "mining_block_code": safe_get(summary, "mining_block_code"),
                "material_seam": safe_get(summary, "material_seam"),
                "value_type": "Thickness",
                "thickness_value": safe_get(summary, "thickness_value"),
                "density_value": safe_get(summary, "density_value"),
                "avg_value": safe_get(summary, "thickness_value"),
                "effective_area": safe_get(summary, "effective_area"),
                "volume": safe_get(summary, "volume"),
                "tonnes": safe_get(summary, "tonnes"),
                "material_status": safe_get(summary, "material_status"),
                "material_stack": safe_get(summary, "material_stack"),
                "material_summary": safe_get(summary, "name"),
            }
        )

        if safe_get(summary, "density_value") is not None:
            rows.append(
                {
                    "mining_block": safe_get(summary, "mining_block"),
                    "mining_block_code": safe_get(summary, "mining_block_code"),
                    "material_seam": safe_get(summary, "material_seam"),
                    "value_type": "Density",
                    "density_value": safe_get(summary, "density_value"),
                    "avg_value": safe_get(summary, "density_value"),
                    "effective_area": safe_get(summary, "effective_area"),
                    "volume": safe_get(summary, "volume"),
                    "tonnes": safe_get(summary, "tonnes"),
                    "material_status": safe_get(summary, "material_status"),
                    "material_stack": safe_get(summary, "material_stack"),
                    "material_summary": safe_get(summary, "name"),
                }
            )

    values = get_material_values(
        selected_blocks=selected_blocks,
        material_seam=material_seam,
    )

    for value in values:
        rows.append(
            {
                "mining_block": safe_get(value, "mining_block"),
                "mining_block_code": safe_get(value, "mining_block_code"),
                "material_seam": safe_get(value, "material_seam"),
                "value_type": safe_get(value, "value_type"),
                "variable_code": safe_get(value, "variable_code"),
                "variable_name": safe_get(value, "variable_name"),
                "avg_value": safe_get(value, "avg_value"),
                "min_value": safe_get(value, "min_value"),
                "max_value": safe_get(value, "max_value"),
                "point_count": safe_get(value, "point_count"),
                "material_value": safe_get(value, "name"),
                "source_geology_run": safe_get(value, "source_geology_run"),
                "source_geology_result": safe_get(value, "source_geology_result"),
            }
        )

    return rows


def get_material_summaries(selected_blocks, material_stack=None, material_seam=None):
    selected_blocks = normalise_selected_blocks(selected_blocks)

    if not selected_blocks:
        return []

    fields = existing_fields(
        "Mining Block Material Summary",
        [
            "name",
            "mining_block",
            "mining_block_code",
            "material_seam",
            "effective_area",
            "thickness_value",
            "density_value",
            "volume",
            "tonnes",
            "material_status",
            "material_stack",
        ],
    )

    filters = {
        "mining_block": ["in", selected_blocks],
    }

    if material_stack and has_field("Mining Block Material Summary", "material_stack"):
        filters["material_stack"] = material_stack

    if material_seam and has_field("Mining Block Material Summary", "material_seam"):
        filters["material_seam"] = material_seam

    return frappe.get_all(
        "Mining Block Material Summary",
        filters=filters,
        fields=fields,
        limit_page_length=0,
    )


def get_material_values(selected_blocks, material_seam=None):
    selected_blocks = normalise_selected_blocks(selected_blocks)

    if not selected_blocks:
        return []

    fields = existing_fields(
        "Mining Block Material Value",
        [
            "name",
            "mining_block",
            "mining_block_code",
            "material_seam",
            "value_type",
            "variable_code",
            "variable_name",
            "avg_value",
            "min_value",
            "max_value",
            "point_count",
            "source_geology_run",
            "source_geology_result",
        ],
    )

    filters = {
        "mining_block": ["in", selected_blocks],
    }

    if material_seam and has_field("Mining Block Material Value", "material_seam"):
        filters["material_seam"] = material_seam

    return frappe.get_all(
        "Mining Block Material Value",
        filters=filters,
        fields=fields,
        limit_page_length=0,
    )


def recalculate_selection_totals(block_rows, material_rows):
    selected_block_count = len(block_rows or [])

    total_effective_area = sum_float(
        row.get("effective_area") for row in block_rows or []
    )

    total_volume = sum_float(
        row.get("volume")
        for row in material_rows or []
        if row.get("value_type") in ("Thickness", None, "")
    )

    total_tonnes = sum_float(
        row.get("tonnes")
        for row in material_rows or []
        if row.get("value_type") in ("Thickness", None, "")
    )

    if not total_volume:
        total_volume = sum_float(row.get("total_volume") for row in block_rows or [])

    if not total_tonnes:
        total_tonnes = sum_float(row.get("total_tonnes") for row in block_rows or [])

    average_density = 0
    if total_volume:
        average_density = total_tonnes / total_volume

    cv_values = [
        row.get("avg_value")
        for row in material_rows or []
        if row.get("value_type") == "Quality"
        and row.get("variable_code")
        and "CV" in row.get("variable_code").upper()
        and row.get("avg_value") is not None
    ]

    average_cv = 0
    if cv_values:
        average_cv = sum_float(cv_values) / len(cv_values)

    return {
        "selected_block_count": selected_block_count,
        "total_effective_area": total_effective_area,
        "total_volume": total_volume,
        "total_tonnes": total_tonnes,
        "average_density": average_density,
        "average_cv": average_cv,
    }


def calculate_totals_from_blocks(blocks, summaries=None, values=None):
    summaries = summaries or []
    values = values or []

    block_rows = [
        {
            "effective_area": block.get("effective_area"),
            "total_volume": first_number(
                block.get("total_volume"),
                block.get("volume"),
            ),
            "total_tonnes": first_number(
                block.get("total_tonnes"),
                block.get("tonnes"),
            ),
        }
        for block in blocks or []
    ]

    material_rows = []

    for summary in summaries:
        material_rows.append(
            {
                "value_type": "Thickness",
                "effective_area": summary.get("effective_area"),
                "volume": summary.get("volume"),
                "tonnes": summary.get("tonnes"),
            }
        )

    for value in values:
        material_rows.append(
            {
                "value_type": value.get("value_type"),
                "variable_code": value.get("variable_code"),
                "avg_value": value.get("avg_value"),
            }
        )

    return recalculate_selection_totals(block_rows, material_rows)


def validate_selection(geo_project, geo_pit_layout, selected_blocks):
    selected_blocks = normalise_selected_blocks(selected_blocks)

    if not geo_project:
        frappe.throw(_("Geo Project is required."))

    if not geo_pit_layout:
        frappe.throw(_("Geo Pit Layout is required."))

    if not selected_blocks:
        frappe.throw(_("No Mining Blocks selected."))

    fields = existing_fields(
        "Mining Block",
        [
            "name",
            "geo_project",
            "source_pit_layout",
        ],
    )

    found_blocks = frappe.get_all(
        "Mining Block",
        filters={"name": ["in", selected_blocks]},
        fields=fields,
        limit_page_length=0,
    )

    found_by_name = {block.name: block for block in found_blocks}
    missing = [block_name for block_name in selected_blocks if block_name not in found_by_name]

    if missing:
        frappe.throw(
            _("These selected Mining Blocks were not found: {0}").format(
                ", ".join(missing[:20])
            )
        )

    if has_field("Mining Block", "geo_project"):
        project_mismatches = [
            block.name
            for block in found_blocks
            if safe_get(block, "geo_project") != geo_project
        ]

        if project_mismatches:
            frappe.throw(
                _("Some selected blocks do not belong to Geo Project {0}: {1}").format(
                    geo_project,
                    ", ".join(project_mismatches[:20]),
                )
            )

    if has_field("Mining Block", "source_pit_layout"):
        layout_mismatches = [
            block.name
            for block in found_blocks
            if safe_get(block, "source_pit_layout") != geo_pit_layout
        ]

        if layout_mismatches:
            frappe.throw(
                _("Some selected blocks do not belong to Geo Pit Layout {0}: {1}").format(
                    geo_pit_layout,
                    ", ".join(layout_mismatches[:20]),
                )
            )


def build_block_payload_for_page(blocks):
    payload = []

    for block in blocks or []:
        payload.append(
            {
                "name": safe_get(block, "name"),
                "mining_block_code": safe_get(block, "mining_block_code"),
                "geo_project": safe_get(block, "geo_project"),
                "source_pit_layout": safe_get(block, "source_pit_layout"),
                "source_layout_block": safe_get(block, "source_layout_block"),
                "cut_no": safe_get(block, "cut_no"),
                "block_no": safe_get(block, "block_no"),
                "row_no": safe_get(block, "row_no"),
                "column_no": safe_get(block, "column_no"),
                "centroid_x": safe_get(block, "centroid_x"),
                "centroid_y": safe_get(block, "centroid_y"),
                "centroid_z": safe_get(block, "centroid_z"),
                "area": safe_get(block, "area"),
                "effective_area": safe_get(block, "effective_area"),
                "total_volume": first_number(
                    safe_get(block, "total_volume"),
                    safe_get(block, "volume"),
                ),
                "total_tonnes": first_number(
                    safe_get(block, "total_tonnes"),
                    safe_get(block, "tonnes"),
                ),
                "block_status": safe_get(block, "block_status"),
                "planning_status": safe_get(block, "planning_status"),
                "polygon_geojson": parse_json_safely(safe_get(block, "polygon_geojson")),
            }
        )

    return payload


def build_summary_payload_for_page(summaries):
    payload = []

    for summary in summaries or []:
        payload.append(
            {
                "name": safe_get(summary, "name"),
                "mining_block": safe_get(summary, "mining_block"),
                "mining_block_code": safe_get(summary, "mining_block_code"),
                "material_seam": safe_get(summary, "material_seam"),
                "effective_area": safe_get(summary, "effective_area"),
                "thickness_value": safe_get(summary, "thickness_value"),
                "density_value": safe_get(summary, "density_value"),
                "volume": safe_get(summary, "volume"),
                "tonnes": safe_get(summary, "tonnes"),
                "material_status": safe_get(summary, "material_status"),
                "material_stack": safe_get(summary, "material_stack"),
            }
        )

    return payload


def build_value_payload_for_page(values):
    payload = []

    for value in values or []:
        payload.append(
            {
                "name": safe_get(value, "name"),
                "mining_block": safe_get(value, "mining_block"),
                "mining_block_code": safe_get(value, "mining_block_code"),
                "material_seam": safe_get(value, "material_seam"),
                "value_type": safe_get(value, "value_type"),
                "variable_code": safe_get(value, "variable_code"),
                "variable_name": safe_get(value, "variable_name"),
                "avg_value": safe_get(value, "avg_value"),
                "min_value": safe_get(value, "min_value"),
                "max_value": safe_get(value, "max_value"),
                "point_count": safe_get(value, "point_count"),
                "source_geology_run": safe_get(value, "source_geology_run"),
                "source_geology_result": safe_get(value, "source_geology_result"),
            }
        )

    return payload


def normalise_selection_entries(selected_blocks):
    if not selected_blocks:
        return []

    if isinstance(selected_blocks, str):
        selected_blocks = json.loads(selected_blocks)

    entries = []

    for row in selected_blocks:
        if not row:
            continue

        if isinstance(row, dict):
            block_name = row.get("name") or row.get("mining_block")
            dependency_group = row.get("dependency_group") or row.get("planning_cut")
            remarks = row.get("remarks")
        else:
            block_name = row
            dependency_group = None
            remarks = None

        if not block_name:
            continue

        if block_name in [entry["name"] for entry in entries]:
            continue

        entries.append(
            {
                "name": block_name,
                "dependency_group": dependency_group,
                "remarks": remarks,
            }
        )

    return entries


def normalise_selected_blocks(selected_blocks):
    return [entry["name"] for entry in normalise_selection_entries(selected_blocks)]


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


def sum_float(values):
    total = 0.0

    for value in values:
        if value is None:
            continue

        try:
            total += float(value)
        except Exception:
            continue

    return total


def first_number(*values):
    for value in values:
        if value is None:
            continue

        try:
            return float(value)
        except Exception:
            continue

    return 0.0


def safe_get(row, fieldname, default=None):
    if not row:
        return default

    if hasattr(row, "get"):
        return row.get(fieldname, default)

    return getattr(row, fieldname, default)


def has_field(doctype, fieldname):
    if fieldname == "name":
        return True

    meta = frappe.get_meta(doctype)
    return bool(meta.has_field(fieldname))


def existing_fields(doctype, fields):
    clean = []

    for fieldname in fields:
        if fieldname == "name" or has_field(doctype, fieldname):
            if fieldname not in clean:
                clean.append(fieldname)

    if "name" not in clean:
        clean.insert(0, "name")

    return clean


def get_block_order_by():
    order_fields = []

    for fieldname in ["cut_no", "block_no", "row_no", "column_no"]:
        if has_field("Mining Block", fieldname):
            order_fields.append("{0} asc".format(fieldname))

    if order_fields:
        return ", ".join(order_fields)

    return "name asc"