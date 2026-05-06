import os

import frappe
from frappe.model.document import Document
from frappe.utils import now

from is_production.geo_planning.doctype.geo_import_batch.geo_import_batch import (
	_get_file_path,
	_get_file_hash,
	_detect_variables_from_header,
	_parse_selected_variable_file,
	_get_geo_model_output,
)


class GeoCalculationBatch(Document):
	def validate(self):
		self.set_full_names()
		self.set_defaults()

	def set_defaults(self):
		if not self.source_mode:
			self.source_mode = "Attached Files"

		if not self.calculation_type:
			self.calculation_type = "Reference Minus Target"

		if not self.processing_status:
			self.processing_status = "Draft"

		if not self.approval_status:
			self.approval_status = "Draft"

		if not self.coordinate_rounding:
			self.coordinate_rounding = 2

		if not self.replace_existing:
			self.replace_existing = 1

	def set_full_names(self):
		self.reference_full_name = _make_full_name(
			self.reference_variable_code,
			self.reference_variable_name,
		)

		self.target_full_name = _make_full_name(
			self.target_variable_code,
			self.target_variable_name,
		)

		self.calculated_full_name = _make_full_name(
			self.calculated_variable_code,
			self.calculated_variable_name,
		)


def _make_full_name(code, name):
	code = (code or "").strip()
	name = (name or "").strip()

	if code and name:
		return f"{code} - {name}"

	if code:
		return code

	return ""


def _doctype_has_field(doctype, fieldname):
	return fieldname in [df.fieldname for df in frappe.get_meta(doctype).fields]


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


def _get_source_file_path(batch, side):
	source_mode = batch.source_mode or "Attached Files"

	if side not in {"reference", "target"}:
		frappe.throw("Invalid side. Use reference or target.")

	if source_mode == "Attached Files":
		file_url = batch.get(f"{side}_file_attachment")

		if not file_url:
			frappe.throw(f"{side.title()} File Attachment is required.")

		return _get_file_path(file_url)

	if source_mode == "Existing Import Batches":
		import_batch_name = batch.get(f"{side}_import_batch")

		if not import_batch_name:
			frappe.throw(f"{side.title()} Import Batch is required.")

		import_batch = frappe.get_doc("Geo Import Batch", import_batch_name)

		if not import_batch.raw_file_attachment:
			frappe.throw(f"{side.title()} Import Batch has no Raw File Attachment.")

		return _get_file_path(import_batch.raw_file_attachment)

	frappe.throw(f"Unsupported Source Mode: {source_mode}")


@frappe.whitelist()
def detect_calculation_variables(docname, side):
	batch = frappe.get_doc("Geo Calculation Batch", docname)
	file_path = _get_source_file_path(batch, side)

	if not os.path.exists(file_path):
		frappe.throw(f"Attached file not found on server: {file_path}")

	variables = _detect_variables_from_header(file_path)

	return [{"code": v} for v in variables]


@frappe.whitelist()
def enqueue_create_calculated_points(docname, replace_existing=1):
	job = frappe.enqueue(
		"is_production.geo_planning.doctype.geo_calculation_batch.geo_calculation_batch.create_calculated_points_background",
		queue="long",
		timeout=7200,
		docname=docname,
		replace_existing=int(replace_existing),
		user=frappe.session.user,
		job_name=f"Create Geo Calculated Points - {docname}",
	)

	frappe.db.set_value(
		"Geo Calculation Batch",
		docname,
		{
			"processing_status": "Validated",
			"calculation_log": f"Background calculated points job started at {now()}.\nJob ID: {job.id}",
		},
		update_modified=False,
	)
	frappe.db.commit()

	return {"job_id": job.id}


def _publish_complete(
	user,
	batch_name,
	status,
	reference_row_count=0,
	target_row_count=0,
	matched_count=0,
	success_count=0,
	error_count=0,
	variable_code=None,
	full_name=None,
):
	if not user:
		return

	frappe.publish_realtime(
		"geo_calculated_points_complete",
		{
			"status": status,
			"batch": batch_name,
			"reference_row_count": reference_row_count,
			"target_row_count": target_row_count,
			"matched_count": matched_count,
			"success_count": success_count,
			"error_count": error_count,
			"variable_code": variable_code,
			"full_name": full_name,
		},
		user=user,
	)


def _coordinate_key(x, y, decimals):
	decimals = _int(decimals, 2)
	return f"{round(_float(x), decimals):.{decimals}f}|{round(_float(y), decimals):.{decimals}f}"


def _calculate_value(reference_z, target_z, calculation_type):
	reference_z = _float(reference_z)
	target_z = _float(target_z)

	if calculation_type == "Target Minus Reference":
		return target_z - reference_z

	if calculation_type == "Absolute Difference":
		return abs(reference_z - target_z)

	return reference_z - target_z


