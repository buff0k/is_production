import frappe


DEFAULT_VALUE_TYPE = "Thickness"
DEFAULT_DENSITY = 1.5


_MATERIAL_VALUE_FIELDS = [
    "mbmv.name",
    "mbmv.mining_block",
    "mbmv.geo_project",
    "mbmv.material_seam",
    "mbmv.variable_name",
    "mbmv.value_type",
    "mbmv.avg_value",
    "mbmv.min_value",
    "mbmv.max_value",
    "mbmv.point_count",
    "mbmv.effective_area",
    "mbmv.volume",
    "mbmv.density",
    "mbmv.tonnes",
    "mbmv.passes_rule",
    "mbmv.material_status",
    "mb.source_pit_layout",
    "mb.effective_area AS block_effective_area",
    "mb.planning_status",
]


_BLOCK_FIELDS = [
    "name",
    "mining_block_code",
    "geo_project",
    "source_pit_layout",
    "effective_area",
    "planning_status",
    "block_status",
]


_PLANNING_STATUS_RULES = {
    "mineable": "Mineable",
    "not_evaluated": "Not Evaluated",
    "not_mineable": "Not Mineable",
    "review": "Review",
}


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


def _get_mining_blocks_for_layout(source_pit_layout):
    if not source_pit_layout:
        frappe.throw("Source Pit Layout is required.")

    blocks = frappe.get_all(
        "Mining Block",
        filters={"source_pit_layout": source_pit_layout},
        fields=_BLOCK_FIELDS,
        limit_page_length=0,
    )

    if not blocks:
        frappe.throw(f"No Mining Block records found for Source Pit Layout {source_pit_layout}.")

    return blocks


def _get_material_values(source_pit_layout, value_type=None, material_seam=None):
    value_type_clause = "AND mbmv.value_type = %(value_type)s" if value_type else ""
    material_seam_clause = "AND mbmv.material_seam = %(material_seam)s" if material_seam else ""

    rows = frappe.db.sql(
        """
        SELECT
            {fields}
        FROM `tabMining Block Material Value` mbmv
        INNER JOIN `tabMining Block` mb
            ON mb.name = mbmv.mining_block
        WHERE mb.source_pit_layout = %(source_pit_layout)s
        {value_type_clause}
        {material_seam_clause}
        ORDER BY mb.mining_block_code ASC
        """.format(
            fields=",\n            ".join(_MATERIAL_VALUE_FIELDS),
            value_type_clause=value_type_clause,
            material_seam_clause=material_seam_clause,
        ),
        {
            "source_pit_layout": source_pit_layout,
            "value_type": value_type,
            "material_seam": material_seam,
        },
        as_dict=True,
    )

    return rows


def _status_from_value(row, mineable_only=True):
    """
    Keep this deliberately simple for Phase 4.

    If the geology rule passed, material is Mineable.
    If it failed, material is Excluded.
    If there is no value, material is No Data.
    """
    # Preserve "No Data" separately from true failed/excluded blocks.
    if row.get("avg_value") is None or _int(row.get("point_count"), 0) == 0:
        return "No Data"

    current_status = row.get("material_status")

    if current_status == "No Data":
        return "No Data"

    if _int(row.get("passes_rule"), 0) == 1:
        return "Mineable"

    if mineable_only:
        return "Excluded"

    return current_status or "Review"


def _planning_status_from_statuses(statuses):
    if not statuses:
        return _PLANNING_STATUS_RULES["not_evaluated"]

    if "Mineable" in statuses:
        return _PLANNING_STATUS_RULES["mineable"]

    if all(status == "No Data" for status in statuses):
        return _PLANNING_STATUS_RULES["not_evaluated"]

    if all(status in ("Excluded", "Waste", "No Data") for status in statuses):
        return _PLANNING_STATUS_RULES["not_mineable"]

    return _PLANNING_STATUS_RULES["review"]


def _update_mining_block_status(mining_block):
    """
    Update Mining Block.planning_status from its material values.

    Simple rule for now:
    - at least one Mineable material value => Mineable
    - only Excluded/Waste values => Not Mineable
    - only No Data values => Not Evaluated
    - mixed/unclear => Review
    """
    rows = frappe.get_all(
        "Mining Block Material Value",
        filters={"mining_block": mining_block},
        fields=["material_status"],
        limit_page_length=0,
    )

    statuses = [row.material_status for row in rows if row.material_status]
    planning_status = _planning_status_from_statuses(statuses)

    frappe.db.set_value(
        "Mining Block",
        mining_block,
        "planning_status",
        planning_status,
        update_modified=False,
    )

    return planning_status


def _has_no_data(row):
    return row.get("avg_value") is None or _int(row.get("point_count"), 0) == 0


def _get_effective_area(row):
    effective_area = _float(row.get("effective_area"), 0)

    if effective_area <= 0:
        effective_area = _float(row.get("block_effective_area"), 0)

    return effective_area


def _save_material_status(row, material_status):
    doc = frappe.get_doc("Mining Block Material Value", row.name)
    doc.material_status = material_status
    doc.save(ignore_permissions=True)
    return doc


