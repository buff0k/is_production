# Copyright (c) 2026, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, flt, formatdate, getdate


PARENT_DOCTYPE = "Daily Diesel Sheet"
CHILD_DOCTYPE = "Daily Diesel Entries"
CHILD_TABLE_FIELD = "daily_diesel_entries"


def execute(filters: dict | None = None):
	"""Build an Excel-style daily diesel matrix.

	Each row represents one site and calendar date. Each dynamic machine column
	contains the total litres issued to that fleet number on that date. If more
	than one submitted sheet or shift exists for the same machine and date, the
	values are added together.
	"""
	filters = frappe._dict(filters or {})
	_validate_filters(filters)
	_check_permission()

	sheets = _get_permitted_sheets(filters)
	entries = _get_diesel_entries(filters, sheets)
	fleets = _get_fleet_columns(filters, entries)
	columns = _get_columns(fleets)
	data = _build_matrix(filters, sheets, entries, fleets)
	chart = _get_chart(filters, entries)
	summary = _get_report_summary(filters, entries)
	message = _get_message(sheets, entries)

	return columns, data, message, chart, summary


def _validate_filters(filters: frappe._dict) -> None:
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("Open Start Date and Close Date are required."))

	filters.from_date = getdate(filters.from_date)
	filters.to_date = getdate(filters.to_date)

	if filters.from_date > filters.to_date:
		frappe.throw(_("Open Start Date cannot be after Close Date."))


def _check_permission() -> None:
	if not frappe.has_permission(PARENT_DOCTYPE, "read"):
		frappe.throw(
			_("You do not have permission to read Daily Diesel Sheets."),
			frappe.PermissionError,
		)


def _get_permitted_sheets(filters: frappe._dict) -> list[frappe._dict]:
	"""Use get_list so normal DocType and User Permissions remain in force."""
	sheet_filters: dict = {
		"docstatus": 1,
		"daily_sheet_date": ["between", [filters.from_date, filters.to_date]],
	}

	if filters.get("site"):
		sheet_filters["location"] = filters.site

	return frappe.get_list(
		PARENT_DOCTYPE,
		filters=sheet_filters,
		fields=["name", "daily_sheet_date", "location"],
		order_by="daily_sheet_date asc, location asc",
		limit_page_length=0,
	)


def _get_diesel_entries(
	filters: frappe._dict,
	sheets: list[frappe._dict],
) -> list[frappe._dict]:
	if not sheets:
		return []

	conditions = [
		"sheet.name in %(sheet_names)s",
		"sheet.docstatus = 1",
		"entry.parenttype = %(parent_doctype)s",
		"entry.parentfield = %(parentfield)s",
		"coalesce(entry.asset_name, '') != ''",
	]
	values = {
		"sheet_names": tuple(sheet.name for sheet in sheets),
		"parent_doctype": PARENT_DOCTYPE,
		"parentfield": CHILD_TABLE_FIELD,
	}

	if filters.get("asset_category"):
		conditions.append("asset.asset_category = %(asset_category)s")
		values["asset_category"] = filters.asset_category

	if filters.get("fleet_number"):
		conditions.append("entry.asset_name = %(fleet_number)s")
		values["fleet_number"] = filters.fleet_number

	return frappe.db.sql(
		f"""
			select
				sheet.daily_sheet_date,
				sheet.location as site,
				entry.asset_name as fleet_number,
				max(coalesce(asset.asset_category, '')) as asset_category,
				sum(coalesce(entry.litres_issued, 0)) as litres_issued
			from `tab{PARENT_DOCTYPE}` sheet
			inner join `tab{CHILD_DOCTYPE}` entry
				on entry.parent = sheet.name
			left join `tabAsset` asset
				on asset.name = entry.asset_name
			where {" and ".join(conditions)}
			group by
				sheet.daily_sheet_date,
				sheet.location,
				entry.asset_name
			order by
				sheet.daily_sheet_date,
				sheet.location,
				asset_category,
				entry.asset_name
		""",
		values=values,
		as_dict=True,
	)


def _get_fleet_columns(
	filters: frappe._dict,
	entries: list[frappe._dict],
) -> list[frappe._dict]:
	by_fleet: dict[str, str] = {}

	for entry in entries:
		by_fleet[entry.fleet_number] = entry.asset_category or ""

	# Keep a specifically selected fleet visible even when it received no diesel
	# during the selected period.
	if filters.get("fleet_number") and filters.fleet_number not in by_fleet:
		asset_category = frappe.db.get_value(
			"Asset",
			filters.fleet_number,
			"asset_category",
		) or ""
		by_fleet[filters.fleet_number] = asset_category

	sorted_fleets = sorted(
		by_fleet.items(),
		key=lambda item: ((item[1] or "").lower(), item[0].lower()),
	)

	return [
		frappe._dict(
			fleet_number=fleet_number,
			asset_category=asset_category,
			fieldname=f"fleet_{index}",
		)
		for index, (fleet_number, asset_category) in enumerate(sorted_fleets, start=1)
	]