def _resolve_geo_model_output(batch):
	if batch.geo_model_output:
		return batch.geo_model_output

	if batch.source_mode == "Existing Import Batches" and batch.reference_import_batch:
		return _get_geo_model_output(frappe.get_doc("Geo Import Batch", batch.reference_import_batch))

	frappe.throw(
		"Geo Model Output is required when using Attached Files. "
		"Set Geo Model Output on the Geo Calculation Batch."
	)


def _delete_existing_points(batch):
	if not frappe.db.exists("DocType", "Geo Calculated Points"):
		return

	existing = frappe.get_all(
		"Geo Calculated Points",
		filters={"calculation_batch": batch.name},
		pluck="name",
	)

	for name in existing:
		frappe.delete_doc(
			"Geo Calculated Points",
			name,
			force=True,
			ignore_permissions=True,
		)

	frappe.db.commit()


def _set_batch_status(docname, values):
	frappe.db.set_value(
		"Geo Calculation Batch",
		docname,
		values,
		update_modified=False,
	)
	frappe.db.commit()


def create_calculated_points_background(docname, replace_existing=1, user=None):
	try:
		result = create_calculated_points(docname, replace_existing)

		_publish_complete(
			user=user,
			batch_name=docname,
			status="success",
			reference_row_count=result["reference_row_count"],
			target_row_count=result["target_row_count"],
			matched_count=result["matched_count"],
			success_count=result["success_count"],
			error_count=result["error_count"],
			variable_code=result["calculated_variable_code"],
			full_name=result["calculated_full_name"],
		)

		return result

	except Exception:
		error_message = frappe.get_traceback()

		_set_batch_status(
			docname,
			{
				"processing_status": "Error",
				"error_count": 1,
				"calculation_log": f"Background calculated points job failed at {now()}.\n\n{error_message}",
			},
		)

		_publish_complete(
			user=user,
			batch_name=docname,
			status="error",
			error_count=1,
		)

		raise


