// Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Diesel Usage Site Analyses"] = {
    "filters": [
        {
            "fieldname": "date_from",
            "label": __("Date From"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
        },
        {
            "fieldname": "date_to",
            "label": __("Date To"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "site",
            "label": __("Site"),
            "fieldtype": "Link",
            "options": "Location"
        },
        {
            "fieldname": "group_by",
            "label": __("Group By"),
            "fieldtype": "Select",
            "options": ["Site", "Asset Name", "Asset Category"],
            "default": "Site"
        },
        {
            "fieldname": "asset_name",
            "label": __("Asset Name"),
            "fieldtype": "Link",
            "options": "Asset"
        },
        {
            "fieldname": "docstatus",
            "label": __("Docstatus"),
            "fieldtype": "Select",
            "options": ["", "0", "1"],
            "default": ""
        },
        {
            "fieldname": "asset_category",
            "label": __("Asset Category"),
            "fieldtype": "Select",
            "options": ["", "ADT", "Diesel Bowsers", "Dozer", "Excavator", "Grader", "Lightning Plant", "Service Truck", "TLB", "Water Bowser", "LDV"],
            "default": ""
        },
        {
            "fieldname": "view_mode",
            "label": __("View Mode"),
            "fieldtype": "Select",
            "options": ["Totals and Details", "Only Totals"],
            "default": "Totals and Details"
        }
    ],

    "formatter": function(value, row, column, data, default_formatter) {
        if (column.fieldname === "site" && data && data["is_group"] === 1) {
            value = `<span style='font-weight:bold;'>${value}</span>`;
        }
        return default_formatter(value, row, column, data);
    },

    "tree": true,

    "data": {
        "get_tree_data": function(filters, callback) {
            frappe.call({
                method: "frappe.desk.reportview.get",
                args: {
                    filters: filters,
                },
                callback: function(r) {
                    if (r.message) {
                        callback(r.message);
                    }
                }
            });
        }
    }
};

