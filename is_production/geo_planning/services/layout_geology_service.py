import json

import frappe
import geopandas as gpd
import pandas as pd
from frappe.utils import now
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


def _int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _bool(value):
    return str(value).lower() in ("1", "true", "yes", "y")


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
        return json.dumps(value, default=str)
    except Exception:
        return "{}"


def _get_layout_project(geo_pit_layout):
    if not geo_pit_layout:
        frappe.throw("Geo Pit Layout is required.")

    geo_project = frappe.db.get_value("Geo Pit Layout", geo_pit_layout, "geo_project")

    if not geo_project:
        frappe.throw(f"Geo Project could not be found for layout {geo_pit_layout}.")

    return geo_project


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


def _get_import_batch_field():
    if _has_field("Geo Model Points", "import_batch"):
        return "import_batch"
    if _has_field("Geo Model Points", "geo_import_batch"):
        return "geo_import_batch"
    return "import_batch"


def _get_import_batch_points(geo_project, geo_import_batch):
    if not geo_import_batch:
        frappe.throw("Geo Import Batch is required.")

    batch_field = _get_import_batch_field()

    fields = ["name", "x", "y", "z", "variable_name", "row_no"]

    if _has_field("Geo Model Points", "variable_code"):
        fields.append("variable_code")

    points = frappe.get_all(
        "Geo Model Points",
        filters={
            "geo_project": geo_project,
            batch_field: geo_import_batch,
        },
        fields=fields,
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

    fields = [
        "name",
        "x",
        "y",
        "z",
        "calculated_z",
        "variable_name",
        "variable_code",
        "row_no",
    ]

    points = frappe.get_all(
        "Geo Calculated Points",
        filters={
            "geo_project": geo_project,
            "calculation_batch": geo_calculation_batch,
        },
        fields=fields,
        limit_page_length=0,
    )

    if not points:
        frappe.throw(
            f"No Geo Calculated Points found for project {geo_project} and calculation batch {geo_calculation_batch}."
        )

    return points


def _source_points_to_dataframe(source_type, points, variable_name=None, variable_code=None):
    rows = []
    is_calculation_batch = source_type == SOURCE_TYPE_CALCULATION

    for p in points:
        if p.get("x") is None or p.get("y") is None:
            continue

        point_variable_name = p.get("variable_name")
        point_variable_code = p.get("variable_code")

        if variable_name and point_variable_name and point_variable_name != variable_name:
            continue

        if variable_code and point_variable_code and point_variable_code != variable_code:
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
                "variable_name": point_variable_name,
                "variable_code": point_variable_code,
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
        return summaries, 0

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

    return summaries, len(joined)


def _source_batch_fields(source_type, geo_import_batch=None, geo_calculation_batch=None):
    return {
        "geo_import_batch": geo_import_batch if source_type == SOURCE_TYPE_IMPORT else None,
        "geo_calculation_batch": geo_calculation_batch if source_type == SOURCE_TYPE_CALCULATION else None,
    }


def _normalise_source_type(source_type):
    if source_type == SOURCE_TYPE_CALCULATION:
        return SOURCE_TYPE_CALCULATION
    return SOURCE_TYPE_IMPORT


@frappe.whitelist()
def preview_layout_geology(
    geo_pit_layout,
    source_type,
    geo_import_batch=None,
    geo_calculation_batch=None,
    variable_name=None,
    variable_code=None,
    rule_enabled=0,
    rule_operator=None,
    rule_value=None,
    rule_value_to=None,
):
    """
    Preview geology assignment without saving Geo Pit Layout Geology Result records.
    """
    geo_project = _get_layout_project(geo_pit_layout)

    blocks = _get_layout_blocks(geo_pit_layout)
    blocks_gdf = _blocks_to_geodataframe(blocks)

    source_type = _normalise_source_type(source_type)

    if source_type == SOURCE_TYPE_CALCULATION:
        source_points = _get_calculation_batch_points(geo_project, geo_calculation_batch)
    else:
        source_points = _get_import_batch_points(geo_project, geo_import_batch)

    points_df = _source_points_to_dataframe(
        source_type=source_type,
        points=source_points,
        variable_name=variable_name,
        variable_code=variable_code,
    )
    points_gdf = _points_to_geodataframe(points_df)

    summaries, assigned_points = _summarise_points_by_block(blocks_gdf, points_gdf)

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
        "total_points": len(points_df),
        "assigned_points": assigned_points,
        "block_count": len(blocks),
        "result_count": len(results),
        "passing_blocks": passing,
        "failing_blocks": failing,
        "no_data_blocks": no_data,
        "results": results,
    }


