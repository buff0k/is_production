import frappe
from frappe import _


@frappe.whitelist()
def get_spatial_overlay(
    source_type=None,
    geo_project=None,
    geo_import_batch=None,
    pit_outline_batch=None,
    geo_pit_layout=None,
    outline_mode="Point Order",
):
    source_type = source_type or "None"
    outline_mode = outline_mode or "Point Order"

    if source_type == "None":
        return {
            "points": [],
            "source_type": source_type,
            "message": "No spatial source selected.",
        }

    if source_type == "Geo Import Batch":
        if not geo_import_batch:
            frappe.throw(_("Geo Import Batch is required."))

        points = get_points_from_import_batch(
            geo_import_batch=geo_import_batch,
            geo_project=geo_project,
        )

    elif source_type == "Pit Outline Points":
        if not pit_outline_batch and not geo_import_batch:
            frappe.throw(_("Pit Outline Batch is required."))

        points = get_points_from_pit_outline_points(
            geo_project=geo_project,
            geo_import_batch=pit_outline_batch or geo_import_batch,
        )

    elif source_type == "Geo Model Points":
        if not geo_import_batch:
            frappe.throw(_("Geo Import Batch is required."))

        points = get_points_from_geo_model_points(
            geo_project=geo_project,
            geo_import_batch=geo_import_batch,
        )

    else:
        frappe.throw(_("Unsupported spatial source type: {0}").format(source_type))

    points = clean_points(points)

    if len(points) < 3:
        frappe.throw(
            _("At least 3 XY points are required to build an overlay polygon. Found {0}.").format(
                len(points)
            )
        )

    if outline_mode == "Convex Hull":
        points = convex_hull(points)

    points = close_polygon(points)

    return {
        "source_type": source_type,
        "geo_project": geo_project,
        "geo_import_batch": geo_import_batch,
        "pit_outline_batch": pit_outline_batch,
        "geo_pit_layout": geo_pit_layout,
        "outline_mode": outline_mode,
        "point_count": len(points),
        "points": points,
    }


def get_points_from_import_batch(geo_import_batch, geo_project=None):
    points = []

    for doctype in ["Pit Outline Points", "Geo Model Points", "Geo Calculated Points"]:
        if not doctype_exists(doctype):
            continue

        batch_field = first_existing_field(
            doctype,
            ["geo_import_batch", "import_batch", "source_import_batch", "source_batch", "batch"],
        )

        if not batch_field:
            continue

        filters = {
            batch_field: geo_import_batch,
        }

        project_field = first_existing_field(doctype, ["geo_project", "project"])

        if geo_project and project_field:
            filters[project_field] = geo_project

        points.extend(fetch_points_from_doctype(doctype, filters))

    return points


def get_points_from_pit_outline_points(geo_project=None, geo_import_batch=None):
    doctype = "Pit Outline Points"

    if not doctype_exists(doctype):
        frappe.throw(_("DocType Pit Outline Points was not found."))

    filters = {}

    project_field = first_existing_field(doctype, ["geo_project", "project"])
    if geo_project and project_field:
        filters[project_field] = geo_project

    batch_field = first_existing_field(
        doctype,
        ["geo_import_batch", "import_batch", "source_import_batch", "source_batch", "batch"],
    )

    if geo_import_batch and batch_field:
        filters[batch_field] = geo_import_batch

    return fetch_points_from_doctype(doctype, filters)


def get_points_from_geo_model_points(geo_project=None, geo_import_batch=None):
    doctype = "Geo Model Points"

    if not doctype_exists(doctype):
        frappe.throw(_("DocType Geo Model Points was not found."))

    filters = {}

    project_field = first_existing_field(doctype, ["geo_project", "project"])
    if geo_project and project_field:
        filters[project_field] = geo_project

    batch_field = first_existing_field(
        doctype,
        ["geo_import_batch", "import_batch", "source_import_batch", "source_batch", "batch"],
    )

    if geo_import_batch and batch_field:
        filters[batch_field] = geo_import_batch

    return fetch_points_from_doctype(doctype, filters)


