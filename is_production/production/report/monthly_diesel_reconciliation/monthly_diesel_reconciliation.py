# Copyright (c) 2026, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, get_first_day, get_last_day, getdate


DIESEL_PARENT = "Daily Diesel Sheet"
DIESEL_CHILD = "Daily Diesel Entries"
DIESEL_PARENTFIELD = "daily_diesel_entries"

HOURS_PARENT = "Pre-Use Hours"
HOURS_CHILD = "Pre-use Assets"
HOURS_PARENTFIELD = "pre_use_assets"

RATE_DOCTYPE = "OEM Diesel Burn Rate"


def execute(filters: dict | None = None):
	filters = frappe._dict(filters or {})

	_validate_filters(filters)
	_check_permissions()

	period = _get_period(filters.month)

	diesel_sheets = _get_permitted_parents(
		DIESEL_PARENT,
		"daily_sheet_date",
		filters.site,
		period.start_date,
		period.end_date,
	)

	hours_sheets = _get_permitted_parents(
		HOURS_PARENT,
		"shift_date",
		filters.site,
		period.start_date,
		period.end_date,
	)

	diesel_by_asset = _get_diesel_by_asset(diesel_sheets)
	hours_by_asset = _get_hours_by_asset(hours_sheets)

	assets = _get_assets(
		filters.site,
		diesel_by_asset,
		hours_by_asset,
	)

	models = sorted(
		{
			asset.get("item_code")
			for asset in assets.values()
			if asset.get("item_code")
		}
	)

	rates = _get_effective_rates(
		models,
		period.end_date,
	)

	capture_days = _get_capture_days(
		diesel_sheets,
		"daily_sheet_date",
	)

	asset_rows = _build_asset_rows(
		assets,
		diesel_by_asset,
		hours_by_asset,
		rates,
		capture_days,
	)

	data = _add_category_totals(
		asset_rows,
		capture_days,
	)

	columns = _get_columns()
	chart = _get_chart(asset_rows)
	summary = _get_summary(asset_rows)

	message = _get_message(
		diesel_sheets,
		hours_sheets,
		asset_rows,
	)

	return columns, data, message, chart, summary


def _validate_filters(filters: frappe._dict) -> None:
	if not filters.get("site"):
		frappe.throw(_("Site is required."))

	if not filters.get("month"):
		frappe.throw(_("Month is required."))

	filters.month = getdate(filters.month)


def _check_permissions() -> None:
	for doctype in (
		DIESEL_PARENT,
		HOURS_PARENT,
		"Asset",
		RATE_DOCTYPE,
	):
		if not frappe.has_permission(doctype, "read"):
			frappe.throw(
				_("You do not have permission to read {0}.").format(
					doctype
				),
				frappe.PermissionError,
			)


def _get_period(month) -> frappe._dict:
	month = getdate(month)

	return frappe._dict(
		start_date=get_first_day(month),
		end_date=get_last_day(month),
	)


def _get_permitted_parents(
	doctype: str,
	date_field: str,
	site: str,
	start_date,
	end_date,
) -> list[frappe._dict]:
	"""Get submitted parent documents while respecting user permissions."""

	return frappe.get_list(
		doctype,
		filters={
			"docstatus": 1,
			"location": site,
			date_field: [
				"between",
				[start_date, end_date],
			],
		},
		fields=[
			"name",
			date_field,
		],
		order_by=f"{date_field} asc",
		limit_page_length=0,
	)


def _get_diesel_by_asset(
	sheets: list[frappe._dict],
) -> dict[str, float]:
	if not sheets:
		return {}

	rows = frappe.db.sql(
		f"""
			select
				entry.asset_name,
				sum(
					coalesce(entry.litres_issued, 0)
				) as litres_issued
			from `tab{DIESEL_CHILD}` entry
			where entry.parent in %(parents)s
				and entry.parenttype = %(parenttype)s
				and entry.parentfield = %(parentfield)s
				and coalesce(entry.asset_name, '') != ''
			group by entry.asset_name
		""",
		values={
			"parents": tuple(
				sheet.name for sheet in sheets
			),
			"parenttype": DIESEL_PARENT,
			"parentfield": DIESEL_PARENTFIELD,
		},
		as_dict=True,
	)

	return {
		row.asset_name: flt(row.litres_issued)
		for row in rows
	}


