// Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

// File: hierarchy_diesel_report.js
frappe.query_reports["Hierarchy Diesel Report"] = {
    filters: [
        {
            fieldname: "location",
            label: __("Location"),
            fieldtype: "Link",
            options: "Location",
        },
        {
            fieldname: "asset_name",
            label: __("Diesel Bowser"),
            fieldtype: "Link",
            options: "Asset",
        },
        {
            fieldname: "daily_sheet_date",
            label: __("Daily Sheet Date"),
            fieldtype: "Date",
        },
    ],
};