def _get_result_downstream_links(geology_run):
    material_values = 0

    if frappe.db.exists("DocType", "Mining Block Material Value"):
        material_values = frappe.db.count(
            "Mining Block Material Value",
            {"source_geology_run": geology_run},
        )

    return {
        "material_values": _int(material_values, 0),
        "has_downstream_links": bool(material_values),
    }


def clear_geology_results(geology_run, force=0):
    downstream = _get_result_downstream_links(geology_run)

    if downstream["has_downstream_links"] and not _int(force, 0):
        frappe.throw(
            "This geology run already has downstream material values. "
            "Do not delete results. Rerun assignment in update-in-place mode instead."
        )

    existing = frappe.get_all(
        "Geo Pit Layout Geology Result",
        filters={"geology_run": geology_run},
        pluck="name",
        limit_page_length=0,
    )

    for name in existing:
        frappe.delete_doc("Geo Pit Layout Geology Result", name, ignore_permissions=True)

    return len(existing)


def _get_existing_results_by_block(geology_run):
    rows = frappe.get_all(
        "Geo Pit Layout Geology Result",
        filters={"geology_run": geology_run},
        fields=["name", "layout_block"],
        limit_page_length=0,
    )

    out = {}
    for row in rows:
        if row.layout_block:
            out[row.layout_block] = row.name

    return out


def _populate_result_doc(doc, run, result, source_fields):
    doc.geology_run = run.name
    doc.geo_pit_layout = run.geo_pit_layout
    doc.layout_block = result.get("layout_block")
    doc.geo_project = run.geo_project
    doc.block_code = result.get("block_code")
    doc.source_type = run.source_type
    doc.geo_import_batch = source_fields["geo_import_batch"]
    doc.geo_calculation_batch = source_fields["geo_calculation_batch"]
    doc.variable_name = run.variable_name
    doc.avg_value = result.get("avg_value")
    doc.min_value = result.get("min_value")
    doc.max_value = result.get("max_value")
    doc.point_count = result.get("point_count")
    doc.passes_rule = result.get("passes_rule")
    doc.result_status = result.get("result_status")


