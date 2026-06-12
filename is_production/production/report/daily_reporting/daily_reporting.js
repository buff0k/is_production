// Copyright (c) 2025, Isambane Mining (Pty) Ltd
// For license information, please see license.txt

frappe.query_reports["Daily Reporting"] = {
    filters: [
        {
            fieldname: "end_date",
            label: __("Report Date"),
            fieldtype: "Date",
            reqd: 1
        },
        {
            fieldname: "site",
            label: __("Site"),
            fieldtype: "Link",
            options: "Location",
            reqd: 1
        },
        {
            fieldname: "shift",
            label: __("Shift"),
            fieldtype: "Select",
            options: ["", "Day", "Night"],
            default: ""
        }
    ],

    onload: function (report) {
        force_daily_reporting_non_prepared(report);

        $(document)
            .off("focus.daily_reporting blur.daily_reporting", ".comment-cell")
            .on("focus.daily_reporting", ".comment-cell", function () {
                $(this).css({ "background-color": "#ffffcc", "outline": "1px solid #ccc" });
            })
            .on("blur.daily_reporting", ".comment-cell", function () {
                $(this).css({ "background-color": "", "outline": "none" });
            });
    },

    before_refresh: function (report) {
        force_daily_reporting_non_prepared(report);
    }
};

function force_daily_reporting_non_prepared(report) {
    if (report && report.report_doc) {
        report.report_doc.prepared_report = 0;
    }

    if (frappe.query_report && frappe.query_report.report_doc) {
        frappe.query_report.report_doc.prepared_report = 0;
    }
}