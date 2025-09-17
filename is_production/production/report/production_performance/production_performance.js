// monthly_production_performance.js

frappe.query_reports["Monthly Production Performance"] = {
    "filters": [
        {
            fieldname: "month",
            label: __("Production Month"),
            fieldtype: "Date",
            reqd: 1   // ✅ mandatory
        },
        {
            fieldname: "location",
            label: __("Location"),
            fieldtype: "Link",
            options: "Location",
            reqd: 1   // ✅ mandatory
        }
    ]
};
