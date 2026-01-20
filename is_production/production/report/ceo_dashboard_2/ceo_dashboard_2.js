// Copyright (c) 2026, Isambane Mining (Pty) Ltd
// CEO Dashboard Two – Hourly Excavator Production

frappe.query_reports["CEO Dashboard 2"] = {
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
        if (report._auto_refresh_started) return;

        report._auto_refresh_started = true;
        report._refreshing = false;

        const refresh_interval_ms = 60000; // 1 minute

        const auto_refresh = () => {
            if (report._refreshing) {
                // Skip if a refresh is still running
                schedule_next();
                return;
            }

            report._refreshing = true;

            report.refresh().then(() => {
                report._refreshing = false;

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
                    5
                );

                schedule_next();
            });
        };

        const schedule_next = () => {
            report._auto_refresh_timer = setTimeout(
                auto_refresh,
                refresh_interval_ms
            );
        };

        // Start first cycle
        schedule_next();
    },

    onunload: function (report) {
        // Clean up when user leaves the report
        if (report._auto_refresh_timer) {
            clearTimeout(report._auto_refresh_timer);
        }
    }
};
