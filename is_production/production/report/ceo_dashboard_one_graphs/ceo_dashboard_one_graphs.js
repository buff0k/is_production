// Copyright (c) 2026, Isambane Mining (Pty) Ltd
// CEO Dashboard – Multi-Site Monthly Production

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
        // --- Hide Frappe's datatable / empty-state for dashboard-only report ---
        const hide_table_bits = () => {
            if (!report || !report.page || !report.page.main) return;

            report.page.main
                .find(".datatable, .dt-scrollable, .dt-footer, .no-result, .result .no-result")
                .hide();
        };

        // Hide immediately (often too early, but harmless)
        hide_table_bits();

        // Watch this report page for late-mounting datatable/empty-state (v16 behaviour)
        const page_el = report.page && report.page.main && report.page.main.get(0);
        if (page_el && !report._isd_table_observer) {
            report._isd_table_observer = new MutationObserver(() => hide_table_bits());
            report._isd_table_observer.observe(page_el, { childList: true, subtree: true });
        }

        // --- Load Chart.js once (keep your existing approach) ---
        if (!window.Chart) {
            const s = document.createElement("script");
            s.src = "https://cdn.jsdelivr.net/npm/chart.js";
            s.onload = () => {
                // Render any charts that may already be in DOM
                render_all_charts();
            };
            document.head.appendChild(s);
        }

        // --- Observe + render charts (scoped observer, not whole document) ---
        // Ensure we only create this once per report instance
        if (!report._isd_chart_observer) {
            report._isd_chart_observer = observe_charts(report, render_all_charts);
        }

        // Render immediately as well (in case HTML is already present)
        render_all_charts();

        function render_all_charts() {
            if (!window.Chart) return;

            // Prefer scoping to report page to avoid scanning entire document
            const root = (report.page && report.page.main && report.page.main.get(0)) || document;

            root.querySelectorAll("canvas[data-chart]").forEach((canvas) => {
                if (canvas.dataset.rendered) return;

                try {
                    const config = JSON.parse(canvas.dataset.chart);
                    new Chart(canvas.getContext("2d"), config);
                    canvas.dataset.rendered = "1";
                } catch (e) {
                    console.error("Chart render failed", e);
                }
            });
        }
    },

    refresh: function (report) {
        // On refresh, the datatable can reappear; hide again.
        if (!report || !report.page || !report.page.main) return;

        report.page.main
            .find(".datatable, .dt-scrollable, .dt-footer, .no-result, .result .no-result")
            .hide();
    },

    onunload: function (report) {
        // Disconnect observers to prevent leaks across navigation
        if (report && report._isd_table_observer) {
            report._isd_table_observer.disconnect();
            report._isd_table_observer = null;
        }
        if (report && report._isd_chart_observer) {
            report._isd_chart_observer.disconnect();
            report._isd_chart_observer = null;
        }
    }
};


// ---------------------------------------------------------
// Chart observer helper (scoped to report page)
// ---------------------------------------------------------
function observe_charts(report, render_fn) {
    const root = (report.page && report.page.main && report.page.main.get(0)) || document.body;

    const observer = new MutationObserver(() => {
        // Render charts whenever new DOM appears
        render_fn();
    });

    observer.observe(root, {
        childList: true,
        subtree: true
    });

    return observer;
}
