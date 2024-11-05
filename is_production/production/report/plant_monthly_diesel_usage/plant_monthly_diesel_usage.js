// Copyright (c) 2024, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Plant Monthly Diesel Usage"] = {
    "filters": [
        {
            "fieldname": "location",
            "label": "Site",
            "fieldtype": "Link",
            "options": "Location",
            "reqd": 1,
            "on_change": function() {
                const location = frappe.query_report.get_filter_value('location');
                
                if (location) {
                    // Update the asset_name filter options based on the selected location
                    frappe.query_report.get_filter('asset_name').get_query = function() {
                        return {
                            filters: {
                                'location': location,
                                'docstatus': 1  // Only include assets with submitted status
                            }
                        };
                    };
                    
                    // Clear asset_name selection if location is changed
                    frappe.query_report.set_filter_value('asset_name', null);
                    frappe.query_report.refresh();
                }
            }
        },
        {
            "fieldname": "asset_name",
            "label": "Asset Name",
            "fieldtype": "Link",
            "options": "Asset",
            "reqd": 0  // Make asset_name optional
        },
        {
            "fieldname": "from_date",
            "label": "From Date",
            "fieldtype": "Date",
            "default": frappe.datetime.month_start(),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": "To Date",
            "fieldtype": "Date",
            "default": frappe.datetime.month_end(),
            "reqd": 1
        }
    ]
};
