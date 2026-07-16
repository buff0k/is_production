const hodPresentationMonthStart = (() => {
    const today = frappe.datetime.get_today();
    return `${today.slice(0, 7)}-01`;
})();

frappe.query_reports["HOD Presentation"] = {
    filters: [
        {
            fieldname: "start_date",
            label: __("Start Date"),
            fieldtype: "Date",
            reqd: 1,
            default: hodPresentationMonthStart
        },
        {
            fieldname: "end_date",
            label: __("End Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.get_today()
        },
        {
            fieldname: "site",
            label: __("Site"),
            fieldtype: "Link",
            options: "Location",
            reqd: 1
        },
        {
            fieldname: "summary_type",
            label: __("Summary Type"),
            fieldtype: "Select",
            options: [
                "Daily Summary",
                "Average Per Machine",
                "Weekly Summary",
                "Monthly Summary"
            ],
            reqd: 1,
            default: "Average Per Machine"
        },
        {
            fieldname: "machine_scope",
            label: __("Machine Scope"),
            fieldtype: "Select",
            options: [
                "Production Machines",
                "Swing/Spare Machines",
                "Include Swing/Spare"
            ],
            reqd: 1,
            default: "Include Swing/Spare"
        },
        {
            fieldname: "au_target_filter",
            label: __("A & U Target"),
            fieldtype: "Select",
            options: [
                "100% A & U",
                "85% A & U"
            ],
            reqd: 1,
            default: "85% A & U"
        }
    ],

    onload(report) {
        injectHodPresentationStyles();

        report.page.add_inner_button(__("Download Presentation"), () => {
            downloadHodPresentation(report);
        });
    },

    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        const varianceFields = new Set([
            "forecast_variance_bcm",
            "waste_variance_bcm",
            "coal_variance_tons"
        ]);

        if (varianceFields.has(column.fieldname)) {
            const numericValue = Number(data[column.fieldname] || 0);
            const className = numericValue >= 0 ? "hod-positive" : "hod-negative";
            return `<span class="${className}">${value}</span>`;
        }

        if (column.fieldname === "average_bcm_h") {
            const className = Number(data.average_bcm_h || 0) > 0
                ? "hod-kpi-good"
                : "hod-negative";
            return `<span class="${className}">${value}</span>`;
        }

        if (column.fieldname === "average_availability") {
            const className = Number(data.average_availability || 0) >= 85
                ? "hod-au-good"
                : "hod-au-bad";
            return `<span class="${className}">${value}</span>`;
        }

        if (column.fieldname === "average_utilisation") {
            const className = Number(data.average_utilisation || 0) >= 80
                ? "hod-au-good"
                : "hod-au-bad";
            return `<span class="${className}">${value}</span>`;
        }

        if (["actual_bcm", "total_excavator_hours"].includes(column.fieldname)) {
            return `<span class="hod-kpi-primary">${value}</span>`;
        }

        if (column.fieldname === "excluded_hour_entries") {
            const className = Number(data.excluded_hour_entries || 0) > 0
                ? "hod-warning"
                : "hod-muted";
            return `<span class="${className}">${value}</span>`;
        }

        return value;
    }
};

function downloadHodPresentation(report) {
    const getFilterValue = (fieldname) => {
        if (report && typeof report.get_filter_value === "function") {
            return report.get_filter_value(fieldname);
        }
        return frappe.query_report.get_filter_value(fieldname);
    };

    const filters = {
        start_date: getFilterValue("start_date"),
        end_date: getFilterValue("end_date"),
        site: getFilterValue("site"),
        summary_type: getFilterValue("summary_type"),
        machine_scope: getFilterValue("machine_scope"),
        au_target_filter: getFilterValue("au_target_filter")
    };

    const missing = Object.entries(filters)
        .filter(([, filterValue]) => !filterValue)
        .map(([key]) => key.replace(/_/g, " "));

    if (missing.length) {
        frappe.msgprint({
            title: __("Missing Filters"),
            indicator: "orange",
            message: __("Complete all required filters before downloading the presentation.")
        });
        return;
    }

    if (filters.start_date > filters.end_date) {
        frappe.msgprint({
            title: __("Invalid Date Range"),
            indicator: "red",
            message: __("Start Date cannot be after End Date.")
        });
        return;
    }

    const method = "is_production.production.report.hod_presentation.hod_presentation.download_presentation";
    const params = new URLSearchParams(filters);
    const url = `/api/method/${method}?${params.toString()}`;

    const downloadWindow = window.open(url, "_blank");
    if (!downloadWindow) {
        window.location.assign(url);
    }
}

function injectHodPresentationStyles() {
    if (document.getElementById("hod-presentation-report-style")) return;

    const style = document.createElement("style");
    style.id = "hod-presentation-report-style";
    style.textContent = `
        .hod-positive {
            color: #18a957;
            font-weight: 800;
        }

        .hod-negative {
            color: #e03124;
            font-weight: 800;
        }

        .hod-kpi-primary {
            color: #0f1f53;
            font-weight: 900;
        }

        .hod-kpi-good,
        .hod-au-good,
        .hod-au-bad {
            display: inline-block;
            min-width: 62px;
            padding: 3px 8px;
            border-radius: 999px;
            font-weight: 900;
            text-align: center;
        }

        .hod-kpi-good,
        .hod-au-good {
            color: #166534;
            background: #dcfce7;
            border: 1px solid #86efac;
        }

        .hod-au-bad {
            color: #b91c1c;
            background: #fee2e2;
            border: 1px solid #fca5a5;
        }

        .hod-warning {
            color: #b45309;
            font-weight: 800;
        }

        .hod-muted {
            color: #64748b;
            font-weight: 700;
        }
    `;

    document.head.appendChild(style);
}
