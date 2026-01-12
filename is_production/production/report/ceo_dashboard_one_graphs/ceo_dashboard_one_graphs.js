// Copyright (c) 2026, Isambane Mining (Pty) Ltd
// CEO Dashboard One Graphs

frappe.query_reports["CEO Dashboard One Graphs"] = {
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
        report.auto_refresh_interval = 300000;

        if (!report._auto_refresh_started) {
            report._auto_refresh_started = true;

            setInterval(() => {
                report.refresh();
            }, 300000);
        }
    }
};
