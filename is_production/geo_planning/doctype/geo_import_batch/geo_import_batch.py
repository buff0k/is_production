import os
import re
import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import now


class GeoImportBatch(Document):
	def validate(self):
		self.set_full_name()

	def set_full_name(self):
		code = (self.variable_code or "").strip()
		name = (self.variable_name or "").strip()

		if code and name:
			self.full_name = f"{code} - {name}"
		elif code:
			self.full_name = code
		else:
			self.full_name = ""


@frappe.whitelist()
def detect_geo_model_variables_from_file(file_url):
	if not file_url:
		frappe.throw("Please attach a raw file first.")

	file_path = _get_file_path(file_url)

	if not os.path.exists(file_path):
		frappe.throw(f"Attached file not found on server: {file_path}")

	variables = _detect_variables_from_header(file_path)

	return [{"code": v} for v in variables]


@frappe.whitelist()
def detect_geo_model_variables(docname):
	batch = frappe.get_doc("Geo Import Batch", docname)

	if not batch.raw_file_attachment:
		frappe.throw("Please attach a raw file first.")

	return detect_geo_model_variables_from_file(batch.raw_file_attachment)


@frappe.whitelist()
def enqueue_create_geo_model_points(docname, replace_existing=1):
	job = frappe.enqueue(
		"is_production.geo_planning.doctype.geo_import_batch.geo_import_batch.create_geo_model_points_background",
		queue="long",
		timeout=7200,
		docname=docname,
		replace_existing=int(replace_existing),
		user=frappe.session.user,
		job_name=f"Create Geo Model Points - {docname}",
	)

	frappe.db.set_value(
		"Geo Import Batch",
		docname,
		{
			"processing_status": "Validated",
			"import_log": f"Background Geo Model Points import started at {now()}.\nJob ID: {job.id}",
		},
		update_modified=False,
	)
	frappe.db.commit()

	return {"job_id": job.id}


@frappe.whitelist()
def enqueue_create_pit_outline_points(docname, replace_existing=1):
	job = frappe.enqueue(
		"is_production.geo_planning.doctype.geo_import_batch.geo_import_batch.create_pit_outline_points_background",
		queue="long",
		timeout=7200,
		docname=docname,
		replace_existing=int(replace_existing),
		user=frappe.session.user,
		job_name=f"Create Pit Outline Points - {docname}",
	)

	frappe.db.set_value(
		"Geo Import Batch",
		docname,
		{
			"processing_status": "Validated",
			"import_log": f"Background Pit Outline Points import started at {now()}.\nJob ID: {job.id}",
		},
		update_modified=False,
	)
	frappe.db.commit()

	return {"job_id": job.id}


def _set_batch_status(docname, values):
	frappe.db.set_value(
		"Geo Import Batch",
		docname,
		values,
		update_modified=False,
	)
	frappe.db.commit()


def _get_file_path(file_url):
	if not file_url:
		frappe.throw("Raw File Attachment is required.")

	if file_url.startswith("/private/files/"):
		return frappe.get_site_path("private", "files", file_url.replace("/private/files/", ""))

	if file_url.startswith("/files/"):
		return frappe.get_site_path("public", "files", file_url.replace("/files/", ""))

	frappe.throw(f"Unsupported file path: {file_url}")


def _get_file_hash(file_path):
	hash_md5 = hashlib.md5()

	with open(file_path, "rb") as f:
		for chunk in iter(lambda: f.read(8192), b""):
			hash_md5.update(chunk)

	return hash_md5.hexdigest()


def _is_number(value):
	try:
		float(str(value).replace(",", "").strip())
		return True
	except Exception:
		return False


def _to_float(value):
	return float(str(value).replace(",", "").strip())


def _normalise_code(value):
	return str(value or "").strip().upper()


def _split_line(line):
	clean = line.strip()

	if "," in clean:
		return [p.strip() for p in clean.split(",")]

	if "\t" in clean:
		return [p.strip() for p in clean.split("\t")]

	if ";" in clean and not clean.startswith(";"):
		return [p.strip() for p in clean.split(";")]

	return re.split(r"\s+", clean)


def _is_metadata_header_key(key):
	return str(key).lower().strip() in {
		"origin",
		"extent",
		"mesh",
		"rotation",
	}


def _is_system_column_key(key):
	return str(key).lower().strip() in {
		"x",
		"y",
		"z",
		"value",
	}


