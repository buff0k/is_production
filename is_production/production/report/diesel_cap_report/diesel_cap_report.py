# Copyright (c) 2026, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

from __future__ import annotations

from datetime import datetime, date

import frappe
from frappe import _
from frappe.utils import getdate


def execute(filters: dict | None = None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	start_date = getdate(filters.start_date)
	end_date = getdate(filters.end_date)
	site = filters.get("site")

	columns = get_columns()

	production_rows = get_production_totals_by_site_and_date(start_date, end_date, site)
	survey_map = get_latest_survey_by_site(end_date, site)
	diesel_map = get_diesel_totals_by_site(start_date, end_date, site)

	production_map: dict[str, dict[date, float]] = {}
	for row in production_rows:
		row_site = row.get("site")
		row_date = getdate(row.get("prod_date"))
		total_bcm = row.get("total_bcm") or 0

		if not row_site:
			continue

		if row_site not in production_map:
			production_map[row_site] = {}

		production_map[row_site][row_date] = total_bcm

	if site:
		sites = [site]
	else:
		sites = sorted(set(production_map.keys()) | set(diesel_map.keys()))

	data = []
	for row_site in sites:
		site_daily_totals = production_map.get(row_site, {})
		survey_info = survey_map.get(row_site)

		survey_base_bcm = 0
		hourly_after_survey_bcm = 0
		survey_date_used = None

		if survey_info:
			survey_dt = survey_info["survey_date"]
			if start_date <= survey_dt <= end_date:
				survey_base_bcm = (survey_info.get("total_ts_bcm") or 0) + (survey_info.get("total_dozing_bcm") or 0)
				hourly_after_survey_bcm = sum(
					value for prod_dt, value in site_daily_totals.items() if prod_dt > survey_dt
				)
				actual_bcm = survey_base_bcm + hourly_after_survey_bcm
				survey_date_used = survey_info.get("survey_datetime")
			else:
				actual_bcm = sum(site_daily_totals.values())
				hourly_after_survey_bcm = actual_bcm
		else:
			actual_bcm = sum(site_daily_totals.values())
			hourly_after_survey_bcm = actual_bcm

		total_diesel_litres = diesel_map.get(row_site, 0)
		diesel_cap = (total_diesel_litres / actual_bcm) if actual_bcm else 0

		data.append(
			{
				"site": row_site,
				"start_date": start_date,
				"end_date": end_date,
				"survey_base_bcm": survey_base_bcm,
				"hourly_after_survey_bcm": hourly_after_survey_bcm,
				"actual_bcm": actual_bcm,
				"total_diesel_litres": total_diesel_litres,
				"diesel_cap": diesel_cap,
				"survey_date_used": survey_date_used,
			}
		)

	return columns, data


def validate_filters(filters):
	if not filters.get("start_date"):
		frappe.throw(_("Start Date is required"))

	if not filters.get("end_date"):
		frappe.throw(_("End Date is required"))

	start_date = getdate(filters.start_date)
	end_date = getdate(filters.end_date)

	if start_date > end_date:
		frappe.throw(_("Start Date cannot be after End Date"))


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Site"),
			"fieldname": "site",
			"fieldtype": "Link",
			"options": "Location",
			"width": 180,
		},
		{
			"label": _("Start Date"),
			"fieldname": "start_date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("End Date"),
			"fieldname": "end_date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Survey Base BCM"),
			"fieldname": "survey_base_bcm",
			"fieldtype": "Float",
			"precision": 2,
			"width": 140,
		},
		{
			"label": _("Hourly BCM After Survey"),
			"fieldname": "hourly_after_survey_bcm",
			"fieldtype": "Float",
			"precision": 2,
			"width": 170,
		},
		{
			"label": _("Actual BCM's"),
			"fieldname": "actual_bcm",
			"fieldtype": "Float",
			"precision": 2,
			"width": 130,
		},
		{
			"label": _("Total Diesel Litres"),
			"fieldname": "total_diesel_litres",
			"fieldtype": "Float",
			"precision": 1,
			"width": 150,
		},
		{
			"label": _("Diesel Cap"),
			"fieldname": "diesel_cap",
			"fieldtype": "Float",
			"precision": 2,
			"width": 120,
		},
		{
			"label": _("Survey Date Used"),
			"fieldname": "survey_date_used",
			"fieldtype": "Datetime",
			"width": 160,
		},
	]


