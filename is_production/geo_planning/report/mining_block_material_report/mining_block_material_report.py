import frappe
from frappe import _


def execute(filters=None):
    filters = frappe._dict(filters or {})

    columns = get_columns()
    data = get_hierarchical_data(filters)
    chart = get_chart(data)
    summary = get_report_summary(data)

    return columns, data, None, chart, summary


def cint(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def flt(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def get_columns():
    return [
        {
            "label": _("Block / Material / Detail"),
            "fieldname": "tree_node",
            "fieldtype": "Data",
            "width": 320,
        },
        {
            "label": _("Row Type"),
            "fieldname": "row_type",
            "fieldtype": "Data",
            "width": 90,
        },
        {
            "label": _("Geo Project"),
            "fieldname": "geo_project",
            "fieldtype": "Link",
            "options": "Geo Project",
            "width": 150,
        },
        {
            "label": _("Pit Layout"),
            "fieldname": "source_pit_layout",
            "fieldtype": "Link",
            "options": "Geo Pit Layout",
            "width": 150,
        },
        {
            "label": _("Material Stack"),
            "fieldname": "material_stack",
            "fieldtype": "Link",
            "options": "Geo Pit Layout Material Stack",
            "width": 170,
        },
        {
            "label": _("Mining Block"),
            "fieldname": "mining_block",
            "fieldtype": "Link",
            "options": "Mining Block",
            "width": 160,
        },
        {
            "label": _("Block Code"),
            "fieldname": "mining_block_code",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": _("Material / Seam"),
            "fieldname": "material_seam",
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "label": _("Metric Type"),
            "fieldname": "metric_type",
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "label": _("Metric Value"),
            "fieldname": "metric_value",
            "fieldtype": "Float",
            "precision": 3,
            "width": 120,
        },
        {
            "label": _("Unit"),
            "fieldname": "metric_unit",
            "fieldtype": "Data",
            "width": 80,
        },
        {
            "label": _("Thickness"),
            "fieldname": "thickness_value",
            "fieldtype": "Float",
            "precision": 3,
            "width": 110,
        },
        {
            "label": _("Density / RD"),
            "fieldname": "density_value",
            "fieldtype": "Float",
            "precision": 3,
            "width": 110,
        },
        {
            "label": _("Effective Area"),
            "fieldname": "effective_area",
            "fieldtype": "Float",
            "precision": 3,
            "width": 120,
        },
        {
            "label": _("Volume"),
            "fieldname": "volume",
            "fieldtype": "Float",
            "precision": 3,
            "width": 130,
        },
        {
            "label": _("Tonnes"),
            "fieldname": "tonnes",
            "fieldtype": "Float",
            "precision": 3,
            "width": 130,
        },
        {
            "label": _("Avg Value"),
            "fieldname": "avg_value",
            "fieldtype": "Float",
            "precision": 3,
            "width": 110,
        },
        {
            "label": _("Min Value"),
            "fieldname": "min_value",
            "fieldtype": "Float",
            "precision": 3,
            "width": 110,
        },
        {
            "label": _("Max Value"),
            "fieldname": "max_value",
            "fieldtype": "Float",
            "precision": 3,
            "width": 110,
        },
        {
            "label": _("Point Count"),
            "fieldname": "point_count",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": _("Material Status"),
            "fieldname": "material_status",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": _("Planning Status"),
            "fieldname": "planning_status",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": _("Block Status"),
            "fieldname": "block_status",
            "fieldtype": "Data",
            "width": 110,
        },
        {
            "label": _("Cut No"),
            "fieldname": "cut_no",
            "fieldtype": "Int",
            "width": 80,
        },
        {
            "label": _("Block No"),
            "fieldname": "block_no",
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "label": _("Row"),
            "fieldname": "row_no",
            "fieldtype": "Int",
            "width": 70,
        },
        {
            "label": _("Column"),
            "fieldname": "column_no",
            "fieldtype": "Int",
            "width": 80,
        },
        {
            "label": _("Source Geology Run"),
            "fieldname": "source_geology_run",
            "fieldtype": "Link",
            "options": "Geo Pit Layout Geology Run",
            "width": 180,
        },
        {
            "label": _("Source Geology Result"),
            "fieldname": "source_geology_result",
            "fieldtype": "Link",
            "options": "Geo Pit Layout Geology Result",
            "width": 190,
        },
        {
            "label": _("Material Value Record"),
            "fieldname": "material_value_record",
            "fieldtype": "Link",
            "options": "Mining Block Material Value",
            "width": 190,
        },
        {
            "label": _("Summary Record"),
            "fieldname": "summary_record",
            "fieldtype": "Link",
            "options": "Mining Block Material Summary",
            "width": 190,
        },
        {
            "label": _("Parent Node"),
            "fieldname": "parent_node",
            "fieldtype": "Data",
            "hidden": 1,
        },
        {
            "label": _("Sort Key"),
            "fieldname": "sort_key",
            "fieldtype": "Data",
            "hidden": 1,
        },
    ]


def get_hierarchical_data(filters):
    summaries = get_summary_rows(filters)
    values = get_value_rows(filters)

    values_by_block_material = {}

    for value in values:
        key = (value.get("mining_block"), value.get("material_seam"))
        values_by_block_material.setdefault(key, []).append(value)

    summaries_by_block = {}

    for row in summaries:
        summaries_by_block.setdefault(row.get("mining_block"), []).append(row)

    data = []

    for mining_block, material_rows in summaries_by_block.items():
        if not material_rows:
            continue

        first = material_rows[0]

        block_volume = sum(flt(row.get("volume")) for row in material_rows)
        block_tonnes = sum(flt(row.get("tonnes")) for row in material_rows)
        material_count = len(set(row.get("material_seam") for row in material_rows if row.get("material_seam")))

        block_node = f"B::{mining_block}"
        block_label = first.get("mining_block_code") or mining_block

        data.append(
            frappe._dict(
                {
                    "tree_node": block_node,
                    "parent_node": "",
                    "tree_label": f"{block_label} | Materials: {material_count}",
                    "row_type": "Block",
                    "geo_project": first.get("geo_project"),
                    "source_pit_layout": first.get("source_pit_layout"),
                    "material_stack": first.get("material_stack"),
                    "mining_block": mining_block,
                    "mining_block_code": first.get("mining_block_code"),
                    "effective_area": first.get("block_effective_area"),
                    "volume": block_volume,
                    "tonnes": block_tonnes,
                    "material_status": "",
                    "planning_status": first.get("planning_status"),
                    "block_status": first.get("block_status"),
                    "cut_no": first.get("cut_no"),
                    "block_no": first.get("block_no"),
                    "row_no": first.get("row_no"),
                    "column_no": first.get("column_no"),
                    "indent": 0,
                    "is_group": 1,
                    "sort_key": f"{first.get('block_no') or 0:08d}",
                }
            )
        )

        material_rows = sorted(
            material_rows,
            key=lambda row: (
                cint(row.get("material_sort"), 999999),
                row.get("material_seam") or "",
            ),
        )

        for material in material_rows:
            material_seam = material.get("material_seam") or "Unknown Material"
            material_node = f"M::{mining_block}::{material_seam}"

            data.append(
                frappe._dict(
                    {
                        "tree_node": material_node,
                        "parent_node": block_node,
                        "tree_label": material_seam,
                        "row_type": "Material",
                        "geo_project": material.get("geo_project"),
                        "source_pit_layout": material.get("source_pit_layout"),
                        "material_stack": material.get("material_stack"),
                        "mining_block": mining_block,
                        "mining_block_code": material.get("mining_block_code"),
                        "material_seam": material_seam,
                        "thickness_value": material.get("thickness_value"),
                        "density_value": material.get("density_value"),
                        "effective_area": material.get("effective_area"),
                        "volume": material.get("volume"),
                        "tonnes": material.get("tonnes"),
                        "material_status": material.get("material_status"),
                        "planning_status": material.get("planning_status"),
                        "block_status": material.get("block_status"),
                        "summary_record": material.get("summary_record"),
                        "indent": 1,
                        "is_group": 1,
                        "sort_key": f"{material.get('block_no') or 0:08d}-{cint(material.get('material_sort'), 999999):08d}",
                    }
                )
            )

            add_standard_metric_rows(data, material, block_node, material_node)

            source_values = values_by_block_material.get((mining_block, material_seam), [])

            if cint(filters.get("include_qualities"), 1) or cint(filters.get("include_source_values"), 0):
                add_source_value_rows(data, source_values, material_node, filters)

    if cint(filters.get("hide_zero_rows"), 0):
        data = [
            row
            for row in data
            if not (
                row.get("row_type") == "Metric"
                and not flt(row.get("metric_value"))
                and row.get("metric_type") in ("Volume", "Tonnes", "Density / RD", "Thickness")
            )
        ]

    return data


def add_standard_metric_rows(data, material, block_node, material_node):
    mining_block = material.get("mining_block")
    material_seam = material.get("material_seam") or "Unknown Material"

    standard_metrics = [
        {
            "metric_type": "Thickness",
            "metric_value": material.get("thickness_value"),
            "metric_unit": "m",
            "source_record": material.get("thickness_value_record"),
        },
        {
            "metric_type": "Effective Area",
            "metric_value": material.get("effective_area"),
            "metric_unit": "m²",
            "source_record": "",
        },
        {
            "metric_type": "Volume",
            "metric_value": material.get("volume"),
            "metric_unit": "m³",
            "source_record": material.get("thickness_value_record"),
        },
        {
            "metric_type": "Density / RD",
            "metric_value": material.get("density_value"),
            "metric_unit": "t/m³",
            "source_record": material.get("density_value_record"),
        },
        {
            "metric_type": "Tonnes",
            "metric_value": material.get("tonnes"),
            "metric_unit": "t",
            "source_record": material.get("density_value_record") or material.get("thickness_value_record"),
        },
    ]

    for metric in standard_metrics:
        metric_type = metric["metric_type"]
        metric_node = f"K::{mining_block}::{material_seam}::{metric_type}"

        data.append(
            frappe._dict(
                {
                    "tree_node": metric_node,
                    "parent_node": material_node,
                    "tree_label": metric_type,
                    "row_type": "Metric",
                    "geo_project": material.get("geo_project"),
                    "source_pit_layout": material.get("source_pit_layout"),
                    "material_stack": material.get("material_stack"),
                    "mining_block": mining_block,
                    "mining_block_code": material.get("mining_block_code"),
                    "material_seam": material_seam,
                    "metric_type": metric_type,
                    "metric_value": metric.get("metric_value"),
                    "metric_unit": metric.get("metric_unit"),
                    "thickness_value": material.get("thickness_value") if metric_type == "Thickness" else None,
                    "density_value": material.get("density_value") if metric_type == "Density / RD" else None,
                    "effective_area": material.get("effective_area") if metric_type == "Effective Area" else None,
                    "volume": material.get("volume") if metric_type == "Volume" else None,
                    "tonnes": material.get("tonnes") if metric_type == "Tonnes" else None,
                    "material_status": material.get("material_status"),
                    "planning_status": material.get("planning_status"),
                    "block_status": material.get("block_status"),
                    "material_value_record": metric.get("source_record"),
                    "summary_record": material.get("summary_record"),
                    "indent": 2,
                    "is_group": 0,
                    "sort_key": f"{material.get('block_no') or 0:08d}-{material_seam}-{metric_type}",
                }
            )
        )


def add_source_value_rows(data, source_values, material_node, filters):
    include_all = cint(filters.get("include_source_values"), 0)

    for value in source_values:
        value_type = value.get("value_type") or "Other"

        if not include_all and value_type in ("Thickness", "Density"):
            continue

        metric_label = value.get("variable_code") or value.get("variable_name") or value_type
        metric_type = value_type

        metric_node = f"V::{value.get('mining_block')}::{value.get('material_seam')}::{value.get('material_value_record')}"

        data.append(
            frappe._dict(
                {
                    "tree_node": metric_node,
                    "parent_node": material_node,
                    "tree_label": f"{metric_type}: {metric_label}",
                    "row_type": "Metric",
                    "geo_project": value.get("geo_project"),
                    "source_pit_layout": value.get("source_pit_layout"),
                    "material_stack": value.get("material_stack"),
                    "mining_block": value.get("mining_block"),
                    "mining_block_code": value.get("mining_block_code"),
                    "material_seam": value.get("material_seam"),
                    "metric_type": metric_type,
                    "metric_value": value.get("avg_value"),
                    "metric_unit": get_unit_for_value_type(value_type),
                    "avg_value": value.get("avg_value"),
                    "min_value": value.get("min_value"),
                    "max_value": value.get("max_value"),
                    "point_count": value.get("point_count"),
                    "material_status": value.get("material_status"),
                    "planning_status": value.get("planning_status"),
                    "block_status": value.get("block_status"),
                    "source_geology_run": value.get("source_geology_run"),
                    "source_geology_result": value.get("source_geology_result"),
                    "material_value_record": value.get("material_value_record"),
                    "indent": 2,
                    "is_group": 0,
                    "sort_key": value.get("sort_key"),
                }
            )
        )


def get_unit_for_value_type(value_type):
    if value_type == "Thickness":
        return "m"
    if value_type == "Density":
        return "t/m³"
    if value_type == "Depth":
        return "m"
    if value_type == "Elevation":
        return "m"
    if value_type == "Quality":
        return ""
    return ""


def get_summary_rows(filters):
    conditions = []
    values = {}

    if filters.get("geo_project"):
        conditions.append("s.geo_project = %(geo_project)s")
        values["geo_project"] = filters.geo_project

    if filters.get("source_pit_layout"):
        conditions.append("s.source_pit_layout = %(source_pit_layout)s")
        values["source_pit_layout"] = filters.source_pit_layout

    if filters.get("material_stack"):
        conditions.append("s.material_stack = %(material_stack)s")
        values["material_stack"] = filters.material_stack

    if filters.get("mining_block"):
        conditions.append("s.mining_block = %(mining_block)s")
        values["mining_block"] = filters.mining_block

    if filters.get("material_seam"):
        conditions.append("s.material_seam LIKE %(material_seam)s")
        values["material_seam"] = f"%{filters.material_seam}%"

    if filters.get("material_status"):
        conditions.append("s.material_status = %(material_status)s")
        values["material_status"] = filters.material_status

    if filters.get("planning_status"):
        conditions.append("mb.planning_status = %(planning_status)s")
        values["planning_status"] = filters.planning_status

    if filters.get("block_status"):
        conditions.append("mb.block_status = %(block_status)s")
        values["block_status"] = filters.block_status

    if cint(filters.get("show_only_mineable"), 0):
        conditions.append("s.material_status = 'Mineable'")

    where_clause = " AND ".join(conditions)
    if where_clause:
        where_clause = "WHERE " + where_clause

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
            s.material_status,
            s.calculation_status,
            s.thickness_value_record,
            s.density_value_record,

            mb.mining_block_code,
            mb.cut_no,
            mb.block_no,
            mb.row_no,
            mb.column_no,
            mb.effective_area AS block_effective_area,
            mb.block_status,
            mb.planning_status,

            COALESCE(msi.material_sort, 999999) AS material_sort

        FROM `tabMining Block Material Summary` s

        LEFT JOIN `tabMining Block` mb
            ON mb.name = s.mining_block

        LEFT JOIN (
            SELECT
                parent AS material_stack,
                material_seam,
                MIN(COALESCE(sort_order, idx, 999999)) AS material_sort
            FROM `tabGeo Pit Layout Material Stack Item`
            GROUP BY parent, material_seam
        ) msi
            ON msi.material_stack = s.material_stack
            AND msi.material_seam = s.material_seam

        {where_clause}

        ORDER BY
            mb.block_no,
            mb.row_no,
            mb.column_no,
            COALESCE(msi.material_sort, 999999),
            s.material_seam
        """,
        values,
        as_dict=True,
    )


def get_value_rows(filters):
    conditions = []
    values = {}

    if filters.get("geo_project"):
        conditions.append("v.geo_project = %(geo_project)s")
        values["geo_project"] = filters.geo_project

    if filters.get("source_pit_layout"):
        conditions.append("mb.source_pit_layout = %(source_pit_layout)s")
        values["source_pit_layout"] = filters.source_pit_layout

    if filters.get("material_stack"):
        conditions.append("v.material_stack = %(material_stack)s")
        values["material_stack"] = filters.material_stack

    if filters.get("mining_block"):
        conditions.append("v.mining_block = %(mining_block)s")
        values["mining_block"] = filters.mining_block

    if filters.get("material_seam"):
        conditions.append("v.material_seam LIKE %(material_seam)s")
        values["material_seam"] = f"%{filters.material_seam}%"

    if filters.get("material_status"):
        conditions.append("v.material_status = %(material_status)s")
        values["material_status"] = filters.material_status

    if filters.get("planning_status"):
        conditions.append("mb.planning_status = %(planning_status)s")
        values["planning_status"] = filters.planning_status

    if filters.get("block_status"):
        conditions.append("mb.block_status = %(block_status)s")
        values["block_status"] = filters.block_status

    where_clause = " AND ".join(conditions)
    if where_clause:
        where_clause = "WHERE " + where_clause

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
            v.source_geology_result,

            mb.mining_block_code,
            mb.block_no,
            mb.row_no,
            mb.column_no,
            mb.block_status,
            mb.planning_status,

            COALESCE(msi.sort_order, msi.idx, 999999) AS stack_sort_order,

            CONCAT(
                LPAD(COALESCE(mb.block_no, 0), 8, '0'),
                '-',
                LPAD(COALESCE(msi.sort_order, msi.idx, 999999), 8, '0'),
                '-',
                COALESCE(v.value_type, ''),
                '-',
                COALESCE(v.variable_code, v.variable_name, '')
            ) AS sort_key

        FROM `tabMining Block Material Value` v

        LEFT JOIN `tabMining Block` mb
            ON mb.name = v.mining_block

        LEFT JOIN `tabGeo Pit Layout Material Stack Item` msi
            ON msi.name = v.material_stack_item

        {where_clause}

        ORDER BY
            mb.block_no,
            COALESCE(msi.sort_order, msi.idx, 999999),
            v.value_type,
            v.variable_code,
            v.variable_name
        """,
        values,
        as_dict=True,
    )


def get_report_summary(data):
    block_rows = [row for row in data if row.get("row_type") == "Block"]
    material_rows = [row for row in data if row.get("row_type") == "Material"]

    total_blocks = len(block_rows)
    total_material_rows = len(material_rows)
    total_volume = sum(flt(row.get("volume")) for row in material_rows)
    total_tonnes = sum(flt(row.get("tonnes")) for row in material_rows)

    mineable_materials = len([row for row in material_rows if row.get("material_status") == "Mineable"])
    no_data_materials = len([row for row in material_rows if row.get("material_status") == "No Data"])

    return [
        {
            "value": total_blocks,
            "label": _("Blocks"),
            "datatype": "Int",
            "indicator": "blue",
        },
        {
            "value": total_material_rows,
            "label": _("Materials"),
            "datatype": "Int",
            "indicator": "blue",
        },
        {
            "value": total_volume,
            "label": _("Total Volume"),
            "datatype": "Float",
            "indicator": "green",
        },
        {
            "value": total_tonnes,
            "label": _("Total Tonnes"),
            "datatype": "Float",
            "indicator": "green",
        },
        {
            "value": mineable_materials,
            "label": _("Mineable Materials"),
            "datatype": "Int",
            "indicator": "green",
        },
        {
            "value": no_data_materials,
            "label": _("No Data Materials"),
            "datatype": "Int",
            "indicator": "orange",
        },
    ]


def get_chart(data):
    material_rows = [row for row in data if row.get("row_type") == "Material"]

    totals_by_material = {}

    for row in material_rows:
        material = row.get("material_seam") or "Unknown"

        if material not in totals_by_material:
            totals_by_material[material] = {
                "volume": 0,
                "tonnes": 0,
            }

        totals_by_material[material]["volume"] += flt(row.get("volume"))
        totals_by_material[material]["tonnes"] += flt(row.get("tonnes"))

    if not totals_by_material:
        return None

    labels = list(totals_by_material.keys())

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": _("Volume"),
                    "values": [totals_by_material[label]["volume"] for label in labels],
                },
                {
                    "name": _("Tonnes"),
                    "values": [totals_by_material[label]["tonnes"] for label in labels],
                },
            ],
        },
        "type": "bar",
        "height": 280,
    }