def _get_hours_by_asset(
	sheets: list[frappe._dict],
) -> dict[str, frappe._dict]:
	if not sheets:
		return {}

	rows = frappe.db.sql(
		f"""
			select
				entry.asset_name,
				max(
					coalesce(entry.item_name, '')
				) as model,
				max(
					coalesce(entry.asset_category, '')
				) as asset_category,
				sum(
					coalesce(entry.working_hours, 0)
				) as working_hours
			from `tab{HOURS_CHILD}` entry
			where entry.parent in %(parents)s
				and entry.parenttype = %(parenttype)s
				and entry.parentfield = %(parentfield)s
				and coalesce(entry.asset_name, '') != ''
			group by entry.asset_name
		""",
		values={
			"parents": tuple(
				sheet.name for sheet in sheets
			),
			"parenttype": HOURS_PARENT,
			"parentfield": HOURS_PARENTFIELD,
		},
		as_dict=True,
	)

	return {
		row.asset_name: row
		for row in rows
	}


def _get_assets(
	site: str,
	diesel_by_asset: dict[str, float],
	hours_by_asset: dict[str, frappe._dict],
) -> dict[str, frappe._dict]:
	assets: dict[str, frappe._dict] = {}

	site_assets = frappe.get_list(
		"Asset",
		filters={
			"docstatus": 1,
			"location": site,
		},
		fields=[
			"name",
			"asset_name",
			"asset_category",
			"item_code",
		],
		order_by="asset_category asc, name asc",
		limit_page_length=0,
	)

	for asset in site_assets:
		assets[asset.name] = asset

	transaction_assets = (
		set(diesel_by_asset)
		| set(hours_by_asset)
	)

	missing_assets = sorted(
		transaction_assets - set(assets)
	)

	if missing_assets:
		additional_assets = frappe.get_list(
			"Asset",
			filters={
				"docstatus": 1,
				"name": ["in", missing_assets],
			},
			fields=[
				"name",
				"asset_name",
				"asset_category",
				"item_code",
			],
			limit_page_length=0,
		)

		for asset in additional_assets:
			assets[asset.name] = asset

	return assets


def _get_effective_rates(
	models: list[str],
	month_end,
) -> dict[str, frappe._dict]:
	if not models:
		return {}

	rows = frappe.db.sql(
		f"""
			select
				rate.model,
				rate.burn_rate_lph,
				rate.effective_from
			from `tab{RATE_DOCTYPE}` rate
			inner join (
				select
					model,
					max(effective_from) as effective_from
				from `tab{RATE_DOCTYPE}`
				where model in %(models)s
					and effective_from <= %(month_end)s
				group by model
			) latest
				on latest.model = rate.model
				and latest.effective_from = rate.effective_from
			where rate.name = (
				select duplicate.name
				from `tab{RATE_DOCTYPE}` duplicate
				where duplicate.model = rate.model
					and duplicate.effective_from =
						rate.effective_from
				order by
					duplicate.modified desc,
					duplicate.name desc
				limit 1
			)
		""",
		values={
			"models": tuple(models),
			"month_end": month_end,
		},
		as_dict=True,
	)

	return {
		row.model: row
		for row in rows
	}


def _get_capture_days(
	sheets: list[frappe._dict],
	date_field: str,
) -> int:
	return len(
		{
			getdate(sheet.get(date_field))
			for sheet in sheets
			if sheet.get(date_field)
		}
	)


