frappe.query_reports["Production Summary Review"] = {
    filters: [
        {
            fieldname: "report_date",
            label: "Report Date",
            fieldtype: "Date",
            default: frappe.datetime.get_today()
        },
        {
            fieldname: "site",
            label: "Site",
            fieldtype: "Data"
        }
    ]
};