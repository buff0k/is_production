// Copyright (c) 2026, Isambane Mining (Pty) Ltd
// CEO Dashboard – Multi-Site Monthly Production

frappe.query_reports["CEO Dashboard One"] = {
    filters: [
        {
            fieldname: "define_monthly_production",
            label: __("Define Monthly Production"),
            fieldtype: "Link",
            options: "Define Monthly Production",
            reqd: 1
        }
    ],

    onload: function (report) {
        report.auto_refresh_interval = 1800000;

        if (!report._auto_refresh_started) {
            report._auto_refresh_started = true;

            setInterval(() => {
                report.refresh();

                frappe.show_alert(
                    {
                        message: __("CEO Dashboard updated at {0}", [
                            frappe.datetime.now_time()
                        ]),
                        indicator: "green"
                    },
                    30
                );
            }, 1800000);
        }
    }
};
