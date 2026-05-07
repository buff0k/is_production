import json
import frappe


def _doctype_has_field(doctype, fieldname):
	return fieldname in [df.fieldname for df in frappe.get_meta(doctype).fields]


def _doctype_exists(doctype):
	return frappe.db.exists("DocType", doctype)


def _safe_fields(doctype, requested_fields):
	return [
		fieldname
		for fieldname in requested_fields
		if fieldname == "name" or _doctype_has_field(doctype, fieldname)
	]


def _get_batch_field(doctype="Geo Model Points"):
	if _doctype_has_field(doctype, "import_batch"):
		return "import_batch"

	if _doctype_has_field(doctype, "geo_import_batch"):
		return "geo_import_batch"

	return None


def _parse_batches(model_batches):
	if not model_batches:
		return []

	if isinstance(model_batches, list):
		items = model_batches
	else:
		try:
			items = json.loads(model_batches)
		except Exception:
			items = [x.strip() for x in str(model_batches).split(",") if x.strip()]

	clean = []

	for item in items:
		if isinstance(item, str):
			value = item
		elif isinstance(item, dict):
			value = item.get("value") or item.get("name") or item.get("label")
		else:
			value = str(item or "")

		value = str(value or "").strip()

		if value and value not in clean:
			clean.append(value)

	return clean


@frappe.whitelist()
def get_model_batch_options(txt=None, geo_project=None, page_len=50):
	"""
	Options for the MultiSelectList field.

	Returns batches that actually have Geo Model Points, optionally filtered by project.
	"""
	if not _doctype_exists("Geo Model Points") or not _doctype_exists("Geo Import Batch"):
		return []

	batch_field = _get_batch_field("Geo Model Points")

	if not batch_field:
		return []

	conditions = []
	values = {
		"txt": f"%{txt or ''}%",
		"page_len": int(page_len or 50),
	}

	if geo_project and _doctype_has_field("Geo Model Points", "geo_project"):
		conditions.append("gmp.geo_project = %(geo_project)s")
		values["geo_project"] = geo_project

	if txt:
		conditions.append(
			"(gib.name LIKE %(txt)s OR gib.batch_id LIKE %(txt)s OR "
			"gib.variable_name LIKE %(txt)s OR gib.full_name LIKE %(txt)s OR "
			"gib.variable_code LIKE %(txt)s)"
		)

	where_clause = " AND ".join(conditions)

	if where_clause:
		where_clause = "WHERE " + where_clause

	rows = frappe.db.sql(
		f"""
		SELECT DISTINCT
			gib.name AS value,
			COALESCE(gib.full_name, gib.variable_name, gib.variable_code, gib.batch_id, gib.name) AS description
		FROM `tabGeo Model Points` gmp
		INNER JOIN `tabGeo Import Batch` gib
			ON gib.name = gmp.{batch_field}
		{where_clause}
		ORDER BY gib.modified DESC
		LIMIT %(page_len)s
		""",
		values,
		as_dict=True,
	)

	return rows


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_model_batch_query(doctype, txt, searchfield, start, page_len, filters):
	"""
	Optional Link query helper if you later switch to a Link/Table MultiSelect approach.
	"""
	rows = get_model_batch_options(
		txt=txt,
		geo_project=(filters or {}).get("geo_project"),
		page_len=page_len,
	)

	return [(row.get("value"), row.get("description")) for row in rows]


@frappe.whitelist()
def get_multi_batch_surfaces(
	geo_project=None,
	geo_model_output=None,
	version_tag=None,
	model_batches=None
):
	"""
	Load X/Y/Z points for multiple selected model/import batches.

	Each selected batch is returned as one 3D surface:
	[
		{
			"batch": "...",
			"label": "...",
			"points": [{"x": 1, "y": 2, "z": 3}, ...],
			"stats": {...}
		}
	]
	"""
	doctype = "Geo Model Points"

	if not _doctype_exists(doctype):
		return []

	batches = _parse_batches(model_batches)

	if not batches:
		return []

	batch_field = _get_batch_field(doctype)

	if not batch_field:
		frappe.throw("Geo Model Points must have either import_batch or geo_import_batch field.")

	fields = _safe_fields(
		doctype,
		[
			"x",
			"y",
			"z",
			"variable_name",
			"variable_code",
			"full_name",
			"version_tag",
			"geo_project",
			"geo_model_output",
			"import_batch",
			"geo_import_batch",
			"row_no"
		]
	)

	surfaces = []

	for batch in batches:
		filters = {
			batch_field: batch
		}

		if geo_project and _doctype_has_field(doctype, "geo_project"):
			filters["geo_project"] = geo_project

		if geo_model_output and _doctype_has_field(doctype, "geo_model_output"):
			filters["geo_model_output"] = geo_model_output

		if version_tag and _doctype_has_field(doctype, "version_tag"):
			filters["version_tag"] = version_tag

		rows = frappe.get_all(
			doctype,
			filters=filters,
			fields=fields,
			order_by="row_no asc",
			limit_page_length=0
		)

		points = []

		for row in rows:
			try:
				x = float(row.get("x"))
				y = float(row.get("y"))
				z = float(row.get("z"))
			except Exception:
				continue

			points.append({
				"x": x,
				"y": y,
				"z": z,
			})

		label = batch

		if rows:
			first = rows[0]
			label = (
				first.get("full_name")
				or first.get("variable_name")
				or first.get("variable_code")
				or batch
			)

		stats = _get_point_stats(points)

		surfaces.append({
			"batch": batch,
			"label": label,
			"points": points,
			"stats": stats
		})

	return surfaces


def _get_point_stats(points):
	if not points:
		return {
			"count": 0,
			"min_x": None,
			"max_x": None,
			"min_y": None,
			"max_y": None,
			"min_z": None,
			"max_z": None,
		}

	xs = [p["x"] for p in points]
	ys = [p["y"] for p in points]
	zs = [p["z"] for p in points]

	return {
		"count": len(points),
		"min_x": min(xs),
		"max_x": max(xs),
		"min_y": min(ys),
		"max_y": max(ys),
		"min_z": min(zs),
		"max_z": max(zs),
	}