def _read_grid_metadata(file_path):
	metadata = {}

	with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
		for line in f:
			clean = line.strip()

			if not clean:
				continue

			if not clean.startswith(";"):
				break

			header = clean.replace(";", "", 1).strip()
			parts = header.split()

			if not parts:
				continue

			key = parts[0].lower()

			if key in {"origin", "extent", "mesh"} and len(parts) >= 3:
				metadata[key] = {
					"x": parts[1],
					"y": parts[2],
				}

			elif key == "rotation" and len(parts) >= 2:
				metadata[key] = " ".join(parts[1:])

	return metadata


def _read_header_fields(file_path):
	fields = []

	with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
		for line in f:
			clean = line.strip()

			if not clean:
				continue

			if not clean.startswith(";"):
				break

			header = clean.replace(";", "", 1).strip()
			parts = header.split()

			if len(parts) < 3:
				continue

			code = parts[0].strip()

			if _is_metadata_header_key(code):
				continue

			if not (_is_number(parts[1]) and _is_number(parts[2])):
				continue

			start = int(float(parts[1]))
			width = int(float(parts[2]))

			if start <= 0 or width <= 0:
				continue

			fields.append({
				"code": code,
				"code_normalised": _normalise_code(code),
				"start": start,
				"width": width,
			})

	return fields


def _detect_variables_from_header(file_path):
	fields = _read_header_fields(file_path)
	variables = []

	for field in fields:
		code = field["code"]

		if not _is_system_column_key(code):
			variables.append(code)

	return variables


def _get_selected_field(fields, selected_variable_code):
	selected_norm = _normalise_code(selected_variable_code)

	for field in fields:
		if field["code_normalised"] == selected_norm:
			return field

	return None


def _get_field_by_code(fields, code):
	code_norm = _normalise_code(code)

	for field in fields:
		if field["code_normalised"] == code_norm:
			return field

	return None


def _read_fixed_width_value(line, field):
	start_index = field["start"] - 1
	end_index = start_index + field["width"]

	if len(line) < start_index:
		return ""

	return line[start_index:end_index].strip()


def _parse_selected_variable_file(file_path, selected_variable_code):
	selected_variable_code = (selected_variable_code or "").strip()

	if not selected_variable_code:
		frappe.throw("Please select a Variable Code before importing.")

	fields = _read_header_fields(file_path)

	if not fields:
		return _parse_simple_xyz_file(file_path, selected_variable_code)

	x_field = _get_field_by_code(fields, "x")
	y_field = _get_field_by_code(fields, "y")
	selected_field = _get_selected_field(fields, selected_variable_code)

	if not x_field or not y_field:
		return _parse_simple_xyz_file(file_path, selected_variable_code)

	if not selected_field:
		available = ", ".join([f["code"] for f in fields if not _is_system_column_key(f["code"])])
		frappe.throw(
			f"Variable Code '{selected_variable_code}' was not found in the file header.<br>"
			f"Available variables: {available}"
		)

	points = _parse_fixed_width_points(
		file_path=file_path,
		x_field=x_field,
		y_field=y_field,
		selected_field=selected_field,
	)

	if points:
		return points

	return _parse_split_points_from_header(
		file_path=file_path,
		fields=fields,
		selected_variable_code=selected_field["code"],
	)


def _parse_fixed_width_points(file_path, x_field, y_field, selected_field):
	points = []

	with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
		for physical_line_no, line in enumerate(f, start=1):
			clean = line.strip()

			if not clean or clean.startswith(";"):
				continue

			try:
				x_raw = _read_fixed_width_value(line, x_field)
				y_raw = _read_fixed_width_value(line, y_field)
				z_raw = _read_fixed_width_value(line, selected_field)

				if not z_raw:
					continue

				if not (_is_number(x_raw) and _is_number(y_raw) and _is_number(z_raw)):
					continue

				points.append({
					"source_line_no": physical_line_no,
					"x": _to_float(x_raw),
					"y": _to_float(y_raw),
					"z": _to_float(z_raw),
					"variable_code": selected_field["code"],
				})

			except Exception:
				continue

	return points