@frappe.whitelist()
def create_calculated_points(docname, replace_existing=1):
	batch = frappe.get_doc("Geo Calculation Batch", docname)

	if not batch.geo_project:
		frappe.throw("Geo Project is required.")

	if not batch.geo_model_output:
		frappe.throw("Geo Model Output is required.")

	if not batch.version_tag:
		frappe.throw("Version Tag is required.")

	if not batch.reference_variable_code:
		frappe.throw("Reference Variable Code is required.")

	if not batch.target_variable_code:
		frappe.throw("Target Variable Code is required.")

	if not batch.calculated_variable_code:
		frappe.throw("Calculated Variable Code is required.")

	if not frappe.db.exists("DocType", "Geo Calculated Points"):
		frappe.throw("Please create DocType: Geo Calculated Points.")

	reference_file_path = _get_source_file_path(batch, "reference")
	target_file_path = _get_source_file_path(batch, "target")

	if not os.path.exists(reference_file_path):
		frappe.throw(f"Reference file not found on server: {reference_file_path}")

	if not os.path.exists(target_file_path):
		frappe.throw(f"Target file not found on server: {target_file_path}")

	_set_batch_status(
		docname,
		{
			"processing_status": "Processing",
			"calculation_log": f"Reading reference and target files at {now()}...",
		},
	)

	reference_points = _parse_selected_variable_file(
		reference_file_path,
		batch.reference_variable_code,
	)

	target_points = _parse_selected_variable_file(
		target_file_path,
		batch.target_variable_code,
	)

	reference_row_count = len(reference_points)
	target_row_count = len(target_points)

	if not reference_points:
		frappe.throw(f"No valid rows found for reference variable: {batch.reference_variable_code}")

	if not target_points:
		frappe.throw(f"No valid rows found for target variable: {batch.target_variable_code}")

	if int(replace_existing or 0):
		_delete_existing_points(batch)

	geo_model_output = _resolve_geo_model_output(batch)
	coordinate_rounding = _int(batch.coordinate_rounding, 2)
	calculation_type = batch.calculation_type or "Reference Minus Target"

	reference_lookup = {}

	for point in reference_points:
		key = _coordinate_key(point["x"], point["y"], coordinate_rounding)
		reference_lookup[key] = point

	target_keys = set()
	success_count = 0
	error_count = 0
	matched_count = 0
	missing_reference_count = 0
	error_messages = []

	for index, target_point in enumerate(target_points, start=1):
		try:
			key = _coordinate_key(target_point["x"], target_point["y"], coordinate_rounding)
			target_keys.add(key)

			reference_point = reference_lookup.get(key)

			if not reference_point:
				missing_reference_count += 1
				continue

			matched_count += 1

			reference_z = _float(reference_point["z"])
			target_z = _float(target_point["z"])
			calculated_z = _calculate_value(reference_z, target_z, calculation_type)

			if calculated_z < 0 and not batch.allow_negative_values:
				error_count += 1
				error_messages.append(
					f"Row {index}: negative calculated value at {target_point['x']}, {target_point['y']}. "
					f"Reference {reference_z}, target {target_z}, result {calculated_z}."
				)
				continue

			doc = frappe.new_doc("Geo Calculated Points")

			_set_if_field(doc, "geo_project", batch.geo_project)
			_set_if_field(doc, "geo_model_output", geo_model_output)
			_set_if_field(doc, "calculation_batch", batch.name)
			_set_if_field(doc, "row_no", success_count + 1)

			_set_if_field(doc, "x", _float(target_point["x"]))
			_set_if_field(doc, "y", _float(target_point["y"]))

			_set_if_field(doc, "z", calculated_z)
			_set_if_field(doc, "calculated_z", calculated_z)
			_set_if_field(doc, "reference_z", reference_z)
			_set_if_field(doc, "target_z", target_z)

			_set_if_field(doc, "reference_variable_code", batch.reference_variable_code)
			_set_if_field(doc, "reference_variable_name", batch.reference_full_name)
			_set_if_field(doc, "target_variable_code", batch.target_variable_code)
			_set_if_field(doc, "target_variable_name", batch.target_full_name)

			_set_if_field(doc, "variable_code", batch.calculated_variable_code)
			_set_if_field(doc, "variable_name", batch.calculated_full_name)
			_set_if_field(doc, "full_name", batch.calculated_full_name)

			_set_if_field(doc, "calculation_type", calculation_type)
			_set_if_field(doc, "match_status", "Matched")
			_set_if_field(doc, "version_tag", batch.version_tag)
			_set_if_field(doc, "status", "Draft")
			_set_if_field(
				doc,
				"remarks",
				f"{batch.calculated_variable_code} = {batch.reference_variable_code} - {batch.target_variable_code}; "
				f"reference {reference_z}; target {target_z}; calculated {calculated_z}; key {key}"
			)

			doc.insert(ignore_permissions=True)
			success_count += 1

			if success_count % 1000 == 0:
				_set_batch_status(
					docname,
					{
						"reference_row_count": reference_row_count,
						"target_row_count": target_row_count,
						"matched_count": matched_count,
						"missing_reference_count": missing_reference_count,
						"success_count": success_count,
						"error_count": error_count,
						"processing_status": "Processing",
						"calculation_log": (
							f"Calculation running at {now()}...\n"
							f"Calculated Variable: {batch.calculated_full_name}\n"
							f"Reference rows: {reference_row_count}\n"
							f"Target rows: {target_row_count}\n"
							f"Matched so far: {matched_count}\n"
							f"Created so far: {success_count}\n"
							f"Errors so far: {error_count}"
						),
					},
				)

		except Exception as e:
			error_count += 1
			error_messages.append(f"Target row {index}: {str(e)}")

	reference_keys = set(reference_lookup.keys())
	missing_target_count = len(reference_keys - target_keys)

	reference_file_hash = _get_file_hash(reference_file_path)
	target_file_hash = _get_file_hash(target_file_path)

	processing_status = "Processed" if error_count == 0 else "Error"

	_set_batch_status(
		docname,
		{
			"geo_model_output": geo_model_output,
			"calculated_full_name": batch.calculated_full_name,
			"reference_full_name": batch.reference_full_name,
			"target_full_name": batch.target_full_name,
			"reference_row_count": reference_row_count,
			"target_row_count": target_row_count,
			"matched_count": matched_count,
			"missing_reference_count": missing_reference_count,
			"missing_target_count": missing_target_count,
			"success_count": success_count,
			"error_count": error_count,
			"reference_file_hash": reference_file_hash,
			"target_file_hash": target_file_hash,
			"processing_status": processing_status,
			"calculation_date": now(),
			"calculated_by": frappe.session.user,
			"calculation_log": "\n".join([
				f"Geo Calculated Points completed at {now()}",
				f"Source Mode: {batch.source_mode}",
				f"Calculation Type: {calculation_type}",
				f"Calculated Variable Code: {batch.calculated_variable_code}",
				f"Calculated Full Name: {batch.calculated_full_name}",
				f"Reference Variable: {batch.reference_variable_code}",
				f"Target Variable: {batch.target_variable_code}",
				f"Coordinate Rounding: {coordinate_rounding}",
				f"Geo Model Output: {geo_model_output}",
				"",
				f"Reference rows: {reference_row_count}",
				f"Target rows: {target_row_count}",
				f"Matched rows: {matched_count}",
				f"Missing reference rows: {missing_reference_count}",
				f"Missing target rows: {missing_target_count}",
				f"Created rows: {success_count}",
				f"Error rows: {error_count}",
				"",
				"Errors:",
				"\n".join(error_messages[:100]) if error_messages else "None",
			]),
		},
	)

	return {
		"reference_row_count": reference_row_count,
		"target_row_count": target_row_count,
		"matched_count": matched_count,
		"missing_reference_count": missing_reference_count,
		"missing_target_count": missing_target_count,
		"success_count": success_count,
		"error_count": error_count,
		"geo_model_output": geo_model_output,
		"calculated_variable_code": batch.calculated_variable_code,
		"calculated_full_name": batch.calculated_full_name,
	}