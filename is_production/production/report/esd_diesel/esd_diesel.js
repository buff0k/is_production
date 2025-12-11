frappe.query_reports["ESD DIESEL"] = {
    "filters": [
        {
            "fieldname": "start_date",
            "label": __("Start Date"),
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "end_date",
            "label": __("End Date"),
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "machine",
            "label": __("Machine"),
            "fieldtype": "Select",
            "options": ["", "EX01", "ADT01", "ADT02", "ADT03", "ADT04"].join("\n"),
            "reqd": 0
        },
        {
            "fieldname": "shift",
            "label": __("Shift"),
            "fieldtype": "Select",
            "options": ["", "Day", "Night"].join("\n"),
            "reqd": 0
        },
        {
            "fieldname": "site",
            "label": __("Site"),
            "fieldtype": "Link",
            "options": "Location",
            "reqd": 0
        }
    ]
};

// -----------------------------------------
// Helper function for Dashboard embedding
// -----------------------------------------
frappe.query_reports["ESD DIESEL"].load_report_to_div = function (mount, filters) {
    frappe.call({
        method: "frappe.desk.query_report.run",
        args: {
            report_name: "ESD DIESEL",
            filters: filters,
            ignore_prepared_report: true
        },
        callback: function (r) {
            const msg = r.message || {};
            mount.innerHTML = msg.report_html || "<div class='text-muted'>No data</div>";
        }
    });
};
