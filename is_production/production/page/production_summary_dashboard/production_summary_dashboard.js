frappe.pages["production-summary-dashboard"].on_page_load = function (wrapper) {
    new ProductionSummaryDashboard(wrapper);
};

class ProductionSummaryDashboard {
    constructor(wrapper) {
        this.wrapper = $(wrapper);
        this.page = frappe.ui.make_app_page({
            parent: wrapper,
            title: "Production Summary Dashboard",
            single_column: true
        });

        this.groupConfig = [
            {
                key: "group_1",
                title: "Koppie / Uitgevallen / Bankfontein",
                sites: ["Koppie", "Uitgevallen", "Bankfontein"]
            },
            {
                key: "group_2",
                title: "Klipfontein / Gwab",
                sites: ["Klipfontein", "Gwab"]
            },
            {
                key: "group_3",
                title: "Kriel Rehabilitation",
                sites: ["Kriel Rehabilitation"]
            }
        ];

        this.inject_css();
        this.make_filters();
        this.make_body();
        this.bind_actions();
        this.load_data();
    }

    inject_css() {
        if ($("#production-summary-dashboard-style").length) return;

        $(`<style id="production-summary-dashboard-style">
            .layout-main-section {
                padding-bottom: 0 !important;
            }

            .psd-root {
                padding: 6px 0 10px;
            }

            .psd-filter-panel {
                background: #ffffff;
                border: 1px solid #d1d8dd;
                border-radius: 10px;
                padding: 8px;
                margin-bottom: 10px;
            }

            .psd-filter-group {
                border: 1px solid #e4e8ee;
                border-radius: 8px;
                padding: 8px 10px;
                margin-bottom: 8px;
                background: #f9fafb;
            }

            .psd-filter-group:last-child {
                margin-bottom: 0;
            }

            .psd-filter-group-title {
                font-size: 12px;
                font-weight: 700;
                color: #1f2d3d;
                margin-bottom: 6px;
                line-height: 1.2;
            }

            .psd-filter-row {
                display: grid;
                grid-template-columns: minmax(180px, 1fr) minmax(180px, 1fr);
                gap: 10px;
                align-items: end;
            }

            .psd-filter-row .form-group {
                margin-bottom: 0 !important;
            }

            .psd-filter-row .control-label {
                font-size: 11px !important;
                margin-bottom: 2px !important;
            }

            .psd-filter-row .control-input,
            .psd-filter-row input {
                min-height: 28px !important;
                height: 28px !important;
                font-size: 12px !important;
                padding-top: 4px !important;
                padding-bottom: 4px !important;
            }

            @media (max-width: 768px) {
                .psd-filter-row {
                    grid-template-columns: 1fr;
                }
            }

            .psd-summary {
                display: grid;
                grid-template-columns: repeat(5, minmax(170px, 1fr));
                gap: 10px;
                margin-bottom: 10px;
            }

            @media (max-width: 1200px) {
                .psd-summary {
                    grid-template-columns: repeat(3, minmax(170px, 1fr));
                }
            }

            @media (max-width: 768px) {
                .psd-summary {
                    grid-template-columns: repeat(2, minmax(150px, 1fr));
                }
            }

            .psd-summary-card {
                background: #ffffff;
                border: 1px solid #d1d8dd;
                border-radius: 8px;
                padding: 8px 10px;
                text-align: center;
                box-shadow: 0 1px 2px rgba(0,0,0,0.03);
                min-height: 88px;
                display: flex;
                flex-direction: column;
                justify-content: center;
            }

            .psd-summary-card .label {
                font-size: 11px;
                color: #5e6c84;
                margin-bottom: 4px;
                line-height: 1.2;
            }

            .psd-summary-card .value {
                font-size: 28px;
                font-weight: 700;
                line-height: 1.05;
                color: #1f2d3d;
            }

            .psd-summary-card .value.positive {
                color: #18a957;
            }

            .psd-summary-card .value.negative {
                color: #e03124;
            }

            .psd-section {
                margin-bottom: 10px;
            }

            .psd-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(260px, 1fr));
                gap: 12px;
            }

            @media (max-width: 1200px) {
                .psd-grid {
                    grid-template-columns: repeat(2, minmax(240px, 1fr));
                }
            }

            @media (max-width: 768px) {
                .psd-grid {
                    grid-template-columns: 1fr;
                }
            }

            .psd-card {
                background: #f7f8fa;
                border: 1px solid #cfd6de;
                border-radius: 8px;
                padding: 10px;
            }

            .psd-card-header {
                background: #0f1f53;
                color: #ffffff;
                text-align: center;
                font-weight: 700;
                font-size: 17px;
                letter-spacing: 0.3px;
                border-radius: 5px;
                padding: 8px 10px;
                margin-bottom: 10px;
                text-transform: uppercase;
                line-height: 1.1;
            }

            .psd-variance-box {
                border-radius: 6px;
                padding: 12px 8px;
                text-align: center;
                margin: 0 8px 10px;
                background: #f5eaea;
            }

            .psd-variance-box.positive {
                background: #dfeee5;
            }

            .psd-variance-label {
                font-size: 11px;
                font-weight: 700;
                color: #62708a;
                text-transform: uppercase;
                margin-bottom: 2px;
                line-height: 1.2;
            }

            .psd-variance-value {
                font-size: 22px;
                font-weight: 800;
                line-height: 1.1;
                color: #e03124;
            }

            .psd-variance-box.positive .psd-variance-value {
                color: #18a957;
            }

            .psd-metric-table {
                width: 100%;
                border-collapse: collapse;
                overflow: hidden;
                border-radius: 6px;
                background: #ffffff;
            }

            .psd-metric-table tr:nth-child(even) {
                background: #f0f2f5;
            }

            .psd-metric-table td {
                border: 1px solid #d7dde5;
                padding: 5px 7px;
                font-size: 12px;
                color: #304055;
                vertical-align: middle;
                line-height: 1.15;
            }

            .psd-metric-table td.label {
                width: 48%;
                color: #5e6c84;
            }

            .psd-metric-table td.unit {
                width: 18%;
                text-align: right;
                font-weight: 700;
            }

            .psd-metric-table td.value {
                width: 34%;
                text-align: right;
                font-weight: 700;
            }

            .psd-positive {
                color: #18a957 !important;
            }

            .psd-negative {
                color: #e03124 !important;
            }

            .psd-footer-line {
                font-size: 12px;
                color: #5e6c84;
                margin: 6px 6px 0;
                line-height: 1.15;
            }

            .psd-empty {
                background: #ffffff;
                border: 1px dashed #cfd6de;
                border-radius: 8px;
                padding: 16px;
                text-align: center;
                color: #5e6c84;
                font-size: 13px;
            }

            .psd-section-empty {
                background: #ffffff;
                border: 1px dashed #cfd6de;
                border-radius: 8px;
                padding: 14px;
                text-align: center;
                color: #5e6c84;
                font-size: 13px;
            }
        </style>`).appendTo("head");
    }

