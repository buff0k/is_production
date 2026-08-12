// Copyright (c) 2026, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Diesel Receipt Site Analyses"] = {
	filters: [
		{
			fieldname: "date_from",
			label: __("Date From"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "date_to",
			label: __("Date To"),
			fieldtype: "Date",
			default: frappe.datetime.month_end(),
			reqd: 1,
		},
		{
			fieldname: "site",
			label: __("Site"),
			fieldtype: "Link",
			options: "Location",
		},
		{
			fieldname: "diesel_bowsers",
			label: __("Diesel Bowsers"),
			fieldtype: "MultiSelectList",
			description: __("Selecting bowsers automatically shows diesel taken from Main Tank or Bulk Tank."),
			get_data(txt) {
				const site =
					frappe.query_report.get_filter_value("site");

				const filters = {
					asset_category: "Diesel Bowsers",
				};

				if (site) {
					filters.location = site;
				}

				return frappe.db.get_link_options(
					"Asset",
					txt,
					filters
				);
			},
		},
		{
			fieldname: "group_by",
			label: __("Group By"),
			fieldtype: "Select",
			options: [
				"Site",
				"Diesel Bowser/Plant",
				"Receipt Tank",
				"Operator",
			],
			default: "Site",
			reqd: 1,
		},
		{
			fieldname: "view_mode",
			label: __("View Mode"),
			fieldtype: "Select",
			options: [
				"Totals and Details",
				"Totals Only",
				"Details Only",
			],
			default: "Totals and Details",
			reqd: 1,
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(
			value,
			row,
			column,
			data
		);

		if (data && data.row_type === "total") {
			value = `<strong>${value}</strong>`;
		}

		return value;
	},
};
