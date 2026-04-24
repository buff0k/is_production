// Copyright (c) 2026, Isambane Mining (Pty) Ltd
// Number of ADT's

frappe.query_reports["Number of ADT's"] = {
    filters: [
        {
            fieldname: "start_date",
            label: __("Start Date"),
            fieldtype: "Date",
            default: frappe.datetime.month_start()
        },
        {
            fieldname: "end_date",
            label: __("End Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today()
        },
        {
            fieldname: "site",
            label: __("Site"),
            fieldtype: "Link",
            options: "Location"
        },
        {
            fieldname: "shift",
            label: __("Shift"),
            fieldtype: "Select",
            options: "\nDay\nNight"
        }
    ],

    onload: function (report) {
        if (!report.get_filter_value("start_date")) {
            report.set_filter_value("start_date", frappe.datetime.month_start());
        }

        if (!report.get_filter_value("end_date")) {
            report.set_filter_value("end_date", frappe.datetime.get_today());
        }
    },

    formatter: function (value, row, column, data, default_formatter) {
        let formatted = default_formatter(value, row, column, data);

        if (!data) return formatted;

        if (
            column.fieldname === "avg_used" ||
            column.fieldname === "avg_avail" ||
            column.fieldname === "report_date" ||
            column.fieldname === "day_name"
        ) {
            formatted = `<b>${formatted || 0}</b>`;
        }

        if (column.fieldname === "report_date" || column.fieldname === "day_name") {
            formatted = `<b>${value || ""}</b>`;
        }

        return formatted;
    }
};