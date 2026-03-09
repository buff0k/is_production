import frappe
from frappe import _
from frappe.utils import flt, getdate


DOCTYPE = "Daily Drilling Report"
TABLE = f"`tab{DOCTYPE}`"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	_validate_filters(filters)

	columns = get_columns()
	data = get_data(filters)

	# Add TOTAL row at the bottom of the grid
	data = add_total_row(data)

	# ✅ Report Summary removed (top cards)
	return columns, data, None, None, None


def _validate_filters(filters):
	if filters.get("start_date") and filters.get("end_date"):
		start = getdate(filters.start_date)
		end = getdate(filters.end_date)
		if start > end:
			frappe.throw(_("Start Date cannot be after End Date."))


def get_columns():
	return [
		{"label": _("ID"), "fieldname": "name", "fieldtype": "Link", "options": DOCTYPE, "width": 220},
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 110},
		{"label": _("Site"), "fieldname": "site", "fieldtype": "Data", "width": 140},
		{"label": _("Area"), "fieldname": "area", "fieldtype": "Data", "width": 140},
		{"label": _("Material"), "fieldname": "material", "fieldtype": "Data", "width": 140},
		{"label": _("Drill No"), "fieldname": "drill_no", "fieldtype": "Data", "width": 120},
		{"label": _("Shift"), "fieldname": "shift", "fieldtype": "Data", "width": 90},

		{"label": _("Total Holes"), "fieldname": "holes", "fieldtype": "Float", "width": 110},
		{"label": _("Total Meters"), "fieldname": "meters", "fieldtype": "Float", "width": 110},
		{"label": _("Total Drill Hrs"), "fieldname": "drill_hrs", "fieldtype": "Float", "width": 120},
	]


def get_data(filters):
	conditions, values = get_conditions(filters)

	query = f"""
		SELECT
			name,
			date,
			site,
			area,
			material,
			drill_no,
			shift,
			COALESCE(total_holes, 0) AS holes,
			COALESCE(total_meters, 0) AS meters,
			COALESCE(total_drilling_hrs, 0) AS drill_hrs
		FROM {TABLE}
		WHERE docstatus < 2
			{conditions}
		ORDER BY date ASC, name ASC
	"""

	return frappe.db.sql(query, values, as_dict=True)


def get_conditions(filters):
	conditions = []
	values = {}

	# Date range
	if filters.get("start_date"):
		conditions.append("AND date >= %(start_date)s")
		values["start_date"] = filters.start_date

	if filters.get("end_date"):
		conditions.append("AND date <= %(end_date)s")
		values["end_date"] = filters.end_date

	# ✅ Site (ignore All / blank)
	if filters.get("site") and str(filters.site).strip() and str(filters.site).lower() != "all":
		conditions.append("AND site = %(site)s")
		values["site"] = str(filters.site).strip()

	return "\n".join(conditions), values


def add_total_row(data):
	total_holes = 0.0
	total_meters = 0.0
	total_drill_hrs = 0.0

	for row in data:
		if (row.get("name") or "") == "TOTAL":
			continue
		total_holes += flt(row.get("holes") or 0)
		total_meters += flt(row.get("meters") or 0)
		total_drill_hrs += flt(row.get("drill_hrs") or 0)

	data.append({
		"name": "TOTAL",
		"date": None,
		"site": "",
		"area": "",
		"material": "",
		"drill_no": "",
		"shift": "",
		"holes": total_holes,
		"meters": total_meters,
		"drill_hrs": total_drill_hrs,
	})
	return data