def _parse_split_points_from_header(file_path, fields, selected_variable_code):
	field_codes = [f["code"] for f in fields]
	lower_codes = [c.lower() for c in field_codes]

	if "x" not in lower_codes or "y" not in lower_codes:
		return []

	selected_field = _get_selected_field(fields, selected_variable_code)

	if not selected_field:
		return []

	x_index = lower_codes.index("x")
	y_index = lower_codes.index("y")
	value_index = field_codes.index(selected_field["code"])

	points = []

	with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
		for physical_line_no, line in enumerate(f, start=1):
			clean = line.strip()

			if not clean or clean.startswith(";"):
				continue

			parts = _split_line(clean)

			if len(parts) <= max(x_index, y_index, value_index):
				continue

			try:
				x_raw = parts[x_index]
				y_raw = parts[y_index]
				z_raw = parts[value_index]

				if not (_is_number(x_raw) and _is_number(y_raw) and _is_number(z_raw)):
					continue

				points.append({
					"source_line_no": physical_line_no,
					"x": _to_float(x_raw),
					"y": _to_float(y_raw),
					"z": _to_float(z_raw),
					"variable_code": selected_field["code"],
				})

			except Exception:
				continue

	return points


def _parse_simple_xyz_file(file_path, selected_variable_code):
	points = []

	with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
		for physical_line_no, line in enumerate(f, start=1):
			clean = line.strip()

			if not clean or clean.startswith(";"):
				continue

			parts = _split_line(clean)
			numeric_parts = [p for p in parts if _is_number(p)]

			if len(numeric_parts) < 3:
				continue

			try:
				points.append({
					"source_line_no": physical_line_no,
					"x": _to_float(numeric_parts[0]),
					"y": _to_float(numeric_parts[1]),
					"z": _to_float(numeric_parts[2]),
					"variable_code": selected_variable_code,
				})
			except Exception:
				continue

	return points


def _get_geo_model_output(batch):
	model_output_meta = frappe.get_meta("Geo Model Output")
	fieldnames = [df.fieldname for df in model_output_meta.fields]

	for batch_field in ["geo_import_batch", "import_batch", "geo_batch"]:
		if batch_field in fieldnames:
			outputs = frappe.get_all(
				"Geo Model Output",
				filters={batch_field: batch.name},
				fields=["name"],
				limit=1,
			)

			if outputs:
				return outputs[0].name

	frappe.throw(
		"No Geo Model Output record found for this Geo Import Batch. "
		"Create the Geo Model Output first, then press Geo Model Points or Pit Outline."
	)


def _doctype_has_field(doctype, fieldname):
	return fieldname in [df.fieldname for df in frappe.get_meta(doctype).fields]


def _publish_complete(
	user,
	event_name,
	batch_name,
	status,
	row_count=0,
	success_count=0,
	error_count=0,
	variable_code=None,
	full_name=None,
):
	if not user:
		return

	frappe.publish_realtime(
		event_name,
		{
			"status": status,
			"batch": batch_name,
			"row_count": row_count,
			"success_count": success_count,
			"error_count": error_count,
			"variable_code": variable_code,
			"full_name": full_name,
		},
		user=user,
	)


def create_geo_model_points_background(docname, replace_existing=1, user=None):
	try:
		result = _create_geo_points_for_target(
			docname=docname,
			replace_existing=replace_existing,
			target_doctype="Geo Model Points",
			target_label="Geo Model Points",
			batch_fieldname="import_batch",
			remarks_fieldname="remarks",
		)

		_publish_complete(
			user=user,
			event_name="geo_model_points_import_complete",
			batch_name=docname,
			status="success",
			row_count=result["row_count"],
			success_count=result["success_count"],
			error_count=result["error_count"],
			variable_code=result["variable_code"],
			full_name=result["full_name"],
		)

		return result

	except Exception:
		error_message = frappe.get_traceback()

		_set_batch_status(
			docname,
			{
				"processing_status": "Error",
				"error_count": 1,
				"import_log": f"Background Geo Model Points import failed at {now()}.\n\n{error_message}",
			},
		)

		_publish_complete(
			user=user,
			event_name="geo_model_points_import_complete",
			batch_name=docname,
			status="error",
			row_count=0,
			success_count=0,
			error_count=1,
		)

		raise


