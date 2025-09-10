// Copyright (c) 2025, Isambane Mining (Pty) Ltd
// For license information, please see license.txt

frappe.query_reports["Production Shift Material"] = {
    "filters": [
        {
            "fieldname": "start_date",
            "label": __("Start Date"),
            "fieldtype": "Date",
            "reqd": 1
        },
        {
            "fieldname": "end_date",
            "label": __("End Date"),
            "fieldtype": "Date",
            "reqd": 1
        },
        {
            "fieldname": "site",
            "label": __("Site"),
            "fieldtype": "Link",
            "options": "Location",
            "reqd": 1
        },
        {
            "fieldname": "shift",
            "label": __("Shift"),
            "fieldtype": "Select",
            "options": "\nDay\nNight\nMorning\nAfternoon",  // first blank line = all shifts
            "reqd": 0
        }
    ]
};








