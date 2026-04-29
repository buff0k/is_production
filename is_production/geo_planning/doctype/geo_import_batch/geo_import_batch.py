import os
import re
import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import now


class GeoImportBatch(Document):
	pass


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


def _detect_variable_from_header(line):
	clean = line.replace(";", "").strip()
	parts = clean.split()

	if not parts:
		return None

	key = parts[0].strip()

	if key.lower() in {"origin", "extent", "mesh", "rotation", "x", "y", "z"}:
		return None

	return key


def _split_line(line):
	clean = line.strip()

	if "," in clean:
		return [p.strip() for p in clean.split(",")]

	if "\t" in clean:
		return [p.strip() for p in clean.split("\t")]

	if ";" in clean and not clean.startswith(";"):
		return [p.strip() for p in clean.split(";")]

	return re.split(r"\s+", clean)


def _parse_any_xyz_file(file_path):
	points = []
	header_variable_name = None
	header_map = None

	with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
		for physical_line_no, line in enumerate(f, start=1):
			clean = line.strip()

			if not clean:
				continue

			if clean.startswith(";"):
				found_variable = _detect_variable_from_header(clean)
				if found_variable:
					header_variable_name = found_variable
				continue

			parts = _split_line(clean)

			if len(parts) < 3:
				continue

			lower_parts = [p.lower().strip() for p in parts]

			if "x" in lower_parts and "y" in lower_parts:
				try:
					header_map = {
						"x": lower_parts.index("x"),
						"y": lower_parts.index("y"),
					}

					if "z" in lower_parts:
						header_map["z"] = lower_parts.index("z")
					elif "value" in lower_parts:
						header_map["z"] = lower_parts.index("value")
					elif "tops" in lower_parts:
						header_map["z"] = lower_parts.index("tops")
						header_variable_name = "TOPS"

					continue
				except Exception:
					header_map = None
					continue

			try:
				if header_map:
					x_raw = parts[header_map["x"]]
					y_raw = parts[header_map["y"]]
					z_raw = parts[header_map["z"]]
				else:
					numeric_parts = [p for p in parts if _is_number(p)]

					if len(numeric_parts) < 3:
						continue

					x_raw = numeric_parts[0]
					y_raw = numeric_parts[1]
					z_raw = numeric_parts[2]

				points.append({
					"source_line_no": physical_line_no,
					"x": _to_float(x_raw),
					"y": _to_float(y_raw),
					"z": _to_float(z_raw),
				})

			except Exception:
				continue

	return points, header_variable_name


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
		"Create the Geo Model Output first, then press Geo Model Points."
	)


def _publish_complete(user, batch_name, status, row_count=0, success_count=0, error_count=0):
	if not user:
		return

	frappe.publish_realtime(
		"geo_model_points_import_complete",
		{
			"status": status,
			"batch": batch_name,
			"row_count": row_count,
			"success_count": success_count,
			"error_count": error_count,
		},
		user=user,
	)


def create_geo_model_points_background(docname, replace_existing=1, user=None):
	try:
		result = _create_geo_model_points(docname, replace_existing)

		_publish_complete(
			user=user,
			batch_name=docname,
			status="success",
			row_count=result["row_count"],
			success_count=result["success_count"],
			error_count=result["error_count"],
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
			batch_name=docname,
			status="error",
			row_count=0,
			success_count=0,
			error_count=1,
		)

		raise


@frappe.whitelist()
def create_geo_model_points(docname, replace_existing=1):
	return _create_geo_model_points(docname, replace_existing)


def _create_geo_model_points(docname, replace_existing=1):
	batch = frappe.get_doc("Geo Import Batch", docname)

	if not batch.raw_file_attachment:
		frappe.throw("Please attach a raw file before creating Geo Model Points.")

	if not batch.geo_project:
		frappe.throw("Geo Project is required.")

	if not batch.version_tag:
		frappe.throw("Version Tag is required.")

	file_path = _get_file_path(batch.raw_file_attachment)

	if not os.path.exists(file_path):
		frappe.throw(f"Attached file not found on server: {file_path}")

	_set_batch_status(
		docname,
		{
			"processing_status": "Validated",
			"import_log": f"Reading attached file at {now()}...",
		},
	)

	points, header_variable_name = _parse_any_xyz_file(file_path)
	row_count = len(points)

	if row_count == 0:
		_set_batch_status(
			docname,
			{
				"row_count": 0,
				"success_count": 0,
				"error_count": 1,
				"processing_status": "Error",
				"import_log": "No valid X Y Z rows found in attached file.",
			},
		)
		frappe.throw("No valid X Y Z rows found in the attached file.")

	variable_name = batch.variable_name or header_variable_name or "MODEL_VALUE"
	geo_model_output = _get_geo_model_output(batch)
	file_hash = _get_file_hash(file_path)

	if replace_existing:
		existing_points = frappe.get_all(
			"Geo Model Points",
			filters={"import_batch": docname},
			pluck="name",
		)

		for point_name in existing_points:
			frappe.delete_doc(
				"Geo Model Points",
				point_name,
				force=True,
				ignore_permissions=True,
			)

		frappe.db.commit()

	success_count = 0
	error_count = 0
	error_messages = []

	for index, point in enumerate(points, start=1):
		try:
			point_doc = frappe.get_doc({
				"doctype": "Geo Model Points",
				"geo_project": batch.geo_project,
				"geo_model_output": geo_model_output,
				"import_batch": docname,
				"row_no": index,
				"x": point["x"],
				"y": point["y"],
				"z": point["z"],
				"variable_name": variable_name,
				"version_tag": batch.version_tag,
				"status": "Draft",
				"remarks": f"Imported from {batch.raw_file_attachment}; source line {point['source_line_no']}",
			})

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
							f"Import running at {now()}...\n"
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

	_set_batch_status(
		docname,
		{
			"row_count": row_count,
			"success_count": success_count,
			"error_count": error_count,
			"file_hash": file_hash,
			"processing_status": "Processed" if error_count == 0 else "Error",
			"import_log": "\n".join([
				f"Geo Model Points import completed at {now()}",
				f"File: {batch.raw_file_attachment}",
				f"Variable Name: {variable_name}",
				f"Version Tag: {batch.version_tag}",
				f"Geo Model Output: {geo_model_output}",
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
		"variable_name": variable_name,
	}