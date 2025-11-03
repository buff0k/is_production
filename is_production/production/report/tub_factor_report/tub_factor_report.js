frappe.query_reports["Tub Factor Report"] = {
    "filters": [
        {
            "fieldname": "item_name",
            "label": __("Item Name"),
            "fieldtype": "Link",
            "options": "Item",
            "reqd": 0
        },
        {
            "fieldname": "mat_type",
            "label": __("Material Type"),
            "fieldtype": "Link",
            "options": "Material Type",
            "reqd": 0
        }
    ]
};
