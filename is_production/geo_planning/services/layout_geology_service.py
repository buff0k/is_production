import json

import frappe
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, shape


SOURCE_TYPE_CALCULATION = "Geo Calculation Batch"
SOURCE_TYPE_IMPORT = "Geo Import Batch"


def _float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _bool(value):
    return str(value).lower() in ("1", "true", "yes", "y")


def _get_layout_blocks(geo_pit_layout):
    if not geo_pit_layout:
        frappe.throw("Geo Pit Layout is required.")

    blocks = frappe.get_all(
        "Geo Pit Layout Block",
        filters={"geo_pit_layout": geo_pit_layout},
        fields=[
            "name",
            "geo_pit_layout",
            "geo_project",
            "block_code",
            "polygon_geojson",
            "effective_area",
            "inside_percent",
        ],
        order_by="block_no asc",
        limit_page_length=0,
    )

    if not blocks:
        frappe.throw(f"No Geo Pit Layout Block records found for layout {geo_pit_layout}.")

    return blocks


def _get_layout_project(geo_pit_layout):
    return frappe.db.get_value("Geo Pit Layout", geo_pit_layout, "geo_project")


def _get_import_batch_points(geo_project, geo_import_batch):
    if not geo_import_batch:
        frappe.throw("Geo Import Batch is required.")

    points = frappe.get_all(
        "Geo Model Points",
        filters={
            "geo_project": geo_project,
            "import_batch": geo_import_batch,
        },
        fields=["name", "x", "y", "z", "variable_name", "row_no"],
        limit_page_length=0,
    )

    if not points:
        frappe.throw(
            f"No Geo Model Points found for project {geo_project} and import batch {geo_import_batch}."
        )

    return points


def _get_calculation_batch_points(geo_project, geo_calculation_batch):
    if not geo_calculation_batch:
        frappe.throw("Geo Calculation Batch is required.")

    points = frappe.get_all(
        "Geo Calculated Points",
        filters={
            "geo_project": geo_project,
            "calculation_batch": geo_calculation_batch,
        },
        fields=[
            "name",
            "x",
            "y",
            "z",
            "calculated_z",
            "variable_name",
            "variable_code",
            "row_no",
        ],
        limit_page_length=0,
    )

    if not points:
        frappe.throw(
            f"No Geo Calculated Points found for project {geo_project} and calculation batch {geo_calculation_batch}."
        )

    return points


def _source_points_to_dataframe(source_type, points):
    rows = []
    is_calculation_batch = source_type == SOURCE_TYPE_CALCULATION

    for p in points:
        if p.get("x") is None or p.get("y") is None:
            continue

        if is_calculation_batch:
            value = p.get("calculated_z")
            if value is None:
                value = p.get("z")
        else:
            value = p.get("z")

        if value is None:
            continue

        rows.append(
            {
                "point_name": p.get("name"),
                "x": _float(p.get("x")),
                "y": _float(p.get("y")),
                "value": _float(value),
                "variable_name": p.get("variable_name"),
                "variable_code": p.get("variable_code"),
            }
        )

    if not rows:
        frappe.throw("No valid source points with X, Y and value were found.")

    return pd.DataFrame(rows)


def _blocks_to_geodataframe(blocks):
    rows = []

    for b in blocks:
        try:
            geom_json = json.loads(b.get("polygon_geojson") or "{}")
            geom = shape(geom_json)
        except Exception:
            continue

        if geom.is_empty:
            continue

        rows.append(
            {
                "layout_block": b.get("name"),
                "geo_pit_layout": b.get("geo_pit_layout"),
                "geo_project": b.get("geo_project"),
                "block_code": b.get("block_code"),
                "effective_area": _float(b.get("effective_area")),
                "inside_percent": _float(b.get("inside_percent")),
                "geometry": geom,
            }
        )

    if not rows:
        frappe.throw("No valid block polygons were found in the selected layout.")

    return gpd.GeoDataFrame(rows, geometry="geometry")


def _points_to_geodataframe(df):
    return gpd.GeoDataFrame(
        df,
        geometry=[Point(xy) for xy in zip(df["x"], df["y"])],
    )


