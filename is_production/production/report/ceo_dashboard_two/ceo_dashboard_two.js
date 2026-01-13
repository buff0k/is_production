// Copyright (c) 2026, Isambane Mining (Pty) Ltd
// CEO Dashboard Two – Hourly Excavator Production

frappe.query_reports["CEO Dashboard Two"] = {
    filters: [
        {
            fieldname: "monthly_production_plan",
            label: __("Monthly Production Plan"),
            fieldtype: "Link",
            options: "Define Monthly Production",
            reqd: 1
        }
    ],

    onload: function (report) {
        if (!report._auto_refresh_started) {
            report._auto_refresh_started = true;

            setInterval(() => {
                report.refresh();

                const now = new Date();
                const time = now.toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit"
                });

                frappe.show_alert(
                    {
                        message: `CEO Dashboard updated at ${time}`,
                        indicator: "green"
                    },
                    30
                );
            }, 1800000); // 30 minutes
        }
    }
};
