// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.pages["hourly-dashboard"].on_page_load = function (wrapper) {
  const REPORT_NAME = "Hourly Dashboard";
  const STORAGE_KEY = "hourly_dash_define_monthly_production";

  const SLOT_LABELS = [
    "06-07", "07-08", "08-09", "09-10", "10-11", "11-12", "12-13",
    "13-14", "14-15", "15-16", "16-17", "17-18",
    "18-19", "19-20", "20-21", "21-22", "22-23", "23-24",
    "24-01", "01-02", "02-03", "03-04", "04-05", "05-06"
  ];

  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Hourly Dashboard",
    single_column: true
  });

  // -------------------------
  // Filter
  // -------------------------
  const dmp = page.add_field({
    fieldtype: "Link",
    label: __("Define Monthly Production"),
    fieldname: "define_monthly_production",
    options: "Define Monthly Production",
    reqd: 1,
    change: () => {
      const val = dmp.get_value();

      if (!val) {
        localStorage.removeItem(STORAGE_KEY);
        $status.text("Select a Define Monthly Production to load the dashboard.");
        $dash.empty();
        return;
      }

      localStorage.setItem(STORAGE_KEY, val);
      load_and_render(false);
      start_aligned_refresh();
    }
  });

  // -------------------------
  // Dashboard container
  // -------------------------
  const $wrap = $(`<div style="margin-top: 12px;"></div>`).appendTo(page.main);
  const $status = $(`<div class="text-muted" style="margin-bottom: 10px;"></div>`).appendTo($wrap);
  const $dash = $(`<div class="isd-hourly-dashboard-page"></div>`).appendTo($wrap);

  // -------------------------
  // Refresh scheduler (:10 and :30)
  // -------------------------
  let _auto_refresh_started = false;
  let _refreshing = false;
  let _timer = null;

  function ms_until_next_refresh() {
    const now = new Date();
    const minutes = now.getMinutes();
    const seconds = now.getSeconds();
    const ms = now.getMilliseconds();

    let nextMinute;

    if (minutes < 10) {
      nextMinute = 10;
    } else if (minutes < 30) {
      nextMinute = 30;
    } else {
      nextMinute = 70; // next hour + 10
    }

    return (nextMinute - minutes) * 60 * 1000 - seconds * 1000 - ms;
  }

  function start_aligned_refresh() {
    if (_auto_refresh_started) return;

    _auto_refresh_started = true;

    const schedule_next = () => {
      clear_existing_timer();
      _timer = setTimeout(auto_refresh, ms_until_next_refresh());
    };

    const auto_refresh = () => {
      if (_refreshing) {
        schedule_next();
        return;
      }

      if (!dmp.get_value()) {
        schedule_next();
        return;
      }

      _refreshing = true;

      load_and_render(true)
        .finally(() => {
          _refreshing = false;
          schedule_next();
        });
    };

    schedule_next();
  }

  function clear_existing_timer() {
    if (_timer) {
      clearTimeout(_timer);
      _timer = null;
    }
  }

  // -------------------------
  // Report runner
  // -------------------------
  function run_report(filters) {
    return frappe.call({
      method: "frappe.desk.query_report.run",
      args: {
        report_name: REPORT_NAME,
        filters: filters
      },
      freeze: false
    });
  }

  // -------------------------
  // Helpers
  // -------------------------
  function escape_html(value) {
    return frappe.utils.escape_html(value == null ? "" : String(value));
  }

  function slot_field(slotNumber) {
    return `slot_${String(slotNumber).padStart(2, "0")}`;
  }

  function normalise_int(value) {
    const parsed = parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function get_cell_display(value) {
    value = normalise_int(value);

    if (value === 0) {
      return {
        css_class: "isd-blank",
        display: "",
        title: ""
      };
    }

    if (value >= 1 && value <= 199) {
      return {
        css_class: "isd-low",
        display: String(value),
        title: `${value} bcm`
      };
    }

    if (value >= 200 && value <= 219) {
      return {
        css_class: "isd-medium",
        display: String(value),
        title: `${value} bcm`
      };
    }

    return {
      css_class: "isd-high",
      display: String(value),
      title: `${value} bcm`
    };
  }

  function extract_rows_from_response(res) {
    const payload = res && res.message ? res.message : res;

    if (!payload) return [];

    if (Array.isArray(payload.result)) {
      return payload.result;
    }

    if (Array.isArray(payload.data)) {
      return payload.data;
    }

    if (Array.isArray(payload)) {
      return payload;
    }

    return [];
  }

  function group_rows_by_site(rows) {
    const siteMap = new Map();

    rows.forEach((row) => {
      const site = (row.site || "").trim();
      if (!site) return;

      if (!siteMap.has(site)) {
        siteMap.set(site, {
          site: site,
          site_order: normalise_int(row.site_order),
          production_day: row.production_day || "",
          header_colour: row.header_colour || "#FFFFFF",
          rows: []
        });
      }

      const group = siteMap.get(site);

      // Keep the first meaningful metadata values.
      if (!group.production_day && row.production_day) {
        group.production_day = row.production_day;
      }

      if ((!group.header_colour || group.header_colour === "#FFFFFF") && row.header_colour) {
        group.header_colour = row.header_colour;
      }

      if (!row.is_empty_site) {
        group.rows.push(row);
      }
    });

    return Array.from(siteMap.values()).sort((a, b) => {
      if (a.site_order !== b.site_order) {
        return a.site_order - b.site_order;
      }

      return a.site.localeCompare(b.site);
    });
  }

  function render_hour_header() {
    const hourHeaders = SLOT_LABELS.map((label) => {
      const escapedLabel = escape_html(label);
      const displayLabel = escapedLabel.replace("-", "<br>");

      return `<th title="${escapedLabel}">${displayLabel}</th>`;
    }).join("");

    return `<tr><th>Excavator</th>${hourHeaders}</tr>`;
  }

  function render_excavator_row(row) {
    const excavator = escape_html(row.excavator || "");

    const cells = [
      `<td class="isd-ex" title="${excavator}">${excavator}</td>`
    ];

    for (let slot = 1; slot <= 24; slot++) {
      const value = normalise_int(row[slot_field(slot)]);
      const cell = get_cell_display(value);
      const titleAttr = cell.title ? ` title="${escape_html(cell.title)}"` : "";

      cells.push(
        `<td class="${cell.css_class}"${titleAttr}>${escape_html(cell.display)}</td>`
      );
    }

    return `<tr>${cells.join("")}</tr>`;
  }

  function render_site_block(group) {
    const rowsHtml = group.rows.map(render_excavator_row).join("");

    return `
      <div class="isd-site">
        <div class="isd-site-header" style="background-color: ${escape_html(group.header_colour)};">
          <div>Site: ${escape_html(group.site)}</div>
          <div class="isd-site-sub">Production Day: ${escape_html(group.production_day)}</div>
        </div>

        <div class="isd-table-wrap">
          <table>
            ${render_hour_header()}
            ${rowsHtml}
          </table>
        </div>
      </div>
    `;
  }

  function render_dashboard(rows) {
    if (!rows.length) {
      $dash.html(`<div class="text-muted">No data for the selected filter.</div>`);
      return;
    }

    const groupedSites = group_rows_by_site(rows);

    if (!groupedSites.length) {
      $dash.html(`<div class="text-muted">No sites found for the selected filter.</div>`);
      return;
    }

    const html = `
      <div class="isd-hourly-dashboard">
        <div class="isd-grid">
          ${groupedSites.map(render_site_block).join("")}
        </div>
      </div>
    `;

    $dash.html(html);
  }

  // -------------------------
  // Main loader
  // -------------------------
  function load_and_render(is_auto) {
    const val = dmp.get_value();

    if (!val) {
      return Promise.resolve();
    }

    $status.text(is_auto ? "Refreshing..." : "Loading...");

    return run_report({ define_monthly_production: val })
      .then((res) => {
        const rows = extract_rows_from_response(res);
        render_dashboard(rows);

        const time = new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit"
        });

        $status.text(`Last updated: ${time} (refreshes at :10 and :30)`);

        if (is_auto) {
          frappe.show_alert(
            {
              message: `Hourly Dashboard updated at ${time}`,
              indicator: "green"
            },
            5
          );
        }
      })
      .catch((e) => {
        console.error(e);
        $status.text("Error loading dashboard data.");
        $dash.html(`<div class="text-danger">Could not load data. Check console / server logs.</div>`);
      });
  }

  // -------------------------
  // Restore last selection
  // -------------------------
  const last = localStorage.getItem(STORAGE_KEY);

  if (last) {
    dmp.set_value(last);

    setTimeout(() => {
      if (dmp.get_value()) {
        load_and_render(false);
        start_aligned_refresh();
      }
    }, 0);
  } else {
    $status.text("Select a Define Monthly Production to load the dashboard.");
  }

  // -------------------------
  // Cleanup
  // -------------------------
  frappe.pages["hourly-dashboard"].on_page_unload = function () {
    clear_existing_timer();
    _auto_refresh_started = false;
    _refreshing = false;
  };
};