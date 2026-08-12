# Copyright (c) 2026, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

from collections import OrderedDict

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate


GROUP_FIELDS = {
	"Site": (
		"location",
		_("Site"),
	),
	"Diesel Bowser/Plant": (
		"asset_name",
		_("Diesel Bowser/Plant"),
	),
	"Receipt Tank": (
		"diesel_receipt_tank",
		_("Receipt Tank"),
	),
	"Operator": (
		"employee_name",
		_("Operator"),
	),
}

VIEW_MODES = {
	"Totals and Details",
	"Totals Only",
	"Details Only",
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	columns = get_columns()
	receipts = get_receipts(filters)
	data = build_data(receipts, filters)
	report_summary = get_report_summary(receipts)
	chart = get_chart(receipts, filters)

	return (
		columns,
		data,
		None,
		chart,
		report_summary,
	)


def validate_filters(filters):
	if not filters.get("date_from"):
		frappe.throw(_("Date From is required."))

	if not filters.get("date_to"):
		frappe.throw(_("Date To is required."))

	filters.date_from = getdate(filters.date_from)
	filters.date_to = getdate(filters.date_to)

	if filters.date_from > filters.date_to:
		frappe.throw(
			_("Date From cannot be after Date To.")
		)

	filters.group_by = (
		filters.get("group_by") or "Site"
	)

	filters.view_mode = (
		filters.get("view_mode")
		or "Totals and Details"
	)

	if filters.group_by not in GROUP_FIELDS:
		frappe.throw(
			_("Invalid Group By selection.")
		)

	if filters.view_mode not in VIEW_MODES:
		frappe.throw(
			_("Invalid View Mode selection.")
		)


def get_columns():
	return [
		{
			"fieldname": "analysis_group",
			"label": _("Analysis Group"),
			"fieldtype": "Data",
			"width": 190,
			"hidden": 1,
		},
		{
			"fieldname": "location",
			"label": _("Site"),
			"fieldtype": "Link",
			"options": "Location",
			"width": 140,
		},
		{
			"fieldname": "receipt_datetime",
			"label": _("Receipt Date & Time"),
			"fieldtype": "Datetime",
			"width": 155,
		},
		{
			"fieldname": "diesel_receipt",
			"label": _("Receipt Number"),
			"fieldtype": "Data",
			"width": 125,
		},
		{
			"fieldname": "receipt_document",
			"label": _("Document"),
			"fieldtype": "Link",
			"options": "Diesel Receipt",
			"width": 170,
		},
		{
			"fieldname": "asset_name",
			"label": _("Diesel Bowser/Plant"),
			"fieldtype": "Link",
			"options": "Asset",
			"width": 150,
		},
		{
			"fieldname": "diesel_receipt_tank",
			"label": _("Receipt Tank"),
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"fieldname": "opening_reading",
			"label": _("Opening Reading (L)"),
			"fieldtype": "Float",
			"precision": 1,
			"width": 145,
		},
		{
			"fieldname": "closing_reading",
			"label": _("Closing Reading (L)"),
			"fieldtype": "Float",
			"precision": 1,
			"width": 145,
		},
		{
			"fieldname": "litres_received",
			"label": _("Litres Received"),
			"fieldtype": "Float",
			"precision": 1,
			"width": 130,
		},
		{
			"fieldname": "status",
			"label": _("Status"),
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"fieldname": "employee_name",
			"label": _("Operator ID"),
			"fieldtype": "Link",
			"options": "Employee",
			"width": 120,
		},
		{
			"fieldname": "operator_name",
			"label": _("Operator Name"),
			"fieldtype": "Data",
			"width": 160,
		},
	]


def get_receipts(filters):
	conditions = [
		"dr.docstatus IN (0, 1)",
		(
			"dr.date_time_diesel_receipt "
			">= %(date_from)s"
		),
		(
			"dr.date_time_diesel_receipt "
			"< %(date_to_exclusive)s"
		),
	]

	parameters = {
		"date_from": filters.date_from,
		"date_to_exclusive": add_days(
			filters.date_to,
			1,
		),
	}

	if filters.get("site"):
		conditions.append(
			"dr.location = %(site)s"
		)
		parameters["site"] = filters.site

	diesel_bowsers = (
		filters.get("diesel_bowsers") or []
	)

	if isinstance(diesel_bowsers, str):
		try:
			diesel_bowsers = frappe.parse_json(
				diesel_bowsers
			)
		except (TypeError, ValueError):
			diesel_bowsers = [
				value.strip()
				for value in diesel_bowsers.split(",")
				if value.strip()
			]


	if diesel_bowsers:
		conditions.append(
			"dr.asset_name IN %(diesel_bowsers)s"
		)
		parameters["diesel_bowsers"] = tuple(
			diesel_bowsers
		)

		# Selected bowsers show diesel supplied from
		# either a Main Tank or a Bulk Tank.
		conditions.append(
			"("
			"dr.diesel_receipt_tank "
			"LIKE %(main_tank_pattern)s "
			"OR "
			"dr.diesel_receipt_tank "
			"LIKE %(bulk_tank_pattern)s"
			")"
		)

		parameters["main_tank_pattern"] = (
			"%Main Tank%"
		)

		parameters["bulk_tank_pattern"] = (
			"%Bulk Tank%"
		)


	return frappe.db.sql(
		f"""
			SELECT
				dr.name AS receipt_document,
				dr.docstatus,
				dr.location,
				dr.date_time_diesel_receipt
					AS receipt_datetime,
				dr.diesel_receipt,
				dr.asset_name,
				CASE
					WHEN dr.diesel_receipt_tank
						LIKE '%%Main Tank%%'
					THEN 'Main Tank'

					WHEN dr.diesel_receipt_tank
						LIKE '%%Bulk Tank%%'
					THEN 'Bulk Tank'

					ELSE dr.diesel_receipt_tank
				END AS diesel_receipt_tank,
				dr.open_reading_ltrs
					AS opening_reading,
				dr.close_reading_ltrs
					AS closing_reading,
				dr.litres_dispensed
					AS litres_received,
				dr.employee_name,
				dr.diesel_operator_name
					AS operator_name
			FROM `tabDiesel Receipt` dr
			WHERE {" AND ".join(conditions)}
			ORDER BY
				dr.date_time_diesel_receipt,
				dr.name
		""",
		parameters,
		as_dict=True,
	)


def build_data(receipts, filters):
	group_field, group_label = (
		GROUP_FIELDS[filters.group_by]
	)

	groups = OrderedDict()

	for receipt in receipts:
		group_value = (
			receipt.get(group_field)
			or _("Not Set")
		)

		groups.setdefault(
			group_value,
			[],
		).append(receipt)

	show_totals = filters.view_mode in {
		"Totals and Details",
		"Totals Only",
	}

	show_details = filters.view_mode in {
		"Totals and Details",
		"Details Only",
	}

	data = []

	for group_value, group_receipts in groups.items():
		if show_totals:
			group_total = sum(
				flt(row.litres_received)
				for row in group_receipts
			)

			data.append(
				{
					"analysis_group": _(
						"{0}: {1}"
					).format(
						group_label,
						group_value,
					),
					"location": (
						group_value
						if filters.group_by
						== "Site"
						else None
					),
					"litres_received": group_total,
					"status": None,
					"row_type": "total",
					"indent": 0,
				}
			)

		if show_details:
			for receipt in group_receipts:
				detail = dict(receipt)

				detail.update(
					{
						"analysis_group": (
							group_value
						),
						"status": (
							_("Submitted")
							if receipt.docstatus == 1
							else _("Draft")
						),
						"row_type": "detail",
						"indent": (
							1
							if show_totals
							else 0
						),
					}
				)

				data.append(detail)

	return data


def get_report_summary(receipts):
	total_litres = sum(
		flt(row.litres_received)
		for row in receipts
	)

	total_receipts = len(receipts)

	total_sites = len(
		{
			row.location
			for row in receipts
			if row.location
		}
	)

	average_receipt = (
		total_litres / total_receipts
		if total_receipts
		else 0
	)

	return [
		{
			"value": total_litres,
			"indicator": "Blue",
			"label": _("Total Litres Received"),
			"datatype": "Float",
			"precision": 1,
		},
		{
			"value": total_receipts,
			"indicator": "Green",
			"label": _("Total Receipts"),
			"datatype": "Int",
		},
		{
			"value": total_sites,
			"indicator": "Orange",
			"label": _("Sites"),
			"datatype": "Int",
		},
		{
			"value": average_receipt,
			"indicator": "Grey",
			"label": _(
				"Average Litres per Receipt"
			),
			"datatype": "Float",
			"precision": 1,
		},
	]


def get_chart(receipts, filters):
	group_field, group_label = (
		GROUP_FIELDS[filters.group_by]
	)

	group_totals = OrderedDict()

	for receipt in receipts:
		group_value = (
			receipt.get(group_field)
			or _("Not Set")
		)

		group_totals[group_value] = (
			group_totals.get(group_value, 0)
			+ flt(receipt.litres_received)
		)

	if not group_totals:
		return None

	return {
		"data": {
			"labels": list(group_totals.keys()),
			"datasets": [
				{
					"name": _(
						"Litres Received by {0}"
					).format(group_label),
					"values": list(
						group_totals.values()
					),
				}
			],
		},
		"type": "bar",
		"colors": ["#2490ef"],
		"barOptions": {
			"spaceRatio": 0.35,
		},
		"height": 280,
	}
