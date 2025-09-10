// Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Production Shift Location"] = {
    "filters": [
        {
            "fieldname": "start_date",
            "label": __("Start Date"),
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "end_date",
            "label": __("End Date"),
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.get_today()
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
            "options": "\nDay\nNight\nMorning\nAfternoon",  // ← first option empty (means 'all')
            "reqd": 0
        }
    ]
};