def create_pit_outline_points_background(docname, replace_existing=1, user=None):
	try:
		result = _create_geo_points_for_target(
			docname=docname,
			replace_existing=replace_existing,
			target_doctype="Pit Outline Points",
			target_label="Pit Outline Points",
			batch_fieldname="geo_import_batch",
			remarks_fieldname="remarks_comments",
		)

		_publish_complete(
			user=user,
			event_name="pit_outline_points_import_complete",
			batch_name=docname,
			status="success",
			row_count=result["row_count"],
			success_count=result["success_count"],
			error_count=result["error_count"],
			variable_code=result["variable_code"],
			full_name=result["full_name"],
		)

		return result

	except Exception:
		error_message = frappe.get_traceback()

		_set_batch_status(
			docname,
			{
				"processing_status": "Error",
				"error_count": 1,
				"import_log": f"Background Pit Outline Points import failed at {now()}.\n\n{error_message}",
			},
		)

		_publish_complete(
			user=user,
			event_name="pit_outline_points_import_complete",
			batch_name=docname,
			status="error",
			row_count=0,
			success_count=0,
			error_count=1,
		)

		raise


@frappe.whitelist()
def create_geo_model_points(docname, replace_existing=1):
	return _create_geo_points_for_target(
		docname=docname,
		replace_existing=replace_existing,
		target_doctype="Geo Model Points",
		target_label="Geo Model Points",
		batch_fieldname="import_batch",
		remarks_fieldname="remarks",
	)


@frappe.whitelist()
def create_pit_outline_points(docname, replace_existing=1):
	return _create_geo_points_for_target(
		docname=docname,
		replace_existing=replace_existing,
		target_doctype="Pit Outline Points",
		target_label="Pit Outline Points",
		batch_fieldname="geo_import_batch",
		remarks_fieldname="remarks_comments",
	)


