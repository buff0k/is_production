import frappe


def _doctype_exists(doctype):
	return bool(frappe.db.exists("DocType", doctype))


def _doctype_has_field(doctype, fieldname):
	if not _doctype_exists(doctype):
		return False

	return fieldname in [df.fieldname for df in frappe.get_meta(doctype).fields]


def _safe_fields(doctype, requested_fields):
	return [
		fieldname
		for fieldname in requested_fields
		if fieldname == "name" or _doctype_has_field(doctype, fieldname)
	]


def _clean_filters(doctype, raw_filters):
	filters = {}

	for fieldname, value in raw_filters.items():
		if value not in [None, ""] and _doctype_has_field(doctype, fieldname):
			filters[fieldname] = value

	return filters


def _float(value, default=0):
	try:
		if value in [None, ""]:
			return default

		return float(value)
	except Exception:
		return default


def _get_batch_field(doctype):
	if _doctype_has_field(doctype, "geo_import_batch"):
		return "geo_import_batch"

	if _doctype_has_field(doctype, "import_batch"):
		return "import_batch"

	return None


def _normalise_point(row):
	row = dict(row)

	row["x"] = _float(row.get("x"), None)
	row["y"] = _float(row.get("y"), None)
	row["z"] = _float(row.get("z"), 0)

	return row


def _dedupe_xy(rows):
	seen = set()
	output = []

	for row in rows:
		point = _normalise_point(row)

		if point.get("x") is None or point.get("y") is None:
			continue

		key = (round(point["x"], 6), round(point["y"], 6))

		if key in seen:
			continue

		seen.add(key)
		output.append(point)

	return output


def _normalise_rows(rows):
	return [
		point
		for point in (_normalise_point(row) for row in rows)
		if point.get("x") is not None and point.get("y") is not None
	]


def _safe_order_by(doctype, preferred_fields=None):
	preferred_fields = preferred_fields or []
	parts = []

	for item in preferred_fields:
		fieldname = item.split()[0]

		if _doctype_has_field(doctype, fieldname):
			parts.append(item)

	if not parts:
		return "modified desc" if _doctype_has_field(doctype, "modified") else "name asc"

	return ", ".join(parts)


def _boundary_sort_key(row):
	def number_or_large(value):
		try:
			return float(value)
		except Exception:
			return 999999999

	return (
		number_or_large(row.get("source_point_no")),
		number_or_large(row.get("row_no")),
		number_or_large(row.get("source_line_no")),
		str(row.get("name") or ""),
	)


def _cross(o, a, b):
	return (a["x"] - o["x"]) * (b["y"] - o["y"]) - (a["y"] - o["y"]) * (b["x"] - o["x"])


def _convex_hull(rows):
	points = _dedupe_xy(rows)

	if len(points) <= 3:
		return points

	points = sorted(points, key=lambda p: (p["x"], p["y"]))

	lower = []

	for point in points:
		while len(lower) >= 2 and _cross(lower[-2], lower[-1], point) <= 0:
			lower.pop()

		lower.append(point)

	upper = []

	for point in reversed(points):
		while len(upper) >= 2 and _cross(upper[-2], upper[-1], point) <= 0:
			upper.pop()

		upper.append(point)

	return lower[:-1] + upper[:-1]


def _prepare_outline_points(rows, outline_mode=None):
	mode = (outline_mode or "Point Order").strip()

	if mode == "Convex Hull":
		return _convex_hull(rows)

	return sorted(_dedupe_xy(rows), key=_boundary_sort_key)


@frappe.whitelist()
def get_import_batch_points(
	geo_project=None,
	geo_import_batch=None,
):
	"""
	Light viewer read only.

	Reads existing Geo Model Points for one Geo Import Batch.
	This page does not create, update, generate or save records.
	"""
	doctype = "Geo Model Points"

	if not _doctype_exists(doctype):
		return []

	raw_filters = {
		"geo_project": geo_project,
	}

	batch_field = _get_batch_field(doctype)

	if geo_import_batch and batch_field:
		raw_filters[batch_field] = geo_import_batch

	filters = _clean_filters(doctype, raw_filters)

	fields = _safe_fields(
		doctype,
		[
			"name",
			"x",
			"y",
			"z",
			"variable_name",
			"variable_code",
			"full_name",
			"version_tag",
			"geo_project",
			"geo_model_output",
			"geo_import_batch",
			"import_batch",
			"row_no",
		],
	)

	rows = frappe.get_all(
		doctype,
		filters=filters,
		fields=fields,
		limit_page_length=0,
		order_by=_safe_order_by(doctype, ["y asc", "x asc", "row_no asc", "name asc"]),
	)

	return _normalise_rows(rows)


