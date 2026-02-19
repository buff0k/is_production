frappe.pages["ceo-dashboard-1"].on_page_load = function (wrapper) {
  const REPORT_NAME = "CEO DASHBOARD";
  const STORAGE_KEY = "ceo_dash_define_monthly_production";

  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Site Volume Tracking",
    single_column: true
  });

  // -------------------------
  // Filter (Define Monthly Production)
  // -------------------------
  const dmp = page.add_field({
    fieldtype: "Link",
    label: __("Define Monthly Production"),
    fieldname: "define_monthly_production",
    options: "Define Monthly Production",
    reqd: 1,
    change: () => {
      const val = dmp.get_value();
      if (!val) return;

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
  const $dash = $(`<div class="dashboard-grid"></div>`).appendTo($wrap);

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
    if (minutes < 10) nextMinute = 10;
    else if (minutes < 30) nextMinute = 30;
    else nextMinute = 70; // next hour + 10

    return (nextMinute - minutes) * 60 * 1000 - seconds * 1000 - ms;
  }

  function start_aligned_refresh() {
    if (_auto_refresh_started) return;
    _auto_refresh_started = true;

    const schedule_next = () => {
      const delay = ms_until_next_refresh();
      _timer = setTimeout(auto_refresh, delay);
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
      load_and_render(true).finally(() => {
        _refreshing = false;
        schedule_next();
      });
    };

    schedule_next();
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
  // Helpers (formatting)
  // -------------------------
  function fmt_int(n) {
    const x = Number(n || 0);
    return Math.round(x).toLocaleString();
  }

  function cls_good_bad_from_value(val) {
    const v = Number(val || 0);
    return v >= 0 ? "isd-good" : "isd-bad";
  }

  function arrow_up_down(val) {
    const v = Number(val || 0);
    return v >= 0 ? "▲" : "▼";
  }

  function kpi_box(label, value, opts = {}) {
    const coloured = !!opts.coloured;
    const showArrow = !!opts.showArrow;

    let extraCls = "";
    let arrow = "";

    if (coloured) {
      extraCls = cls_good_bad_from_value(value);
      if (showArrow) arrow = arrow_up_down(value);
    }

    return `
      <div class="kpi-box ${extraCls}">
        <div class="label">${frappe.utils.escape_html(label)}</div>
        <div class="value">
          <span class="trend">
            ${arrow ? `<span class="arrow">${arrow}</span>` : ""}
            <span>${fmt_int(value)}</span>
          </span>
        </div>
      </div>
    `;
  }

  function kpi_required_vs_original(label, required, original) {
    const req = Number(required || 0);
    const orig = Number(original || 0);

    const good = req <= orig;
    const cls = good ? "isd-good" : "isd-bad";
    const arrow = good ? "▲" : "▼";

    return `
      <div class="kpi-box ${cls}">
        <div class="label">${frappe.utils.escape_html(label)}</div>
        <div class="value">
          <span class="trend">
            <span class="arrow">${arrow}</span>
            <span>${fmt_int(req)}</span>
          </span>
        </div>
      </div>
    `;
  }

  // -------------------------
  // THINNER BORDER TABLE (inline styles override your thick CSS)
  // -------------------------
  const BORDER_BLACK = "#000000";
  const OUTER_BORDER_PX = 2;   // thinner outer border
  const GRID_PX = 1;           // thin cell grid lines
  const SEP_PX = 2;            // thinner group separator
  const SUBSEP_PX = 1;         // thin within-group separator

  function th(text, cls = "") {
    // Base cell border
    let style = `border:${GRID_PX}px solid ${BORDER_BLACK};padding:6px 6px;text-align:center;`;

    if (cls === "sep") style += `border-right:${SEP_PX}px solid ${BORDER_BLACK};`;
    if (cls === "subsep") style += `border-right:${SUBSEP_PX}px solid ${BORDER_BLACK};`;

    return `<th class="${cls}" style="${style}">${frappe.utils.escape_html(text)}</th>`;
  }

  function td(value, opts = {}) {
    const cls = opts.cls || "";
    const bg = opts.bg ? `background:${opts.bg};` : "";

    let style = `border:${GRID_PX}px solid ${BORDER_BLACK};padding:6px 6px;text-align:center;${bg}`;

    if (cls === "sep") style += `border-right:${SEP_PX}px solid ${BORDER_BLACK};`;
    if (cls === "subsep") style += `border-right:${SUBSEP_PX}px solid ${BORDER_BLACK};`;

    return `<td class="${cls}" style="${style}">${fmt_int(value)}</td>`;
  }

  function build_summary_table(r) {
    const GREEN = "#C9F2D8";
    const RED = "#F9CACA";

    const mtd_var = Number(r.mtd_var_bcm || 0);
    const coal_var = Number(r.mtd_coal_var_t || 0);
    const waste_var = Number(r.mtd_waste_var_bcm || 0);
    const day_var = Number(r.day_var_bcm || 0);

    // Explicit outer border + collapse to keep it compact
    const tableStyle = `
      width:100%;
      border-collapse:collapse;
      border:${OUTER_BORDER_PX}px solid ${BORDER_BLACK};
    `;

    return `
      <table class="summary-table" style="${tableStyle}">
        <tr>
          ${th("Month Target(bcm)", "subsep")}
          ${th("Month Coal(t)", "subsep")}
          ${th("Month Waste(bcm)", "sep")}

          ${th("MTD Act(bcm)", "subsep")}
          ${th("MTD Plan(bcm)", "subsep")}
          ${th("Var", "sep")}

          ${th("MTD C (t)", "subsep")}
          ${th("MTD C Plan(t)", "subsep")}
          ${th("Var C", "sep")}

          ${th("MTD W (bcm)", "subsep")}
          ${th("MTD W Plan(bcm)", "subsep")}
          ${th("Var W", "sep")}

          ${th("Day BCM", "subsep")}
          ${th("Day Target(bcm)", "subsep")}
          ${th("Day Var", "sep")}
        </tr>
        <tr>
          ${td(r.month_target_bcm, { cls: "subsep" })}
          ${td(r.month_coal_t, { cls: "subsep" })}
          ${td(r.month_waste_bcm, { cls: "sep" })}

          ${td(r.mtd_act_bcm, { cls: "subsep" })}
          ${td(r.mtd_plan_bcm, { cls: "subsep" })}
          ${td(r.mtd_var_bcm, { cls: "sep", bg: mtd_var >= 0 ? GREEN : RED })}

          ${td(r.mtd_coal_t, { cls: "subsep" })}
          ${td(r.mtd_coal_plan_t, { cls: "subsep" })}
          ${td(r.mtd_coal_var_t, { cls: "sep", bg: coal_var >= 0 ? GREEN : RED })}

          ${td(r.mtd_waste_bcm, { cls: "subsep" })}
          ${td(r.mtd_waste_plan_bcm, { cls: "subsep" })}
          ${td(r.mtd_waste_var_bcm, { cls: "sep", bg: waste_var >= 0 ? GREEN : RED })}

          ${td(r.day_bcm, { cls: "subsep" })}
          ${td(r.day_target_bcm, { cls: "subsep" })}
          ${td(r.day_var_bcm, { cls: "sep", bg: day_var >= 0 ? GREEN : RED })}
        </tr>
      </table>
    `;
  }

  function build_site_card(r) {
    const site = r.site || "";
    const start = r.prod_start ? frappe.datetime.str_to_user(r.prod_start) : "";
    const end = r.prod_end ? frappe.datetime.str_to_user(r.prod_end) : "";
    const bg = r.site_colour || "#EEF4FB";

    const forecast_var = Number(r.forecast_var || 0);

    return `
      <div class="site-section">
        <div style="padding:8px;background:${bg};">
          <div style="font-size:17px;">SITE: ${frappe.utils.escape_html(site)}</div>
          <div style="font-size:12px;">
            PRODUCTION PERIOD: ${frappe.utils.escape_html(start)} → ${frappe.utils.escape_html(end)}
          </div>

          <div class="kpi-bar">
            ${kpi_box("Month Target", r.month_target_bcm)}
            ${kpi_box("Forecast", r.forecast_bcm)}
            ${kpi_box("Var: Forecast vs.Month Target", forecast_var, { coloured: true, showArrow: true })}
            ${kpi_box("Days Left in Month", r.days_left)}
            ${kpi_box("Original Daily Target", r.original_daily_target)}
            ${kpi_box("Current Avg per Day", r.current_avg_per_day)}
            ${kpi_required_vs_original("Required Daily for Target", r.required_daily, r.original_daily_target)}
          </div>
        </div>

        <div style="padding:6px;">
          ${build_summary_table(r)}
        </div>
      </div>
    `;
  }

  function render_dashboard(rows) {
    if (!rows || !rows.length) {
      $dash.html(`<div class="text-muted">No data for the selected filter.</div>`);
      return;
    }

    const sorted = [...rows].sort((a, b) => String(a.site || "").localeCompare(String(b.site || "")));
    $dash.html(sorted.map(build_site_card).join(""));
  }

  // -------------------------
  // Main loader
  // -------------------------
  function load_and_render(is_auto) {
    const val = dmp.get_value();
    if (!val) return Promise.resolve();

    $status.text(is_auto ? "Refreshing…" : "Loading…");

    return run_report({ define_monthly_production: val })
      .then((res) => {
        const payload = res.message || {};
        const rows = payload.result || [];
        render_dashboard(rows);

        const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        $status.text(`Last updated: ${time} (refreshes at :10 and :30)`);
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
  frappe.pages["ceo-dashboard-1"].on_page_unload = function () {
    if (_timer) clearTimeout(_timer);
    _timer = null;
    _auto_refresh_started = false;
    _refreshing = false;
  };
};