    make_filters() {
        this.groupFilters = {};

        const filterPanel = $(`<div class="psd-filter-panel"></div>`);

        this.groupConfig.forEach(group => {
            const groupBox = $(`
                <div class="psd-filter-group">
                    <div class="psd-filter-group-title">${frappe.utils.escape_html(group.title)}</div>
                    <div class="psd-filter-row"></div>
                </div>
            `);

            const row = groupBox.find(".psd-filter-row");

            const startField = this.page.add_field({
                label: "Start Date",
                fieldtype: "Date",
                fieldname: `${group.key}_start_date`,
                change: () => this.load_data()
            });

            const endField = this.page.add_field({
                label: "End Date",
                fieldtype: "Date",
                fieldname: `${group.key}_end_date`,
                change: () => this.load_data()
            });

            row.append(startField.$wrapper);
            row.append(endField.$wrapper);

            this.groupFilters[group.key] = {
                start_date: startField,
                end_date: endField
            };

            filterPanel.append(groupBox);
        });

        $(this.page.body).append(filterPanel);
    }

    make_body() {
        this.body = $(`<div class="psd-root">
            <div class="psd-summary"></div>
            <div class="psd-content"></div>
        </div>`);

        $(this.page.body).append(this.body);

        this.summary_area = this.body.find(".psd-summary");
        this.content_area = this.body.find(".psd-content");
    }

