// Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Diesel Usage Site Analyses"] = {
    "filters": [
        {
            "fieldname": "month",
            "label": __("Month"),
            "fieldtype": "Select",
            "options": ["", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"],
            "default": frappe.datetime.get_today().split("-")[1]
        },
        {
            "fieldname": "year",
            "label": __("Year"),
            "fieldtype": "Int",
            "default": frappe.datetime.get_today().split("-")[0]
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
            "options": ["Site", "Asset Name"],
            "default": "Site"
        },
        {
            "fieldname": "asset_name",
            "label": __("Asset Name"),
            "fieldtype": "Link",
            "options": "Asset"
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
