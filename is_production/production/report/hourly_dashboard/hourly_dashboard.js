// Copyright (c) 2026, Isambane Mining (Pty) Ltd
// Hourly Dashboard – Multi-Site Monthly Production


frappe.query_reports["Hourly Dashboard"] = {
    filters: [
        {
            fieldname: "monthly_production_planning",
            label: __("Monthly Production Planning"),
            fieldtype: "Link",
            options: "Monthly Production Planning"
        }
    ],

    onload: function (report) {
        if (!report.get_filter_value("monthly_production_planning")) {
            frappe.db.get_list("Monthly Production Planning", {
                fields: ["name"],
                order_by: "prod_month_end_date desc, modified desc",
                limit: 1
            }).then((rows) => {
                if (rows.length) {
                    report.set_filter_value("monthly_production_planning", rows[0].name);
                    report.refresh();
                }
            });
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

        const schedule_next = () => {
            if (report._auto_refresh_timer) {
                clearTimeout(report._auto_refresh_timer);
            }

            report._auto_refresh_timer = setTimeout(auto_refresh, get_ms_until_next_refresh());
        };

        const auto_refresh = () => {
            if (report._refreshing) {
                schedule_next();
                return;
            }

            report._refreshing = true;

            Promise.resolve(report.refresh())
                .then(() => {
                    const time = new Date().toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit"
                    });

                    frappe.show_alert(
                        {
                            message: `Hourly Dashboard data updated at ${time}`,
                            indicator: "green"
                        },
                        5
                    );
                })
                .finally(() => {
                    report._refreshing = false;
                    schedule_next();
                });
        };

        schedule_next();
    },

    onunload: function (report) {
        if (report._auto_refresh_timer) {
            clearTimeout(report._auto_refresh_timer);
            report._auto_refresh_timer = null;
        }

        report._auto_refresh_started = false;
        report._refreshing = false;
    }
};