def fetch_points_from_doctype(doctype, filters):
    x_field = first_existing_field(
        doctype,
        ["x", "x_coordinate", "coord_x", "easting", "east", "longitude"],
    )
    y_field = first_existing_field(
        doctype,
        ["y", "y_coordinate", "coord_y", "northing", "north", "latitude"],
    )
    z_field = first_existing_field(
        doctype,
        ["z", "z_coordinate", "coord_z", "elevation", "rl", "value"],
    )

    if not x_field or not y_field:
        return []

    fields = ["name", x_field, y_field]

    if z_field:
        fields.append(z_field)

    for optional_field in [
        "row_no",
        "idx",
        "variable_name",
        "variable_code",
        "full_name",
        "version_tag",
        "geo_import_batch",
        "import_batch",
        "geo_project",
        "geo_model_output",
    ]:
        if has_field(doctype, optional_field) and optional_field not in fields:
            fields.append(optional_field)

    order_by = get_point_order_by(doctype)

    rows = frappe.get_all(
        doctype,
        filters=filters,
        fields=fields,
        order_by=order_by,
        limit_page_length=0,
    )

    points = []

    for row in rows:
        points.append(
            {
                "name": row.get("name"),
                "x": flt_safe(row.get(x_field)),
                "y": flt_safe(row.get(y_field)),
                "z": flt_safe(row.get(z_field)) if z_field else None,
                "row_no": row.get("row_no"),
                "idx": row.get("idx"),
                "variable_name": row.get("variable_name"),
                "variable_code": row.get("variable_code"),
                "full_name": row.get("full_name"),
                "version_tag": row.get("version_tag"),
                "geo_import_batch": row.get("geo_import_batch") or row.get("import_batch"),
                "geo_project": row.get("geo_project"),
                "geo_model_output": row.get("geo_model_output"),
                "source_doctype": doctype,
            }
        )

    return points


def get_point_order_by(doctype):
    order_fields = []

    for fieldname in ["row_no", "idx", "sequence_no", "point_no", "name"]:
        if fieldname == "name" or has_field(doctype, fieldname):
            order_fields.append("{0} asc".format(fieldname))

    return ", ".join(order_fields) if order_fields else "name asc"


def first_existing_field(doctype, fieldnames):
    for fieldname in fieldnames:
        if has_field(doctype, fieldname):
            return fieldname

    return None


def doctype_exists(doctype):
    return bool(frappe.db.exists("DocType", doctype))


def has_field(doctype, fieldname):
    if fieldname == "name":
        return True

    meta = frappe.get_meta(doctype)
    return bool(meta.has_field(fieldname))


def clean_points(points):
    clean = []
    seen = set()

    for point in points or []:
        x = flt_safe(point.get("x"))
        y = flt_safe(point.get("y"))

        key = (round(x, 6), round(y, 6))

        if key in seen:
            continue

        seen.add(key)

        clean.append(
            {
                "x": x,
                "y": y,
                "z": point.get("z"),
                "name": point.get("name"),
                "row_no": point.get("row_no"),
                "idx": point.get("idx"),
                "variable_name": point.get("variable_name"),
                "variable_code": point.get("variable_code"),
                "full_name": point.get("full_name"),
                "version_tag": point.get("version_tag"),
                "geo_import_batch": point.get("geo_import_batch"),
                "geo_project": point.get("geo_project"),
                "geo_model_output": point.get("geo_model_output"),
                "source_doctype": point.get("source_doctype"),
            }
        )

    return clean


def close_polygon(points):
    if not points:
        return []

    first = points[0]
    last = points[-1]

    if round(first["x"], 6) == round(last["x"], 6) and round(first["y"], 6) == round(last["y"], 6):
        return points

    return points + [dict(first)]


def convex_hull(points):
    sorted_points = sorted(points, key=lambda p: (p["x"], p["y"]))

    if len(sorted_points) <= 1:
        return sorted_points

    def cross(o, a, b):
        return (a["x"] - o["x"]) * (b["y"] - o["y"]) - (a["y"] - o["y"]) * (b["x"] - o["x"])

    lower = []

    for point in sorted_points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()

        lower.append(point)

    upper = []

    for point in reversed(sorted_points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()

        upper.append(point)

    return lower[:-1] + upper[:-1]


def flt_safe(value):
    if value is None or value == "":
        return 0.0

    try:
        return float(value)
    except Exception:
        return 0.0