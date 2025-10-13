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
        // UI enhancement for editable comment cells
        $(document).on('focus', '.comment-cell', function () {
            $(this).css({ "background-color": "#ffffcc", "outline": "1px solid #ccc" });
        }).on('blur', '.comment-cell', function () {
            $(this).css({ "background-color": "", "outline": "none" });
        });
    }
};
