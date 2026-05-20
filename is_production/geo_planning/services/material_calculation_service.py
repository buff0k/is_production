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
        return json.dumps(value, default=str, indent=2)
    except Exception:
        return "{}"


def _get_stack(material_stack):
    if not material_stack:
        frappe.throw("Geo Pit Layout Material Stack is required.")

    return frappe.get_doc("Geo Pit Layout Material Stack", material_stack)


def _get_stack_items(stack):
    from is_production.geo_planning.services.material_stack_service import _get_stack_items
    return _get_stack_items(stack)


def _get_material_values(material_stack):
    if not _has_field("Mining Block Material Value", "material_stack"):
        frappe.throw("Mining Block Material Value.material_stack field is required.")

    return frappe.get_all(
        "Mining Block Material Value",
        filters={"material_stack": material_stack},
        fields=[
            "name",
            "mining_block",
            "geo_project",
            "material_stack",
            "material_stack_item",
            "source_geology_run",
            "source_geology_result",
            "material_seam",
            "value_type",
            "variable_name",
            "avg_value",
            "min_value",
            "max_value",
            "point_count",
            "effective_area",
            "passes_rule",
            "material_status",
        ],
        limit_page_length=0,
    )


def _get_mining_blocks(names):
    if not names:
        return {}

    rows = frappe.get_all(
        "Mining Block",
        filters={"name": ["in", list(names)]},
        fields=[
            "name",
            "geo_project",
            "source_pit_layout",
            "source_layout_block",
            "effective_area",
            "planning_status",
        ],
        limit_page_length=0,
    )

    return {row.name: row for row in rows}


def _group_values(rows):
    grouped = {}

    for row in rows:
        key = (row.mining_block, row.material_seam)
        grouped.setdefault(key, []).append(row)

    return grouped


def _stack_item_lookup(items):
    return {item["name"]: item for item in items}


def _is_no_data(row):
    return row.avg_value is None or _int(row.point_count, 0) <= 0 or row.material_status == "No Data"


def _is_excluded(row):
    return row.material_status in ("Excluded", "Waste")


def _choose_thickness_value(rows, item_by_name):
    candidates = []

    for row in rows:
        item = item_by_name.get(row.material_stack_item)

        use_for_volume = _int(item.get("use_for_volume"), 0) if item else 0

        if row.value_type == "Thickness" or use_for_volume:
            candidates.append(row)

    if not candidates:
        return None

    candidates.sort(key=lambda r: (0 if r.value_type == "Thickness" else 1, r.name))
    return candidates[0]


def _choose_density_value(rows, item_by_name):
    candidates = []

    for row in rows:
        item = item_by_name.get(row.material_stack_item)
        use_for_density = _int(item.get("use_for_density"), 0) if item else 0

        if row.value_type == "Density" or use_for_density:
            candidates.append(row)

    if not candidates:
        return None

    candidates.sort(key=lambda r: (0 if r.value_type == "Density" else 1, r.name))
    return candidates[0]


def _manual_density_for_material(material_seam, items):
    for item in items:
        if item["material_seam"] != material_seam:
            continue

        if item["density_source"] == "Manual" and _float(item["manual_density"], 0) > 0:
            return _float(item["manual_density"], 0)

    for item in items:
        if item["material_seam"] != material_seam:
            continue

        if _float(item["manual_density"], 0) > 0:
            return _float(item["manual_density"], 0)

    return None


def _material_requires_tonnes(material_seam, items):
    for item in items:
        if item["material_seam"] == material_seam and _int(item["use_for_tonnes"], 0):
            return True

    return False


def _effective_area(row, mining_block):
    area = _float(row.effective_area, 0)

    if area <= 0 and mining_block:
        area = _float(mining_block.effective_area, 0)

    return area


def _summary_status(thickness_row):
    if not thickness_row:
        return "No Data"

    if _is_no_data(thickness_row):
        return "No Data"

    if _is_excluded(thickness_row):
        return "Excluded"

    return "Mineable"


