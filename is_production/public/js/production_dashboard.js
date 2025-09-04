// Copyright (c) 2025, BuFf0k and contributors
// For license information, please see license.txt

/* Production Dashboard
 * - Full-width chart: BCM by Plant No. (title shows Total BCM)
 * - Row 2: Material (L) • Location (R)
 * - Row 3: Excavators (L, +BCM/hr) • ADT (R, +BCM/hr)
 * - Row 4: Dozing (full width, +BCM/hr)
 * - Adds uniform vertical spacing between rows and auto-refreshes every 5 minutes
 */

frappe.pages['production-dashboard'].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: 'Production Dashboard',
    single_column: true
  });

  // -------- Normalize main element (handles jQuery-wrapped page.main) --------
  const mainEl =
    (page.main && page.main.jquery && page.main.get && page.main.get(0)) ||
    (page.main && page.main.nodeType === 1 && page.main) ||
    (page.body && page.body.jquery && page.body.get && page.body.get(0)) ||
    (page.body && page.body.nodeType === 1 && page.body) ||
    (wrapper && wrapper.$wrapper && wrapper.$wrapper.get && wrapper.$wrapper.get(0)) ||
    wrapper;

  if (!mainEl) {
    console.error('Production Dashboard: main container not found');
    frappe.msgprint(__('Unable to render dashboard (container missing).'));
    return;
  }

  // ------------- Shared Filters -------------
  const start = page.add_field({ fieldname: 'start_date', label: 'Start Date', fieldtype: 'Date', reqd: 1 });
  const end   = page.add_field({ fieldname: 'end_date',   label: 'End Date',   fieldtype: 'Date', reqd: 1 });
  const site  = page.add_field({ fieldname: 'site',       label: 'Site',       fieldtype: 'Link', options: 'Location', reqd: 1 });

  // Primary action to manually trigger
  page.set_primary_action(__('Run'), () => refresh_all(true));

  // ------------- Helpers for building UI -------------
  const makeCard = (title, padding = '12px') => {
    const card = document.createElement('div');
    card.className = 'frappe-card';
    card.style.padding = padding;

    const hWrap = document.createElement('div');
    hWrap.style.display = 'flex';
    hWrap.style.alignItems = 'center';
    hWrap.style.justifyContent = 'space-between';

    const h = document.createElement('div');
    h.className = 'text-muted';
    h.style.marginBottom = '6px';
    h.textContent = title;

    const hExtra = document.createElement('div'); // right-side inline metrics (Totals / BCM/hr)
    hExtra.className = 'text-muted';
    hExtra.style.marginBottom = '6px';
    hExtra.style.marginLeft = '12px';

    hWrap.appendChild(h);
    hWrap.appendChild(hExtra);
    card.appendChild(hWrap);

    return { card, titleEl: h, extraEl: hExtra };
  };

  const stripTags = (s) => (s == null ? '' : String(s).replace(/<[^>]*>/g, ''));
  const setTitleExtra = (extraEl, parts) => {
    if (!extraEl) return;
    while (extraEl.firstChild) extraEl.removeChild(extraEl.firstChild);
    (parts || [])
      .filter(p => p && p.value !== undefined && p.value !== null && p.value !== '')
      .forEach(p => {
        const span = document.createElement('span');
        span.style.marginLeft = '12px';

        const b = document.createElement('b');
        b.textContent = (p.label || '') + ':';
        span.appendChild(b);

        span.appendChild(document.createTextNode(' ' + stripTags(p.value)));
        extraEl.appendChild(span);
      });
  };

  const addRowSpacing = (el) => {
    el.classList.add('mb-4'); // uniform bottom margin between rows
    return el;
  };

  // ------------- Layout -------------

  // Row 1: Chart (full width)
  const chartRow = addRowSpacing(document.createElement('div'));
  const chartCardBits = makeCard('BCM by Plant No.', '16px');
  const chartMount = document.createElement('div');
  chartMount.id = 'chart-plant';
  const chartEmpty = document.createElement('div');
  chartEmpty.id = 'chart-plant-empty';
  chartEmpty.className = 'text-muted';
  chartEmpty.style.display = 'none';
  chartEmpty.textContent = 'No data';
  chartCardBits.card.appendChild(chartMount);
  chartCardBits.card.appendChild(chartEmpty);
  chartRow.appendChild(chartCardBits.card);
  mainEl.appendChild(chartRow);

  // Row 2: Material (L) • Location (R)
  const row2 = addRowSpacing(document.createElement('div'));
  row2.className = 'row g-3';
  const matCol = document.createElement('div'); matCol.className = 'col-lg-6';
  const locCol = document.createElement('div'); locCol.className = 'col-lg-6';

  const matBits = makeCard('BCM by Material Type');
  const matMount = document.createElement('div'); matMount.id = 'tbl-material';
  const matEmpty = document.createElement('div'); matEmpty.id = 'tbl-material-empty'; matEmpty.className = 'text-muted'; matEmpty.style.display = 'none'; matEmpty.textContent = 'No data';
  matBits.card.appendChild(matMount); matBits.card.appendChild(matEmpty); matCol.appendChild(matBits.card);

  const locBits = makeCard('BCM by Mining Area (Truck + Dozer)');
  const locMount = document.createElement('div'); locMount.id = 'tbl-location';
  const locEmpty = document.createElement('div'); locEmpty.id = 'tbl-location-empty'; locEmpty.className = 'text-muted'; locEmpty.style.display = 'none'; locEmpty.textContent = 'No data';
  locBits.card.appendChild(locMount); locBits.card.appendChild(locEmpty); locCol.appendChild(locBits.card);

  row2.appendChild(matCol); row2.appendChild(locCol); mainEl.appendChild(row2);

  // Row 3: Excavators (L) • ADT (R)
  const row3 = addRowSpacing(document.createElement('div'));
  row3.className = 'row g-3';
  const excCol = document.createElement('div'); excCol.className = 'col-lg-6';
  const adtCol = document.createElement('div'); adtCol.className = 'col-lg-6';

  const excBits = makeCard('Excavators — per Date');
  const excMount = document.createElement('div'); excMount.id = 'tbl-excavators';
  const excEmpty = document.createElement('div'); excEmpty.id = 'tbl-excavators-empty'; excEmpty.className = 'text-muted'; excEmpty.style.display = 'none'; excEmpty.textContent = 'No data';
  excBits.card.appendChild(excMount); excBits.card.appendChild(excEmpty); excCol.appendChild(excBits.card);

  const adtBits = makeCard('ADT — BCM per Truck');
  const adtMount = document.createElement('div'); adtMount.id = 'tbl-adt';
  const adtEmpty = document.createElement('div'); adtEmpty.id = 'tbl-adt-empty'; adtEmpty.className = 'text-muted'; adtEmpty.style.display = 'none'; adtEmpty.textContent = 'No data';
  adtBits.card.appendChild(adtMount); adtBits.card.appendChild(adtEmpty); adtCol.appendChild(adtBits.card);

  row3.appendChild(excCol); row3.appendChild(adtCol); mainEl.appendChild(row3);

  // Row 4: Dozing (full width)
  const row4 = addRowSpacing(document.createElement('div'));
  const dozBits = makeCard('Dozing — per Date/Shift', '12px');
  const dozMount = document.createElement('div'); dozMount.id = 'tbl-dozing';
  const dozEmpty = document.createElement('div'); dozEmpty.id = 'tbl-dozing-empty'; dozEmpty.className = 'text-muted'; dozEmpty.style.display = 'none'; dozEmpty.textContent = 'No data';
  dozBits.card.appendChild(dozMount); dozBits.card.appendChild(dozEmpty);
  row4.appendChild(dozBits.card);
  mainEl.appendChild(row4);

  // ------------- Data helpers -------------

  const run_report = (report_name, filters) =>
    frappe.call({
      method: 'frappe.desk.query_report.run',
      args: { report_name, filters, ignore_prepared_report: true }
    }).then(r => r.message || { result: [], columns: [] })
      .catch(err => {
        console.error('Report error:', report_name, err);
        const msg = (() => {
          try {
            if (err && err._server_messages) {
              const arr = JSON.parse(err._server_messages);
              if (arr && arr.length) return JSON.parse(arr[0]).message || String(arr[0]);
            }
          } catch (_) {}
          return err?.message || __('Unknown error');
        })();
        frappe.msgprint({ title: __('Error running report'), message: __(report_name) + ': ' + msg, indicator: 'red' });
        return { result: [], columns: [] };
      });

  const get_shift_hours = async (filters) => {
    // Approximate: count of Hourly Production docs in range × 12 hours per shift
    try {
      const res = await frappe.call({
        method: 'frappe.client.get_count',
        args: {
          doctype: 'Hourly Production',
          filters: {
            prod_date: ['between', [filters.start_date, filters.end_date]],
            location: filters.site,
            docstatus: ['<', 2]
          }
        }
      });
      const count = (res && res.message) || 0;
      return count * 12; // 12h per shift
    } catch (e) {
      console.warn('get_shift_hours failed', e);
      return 0;
    }
  };

  function infer_cols_from_rows(rows) {
    if (!rows.length) return [];
    const sample = rows[0];
    return Object.keys(sample).map(k => ({
      label: frappe.model.unscrub(k),
      fieldname: k,
      fieldtype: typeof sample[k] === 'number' ? 'Float' : 'Data',
      width: 150
    }));
  }

  function setEmptyVisible(selector, show) {
    const el = mainEl.querySelector(selector);
    if (el) el.style.display = show ? '' : 'none';
  }

  // ------------- Rendering -------------

  let plantChart;

  async function render_chart_plant(filters) {
    const res = await run_report('Production Shift Plant', filters);
    const rows = res.result || [];

    // Aggregate: sum total_bcm by asset (fallback to item_name)
    const byAsset = {};
    rows.forEach(r => {
      const key = r.asset || r.item_name || 'Unknown';
      byAsset[key] = (byAsset[key] || 0) + (r.total_bcm || 0);
    });

    const labels = Object.keys(byAsset);
    const values = labels.map(k => byAsset[k]);
    const plantTotal = values.reduce((a, b) => a + (Number(b) || 0), 0);

    // Update title extras (Total BCM) — plain text
    setTitleExtra(chartCardBits.extraEl, [
      { label: 'Total BCM', value: frappe.format(plantTotal, { fieldtype: 'Float', precision: 2 }) }
    ]);

    const mount = chartMount || mainEl.querySelector('#chart-plant');
    if (!mount) {
      console.warn('Chart mount not found');
      return;
    }

    if (!labels.length) {
      chartEmpty.style.display = '';
      if (plantChart) {
        plantChart.update({ labels: [], datasets: [{ name: 'BCM', values: [] }] });
      }
      return;
    }
    chartEmpty.style.display = 'none';

    const chartData = {
      labels,
      datasets: [{ name: 'BCM', values }]
    };

    if (!plantChart) {
      plantChart = new frappe.Chart(mount, {
        data: chartData,
        type: 'bar',
        height: 300,
        barOptions: { spaceRatio: 0.3 }
      });
    } else {
      plantChart.update(chartData);
    }
  }

  async function render_table(report_name, filters, mountSelector) {
    const res = await run_report(report_name, filters);
    const rows = res.result || [];
    const cols = (res.columns && res.columns.length) ? res.columns : infer_cols_from_rows(rows);

    const mount = mainEl.querySelector(mountSelector);
    if (!mount) return;

    if (!rows.length) {
      mount.innerHTML = '';
      setEmptyVisible(mountSelector + '-empty', true);
      return 0; // return sum
    }
    setEmptyVisible(mountSelector + '-empty', false);

    const thead = cols.map(c => `<th>${frappe.utils.escape_html(c.label || c.fieldname || '')}</th>`).join('');
    const tbody = rows.map(r => `
      <tr>
        ${cols.map(c => {
          const v = r[c.fieldname] ?? '';
          const formatted = (c.fieldtype === 'Float')
            ? frappe.format(v || 0, { fieldtype: 'Float', precision: c.precision || 2 })
            : frappe.utils.escape_html(String(v || ''));
          return `<td style="${c.fieldtype === 'Float' ? 'text-align:right' : ''}">${formatted}</td>`;
        }).join('')}
      </tr>
    `).join('');

    mount.innerHTML = `
      <table class="table table-bordered" style="width:100%">
        <thead><tr>${thead}</tr></thead>
        <tbody>${tbody}</tbody>
      </table>
    `;

    // Return a total BCM if obvious field exists
    const sumField = ['total_bcm', 'cumulative_bcm', 'bcm', 'bcm_total'].find(f => rows.length && (f in rows[0]));
    const total = sumField ? rows.reduce((acc, r) => acc + (Number(r[sumField]) || 0), 0) : 0;
    return total;
  }

  // ------------- Refresh flow -------------

  let runningToast;

  async function refresh_all(show_toast) {
    const filters = {
      start_date: start.get_value(),
      end_date: end.get_value(),
      site: site.get_value()
    };
    if (!filters.start_date || !filters.end_date || !filters.site) {
      if (show_toast) {
        frappe.show_alert({ message: __('Select Start, End and Site to run'), indicator: 'orange' });
      }
      return;
    }

    if (show_toast) {
      runningToast = frappe.show_alert({ message: __('Running reports...'), indicator: 'blue' }, 5);
    }

    // Compute hours once for BCM/hr
    const hours = await get_shift_hours(filters);

    // Chart
    await render_chart_plant(filters); // sets Total BCM in chart title

    // Row 2
    await render_table('Production Shift Material',   filters, '#tbl-material'); // no footer total
    await render_table('Production Shift Location',   filters, '#tbl-location');

    // Row 3 (with BCM/hr in titles)
    const excTotal = await render_table('Production Shift Excavators', filters, '#tbl-excavators');
    const adtTotal = await render_table('Production Shift ADT',        filters, '#tbl-adt');

    // Row 4 (full width, with BCM/hr)
    const dozTotal = await render_table('Production Shift Dozing',     filters, '#tbl-dozing');

    // Update inline metrics (right side of headings) — plain text values
    const fmt = (v) => stripTags(frappe.format(v || 0, { fieldtype: 'Float', precision: 2 }));
    const perHr = (tot) => (hours ? fmt(tot / hours) : '—');

    setTitleExtra(adtBits.extraEl, [{ label: 'BCM per Hour', value: perHr(adtTotal) }]);
    setTitleExtra(dozBits.extraEl, [{ label: 'BCM per Hour', value: perHr(dozTotal) }]);
    setTitleExtra(excBits.extraEl, [{ label: 'BCM per Hour', value: perHr(excTotal) }]);

    if (runningToast && runningToast.hide) runningToast.hide();
    frappe.show_alert({ message: __('Done'), indicator: 'green' });
  }

  // ------------- Defaults & Event Wiring -------------

  const today = frappe.datetime.get_today();
  const week_ago = frappe.datetime.add_days(today, -6);
  start.set_value(week_ago);
  end.set_value(today);

  const wire = (ctrl) => {
    if (!ctrl || !ctrl.$input) return;
    ctrl.$input.on('change', () => refresh_all(false));
    ctrl.$input.on('awesomplete-selectcomplete', () => refresh_all(false));
    ctrl.$input.on('blur', () => refresh_all(false));
  };
  [start, end, site].forEach(wire);

  // Optional: role guard (server already restricts via Page roles)
  try {
    const allowed = ['System User', 'Production User', 'Production Manager'].some(r => frappe.user.has_role(r));
    if (!allowed) {
      frappe.msgprint(__('You do not have access to this dashboard.'));
      return;
    }
  } catch (e) { /* ignore */ }

  // Auto-refresh every 5 minutes (uses current filters; safe no-op if filters missing)
  setInterval(() => {
    refresh_all(false);
  }, 5 * 60 * 1000);

  // Optionally set a default site and auto-run:
  // site.set_value('YOUR_DEFAULT_LOCATION_NAME');
  // refresh_all(true);
};
