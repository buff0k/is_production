import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
	f = _normalize_filters(filters)

	columns = _get_columns()
	if not f["start_date"] or not f["end_date"]:
		return columns, []

	# 1) Excavators list (Asset)
	excavators = _get_excavators(site=f["site"])
	if not excavators:
		return columns, []

	display_list, valid_ids, id_to_display = _build_excavator_keys(excavators)

	# 2) Working Hours (Pre-Use)
	working_map = _get_working_hours_map(
		start_date=f["start_date"],
		end_date=f["end_date"],
		site=f["site"],
		shift=f["shift"],
		valid_ids=valid_ids,
	)

	# 3) Non-production hours
	non_prod_map = _get_non_prod_hours_map(
		start_date=f["start_date"],
		end_date=f["end_date"],
		site=f["site"],
		shift=f["shift"],
		valid_ids=valid_ids,
	)

	# 4) BCMs (Hourly Production -> Truck Loads)
	bcms_map = _get_bcms_map(
		start_date=f["start_date"],
		end_date=f["end_date"],
		site=f["site"],
		shift=f["shift"],
		valid_ids=valid_ids,
	)

	working = _normalize_to_display(working_map, id_to_display)
	non_prod = _normalize_to_display(non_prod_map, id_to_display)
	bcms = _normalize_to_display(bcms_map, id_to_display)

	data = []
	for exc in display_list:
		wh = flt(working.get(exc, 0.0), 3)
		nh = flt(non_prod.get(exc, 0.0), 3)

		total_prod = flt(wh - nh, 3)
		b = flt(bcms.get(exc, 0.0), 3)

		pct = flt((total_prod / wh) * 100.0, 2) if wh else 0.0
		rate = flt((b / total_prod), 3) if total_prod else 0.0

		data.append(
			{
				"excavator": exc,
				"working_hours": wh,
				"non_prod_hours": nh,
				"total_prod_hours": total_prod,
				"bcms": b,
				"pct_hours_prod": pct,
				"rate_per_hour": rate,
			}
		)

	return columns, data


def _get_columns():
	return [
		{"label": _("Excavators"), "fieldname": "excavator", "fieldtype": "Data", "width": 180},
		{"label": _("Working Hours"), "fieldname": "working_hours", "fieldtype": "Float", "width": 140},
		{"label": _("Hours (Non-Production)"), "fieldname": "non_prod_hours", "fieldtype": "Float", "width": 170},
		{"label": _("Total Hours on Production"), "fieldname": "total_prod_hours", "fieldtype": "Float", "width": 180},
		{"label": _("BCM's"), "fieldname": "bcms", "fieldtype": "Float", "width": 120},
		{"label": _("% Hours on Production"), "fieldname": "pct_hours_prod", "fieldtype": "Percent", "width": 170},
		{"label": _("Rates per Hour"), "fieldname": "rate_per_hour", "fieldtype": "Float", "width": 140},
	]


def _normalize_filters(filters):
	filters = filters or {}

	start_date = getdate(filters.get("start_date")) if filters.get("start_date") else None
	end_date = getdate(filters.get("end_date")) if filters.get("end_date") else None

	if start_date and not end_date:
		end_date = start_date
	if end_date and not start_date:
		start_date = end_date

	shift = filters.get("shift")
	if shift and shift not in ("Day", "Night", "Morning", "Afternoon"):
		shift = None

	return {
		"start_date": start_date,
		"end_date": end_date,
		"site": filters.get("site"),
		"shift": shift,
	}


def _get_excavators(site=None):
	filters = {"asset_category": "Excavator", "docstatus": 1}
	if site:
		filters["location"] = site

	return frappe.get_all(
		"Asset",
		filters=filters,
		fields=["name", "asset_name"],
		order_by="asset_name asc",
		limit_page_length=5000,
	)


def _build_excavator_keys(exc_rows):
	display_list = []
	valid_ids = []
	id_to_display = {}

	for r in exc_rows:
		name = r.get("name")
		asset_name = r.get("asset_name")
		display = asset_name or name
		if not display:
			continue

		display_list.append(display)

		# Match via Asset.name AND Asset.asset_name (your system uses both patterns)
		if name:
			valid_ids.append(name)
			id_to_display[name] = display
		if asset_name:
			valid_ids.append(asset_name)
			id_to_display[asset_name] = display

	seen = set()
	valid_ids = [x for x in valid_ids if not (x in seen or seen.add(x))]

	return display_list, valid_ids, id_to_display


