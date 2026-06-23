// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt


frappe.pages["ceo-dashboard-1"].on_page_load = function (wrapper) {
  const REPORT_NAME = "CEO Dashboard 1";
  const STORAGE_KEY = "ceo_dash_define_monthly_production";
  const SITE_COLOUR_METHOD =
    "is_production.production.doctype.production_dashboard_setup.production_dashboard_setup.get_site_colour_map";

  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Site Volume Tracking",
    single_column: true
  });

  // -------------------------
  // Runtime site colour mapping
  // Source: Production Dashboard Setup singleton via whitelisted method
  // -------------------------
  let _site_colour_map = null;

  function get_site_colour_map() {
    if (_site_colour_map) {
      return Promise.resolve(_site_colour_map);
    }

    return frappe.call({
      method: SITE_COLOUR_METHOD,
      freeze: false
    })
      .then((r) => {
        _site_colour_map = r.message || {};
        return _site_colour_map;
      })
      .catch((e) => {
        console.error("Could not load Production Dashboard Setup site colours:", e);
        _site_colour_map = {};
        return _site_colour_map;
      });
  }

  function clear_site_colour_cache() {
    _site_colour_map = null;
  }

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
        return;
      }

      localStorage.setItem(STORAGE_KEY, val);
      clear_site_colour_cache();
      load_and_render(false);
      start_aligned_refresh();
    }
  });

  // -------------------------
  // Dashboard container
  // -------------------------
  const $wrap = $(`<div class="isd-dashboard isd-dashboard--ceo-volume"></div>`).appendTo(page.main);
  const $status = $(`<div class="isd-dashboard-status text-muted"></div>`).appendTo($wrap);
  const $dash = $(`<div class="isd-dashboard-grid"></div>`).appendTo($wrap);

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
      nextMinute = 70;
    }

    return (nextMinute - minutes) * 60 * 1000 - seconds * 1000 - ms;
  }

  function start_aligned_refresh() {
    if (_auto_refresh_started) {
      return;
    }

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
  // Selected Define Monthly Production order
  // -------------------------
  function get_site_order_map(docname) {
    if (!docname) {
      return Promise.resolve({});
    }

    return frappe.db.get_doc("Define Monthly Production", docname)
      .then((doc) => {
        const rows = Array.isArray(doc.define) ? doc.define : [];
        const orderMap = {};

        rows.forEach((row, idx) => {
          const site = String(row.site || "").trim();

          if (site && !(site in orderMap)) {
            orderMap[site] = idx;
          }
        });

        return orderMap;
      })
      .catch((e) => {
        console.error("Could not read Define Monthly Production order:", e);
        return {};
      });
  }

  // -------------------------
  // Formatting helpers
  // -------------------------
  function fmt_int(n) {
    const x = Number(n || 0);
    return Math.round(x).toLocaleString();
  }

  function fmt_decimal(n, decimals = 1) {
    const x = Number(n || 0);

    return x.toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });
  }

  function escape_html(value) {
    return frappe.utils.escape_html(value == null ? "" : String(value));
  }

  function good_bad_class_from_value(val) {
    const v = Number(val || 0);
    return v >= 0 ? "isd-dashboard-good" : "isd-dashboard-bad";
  }

  function arrow_up_down(val) {
    const v = Number(val || 0);
    return v >= 0 ? "▲" : "▼";
  }

  // -------------------------
  // KPI builders
  // -------------------------
  function kpi_box(label, value, opts = {}) {
    const coloured = !!opts.coloured;
    const showArrow = !!opts.showArrow;
    const sublabel = opts.sublabel || "";
    const formatter = typeof opts.formatter === "function" ? opts.formatter : fmt_int;

    let classes = "isd-dashboard-kpi";
    let arrow = "";
    let inlineStyle = "";

    if (opts.customBackground) {
      inlineStyle += `background:${opts.customBackground};`;
    }

    if (opts.customTextColor) {
      inlineStyle += `color:${opts.customTextColor};`;
    }

    if (coloured) {
      classes += ` ${good_bad_class_from_value(value)}`;

      if (showArrow) {
        arrow = arrow_up_down(value);
      }
    }

    return `
      <div class="${classes}" style="${inlineStyle}">
        <div class="isd-dashboard-kpi-label">${escape_html(label)}</div>
        ${
          sublabel
            ? `<div class="isd-dashboard-kpi-sub-label">${escape_html(sublabel)}</div>`
            : `<div class="isd-dashboard-kpi-sub-label">&nbsp;</div>`
        }
        <div class="isd-dashboard-kpi-value">
          <span class="isd-dashboard-kpi-trend">
            ${arrow ? `<span class="isd-dashboard-kpi-arrow">${arrow}</span>` : ""}
            <span>${formatter(value)}</span>
          </span>
        </div>
      </div>
    `;
  }

  function kpi_required_vs_original(label, required, original) {
    const req = Number(required || 0);
    const orig = Number(original || 0);

    const good = req <= orig;
    const cls = good ? "isd-dashboard-good" : "isd-dashboard-bad";
    const arrow = good ? "▲" : "▼";

    return `
      <div class="isd-dashboard-kpi ${cls}">
        <div class="isd-dashboard-kpi-label">${escape_html(label)}</div>
        <div class="isd-dashboard-kpi-sub-label">&nbsp;</div>
        <div class="isd-dashboard-kpi-value">
          <span class="isd-dashboard-kpi-trend">
            <span class="isd-dashboard-kpi-arrow">${arrow}</span>
            <span>${fmt_int(req)}</span>
          </span>
        </div>
      </div>
    `;
  }

  // -------------------------
  // Table builders
  // -------------------------
  function th(text, sepClass = "") {
    const classes = ["isd-dashboard-th"];

    if (sepClass) {
      classes.push(sepClass);
    }

    return `
      <th class="${classes.join(" ")}">
        <span class="isd-dashboard-cell-inner">${escape_html(text)}</span>
      </th>
    `;
  }

  function td(value, opts = {}) {
    const classes = ["isd-dashboard-td"];
    const innerClasses = ["isd-dashboard-cell-inner"];

    if (opts.sepClass) {
      classes.push(opts.sepClass);
    }

    if (opts.varClass) {
      innerClasses.push(opts.varClass);
    }

    return `
      <td class="${classes.join(" ")}">
        <span class="${innerClasses.join(" ")}">${fmt_int(value)}</span>
      </td>
    `;
  }

  function variance_class(value) {
    return Number(value || 0) >= 0
      ? "isd-dashboard-var-good"
      : "isd-dashboard-var-bad";
  }

  function build_summary_table(r) {
    const mtd_var = Number(r.mtd_var_bcm || 0);
    const coal_var = Number(r.mtd_coal_var_t || 0);
    const waste_var = Number(r.mtd_waste_var_bcm || 0);
    const day_var = Number(r.day_var_bcm || 0);

    return `
      <table class="isd-dashboard-table isd-dashboard-table--summary">
        <tr>
          ${th("Month Target(bcm)", "isd-dashboard-subsep")}
          ${th("Month Coal(t)", "isd-dashboard-subsep")}
          ${th("Month Waste(bcm)", "isd-dashboard-sep")}

          ${th("MTD Act(bcm)", "isd-dashboard-subsep")}
          ${th("MTD Plan(bcm)", "isd-dashboard-subsep")}
          ${th("Var", "isd-dashboard-sep")}

          ${th("MTD C (t)", "isd-dashboard-subsep")}
          ${th("MTD C Plan(t)", "isd-dashboard-subsep")}
          ${th("Var C", "isd-dashboard-sep")}

          ${th("MTD W (bcm)", "isd-dashboard-subsep")}
          ${th("MTD W Plan(bcm)", "isd-dashboard-subsep")}
          ${th("Var W", "isd-dashboard-sep")}

          ${th("Day BCM", "isd-dashboard-subsep")}
          ${th("Day Target(bcm)", "isd-dashboard-subsep")}
          ${th("Day Var", "isd-dashboard-sep")}
        </tr>
        <tr>
          ${td(r.month_target_bcm, { sepClass: "isd-dashboard-subsep" })}
          ${td(r.month_coal_t, { sepClass: "isd-dashboard-subsep" })}
          ${td(r.month_waste_bcm, { sepClass: "isd-dashboard-sep" })}

          ${td(r.mtd_act_bcm, { sepClass: "isd-dashboard-subsep" })}
          ${td(r.mtd_plan_bcm, { sepClass: "isd-dashboard-subsep" })}
          ${td(r.mtd_var_bcm, {
            sepClass: "isd-dashboard-sep",
            varClass: variance_class(mtd_var)
          })}

          ${td(r.mtd_coal_t, { sepClass: "isd-dashboard-subsep" })}
          ${td(r.mtd_coal_plan_t, { sepClass: "isd-dashboard-subsep" })}
          ${td(r.mtd_coal_var_t, {
            sepClass: "isd-dashboard-sep",
            varClass: variance_class(coal_var)
          })}

          ${td(r.mtd_waste_bcm, { sepClass: "isd-dashboard-subsep" })}
          ${td(r.mtd_waste_plan_bcm, { sepClass: "isd-dashboard-subsep" })}
          ${td(r.mtd_waste_var_bcm, {
            sepClass: "isd-dashboard-sep",
            varClass: variance_class(waste_var)
          })}

          ${td(r.day_bcm, { sepClass: "isd-dashboard-subsep" })}
          ${td(r.day_target_bcm, { sepClass: "isd-dashboard-subsep" })}
          ${td(r.day_var_bcm, {
            sepClass: "isd-dashboard-sep",
            varClass: variance_class(day_var)
          })}
        </tr>
      </table>
    `;
  }

  // -------------------------
  // Card builders
  // -------------------------
  function get_header_background_style(site, siteColourMap) {
    const mappedColour = siteColourMap && siteColourMap[site]
      ? String(siteColourMap[site]).trim()
      : "";

    if (!mappedColour) {
      return "background:transparent;";
    }

    return `background:${mappedColour};`;
  }

  function build_site_card(r, siteColourMap) {
    const site = String(r.site || "").trim();
    const start = r.prod_start ? frappe.datetime.str_to_user(r.prod_start) : "";
    const end = r.prod_end ? frappe.datetime.str_to_user(r.prod_end) : "";
    const forecast_var = Number(r.forecast_var || 0);
    const employeeLabel = `Employees: ${fmt_int(r.employee_count || 0)}`;
    const headerBackground = get_header_background_style(site, siteColourMap);

    return `
      <div class="isd-dashboard-card">
        <div class="isd-dashboard-card-header" style="${headerBackground}">
          <div class="isd-dashboard-card-title">SITE: ${escape_html(site)}</div>
          <div class="isd-dashboard-card-subtitle">
            PRODUCTION PERIOD: ${escape_html(start)} → ${escape_html(end)}
          </div>

          <div class="isd-dashboard-kpi-row">
            ${kpi_box("Month Target", r.month_target_bcm)}
            ${kpi_box("Forecast", r.forecast_bcm)}
            ${kpi_box("Var: Forecast vs.Month Target", forecast_var, {
              coloured: true,
              showArrow: true
            })}
            ${kpi_box("Days Left in Month", r.days_left)}
            ${kpi_box("Original Daily Target", r.original_daily_target)}
            ${kpi_box("Current Avg per Day", r.current_avg_per_day)}
            ${kpi_required_vs_original(
              "Required Daily for Target",
              r.required_daily,
              r.original_daily_target
            )}
            ${kpi_box("Projected BCM/man", r.projected_bcm_per_man, {
              sublabel: employeeLabel,
              formatter: (v) => fmt_decimal(v, 1),
              customBackground: "#d9f0ff",
              customTextColor: "#000000"
            })}
          </div>
        </div>

        <div class="isd-dashboard-table-wrap">
          ${build_summary_table(r)}
        </div>
      </div>
    `;
  }

  function render_dashboard(rows, siteOrderMap, siteColourMap) {
    if (!rows || !rows.length) {
      $dash.html(`<div class="text-muted">No data for the selected filter.</div>`);
      return;
    }

    const sorted = [...rows].sort((a, b) => {
      const aSite = String(a.site || "").trim();
      const bSite = String(b.site || "").trim();

      const aHasOrder = Object.prototype.hasOwnProperty.call(siteOrderMap, aSite);
      const bHasOrder = Object.prototype.hasOwnProperty.call(siteOrderMap, bSite);

      if (aHasOrder && bHasOrder) {
        return siteOrderMap[aSite] - siteOrderMap[bSite];
      }

      if (aHasOrder) {
        return -1;
      }

      if (bHasOrder) {
        return 1;
      }

      return aSite.localeCompare(bSite);
    });

    $dash.html(sorted.map((row) => build_site_card(row, siteColourMap)).join(""));
  }

  // -------------------------
  // Main loader
  // -------------------------
  function load_and_render(is_auto) {
    const val = dmp.get_value();

    if (!val) {
      return Promise.resolve();
    }

    $status.text(is_auto ? "Refreshing…" : "Loading…");

    return Promise.all([
      run_report({ define_monthly_production: val }),
      get_site_order_map(val),
      get_site_colour_map()
    ])
      .then(([res, siteOrderMap, siteColourMap]) => {
        const payload = res.message || {};
        const rows = payload.result || [];

        render_dashboard(rows, siteOrderMap, siteColourMap);

        const time = new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit"
        });

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
    if (_timer) {
      clearTimeout(_timer);
    }

    _timer = null;
    _auto_refresh_started = false;
    _refreshing = false;
  };
};