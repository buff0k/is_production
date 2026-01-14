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

        // Attach message to page header (PERSISTS)
        if (!report._last_update_el) {
            report._last_update_el = $(
                `<span class="indicator-pill blue" style="margin-left:15px;">
                    Last updated: never
                </span>`
            );
            report.page.set_secondary_action(
                __(""),
                () => {},
                null,
                report._last_update_el
            );
        }

        const update_timestamp = () => {
            report._last_update_el.text(
                __("Last updated: {0}", [frappe.datetime.now_time()])
            );
        };

        // Initial + after every refresh
        report.on("refresh", update_timestamp);
        update_timestamp();

        if (!report._auto_refresh_started) {
            report._auto_refresh_started = true;

            setInterval(() => {
                report.refresh();
            }, 1800000);
        }
    }
};