def _upsert_summary(
    mining_block,
    mb,
    stack,
    material_seam,
    thickness_row,
    density_row,
    thickness,
    density,
    effective_area,
    volume,
    tonnes,
    material_status,
):
    filters = {
        "mining_block": mining_block,
        "material_stack": stack.name,
        "material_seam": material_seam,
    }

    existing = frappe.db.get_value("Mining Block Material Summary", filters, "name")

    if existing:
        doc = frappe.get_doc("Mining Block Material Summary", existing)
        created = 0
        updated = 1
    else:
        doc = frappe.new_doc("Mining Block Material Summary")
        created = 1
        updated = 0

    doc.mining_block = mining_block
    doc.geo_project = mb.geo_project if mb else stack.geo_project
    doc.source_pit_layout = stack.geo_pit_layout
    doc.material_stack = stack.name
    doc.material_seam = material_seam

    _set_if_field(doc, "thickness_value_record", thickness_row.name if thickness_row else None)
    doc.thickness_value = thickness
    doc.thickness_point_count = _int(thickness_row.point_count, 0) if thickness_row else 0

    _set_if_field(doc, "density_value_record", density_row.name if density_row else None)
    doc.density_value = density
    doc.density_point_count = _int(density_row.point_count, 0) if density_row else 0

    doc.effective_area = effective_area
    doc.volume = volume
    doc.tonnes = tonnes
    doc.material_status = material_status
    doc.calculation_status = "Calculated"
    doc.remarks = "Calculated from Geo Pit Layout Material Stack."

    if existing:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True)

    return doc, created, updated


def _update_value_row(row, effective_area, volume, density, tonnes, material_status):
    doc = frappe.get_doc("Mining Block Material Value", row.name)
    doc.effective_area = effective_area
    doc.volume = volume
    doc.density = density
    doc.tonnes = tonnes
    doc.material_status = material_status
    doc.save(ignore_permissions=True)


def _update_block_planning_status(mining_block):
    summaries = frappe.get_all(
        "Mining Block Material Summary",
        filters={"mining_block": mining_block},
        fields=["material_status"],
        limit_page_length=0,
    )

    statuses = [row.material_status for row in summaries if row.material_status]

    if not statuses:
        status = "Not Evaluated"
    elif "Mineable" in statuses:
        status = "Mineable"
    elif all(s in ("No Data",) for s in statuses):
        status = "Not Evaluated"
    elif all(s in ("Excluded", "Waste", "No Data") for s in statuses):
        status = "Not Mineable"
    else:
        status = "Review"

    frappe.db.set_value(
        "Mining Block",
        mining_block,
        "planning_status",
        status,
        update_modified=False,
    )

    return status


