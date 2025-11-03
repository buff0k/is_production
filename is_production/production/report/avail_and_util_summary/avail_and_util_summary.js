frappe.query_reports["Avail and Util summary"] = {
    "filters": [
        {
            "fieldname": "start_date",
            "label": __("Start Date"),
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.add_days(frappe.datetime.nowdate(), -7)
        },
        {
            "fieldname": "end_date",
            "label": __("End Date"),
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.nowdate()
        },
        {
            "fieldname": "site",
            "label": __("Site"),
            "fieldtype": "Link",
            "options": "Location",
            "reqd": 0
        }
    ]
}
