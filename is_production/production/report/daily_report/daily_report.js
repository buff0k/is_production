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

  // NEW FILTER: Monthly Production Planning 
  const monthly_production = page.add_field({ 
    fieldname: 'monthly_production', label: 'Monthly Production', 
    fieldtype: 'Link', options: 'Monthly Production Planning', reqd: 1 
  }); 

  // Dynamically filter monthly_production by selected site, sorted Descending 
  monthly_production.get_query = () => { 
    const site_val = site.get_value(); 
    if (!site_val) { 
      frappe.msgprint(__('Please select a Site first.')); 
      return { filters: [] }; 
    } 
    return { 
      filters: { location: site_val }, 
      order_by: 'creation desc' 
    }; 
  }; 

  const shift = page.add_field({ 
    fieldname: 'shift', label: 'Shift', 
    fieldtype: 'Select', 
    options: ["", "Day", "Night", "Morning", "Afternoon"], // blank = all 
    reqd: 0 
  }); 

  page.set_primary_action(__('Run'), () => refresh_all(true)); 

  // -------- Tabs (manual toggle) -------- 
  const tabNav = document.createElement('div'); 
  tabNav.className = 'mb-3'; 

  const tab1Btn = document.createElement('button'); 
  tab1Btn.textContent = 'Production Dashboard'; 
  tab1Btn.className = 'btn btn-primary me-2'; 

  const tab2Btn = document.createElement('button'); 
  tab2Btn.textContent = 'Production Dashboard Weekly'; 
  tab2Btn.className = 'btn btn-secondary'; 

  tabNav.appendChild(tab1Btn); 
  tabNav.appendChild(tab2Btn); 
  mainEl.appendChild(tabNav); 

  const tab1Pane = document.createElement('div'); 
  tab1Pane.style.display = 'block'; // default visible 
  mainEl.appendChild(tab1Pane); 

  const tab2Pane = document.createElement('div'); 
  tab2Pane.style.display = 'none'; // hidden initially 
  mainEl.appendChild(tab2Pane); 

  // Toggle logic 
  tab1Btn.onclick = () => { 
    tab1Pane.style.display = 'block'; 
    tab2Pane.style.display = 'none'; 
    tab1Btn.className = 'btn btn-primary me-2'; 
    tab2Btn.className = 'btn btn-secondary'; 
  }; 
  tab2Btn.onclick = () => { 
    tab1Pane.style.display = 'none'; 
    tab2Pane.style.display = 'block'; 
    tab1Btn.className = 'btn btn-secondary me-2'; 
    tab2Btn.className = 'btn btn-primary'; 
  }; 

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
    hWrap.appendChild(h); 
    card.appendChild(hWrap); 
    return { card }; 
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

  // ============================================================== 
  // TAB 1: Original Dashboard 
  // ============================================================== 

  // Row 1: Total BCM + Productivity KPIs 
  const totalRow = document.createElement('div'); 
  totalRow.style.display = 'flex'; 
  totalRow.style.gap = '20px'; 

  const totalBits = makeCard('Total BCM Tallies'); 
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

  tab1Pane.appendChild(totalRow); 

  // Row 2: Charts 
  const chartRow = document.createElement('div'); 
  chartRow.className = 'row g-3'; 
  const chartCol1 = document.createElement('div'); chartCol1.className = 'col-lg-6'; 
  const chartCol2 = document.createElement('div'); chartCol2.className = 'col-lg-6'; 
  const teamsBits = makeCard('Production Shift Teams'); 
  const teamsMount = document.createElement('canvas'); teamsMount.id = 'chart-teams'; 
  teamsBits.card.appendChild(teamsMount); chartCol1.appendChild(teamsBits.card); 
  const dozingBits = makeCard('Production Shift Dozing'); 
  const dozingMount = document.createElement('canvas'); dozingMount.id = 'chart-dozing'; 
  dozingBits.card.appendChild(dozingMount); chartCol2.appendChild(dozingBits.card); 
  chartRow.appendChild(chartCol1); chartRow.appendChild(chartCol2); 
  tab1Pane.appendChild(chartRow); 

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
  row3.appendChild(matCol); row3.appendChild(locCol); tab1Pane.appendChild(row3); 

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
  row4.appendChild(teamsCol); row4.appendChild(dozingCol); tab1Pane.appendChild(row4); 

  // Row 5: Productivity table 
  const row5 = document.createElement('div'); 
  const prodBits = makeCard('Productivity Report'); 
  const prodMount = document.createElement('div'); prodMount.id = 'tbl-productivity'; 
  prodBits.card.appendChild(prodMount); row5.appendChild(prodBits.card); 
  tab1Pane.appendChild(row5); 

  // ============================================================== 
  // TAB 2: Production Performance + Machine Productivity 
  // ============================================================== 
  const perfTblBits = makeCard('Production Performance Report'); 
  const perfTblMount = document.createElement('div'); perfTblMount.id = 'tbl-performance'; 
  perfTblBits.card.appendChild(perfTblMount); 
  tab2Pane.appendChild(perfTblBits.card); 

  // Excavator Productivity table 
  const excavTblBits = makeCard('Excavator Productivity (Machines)'); 
  const excavTblMount = document.createElement('div'); excavTblMount.id = 'tbl-excavators'; 
  excavTblBits.card.appendChild(excavTblMount); 
  tab2Pane.appendChild(excavTblBits.card); 

  // Dozer Productivity table 
  const dozerTblBits = makeCard('Dozer Productivity (Machines)'); 
  const dozerTblMount = document.createElement('div'); dozerTblMount.id = 'tbl-dozers'; 
  dozerTblBits.card.appendChild(dozerTblMount); 
  tab2Pane.appendChild(dozerTblBits.card); 

  // -------- Chart.js Setup -------- 
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
    const ctx = document.getElementById('chart-teams').getContext('2d'); 
    if (teamsChart) teamsChart.destroy(); 
    teamsChart = new Chart(ctx, { 
      type: 'bar', 
      data: { 
        labels, 
        datasets: [ 
          { label: 'BCM', data: values, backgroundColor: 'rgba(54,162,235,0.6)', yAxisID: 'y-left' }, 
          { label: 'Productivity/HR', data: productivityVals, type: 'line', borderColor: 'red', yAxisID: 'y-right' }, 
          { label: 'Threshold 220', data: thresholdVals, type: 'line', borderColor: 'green', borderDash: [5,5], yAxisID: 'y-right' } 
        ] 
      }, 
      options: { 
        responsive: true, 
        interaction: { mode: 'index', intersect: false }, 
        scales: { 
          'y-left': { type: 'linear', position: 'left', title: { display: true, text: 'BCM' } }, 
          'y-right': { type: 'linear', position: 'right', title: { display: true, text: 'Productivity/HR' }, grid: { drawOnChartArea: false } } 
        } 
      } 
    }); 
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
    const ctx = document.getElementById('chart-dozing').getContext('2d'); 
    if (dozingChart) dozingChart.destroy(); 
    dozingChart = new Chart(ctx, { 
      type: 'bar', 
      data: { 
        labels, 
        datasets: [ 
          { label: 'BCM', data: values, backgroundColor: 'rgba(54,162,235,0.6)', yAxisID: 'y-left' }, 
          { label: 'Productivity/HR', data: productivityVals, type: 'line', borderColor: 'red', yAxisID: 'y-right' } 
        ] 
      }, 
      options: { 
        responsive: true, 
        interaction: { mode: 'index', intersect: false }, 
        scales: { 
          'y-left': { type: 'linear', position: 'left', title: { display: true, text: 'BCM' } }, 
          'y-right': { type: 'linear', position: 'right', title: { display: true, text: 'Productivity/HR' }, grid: { drawOnChartArea: false } } 
        } 
      } 
    }); 
    return total; 
  } 

  // -------- Table Renderer -------- 
  async function render_table(report_name, filters, mountSelector, parentEl, collapsible = false) { 
    const res = await run_report(report_name, filters); 
    const rows = res.result || []; 
    const cols = res.columns || []; 
    const mount = parentEl.querySelector(mountSelector); 
    if (!rows.length) { 
      mount.innerHTML = '<div class="text-muted">No data</div>'; 
      return; 
    } 
    const thead = cols.map(c => `<th>${c.label}</th>`).join(''); 
    const tbody = rows.map(r => { 
      if (collapsible) { 
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
      } else { 
        return `<tr>${cols.map(c => `<td>${r[c.fieldname] ?? ''}</td>`).join('')}</tr>`; 
      } 
    }).join(''); 
    mount.innerHTML = ` 
      <table class="table table-bordered" style="width:100%"> 
        <thead><tr>${thead}</tr></thead> 
        <tbody>${tbody}</tbody> 
      </table> 
    `; 
    if (collapsible) { 
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
  } 

  // -------- Child-only table renderer (Excavator, Dozer, etc.) --------
  function render_child_table(rows, cols, parentLabel, mountSelector, parentEl) {
    const parentIndex = rows.findIndex(r =>
      r.label && r.label.toLowerCase().includes(parentLabel.toLowerCase()) && Number(r.indent || 0) === 0
    );

    let childRows = [];
    if (parentIndex !== -1) {
      for (let i = parentIndex + 1; i < rows.length; i++) {
        const r = rows[i];
        if (Number(r.indent || 0) === 0) break;
        childRows.push(r);
      }
    }

    const mount = parentEl.querySelector(mountSelector);
    if (childRows.length) {
      const thead = cols.map(c => `<th>${c.label}</th>`).join('');
      const tbody = childRows.map(r =>
        `<tr>${cols.map(c => `<td>${r[c.fieldname] ?? ''}</td>`).join('')}</tr>`
      ).join('');
      mount.innerHTML = `
        <table class="table table-bordered" style="width:100%">
          <thead><tr>${thead}</tr></thead>
          <tbody>${tbody}</tbody>
        </table>
      `;
    } else {
      mount.innerHTML = `<div class="text-muted">No ${parentLabel} data</div>`;
    }
  }

  // -------- Refresh Flow -------- 
  async function refresh_all() { 
    const start_v = start.get_value(); 
    const end_v = end.get_value(); 
    const site_v = site.get_value(); 
    const monthly_v = monthly_production.get_value(); 
    const shift_v = shift.get_value(); 
    if (!start_v || !end_v || !site_v || !monthly_v) return; 
    const filters = { start_date: start_v, end_date: end_v, site: site_v, monthly_production: monthly_v }; 
    if (shift_v) filters.shift = shift_v; 
    const teamsTotal = await render_chart_teams(filters) || 0; 
    const dozingTotal = await render_chart_dozing(filters) || 0; 
    document.getElementById('total-bcm').textContent = (teamsTotal + dozingTotal).toLocaleString(); 

    // Update excavator & dozer productivity per hour
    const prodRes = await run_report('Productivity', filters); 
    if (prodRes.result && prodRes.result.length) { 
      let excavatorProd = 0; 
      let dozerProd = 0; 
      prodRes.result.forEach(r => { 
        if (r.label && r.label.toLowerCase().includes("excavator")) { 
          excavatorProd += Number(r.productivity) || 0; 
        } 
        if (r.label && r.label.toLowerCase().includes("dozer")) { 
          dozerProd += Number(r.productivity) || 0; 
        } 
      }); 
      document.getElementById('excavator-prod').textContent = excavatorProd.toFixed(2) + " BCM/hr"; 
      document.getElementById('dozer-prod').textContent = dozerProd.toFixed(2) + " BCM/hr"; 
    } 

    await render_table('Production Shift Material', filters, '#tbl-material', tab1Pane, true); 
    await render_table('Production Shift Location', filters, '#tbl-location', tab1Pane, true); 
    await render_table('Production Shift Teams', filters, '#tbl-teams', tab1Pane, true); 
    await render_table('Production Shift Dozing', filters, '#tbl-dozing', tab1Pane, true); 
    await render_table('Productivity', filters, '#tbl-productivity', tab1Pane, true); 
    await render_table('Production Performance', filters, '#tbl-performance', tab2Pane, false); 

    // NEW: Excavator & Dozer child-only tables
    if (prodRes.result && prodRes.result.length) {
      const rows = prodRes.result;
      const cols = prodRes.columns || [];

      render_child_table(rows, cols, "excavator", "#tbl-excavators", tab2Pane);
      render_child_table(rows, cols, "dozer", "#tbl-dozers", tab2Pane);
    }
  } 

  // -------- Defaults -------- 
  const today = frappe.datetime.get_today(); 
  const week_ago = frappe.datetime.add_days(today, -6); 
  start.set_value(week_ago); 
  end.set_value(today); 
  const script = document.createElement("script"); 
  script.src = "https://cdn.jsdelivr.net/npm/chart.js"; 
  document.head.appendChild(script); 
  script.onload = () => { 
    refresh_all(); 
    setInterval(() => refresh_all(), 300000); 
  }; 
}; 














































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