    bind_actions() {
        this.page.set_primary_action("Refresh", () => this.load_data(), "refresh");
    }

    get_filter_args() {
        return {
            group_1_start_date: this.groupFilters.group_1.start_date.get_value(),
            group_1_end_date: this.groupFilters.group_1.end_date.get_value(),
            group_2_start_date: this.groupFilters.group_2.start_date.get_value(),
            group_2_end_date: this.groupFilters.group_2.end_date.get_value(),
            group_3_start_date: this.groupFilters.group_3.start_date.get_value(),
            group_3_end_date: this.groupFilters.group_3.end_date.get_value()
        };
    }

    hasAnyActiveGroup() {
        return this.groupConfig.some(group => {
            const filters = this.groupFilters[group.key];
            return filters.start_date.get_value() && filters.end_date.get_value();
        });
    }

    async load_data() {
        this.summary_area.empty();

        if (!this.hasAnyActiveGroup()) {
            this.content_area.html(`<div class="psd-empty">Select Start Date and End Date for a site group at the top to load production.</div>`);
            return;
        }

        this.content_area.html(`<div class="psd-empty">Loading dashboard...</div>`);

        try {
            const r = await frappe.call({
                method: "is_production.production.page.production_summary_dashboard.production_summary_dashboard.get_dashboard_data",
                args: this.get_filter_args()
            });

            const data = r.message || {};
            const rows = data.rows || [];
            const summary = data.summary || {};

            this.render_summary(summary);
            this.render_cards(rows);
        } catch (e) {
            this.summary_area.empty();
            this.content_area.html(`<div class="psd-empty">Failed to load dashboard.</div>`);
            frappe.msgprint({
                title: "Dashboard Error",
                indicator: "red",
                message: e.message || "Unable to load dashboard data."
            });
        }
    }

    render_summary(summary) {
        const cards = [
            {
                label: "Total Monthly Target BCM",
                value: summary.total_monthly_target_bcm || 0
            },
            {
                label: "Total Forecast BCM",
                value: summary.total_forecast_bcm || 0
            },
            {
                label: "Total Forecast Variance BCM",
                value: summary.total_forecast_variance_bcm || 0,
                variance: true
            },
            {
                label: "Total Waste Variance BCM",
                value: summary.total_waste_variance_bcm || 0,
                variance: true
            },
            {
                label: "Total Coal Variance Tons",
                value: summary.total_coal_variance_tons || 0,
                variance: true
            }
        ];

        const html = cards.map(card => {
            const cls = card.variance ? this.varianceClass(card.value) : "";
            return `
                <div class="psd-summary-card">
                    <div class="label">${frappe.utils.escape_html(card.label)}</div>
                    <div class="value ${cls}">${this.formatNumber(card.value, 0)}</div>
                </div>
            `;
        }).join("");

        this.summary_area.html(html);
    }

    render_cards(rows) {
        if (!rows.length) {
            this.content_area.html(`
                <div class="psd-empty">
                    No Monthly Production Planning record found for the selected dates.
                </div>
            `);
            return;
        }

        rows.sort((a, b) => {
            const order = {
                "Koppie": 1,
                "Uitgevallen": 2,
                "Bankfontein": 3,
                "Kriel Rehabilitation": 4,
                "Kriel Rehab": 4,
                "Gwab": 5,
                "Klipfontein": 6
            };
            return (order[a.site] || 999) - (order[b.site] || 999);
        });

        this.content_area.html(`
            <div class="psd-section">
                <div class="psd-grid">
                    ${rows.map(row => this.renderCard(row)).join("")}
                </div>
            </div>
        `);
    }