def _build_asset_rows(
	assets: dict[str, frappe._dict],
	diesel_by_asset: dict[str, float],
	hours_by_asset: dict[str, frappe._dict],
	rates: dict[str, frappe._dict],
	capture_days: int,
) -> list[dict]:
	rows: list[dict] = []

	for asset_name, asset in assets.items():
		hours_row = (
			hours_by_asset.get(asset_name)
			or frappe._dict()
		)

		asset_model = (
			asset.get("item_code")
			or ""
		)

		rate_row = (
			rates.get(asset_model)
			or frappe._dict()
		)

		litres = flt(
			diesel_by_asset.get(asset_name),
			2,
		)

		working_hours = flt(
			hours_row.get("working_hours"),
			2,
		)

		actual_lph = (
			flt(litres / working_hours, 2)
			if working_hours > 0
			else None
		)

		oem_rate = (
			flt(
				rate_row.get("burn_rate_lph"),
				2,
			)
			if rate_row.get("burn_rate_lph")
			else None
		)

		variance = (
			flt(oem_rate - actual_lph, 2)
			if (
				oem_rate is not None
				and actual_lph is not None
			)
			else None
		)

		model = (
			hours_row.get("model")
			or asset_model
			or asset.get("asset_name")
			or ""
		)

		asset_category = (
			hours_row.get("asset_category")
			or asset.get("asset_category")
			or _("Uncategorised")
		)

		rows.append(
			{
				"asset_category": asset_category,
				"fleet_number": asset_name,
				"model": model,
				"quantity": 1,
				"litres_mtd": litres,
				"average_litres_day": (
					flt(
						litres / capture_days,
						2,
					)
					if capture_days
					else 0
				),
				"mtd_hours": working_hours,
				"actual_lph": actual_lph,
				"oem_burn_rate": oem_rate,
				"rate_effective_from": (
					rate_row.get(
						"effective_from"
					)
				),
				"variance": variance,
			}
		)

	rows.sort(
		key=lambda row: (
			(
				row["asset_category"]
				or ""
			).lower(),
			row["fleet_number"].lower(),
		)
	)

	return rows


def _add_category_totals(
	asset_rows: list[dict],
	capture_days: int,
) -> list[dict]:
	grouped: defaultdict[str, list[dict]] = (
		defaultdict(list)
	)

	for row in asset_rows:
		grouped[
			row["asset_category"]
		].append(row)

	data: list[dict] = []

	for category in sorted(
		grouped,
		key=lambda value: (
			value or ""
		).lower(),
	):
		category_rows = grouped[category]

		data.extend(category_rows)

		data.append(
			_total_row(
				category_rows,
				capture_days,
				category=category,
			)
		)

	if asset_rows:
		data.append(
			_total_row(
				asset_rows,
				capture_days,
				grand_total=True,
			)
		)

	return data


def _total_row(
	rows: list[dict],
	capture_days: int,
	category: str | None = None,
	grand_total: bool = False,
) -> dict:
	litres = flt(
		sum(
			flt(row.get("litres_mtd"))
			for row in rows
		),
		2,
	)

	hours = flt(
		sum(
			flt(row.get("mtd_hours"))
			for row in rows
		),
		2,
	)

	return {
		"asset_category": category or "",
		"fleet_number": None,
		"model": (
			_("Grand Total")
			if grand_total
			else _("{0} Total").format(category)
		),
		"quantity": len(rows),
		"litres_mtd": litres,
		"average_litres_day": (
			flt(litres / capture_days, 2)
			if capture_days
			else 0
		),
		"mtd_hours": hours,
		"actual_lph": (
			flt(litres / hours, 2)
			if hours > 0
			else None
		),
		"is_category_total": (
			0 if grand_total else 1
		),
		"is_grand_total": (
			1 if grand_total else 0
		),
	}


