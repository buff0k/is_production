import frappe


@frappe.whitelist()
def get_geo_points(
	geo_project=None,
	version_tag=None,
	variable_name=None,
	import_batch=None,
	geo_model_output=None
):
	filters = {}

	if geo_project:
		filters["geo_project"] = geo_project

	if version_tag:
		filters["version_tag"] = version_tag

	if variable_name:
		filters["variable_name"] = variable_name

	if import_batch:
		filters["import_batch"] = import_batch

	if geo_model_output:
		filters["geo_model_output"] = geo_model_output

	return frappe.get_all(
		"Geo Model Points",
		filters=filters,
		fields=[
			"x",
			"y",
			"z",
			"variable_name",
			"version_tag",
			"import_batch",
			"geo_project",
			"geo_model_output"
		],
		limit_page_length=0,
		order_by="row_no asc"
	)