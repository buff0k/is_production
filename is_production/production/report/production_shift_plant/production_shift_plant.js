frappe.query_reports["Production Shift Plant"] = {
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
            "label": __("Site Location"),
            "fieldtype": "Link",
            "options": "Location",
            "reqd": 1
        }
    ]
};
