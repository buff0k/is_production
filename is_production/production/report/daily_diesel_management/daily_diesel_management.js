// Copyright (c) 2026, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Daily Diesel Management"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("Open Start Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("Close Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "site",
			label: __("Site"),
			fieldtype: "Link",
			options: "Location",
			on_change() {
				refresh_after_parent_filter_change();
			},
		},
		{
			fieldname: "asset_category",
			label: __("Asset Category"),
			fieldtype: "Link",
			options: "Asset Category",
			on_change() {
				refresh_after_parent_filter_change();
			},
		},
		{
			fieldname: "fleet_number",
			label: __("Fleet Number"),
			fieldtype: "Link",
			options: "Asset",
			get_query() {
				const filters = {};
				const site = frappe.query_report.get_filter_value("site");
				const asset_category = frappe.query_report.get_filter_value("asset_category");

				if (site) {
					filters.location = site;
				}

				if (asset_category) {
					filters.asset_category = asset_category;
				}

				return { filters };
			},
		},
	],

	formatter(value, row, column, data, default_formatter) {
		const formatted_value = default_formatter(value, row, column, data);

		if (column.fieldname === "daily_total") {
			return `<strong>${formatted_value}</strong>`;
		}

		if (column.fieldname && column.fieldname.startsWith("fleet_") && Number(value) > 0) {
			return `<span style="color: #b85c00; font-weight: 600;">${formatted_value}</span>`;
		}

		return formatted_value;
	},
};


function refresh_after_parent_filter_change() {
	const current_fleet = frappe.query_report.get_filter_value("fleet_number");

	if (current_fleet) {
		frappe.query_report.set_filter_value("fleet_number", "");
		return;
	}

	frappe.query_report.refresh();
}

