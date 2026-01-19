// Copyright (c) 2026, Isambane Mining (Pty) Ltd
// CEO Dashboard – Multi-Site Monthly Production

frappe.query_reports["CEO Dashboard 1"] = {
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

        const AUTO_REFRESH_MS = 45 * 60 * 1000; // 45 minutes

        // AUTO REFRESH ONLY — NO UI WORK
        if (!report._auto_refresh_started) {
            report._auto_refresh_started = true;

            setInterval(() => {
                report.refresh();
            }, AUTO_REFRESH_MS);
        }
    }
};
