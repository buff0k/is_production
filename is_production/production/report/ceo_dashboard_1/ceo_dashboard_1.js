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
        // --------------------------------------------------
        // Hide Frappe datatable / empty-state for dashboard-only report (v16-safe)
        // --------------------------------------------------
        const hide_table_bits = () => {
            if (!report || !report.page || !report.page.main) return;

            report.page.main
                .find(".datatable, .dt-scrollable, .dt-footer, .no-result, .result .no-result")
                .hide();
        };

        // Hide immediately (safe but sometimes too early)
        hide_table_bits();

        // Observe this report page for late datatable mounts (common in v16)
        const page_el = report.page && report.page.main && report.page.main.get(0);
        if (page_el && !report._isd_table_observer) {
            report._isd_table_observer = new MutationObserver(() => hide_table_bits());
            report._isd_table_observer.observe(page_el, { childList: true, subtree: true });
        }

        // Also hide after refresh renders content
        if (!report._isd_refresh_wrapped) {
            report._isd_refresh_wrapped = true;

            const original_refresh = report.refresh.bind(report);
            report.refresh = function () {
                hide_table_bits();
                return original_refresh().then(() => {
                    hide_table_bits();
                    setTimeout(hide_table_bits, 50);
                });
            };
        }

        // --------------------------------------------------
        // Your existing auto-refresh logic (unchanged)
        // --------------------------------------------------
        if (report._auto_refresh_started) return;
        report._auto_refresh_started = true;
        report._refreshing = false;

        // --------------------------------------------------
        // Calculate ms until next :10 or :30
        // --------------------------------------------------
        const ms_until_next_refresh = () => {
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

            return (
                (nextMinute - minutes) * 60 * 1000
                - seconds * 1000
                - ms
            );
        };

        // --------------------------------------------------
        // Refresh logic
        // --------------------------------------------------
        const auto_refresh = () => {
            if (report._refreshing) {
                schedule_next();
                return;
            }

            report._refreshing = true;

            report.refresh().then(() => {
                report._refreshing = false;

                const time = new Date().toLocaleTimeString([], {
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
            const delay = ms_until_next_refresh();
            report._auto_refresh_timer = setTimeout(auto_refresh, delay);
        };

        // Start aligned refresh cycle
        schedule_next();
    },

    refresh: function (report) {
        // In case Frappe re-mounts datatable on manual refresh/filter change
        if (!report || !report.page || !report.page.main) return;
        report.page.main
            .find(".datatable, .dt-scrollable, .dt-footer, .no-result, .result .no-result")
            .hide();
    },

    onunload: function (report) {
        if (report._auto_refresh_timer) {
            clearTimeout(report._auto_refresh_timer);
        }
        if (report._isd_table_observer) {
            report._isd_table_observer.disconnect();
            report._isd_table_observer = null;
        }
    }
};