@frappe.whitelist()
def get_pit_outline_points(
	geo_project=None,
	geo_import_batch=None,
	outline_mode=None,
):
	"""
	Reads existing Pit Outline Points for a selected Geo Import Batch.

	Mode:
	- Point Order: ordered polygon using source point / row order.
	- Convex Hull: outside envelope for unordered points.
	"""
	doctype = "Pit Outline Points"

	if not _doctype_exists(doctype):
		return []

	raw_filters = {
		"geo_project": geo_project,
	}

	batch_field = _get_batch_field(doctype)

	if geo_import_batch and batch_field:
		raw_filters[batch_field] = geo_import_batch

	filters = _clean_filters(doctype, raw_filters)

	fields = _safe_fields(
		doctype,
		[
			"name",
			"x",
			"y",
			"z",
			"variable_name",
			"variable_code",
			"full_name",
			"version_tag",
			"geo_project",
			"geo_model_output",
			"geo_import_batch",
			"import_batch",
			"row_no",
			"source_point_no",
			"source_line_no",
			"source_x",
			"source_y",
			"latitude",
			"longitude",
			"boundary_type",
			"boundary_format",
			"coordinate_transform",
		],
	)

	rows = frappe.get_all(
		doctype,
		filters=filters,
		fields=fields,
		limit_page_length=0,
		order_by=_safe_order_by(doctype, ["row_no asc", "source_point_no asc", "source_line_no asc", "name asc"]),
	)

	return _prepare_outline_points(rows, outline_mode=outline_mode)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_geo_import_batch_query(doctype, txt, searchfield, start, page_len, filters):
	geo_project = (filters or {}).get("geo_project")

	conditions = []
	values = {
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len,
	}

	if geo_project and _doctype_has_field("Geo Import Batch", "geo_project"):
		conditions.append("gib.geo_project = %(geo_project)s")
		values["geo_project"] = geo_project

	if txt:
		conditions.append(
			"(gib.name LIKE %(txt)s OR "
			"gib.batch_id LIKE %(txt)s OR "
			"gib.variable_code LIKE %(txt)s OR "
			"gib.variable_name LIKE %(txt)s OR "
			"gib.full_name LIKE %(txt)s)"
		)

	where_clause = " AND ".join(conditions)

	if where_clause:
		where_clause = "WHERE " + where_clause

	return frappe.db.sql(
		f"""
		SELECT
			gib.name,
			COALESCE(
				gib.full_name,
				gib.variable_name,
				gib.variable_code,
				gib.batch_id,
				gib.name
			)
		FROM `tabGeo Import Batch` gib
		{where_clause}
		ORDER BY gib.modified DESC
		LIMIT %(start)s, %(page_len)s
		""",
		values,
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_pit_outline_batch_query(doctype, txt, searchfield, start, page_len, filters):
	"""
	Only show Geo Import Batches that already have Pit Outline Points.
	"""
	if not _doctype_exists("Pit Outline Points"):
		return []

	geo_project = (filters or {}).get("geo_project")

	batch_field = _get_batch_field("Pit Outline Points")

	if not batch_field:
		return []

	conditions = []
	values = {
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len,
	}

	if geo_project and _doctype_has_field("Pit Outline Points", "geo_project"):
		conditions.append("pop.geo_project = %(geo_project)s")
		values["geo_project"] = geo_project

	if txt:
		conditions.append(
			"(gib.name LIKE %(txt)s OR "
			"gib.batch_id LIKE %(txt)s OR "
			"gib.variable_code LIKE %(txt)s OR "
			"gib.variable_name LIKE %(txt)s OR "
			"gib.full_name LIKE %(txt)s)"
		)

	where_clause = " AND ".join(conditions)

	if where_clause:
		where_clause = "WHERE " + where_clause

	return frappe.db.sql(
		f"""
		SELECT DISTINCT
			gib.name,
			COALESCE(
				gib.full_name,
				gib.variable_name,
				gib.variable_code,
				gib.batch_id,
				gib.name
			)
		FROM `tabPit Outline Points` pop
		INNER JOIN `tabGeo Import Batch` gib
			ON gib.name = pop.{batch_field}
		{where_clause}
		ORDER BY gib.modified DESC
		LIMIT %(start)s, %(page_len)s
		""",
		values,
	)