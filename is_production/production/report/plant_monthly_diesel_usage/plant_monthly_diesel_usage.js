frappe.query_reports["Plant Monthly Diesel Usage"] = {
    "filters": [
        {
            "fieldname": "location",
            "label": "Site",
            "fieldtype": "Link",
            "options": "Location",
            "reqd": 1,
            "on_change": function() {
                frappe.query_report.refresh();
                
                // Clear and update asset_name filter based on location
                let location = frappe.query_report.get_filter_value("location");
                if (location) {
                    frappe.db.get_list("Asset", {
                        filters: {
                            location: location
                        },
                        fields: ["name"]
                    }).then(assets => {
                        let asset_names = assets.map(asset => asset.name);
                        frappe.query_report.set_filter_value("asset_name", asset_names);
                    });
                } else {
                    frappe.query_report.set_filter_value("asset_name", []);
                }
            }
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
        },
        {
            "fieldname": "asset_name",
            "label": "Asset Name",
            "fieldtype": "Link",
            "options": "Asset",
            "get_query": function() {
                let location = frappe.query_report.get_filter_value("location");
                return {
                    filters: {
                        "location": location
                    }
                };
            }
        },
        {
            "fieldname": "display_type",
            "label": "Display Type",
            "fieldtype": "Select",
            "options": ["Totals Only", "Totals and Details"],
            "default": "Totals and Details",
            "reqd": 1
        }
    ]
};