def _normalize_to_display(raw_map, id_to_display):
	out = {}
	for k, v in (raw_map or {}).items():
		display = id_to_display.get(k)
		if not display:
			continue
		out[display] = out.get(display, 0.0) + flt(v)
	return out


def _in_clause(field_sql, values, params):
	if not values:
		return "1=0"
	placeholders = ", ".join(["%s"] * len(values))
	params.extend(values)
	return f"{field_sql} IN ({placeholders})"


# ----------------------------
# Working Hours: Pre-Use Hours -> Pre-use Assets
# ----------------------------
def _get_working_hours_map(start_date, end_date, site, shift, valid_ids):
	parent_dt = "Pre-Use Hours"
	child_dt = "Pre-use Assets"

	params = []
	conds = ["p.docstatus < 2", "p.shift_date BETWEEN %s AND %s"]
	params.extend([start_date, end_date])

	if site:
		conds.append("p.location = %s")
		params.append(site)

	if shift:
		conds.append("p.shift = %s")
		params.append(shift)

	conds.append(_in_clause("c.asset_name", valid_ids, params))
	where_sql = " AND ".join(conds)

	rows = frappe.db.sql(
		f"""
		SELECT
			c.asset_name AS excavator,
			COALESCE(SUM(COALESCE(c.working_hours, 0)), 0) AS working_hours
		FROM `tab{parent_dt}` p
		INNER JOIN `tab{child_dt}` c ON c.parent = p.name
		WHERE {where_sql}
		GROUP BY c.asset_name
		""",
		params,
		as_dict=True,
	)

	return {r["excavator"]: flt(r["working_hours"]) for r in rows if r.get("excavator")}


# ----------------------------
# Non-Production: NP Worked Hours -> Equipment Breakdown
# ----------------------------
def _get_non_prod_hours_map(start_date, end_date, site, shift, valid_ids):
	parent_dt = "Non-Production Worked Hours"
	child_dt = "Equipment Breakdown"

	params = []
	conds = ["p.docstatus < 2", "p.shift_date BETWEEN %s AND %s"]
	params.extend([start_date, end_date])

	parent_meta = frappe.get_meta(parent_dt)
	site_field = "location" if parent_meta.has_field("location") else ("site" if parent_meta.has_field("site") else None)
	shift_field = "shift" if parent_meta.has_field("shift") else None

	if site and site_field:
		conds.append(f"p.`{site_field}` = %s")
		params.append(site)

	if shift and shift_field:
		conds.append("p.shift = %s")
		params.append(shift)

	conds.append(_in_clause("c.machine", valid_ids, params))
	where_sql = " AND ".join(conds)

	rows = frappe.db.sql(
		f"""
		SELECT
			c.machine AS excavator,
			COALESCE(SUM(COALESCE(c.hours, 0)), 0) AS non_prod_hours
		FROM `tab{parent_dt}` p
		INNER JOIN `tab{child_dt}` c ON c.parent = p.name
		WHERE {where_sql}
		GROUP BY c.machine
		""",
		params,
		as_dict=True,
	)

	return {r["excavator"]: flt(r["non_prod_hours"]) for r in rows if r.get("excavator")}


# ----------------------------
# BCMs: Hourly Production -> Truck Loads
#
# IMPORTANT FIX:
# Your Hourly Production logic uses docstatus < 2 in calculations.
# So we also use docstatus < 2 here (NOT docstatus = 1).
# ----------------------------
def _get_bcms_map(start_date, end_date, site, shift, valid_ids):
	parent_dt = "Hourly Production"
	child_dt = "Truck Loads"

	params = []
	conds = ["p.docstatus < 2", "p.prod_date BETWEEN %s AND %s"]
	params.extend([start_date, end_date])

	if site:
		conds.append("p.location = %s")
		params.append(site)

	if shift:
		conds.append("p.shift = %s")
		params.append(shift)

	conds.append(_in_clause("c.asset_name_shoval", valid_ids, params))
	where_sql = " AND ".join(conds)

	rows = frappe.db.sql(
		f"""
		SELECT
			c.asset_name_shoval AS excavator,
			COALESCE(SUM(COALESCE(c.bcms, 0)), 0) AS bcms
		FROM `tab{parent_dt}` p
		INNER JOIN `tab{child_dt}` c ON c.parent = p.name
		WHERE {where_sql}
		GROUP BY c.asset_name_shoval
		""",
		params,
		as_dict=True,
	)

	return {r["excavator"]: flt(r["bcms"]) for r in rows if r.get("excavator")}
