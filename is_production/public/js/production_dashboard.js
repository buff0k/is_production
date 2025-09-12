// Copyright (c) 2025, Isambane Mining (Pty) Ltd 
// For license information, please see license.txt

frappe.pages['production-dashboard'].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: 'Production Dashboard',
    single_column: true
  });

  const mainEl = page.main.get(0);

  // -------- Filters --------
  const start = page.add_field({
    fieldname: 'start_date', label: 'Start Date',
    fieldtype: 'Date', reqd: 0
  });
  const end = page.add_field({
    fieldname: 'end_date', label: 'End Date',
    fieldtype: 'Date', reqd: 0
  });
  const site = page.add_field({
    fieldname: 'site', label: 'Site',
    fieldtype: 'Link', options: 'Location', reqd: 0
  });
  const shift = page.add_field({
    fieldname: 'shift', label: 'Shift',
    fieldtype: 'Select',
    options: ["", "Day", "Night", "Morning", "Afternoon"], // blank = all
    reqd: 0
  });

  page.set_primary_action(__('Run'), () => refresh_all(true));

  // -------- Helpers --------
  const makeCard = (title) => {
    const card = document.createElement('div');
    card.className = 'frappe-card';
    card.style.padding = '12px';

    const hWrap = document.createElement('div');
    hWrap.style.display = 'flex';
    hWrap.style.alignItems = 'center';
    hWrap.style.justifyContent = 'space-between';

    const h = document.createElement('div');
    h.className = 'text-muted';
    h.style.marginBottom = '6px';
    h.textContent = title;

    const hExtra = document.createElement('div');
    hExtra.className = 'text-muted';
    hExtra.style.marginBottom = '6px';
    hExtra.style.marginLeft = '12px';

    hWrap.appendChild(h);
    hWrap.appendChild(hExtra);
    card.appendChild(hWrap);

    return { card, titleEl: h, extraEl: hExtra };
  };

  const setTitleExtra = (extraEl, parts) => {
    while (extraEl.firstChild) extraEl.removeChild(extraEl.firstChild);
    (parts || [])
      .filter(p => p.value !== undefined && p.value !== null && p.value !== '')
      .forEach(p => {
        const span = document.createElement('span');
        span.style.marginLeft = '12px';
        const b = document.createElement('b');
        b.textContent = (p.label || '') + ':';
        span.appendChild(b);
        span.appendChild(document.createTextNode(' ' + p.value));
        extraEl.appendChild(span);
      });
  };

  const run_report = (report_name, filters) =>
    frappe.call({
      method: 'frappe.desk.query_report.run',
      args: { report_name, filters, ignore_prepared_report: true }
    }).then(r => {
      const msg = r.message || {};
      return {
        result: msg.result || [],
        columns: msg.columns || [],
        summary: msg.report_summary || []
      };
    });

  // -------- Layout --------

  // Row 1: Total BCM + Productivity KPIs
  const totalRow = document.createElement('div');
  totalRow.style.display = 'flex';
  totalRow.style.gap = '20px';

  const totalBits = makeCard('Total BCM');
  const totalValue = document.createElement('div');
  totalValue.style.fontSize = '22px';
  totalValue.style.fontWeight = 'bold';
  totalValue.id = 'total-bcm';
  totalValue.textContent = '0';
  totalBits.card.appendChild(totalValue);

  const excavatorBits = makeCard('Overall Team Productivity per Hour');
  const excavatorValue = document.createElement('div');
  excavatorValue.style.fontSize = '18px';
  excavatorValue.style.fontWeight = 'bold';
  excavatorValue.id = 'excavator-prod';
  excavatorValue.textContent = '0 BCM/hr';
  excavatorBits.card.appendChild(excavatorValue);

  const dozerBits = makeCard('Overall Dozing Productivity per Hour');
  const dozerValue = document.createElement('div');
  dozerValue.style.fontSize = '18px';
  dozerValue.style.fontWeight = 'bold';
  dozerValue.id = 'dozer-prod';
  dozerValue.textContent = '0 BCM/hr';
  dozerBits.card.appendChild(dozerValue);

  totalRow.appendChild(totalBits.card);
  totalRow.appendChild(excavatorBits.card);
  totalRow.appendChild(dozerBits.card);

  mainEl.appendChild(totalRow);

  // Row 2: Charts
  const chartRow = document.createElement('div');
  chartRow.className = 'row g-3';

  const chartCol1 = document.createElement('div'); chartCol1.className = 'col-lg-6';
  const chartCol2 = document.createElement('div'); chartCol2.className = 'col-lg-6';

  const teamsBits = makeCard('Production Shift Teams');
  const teamsMount = document.createElement('div'); teamsMount.id = 'chart-teams';
  teamsBits.card.appendChild(teamsMount); chartCol1.appendChild(teamsBits.card);

  const dozingBits = makeCard('Production Shift Dozing');
  const dozingMount = document.createElement('div'); dozingMount.id = 'chart-dozing';
  dozingBits.card.appendChild(dozingMount); chartCol2.appendChild(dozingBits.card);

  chartRow.appendChild(chartCol1); chartRow.appendChild(chartCol2);
  mainEl.appendChild(chartRow);

  // Row 3: Material + Location
  const row3 = document.createElement('div'); row3.className = 'row g-3';
  const matCol = document.createElement('div'); matCol.className = 'col-lg-6';
  const locCol = document.createElement('div'); locCol.className = 'col-lg-6';

  const matBits = makeCard('Production Shift Material');
  const matMount = document.createElement('div'); matMount.id = 'tbl-material';
  matBits.card.appendChild(matMount); matCol.appendChild(matBits.card);

  const locBits = makeCard('Production Shift Location');
  const locMount = document.createElement('div'); locMount.id = 'tbl-location';
  locBits.card.appendChild(locMount); locCol.appendChild(locBits.card);

  row3.appendChild(matCol); row3.appendChild(locCol); mainEl.appendChild(row3);

  // Row 4: Teams + Dozing tables
  const row4 = document.createElement('div'); row4.className = 'row g-3';
  const teamsCol = document.createElement('div'); teamsCol.className = 'col-lg-6';
  const dozingCol = document.createElement('div'); dozingCol.className = 'col-lg-6';

  const teamsTblBits = makeCard('Production Shift Teams (Table)');
  const teamsTblMount = document.createElement('div'); teamsTblMount.id = 'tbl-teams';
  teamsTblBits.card.appendChild(teamsTblMount); teamsCol.appendChild(teamsTblBits.card);

  const dozingTblBits = makeCard('Production Shift Dozing (Table)');
  const dozingTblMount = document.createElement('div'); dozingTblMount.id = 'tbl-dozing';
  dozingTblBits.card.appendChild(dozingTblMount); dozingCol.appendChild(dozingTblBits.card);

  row4.appendChild(teamsCol); row4.appendChild(dozingCol); mainEl.appendChild(row4);

  // Row 5: Productivity table
  const row5 = document.createElement('div');
  const prodBits = makeCard('Productivity Report');
  const prodMount = document.createElement('div'); prodMount.id = 'tbl-productivity';
  prodBits.card.appendChild(prodMount); row5.appendChild(prodBits.card);
  mainEl.appendChild(row5);

  // -------- Renderers --------
  let teamsChart, dozingChart;

  async function render_chart_teams(filters) {
    const res = await run_report('Production Shift Teams', filters);
    const prodRes = await run_report('Productivity', filters);

    const parents = (res.result || []).filter(r => Number(r.indent || 0) === 0);
    const labels = parents.map(r => r.excavator || 'Unknown');
    const values = parents.map(r => Number(r.bcms) || 0);
    const total = values.reduce((a, b) => a + b, 0);

    const prodMap = {};
    (prodRes.result || []).forEach(r => {
      if (r.indent === 1) prodMap[r.label] = Number(r.productivity) || 0;
    });
    const productivityVals = labels.map(l => prodMap[l] || 0);
    const thresholdVals = Array(labels.length).fill(220);

    const chartData = {
      labels,
      datasets: [
        { name: 'BCM', chartType: 'bar', values, axis: 'left' },
        { name: 'Productivity/HR', chartType: 'line', values: productivityVals, axis: 'right' },
        { name: 'Threshold 220', chartType: 'line', values: thresholdVals, axis: 'right', color: 'red' }
      ]
    };

    if (!teamsChart) {
      teamsChart = new frappe.Chart(teamsMount, {
        data: chartData,
        type: 'axis-mixed',
        height: 300,
        barOptions: { spaceRatio: 0.3 },
        valuesOverPoints: 1,
        lineOptions: { dotSize: 4, regionFill: 1, hideLine: 0, hideDots: 0 },
        axisOptions: {
          xAxisMode: 'tick',
          xIsSeries: true,
          yAxis: [
            { title: "BCM", position: 'left', show: true },
            { title: "Output/Hr", position: 'right', show: true }
          ]
        }
      });
    } else {
      teamsChart.update(chartData);
    }
    return total;
  }

  async function render_chart_dozing(filters) {
    const res = await run_report('Production Shift Dozing', filters);
    const prodRes = await run_report('Productivity', filters);

    const parents = (res.result || []).filter(r => Number(r.indent || 0) === 0);
    const labels = parents.map(r => r.label || 'Unknown');
    const values = parents.map(r => Number(r.bcm_hour) || 0);
    const total = values.reduce((a, b) => a + b, 0);

    const prodMap = {};
    (prodRes.result || []).forEach(r => {
      if (r.indent === 1) prodMap[r.label] = Number(r.productivity) || 0;
    });
    const productivityVals = labels.map(l => prodMap[l] || 0);

    const chartData = {
      labels,
      datasets: [
        { name: 'BCM', chartType: 'bar', values, axis: 'left' },
        { name: 'Productivity/HR', chartType: 'line', values: productivityVals, axis: 'right' }
      ]
    };

    if (!dozingChart) {
      dozingChart = new frappe.Chart(dozingMount, {
        data: chartData,
        type: 'axis-mixed',
        height: 300,
        barOptions: { spaceRatio: 0.3 },
        valuesOverPoints: 1,
        lineOptions: { dotSize: 4, regionFill: 1, hideLine: 0, hideDots: 0 },
        axisOptions: {
          xAxisMode: 'tick',
          xIsSeries: true,
          yAxis: [
            { title: "BCM", position: 'left', show: true },
            { title: "Output/Hr", position: 'right', show: true }
          ]
        }
      });
    } else {
      dozingChart.update(chartData);
    }
    return total;
  }

  // -------- Collapsible Table Renderer --------
  async function render_table(report_name, filters, mountSelector) {
    const res = await run_report(report_name, filters);
    const rows = res.result || [];
    const cols = res.columns || [];
    const mount = mainEl.querySelector(mountSelector);

    if (!rows.length) {
      mount.innerHTML = '<div class="text-muted">No data</div>';
      return;
    }

    const thead = cols.map(c => `<th>${c.label}</th>`).join('');
    const tbody = rows.map(r => {
      const indent = Number(r.indent || 0);
      const isParent = indent === 0;
      return `
        <tr data-indent="${indent}" class="${isParent ? 'group-row' : 'child-row'}" style="${indent > 0 ? 'display:none;' : ''}">
          ${cols.map((c, i) => {
            const v = r[c.fieldname] ?? '';
            const pad = (i === 0 ? `padding-left:${indent * 20}px;` : '');
            const bold = (isParent ? 'font-weight:600;' : '');
            const clickable = (i === 0 && isParent) ? 'class="toggle-cell"' : '';
            return `<td style="${pad}${bold}" ${clickable}>${v}</td>`;
          }).join('')}
        </tr>
      `;
    }).join('');

    mount.innerHTML = `
      <table class="table table-bordered" style="width:100%">
        <thead><tr>${thead}</tr></thead>
        <tbody>${tbody}</tbody>
      </table>
    `;

    // restore expand/collapse
    mount.querySelectorAll('.toggle-cell').forEach(cell => {
      cell.style.cursor = 'pointer';
      cell.addEventListener('click', () => {
        const row = cell.parentElement;
        const rowIndent = Number(row.dataset.indent);
        let next = row.nextElementSibling;
        let show = false;

        while (next && Number(next.dataset.indent) > rowIndent) {
          if (next.style.display === 'none') { show = true; break; }
          next = next.nextElementSibling;
        }

        next = row.nextElementSibling;
        while (next && Number(next.dataset.indent) > rowIndent) {
          next.style.display = show ? '' : 'none';
          next = next.nextElementSibling;
        }
      });
    });
  }

  // -------- Refresh Flow --------
  async function refresh_all() {
    const start_v = start.get_value();
    const end_v = end.get_value();
    const site_v = site.get_value();
    const shift_v = shift.get_value();

    if (!start_v || !end_v || !site_v) return;

    const filters = { start_date: start_v, end_date: end_v, site: site_v };
    if (shift_v) filters.shift = shift_v;

    const teamsTotal = await render_chart_teams(filters) || 0;
    const dozingTotal = await render_chart_dozing(filters) || 0;

    document.getElementById('total-bcm').textContent =
      (teamsTotal + dozingTotal).toLocaleString();

    // ✅ Get productivity totals from Productivity report
    const prodRes = await run_report('Productivity', filters);
    const prodParents = (prodRes.result || []).filter(r => Number(r.indent || 0) === 0);

    let excavatorRow = prodParents.find(r => r.label === "Excavator");
    let dozerRow = prodParents.find(r => r.label === "Dozer");

    let excavatorProd = (excavatorRow && excavatorRow.working_hours > 0)
      ? (Number(excavatorRow.output.replace(/,/g,'')) / excavatorRow.working_hours).toFixed(2)
      : 0;

    let dozerProd = (dozerRow && dozerRow.working_hours > 0)
      ? (Number(dozerRow.output.replace(/,/g,'')) / dozerRow.working_hours).toFixed(2)
      : 0;

    document.getElementById('excavator-prod').textContent = excavatorProd + " BCM/hr";
    document.getElementById('dozer-prod').textContent = dozerProd + " BCM/hr";

    await render_table('Production Shift Material', filters, '#tbl-material');
    await render_table('Production Shift Location', filters, '#tbl-location');
    await render_table('Production Shift Teams', filters, '#tbl-teams');
    await render_table('Production Shift Dozing', filters, '#tbl-dozing');
    await render_table('Productivity', filters, '#tbl-productivity');
  }

  // -------- Defaults --------
  const today = frappe.datetime.get_today();
  const week_ago = frappe.datetime.add_days(today, -6);
  start.set_value(week_ago);
  end.set_value(today);

  refresh_all();
  setInterval(() => refresh_all(), 300000);
};