def _save_volume_tonnes(row, effective_area, volume, density, tonnes, material_status):
    doc = frappe.get_doc("Mining Block Material Value", row.name)
    doc.effective_area = effective_area
    doc.volume = volume
    doc.density = density
    doc.tonnes = tonnes
    doc.material_status = material_status
    doc.save(ignore_permissions=True)
    return doc


@frappe.whitelist()
def get_planning_calculation_summary(source_pit_layout, value_type=DEFAULT_VALUE_TYPE, material_seam=None):
    """
    Summary before running Phase 4 calculations.
    """
    blocks = _get_mining_blocks_for_layout(source_pit_layout)
    values = _get_material_values(
        source_pit_layout=source_pit_layout,
        value_type=value_type,
        material_seam=material_seam,
    )

    with_value = [value for value in values if value.avg_value is not None]
    mineable = [value for value in values if value.material_status == "Mineable" or _int(value.passes_rule, 0) == 1]
    no_data = [value for value in values if value.avg_value is None or value.material_status == "No Data"]

    return {
        "source_pit_layout": source_pit_layout,
        "value_type": value_type,
        "material_seam": material_seam,
        "mining_block_count": len(blocks),
        "material_value_count": len(values),
        "values_with_data": len(with_value),
        "mineable_or_passing_values": len(mineable),
        "no_data_values": len(no_data),
    }


@frappe.whitelist()
def calculate_volume_and_tonnes(
    source_pit_layout,
    value_type=DEFAULT_VALUE_TYPE,
    material_seam=None,
    density=DEFAULT_DENSITY,
    mineable_only=1,
    update_block_status=1,
):
    """
    Phase 4:
    Calculate volume and tonnes for Mining Block Material Value records.

    Current formula:
        volume = effective_area * avg_value
        tonnes = volume * density

    Intended first use:
        value_type = Thickness
        avg_value = average thickness per block
        density = default material density entered by planner

    Later, density can come from a density grid/import batch.
    """
    if not source_pit_layout:
        frappe.throw("Source Pit Layout is required.")

    density = _float(density, DEFAULT_DENSITY)

    if density <= 0:
        frappe.throw("Density must be greater than zero.")

    values = _get_material_values(
        source_pit_layout=source_pit_layout,
        value_type=value_type,
        material_seam=material_seam,
    )

    if not values:
        frappe.throw("No Mining Block Material Value records found for the selected filters.")

    updated = 0
    skipped_no_data = 0
    skipped_not_mineable = 0
    total_volume = 0.0
    total_tonnes = 0.0
    mineable_values = 0

    mineable_only = _int(mineable_only, 1)
    update_block_status = _int(update_block_status, 1)
    touched_blocks = set()

    for row in values:
        if _has_no_data(row):
            skipped_no_data += 1
            _save_material_status(row, "No Data")
            touched_blocks.add(row.mining_block)
            continue

        material_status = _status_from_value(row, mineable_only=bool(mineable_only))

        if mineable_only and material_status != "Mineable":
            skipped_not_mineable += 1
            _save_material_status(row, material_status)
            touched_blocks.add(row.mining_block)
            continue

        effective_area = _get_effective_area(row)
        volume = effective_area * _float(row.get("avg_value"))
        tonnes = volume * density

        _save_volume_tonnes(row, effective_area, volume, density, tonnes, material_status)

        total_volume += volume
        total_tonnes += tonnes
        updated += 1

        if material_status == "Mineable":
            mineable_values += 1

        touched_blocks.add(row.mining_block)

    if update_block_status:
        for mining_block in touched_blocks:
            _update_mining_block_status(mining_block)

    frappe.db.commit()

    return {
        "source_pit_layout": source_pit_layout,
        "value_type": value_type,
        "material_seam": material_seam,
        "density": density,
        "records_checked": len(values),
        "records_updated": updated,
        "mineable_values": mineable_values,
        "skipped_no_data": skipped_no_data,
        "skipped_not_mineable": skipped_not_mineable,
        "total_volume": total_volume,
        "total_tonnes": total_tonnes,
    }


@frappe.whitelist()
def get_volume_tonnes_summary(source_pit_layout, value_type=DEFAULT_VALUE_TYPE, material_seam=None):
    """
    Post-calculation summary.
    """
    rows = _get_material_values(
        source_pit_layout=source_pit_layout,
        value_type=value_type,
        material_seam=material_seam,
    )

    total_volume = 0.0
    total_tonnes = 0.0
    mineable_volume = 0.0
    mineable_tonnes = 0.0
    updated = 0

    status_counts = {}

    for row in rows:
        status = row.get("material_status") or "Unspecified"
        status_counts[status] = status_counts.get(status, 0) + 1

        volume = _float(row.get("volume"), 0)
        tonnes = _float(row.get("tonnes"), 0)

        if volume or tonnes:
            updated += 1

        total_volume += volume
        total_tonnes += tonnes

        if status == "Mineable":
            mineable_volume += volume
            mineable_tonnes += tonnes

    return {
        "source_pit_layout": source_pit_layout,
        "value_type": value_type,
        "material_seam": material_seam,
        "material_value_count": len(rows),
        "records_with_volume_or_tonnes": updated,
        "status_counts": status_counts,
        "total_volume": total_volume,
        "total_tonnes": total_tonnes,
        "mineable_volume": mineable_volume,
        "mineable_tonnes": mineable_tonnes,
    }