def get_production_totals_by_site_and_date(start_date, end_date, site=None) -> list[dict]:
	conditions = [
		"hp.docstatus < 2",
		"hp.prod_date BETWEEN %(start_date)s AND %(end_date)s",
	]
	values = {
		"start_date": start_date,
		"end_date": end_date,
	}

	if site:
		conditions.append("hp.location = %(site)s")
		values["site"] = site

	where_clause = " AND ".join(conditions)

	return frappe.db.sql(
		f"""
		SELECT
			hp.location AS site,
			hp.prod_date AS prod_date,
			SUM(COALESCE(hp.total_ts_bcm, 0) + COALESCE(hp.total_dozing_bcm, 0)) AS total_bcm
		FROM `tabHourly Production` hp
		WHERE {where_clause}
		GROUP BY hp.location, hp.prod_date
		ORDER BY hp.location, hp.prod_date
		""",
		values,
		as_dict=True,
	)


def get_latest_survey_by_site(end_date, site=None) -> dict[str, dict]:
	values = {
		"end_datetime": f"{end_date} 23:59:59",
	}

	site_filter_sub = ""
	site_filter_outer = ""
	if site:
		site_filter_sub = " AND location = %(site)s"
		site_filter_outer = " AND s.location = %(site)s"
		values["site"] = site

	rows = frappe.db.sql(
		f"""
		SELECT
			s.location,
			s.last_production_shift_start_date,
			COALESCE(s.total_ts_bcm, 0) AS total_ts_bcm,
			COALESCE(s.total_dozing_bcm, 0) AS total_dozing_bcm
		FROM `tabSurvey` s
		INNER JOIN (
			SELECT
				location,
				MAX(last_production_shift_start_date) AS max_survey_dt
			FROM `tabSurvey`
			WHERE last_production_shift_start_date <= %(end_datetime)s
			{site_filter_sub}
			GROUP BY location
		) latest
			ON latest.location = s.location
			AND latest.max_survey_dt = s.last_production_shift_start_date
		WHERE 1=1
		{site_filter_outer}
		""",
		values,
		as_dict=True,
	)

	out = {}
	for row in rows:
		row_site = row.get("location")
		survey_datetime = row.get("last_production_shift_start_date")
		if not row_site or not survey_datetime:
			continue

		if isinstance(survey_datetime, datetime):
			survey_date = survey_datetime.date()
		else:
			survey_date = getdate(survey_datetime)

		out[row_site] = {
			"survey_datetime": survey_datetime,
			"survey_date": survey_date,
			"total_ts_bcm": row.get("total_ts_bcm") or 0,
			"total_dozing_bcm": row.get("total_dozing_bcm") or 0,
		}

	return out


def get_diesel_totals_by_site(start_date, end_date, site=None) -> dict[str, float]:
	conditions = [
		"dds.docstatus = 1",
		"dds.daily_sheet_date BETWEEN %(start_date)s AND %(end_date)s",
	]
	values = {
		"start_date": start_date,
		"end_date": end_date,
	}

	if site:
		conditions.append("dds.location = %(site)s")
		values["site"] = site

	where_clause = " AND ".join(conditions)

	rows = frappe.db.sql(
		f"""
		SELECT
			dds.location AS site,
			SUM(COALESCE(dds.litres_issued_equipment, 0)) AS total_diesel_litres
		FROM `tabDaily Diesel Sheet` dds
		WHERE {where_clause}
		GROUP BY dds.location
		ORDER BY dds.location
		""",
		values,
		as_dict=True,
	)

	return {
		row["site"]: row.get("total_diesel_litres") or 0
		for row in rows
		if row.get("site")
	}