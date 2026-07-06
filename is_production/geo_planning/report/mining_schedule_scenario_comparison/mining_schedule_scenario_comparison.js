// Copyright (c) 2026, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Mining Schedule Scenario Comparison"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1)
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today()
		},
		{
			fieldname: "geo_project",
			label: __("Geo Project"),
			fieldtype: "Link",
			options: "Geo Project"
		},
		{
			fieldname: "geo_pit_layout",
			label: __("Geo Pit Layout"),
			fieldtype: "Link",
			options: "Geo Pit Layout",
			get_query() {
				const geo_project = frappe.query_report.get_filter_value("geo_project");

				if (!geo_project) {
					return {};
				}

				return {
					filters: {
						geo_project: geo_project
					}
				};
			}
		},
		{
			fieldname: "mining_schedule_selection",
			label: __("Source Selection"),
			fieldtype: "Link",
			options: "Mining Schedule Selection",
			get_query() {
				const geo_project = frappe.query_report.get_filter_value("geo_project");
				const geo_pit_layout = frappe.query_report.get_filter_value("geo_pit_layout");

				const filters = {};

				if (geo_project) {
					filters.geo_project = geo_project;
				}

				if (geo_pit_layout) {
					filters.geo_pit_layout = geo_pit_layout;
				}

				return {
					filters: filters
				};
			}
		},
		{
			fieldname: "schedule_status",
			label: __("Schedule Status"),
			fieldtype: "Select",
			options: "\nDraft\nGenerated\nReviewed\nApproved\nCancelled"
		},
		{
			fieldname: "rule_parse_status",
			label: __("Rule Parse Status"),
			fieldtype: "Select",
			options: "\nNot Parsed\nParsed\nWarning\nError\nApproved"
		},
		{
			fieldname: "engine_run_status",
			label: __("Engine Run Status"),
			fieldtype: "Select",
			options: "\nQueued\nRunning\nComplete\nFailed\nCancelled\nNo Run"
		},
		{
			fieldname: "engine_mode",
			label: __("Engine Mode"),
			fieldtype: "Select",
			options: "\nRule Based\nSimulation\nOptimised"
		},
		{
			fieldname: "rule_set",
			label: __("Rule Set"),
			fieldtype: "Link",
			options: "Mining Schedule Rule Set"
		},
		{
			fieldname: "show_only_with_runs",
			label: __("Only Scenarios With Engine Runs"),
			fieldtype: "Check",
			default: 0
		},
		{
			fieldname: "show_only_with_warnings",
			label: __("Only Scenarios With Warnings"),
			fieldtype: "Check",
			default: 0
		},
		{
			fieldname: "show_only_with_errors",
			label: __("Only Scenarios With Errors"),
			fieldtype: "Check",
			default: 0
		}
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (!data) {
			return value;
		}

		if (column.fieldname === "schedule_status") {
			if (data.schedule_status === "Approved") {
				value = `<span class="indicator-pill green">${value}</span>`;
			} else if (data.schedule_status === "Reviewed") {
				value = `<span class="indicator-pill purple">${value}</span>`;
			} else if (data.schedule_status === "Generated") {
				value = `<span class="indicator-pill blue">${value}</span>`;
			} else if (data.schedule_status === "Cancelled") {
				value = `<span class="indicator-pill red">${value}</span>`;
			} else {
				value = `<span class="indicator-pill orange">${value}</span>`;
			}
		}

		if (column.fieldname === "run_status") {
			if (data.run_status === "Complete") {
				value = `<span class="indicator-pill green">${value}</span>`;
			} else if (data.run_status === "Failed") {
				value = `<span class="indicator-pill red">${value}</span>`;
			} else if (data.run_status === "No Run") {
				value = `<span class="indicator-pill gray">${value}</span>`;
			} else {
				value = `<span class="indicator-pill orange">${value}</span>`;
			}
		}

		if (column.fieldname === "warnings" && cint(data.warnings) > 0) {
			value = `<span class="indicator-pill orange">${value}</span>`;
		}

		if (column.fieldname === "errors" && cint(data.errors) > 0) {
			value = `<span class="indicator-pill red">${value}</span>`;
		}

		if (column.fieldname === "blocked_tasks" && cint(data.blocked_tasks) > 0) {
			value = `<span class="indicator-pill red">${value}</span>`;
		}

		if (column.fieldname === "pending_tasks" && cint(data.pending_tasks) > 0) {
			value = `<span class="indicator-pill orange">${value}</span>`;
		}

		return value;
	}
};