def _get_columns() -> list[dict]:
	return [
		{
			"fieldname": "asset_category",
			"label": _("Asset Category"),
			"fieldtype": "Link",
			"options": "Asset Category",
			"width": 145,
		},
		{
			"fieldname": "fleet_number",
			"label": _("Fleet Number"),
			"fieldtype": "Link",
			"options": "Asset",
			"width": 125,
		},
		{
			"fieldname": "model",
			"label": _("Model / Description"),
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"fieldname": "quantity",
			"label": _("Quantity"),
			"fieldtype": "Int",
			"width": 80,
		},
		{
			"fieldname": "litres_mtd",
			"label": _("Litres Consumed MTD"),
			"fieldtype": "Float",
			"precision": 2,
			"width": 145,
		},
		{
			"fieldname": "average_litres_day",
			"label": _("Average Litres/Day"),
			"fieldtype": "Float",
			"precision": 2,
			"width": 135,
		},
		{
			"fieldname": "mtd_hours",
			"label": _("MTD Working Hours"),
			"fieldtype": "Float",
			"precision": 2,
			"width": 135,
		},
		{
			"fieldname": "actual_lph",
			"label": _("Actual Litres/Hour"),
			"fieldtype": "Float",
			"precision": 2,
			"width": 135,
		},
		{
			"fieldname": "oem_burn_rate",
			"label": _("OEM Burn Rate"),
			"fieldtype": "Float",
			"precision": 2,
			"width": 120,
		},
		{
			"fieldname": "rate_effective_from",
			"label": _("Rate Effective From"),
			"fieldtype": "Date",
			"width": 125,
		},
		{
			"fieldname": "variance",
			"label": _("Variance"),
			"fieldtype": "Float",
			"precision": 2,
			"width": 100,
		},
	]


def _get_chart(
	asset_rows: list[dict],
) -> dict | None:
	if not asset_rows:
		return None

	category_litres: defaultdict[str, float] = (
		defaultdict(float)
	)

	for row in asset_rows:
		category_litres[
			row["asset_category"]
		] += flt(row["litres_mtd"])

	categories = sorted(
		category_litres,
		key=lambda value: (
			value or ""
		).lower(),
	)

	return {
		"data": {
			"labels": categories,
			"datasets": [
				{
					"name": _("Litres Consumed"),
					"values": [
						flt(
							category_litres[
								category
							],
							2,
						)
						for category in categories
					],
				}
			],
		},
		"type": "bar",
		"height": 280,
		"colors": ["#E67E22"],
	}


def _get_summary(
	asset_rows: list[dict],
) -> list[dict]:
	total_litres = flt(
		sum(
			flt(row["litres_mtd"])
			for row in asset_rows
		),
		2,
	)

	total_hours = flt(
		sum(
			flt(row["mtd_hours"])
			for row in asset_rows
		),
		2,
	)

	actual_lph = (
		flt(total_litres / total_hours, 2)
		if total_hours > 0
		else 0
	)

	return [
		{
			"value": total_litres,
			"indicator": "Blue",
			"label": _("Total Litres"),
			"datatype": "Float",
		},
		{
			"value": total_hours,
			"indicator": "Green",
			"label": _("MTD Working Hours"),
			"datatype": "Float",
		},
		{
			"value": len(asset_rows),
			"indicator": "Gray",
			"label": _("Machines"),
			"datatype": "Int",
		},
		{
			"value": actual_lph,
			"indicator": "Orange",
			"label": _("Actual Litres/Hour"),
			"datatype": "Float",
		},
	]


def _get_message(
	diesel_sheets: list[frappe._dict],
	hours_sheets: list[frappe._dict],
	asset_rows: list[dict],
) -> str | None:
	messages = []

	if not diesel_sheets:
		messages.append(
			_(
				"No submitted Daily Diesel Sheets "
				"were found."
			)
		)

	if not hours_sheets:
		messages.append(
			_(
				"No submitted Pre-Use Hours "
				"records were found."
			)
		)

	if not asset_rows:
		messages.append(
			_(
				"No Assets were found for the "
				"selected Site and Month."
			)
		)
	else:
		missing_rates = sum(
			1
			for row in asset_rows
			if row.get("oem_burn_rate") is None
		)

		if missing_rates:
			messages.append(
				_(
					"{0} machine(s) have no "
					"effective OEM diesel burn "
					"rate for this month."
				).format(missing_rates)
			)

	return " ".join(messages) or None