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
        const hide_table_bits = () => {
            if (!report || !report.page || !report.page.main) return;
            report.page.main.find(".datatable, .dt-scrollable, .dt-footer, .result .no-result, .no-result").hide();
        };

        hide_table_bits();

        const page_el = report.page && report.page.main && report.page.main.get(0);
        if (page_el && !report._isd_table_observer) {
            report._isd_table_observer = new MutationObserver(() => hide_table_bits());
            report._isd_table_observer.observe(page_el, { childList: true, subtree: true });
        }

        if (report._auto_refresh_started) return;

        report._auto_refresh_started = true;
        report._refreshing = false;

        const get_ms_until_next_refresh = () => {
            const now = new Date();
            const minutes = now.getMinutes();
            const seconds = now.getSeconds();
            const ms = now.getMilliseconds();

            let nextMinute;
            if (minutes < 10) nextMinute = 10;
            else if (minutes < 30) nextMinute = 30;
            else nextMinute = 70; // next hour + 10 minutes

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

                hide_table_bits();

                const time = new Date().toLocaleTimeString([], {
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
            report._auto_refresh_timer = setTimeout(auto_refresh, get_ms_until_next_refresh());
        };

        schedule_next();
    },

    refresh: function (report) {
        if (!report || !report.page || !report.page.main) return;
        report.page.main.find(".datatable, .dt-scrollable, .dt-footer, .result .no-result, .no-result").hide();
    },

    onunload: function (report) {
        if (report._auto_refresh_timer) clearTimeout(report._auto_refresh_timer);

        if (report._isd_table_observer) {
            report._isd_table_observer.disconnect();
            report._isd_table_observer = null;
        }
    }
};
