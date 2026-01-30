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
        "fieldname": "location",
        "label": __("Site"),
        "fieldtype": "Link",
        "options": "Location",
        "reqd": 0
    },

    {
        "fieldname": "asset",
        "label": __("Asset"),
        "fieldtype": "Link",
        "options": "Asset",
        "reqd": 0
    },    
    // NEW: Category filter (All + categories loaded onload)
    {
        "fieldname": "asset_category",
        "label": __("Asset Category"),
        "fieldtype": "Select",
        "options": ["All"],
        "default": "All",
        "reqd": 0
    },

    // NEW: Metric selector
    {
        "fieldname": "metric",
        "label": __("Metric"),
        "fieldtype": "Select",
        "options": ["All", "Availability %", "Utilisation %"],
        "default": "All",
        "reqd": 0
    },



    // NEW: Chart view selector
    {
        "fieldname": "chart_type",
        "label": __("Chart View"),
        "fieldtype": "Select",
        "options": ["Bar", "Line"],
        "default": "Bar",
        "reqd": 0
    }
],


    onload: function (report) {



        // Load Asset Category options (Select) -> ["All", ...categories]
        const cat_filter = report.get_filter("asset_category");
        if (cat_filter) {
            frappe.db.get_list("Availability and Utilisation", {
                fields: ["asset_category"],
                group_by: "asset_category",
                order_by: "asset_category asc",
                limit: 999
            }).then(rows => {
                const cats = (rows || [])
                    .map(r => (r.asset_category || "Uncategorised"))
                    .filter(Boolean);

                const unique = ["All", ...Array.from(new Set(cats))];
                cat_filter.df.options = unique;
                cat_filter.refresh();
            });
        }



        // Add toggle for charts
        report.page.add_inner_button(__('Show/Hide Charts'), function () {
            const charts = document.querySelectorAll('.frappe-chart');
            charts.forEach(ch => {
                ch.style.display = ch.style.display === 'none' ? 'block' : 'none';
            });
        });

        // Always refresh button
        report.page.set_primary_action(__("Refresh"), function () {
            report.refresh();
        });
    },

    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "plant_shift_availability" && data.plant_shift_availability >= 85)
            value = `<span style="color:#4CAF50;font-weight:600;">${value}</span>`;
        else if (column.fieldname === "plant_shift_availability")
            value = `<span style="color:#f0ad4e;font-weight:600;">${value}</span>`;
        if (column.fieldname === "plant_shift_utilisation" && data.plant_shift_utilisation >= 75)
            value = `<span style="color:#2196F3;font-weight:600;">${value}</span>`;
        else if (column.fieldname === "plant_shift_utilisation")
            value = `<span style="color:#ff7043;font-weight:600;">${value}</span>`;
        return value;
    }
};
