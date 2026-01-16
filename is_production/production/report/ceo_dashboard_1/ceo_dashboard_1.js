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

        // ===============================
        // CONFIG
        // ===============================
        const AUTO_REFRESH_MS = 1800000;   // 30 minutes
        const MESSAGE_INTERVAL_MS = 180000; // 3 minutes
        const MESSAGE_VISIBLE_MS = 15000;   // 15 seconds

        report.auto_refresh_interval = AUTO_REFRESH_MS;

        // ===============================
        // HEADER "LAST UPDATED" PILL
        // ===============================
        if (!report._last_update_el) {
            report._last_update_el = $(`
                <span class="indicator-pill blue" style="margin-left:15px;">
                    Last updated: never
                </span>
            `);

            report.page.set_secondary_action(
                __(""),
                () => {},
                null,
                report._last_update_el
            );
        }

        const update_timestamp = () => {
            report._last_refresh_time = moment();
            report._next_refresh_time = moment(report._last_refresh_time).add(AUTO_REFRESH_MS, "milliseconds");

            report._last_update_el.text(
                __("Last updated: {0}", [report._last_refresh_time.format("HH:mm:ss")])
            );
        };

        report.on("refresh", update_timestamp);
        update_timestamp();

        // ===============================
        // AUTO REFRESH (30 MIN)
        // ===============================
        if (!report._auto_refresh_started) {
            report._auto_refresh_started = true;

            setInterval(() => {
                report.refresh();
            }, AUTO_REFRESH_MS);
        }

        // ===============================
        // FLOATING MESSAGE (EVERY 3 MIN)
        // ===============================
        if (!report._info_message_started) {
            report._info_message_started = true;

            setInterval(() => {
                show_update_message(report);
            }, MESSAGE_INTERVAL_MS);
        }

        // ===============================
        // MESSAGE FUNCTION
        // ===============================
        function show_update_message(report) {
            if (!report._last_refresh_time || !report._next_refresh_time) {
                return;
            }

            const message_html = `
                <div style="
                    font-weight: bold;
                    font-size: 13px;
                    line-height: 1.6;
                ">
                    ⏱ Last updated: ${report._last_refresh_time.format("HH:mm:ss")}<br>
                    🔄 Next update: ${report._next_refresh_time.format("HH:mm:ss")}
                </div>
            `;

            const msg = frappe.msgprint({
                title: __("Dashboard Update Status"),
                message: message_html,
                indicator: "blue",
                wide: false
            });

            // Auto-close after 15 seconds
            setTimeout(() => {
                if (msg && msg.hide) {
                    msg.hide();
                }
            }, MESSAGE_VISIBLE_MS);
        }
    }
};
