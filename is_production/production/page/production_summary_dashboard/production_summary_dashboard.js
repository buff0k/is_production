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

        this.last_rows = [];
        this.last_summary = {};

        this.inject_assets_and_css();
        this.make_filters();
        this.make_body();
        this.bind_actions();
        this.load_data();
    }

    inject_assets_and_css() {
        if (!window.XLSX && !document.getElementById("psd-xlsx-lib")) {
            const script = document.createElement("script");
            script.id = "psd-xlsx-lib";
            script.src = "https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js";
            document.head.appendChild(script);
        }

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

            @media print {
                body * {
                    visibility: hidden !important;
                }

                #psd-print-wrapper,
                #psd-print-wrapper * {
                    visibility: visible !important;
                }

                #psd-print-wrapper {
                    position: absolute;
                    left: 0;
                    top: 0;
                    width: 100%;
                    background: white;
                    padding: 12px;
                }
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
        this.page.add_inner_button("Download PDF", () => this.download_pdf());
        this.page.add_inner_button("Export Excel", () => this.export_excel());
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
            this.last_rows = [];
            this.last_summary = {};
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

            this.last_rows = rows;
            this.last_summary = summary;

            this.render_summary(summary);
            this.render_cards(rows);
        } catch (e) {
            this.last_rows = [];
            this.last_summary = {};
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
            <div id="psd-print-wrapper">
                <div class="psd-section">
                    <div class="psd-grid">
                        ${rows.map(row => this.renderCard(row)).join("")}
                    </div>
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

    download_pdf() {
        const printArea = document.getElementById("psd-print-wrapper");
        if (!printArea) {
            frappe.msgprint("Nothing to print yet.");
            return;
        }

        const win = window.open("", "_blank");
        const printHtml = `
            <html>
                <head>
                    <title>Production Summary Dashboard</title>
                    <style>
                        body {
                            font-family: Arial, sans-serif;
                            margin: 16px;
                            color: #1f2d3d;
                        }
                        h1 {
                            font-size: 20px;
                            margin-bottom: 12px;
                        }
                        .psd-grid {
                            display: grid;
                            grid-template-columns: repeat(2, 1fr);
                            gap: 12px;
                        }
                        .psd-card {
                            background: #f7f8fa;
                            border: 1px solid #cfd6de;
                            border-radius: 8px;
                            padding: 10px;
                            page-break-inside: avoid;
                        }
                        .psd-card-header {
                            background: #0f1f53;
                            color: #ffffff;
                            text-align: center;
                            font-weight: 700;
                            font-size: 16px;
                            border-radius: 5px;
                            padding: 8px 10px;
                            margin-bottom: 10px;
                            text-transform: uppercase;
                        }
                        .psd-variance-box {
                            border-radius: 6px;
                            padding: 12px 8px;
                            text-align: center;
                            margin: 0 8px 10px;
                            background: #f5eaea;
                        }
                        .psd-variance-label {
                            font-size: 11px;
                            font-weight: 700;
                            color: #62708a;
                            text-transform: uppercase;
                            margin-bottom: 2px;
                        }
                        .psd-variance-value {
                            font-size: 22px;
                            font-weight: 800;
                            color: #e03124;
                        }
                        .psd-metric-table {
                            width: 100%;
                            border-collapse: collapse;
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
                        .psd-footer-line {
                            font-size: 12px;
                            color: #5e6c84;
                            margin: 6px 6px 0;
                        }
                    </style>
                </head>
                <body>
                    <h1>Production Summary Dashboard</h1>
                    ${printArea.outerHTML}
                </body>
            </html>
        `;

        win.document.open();
        win.document.write(printHtml);
        win.document.close();

        setTimeout(() => {
            win.focus();
            win.print();
        }, 500);
    }

    export_excel() {
        if (!this.last_rows || !this.last_rows.length) {
            frappe.msgprint("No data to export.");
            return;
        }

        if (!window.XLSX) {
            frappe.msgprint("Excel library still loading. Please wait a few seconds and try again.");
            return;
        }

        const wb = XLSX.utils.book_new();

        const wsDashboard = this.build_dashboard_sheet();
        const wsRaw = this.build_raw_sheet();

        XLSX.utils.book_append_sheet(wb, wsDashboard, "Dashboard View");
        XLSX.utils.book_append_sheet(wb, wsRaw, "Raw Data");

        XLSX.writeFile(wb, "Production_Summary.xlsx");
    }

    build_dashboard_sheet() {
        const rows = [...this.last_rows].sort((a, b) => {
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

        const ws = {};
        const merges = [];
        const siteCardWidth = 4;
        const gapCols = 1;
        const cardHeight = 15;

        const summaryStartRow = 0;
        const summaryItems = [
            ["Total Monthly Target BCM", this.last_summary.total_monthly_target_bcm || 0],
            ["Total Forecast BCM", this.last_summary.total_forecast_bcm || 0],
            ["Total Forecast Variance BCM", this.last_summary.total_forecast_variance_bcm || 0],
            ["Total Waste Variance BCM", this.last_summary.total_waste_variance_bcm || 0],
            ["Total Coal Variance Tons", this.last_summary.total_coal_variance_tons || 0]
        ];

        this.setCell(ws, 0, summaryStartRow, "Production Summary Dashboard", this.styles().title);
        merges.push({ s: { r: 0, c: 0 }, e: { r: 0, c: 14 } });

        summaryItems.forEach((item, index) => {
            const startCol = index * 3;
            this.setCell(ws, startCol, 2, item[0], this.styles().summaryLabel);
            merges.push({ s: { r: 2, c: startCol }, e: { r: 2, c: startCol + 1 } });

            const summaryValueStyle = this.isVarianceLabel(item[0])
                ? this.varianceExcelStyle(item[1], true)
                : this.styles().summaryValue;

            this.setCell(ws, startCol, 3, item[1], summaryValueStyle);
            merges.push({ s: { r: 3, c: startCol }, e: { r: 3, c: startCol + 1 } });
        });

        const cardStartRow = 6;

        rows.forEach((row, idx) => {
            const gridRow = Math.floor(idx / 3);
            const gridCol = idx % 3;

            const baseCol = gridCol * (siteCardWidth + gapCols);
            const baseRow = cardStartRow + gridRow * (cardHeight + 1);

            this.drawCard(ws, merges, row, baseCol, baseRow);
        });

        ws["!merges"] = merges;
        ws["!cols"] = this.dashboardCols();
        ws["!ref"] = this.computeRef(rows, cardStartRow, cardHeight);

        return ws;
    }

    drawCard(ws, merges, row, baseCol, baseRow) {
        const styles = this.styles();
        const varianceStyle = this.varianceExcelStyle(row.forecast_variance_bcm, false);
        const wasteStyle = this.varianceExcelStyle(row.waste_variance_bcm, false);
        const coalStyle = this.varianceExcelStyle(row.coal_variance_tons, false);

        // Header
        this.setCell(ws, baseCol, baseRow, String(row.site || "").toUpperCase(), styles.cardHeader);
        merges.push({
            s: { r: baseRow, c: baseCol },
            e: { r: baseRow, c: baseCol + 3 }
        });

        // Variance block
        this.setCell(ws, baseCol, baseRow + 1, "FORECAST VARIANCE", styles.varianceLabel);
        merges.push({
            s: { r: baseRow + 1, c: baseCol },
            e: { r: baseRow + 1, c: baseCol + 3 }
        });

        this.setCell(ws, baseCol, baseRow + 2, `${this.formatSignedNumber(row.forecast_variance_bcm, 0)} BCM`, varianceStyle);
        merges.push({
            s: { r: baseRow + 2, c: baseCol },
            e: { r: baseRow + 2, c: baseCol + 3 }
        });

        const metrics = [
            ["Monthly target", "BCM", row.monthly_target_bcm, styles.metricValue],
            ["Forecast", "BCM", row.forecast_bcm, styles.metricValue],
            ["Waste variance", "BCM", row.waste_variance_bcm, wasteStyle],
            ["Coal variance", "TONS", row.coal_variance_tons, coalStyle],
            ["Actual BCMs", "BCM", row.actual_bcm, styles.metricValue],
            ["Actual coal", "TONS", row.actual_coal_tons, styles.metricValue],
            ["Daily required", "BCM", row.daily_required_bcm, styles.metricValue],
            ["Daily achieved", "BCM", row.daily_achieved_bcm, styles.metricValue],
            ["Days worked / left", "", `${row.days_worked} / ${row.days_left}`, styles.metricValue],
            ["Strip ratio", "", row.strip_ratio, styles.metricValue]
        ];

        metrics.forEach((m, i) => {
            const r = baseRow + 3 + i;
            this.setCell(ws, baseCol, r, m[0], styles.metricLabel);
            this.setCell(ws, baseCol + 1, r, m[1], styles.metricUnit);
            this.setCell(ws, baseCol + 2, r, m[2], m[3]);
            merges.push({
                s: { r, c: baseCol + 2 },
                e: { r, c: baseCol + 3 }
            });
        });

        this.setCell(ws, baseCol, baseRow + 13, `Forecast delivery ${this.formatNumber(row.forecast_delivery_percent, 1)}%`, styles.footer);
        merges.push({
            s: { r: baseRow + 13, c: baseCol },
            e: { r: baseRow + 13, c: baseCol + 3 }
        });
    }

    build_raw_sheet() {
        const summaryData = [
            { "Metric": "Total Monthly Target BCM", "Value": this.last_summary.total_monthly_target_bcm || 0 },
            { "Metric": "Total Forecast BCM", "Value": this.last_summary.total_forecast_bcm || 0 },
            { "Metric": "Total Forecast Variance BCM", "Value": this.last_summary.total_forecast_variance_bcm || 0 },
            { "Metric": "Total Waste Variance BCM", "Value": this.last_summary.total_waste_variance_bcm || 0 },
            { "Metric": "Total Coal Variance Tons", "Value": this.last_summary.total_coal_variance_tons || 0 }
        ];

        const detailData = this.last_rows.map(r => ({
            "Site": r.site,
            "Monthly Target BCM": r.monthly_target_bcm,
            "Forecast BCM": r.forecast_bcm,
            "Forecast Variance BCM": r.forecast_variance_bcm,
            "Waste Variance BCM": r.waste_variance_bcm,
            "Coal Variance Tons": r.coal_variance_tons,
            "Actual BCM": r.actual_bcm,
            "Actual Coal Tons": r.actual_coal_tons,
            "Daily Required BCM": r.daily_required_bcm,
            "Daily Achieved BCM": r.daily_achieved_bcm,
            "Days Worked": r.days_worked,
            "Days Left": r.days_left,
            "Strip Ratio": r.strip_ratio,
            "Forecast Delivery %": r.forecast_delivery_percent
        }));

        const ws = XLSX.utils.aoa_to_sheet([["Summary"]]);
        XLSX.utils.sheet_add_json(ws, summaryData, { origin: "A3" });
        XLSX.utils.sheet_add_aoa(ws, [[""]], { origin: "A10" });
        XLSX.utils.sheet_add_aoa(ws, [["Site Details"]], { origin: "A12" });
        XLSX.utils.sheet_add_json(ws, detailData, { origin: "A14" });

        return ws;
    }

    styles() {
        return {
            title: {
                font: { bold: true, sz: 16, color: { rgb: "1F2D3D" } },
                alignment: { horizontal: "center", vertical: "center" }
            },
            summaryLabel: {
                font: { bold: true, sz: 10, color: { rgb: "5E6C84" } },
                fill: { fgColor: { rgb: "F4F6F8" } },
                alignment: { horizontal: "center", vertical: "center", wrapText: true },
                border: this.borderAll()
            },
            summaryValue: {
                font: { bold: true, sz: 16, color: { rgb: "1F2D3D" } },
                alignment: { horizontal: "center", vertical: "center" },
                border: this.borderAll()
            },
            cardHeader: {
                font: { bold: true, sz: 12, color: { rgb: "FFFFFF" } },
                fill: { fgColor: { rgb: "0F1F53" } },
                alignment: { horizontal: "center", vertical: "center" },
                border: this.borderAll()
            },
            varianceLabel: {
                font: { bold: true, sz: 10, color: { rgb: "62708A" } },
                fill: { fgColor: { rgb: "F5EAEA" } },
                alignment: { horizontal: "center", vertical: "center" },
                border: this.borderAll()
            },
            variancePositive: {
                font: { bold: true, sz: 14, color: { rgb: "18A957" } },
                fill: { fgColor: { rgb: "DFEEE5" } },
                alignment: { horizontal: "center", vertical: "center" },
                border: this.borderAll()
            },
            varianceNegative: {
                font: { bold: true, sz: 14, color: { rgb: "E03124" } },
                fill: { fgColor: { rgb: "F5EAEA" } },
                alignment: { horizontal: "center", vertical: "center" },
                border: this.borderAll()
            },
            metricLabel: {
                font: { sz: 10, color: { rgb: "5E6C84" } },
                alignment: { horizontal: "left", vertical: "center" },
                border: this.borderAll()
            },
            metricUnit: {
                font: { bold: true, sz: 10, color: { rgb: "304055" } },
                alignment: { horizontal: "right", vertical: "center" },
                border: this.borderAll()
            },
            metricValue: {
                font: { bold: true, sz: 10, color: { rgb: "304055" } },
                alignment: { horizontal: "right", vertical: "center" },
                border: this.borderAll()
            },
            footer: {
                font: { sz: 10, color: { rgb: "5E6C84" } },
                alignment: { horizontal: "left", vertical: "center" },
                border: this.borderAll()
            }
        };
    }

    varianceExcelStyle(value, isSummary) {
        const positive = Number(value || 0) >= 0;
        const base = this.styles();
        if (isSummary) {
            return {
                font: {
                    bold: true,
                    sz: 16,
                    color: { rgb: positive ? "18A957" : "E03124" }
                },
                alignment: { horizontal: "center", vertical: "center" },
                border: this.borderAll()
            };
        }
        return positive ? base.variancePositive : base.varianceNegative;
    }

    borderAll() {
        return {
            top: { style: "thin", color: { rgb: "D7DDE5" } },
            bottom: { style: "thin", color: { rgb: "D7DDE5" } },
            left: { style: "thin", color: { rgb: "D7DDE5" } },
            right: { style: "thin", color: { rgb: "D7DDE5" } }
        };
    }

    setCell(ws, col, row, value, style) {
        const cellRef = XLSX.utils.encode_cell({ c: col, r: row });
        ws[cellRef] = {
            v: value,
            t: typeof value === "number" ? "n" : "s",
            s: style
        };
    }

    dashboardCols() {
        return [
            { wch: 20 }, { wch: 10 }, { wch: 14 }, { wch: 2 },
            { wch: 3 },
            { wch: 20 }, { wch: 10 }, { wch: 14 }, { wch: 2 },
            { wch: 3 },
            { wch: 20 }, { wch: 10 }, { wch: 14 }, { wch: 2 },
            { wch: 3 }
        ];
    }

    computeRef(rows, cardStartRow, cardHeight) {
        const cardRows = Math.ceil(rows.length / 3);
        const lastRow = cardStartRow + (cardRows * (cardHeight + 1)) + 2;
        const lastCol = 14;
        return XLSX.utils.encode_range({
            s: { c: 0, r: 0 },
            e: { c: lastCol, r: lastRow }
        });
    }

    isVarianceLabel(label) {
        return String(label).toLowerCase().includes("variance");
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