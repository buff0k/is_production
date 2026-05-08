import json
import frappe

try:
	from is_production.geo_planning.services.viewer_geometry_service import generate_preview_blocks
except Exception:
	generate_preview_blocks = None



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


def _is_enabled(value):
	return str(value or "").lower() in ["1", "true", "yes", "on"]


def _apply_z_filter(rows, z_filter_enabled=None, z_filter_mode=None, z_filter_value=None, z_filter_value_to=None):
	if not _is_enabled(z_filter_enabled):
		return rows

	mode = z_filter_mode or "Less Than"
	value = _float(z_filter_value, None)
	value_to = _float(z_filter_value_to, None)

	if value is None:
		return rows

	filtered = []

	for row in rows:
		z = row.get("z")

		if z is None:
			z = row.get("calculated_z")

		try:
			z = float(z)
		except Exception:
			continue

		keep = True

		if mode == "Less Than":
			keep = z < value
		elif mode == "Less Than Or Equal":
			keep = z <= value
		elif mode == "Greater Than":
			keep = z > value
		elif mode == "Greater Than Or Equal":
			keep = z >= value
		elif mode == "Equal":
			keep = z == value
		elif mode == "Between":
			if value_to is None:
				keep = True
			else:
				low = min(value, value_to)
				high = max(value, value_to)
				keep = low <= z <= high
		elif mode == "Outside":
			if value_to is None:
				keep = True
			else:
				low = min(value, value_to)
				high = max(value, value_to)
				keep = z < low or z > high

		if keep:
			filtered.append(row)

	return filtered


@frappe.whitelist()
def get_geo_points(
	geo_project=None,
	version_tag=None,
	variable_name=None,
	import_batch=None,
	geo_model_output=None,
	data_source=None,
	calculation_batch=None,
	z_filter_enabled=None,
	z_filter_mode=None,
	z_filter_value=None,
	z_filter_value_to=None
):
	data_source = data_source or "Geo Model"

	if data_source == "Geo Depth":
		return get_geo_depth_points(
			geo_project=geo_project,
			version_tag=version_tag,
			variable_name=variable_name,
			calculation_batch=calculation_batch,
			geo_model_output=geo_model_output,
			z_filter_enabled=z_filter_enabled,
			z_filter_mode=z_filter_mode,
			z_filter_value=z_filter_value,
			z_filter_value_to=z_filter_value_to,
		)

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

	rows = frappe.get_all(
		doctype,
		filters=filters,
		fields=fields,
		limit_page_length=0,
		order_by="row_no asc"
	)

	return _apply_z_filter(
		rows,
		z_filter_enabled=z_filter_enabled,
		z_filter_mode=z_filter_mode,
		z_filter_value=z_filter_value,
		z_filter_value_to=z_filter_value_to,
	)