def _passes_rule(value, operator, rule_value=None, rule_value_to=None):
    if value is None:
        return False

    value = _float(value)
    rule_value = _float(rule_value)
    rule_value_to = _float(rule_value_to)

    if operator == "Greater Than":
        return value > rule_value
    if operator == "Greater Than Or Equal":
        return value >= rule_value
    if operator == "Less Than":
        return value < rule_value
    if operator == "Less Than Or Equal":
        return value <= rule_value
    if operator == "Equal":
        return value == rule_value
    if operator == "Between":
        low = min(rule_value, rule_value_to)
        high = max(rule_value, rule_value_to)
        return low <= value <= high
    if operator == "Outside":
        low = min(rule_value, rule_value_to)
        high = max(rule_value, rule_value_to)
        return value < low or value > high

    return True


def _summarise_points_by_block(blocks_gdf, points_gdf):
    """
    Assign point values to block polygons using GeoPandas spatial join.
    Returns dict keyed by Geo Pit Layout Block name.
    """
    joined = gpd.sjoin(
        points_gdf,
        blocks_gdf[["layout_block", "block_code", "geometry"]],
        how="inner",
        predicate="within",
    )

    summaries = {}

    if joined.empty:
        return summaries

    for layout_block, group in joined.groupby("layout_block"):
        values = group["value"].astype(float)
        block_code = group["block_code"].iloc[0]

        summaries[layout_block] = {
            "layout_block": layout_block,
            "block_code": block_code,
            "avg_value": float(values.mean()),
            "min_value": float(values.min()),
            "max_value": float(values.max()),
            "point_count": int(values.count()),
        }

    return summaries


def _source_batch_fields(source_type, geo_import_batch=None, geo_calculation_batch=None):
    return {
        "geo_import_batch": geo_import_batch if source_type == SOURCE_TYPE_IMPORT else None,
        "geo_calculation_batch": geo_calculation_batch if source_type == SOURCE_TYPE_CALCULATION else None,
    }


@frappe.whitelist()
def preview_layout_geology(
    geo_pit_layout,
    source_type,
    geo_import_batch=None,
    geo_calculation_batch=None,
    rule_enabled=0,
    rule_operator=None,
    rule_value=None,
    rule_value_to=None,
):
    """
    Preview geology assignment without saving Geo Pit Layout Geology Run/Result records.
    """
    geo_project = _get_layout_project(geo_pit_layout)

    blocks = _get_layout_blocks(geo_pit_layout)
    blocks_gdf = _blocks_to_geodataframe(blocks)

    if source_type == SOURCE_TYPE_CALCULATION:
        source_points = _get_calculation_batch_points(geo_project, geo_calculation_batch)
    else:
        source_type = SOURCE_TYPE_IMPORT
        source_points = _get_import_batch_points(geo_project, geo_import_batch)

    points_df = _source_points_to_dataframe(source_type, source_points)
    points_gdf = _points_to_geodataframe(points_df)

    summaries = _summarise_points_by_block(blocks_gdf, points_gdf)

    rule_on = _bool(rule_enabled)
    results = []
    passing = 0
    failing = 0
    no_data = 0

    for block in blocks:
        layout_block = block.get("name")
        row = summaries.get(layout_block)

        if not row:
            no_data += 1
            results.append(
                {
                    "layout_block": layout_block,
                    "block_code": block.get("block_code"),
                    "avg_value": None,
                    "min_value": None,
                    "max_value": None,
                    "point_count": 0,
                    "passes_rule": 0,
                    "result_status": "No Data",
                }
            )
            continue

        passes = 1
        status = "Review"

        if rule_on:
            passes = 1 if _passes_rule(row["avg_value"], rule_operator, rule_value, rule_value_to) else 0
            status = "Pass" if passes else "Fail"
        else:
            status = "Review"

        if status == "Pass":
            passing += 1
        elif status == "Fail":
            failing += 1

        results.append(
            {
                "layout_block": layout_block,
                "block_code": row["block_code"],
                "avg_value": row["avg_value"],
                "min_value": row["min_value"],
                "max_value": row["max_value"],
                "point_count": row["point_count"],
                "passes_rule": passes,
                "result_status": status,
            }
        )

    return {
        "geo_project": geo_project,
        "geo_pit_layout": geo_pit_layout,
        "source_type": source_type,
        "block_count": len(blocks),
        "result_count": len(results),
        "passing_blocks": passing,
        "failing_blocks": failing,
        "no_data_blocks": no_data,
        "results": results,
    }