def _create_geo_points_for_target(
	docname,
	replace_existing=1,
	target_doctype=None,
	target_label=None,
	batch_fieldname=None,
	remarks_fieldname=None,
):
	batch = frappe.get_doc("Geo Import Batch", docname)

	if not batch.raw_file_attachment:
		frappe.throw(f"Please attach a raw file before creating {target_label}.")

	if not batch.geo_project:
		frappe.throw("Geo Project is required.")

	if not batch.version_tag:
		frappe.throw("Version Tag is required.")

	if not batch.variable_code:
		frappe.throw("Please detect and select a Variable Code before importing.")

	file_path = _get_file_path(batch.raw_file_attachment)

	if not os.path.exists(file_path):
		frappe.throw(f"Attached file not found on server: {file_path}")

	variable_code = batch.variable_code.strip()
	variable_name = (batch.variable_name or variable_code).strip()
	full_name = f"{variable_code} - {variable_name}" if variable_name else variable_code
	grid_metadata = _read_grid_metadata(file_path)

	frappe.db.set_value(
		"Geo Import Batch",
		docname,
		{
			"full_name": full_name,
			"processing_status": "Validated",
			"import_log": f"Reading attached file for {target_label} at {now()}...",
		},
		update_modified=False,
	)
	frappe.db.commit()

	points = _parse_selected_variable_file(file_path, variable_code)
	row_count = len(points)

	if row_count == 0:
		available_variables = _detect_variables_from_header(file_path)

		_set_batch_status(
			docname,
			{
				"row_count": 0,
				"success_count": 0,
				"error_count": 1,
				"processing_status": "Error",
				"import_log": "\n".join([
					f"No valid X/Y/value rows found for variable code: {variable_code}",
					f"Target: {target_label}",
					"",
					"Possible reasons:",
					"1. The selected variable exists in the header but has blank values in the data rows.",
					"2. The selected variable code was typed differently from the file header.",
					"3. The file layout is not fixed-width or normal delimited text.",
					"",
					"Available variables detected:",
					", ".join(available_variables) if available_variables else "None",
				]),
			},
		)

		frappe.throw(
			f"No valid X/Y/value rows found for variable code: {variable_code}. "
			"Check the Import Log for detected variables and possible causes."
		)

	geo_model_output = _get_geo_model_output(batch)
	file_hash = _get_file_hash(file_path)

	if replace_existing:
		existing_filters = {}

		if _doctype_has_field(target_doctype, batch_fieldname):
			existing_filters[batch_fieldname] = docname

		if _doctype_has_field(target_doctype, "variable_code"):
			existing_filters["variable_code"] = variable_code
		elif _doctype_has_field(target_doctype, "variable_name"):
			existing_filters["variable_name"] = full_name

		existing_points = frappe.get_all(
			target_doctype,
			filters=existing_filters,
			pluck="name",
		)

		for point_name in existing_points:
			frappe.delete_doc(
				target_doctype,
				point_name,
				force=True,
				ignore_permissions=True,
			)

		frappe.db.commit()

	target_has_variable_code = _doctype_has_field(target_doctype, "variable_code")
	target_has_full_name = _doctype_has_field(target_doctype, "full_name")
	target_has_batch_field = _doctype_has_field(target_doctype, batch_fieldname)
	target_has_remarks_field = _doctype_has_field(target_doctype, remarks_fieldname)

	success_count = 0
	error_count = 0
	error_messages = []

	for index, point in enumerate(points, start=1):
		try:
			point_data = {
				"doctype": target_doctype,
				"geo_project": batch.geo_project,
				"geo_model_output": geo_model_output,
				"row_no": index,
				"x": point["x"],
				"y": point["y"],
				"z": point["z"],
				"variable_name": full_name,
				"version_tag": batch.version_tag,
				"status": "Draft",
			}

			if target_has_batch_field:
				point_data[batch_fieldname] = docname

			if target_has_variable_code:
				point_data["variable_code"] = variable_code

			if target_has_full_name:
				point_data["full_name"] = full_name

			if target_has_remarks_field:
				point_data[remarks_fieldname] = (
					f"Imported from {batch.raw_file_attachment}; "
					f"source line {point['source_line_no']}; "
					f"variable code {variable_code}; "
					f"target {target_label}"
				)

			point_doc = frappe.get_doc(point_data)
			point_doc.insert(ignore_permissions=True)
			success_count += 1

			if success_count % 1000 == 0:
				_set_batch_status(
					docname,
					{
						"row_count": row_count,
						"success_count": success_count,
						"error_count": error_count,
						"processing_status": "Validated",
						"import_log": (
							f"{target_label} import running at {now()}...\n"
							f"Variable Code: {variable_code}\n"
							f"Full Name: {full_name}\n"
							f"Rows found: {row_count}\n"
							f"Rows created so far: {success_count}\n"
							f"Rows failed so far: {error_count}"
						),
					},
				)

		except Exception as e:
			error_count += 1
			error_messages.append(
				f"Row {index}, source line {point.get('source_line_no')}: {str(e)}"
			)

	metadata_lines = []

	if grid_metadata.get("origin"):
		metadata_lines.append(
			f"Origin: {grid_metadata['origin']['x']}, {grid_metadata['origin']['y']}"
		)

	if grid_metadata.get("extent"):
		metadata_lines.append(
			f"Extent: {grid_metadata['extent']['x']}, {grid_metadata['extent']['y']}"
		)

	if grid_metadata.get("mesh"):
		metadata_lines.append(
			f"Mesh: {grid_metadata['mesh']['x']} x {grid_metadata['mesh']['y']}"
		)

	if grid_metadata.get("rotation"):
		metadata_lines.append(
			f"Rotation: {grid_metadata['rotation']}"
		)

	_set_batch_status(
		docname,
		{
			"row_count": row_count,
			"success_count": success_count,
			"error_count": error_count,
			"file_hash": file_hash,
			"processing_status": "Processed" if error_count == 0 else "Error",
			"import_log": "\n".join([
				f"{target_label} import completed at {now()}",
				f"Target Doctype: {target_doctype}",
				f"File: {batch.raw_file_attachment}",
				f"Variable Code: {variable_code}",
				f"Variable Name: {variable_name}",
				f"Full Name: {full_name}",
				f"Version Tag: {batch.version_tag}",
				f"Geo Model Output: {geo_model_output}",
				"",
				"Grid Metadata:",
				"\n".join(metadata_lines) if metadata_lines else "None",
				"",
				f"Rows found: {row_count}",
				f"Rows created: {success_count}",
				f"Rows failed: {error_count}",
				"",
				"Errors:",
				"\n".join(error_messages[:100]) if error_messages else "None",
			]),
		},
	)

	return {
		"row_count": row_count,
		"success_count": success_count,
		"error_count": error_count,
		"geo_model_output": geo_model_output,
		"variable_code": variable_code,
		"variable_name": variable_name,
		"full_name": full_name,
		"target_doctype": target_doctype,
	}