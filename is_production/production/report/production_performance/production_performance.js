frappe.query_reports["Production Performance"] = {
    "filters": [
        {
            fieldname: "start_date",
            label: __("Start Date"),
            fieldtype: "Date",
            reqd: 1
        },
        {
            fieldname: "end_date",
            label: __("End Date"),
            fieldtype: "Date",
            reqd: 1
        },
        {
            fieldname: "site",
            label: __("Site"),
            fieldtype: "Link",
            options: "Location",
            reqd: 1
        }
    ],

    "formatter": function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        // Section headers
        if (data && data.metric && data.metric.startsWith("<b>") && column.fieldname === "metric") {
            return `<div style="font-weight:bold; background:#f4f6f7; padding:6px; border-radius:4px;">${value}</div>`;
        }

        // Values styling
        if (column.fieldname === "value" && value) {
            return `<div style="text-align:right; font-weight:600; color:#2c3e50;">${value}</div>`;
        }

        return value;
    }
};