@frappe.whitelist()
def create_layout_geology_run(
    run_name,
    geo_pit_layout,
    source_type,
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
    """
    Apply one geology source batch to one saved layout and save per-block results.
    Creates:
    - Geo Pit Layout Geology Run
    - Geo Pit Layout Geology Result records
    """
    if not run_name:
        frappe.throw("Run Name is required.")

    geo_project = _get_layout_project(geo_pit_layout)

    payload = preview_layout_geology(
        geo_pit_layout=geo_pit_layout,
        source_type=source_type,
        geo_import_batch=geo_import_batch,
        geo_calculation_batch=geo_calculation_batch,
        rule_enabled=rule_enabled,
        rule_operator=rule_operator,
        rule_value=rule_value,
        rule_value_to=rule_value_to,
    )

    source_fields = _source_batch_fields(
        payload["source_type"],
        geo_import_batch=geo_import_batch,
        geo_calculation_batch=geo_calculation_batch,
    )

    run = frappe.new_doc("Geo Pit Layout Geology Run")
    run.run_name = run_name
    run.geo_project = geo_project
    run.geo_pit_layout = geo_pit_layout
    run.source_type = payload["source_type"]
    run.geo_import_batch = source_fields["geo_import_batch"]
    run.geo_calculation_batch = source_fields["geo_calculation_batch"]
    run.variable_name = variable_name
    run.value_meaning = value_meaning
    run.rule_enabled = 1 if _bool(rule_enabled) else 0
    run.rule_operator = rule_operator
    run.rule_value = _float(rule_value) if rule_value not in (None, "") else None
    run.rule_value_to = _float(rule_value_to) if rule_value_to not in (None, "") else None
    run.processing_status = "Running"
    run.remarks = remarks
    run.insert(ignore_permissions=True)

    passing = 0
    failing = 0
    no_data = 0

    for result in payload["results"]:
        doc = frappe.new_doc("Geo Pit Layout Geology Result")
        doc.geology_run = run.name
        doc.geo_pit_layout = geo_pit_layout
        doc.layout_block = result.get("layout_block")
        doc.geo_project = geo_project
        doc.block_code = result.get("block_code")
        doc.source_type = payload["source_type"]
        doc.geo_import_batch = source_fields["geo_import_batch"]
        doc.geo_calculation_batch = source_fields["geo_calculation_batch"]
        doc.variable_name = variable_name
        doc.avg_value = result.get("avg_value")
        doc.min_value = result.get("min_value")
        doc.max_value = result.get("max_value")
        doc.point_count = result.get("point_count")
        doc.passes_rule = result.get("passes_rule")
        doc.result_status = result.get("result_status")
        doc.insert(ignore_permissions=True)

        if doc.result_status == "Pass":
            passing += 1
        elif doc.result_status == "Fail":
            failing += 1
        elif doc.result_status == "No Data":
            no_data += 1

    run.passing_blocks = passing
    run.failing_blocks = failing
    run.no_data_blocks = no_data
    run.processing_status = "Complete"
    run.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "geology_run": run.name,
        "geo_pit_layout": geo_pit_layout,
        "source_type": payload["source_type"],
        "results_created": len(payload["results"]),
        "passing_blocks": passing,
        "failing_blocks": failing,
        "no_data_blocks": no_data,
    }


@frappe.whitelist()
def get_geology_results(geology_run):
    if not geology_run:
        frappe.throw("Geology Run is required.")

    return frappe.get_all(
        "Geo Pit Layout Geology Result",
        filters={"geology_run": geology_run},
        fields=[
            "name",
            "geology_run",
            "geo_pit_layout",
            "layout_block",
            "block_code",
            "avg_value",
            "min_value",
            "max_value",
            "point_count",
            "passes_rule",
            "result_status",
        ],
        order_by="block_code asc",
        limit_page_length=0,
    )
