import json
import frappe


def execute(filters=None):
	filters = filters or {}

	columns = get_columns()
	data = get_data(filters)
	message = get_summary_message(data, filters)
	chart = get_chart(data)

	return columns, data, message, chart


def get_columns():
	return [
		{
			"label": "Geo Project",
			"fieldname": "geo_project",
			"fieldtype": "Link",
			"options": "Geo Project",
			"width": 180
		},
		{
			"label": "Geo Model Output",
			"fieldname": "geo_model_output",
			"fieldtype": "Link",
			"options": "Geo Model Output",
			"width": 180
		},
		{
			"label": "Import Batch",
			"fieldname": "import_batch",
			"fieldtype": "Link",
			"options": "Geo Import Batch",
			"width": 180
		},
		{
			"label": "Row No",
			"fieldname": "row_no",
			"fieldtype": "Int",
			"width": 90
		},
		{
			"label": "X",
			"fieldname": "x",
			"fieldtype": "Float",
			"width": 120
		},
		{
			"label": "Y",
			"fieldname": "y",
			"fieldtype": "Float",
			"width": 130
		},
		{
			"label": "Z / Value",
			"fieldname": "z",
			"fieldtype": "Float",
			"width": 120
		},
		{
			"label": "Heat Band",
			"fieldname": "heat_band",
			"fieldtype": "Data",
			"width": 110
		},
		{
			"label": "Variable Name",
			"fieldname": "variable_name",
			"fieldtype": "Data",
			"width": 140
		},
		{
			"label": "Version Tag",
			"fieldname": "version_tag",
			"fieldtype": "Data",
			"width": 130
		},
		{
			"label": "Status",
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": "Min Z",
			"fieldname": "min_z",
			"fieldtype": "Float",
			"hidden": 1
		},
		{
			"label": "Max Z",
			"fieldname": "max_z",
			"fieldtype": "Float",
			"hidden": 1
		}
	]


def get_data(filters):
	conditions = []
	values = {}

	if filters.get("geo_project"):
		conditions.append("gmp.geo_project = %(geo_project)s")
		values["geo_project"] = filters.get("geo_project")

	if filters.get("geo_model_output"):
		conditions.append("gmp.geo_model_output = %(geo_model_output)s")
		values["geo_model_output"] = filters.get("geo_model_output")

	if filters.get("import_batch"):
		conditions.append("gmp.import_batch = %(import_batch)s")
		values["import_batch"] = filters.get("import_batch")

	if filters.get("status"):
		conditions.append("gmp.status = %(status)s")
		values["status"] = filters.get("status")

	variable_names = normalize_multiselect(filters.get("variable_names"))
	if variable_names:
		conditions.append("gmp.variable_name IN %(variable_names)s")
		values["variable_names"] = tuple(variable_names)

	version_tags = normalize_multiselect(filters.get("version_tags"))
	if version_tags:
		conditions.append("gmp.version_tag IN %(version_tags)s")
		values["version_tags"] = tuple(version_tags)

	if filters.get("x_from") is not None:
		conditions.append("gmp.x >= %(x_from)s")
		values["x_from"] = filters.get("x_from")

	if filters.get("x_to") is not None:
		conditions.append("gmp.x <= %(x_to)s")
		values["x_to"] = filters.get("x_to")

	if filters.get("y_from") is not None:
		conditions.append("gmp.y >= %(y_from)s")
		values["y_from"] = filters.get("y_from")

	if filters.get("y_to") is not None:
		conditions.append("gmp.y <= %(y_to)s")
		values["y_to"] = filters.get("y_to")

	if filters.get("z_from") is not None:
		conditions.append("gmp.z >= %(z_from)s")
		values["z_from"] = filters.get("z_from")

	if filters.get("z_to") is not None:
		conditions.append("gmp.z <= %(z_to)s")
		values["z_to"] = filters.get("z_to")

	where_clause = ""
	if conditions:
		where_clause = "WHERE " + " AND ".join(conditions)

	limit = filters.get("limit") or 5000
	try:
		limit = int(limit)
	except Exception:
		limit = 5000

	if limit <= 0:
		limit = 5000

	if limit > 50000:
		limit = 50000

	values["limit"] = limit

	range_row = frappe.db.sql(
		f"""
		SELECT
			MIN(gmp.z) AS min_z,
			MAX(gmp.z) AS max_z
		FROM `tabGeo Model Points` gmp
		{where_clause}
		""",
		values,
		as_dict=True
	)

	min_z = range_row[0].min_z if range_row and range_row[0].min_z is not None else 0
	max_z = range_row[0].max_z if range_row and range_row[0].max_z is not None else 0

	rows = frappe.db.sql(
		f"""
		SELECT
			gmp.geo_project,
			gmp.geo_model_output,
			gmp.import_batch,
			gmp.row_no,
			gmp.x,
			gmp.y,
			gmp.z,
			gmp.variable_name,
			gmp.version_tag,
			gmp.status
		FROM `tabGeo Model Points` gmp
		{where_clause}
		ORDER BY
			gmp.variable_name,
			gmp.version_tag,
			gmp.row_no
		LIMIT %(limit)s
		""",
		values,
		as_dict=True
	)

	for row in rows:
		row["min_z"] = min_z
		row["max_z"] = max_z
		row["heat_band"] = get_heat_band(row.z, min_z, max_z)

	return rows


