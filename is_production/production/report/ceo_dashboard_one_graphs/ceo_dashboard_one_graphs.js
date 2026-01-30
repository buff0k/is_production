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

        hide_table_bits();

        const page_el = report.page && report.page.main && report.page.main.get(0);
        if (page_el && !report._isd_table_observer) {
            report._isd_table_observer = new MutationObserver(() => hide_table_bits());
            report._isd_table_observer.observe(page_el, { childList: true, subtree: true });
        }

        // --- Load Chart.js once ---
        if (!window.Chart) {
            const s = document.createElement("script");
            s.src = "https://cdn.jsdelivr.net/npm/chart.js";
            s.onload = () => render_all_charts();
            document.head.appendChild(s);
        }

        if (!report._isd_chart_observer) {
            report._isd_chart_observer = observe_charts(report, render_all_charts);
        }

        render_all_charts();

        function render_all_charts() {
            if (!window.Chart) return;

            const root = (report.page && report.page.main && report.page.main.get(0)) || document;

            root.querySelectorAll("canvas[data-chart]").forEach((canvas) => {
                // If we already rendered, just resize (handles layout changes)
                if (canvas._isd_chart) {
                    try {
                        canvas._isd_chart.resize();
                        setTimeout(() => canvas._isd_chart && canvas._isd_chart.resize(), 80);
                    } catch (e) {
                        // ignore
                    }
                    return;
                }

                try {
                    const config = JSON.parse(canvas.dataset.chart);
                    const chart = new Chart(canvas.getContext("2d"), config);
                    canvas._isd_chart = chart;
                    canvas.dataset.rendered = "1";

                    // Fix: allow time for flex/grid sizing before final layout calc
                    setTimeout(() => chart.resize(), 50);
                    setTimeout(() => chart.resize(), 150);
                } catch (e) {
                    console.error("Chart render failed", e);
                }
            });
        }
    },

    refresh: function (report) {
        if (!report || !report.page || !report.page.main) return;

        report.page.main
            .find(".datatable, .dt-scrollable, .dt-footer, .no-result, .result .no-result")
            .hide();
    },

    onunload: function (report) {
        if (report && report._isd_table_observer) {
            report._isd_table_observer.disconnect();
            report._isd_table_observer = null;
        }
        if (report && report._isd_chart_observer) {
            report._isd_chart_observer.disconnect();
            report._isd_chart_observer = null;
        }

        // Destroy any charts we created
        try {
            const root = (report.page && report.page.main && report.page.main.get(0)) || document;
            root.querySelectorAll("canvas[data-chart]").forEach((canvas) => {
                if (canvas._isd_chart) {
                    canvas._isd_chart.destroy();
                    canvas._isd_chart = null;
                }
            });
        } catch (e) {
            // ignore
        }
    }
};

function observe_charts(report, render_fn) {
    const root = (report.page && report.page.main && report.page.main.get(0)) || document.body;

    const observer = new MutationObserver(() => {
        render_fn();
    });

    observer.observe(root, { childList: true, subtree: true });
    return observer;
}
