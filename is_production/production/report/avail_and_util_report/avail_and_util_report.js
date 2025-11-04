frappe.query_reports["Avail and Util report"] = {
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
        }
    ],

    onload: function(report) {
        report.page.set_primary_action(__("Refresh"), function() {
            report.refresh();
        });
    },

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        // Breakdown reason = red
        if (column.fieldname === "breakdown_reason" && data.breakdown_reason) {
            value = `<span style="color:#d9534f;font-weight:600;" title="${data.breakdown_reason}">
                        ${data.breakdown_reason}
                     </span>`;
        }

        // Delay reason = orange
        if (column.fieldname === "other_delay_reason" && data.other_delay_reason) {
            value = `<span style="color:#f0ad4e;" title="${data.other_delay_reason}">
                        ${data.other_delay_reason}
                     </span>`;
        }

        return value;
    }
};