def get_heat_band(z, min_z, max_z):
	try:
		z = float(z)
		min_z = float(min_z)
		max_z = float(max_z)
	except Exception:
		return "Unknown"

	if max_z <= min_z:
		return "Single"

	ratio = (z - min_z) / (max_z - min_z)

	if ratio >= 0.66:
		return "High"

	if ratio >= 0.33:
		return "Medium"

	return "Low"


def normalize_multiselect(value):
	if not value:
		return []

	if isinstance(value, list):
		return [v for v in value if v]

	if isinstance(value, tuple):
		return [v for v in value if v]

	if isinstance(value, str):
		try:
			parsed = json.loads(value)
			if isinstance(parsed, list):
				return [v for v in parsed if v]
		except Exception:
			pass

		return [v.strip() for v in value.split(",") if v.strip()]

	return []


def get_summary_message(data, filters):
	if not data:
		return """
			<div style="padding:10px; border-radius:8px; background:#fff7ed;">
				<b>No Geo Model Points found.</b><br>
				Adjust your project, variable, version, coordinate, or Z-value filters.
			</div>
		"""

	z_values = [row.z for row in data if row.z is not None]

	min_z = min(z_values) if z_values else 0
	max_z = max(z_values) if z_values else 0
	avg_z = sum(z_values) / len(z_values) if z_values else 0

	variables = sorted(set([row.variable_name for row in data if row.variable_name]))
	versions = sorted(set([row.version_tag for row in data if row.version_tag]))

	return f"""
		<div style="
			display:grid;
			grid-template-columns: repeat(4, minmax(160px, 1fr));
			gap:10px;
			margin-bottom:12px;
		">
			<div style="padding:12px; border-radius:10px; background:#eff6ff;">
				<b>Rows Shown</b><br>{len(data)}
			</div>
			<div style="padding:12px; border-radius:10px; background:#f0fdf4;">
				<b>Z Range</b><br>{round(min_z, 4)} to {round(max_z, 4)}
			</div>
			<div style="padding:12px; border-radius:10px; background:#fff7ed;">
				<b>Average Z</b><br>{round(avg_z, 4)}
			</div>
			<div style="padding:12px; border-radius:10px; background:#fef2f2;">
				<b>Variables / Versions</b><br>{len(variables)} / {len(versions)}
			</div>
		</div>
	"""


def get_chart(data):
	if not data:
		return None

	bands = {
		"Low": 0,
		"Medium": 0,
		"High": 0,
		"Single": 0,
		"Unknown": 0
	}

	for row in data:
		bands[row.heat_band] = bands.get(row.heat_band, 0) + 1

	return {
		"data": {
			"labels": list(bands.keys()),
			"datasets": [
				{
					"name": "Point Count",
					"values": list(bands.values())
				}
			]
		},
		"type": "bar",
		"height": 220
	}


@frappe.whitelist()
def get_filter_options(fieldname, txt=None):
	allowed_fields = {
		"variable_name",
		"version_tag"
	}

	if fieldname not in allowed_fields:
		frappe.throw("Invalid filter field.")

	txt = txt or ""

	rows = frappe.db.sql(
		f"""
		SELECT DISTINCT {fieldname} AS value
		FROM `tabGeo Model Points`
		WHERE
			{fieldname} IS NOT NULL
			AND {fieldname} != ''
			AND {fieldname} LIKE %(txt)s
		ORDER BY {fieldname}
		LIMIT 50
		""",
		{"txt": f"%{txt}%"},
		as_dict=True
	)

	return [
		{
			"value": row.value,
			"description": row.value
		}
		for row in rows
	]