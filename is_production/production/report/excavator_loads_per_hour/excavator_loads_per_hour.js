// Copyright (c) 2026, Isambane Mining (Pty) Ltd
// Excavator BCM Per Hour
//
// This report shows total converted BCM per day per hour.
// It sums all excavators together into one hourly value per day.

frappe.query_reports["Excavator Loads Per Hour"] = {
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
        if (value !== null && value !== undefined && value !== "" && is_numeric_column(column)) {
            value = parseInt(value || 0, 10);
        }

        let formatted = default_formatter(value, row, column, data);

        if (!data) return formatted;

        if (
            column.fieldname === "report_date" ||
            column.fieldname === "day_name" ||
            column.fieldname === "total_bcm" ||
            column.fieldname === "avg_bcm_per_hour"
        ) {
            formatted = `<b>${formatted || ""}</b>`;
        }

        return formatted;
    }
};

function is_numeric_column(column) {
    if (!column || !column.fieldname) return false;

    if (
        column.fieldname === "total_bcm" ||
        column.fieldname === "avg_bcm_per_hour"
    ) {
        return true;
    }

    return column.fieldname.startsWith("h_");
}