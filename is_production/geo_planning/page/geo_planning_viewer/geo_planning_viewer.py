import json
import frappe


def _doctype_has_field(doctype, fieldname):
	return fieldname in [df.fieldname for df in frappe.get_meta(doctype).fields]


def _doctype_exists(doctype):
	return frappe.db.exists("DocType", doctype)


def _clean_filters(doctype, raw_filters):
	filters = {}

	for fieldname, value in raw_filters.items():
		if value and _doctype_has_field(doctype, fieldname):
			filters[fieldname] = value

	return filters


def _safe_fields(doctype, requested_fields):
	return [
		fieldname
		for fieldname in requested_fields
		if fieldname == "name" or _doctype_has_field(doctype, fieldname)
	]


def _set_if_field(doc, fieldname, value):
	if _doctype_has_field(doc.doctype, fieldname):
		doc.set(fieldname, value)


def _float(value, default=0):
	try:
		return float(value or default)
	except Exception:
		return default


def _int(value, default=0):
	try:
		return int(float(value or default))
	except Exception:
		return default


@frappe.whitelist()
def get_geo_points(
	geo_project=None,
	version_tag=None,
	variable_name=None,
	import_batch=None,
	geo_model_output=None
):
	doctype = "Geo Model Points"

	raw_filters = {
		"geo_project": geo_project,
		"version_tag": version_tag,
		"variable_name": variable_name,
		"geo_model_output": geo_model_output,
	}

	if import_batch:
		if _doctype_has_field(doctype, "import_batch"):
			raw_filters["import_batch"] = import_batch
		elif _doctype_has_field(doctype, "geo_import_batch"):
			raw_filters["geo_import_batch"] = import_batch

	filters = _clean_filters(doctype, raw_filters)

	fields = _safe_fields(
		doctype,
		[
			"x",
			"y",
			"z",
			"variable_name",
			"version_tag",
			"geo_project",
			"geo_model_output",
			"import_batch",
			"geo_import_batch",
			"variable_code",
			"full_name",
			"row_no"
		]
	)

	return frappe.get_all(
		doctype,
		filters=filters,
		fields=fields,
		limit_page_length=0,
		order_by="row_no asc"
	)


