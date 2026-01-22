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

    onload() {
        // Load Chart.js once
        if (!window.Chart) {
            const s = document.createElement("script");
            s.src = "https://cdn.jsdelivr.net/npm/chart.js";
            document.head.appendChild(s);
        }

        observe_charts();
    }
};

function observe_charts() {
    const observer = new MutationObserver(() => {
        if (!window.Chart) return;

        document.querySelectorAll("canvas[data-chart]").forEach(canvas => {
            if (canvas.dataset.rendered) return;

            try {
                const config = JSON.parse(canvas.dataset.chart);
                new Chart(canvas.getContext("2d"), config);
                canvas.dataset.rendered = "1";
            } catch (e) {
                console.error("Chart render failed", e);
            }
        });
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
}