@frappe.whitelist()
def get_geo_depth_points(
	geo_project=None,
	version_tag=None,
	variable_name=None,
	calculation_batch=None,
	geo_model_output=None,
	z_filter_enabled=None,
	z_filter_mode=None,
	z_filter_value=None,
	z_filter_value_to=None
):
	doctype = "Geo Calculated Points"

	if not _doctype_exists(doctype):
		return []

	raw_filters = {
		"geo_project": geo_project,
		"version_tag": version_tag,
		"geo_model_output": geo_model_output,
		"calculation_batch": calculation_batch,
	}

	filters = _clean_filters(doctype, raw_filters)

	fields = _safe_fields(
		doctype,
		[
			"x",
			"y",
			"z",
			"calculated_z",
			"reference_z",
			"target_z",
			"reference_variable_code",
			"reference_variable_name",
			"target_variable_code",
			"target_variable_name",
			"variable_code",
			"variable_name",
			"full_name",
			"version_tag",
			"geo_project",
			"geo_model_output",
			"calculation_batch",
			"row_no",
			"match_status",
			"calculation_type"
		]
	)

	or_filters = None

	if variable_name:
		or_filters = [
			["Geo Calculated Points", "variable_name", "like", f"%{variable_name}%"],
			["Geo Calculated Points", "variable_code", "like", f"%{variable_name}%"],
			["Geo Calculated Points", "full_name", "like", f"%{variable_name}%"],
		]

	rows = frappe.get_all(
		doctype,
		filters=filters,
		or_filters=or_filters,
		fields=fields,
		limit_page_length=0,
		order_by="row_no asc"
	)

	for row in rows:
		if row.get("calculated_z") is not None:
			row["z"] = row.get("calculated_z")

		row["import_batch"] = row.get("calculation_batch")
		row["geo_import_batch"] = row.get("calculation_batch")
		row["data_source"] = "Geo Depth"

	return _apply_z_filter(
		rows,
		z_filter_enabled=z_filter_enabled,
		z_filter_mode=z_filter_mode,
		z_filter_value=z_filter_value,
		z_filter_value_to=z_filter_value_to,
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
def get_geo_depth_batch_query(doctype, txt, searchfield, start, page_len, filters):
	if not _doctype_exists("Geo Calculation Batch"):
		return []

	geo_project = (filters or {}).get("geo_project")

	conditions = []
	values = {
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len,
	}

	if geo_project:
		conditions.append("gcb.geo_project = %(geo_project)s")
		values["geo_project"] = geo_project

	if txt:
		conditions.append(
			"(gcb.name LIKE %(txt)s OR gcb.batch_id LIKE %(txt)s OR "
			"gcb.calculation_name LIKE %(txt)s OR "
			"gcb.calculated_variable_code LIKE %(txt)s OR "
			"gcb.calculated_variable_name LIKE %(txt)s OR "
			"gcb.calculated_full_name LIKE %(txt)s)"
		)

	where_clause = " AND ".join(conditions)

	if where_clause:
		where_clause = "WHERE " + where_clause

	return frappe.db.sql(
		f"""
		SELECT DISTINCT
			gcb.name,
			COALESCE(
				gcb.calculated_full_name,
				gcb.calculated_variable_name,
				gcb.calculated_variable_code,
				gcb.calculation_name,
				gcb.batch_id,
				gcb.name
			)
		FROM `tabGeo Calculation Batch` gcb
		{where_clause}
		ORDER BY gcb.modified DESC
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
def generate_backend_preview_blocks(
	data_source=None,
	geo_project=None,
	version_tag=None,
	variable_name=None,
	import_batch=None,
	geo_model_output=None,
	calculation_batch=None,
	pit_outline_batch=None,
	z_filter_enabled=None,
	z_filter_mode=None,
	z_filter_value=None,
	z_filter_value_to=None,
	block_size_x=100,
	block_size_y=40,
	mesh_size_x=None,
	mesh_size_y=None,
	block_angle_degrees=0,
	minimum_inside_percent=50,
	auto_number_blocks=0,
	cut_no=1,
	points_json=None,
	pit_points_json=None
):
	"""
	Generate preview mining blocks using backend geometry.

	Important:
	- The browser should NOT send all geology points back to Python.
	- The browser sends filters only.
	- Python loads Geo Model Points / Geo Calculated Points / Pit Outline Points directly.
	- This avoids Frappe's 250 MB request limit.
	"""
	if generate_preview_blocks is None:
		frappe.throw(
			"viewer_geometry_service.py could not be imported. "
			"Please create is_production/geo_planning/services/viewer_geometry_service.py "
			"and restart the bench."
		)

	data_source = data_source or "Geo Model"

	# Backwards compatibility only. Avoid this for large models.
	if points_json:
		try:
			points = json.loads(points_json or "[]")
		except Exception:
			frappe.throw("Invalid points JSON.")
	else:
		points = get_geo_points(
			data_source=data_source,
			geo_project=geo_project,
			version_tag=version_tag,
			variable_name=variable_name,
			import_batch=import_batch,
			geo_model_output=geo_model_output,
			calculation_batch=calculation_batch,
			z_filter_enabled=z_filter_enabled,
			z_filter_mode=z_filter_mode,
			z_filter_value=z_filter_value,
			z_filter_value_to=z_filter_value_to,
		)

	if pit_points_json:
		try:
			pit_points = json.loads(pit_points_json or "[]")
		except Exception:
			frappe.throw("Invalid pit outline points JSON.")
	else:
		pit_points = []

		if pit_outline_batch:
			pit_points = get_pit_outline_points(
				geo_project=geo_project,
				geo_import_batch=pit_outline_batch,
			)

	if not points:
		frappe.throw("No model/depth points matched the selected filters.")

	blocks = generate_preview_blocks(
		points=points,
		pit_points=pit_points,
		block_size_x=_float(block_size_x, 100),
		block_size_y=_float(block_size_y, 40),
		mesh_size_x=_float(mesh_size_x, 0),
		mesh_size_y=_float(mesh_size_y, 0),
		angle_degrees=_float(block_angle_degrees, 0),
		minimum_inside_percent=_float(minimum_inside_percent, 50),
		auto_number_blocks=_int(auto_number_blocks, 0),
		cut_no=_int(cut_no, 1),
	)

	return blocks


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
	blocks_json=None,
	data_source=None,
	geo_depth_batch=None
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
	_set_if_field(layout, "data_source", data_source)
	_set_if_field(layout, "geo_depth_batch", geo_depth_batch)
	_set_if_field(layout, "calculation_batch", geo_depth_batch)

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
		_set_if_field(doc, "data_source", data_source)
		_set_if_field(doc, "geo_depth_batch", geo_depth_batch)
		_set_if_field(doc, "calculation_batch", geo_depth_batch)

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
		_set_if_field(doc, "area", _float(block.get("area")))
		_set_if_field(doc, "effective_area", _float(block.get("effective_area")))
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
			"data_source",
			"geo_depth_batch",
			"calculation_batch",
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
			"area",
			"effective_area",
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