    renderCard(row) {
        const varianceClass = this.varianceClass(row.forecast_variance_bcm);
        const wasteClass = this.varianceClass(row.waste_variance_bcm) === "positive" ? "psd-positive" : "psd-negative";
        const coalClass = this.varianceClass(row.coal_variance_tons) === "positive" ? "psd-positive" : "psd-negative";

        return `
            <div class="psd-card">
                <div class="psd-card-header">${frappe.utils.escape_html(row.site || "")}</div>

                <div class="psd-variance-box ${varianceClass}">
                    <div class="psd-variance-label">Forecast Variance</div>
                    <div class="psd-variance-value">${this.formatSignedNumber(row.forecast_variance_bcm, 0)} BCM</div>
                </div>

                <table class="psd-metric-table">
                    <tr>
                        <td class="label">Monthly target</td>
                        <td class="unit">BCM</td>
                        <td class="value">${this.formatNumber(row.monthly_target_bcm, 0)}</td>
                    </tr>
                    <tr>
                        <td class="label">Forecast</td>
                        <td class="unit">BCM</td>
                        <td class="value">${this.formatNumber(row.forecast_bcm, 0)}</td>
                    </tr>
                    <tr>
                        <td class="label">Waste variance</td>
                        <td class="unit ${wasteClass}">BCM</td>
                        <td class="value ${wasteClass}">${this.formatSignedNumber(row.waste_variance_bcm, 0)}</td>
                    </tr>
                    <tr>
                        <td class="label">Coal variance</td>
                        <td class="unit ${coalClass}">TONS</td>
                        <td class="value ${coalClass}">${this.formatSignedNumber(row.coal_variance_tons, 0)}</td>
                    </tr>
                    <tr>
                        <td class="label">Actual BCMs</td>
                        <td class="unit">BCM</td>
                        <td class="value">${this.formatNumber(row.actual_bcm, 0)}</td>
                    </tr>
                    <tr>
                        <td class="label">Actual coal</td>
                        <td class="unit">TONS</td>
                        <td class="value">${this.formatNumber(row.actual_coal_tons, 0)}</td>
                    </tr>
                    <tr>
                        <td class="label">Daily required</td>
                        <td class="unit">BCM</td>
                        <td class="value">${this.formatNumber(row.daily_required_bcm, 1)}</td>
                    </tr>
                    <tr>
                        <td class="label">Daily achieved</td>
                        <td class="unit">BCM</td>
                        <td class="value">${this.formatNumber(row.daily_achieved_bcm, 1)}</td>
                    </tr>
                    <tr>
                        <td class="label">Days worked / left</td>
                        <td class="unit"></td>
                        <td class="value">${this.formatNumber(row.days_worked, 0)} / ${this.formatNumber(row.days_left, 0)}</td>
                    </tr>
                    <tr>
                        <td class="label">Strip ratio</td>
                        <td class="unit"></td>
                        <td class="value">${this.formatNumber(row.strip_ratio, 1)}</td>
                    </tr>
                </table>

                <div class="psd-footer-line">
                    Forecast delivery ${this.formatNumber(row.forecast_delivery_percent, 1)}%
                </div>
            </div>
        `;
    }

    varianceClass(value) {
        return (flt(value) || 0) >= 0 ? "positive" : "negative";
    }

    formatNumber(value, decimals = 0) {
        const num = Number(value || 0);
        return new Intl.NumberFormat("en-US", {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        }).format(num);
    }

    formatSignedNumber(value, decimals = 0) {
        const num = Number(value || 0);
        const abs = Math.abs(num);
        const formatted = this.formatNumber(abs, decimals);
        if (num > 0) return `+${formatted}`;
        if (num < 0) return `-${formatted}`;
        return `+${formatted}`;
    }
}