def run_geology_assignment(
    geology_run,
    clear_existing_results=0,
    overwrite_existing=1,
):
    """
    Worker-safe method.

    Reads an existing Geo Pit Layout Geology Run and creates/updates
    Geo Pit Layout Geology Result rows.
    """
    if not geology_run:
        frappe.throw("Geology Run is required.")

    run = frappe.get_doc("Geo Pit Layout Geology Run", geology_run)

    if not run.geo_pit_layout:
        frappe.throw("Geo Pit Layout is required on the Geology Run.")

    if not run.geo_project:
        run.geo_project = _get_layout_project(run.geo_pit_layout)

    run.source_type = _normalise_source_type(run.source_type)

    if run.source_type == SOURCE_TYPE_IMPORT and not run.geo_import_batch:
        frappe.throw("Geo Import Batch is required for Source Type Geo Import Batch.")

    if run.source_type == SOURCE_TYPE_CALCULATION and not run.geo_calculation_batch:
        frappe.throw("Geo Calculation Batch is required for Source Type Geo Calculation Batch.")

    downstream = _get_result_downstream_links(run.name)

    if downstream["has_downstream_links"]:
        clear_existing_results = 0
        overwrite_existing = 1

    run.processing_status = "Running"
    _set_if_field(run, "assignment_started_on", now())
    _set_if_field(run, "assignment_error", None)
    run.save(ignore_permissions=True)

    if _int(clear_existing_results, 0):
        clear_geology_results(run.name)

    payload = preview_layout_geology(
        geo_pit_layout=run.geo_pit_layout,
        source_type=run.source_type,
        geo_import_batch=run.geo_import_batch,
        geo_calculation_batch=run.geo_calculation_batch,
        variable_name=run.variable_name,
        variable_code=run.get("variable_code"),
        rule_enabled=run.rule_enabled,
        rule_operator=run.rule_operator,
        rule_value=run.rule_value,
        rule_value_to=run.rule_value_to,
    )

    source_fields = _source_batch_fields(
        payload["source_type"],
        geo_import_batch=run.geo_import_batch,
        geo_calculation_batch=run.geo_calculation_batch,
    )

    existing_by_block = _get_existing_results_by_block(run.name)

    created = 0
    updated = 0
    skipped = 0
    passing = 0
    failing = 0
    no_data = 0

    for result in payload["results"]:
        layout_block = result.get("layout_block")
        existing = existing_by_block.get(layout_block)

        if existing and not _int(overwrite_existing, 1):
            skipped += 1
            continue

        if existing:
            doc = frappe.get_doc("Geo Pit Layout Geology Result", existing)
            updated += 1
        else:
            doc = frappe.new_doc("Geo Pit Layout Geology Result")
            created += 1

        _populate_result_doc(doc, run, result, source_fields)

        if existing:
            doc.save(ignore_permissions=True)
        else:
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
    _set_if_field(run, "assignment_completed_on", now())
    _set_if_field(run, "assignment_error", None)
    run.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "geology_run": run.name,
        "geo_pit_layout": run.geo_pit_layout,
        "source_type": payload["source_type"],
        "total_points": payload.get("total_points", 0),
        "assigned_points": payload.get("assigned_points", 0),
        "block_count": payload.get("block_count", 0),
        "results_checked": len(payload["results"]),
        "results_created": created,
        "results_updated": updated,
        "results_skipped": skipped,
        "passing_blocks": passing,
        "failing_blocks": failing,
        "no_data_blocks": no_data,
        "update_in_place": 1 if downstream["has_downstream_links"] else 0,
        "downstream_material_values": downstream["material_values"],
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
    Compatibility method for old viewer workflow.

    New workflow should prefer:
        Create Geo Pit Layout Geology Run
        Click Run Assignment
    """
    if not run_name:
        frappe.throw("Run Name is required.")

    geo_project = _get_layout_project(geo_pit_layout)
    source_type = _normalise_source_type(source_type)
    source_fields = _source_batch_fields(
        source_type,
        geo_import_batch=geo_import_batch,
        geo_calculation_batch=geo_calculation_batch,
    )

    run = frappe.new_doc("Geo Pit Layout Geology Run")
    run.run_name = run_name
    run.geo_project = geo_project
    run.geo_pit_layout = geo_pit_layout
    run.source_type = source_type
    run.geo_import_batch = source_fields["geo_import_batch"]
    run.geo_calculation_batch = source_fields["geo_calculation_batch"]
    run.variable_name = variable_name
    run.value_meaning = value_meaning
    run.rule_enabled = 1 if _bool(rule_enabled) else 0
    run.rule_operator = rule_operator
    run.rule_value = _float(rule_value) if rule_value not in (None, "") else None
    run.rule_value_to = _float(rule_value_to) if rule_value_to not in (None, "") else None
    run.processing_status = "Draft"
    run.remarks = remarks
    run.insert(ignore_permissions=True)

    result = run_geology_assignment(
        geology_run=run.name,
        clear_existing_results=0,
        overwrite_existing=1,
    )

    return result


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
        order_by="block_code asc",
        limit_page_length=0,
    )


@frappe.whitelist()
def get_geology_assignment_summary(geology_run):
    if not geology_run:
        frappe.throw("Geology Run is required.")

    run = frappe.get_doc("Geo Pit Layout Geology Run", geology_run)

    result_count = frappe.db.count(
        "Geo Pit Layout Geology Result",
        {"geology_run": geology_run},
    )

    downstream = _get_result_downstream_links(geology_run)

    return {
        "geology_run": run.name,
        "run_name": run.run_name,
        "geo_project": run.geo_project,
        "geo_pit_layout": run.geo_pit_layout,
        "source_type": run.source_type,
        "geo_import_batch": run.geo_import_batch,
        "geo_calculation_batch": run.geo_calculation_batch,
        "variable_name": run.variable_name,
        "variable_code": run.get("variable_code"),
        "value_meaning": run.value_meaning,
        "processing_status": run.processing_status,
        "result_count": result_count,
        "passing_blocks": run.passing_blocks,
        "failing_blocks": run.failing_blocks,
        "no_data_blocks": run.no_data_blocks,
        "downstream": downstream,
    }