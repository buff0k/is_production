// Copyright (c) 2026, Isambane Mining (Pty) Ltd
// Hourly Dashboard – Multi-Site Monthly Production

frappe.query_reports["Hourly Dashboard"] = {
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
        const hide_table = () => {
            // report.page.main is reliable in v16
            report.page.main.find('.datatable, .dt-scrollable, .dt-footer, .result .no-result').hide();
        };

        // Hide immediately
        hide_table();

        // Also hide again after a short delay (datatable often initializes after onload)
        setTimeout(hide_table, 50);
        setTimeout(hide_table, 250);

        if (report._auto_refresh_started) return;

        report._auto_refresh_started = true;
        report._refreshing = false;

        const get_ms_until_next_refresh = () => {
            const now = new Date();

            const minutes = now.getMinutes();
            const seconds = now.getSeconds();
            const ms = now.getMilliseconds();

            let nextMinute;

            if (minutes < 10) {
                nextMinute = 10;
            } else if (minutes < 30) {
                nextMinute = 30;
            } else {
                nextMinute = 70; // next hour + 10 minutes
            }

            const waitMinutes = nextMinute - minutes;

            return (
                waitMinutes * 60 * 1000
                - seconds * 1000
                - ms
            );
        };

        const auto_refresh = () => {
            if (report._refreshing) {
                schedule_next();
                return;
            }

            report._refreshing = true;

            report.refresh().then(() => {
                report._refreshing = false;

                // Hide again after refresh completes (datatable may re-render)
                hide_table();
                setTimeout(hide_table, 50);

                const now = new Date();
                const time = now.toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit"
                });

                frappe.show_alert(
                    {
                        message: `Hourly Dashboard updated at ${time}`,
                        indicator: "green"
                    },
                    5
                );

                schedule_next();
            });
        };

        const schedule_next = () => {
            const delay = get_ms_until_next_refresh();
            report._auto_refresh_timer = setTimeout(auto_refresh, delay);
        };

        // Schedule first aligned refresh
        schedule_next();
    },

    refresh: function (report) {
        // Runs when filters change or user hits refresh
        report.page.main.find('.datatable, .dt-scrollable, .dt-footer, .result .no-result').hide();
        setTimeout(() => {
            report.page.main.find('.datatable, .dt-scrollable, .dt-footer, .result .no-result').hide();
        }, 50);
    },

    onunload: function (report) {
        if (report._auto_refresh_timer) {
            clearTimeout(report._auto_refresh_timer);
        }
    }
};