@frappe.whitelist()
def calculate_material_stack(
    material_stack,
    mineable_only=0,
    update_block_status=1,
):
    """
    Calculate per-block/per-material summaries from attached Mining Block Material Value rows.

    Formula:
        volume = effective_area * thickness
        tonnes = volume * density

    Density can come from:
        - a stack item with value_type/use_for_density
        - manual_density on a stack item
        - blank/None for volume-only materials
    """
    stack = _get_stack(material_stack)
    items = _get_stack_items(stack)
    item_by_name = _stack_item_lookup(items)

    values = _get_material_values(stack.name)

    if not values:
        frappe.throw("No Mining Block Material Value rows found for this Material Stack. Attach the stack first.")

    mining_block_names = set(row.mining_block for row in values if row.mining_block)
    mining_blocks = _get_mining_blocks(mining_block_names)

    grouped = _group_values(values)

    summaries_created = 0
    summaries_updated = 0
    values_updated = 0
    no_data_count = 0
    error_count = 0
    total_volume = 0.0
    total_tonnes = 0.0
    total_mineable_volume = 0.0
    total_mineable_tonnes = 0.0
    touched_blocks = set()

    for (mining_block, material_seam), rows in grouped.items():
        mb = mining_blocks.get(mining_block)
        thickness_row = _choose_thickness_value(rows, item_by_name)
        density_row = _choose_density_value(rows, item_by_name)

        material_status = _summary_status(thickness_row)

        if material_status == "No Data":
            no_data_count += 1

        if thickness_row and not _is_no_data(thickness_row):
            thickness = _float(thickness_row.avg_value, 0)
        else:
            thickness = None

        effective_area = _effective_area(thickness_row, mb) if thickness_row else (_float(mb.effective_area, 0) if mb else 0)

        requires_tonnes = _material_requires_tonnes(material_seam, items)

        density = None

        if density_row and not _is_no_data(density_row):
            density = _float(density_row.avg_value, 0)

        if not density or density <= 0:
            density = _manual_density_for_material(material_seam, items)

        volume = None
        tonnes = None

        if thickness is not None and effective_area > 0 and material_status != "No Data":
            volume = effective_area * thickness

            if requires_tonnes and density and density > 0:
                tonnes = volume * density

        if _int(mineable_only, 0) and material_status != "Mineable":
            volume = None
            tonnes = None

        if volume:
            total_volume += volume

        if tonnes:
            total_tonnes += tonnes

        if material_status == "Mineable":
            total_mineable_volume += _float(volume, 0)
            total_mineable_tonnes += _float(tonnes, 0)

        try:
            summary_doc, created, updated = _upsert_summary(
                mining_block=mining_block,
                mb=mb,
                stack=stack,
                material_seam=material_seam,
                thickness_row=thickness_row,
                density_row=density_row,
                thickness=thickness,
                density=density,
                effective_area=effective_area,
                volume=volume,
                tonnes=tonnes,
                material_status=material_status,
            )

            summaries_created += created
            summaries_updated += updated

            if thickness_row:
                _update_value_row(
                    row=thickness_row,
                    effective_area=effective_area,
                    volume=volume,
                    density=density,
                    tonnes=tonnes,
                    material_status=material_status,
                )
                values_updated += 1

            touched_blocks.add(mining_block)

        except Exception:
            error_count += 1
            frappe.log_error(frappe.get_traceback(), "Material Stack Calculation Row Error")

    if _int(update_block_status, 1):
        for mining_block in touched_blocks:
            _update_block_planning_status(mining_block)

    stack.calculation_status = "Complete"
    stack.last_calculated_on = now()
    stack.total_volume = total_volume
    stack.total_tonnes = total_tonnes
    stack.mineable_block_count = len([
        1 for block in touched_blocks
        if frappe.db.get_value("Mining Block", block, "planning_status") == "Mineable"
    ])
    stack.no_data_block_count = no_data_count
    stack.error_log = None
    stack.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "material_stack": stack.name,
        "geo_pit_layout": stack.geo_pit_layout,
        "material_value_count": len(values),
        "summary_rows_created": summaries_created,
        "summary_rows_updated": summaries_updated,
        "material_values_updated": values_updated,
        "no_data_count": no_data_count,
        "error_count": error_count,
        "total_volume": total_volume,
        "total_tonnes": total_tonnes,
        "total_mineable_volume": total_mineable_volume,
        "total_mineable_tonnes": total_mineable_tonnes,
        "blocks_touched": len(touched_blocks),
    }


@frappe.whitelist()
def get_material_calculation_summary(material_stack):
    stack = _get_stack(material_stack)

    value_count = frappe.db.count("Mining Block Material Value", {"material_stack": stack.name}) if _has_field("Mining Block Material Value", "material_stack") else 0

    summary_count = 0
    total_volume = 0.0
    total_tonnes = 0.0

    if frappe.db.exists("DocType", "Mining Block Material Summary"):
        rows = frappe.db.sql(
            """
            SELECT
                COUNT(name) AS summary_count,
                SUM(COALESCE(volume, 0)) AS total_volume,
                SUM(COALESCE(tonnes, 0)) AS total_tonnes
            FROM `tabMining Block Material Summary`
            WHERE material_stack = %(material_stack)s
            """,
            {"material_stack": stack.name},
            as_dict=True,
        )[0]

        summary_count = _int(rows.summary_count, 0)
        total_volume = _float(rows.total_volume, 0)
        total_tonnes = _float(rows.total_tonnes, 0)

    return {
        "material_stack": stack.name,
        "geo_pit_layout": stack.geo_pit_layout,
        "material_value_count": value_count,
        "summary_count": summary_count,
        "total_volume": total_volume,
        "total_tonnes": total_tonnes,
        "stack_total_volume": stack.total_volume,
        "stack_total_tonnes": stack.total_tonnes,
        "calculation_status": stack.calculation_status,
        "attach_status": stack.attach_status,
    }