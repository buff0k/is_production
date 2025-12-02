// Copyright (c) 2025, Isambane Mining
// For license information, please see license.txt

frappe.pages["production-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Production Dashboard",
        single_column: true,
    });

    const mainEl = page.main.get(0);

    //-------------------------------------------------------------
    // FILTERS
    //-------------------------------------------------------------

    const start = page.add_field({
        fieldname: "start_date",
        label: "Start Date",
        fieldtype: "Date",
    });

    const end = page.add_field({
        fieldname: "end_date",
        label: "End Date",
        fieldtype: "Date",
    });

    const site = page.add_field({
        fieldname: "site",
        label: "Site",
        fieldtype: "Link",
        options: "Location",
    });

    const monthly_production = page.add_field({
        fieldname: "monthly_production",
        label: "Monthly Production",
        fieldtype: "Link",
        options: "Monthly Production Planning",
        reqd: 1,
    });

    monthly_production.get_query = () => {
        const val = site.get_value();
        if (!val) {
            frappe.msgprint(__("Please select a Site first."));
            return { filters: [] };
        }
        return {
            filters: { location: val },
            order_by: "creation desc",
        };
    };

    const shift = page.add_field({
        fieldname: "shift",
        label: "Shift",
        fieldtype: "Select",
        options: ["", "Day", "Night", "Morning", "Afternoon"],
    });

    page.set_primary_action(__("Run"), () => refresh_all(true));

    //-------------------------------------------------------------
    // TAB NAVIGATION
    //-------------------------------------------------------------

    const tabNav = document.createElement("div");
    tabNav.className = "mb-3";

    const makeTabButton = (label) => {
        const btn = document.createElement("button");
        btn.className = "btn btn-secondary me-2";
        btn.textContent = label;
        return btn;
    };

    const tab1Btn = makeTabButton("Production Dashboard");
    tab1Btn.classList.replace("btn-secondary", "btn-primary");

    const tab2Btn = makeTabButton("Production Dashboard Update");
    const tab3Btn = makeTabButton("Weekly Report");
    const tab4Btn = makeTabButton("Daily & Shift Report");

    tabNav.appendChild(tab1Btn);
    tabNav.appendChild(tab2Btn);
    tabNav.appendChild(tab3Btn);
    tabNav.appendChild(tab4Btn);
    mainEl.appendChild(tabNav);

    //-------------------------------------------------------------
    // TAB PANES
    //-------------------------------------------------------------

    const tab1Pane = document.createElement("div");
    const tab2Pane = document.createElement("div");
    const tab3Pane = document.createElement("div");
    const tab4Pane = document.createElement("div");

    tab1Pane.style.display = "block";
    tab2Pane.style.display = "none";
    tab3Pane.style.display = "none";
    tab4Pane.style.display = "none";

    mainEl.appendChild(tab1Pane);
    mainEl.appendChild(tab2Pane);
    mainEl.appendChild(tab3Pane);
    mainEl.appendChild(tab4Pane);

    let active_tab = 1;

    function switchTab(tabNum) {
        active_tab = tabNum;

        tab1Pane.style.display = tabNum === 1 ? "block" : "none";
        tab2Pane.style.display = tabNum === 2 ? "block" : "none";
        tab3Pane.style.display = tabNum === 3 ? "block" : "none";
        tab4Pane.style.display = tabNum === 4 ? "block" : "none";

        const all = [tab1Btn, tab2Btn, tab3Btn, tab4Btn];
        all.forEach((b) => b.classList.replace("btn-primary", "btn-secondary"));
        all[tabNum - 1].classList.replace("btn-secondary", "btn-primary");

        const f = get_filters();
        if (f) {
            if (tabNum === 1) refresh_tab1(f);
            if (tabNum === 2) refresh_tab2(f);
            if (tabNum === 3) refresh_tab3(f);
            if (tabNum === 4) refresh_tab4(f);
        }
    }

    tab1Btn.onclick = () => switchTab(1);
    tab2Btn.onclick = () => switchTab(2);
    tab3Btn.onclick = () => switchTab(3);
    tab4Btn.onclick = () => switchTab(4);

    //-------------------------------------------------------------
    // COMPONENT HELPERS
    //-------------------------------------------------------------

    const makeCard = (title) => {
        const card = document.createElement("div");
        card.className = "frappe-card compact-card";
        card.style.padding = "8px";

        const hWrap = document.createElement("div");
        hWrap.style.display = "flex";
        hWrap.style.alignItems = "center";
        hWrap.style.justifyContent = "space-between";

        const h = document.createElement("div");
        h.className = "text-muted";
        h.style.marginBottom = "4px";
        h.textContent = title;
        hWrap.appendChild(h);

        card.appendChild(hWrap);
        return { card };
    };

    //-------------------------------------------------------------
    // REPORT RUNNER (Optimized + Cached)
    //-------------------------------------------------------------

    let reportCache = {};

    async function run_report(report_name, filters) {
        const key = report_name + JSON.stringify(filters);
        if (reportCache[key]) return reportCache[key];

        const res = await frappe.call({
            method: "frappe.desk.query_report.run",
            args: {
                report_name,
                filters,
                ignore_prepared_report: true,
            },
        });

        const msg = res.message || {};
        const data = {
            result: msg.result || [],
            columns: msg.columns || [],
            summary: msg.report_summary || [],
            html: msg.report_html || "",
        };

        reportCache[key] = data;
        return data;
    }

    //-------------------------------------------------------------
    // TAB 1 LAYOUT (CARDS + CHARTS + TABLES)
    //-------------------------------------------------------------

    const totalRow = document.createElement("div");
    totalRow.style.display = "flex";
    totalRow.style.gap = "20px";
    //-------------------------------------------------------------
    // TAB 1 — SUMMARY CARDS
    //-------------------------------------------------------------

    const totalBits = makeCard("Total BCM Tallies");
    const totalValue = document.createElement("div");
    totalValue.style.fontSize = "20px";
    totalValue.style.fontWeight = "bold";
    totalValue.id = "total-bcm";
    totalValue.textContent = "0";
    totalBits.card.appendChild(totalValue);

    const actualBcmBits = makeCard("Actual BCM (Survey + HP)");
    const actualBcmValue = document.createElement("div");
    actualBcmValue.id = "actual-bcm-survey";
    Object.assign(actualBcmValue.style, {
        fontSize: "20px",
        fontWeight: "bold",
        color: "#0047ab",
    });
    actualBcmValue.textContent = "0";
    actualBcmBits.card.appendChild(actualBcmValue);

    const varianceBits = makeCard("Survey Variance");
    const varianceValue = document.createElement("div");
    varianceValue.id = "survey-variance";
    Object.assign(varianceValue.style, {
        fontSize: "20px",
        fontWeight: "bold",
        color: "#cc0000",
    });
    varianceValue.textContent = "0";
    varianceBits.card.appendChild(varianceValue);

    const excavatorBits = makeCard("Overall Team Productivity per Hour");
    const excavatorValue = document.createElement("div");
    excavatorValue.id = "excavator-prod";
    excavatorValue.style.fontWeight = "bold";
    excavatorValue.textContent = "0 BCM/hr";
    excavatorBits.card.appendChild(excavatorValue);

    const dozerBits = makeCard("Overall Dozing Productivity per Hour");
    const dozerValue = document.createElement("div");
    dozerValue.id = "dozer-prod";
    dozerValue.style.fontWeight = "bold";
    dozerValue.textContent = "0 BCM/hr";
    dozerBits.card.appendChild(dozerValue);

    totalRow.appendChild(totalBits.card);
    totalRow.appendChild(actualBcmBits.card);
    totalRow.appendChild(varianceBits.card);
    totalRow.appendChild(excavatorBits.card);
    totalRow.appendChild(dozerBits.card);

    tab1Pane.appendChild(totalRow);

    //-------------------------------------------------------------
    // TAB 1 — CHART ROW
    //-------------------------------------------------------------

    let teamsChart = null;
    let dozingChart = null;

    const chartRow = document.createElement("div");
    chartRow.className = "row g-2";

    const chartCol1 = document.createElement("div");
    const chartCol2 = document.createElement("div");
    chartCol1.className = "col-lg-6";
    chartCol2.className = "col-lg-6";

    const teamsBits = makeCard("Production Shift Teams");
    const teamsMount = document.createElement("canvas");
    teamsMount.id = "chart-teams";
    teamsBits.card.appendChild(teamsMount);
    chartCol1.appendChild(teamsBits.card);

    const dozingBits = makeCard("Production Shift Dozing");
    const dozingMount = document.createElement("canvas");
    dozingMount.id = "chart-dozing";
    dozingBits.card.appendChild(dozingMount);
    chartCol2.appendChild(dozingBits.card);

    chartRow.appendChild(chartCol1);
    chartRow.appendChild(chartCol2);
    tab1Pane.appendChild(chartRow);

    //-------------------------------------------------------------
    // CHART RENDERERS — CLEANED & CHART.JS v4 READY
    //-------------------------------------------------------------

    async function render_chart_teams(filters) {
        const res = await run_report("Production Shift Teams", filters);
        const prodRes = await run_report("Productivity", filters);

        const parents = (res.result || []).filter((r) => {
            const name = (r.excavator || "").toLowerCase().trim();
            return (
                Number(r.indent || 0) === 0 &&
                name !== "" &&
                !name.includes("mtd actual bcm")
            );
        });

        const labels = parents.map((r) => r.excavator);
        const values = parents.map((r) => Number(r.bcms) || 0);

        const prodMap = {};
        prodRes.result.forEach((r) => {
            if (r.indent === 1) prodMap[r.label] = Number(r.productivity) || 0;
        });

        const productivity = labels.map((l) => prodMap[l] || 0);
        const threshold = labels.map(() => 220);

        const ctx = document.getElementById("chart-teams").getContext("2d");
        if (teamsChart) teamsChart.destroy();

        teamsChart = new Chart(ctx, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: "BCM",
                        data: values,
                        backgroundColor: "rgba(54,162,235,0.6)",
                        yAxisID: "yLeft",
                    },
                    {
                        label: "Productivity/hr",
                        data: productivity,
                        type: "line",
                        borderColor: "red",
                        yAxisID: "yRight",
                    },
                    {
                        label: "Threshold 220",
                        data: threshold,
                        type: "line",
                        borderColor: "green",
                        borderDash: [6, 4],
                        yAxisID: "yRight",
                    },
                ],
            },
            options: {
                responsive: true,
                interaction: { mode: "index", intersect: false },
                scales: {
                    yLeft: { type: "linear", position: "left" },
                    yRight: {
                        type: "linear",
                        position: "right",
                        grid: { drawOnChartArea: false },
                    },
                },
            },
        });

        return values.reduce((a, b) => a + b, 0);
    }

    async function render_chart_dozing(filters) {
        const res = await run_report("Production Shift Dozing", filters);
        const prodRes = await run_report("Productivity", filters);

        const parents = res.result.filter((r) => Number(r.indent || 0) === 0);

        const labels = parents.map((r) => r.label);
        const values = parents.map((r) => Number(r.bcm_hour) || 0);

        const prodMap = {};
        prodRes.result.forEach((r) => {
            if (r.indent === 1) prodMap[r.label] = Number(r.productivity) || 0;
        });

        const productivity = labels.map((l) => prodMap[l] || 0);

        const ctx = document.getElementById("chart-dozing").getContext("2d");
        if (dozingChart) dozingChart.destroy();

        dozingChart = new Chart(ctx, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: "BCM",
                        data: values,
                        backgroundColor: "rgba(54,162,235,0.6)",
                        yAxisID: "yLeft",
                    },
                    {
                        label: "Productivity/hr",
                        data: productivity,
                        type: "line",
                        borderColor: "red",
                        yAxisID: "yRight",
                    },
                ],
            },
            options: {
                responsive: true,
                interaction: { mode: "index", intersect: false },
                scales: {
                    yLeft: { type: "linear", position: "left" },
                    yRight: {
                        type: "linear",
                        position: "right",
                        grid: { drawOnChartArea: false },
                    },
                },
            },
        });

        return values.reduce((a, b) => a + b, 0);
    }
    //-------------------------------------------------------------
    // GENERIC TABLE RENDERER (Optimized)
    //-------------------------------------------------------------

    async function render_table(report_name, filters, selector, parentEl, collapsible = false) {
        const res = await run_report(report_name, filters);
        const rows = res.result || [];
        const cols = res.columns || [];

        const mount = parentEl.querySelector(selector);
        if (!rows.length) {
            mount.innerHTML = '<div class="text-muted">No data</div>';
            return;
        }

        const thead = cols.map(c => `<th>${c.label}</th>`).join("");

        const tbody = rows.map(r => {
            if (!collapsible) {
                return `<tr>${cols.map(c => `<td>${r[c.fieldname] ?? ""}</td>`).join("")}</tr>`;
            }

            const indent = Number(r.indent || 0);
            const isParent = indent === 0;

            return `
                <tr data-indent="${indent}" 
                    class="${isParent ? "group-row" : "child-row"}"
                    style="${indent > 0 ? "display:none;" : ""}">
                    ${cols.map((c, i) => {
                        const value = r[c.fieldname] ?? "";
                        const pad = i === 0 ? `padding-left:${indent * 20}px;` : "";
                        const bold = isParent ? "font-weight:600;" : "";
                        const clickable = i === 0 && isParent ? 'class="toggle-cell"' : "";
                        return `<td style="${pad}${bold}" ${clickable}>${value}</td>`;
                    }).join("")}
                </tr>`;
        }).join("");

        mount.innerHTML = `
            <table class="table table-bordered" style="width:100%">
                <thead><tr>${thead}</tr></thead>
                <tbody>${tbody}</tbody>
            </table>
        `;

        // Collapsible rows
        if (collapsible) {
            mount.querySelectorAll(".toggle-cell").forEach(cell => {
                cell.style.cursor = "pointer";
                cell.addEventListener("click", () => {
                    const row = cell.parentElement;
                    const lvl = Number(row.dataset.indent);

                    let next = row.nextElementSibling;
                    let show = false;

                    while (next && Number(next.dataset.indent) > lvl) {
                        if (next.style.display === "none") { show = true; break; }
                        next = next.nextElementSibling;
                    }

                    next = row.nextElementSibling;
                    while (next && Number(next.dataset.indent) > lvl) {
                        next.style.display = show ? "" : "none";
                        next = next.nextElementSibling;
                    }
                });
            });
        }
    }

    //-------------------------------------------------------------
    // MONTHLY PRODUCTION RENDERER
    //-------------------------------------------------------------

    async function render_monthly_production(filters, selector, parentEl) {
        const res = await run_report("Monthly Production", filters);

        const mount = parentEl.querySelector(selector);

        if (res.html) {
            mount.innerHTML = res.html;
            return;
        }

        if (!res.result.length) {
            mount.innerHTML = '<div class="text-muted">No Monthly Production data found.</div>';
            return;
        }

        const cols = res.columns;
        const rows = res.result;

        const thead = cols.map(c => `<th>${c.label}</th>`).join("");
        const tbody = rows.map(r =>
            `<tr>${cols.map(c => `<td>${r[c.fieldname] ?? ""}</td>`).join("")}</tr>`
        ).join("");

        mount.innerHTML = `
            <table class="table table-bordered table-sm">
                <thead><tr>${thead}</tr></thead>
                <tbody>${tbody}</tbody>
            </table>`;
    }

    //-------------------------------------------------------------
    // WEEKLY REPORT RENDERER
    //-------------------------------------------------------------

    async function render_weekly_report(filters, selector, parentEl) {
        const res = await run_report("Weekly Report", filters);
        const mount = parentEl.querySelector(selector);

        if (res.html) {
            mount.innerHTML = res.html;
            return;
        }

        if (!res.result.length) {
            mount.innerHTML = '<div class="text-muted">No Weekly Report data</div>';
            return;
        }

        const cols = res.columns;
        const rows = res.result;

        const thead = cols.map(c => `<th>${c.label}</th>`).join("");
        const tbody = rows.map(r =>
            `<tr>${cols.map(c => `<td>${r[c.fieldname] ?? ""}</td>`).join("")}</tr>`
        ).join("");

        mount.innerHTML = `
            <table class="table table-bordered">
                <thead><tr>${thead}</tr></thead>
                <tbody>${tbody}</tbody>
            </table>`;
    }

    //-------------------------------------------------------------
    // DAILY REPORT RENDERER
    //-------------------------------------------------------------

    async function render_daily_report(filters, selector, parentEl) {
        const res = await run_report("Daily Reporting", filters);
        const mount = parentEl.querySelector(selector);

        if (res.html) {
            mount.innerHTML = res.html;
            return;
        }

        if (!res.result.length) {
            mount.innerHTML = '<div class="text-muted">No Daily Report data</div>';
            return;
        }

        const cols = res.columns;
        const rows = res.result;

        const thead = cols.map(c => `<th>${c.label}</th>`).join("");
        const tbody = rows.map(r =>
            `<tr>${cols.map(c => `<td>${r[c.fieldname] ?? ""}</td>`).join("")}</tr>`
        ).join("");

        mount.innerHTML = `
            <table class="table table-bordered">
                <thead><tr>${thead}</tr></thead>
                <tbody>${tbody}</tbody>
            </table>`;
    }

    //-------------------------------------------------------------
    // CHILD TABLE RENDERER (TAB 2)
    //-------------------------------------------------------------

    function render_child_table(rows, cols, parentLabel, selector, parentEl) {
        const parentIndex = rows.findIndex(
            r => r.label?.toLowerCase().includes(parentLabel.toLowerCase()) &&
                 Number(r.indent || 0) === 0
        );

        let children = [];
        if (parentIndex !== -1) {
            for (let i = parentIndex + 1; i < rows.length; i++) {
                if (Number(rows[i].indent || 0) === 0) break;
                children.push(rows[i]);
            }
        }

        const mount = parentEl.querySelector(selector);

        if (!children.length) {
            mount.innerHTML = `<div class="text-muted">No ${parentLabel} data</div>`;
            return;
        }

        const thead = cols.map(c => `<th>${c.label}</th>`).join("");
        const tbody = children.map(r =>
            `<tr>${cols.map(c => `<td>${r[c.fieldname] ?? ""}</td>`).join("")}</tr>`
        ).join("");

        mount.innerHTML = `
            <table class="table table-bordered" style="width:100%">
                <thead><tr>${thead}</tr></thead>
                <tbody>${tbody}</tbody>
            </table>`;
    }

    //-------------------------------------------------------------
    // TAB 1 REFRESH
    //-------------------------------------------------------------

    async function refresh_tab1(filters) {
        await render_chart_teams(filters);
        await render_chart_dozing(filters);

        const matRes = await run_report("Production Shift Material", filters);

        let mtdTallies = 0;
        if (matRes.result.length) {
            const row = matRes.result.find(r =>
                r.mat_type?.toLowerCase().includes("mtd tallies bcm")
            );
            if (row) mtdTallies = Number(row.total_bcm) || 0;
        }
        document.getElementById("total-bcm").textContent = mtdTallies.toLocaleString();

        const prodRes = await run_report("Productivity", filters);

        let excavatorProd = 0;
        let dozerProd = 0;
        prodRes.result.forEach(r => {
            const label = r.label?.toLowerCase() || "";
            if (label.includes("excavator")) excavatorProd += Number(r.productivity) || 0;
            if (label.includes("dozer")) dozerProd += Number(r.productivity) || 0;
        });

        document.getElementById("excavator-prod").textContent =
            `${excavatorProd.toFixed(2)} BCM/hr`;
        document.getElementById("dozer-prod").textContent =
            `${dozerProd.toFixed(2)} BCM/hr`;

        await render_table("Production Shift Material", filters, "#tbl-material", tab1Pane, true);
        await render_table("Production Shift Location", filters, "#tbl-location", tab1Pane, true);
        await render_table("Production Shift Teams", filters, "#tbl-teams", tab1Pane, true);
        await render_table("Production Shift Dozing", filters, "#tbl-dozing", tab1Pane, true);
        await render_monthly_production(filters, "#tbl-monthly-production", tab1Pane);
        await render_table("Productivity", filters, "#tbl-productivity", tab1Pane, true);

        // Variance
        const teamsRes = await run_report("Production Shift Teams", filters);
        let actualBcm = 0;

        if (teamsRes.summary.length) {
            const bcmRow = teamsRes.summary.find(s =>
                s.label?.toLowerCase().includes("mtd actual bcm")
            );
            if (bcmRow) {
                actualBcm = Number(String(bcmRow.value).replace(/,/g, "")) || 0;
            }
        }

        document.getElementById("actual-bcm-survey").textContent =
            actualBcm.toLocaleString();

        const totalBcm = Number(
            document.getElementById("total-bcm").textContent.replace(/,/g, "")
        ) || 0;

        const variance = actualBcm - totalBcm;
        const varianceEl = document.getElementById("survey-variance");

        varianceEl.textContent = variance.toLocaleString();
        varianceEl.style.color = variance >= 0 ? "#006600" : "#cc0000";
    }

    //-------------------------------------------------------------
    // TAB 2 REFRESH
    //-------------------------------------------------------------

    async function refresh_tab2(filters) {
        await render_table("Production Performance", filters,
            "#tbl-performance", tab2Pane);

        const prodRes = await run_report("Productivity", filters);

        render_child_table(prodRes.result, prodRes.columns,
            "excavator", "#tbl-excavators", tab2Pane);

        render_child_table(prodRes.result, prodRes.columns,
            "dozer", "#tbl-dozers", tab2Pane);
    }

    //-------------------------------------------------------------
    // TAB 3 REFRESH
    //-------------------------------------------------------------

    async function refresh_tab3(filters) {
        await render_weekly_report(filters, "#tbl-weekly", tab3Pane);
    }

    //-------------------------------------------------------------
    // TAB 4 REFRESH
    //-------------------------------------------------------------

    async function refresh_tab4(filters) {
        await render_daily_report(filters, "#tbl-daily", tab4Pane);
    }
    //-------------------------------------------------------------
    // FILTER EXTRACTION
    //-------------------------------------------------------------

    function get_filters() {
        const start_v = start.get_value();
        const end_v = end.get_value();
        const site_v = site.get_value();
        const monthly_v = monthly_production.get_value();
        const shift_v = shift.get_value();

        if (!start_v || !end_v || !site_v || !monthly_v) return null;

        const f = {
            start_date: start_v,
            end_date: end_v,
            site: site_v,
            monthly_production: monthly_v,
        };

        if (shift_v) f.shift = shift_v;
        return f;
    }

    //-------------------------------------------------------------
    // GLOBAL REFRESH FUNCTION (FIXED)
    //-------------------------------------------------------------

    async function refresh_all(user_clicked = false) {
        const f = get_filters();
        if (!f) return;

        // Reset cache per full refresh
        reportCache = {};

        if (active_tab === 1) await refresh_tab1(f);
        if (active_tab === 2) await refresh_tab2(f);
        if (active_tab === 3) await refresh_tab3(f);
        if (active_tab === 4) await refresh_tab4(f);
    }

    //-------------------------------------------------------------
    // DEFAULT DATES + CHART.JS LOADER
    //-------------------------------------------------------------

    const today = frappe.datetime.get_today();
    const week_ago = frappe.datetime.add_days(today, -6);

    start.set_value(week_ago);
    end.set_value(today);

    // Load Chart.js v4
    const script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/npm/chart.js";
    document.head.appendChild(script);

    script.onload = () => {
        refresh_all();

        // Auto-refresh every 5 minutes
        setInterval(async () => {
            const f = get_filters();
            if (!f) return;

            // No caching between cycles
            reportCache = {};

            if (active_tab === 1) await refresh_tab1(f);
            if (active_tab === 2) await refresh_tab2(f);
            if (active_tab === 3) await refresh_tab3(f);
            if (active_tab === 4) await refresh_tab4(f);
        }, 300000);
    };

    //-------------------------------------------------------------
    // INLINE COMPACT CSS
    //-------------------------------------------------------------

    const style = document.createElement("style");
    style.innerHTML = `
        .compact-card { padding: 6px !important; }
        .compact-card table { font-size: 11px; }
        .compact-card th, .compact-card td { padding: 2px 4px !important; }
        #production-dashboard .form-control {
            padding: 2px 4px !important;
            font-size: 12px;
            height: auto;
        }
    `;
    document.head.appendChild(style);
};