def _get_columns(fleets: list[frappe._dict]) -> list[dict]:
	columns: list[dict] = [
		{
			"fieldname": "daily_sheet_date",
			"label": _("Date"),
			"fieldtype": "Date",
			"width": 105,
		},
		{
			"fieldname": "day_name",
			"label": _("Day"),
			"fieldtype": "Data",
			"width": 75,
		},
		{
			"fieldname": "site",
			"label": _("Site"),
			"fieldtype": "Link",
			"options": "Location",
			"width": 120,
		},
	]

	for fleet in fleets:
		label = fleet.fleet_number
		if fleet.asset_category:
			label = _("{0} ({1})").format(fleet.fleet_number, fleet.asset_category)

		columns.append(
			{
				"fieldname": fleet.fieldname,
				"label": label,
				"fieldtype": "Float",
				"precision": 2,
				"width": 135,
			}
		)

	columns.append(
		{
			"fieldname": "daily_total",
			"label": _("Daily Total (L)"),
			"fieldtype": "Float",
			"precision": 2,
			"width": 125,
		}
	)

	return columns


def _build_matrix(
	filters: frappe._dict,
	sheets: list[frappe._dict],
	entries: list[frappe._dict],
	fleets: list[frappe._dict],
) -> list[dict]:
	if not sheets:
		return []

	fleet_fieldnames = {
		fleet.fleet_number: fleet.fieldname
		for fleet in fleets
	}
	issued_by_day: defaultdict[tuple, float] = defaultdict(float)

	for entry in entries:
		key = (
			entry.site or "",
			getdate(entry.daily_sheet_date),
			entry.fleet_number,
		)
		issued_by_day[key] += flt(entry.litres_issued)

	sites = sorted({sheet.location or "" for sheet in sheets})
	dates = _date_range(filters.from_date, filters.to_date)
	data: list[dict] = []

	for site in sites:
		for report_date in dates:
			row: dict = {
				"daily_sheet_date": report_date,
				"day_name": report_date.strftime("%a"),
				"site": site,
			}
			daily_total = 0.0

			for fleet_number, fieldname in fleet_fieldnames.items():
				litres = flt(issued_by_day.get((site, report_date, fleet_number)))
				row[fieldname] = litres if litres else None
				daily_total += litres

			row["daily_total"] = flt(daily_total, 2)
			data.append(row)

	return data


def _date_range(from_date, to_date) -> list:
	dates = []
	current_date = getdate(from_date)
	last_date = getdate(to_date)

	while current_date <= last_date:
		dates.append(current_date)
		current_date = add_days(current_date, 1)

	return dates


def _get_chart(filters: frappe._dict, entries: list[frappe._dict]) -> dict | None:
	if not entries:
		return None

	daily_totals: defaultdict = defaultdict(float)
	for entry in entries:
		daily_totals[getdate(entry.daily_sheet_date)] += flt(entry.litres_issued)

	dates = _date_range(filters.from_date, filters.to_date)
	return {
		"data": {
			"labels": [formatdate(report_date, "dd MMM") for report_date in dates],
			"datasets": [
				{
					"name": _("Litres Issued"),
					"values": [flt(daily_totals.get(report_date), 2) for report_date in dates],
				}
			],
		},
		"type": "line",
		"height": 260,
		"colors": ["#E67E22"],
	}


def _get_report_summary(
	filters: frappe._dict,
	entries: list[frappe._dict],
) -> list[dict]:
	total_litres = flt(sum(flt(entry.litres_issued) for entry in entries), 2)
	active_machines = len({entry.fleet_number for entry in entries})
	period_days = len(_date_range(filters.from_date, filters.to_date))
	average_per_day = flt(total_litres / period_days, 2) if period_days else 0

	return [
		{
			"value": total_litres,
			"indicator": "Blue",
			"label": _("Total Litres Issued"),
			"datatype": "Float",
		},
		{
			"value": active_machines,
			"indicator": "Green",
			"label": _("Active Machines"),
			"datatype": "Int",
		},
		{
			"value": period_days,
			"indicator": "Gray",
			"label": _("Days in Period"),
			"datatype": "Int",
		},
		{
			"value": average_per_day,
			"indicator": "Orange",
			"label": _("Average Litres per Day"),
			"datatype": "Float",
		},
	]


def _get_message(
	sheets: list[frappe._dict],
	entries: list[frappe._dict],
) -> str | None:
	if not sheets:
		return _("No submitted Daily Diesel Sheets were found for the selected filters.")

	if not entries:
		return _("Submitted sheets were found, but no matching equipment diesel entries were found.")

	return None