@frappe.whitelist()
def get_pit_outline_points(
	geo_project=None,
	version_tag=None,
	geo_import_batch=None,
	geo_model_output=None,
	variable_name=None
):
	doctype = "Pit Outline Points"

	raw_filters = {
		"geo_project": geo_project,
		"version_tag": version_tag,
		"geo_model_output": geo_model_output,
		"variable_name": variable_name,
	}

	if geo_import_batch:
		if _doctype_has_field(doctype, "geo_import_batch"):
			raw_filters["geo_import_batch"] = geo_import_batch
		elif _doctype_has_field(doctype, "import_batch"):
			raw_filters["import_batch"] = geo_import_batch

	filters = _clean_filters(doctype, raw_filters)

	fields = _safe_fields(
		doctype,
		[
			"x",
			"y",
			"z",
			"variable_name",
			"version_tag",
			"geo_project",
			"geo_model_output",
			"geo_import_batch",
			"import_batch",
			"variable_code",
			"full_name",
			"row_no"
		]
	)

	return frappe.get_all(
		doctype,
		filters=filters,
		fields=fields,
		limit_page_length=0,
		order_by="row_no asc"
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_model_batch_query(doctype, txt, searchfield, start, page_len, filters):
	geo_project = (filters or {}).get("geo_project")

	conditions = []
	values = {
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len,
	}

	if geo_project:
		conditions.append("gmp.geo_project = %(geo_project)s")
		values["geo_project"] = geo_project

	if txt:
		conditions.append(
			"(gib.name LIKE %(txt)s OR gib.batch_id LIKE %(txt)s OR "
			"gib.variable_name LIKE %(txt)s OR gib.full_name LIKE %(txt)s)"
		)

	where_clause = " AND ".join(conditions)

	if where_clause:
		where_clause = "WHERE " + where_clause

	batch_field = "gmp.import_batch" if _doctype_has_field("Geo Model Points", "import_batch") else "gmp.geo_import_batch"

	return frappe.db.sql(
		f"""
		SELECT DISTINCT
			gib.name,
			COALESCE(gib.full_name, gib.variable_name, gib.variable_code, gib.batch_id, gib.name)
		FROM `tabGeo Model Points` gmp
		INNER JOIN `tabGeo Import Batch` gib
			ON gib.name = {batch_field}
		{where_clause}
		ORDER BY gib.modified DESC
		LIMIT %(start)s, %(page_len)s
		""",
		values,
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_pit_outline_batch_query(doctype, txt, searchfield, start, page_len, filters):
	geo_project = (filters or {}).get("geo_project")

	conditions = []
	values = {
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len,
	}

	if geo_project:
		conditions.append("pop.geo_project = %(geo_project)s")
		values["geo_project"] = geo_project

	if txt:
		conditions.append(
			"(gib.name LIKE %(txt)s OR gib.batch_id LIKE %(txt)s OR "
			"gib.variable_name LIKE %(txt)s OR gib.full_name LIKE %(txt)s)"
		)

	where_clause = " AND ".join(conditions)

	if where_clause:
		where_clause = "WHERE " + where_clause

	batch_field = "pop.geo_import_batch" if _doctype_has_field("Pit Outline Points", "geo_import_batch") else "pop.import_batch"

	return frappe.db.sql(
		f"""
		SELECT DISTINCT
			gib.name,
			COALESCE(gib.full_name, gib.variable_name, gib.variable_code, gib.batch_id, gib.name)
		FROM `tabPit Outline Points` pop
		INNER JOIN `tabGeo Import Batch` gib
			ON gib.name = {batch_field}
		{where_clause}
		ORDER BY gib.modified DESC
		LIMIT %(start)s, %(page_len)s
		""",
		values,
	)


@frappe.whitelist()
def save_mining_block_layout(
	layout_name=None,
	geo_project=None,
	geo_model_output=None,
	model_batch=None,
	pit_outline_batch=None,
	block_size_x=None,
	block_size_y=None,
	mesh_size_x=None,
	mesh_size_y=None,
	block_angle_degrees=None,
	minimum_inside_percent=None,
	blocks_json=None
):
	if not _doctype_exists("Geo Mining Block Layout") or not _doctype_exists("Geo Mining Block"):
		frappe.throw(
			"To save block layouts, please create DocTypes: "
			"<b>Geo Mining Block Layout</b> and <b>Geo Mining Block</b>."
		)

	if not layout_name:
		frappe.throw("Layout Name is required.")

	if not geo_project:
		frappe.throw("Geo Project is required.")

	try:
		blocks = json.loads(blocks_json or "[]")
	except Exception:
		frappe.throw("Invalid blocks JSON.")

	if not blocks:
		frappe.throw("No mining blocks were supplied.")

	layout = frappe.new_doc("Geo Mining Block Layout")

	_set_if_field(layout, "layout_name", layout_name)
	_set_if_field(layout, "geo_project", geo_project)
	_set_if_field(layout, "geo_model_output", geo_model_output)
	_set_if_field(layout, "model_batch", model_batch)
	_set_if_field(layout, "pit_outline_batch", pit_outline_batch)
	_set_if_field(layout, "block_size_x", _float(block_size_x))
	_set_if_field(layout, "block_size_y", _float(block_size_y))
	_set_if_field(layout, "mesh_size_x", _float(mesh_size_x))
	_set_if_field(layout, "mesh_size_y", _float(mesh_size_y))
	_set_if_field(layout, "block_angle_degrees", _float(block_angle_degrees))
	_set_if_field(layout, "minimum_inside_percent", _float(minimum_inside_percent))
	_set_if_field(layout, "status", "Draft")

	layout.insert(ignore_permissions=True)

	created = 0

	for block in blocks:
		doc = frappe.new_doc("Geo Mining Block")

		_set_if_field(doc, "layout", layout.name)
		_set_if_field(doc, "geo_project", geo_project)
		_set_if_field(doc, "geo_model_output", geo_model_output)
		_set_if_field(doc, "model_batch", model_batch)
		_set_if_field(doc, "pit_outline_batch", pit_outline_batch)

		_set_if_field(doc, "cut_no", _int(block.get("cut_no")))
		_set_if_field(doc, "block_no", _int(block.get("block_no")))
		_set_if_field(doc, "label", block.get("label") or "")
		_set_if_field(doc, "col", _int(block.get("col")))
		_set_if_field(doc, "row", _int(block.get("row")))
		_set_if_field(doc, "x", _float(block.get("x")))
		_set_if_field(doc, "y", _float(block.get("y")))
		_set_if_field(doc, "width", _float(block.get("width")))
		_set_if_field(doc, "height", _float(block.get("height")))
		_set_if_field(doc, "angle_degrees", _float(block.get("angle_degrees")))
		_set_if_field(doc, "avg_z", _float(block.get("avg_z")))
		_set_if_field(doc, "min_z", _float(block.get("min_z")))
		_set_if_field(doc, "max_z", _float(block.get("max_z")))
		_set_if_field(doc, "point_count", _int(block.get("point_count")))
		_set_if_field(doc, "expected_point_count", _int(block.get("expected_point_count")))
		_set_if_field(doc, "inside_percent", _float(block.get("inside_percent")))
		_set_if_field(doc, "status", block.get("status") or "Draft")
		_set_if_field(doc, "corners_json", json.dumps(block.get("corners") or []))

		doc.insert(ignore_permissions=True)
		created += 1

	frappe.db.commit()

	return {
		"layout": layout.name,
		"blocks_created": created
	}


@frappe.whitelist()
def get_mining_block_layouts(geo_project=None):
	if not _doctype_exists("Geo Mining Block Layout"):
		return []

	filters = {}

	if geo_project and _doctype_has_field("Geo Mining Block Layout", "geo_project"):
		filters["geo_project"] = geo_project

	fields = _safe_fields(
		"Geo Mining Block Layout",
		[
			"name",
			"layout_name",
			"geo_project",
			"geo_model_output",
			"model_batch",
			"pit_outline_batch",
			"block_size_x",
			"block_size_y",
			"mesh_size_x",
			"mesh_size_y",
			"block_angle_degrees",
			"minimum_inside_percent",
			"status"
		]
	)

	return frappe.get_all(
		"Geo Mining Block Layout",
		filters=filters,
		fields=fields,
		order_by="modified desc",
		limit_page_length=100
	)


@frappe.whitelist()
def get_mining_blocks(layout):
	if not _doctype_exists("Geo Mining Block"):
		return []

	filters = {}

	if _doctype_has_field("Geo Mining Block", "layout"):
		filters["layout"] = layout

	fields = _safe_fields(
		"Geo Mining Block",
		[
			"name",
			"layout",
			"cut_no",
			"block_no",
			"label",
			"col",
			"row",
			"x",
			"y",
			"width",
			"height",
			"angle_degrees",
			"avg_z",
			"min_z",
			"max_z",
			"point_count",
			"expected_point_count",
			"inside_percent",
			"status",
			"corners_json"
		]
	)

	return frappe.get_all(
		"Geo Mining Block",
		filters=filters,
		fields=fields,
		order_by="row asc, col asc, block_no asc",
		limit_page_length=0
	)