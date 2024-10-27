// Copyright (c) 2024, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Plant Monthly Diesel Usage"] = {
    "filters": [
        {
            "fieldname": "site",
            "label": __("Site"),
            "fieldtype": "Link",
            "options": "Location",  // Adjust "Location" to the relevant Doctype for your sites if different
            "reqd": 1,
            "default": "",  // Optionally set a default value here
            "get_query": function() {
                return {
                    filters: {
                        "is_group": 0  // Adjust or add filters specific to your setup if necessary
                    }
                };
            }
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.month_start(),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.month_end(),
            "reqd": 1
        }
    ],

    "onload": function(report) {
        report.page.add_inner_button(__('Fetch Records'), function() {
            let filters = report.get_values();
            frappe.call({
                method: "is_production.production.report.plant_monthly_diesel_usage.plant_monthly_diesel_usage.fetch_records",
                args: {
                    "site": filters.site,
                    "from_date": filters.from_date,
                    "to_date": filters.to_date
                },
                callback: function(response) {
                    if(response.message) {
                        report.data = response.message;
                        report.refresh();
                    } else {
                        frappe.msgprint(__('No records found for the selected criteria.'));
                    }
                }
            });
        });
    }
};