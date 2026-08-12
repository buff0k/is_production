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

  const monthly_production = page.add_field({ 
    fieldname: 'monthly_production', label: 'Monthly Production', 
    fieldtype: 'Link', options: 'Monthly Production Planning', reqd: 1 
  }); 

  monthly_production.get_query = () => {
    return {
      query: "is_production.production.doctype.monthly_production_planning.monthly_production_planning.dashboard_monthly_production_query",
      filters: {
        location: site.get_value()
      }
    };
  }; 

  const shift = page.add_field({ 
    fieldname: 'shift', label: 'Shift', 
    fieldtype: 'Select', 
    options: ["", "Day", "Night", "Morning", "Afternoon"], 
    reqd: 0 
  }); 

  page.set_primary_action(__('Run'), () => refresh_all(true)); 

  // -------- Dashboard PDF and Excel Export --------

  function load_xlsx_library() {
    return new Promise((resolve, reject) => {
      if (window.XLSX) {
        resolve(window.XLSX);
        return;
      }

      const existing = document.getElementById('production-dashboard-xlsx-lib');

      if (existing) {
        existing.addEventListener('load', () => resolve(window.XLSX), { once: true });
        existing.addEventListener('error', reject, { once: true });
        return;
      }

      const script = document.createElement('script');
      script.id = 'production-dashboard-xlsx-lib';
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js';
      script.onload = () => resolve(window.XLSX);
      script.onerror = () => reject(new Error('Failed to load the Excel export library.'));
      document.head.appendChild(script);
    });
  }

  function get_active_tab_details() {
    const tabs = {
      1: {
        name: 'Production Dashboard',
        pane: tab1Pane
      },
      2: {
        name: 'Production Dashboard Update',
        pane: tab2Pane
      },
      3: {
        name: 'Weekly Report',
        pane: tab3Pane
      },
      4: {
        name: 'Daily and Shift Report',
        pane: tab4Pane
      }
    };

    return tabs[active_tab] || tabs[1];
  }

  function safe_export_filename(value) {
    return String(value || '')
      .trim()
      .replace(/[\\/:*?"<>|]+/g, '-')
      .replace(/\s+/g, '_')
      .replace(/_+/g, '_');
  }

  function get_export_filename(extension) {
    const filters = get_filters() || {};
    const tab = get_active_tab_details();

    const parts = [
      'Production_Dashboard',
      tab.name,
      filters.site,
      filters.start_date,
      filters.end_date,
      filters.shift
    ].filter(Boolean);

    return `${safe_export_filename(parts.join('_'))}.${extension}`;
  }

  function get_filter_export_rows() {
    const filters = get_filters() || {};

    return [
      ['Production Dashboard Export'],
      [],
      ['Report Tab', get_active_tab_details().name],
      ['Start Date', filters.start_date || ''],
      ['End Date', filters.end_date || ''],
      ['Site', filters.site || ''],
      ['Monthly Production', filters.monthly_production || ''],
      ['Shift', filters.shift || 'All Shifts'],
      ['Exported By', frappe.session.user || ''],
      ['Exported At', frappe.datetime.now_datetime()]
    ];
  }

  function get_summary_export_rows() {
    const summaryFields = [
      ['Total BCM Tallies', 'total-bcm'],
      ['Actual BCM (Survey + HP)', 'actual-bcm-survey'],
      ['Survey Variance', 'survey-variance'],
      ['Overall Team Productivity per Hour', 'excavator-prod'],
      ['Overall Dozing Productivity per Hour', 'dozer-prod']
    ];

    const rows = [['Metric', 'Value']];

    summaryFields.forEach(([label, id]) => {
      const element = document.getElementById(id);

      if (element) {
        rows.push([
          label,
          element.textContent.trim()
        ]);
      }
    });

    return rows;
  }

  function table_to_array(table) {
    return Array.from(table.rows).map(row =>
      Array.from(row.cells).map(cell =>
        cell.innerText
          .replace(/\s+/g, ' ')
          .trim()
      )
    );
  }

  function get_table_title(table, index) {
    const card = table.closest('.frappe-card, .compact-card');

    if (card) {
      const heading = card.querySelector(
        'h1, h2, h3, h4, h5, h6, .card-title, .section-title, .control-label'
      );

      if (heading && heading.textContent.trim()) {
        return heading.textContent.trim();
      }
    }

    const previousHeading = table.previousElementSibling;

    if (previousHeading && previousHeading.textContent.trim()) {
      return previousHeading.textContent.trim();
    }

    return `Table ${index + 1}`;
  }

  function unique_sheet_name(name, usedNames) {
    let cleaned = String(name || 'Sheet')
      .replace(/[\\/*?:[\]]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .slice(0, 31) || 'Sheet';

    let candidate = cleaned;
    let number = 2;

    while (usedNames.has(candidate)) {
      const suffix = ` ${number}`;
      candidate = cleaned.slice(0, 31 - suffix.length) + suffix;
      number += 1;
    }

    usedNames.add(candidate);
    return candidate;
  }

  function set_reasonable_column_widths(worksheet, rows) {
    if (!rows.length) return;

    const maxColumns = Math.max(...rows.map(row => row.length));

    worksheet['!cols'] = Array.from({ length: maxColumns }, (_, columnIndex) => {
      let maxLength = 10;

      rows.forEach(row => {
        const value = row[columnIndex];

        if (value !== undefined && value !== null) {
          maxLength = Math.max(maxLength, String(value).length);
        }
      });

      return {
        wch: Math.min(maxLength + 2, 45)
      };
    });
  }

  async function export_dashboard_excel() {
    const active = get_active_tab_details();

    if (!active.pane) {
      frappe.msgprint(__('The active dashboard tab could not be found.'));
      return;
    }

    const tables = Array.from(active.pane.querySelectorAll('table'))
      .filter(table => table.offsetParent !== null);

    if (!tables.length && active_tab !== 1) {
      frappe.msgprint(__('There is no visible table data to export on this tab.'));
      return;
    }

    frappe.show_alert({
      message: __('Preparing Excel export...'),
      indicator: 'blue'
    });

    try {
      await load_xlsx_library();

      if (!window.XLSX) {
        throw new Error('Excel library is unavailable.');
      }

      const workbook = XLSX.utils.book_new();
      const usedNames = new Set();

      const overviewRows = [
        ...get_filter_export_rows(),
        [],
        ...get_summary_export_rows()
      ];

      const overviewSheet = XLSX.utils.aoa_to_sheet(overviewRows);
      set_reasonable_column_widths(overviewSheet, overviewRows);

      XLSX.utils.book_append_sheet(
        workbook,
        overviewSheet,
        unique_sheet_name('Summary', usedNames)
      );

      tables.forEach((table, index) => {
        const rows = table_to_array(table);

        if (!rows.length) return;

        const title = get_table_title(table, index);
        const worksheet = XLSX.utils.aoa_to_sheet(rows);

        set_reasonable_column_widths(worksheet, rows);

        XLSX.utils.book_append_sheet(
          workbook,
          worksheet,
          unique_sheet_name(title, usedNames)
        );
      });

      XLSX.writeFile(workbook, get_export_filename('xlsx'));

      frappe.show_alert({
        message: __('Excel export completed.'),
        indicator: 'green'
      });
    } catch (error) {
      console.error('Production Dashboard Excel export failed:', error);

      frappe.msgprint({
        title: __('Excel Export Failed'),
        message: __('The dashboard could not be exported to Excel. Please check the browser console.'),
        indicator: 'red'
      });
    }
  }

  function copy_canvas_images(sourcePane, clonedPane) {
    const sourceCanvases = sourcePane.querySelectorAll('canvas');
    const clonedCanvases = clonedPane.querySelectorAll('canvas');

    sourceCanvases.forEach((canvas, index) => {
      const clonedCanvas = clonedCanvases[index];

      if (!clonedCanvas) return;

      try {
        const image = document.createElement('img');
        image.src = canvas.toDataURL('image/png', 1.0);
        image.style.display = 'block';
        image.style.width = '100%';
        image.style.maxWidth = '100%';
        image.style.height = 'auto';

        clonedCanvas.replaceWith(image);
      } catch (error) {
        console.warn('Could not copy dashboard chart into PDF:', error);
      }
    });
  }

  function load_external_script(id, src, readyCheck) {
    return new Promise((resolve, reject) => {
      if (readyCheck()) {
        resolve();
        return;
      }

      const existing = document.getElementById(id);

      if (existing) {
        const waitForLibrary = setInterval(() => {
          if (readyCheck()) {
            clearInterval(waitForLibrary);
            resolve();
          }
        }, 100);

        setTimeout(() => {
          clearInterval(waitForLibrary);

          if (!readyCheck()) {
            reject(new Error(`Library ${id} did not finish loading.`));
          }
        }, 15000);

        return;
      }

      const script = document.createElement('script');
      script.id = id;
      script.src = src;
      script.onload = () => {
        if (readyCheck()) {
          resolve();
        } else {
          reject(new Error(`Library ${id} loaded but is unavailable.`));
        }
      };
      script.onerror = () => reject(new Error(`Failed to load ${src}`));
      document.head.appendChild(script);
    });
  }

  function get_server_pdf_html(active, filters) {
    const clonedPane = active.pane.cloneNode(true);
    const isFullReportTab = active_tab === 3 || active_tab === 4;

    // Replace Chart.js canvases with images for server-side PDF rendering.
    copy_canvas_images(active.pane, clonedPane);

    clonedPane.querySelectorAll(
      'button, script, iframe, .dropdown-menu, .modal, .tooltip, [hidden], .d-none'
    ).forEach(element => element.remove());

    // Keep currently rendered report content visible.
    clonedPane.querySelectorAll('.collapse').forEach(element => {
      element.classList.add('show');
      element.style.display = 'block';
      element.style.height = 'auto';
      element.style.visibility = 'visible';
    });

    clonedPane.querySelectorAll('table').forEach(table => {
      table.style.width = '100%';
      table.style.borderCollapse = 'collapse';
    });

    const escape = value =>
      frappe.utils.escape_html(String(value ?? ''));

    return `
      <!DOCTYPE html>
      <html>
        <head>
          <meta charset="utf-8">

          <style>
            @page {
              size: A4 landscape;
              margin: 6mm;
            }

            * {
              box-sizing: border-box;
            }

            html,
            body {
              width: 100%;
              margin: 0;
              padding: 0;
              background: #ffffff;
              color: #1f272e;
              font-family: Arial, Helvetica, sans-serif;
              font-size: 7px;
            }

            .pdf-header {
              border-bottom: 2px solid #1f272e;
              margin-bottom: 8px;
              padding-bottom: 6px;
            }

            .pdf-header h1 {
              margin: 0 0 3px;
              font-size: 17px;
            }

            .pdf-header h2 {
              margin: 0;
              color: #5e6c84;
              font-size: 11px;
              font-weight: 600;
            }

            .pdf-filters {
              width: 100%;
              margin-bottom: 6px;
              border: 1px solid #d1d8dd;
              border-collapse: collapse;
              background: #f7f8fa;
            }

            .pdf-filters td {
              width: 33.333%;
              border: 1px solid #d1d8dd;
              padding: 4px 5px;
              font-size: 7px;
            }

            .row {
              display: table;
              width: 100%;
              table-layout: fixed;
            }

            .col-lg-6 {
              display: table-cell;
              width: 50%;
              padding: 3px;
              vertical-align: top;
            }

            .frappe-card,
            .compact-card {
              width: 100%;
              margin-bottom: 5px;
              padding: 6px;
              border: 1px solid #d1d8dd;
              border-radius: 4px;
              box-shadow: none;
              page-break-inside: auto;
            }

            .dashboard-pdf-content {
              page-break-before: avoid;
            }

            img {
              display: block;
              width: 100%;
              max-width: 100%;
              height: auto;
            }

            table {
              width: 100%;
              margin-bottom: 6px;
              border-collapse: collapse;
              page-break-inside: auto;
            }

            thead {
              display: table-header-group;
            }

            tr {
              page-break-inside: avoid;
            }

            th,
            td {
              border: 1px solid #c8ced6;
              padding: 2px 3px;
              font-size: 7px;
              line-height: 1.25;
              vertical-align: top;
              word-wrap: break-word;
            }

            th {
              background: #eef1f5;
              font-weight: 700;
            }

            .collapse {
              display: block !important;
              height: auto !important;
              visibility: visible !important;
            }
          </style>
        </head>

        <body>
          ${
            isFullReportTab
              ? ''
              : `
                <div class="pdf-header">
                  <h1>Production Dashboard</h1>
                  <h2>${escape(active.name)}</h2>
                </div>

                <table class="pdf-filters">
                  <tr>
                    <td>
                      <strong>Start Date:</strong>
                      ${escape(filters.start_date)}
                    </td>

                    <td>
                      <strong>End Date:</strong>
                      ${escape(filters.end_date)}
                    </td>

                    <td>
                      <strong>Site:</strong>
                      ${escape(filters.site)}
                    </td>
                  </tr>

                  <tr>
                    <td>
                      <strong>Monthly Production:</strong>
                      ${escape(filters.monthly_production)}
                    </td>

                    <td>
                      <strong>Shift:</strong>
                      ${escape(filters.shift || 'All Shifts')}
                    </td>

                    <td>
                      <strong>Generated:</strong>
                      ${escape(frappe.datetime.now_datetime())}
                    </td>
                  </tr>
                </table>
              `
          }

          <div class="dashboard-pdf-content">
            ${clonedPane.outerHTML}
          </div>
        </body>
      </html>
    `;
  }

  function download_base64_pdf(base64Content, filename) {
    const binary = window.atob(base64Content);
    const bytes = new Uint8Array(binary.length);

    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }

    const blob = new Blob(
      [bytes],
      { type: 'application/pdf' }
    );

    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');

    link.href = url;
    link.download = filename || 'Production_Dashboard.pdf';

    document.body.appendChild(link);
    link.click();
    link.remove();

    window.setTimeout(() => {
      window.URL.revokeObjectURL(url);
    }, 1500);
  }

  async function download_dashboard_pdf() {
    const active = get_active_tab_details();
    const filters = get_filters();

    if (!filters) {
      frappe.msgprint(
        __('Please select the required filters and click Run before downloading the PDF.')
      );
      return;
    }

    if (!active.pane) {
      frappe.msgprint(
        __('The active dashboard tab could not be found.')
      );
      return;
    }

    const html = get_server_pdf_html(active, filters);
    const filename = get_export_filename('pdf').replace(/\.pdf$/i, '');

    frappe.show_alert({
      message: __('Generating PDF on server...'),
      indicator: 'blue'
    });

    try {
      const response = await frappe.call({
        method:
          'is_production.production.page.production_dashboard.production_dashboard.download_dashboard_pdf',
        args: {
          html,
          filename
        },
        freeze: false
      });

      const result = response.message || {};

      if (!result.content) {
        throw new Error('The server returned an empty PDF response.');
      }

      download_base64_pdf(
        result.content,
        result.filename
      );

      frappe.show_alert({
        message: __('PDF downloaded successfully.'),
        indicator: 'green'
      });
    } catch (error) {
      console.error(
        'Server-side Production Dashboard PDF failed:',
        error
      );

      frappe.msgprint({
        title: __('PDF Download Failed'),
        message: __(
          'The server could not generate the PDF. Please check the ERP Error Log.'
        ),
        indicator: 'red'
      });
    }
  }

  page.add_inner_button(__('Download PDF'), download_dashboard_pdf);
  page.add_inner_button(__('Export Excel'), export_dashboard_excel);

  // Start loading Excel support before the user clicks the button.
  load_xlsx_library().catch(error => {
    console.warn('Excel export library did not preload:', error);
  });

  // -------- Tabs -------- 
  const tabNav = document.createElement('div'); 
  tabNav.className = 'mb-3'; 

  const tab1Btn = document.createElement('button'); 
  tab1Btn.textContent = 'Production Dashboard'; 
  tab1Btn.className = 'btn btn-primary me-2'; 

  const tab2Btn = document.createElement('button'); 
  tab2Btn.textContent = 'Production Dashboard Update'; 
  tab2Btn.className = 'btn btn-secondary'; 

  const tab3Btn = document.createElement('button');
  tab3Btn.textContent = 'Weekly Report';
  tab3Btn.className = 'btn btn-secondary';

  // --- Fourth tab button ---
  const tab4Btn = document.createElement('button');
  tab4Btn.textContent = 'Daily & Shift Report';
  tab4Btn.className = 'btn btn-secondary';

  tabNav.appendChild(tab1Btn); 
  tabNav.appendChild(tab2Btn); 
  tabNav.appendChild(tab3Btn); 
  tabNav.appendChild(tab4Btn);
  mainEl.appendChild(tabNav); 


  const tab1Pane = document.createElement('div'); 
  tab1Pane.style.display = 'block'; 
  mainEl.appendChild(tab1Pane); 

  const tab2Pane = document.createElement('div'); 
  tab2Pane.style.display = 'none'; 
  mainEl.appendChild(tab2Pane); 

  // --- Third tab container ---
  const tab3Pane = document.createElement('div');
  tab3Pane.style.display = 'none';
  mainEl.appendChild(tab3Pane);

  // --- Fourth tab container ---
  const tab4Pane = document.createElement('div');
  tab4Pane.style.display = 'none';
  mainEl.appendChild(tab4Pane);


let active_tab = 1;

tab1Btn.onclick = async () => {
    active_tab = 1;

    tab1Pane.style.display = 'block';
    tab2Pane.style.display = 'none';
    tab3Pane.style.display = 'none';
    tab4Pane.style.display = 'none';

    tab1Btn.className = 'btn btn-primary me-2';
    tab2Btn.className = 'btn btn-secondary me-2';
    tab3Btn.className = 'btn btn-secondary me-2';
    tab4Btn.className = 'btn btn-secondary';

    const f = get_filters();
    if (f) await refresh_tab1(f);
};

tab2Btn.onclick = async () => {
    active_tab = 2;

    tab1Pane.style.display = 'none';
    tab2Pane.style.display = 'block';
    tab3Pane.style.display = 'none';
    tab4Pane.style.display = 'none';

    tab1Btn.className = 'btn btn-secondary me-2';
    tab2Btn.className = 'btn btn-primary me-2';
    tab3Btn.className = 'btn btn-secondary me-2';
    tab4Btn.className = 'btn btn-secondary';

    const f = get_filters();
    if (f) await refresh_tab2(f);
};

tab3Btn.onclick = async () => {
    active_tab = 3;

    tab1Pane.style.display = 'none';
    tab2Pane.style.display = 'none';
    tab3Pane.style.display = 'block';
    tab4Pane.style.display = 'none';

    tab1Btn.className = 'btn btn-secondary me-2';
    tab2Btn.className = 'btn btn-secondary me-2';
    tab3Btn.className = 'btn btn-primary me-2';
    tab4Btn.className = 'btn btn-secondary';

    const f = get_filters();
    if (f) await refresh_tab3(f);
};

tab4Btn.onclick = async () => {
    active_tab = 4;

    tab1Pane.style.display = 'none';
    tab2Pane.style.display = 'none';
    tab3Pane.style.display = 'none';
    tab4Pane.style.display = 'block';

    tab1Btn.className = 'btn btn-secondary me-2';
    tab2Btn.className = 'btn btn-secondary me-2';
    tab3Btn.className = 'btn btn-secondary me-2';
    tab4Btn.className = 'btn btn-primary';

    const f = get_filters();
    if (f) await refresh_tab4(f);
};




  // -------- Helpers -------- 
  const makeCard = (title) => { 
    const card = document.createElement('div'); 
    card.className = 'frappe-card compact-card'; 
    card.style.padding = '8px'; 
    const hWrap = document.createElement('div'); 
    hWrap.style.display = 'flex'; 
    hWrap.style.alignItems = 'center'; 
    hWrap.style.justifyContent = 'space-between'; 
    const h = document.createElement('div'); 
    h.className = 'text-muted'; 
    h.style.marginBottom = '4px'; 
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
  const totalRow = document.createElement('div'); 
  totalRow.style.display = 'flex'; 
  totalRow.style.gap = '20px'; 

  const totalBits = makeCard('Total BCM Tallies'); 
// --- Actual BCM (Survey + HP) card ---
const actualBcmBits = makeCard('Actual BCM (Survey + HP)');
const actualBcmValue = document.createElement('div');
actualBcmValue.style.fontSize = '20px';
actualBcmValue.style.fontWeight = 'bold';
actualBcmValue.style.color = '#0047ab'; // Deep blue
actualBcmValue.id = 'actual-bcm-survey';
actualBcmValue.textContent = '0';
actualBcmBits.card.appendChild(actualBcmValue);

// --- Survey Variance card ---
const varianceBits = makeCard('Survey Variance');
const varianceValue = document.createElement('div');
varianceValue.style.fontSize = '20px';
varianceValue.style.fontWeight = 'bold';
varianceValue.style.color = '#cc0000'; // Red for variance
varianceValue.id = 'survey-variance';
varianceValue.textContent = '0';
varianceBits.card.appendChild(varianceValue);

  const totalValue = document.createElement('div'); 
  totalValue.style.fontSize = '20px'; 
  totalValue.style.fontWeight = 'bold'; 
  totalValue.id = 'total-bcm'; 
  totalValue.textContent = '0'; 
  totalBits.card.appendChild(totalValue); 

  const excavatorBits = makeCard('Overall Team Productivity per Hour'); 
  const excavatorValue = document.createElement('div'); 
  excavatorValue.style.fontSize = '14px'; 
  excavatorValue.style.fontWeight = 'bold'; 
  excavatorValue.id = 'excavator-prod'; 
  excavatorValue.textContent = '0 BCM/hr'; 
  excavatorBits.card.appendChild(excavatorValue); 

  const dozerBits = makeCard('Overall Dozing Productivity per Hour'); 
  const dozerValue = document.createElement('div'); 
  dozerValue.style.fontSize = '14px'; 
  dozerValue.style.fontWeight = 'bold'; 
  dozerValue.id = 'dozer-prod'; 
  dozerValue.textContent = '0 BCM/hr'; 
  dozerBits.card.appendChild(dozerValue); 

// --- Append all cards in desired order ---
totalRow.appendChild(totalBits.card);
totalRow.appendChild(actualBcmBits.card);
totalRow.appendChild(varianceBits.card);
totalRow.appendChild(excavatorBits.card);
totalRow.appendChild(dozerBits.card);
tab1Pane.appendChild(totalRow);

  const chartRow = document.createElement('div'); 
  chartRow.className = 'row g-2'; 
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

  const row3 = document.createElement('div'); row3.className = 'row g-2'; 
  const matCol = document.createElement('div'); matCol.className = 'col-lg-6'; 
  const locCol = document.createElement('div'); locCol.className = 'col-lg-6'; 
  const matBits = makeCard('Production Shift Material'); 
  const matMount = document.createElement('div'); matMount.id = 'tbl-material'; 
  matBits.card.appendChild(matMount); matCol.appendChild(matBits.card); 
  const locBits = makeCard('Production Shift Location'); 
  const locMount = document.createElement('div'); locMount.id = 'tbl-location'; 
  locBits.card.appendChild(locMount); locCol.appendChild(locBits.card); 
  row3.appendChild(matCol); row3.appendChild(locCol); tab1Pane.appendChild(row3); 

  const row4 = document.createElement('div'); row4.className = 'row g-2'; 
  const teamsCol = document.createElement('div'); teamsCol.className = 'col-lg-6'; 
  const dozingCol = document.createElement('div'); dozingCol.className = 'col-lg-6'; 
  const teamsTblBits = makeCard('Production Shift Teams (Table)'); 
  const teamsTblMount = document.createElement('div'); teamsTblMount.id = 'tbl-teams'; 
  teamsTblBits.card.appendChild(teamsTblMount); teamsCol.appendChild(teamsTblBits.card); 
  const dozingTblBits = makeCard('Production Shift Dozing (Table)'); 
  const dozingTblMount = document.createElement('div'); dozingTblMount.id = 'tbl-dozing'; 
  dozingTblBits.card.appendChild(dozingTblMount); dozingCol.appendChild(dozingTblBits.card); 
  row4.appendChild(teamsCol); row4.appendChild(dozingCol); tab1Pane.appendChild(row4); 

  const row5 = document.createElement('div'); 
  const prodBits = makeCard('Productivity Report'); 
  const prodMount = document.createElement('div'); prodMount.id = 'tbl-productivity'; 
  prodBits.card.appendChild(prodMount); row5.appendChild(prodBits.card); 
  tab1Pane.appendChild(row5); 

  // ============================================================== 
  // Monthly Production Report (bottom of Tab 1)
  // ============================================================== 
  const row6 = document.createElement('div');
  row6.className = 'row g-2';

  const monthlyCol = document.createElement('div');
  monthlyCol.className = 'col-12';
  const monthlyBits = makeCard('Monthly Production Report');
  const monthlyMount = document.createElement('div');
  monthlyMount.id = 'tbl-monthly-production';
  monthlyBits.card.appendChild(monthlyMount);
  monthlyCol.appendChild(monthlyBits.card);
  row6.appendChild(monthlyCol);

  tab1Pane.appendChild(row6);


  // ============================================================== 
  // TAB 2: Compact Grid Layout 
  // ============================================================== 
  const tab2Row = document.createElement('div');
  tab2Row.className = 'row g-2';

  const perfCol = document.createElement('div');
  perfCol.className = 'col-12';
  const perfTblBits = makeCard('Production Performance Report'); 
  const perfTblMount = document.createElement('div'); perfTblMount.id = 'tbl-performance'; 
  perfTblBits.card.appendChild(perfTblMount); 
  perfCol.appendChild(perfTblBits.card);
  tab2Row.appendChild(perfCol);

  const excavCol = document.createElement('div');
  excavCol.className = 'col-lg-6 col-sm-12';
  const excavTblBits = makeCard('Excavator Productivity (Machines)'); 
  const excavTblMount = document.createElement('div'); excavTblMount.id = 'tbl-excavators'; 
  excavTblBits.card.appendChild(excavTblMount); 
  excavCol.appendChild(excavTblBits.card);
  tab2Row.appendChild(excavCol);

  const dozerCol = document.createElement('div');
  dozerCol.className = 'col-lg-6 col-sm-12';
  const dozerTblBits = makeCard('Dozer Productivity (Machines)'); 
  const dozerTblMount = document.createElement('div'); dozerTblMount.id = 'tbl-dozers'; 
  dozerTblBits.card.appendChild(dozerTblMount); 
  dozerCol.appendChild(dozerTblBits.card);
  tab2Row.appendChild(dozerCol);

  tab2Pane.appendChild(tab2Row);

  // ============================================================== 
// TAB 3: Weekly Report 
// ============================================================== 
const weeklyRow = document.createElement('div');
weeklyRow.className = 'row g-2';

const weeklyCol = document.createElement('div');
weeklyCol.className = 'col-12';
const weeklyBits = makeCard('Weekly Report'); 
const weeklyMount = document.createElement('div'); 
weeklyMount.id = 'tbl-weekly'; 
weeklyBits.card.appendChild(weeklyMount); 
weeklyCol.appendChild(weeklyBits.card);
weeklyRow.appendChild(weeklyCol);

tab3Pane.appendChild(weeklyRow);

// ============================================================== 
// TAB 4: Daily & Shift Report 
// ============================================================== 
const dailyRow = document.createElement('div');
dailyRow.className = 'row g-2';

const dailyCol = document.createElement('div');
dailyCol.className = 'col-12';
const dailyBits = makeCard('Daily & Shift Report'); 
const dailyMount = document.createElement('div'); 
dailyMount.id = 'tbl-daily'; 
dailyBits.card.appendChild(dailyMount); 
dailyCol.appendChild(dailyBits.card);
dailyRow.appendChild(dailyCol);

tab4Pane.appendChild(dailyRow);


  // -------- Chart.js Setup -------- 
  let teamsChart, dozingChart; 

  async function render_chart_teams(filters) {
  const res = await run_report('Production Shift Teams', filters);
  const prodRes = await run_report('Productivity', filters);

  // --- Filter only actual excavators (exclude summary or MTD rows) ---
  const parents = (res.result || []).filter(r => {
    const name = (r.excavator || '').toString().toLowerCase().trim();
    // Exclude blank, null, or MTD Actual BCM rows
    return (
      Number(r.indent || 0) === 0 &&
      name !== '' &&
      !name.includes('mtd actual bcm')
    );
  });

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

  // -------- Monthly Production Report Renderer --------
async function render_monthly_production(filters, mountSelector, parentEl) {
  try {
    const res = await frappe.call({
      method: 'frappe.desk.query_report.run',
      args: {
        report_name: 'Monthly Production',  // must match your Report Name
        filters,
        ignore_prepared_report: true
      }
    });

    const msg = res.message || {};
    const html_output = msg.report_html || msg.message || '';

    const mount = parentEl.querySelector(mountSelector);
    if (html_output) {
      mount.innerHTML = html_output;
    } else if (msg.result && msg.result.length) {
      const cols = msg.columns || [];
      const rows = msg.result;
      const thead = cols.map(c => `<th>${c.label}</th>`).join('');
      const tbody = rows.map(r =>
        `<tr>${cols.map(c => `<td>${r[c.fieldname] || ''}</td>`).join('')}</tr>`
      ).join('');
      mount.innerHTML = `
        <table class="table table-bordered table-sm">
          <thead><tr>${thead}</tr></thead>
          <tbody>${tbody}</tbody>
        </table>`;
    } else {
      mount.innerHTML = '<div class="text-muted">No Monthly Production data found.</div>';
    }
  } catch (e) {
    console.error(e);
    frappe.msgprint(__('Failed to load Monthly Production Report.'));
  }
}

  // -------- Weekly Report Renderer -------- 
async function render_weekly_report(filters, mountSelector, parentEl) {
  try {
    const res = await frappe.call({
      method: 'frappe.desk.query_report.run',
      args: {
        report_name: 'Weekly Report',
        filters,
        ignore_prepared_report: true
      }
    });

    const msg = res.message || {};
    const html_output = msg.report_html || msg.message || '';

    const mount = parentEl.querySelector(mountSelector);
    if (html_output) {
      mount.innerHTML = html_output;
    } else if (msg.result && msg.result.length) {
      // fallback to simple table
      const cols = msg.columns || [];
      const rows = msg.result;
      const thead = cols.map(c => `<th>${c.label}</th>`).join('');
      const tbody = rows.map(r =>
        `<tr>${cols.map(c => `<td>${r[c.fieldname] || ''}</td>`).join('')}</tr>`
      ).join('');
      mount.innerHTML = `
        <table class="table table-bordered">
          <thead><tr>${thead}</tr></thead>
          <tbody>${tbody}</tbody>
        </table>`;
    } else {
      mount.innerHTML = '<div class="text-muted">No Weekly Report data found.</div>';
    }
  } catch (e) {
    console.error(e);
    frappe.msgprint(__('Failed to load Weekly Report.'));
  }
}

// -------- Daily & Shift Report Renderer -------- 
async function render_daily_report(filters, mountSelector, parentEl) {
  try {
    const res = await frappe.call({
      method: 'frappe.desk.query_report.run',
      args: {
        report_name: 'Daily Reporting',
        filters,
        ignore_prepared_report: true
      }
    });

    const msg = res.message || {};
    const html_output = msg.report_html || msg.message || '';

    const mount = parentEl.querySelector(mountSelector);
    if (html_output) {
      mount.innerHTML = html_output;
    } else if (msg.result && msg.result.length) {
      const cols = msg.columns || [];
      const rows = msg.result;
      const thead = cols.map(c => `<th>${c.label}</th>`).join('');
      const tbody = rows.map(r =>
        `<tr>${cols.map(c => `<td>${r[c.fieldname] || ''}</td>`).join('')}</tr>`
      ).join('');
      mount.innerHTML = `
        <table class="table table-bordered">
          <thead><tr>${thead}</tr></thead>
          <tbody>${tbody}</tbody>
        </table>`;
    } else {
      mount.innerHTML = '<div class="text-muted">No Daily Report data found.</div>';
    }
  } catch (e) {
    console.error(e);
    frappe.msgprint(__('Failed to load Daily Report.'));
  }
}


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
        monthly_production: monthly_v
    };
    if (shift_v) f.shift = shift_v;

    return f;
}
async function refresh_tab1(filters) {
    const teamsTotal = await render_chart_teams(filters);
    const dozingTotal = await render_chart_dozing(filters);

    const matRes = await run_report('Production Shift Material', filters);
    let mtdTallies = 0;
    if (matRes.result?.length) {
        const talliesRow = matRes.result.find(r =>
            r.mat_type?.toLowerCase().includes("mtd tallies bcm")
        );
        if (talliesRow) mtdTallies = Number(talliesRow.total_bcm) || 0;
    }
    document.getElementById('total-bcm').textContent = mtdTallies.toLocaleString();

    const prodRes = await run_report('Productivity', filters);
    let excavatorProd = 0, dozerProd = 0;
    prodRes.result?.forEach(r => {
        if (r.label?.toLowerCase().includes("excavator")) excavatorProd += Number(r.productivity) || 0;
        if (r.label?.toLowerCase().includes("dozer")) dozerProd += Number(r.productivity) || 0;
    });

    document.getElementById('excavator-prod').textContent = excavatorProd.toFixed(2) + " BCM/hr";
    document.getElementById('dozer-prod').textContent = dozerProd.toFixed(2) + " BCM/hr";

    await render_table('Production Shift Material', filters, '#tbl-material', tab1Pane, true);
    await render_table('Production Shift Location', filters, '#tbl-location', tab1Pane, true);
    await render_table('Production Shift Teams', filters, '#tbl-teams', tab1Pane, true);
    await render_table('Production Shift Dozing', filters, '#tbl-dozing', tab1Pane, true);
    await render_monthly_production(filters, '#tbl-monthly-production', tab1Pane);
    await render_table('Productivity', filters, '#tbl-productivity', tab1Pane, true);

    // Calculate variance
    const mtdRes = await run_report('Production Shift Teams', filters);
    let actualBcm = 0;
    if (mtdRes.summary?.length) {
        const bcmRow = mtdRes.summary.find(s =>
            s.label?.toLowerCase().includes('mtd actual bcm')
        );
        if (bcmRow) actualBcm = Number(bcmRow.value.replace(/,/g, '')) || 0;
    }

    document.getElementById('actual-bcm-survey').textContent = actualBcm.toLocaleString();
    const totalBcmValue = Number(document.getElementById('total-bcm').textContent.replace(/,/g, '')) || 0;
    const variance = actualBcm - totalBcmValue;
    const varianceEl = document.getElementById('survey-variance');
    varianceEl.textContent = variance.toLocaleString();
    varianceEl.style.color = variance >= 0 ? '#006600' : '#cc0000';
}
async function refresh_tab2(filters) {
    await render_table('Production Performance', filters, '#tbl-performance', tab2Pane, false);

    const prodRes = await run_report('Productivity', filters);
    if (prodRes.result?.length) {
        const rows = prodRes.result;
        const cols = prodRes.columns || [];
        render_child_table(rows, cols, "excavator", "#tbl-excavators", tab2Pane);
        render_child_table(rows, cols, "dozer", "#tbl-dozers", tab2Pane);
    }
}
async function refresh_tab3(filters) {
    await render_weekly_report(filters, '#tbl-weekly', tab3Pane);
}
async function refresh_tab4(filters) {
    await render_daily_report(filters, '#tbl-daily', tab4Pane);
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
    setInterval(async () => {
    const f = get_filters();
    if (!f) return;

    if (active_tab === 1) await refresh_tab1(f);
    if (active_tab === 2) await refresh_tab2(f);
    if (active_tab === 3) await refresh_tab3(f);
    if (active_tab === 4) await refresh_tab4(f);
}, 300000);

  }; 

  // -------- Compact CSS -------- 
  const style = document.createElement('style');
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