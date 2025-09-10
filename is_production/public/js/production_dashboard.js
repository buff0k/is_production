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

  // 🔑 Updated to include summary
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

  // Row 1: Total BCM block
  const totalRow = document.createElement('div');
  const totalBits = makeCard('Total BCM');
  const totalValue = document.createElement('div');
  totalValue.style.fontSize = '22px';
  totalValue.style.fontWeight = 'bold';
  totalValue.id = 'total-bcm';
  totalValue.textContent = '0';
  totalBits.card.appendChild(totalValue);
  totalRow.appendChild(totalBits.card);
  mainEl.appendChild(totalRow);

  // Row 2: Charts (Teams + Dozing)
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

  // -------- Renderers --------
  let teamsChart, dozingChart;

  async function render_chart_teams(filters) {
    const res = await run_report('Production Shift Teams', filters);
    const parents = (res.result || []).filter(r => Number(r.indent || 0) === 0);
    const labels = parents.map(r => r.excavator || 'Unknown');
    const values = parents.map(r => Number(r.bcms) || 0);
    const total = values.reduce((a,b) => a+b, 0);

    // 🔑 Show report_summary if available, else fallback to manual total
    if (res.summary && res.summary.length) {
      setTitleExtra(teamsBits.extraEl, res.summary);
    } else {
      setTitleExtra(teamsBits.extraEl, [{ label: 'Total BCM', value: total }]);
    }

    if (!labels.length) return 0;

    const chartData = { labels, datasets: [{ name: 'BCM', values }] };
    if (!teamsChart) {
      teamsChart = new frappe.Chart(teamsMount, {
        data: chartData,
        type: 'bar',
        height: 300,
        barOptions: { spaceRatio: 0.3 },
        valuesOverPoints: 1
      });
    } else {
      teamsChart.update(chartData);
    }
    return total;
  }

  async function render_chart_dozing(filters) {
    const res = await run_report('Production Shift Dozing', filters);
    const parents = (res.result || []).filter(r => Number(r.indent || 0) === 0);
    const labels = parents.map(r => r.label || 'Unknown');
    const values = parents.map(r => Number(r.bcm_hour) || 0);
    const total = values.reduce((a,b) => a+b, 0);

    if (res.summary && res.summary.length) {
      setTitleExtra(dozingBits.extraEl, res.summary);
    } else {
      setTitleExtra(dozingBits.extraEl, [{ label: 'Total BCM', value: total }]);
    }

    if (!labels.length) return 0;

    const chartData = { labels, datasets: [{ name: 'BCM', values }] };
    if (!dozingChart) {
      dozingChart = new frappe.Chart(dozingMount, {
        data: chartData,
        type: 'bar',
        height: 300,
        barOptions: { spaceRatio: 0.3 },
        valuesOverPoints: 1
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

    // render table
    mount.innerHTML = `
      <table class="table table-bordered" style="width:100%">
        <thead><tr>${thead}</tr></thead>
        <tbody>${tbody}</tbody>
      </table>
    `;

    // append report summary under table
    if (res.summary && res.summary.length) {
      const summaryHtml = res.summary.map(s =>
        `<div><b>${s.label}:</b> ${s.value}</div>`
      ).join('');
      mount.insertAdjacentHTML('beforeend', `<div class="mt-2">${summaryHtml}</div>`);
    }

    // toggle expand/collapse
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

    const filters = {};
    if (start_v) filters.start_date = start_v;
    if (end_v) filters.end_date = end_v;
    if (site_v) filters.site = site_v;
    if (shift_v) filters.shift = shift_v;

    const teamsTotal = await render_chart_teams(filters) || 0;
    const dozingTotal = await render_chart_dozing(filters) || 0;

    // ✅ Format grand total with thousand separator
    document.getElementById('total-bcm').textContent =
      (teamsTotal + dozingTotal).toLocaleString();

    await render_table('Production Shift Material', filters, '#tbl-material');
    await render_table('Production Shift Location', filters, '#tbl-location');
    await render_table('Production Shift Teams', filters, '#tbl-teams');
    await render_table('Production Shift Dozing', filters, '#tbl-dozing');
  }

  // -------- Defaults --------
  const today = frappe.datetime.get_today();
  const week_ago = frappe.datetime.add_days(today, -6);
  start.set_value(week_ago);
  end.set_value(today);

  // Run immediately on load
  refresh_all();

  // Auto-refresh every 5 minutes
  setInterval(() => {
    refresh_all();
  }, 300000);
};
