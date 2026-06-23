// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt


frappe.pages["weekly-production-da"].on_page_load = function (wrapper) {
  render_weekly_production_dashboard_page(wrapper);
};

function render_weekly_production_dashboard_page(wrapper) {
  const REPORT_NAME = "Weekly Production Dashboard";
  const STORAGE_KEY = "weekly_production_dashboard_filters";

  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Weekly Production Dashboard",
    single_column: true
  });

  let _refreshing = false;
  let _auto_load_timer = null;

  // -------------------------
  // Filters
  // -------------------------
  const start_date = page.add_field({
    fieldtype: "Date",
    label: __("Start Date"),
    fieldname: "start_date",
    reqd: 1,
    default: frappe.datetime.month_start(),
    change: () => {
      save_filters();
      auto_load();
    }
  });

  const end_date = page.add_field({
    fieldtype: "Date",
    label: __("End Date"),
    fieldname: "end_date",
    reqd: 1,
    default: frappe.datetime.get_today(),
    change: () => {
      save_filters();
      auto_load();
    }
  });

  const site = page.add_field({
    fieldtype: "Link",
    label: __("Site"),
    fieldname: "site",
    options: "Location",
    reqd: 1,
    default: "Klipfontein",
    change: () => {
      save_filters();
      auto_load();
    }
  });

  page.add_inner_button(__("Load Dashboard"), () => {
    save_filters();
    load_and_render(false);
  });

  // -------------------------
  // Dashboard container
  // -------------------------
  const $wrap = $(`<div class="isd-dashboard isd-dashboard--weekly-production"></div>`).appendTo(page.main);
  const $status = $(`<div class="isd-dashboard-status text-muted"></div>`).appendTo($wrap);
  const $dash = $(`<div class="isd-weekly-dashboard-root"></div>`).appendTo($wrap);

  // -------------------------
  // Filter state
  // -------------------------
  function get_filters() {
    return {
      start_date: start_date.get_value(),
      end_date: end_date.get_value(),
      site: site.get_value()
    };
  }

  function has_required_filters(filters) {
    return !!(filters.start_date && filters.end_date && filters.site);
  }

  function save_filters() {
    const filters = get_filters();
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filters));
  }

  function restore_filters() {
    let saved = {};

    try {
      saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    } catch (e) {
      saved = {};
    }

    if (saved.start_date) {
      start_date.set_value(saved.start_date);
    }

    if (saved.end_date) {
      end_date.set_value(saved.end_date);
    }

    if (saved.site) {
      site.set_value(saved.site);
    }
  }

  function auto_load() {
    clearTimeout(_auto_load_timer);

    _auto_load_timer = setTimeout(() => {
      const filters = get_filters();

      if (!has_required_filters(filters)) {
        $status.text("Select Start Date, End Date, and Site to load the dashboard.");
        $dash.empty();
        return;
      }

      load_and_render(false);
    }, 400);
  }

  // -------------------------
  // Report runner
  // Uses native Promise to avoid Frappe/jQuery Deferred .finally issues
  // -------------------------
  function run_report(filters) {
    return new Promise((resolve, reject) => {
      frappe.call({
        method: "frappe.desk.query_report.run",
        args: {
          report_name: REPORT_NAME,
          filters: filters
        },
        freeze: false,
        callback: function (r) {
          resolve(r);
        },
        error: function (r) {
          reject(r);
        }
      });
    });
  }

  function extract_rows_from_response(res) {
    const payload = res && res.message ? res.message : res;

    if (!payload) {
      return [];
    }

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

  function extract_dashboard_data(res) {
    const rows = extract_rows_from_response(res);

    if (!rows.length || !rows[0].dashboard_json) {
      return null;
    }

    try {
      return JSON.parse(rows[0].dashboard_json);
    } catch (e) {
      console.error(
        "Could not parse Weekly Production Dashboard JSON:",
        e,
        rows[0].dashboard_json
      );
      return null;
    }
  }

  // -------------------------
  // Formatting helpers
  // -------------------------
  function escape_html(value) {
    return frappe.utils.escape_html(value == null ? "" : String(value));
  }

  function as_number(value) {
    if (value === null || value === undefined || value === "") {
      return 0;
    }

    if (typeof value === "number") {
      return value;
    }

    return Number(String(value).replace(/,/g, "").replace(/%/g, "").trim()) || 0;
  }

  function format_number(value, decimals = 0) {
    return as_number(value).toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });
  }

  function format_percent(value) {
    return `${as_number(value).toFixed(1)}%`;
  }

  function clamp_progress(value) {
    return Math.max(0, Math.min(100, as_number(value)));
  }

  function is_coal_excluded_site(filters) {
    const site_name = String(filters.site || "").toLowerCase();

    return (
      site_name.includes("mimosa") ||
      site_name.includes("kriel rehab") ||
      site_name.includes("kriel rehabilitation") ||
      site_name.includes("kriel-rehab") ||
      site_name.includes("kriel_rehab")
    );
  }

  // -------------------------
  // Card renderers
  // -------------------------
  function render_progress_card(title, data) {
    data = data || {};
    const progress = clamp_progress(data.progress);

    return `
      <div class="isd-weekly-card">
        <h2>${escape_html(title)}</h2>

        <div class="isd-weekly-metric-row">
          <span>Target</span>
          <strong>${format_number(data.target)}</strong>
        </div>

        <div class="isd-weekly-metric-row">
          <span>Actual MTD</span>
          <strong>${format_number(data.actual)}</strong>
        </div>

        <div class="isd-weekly-metric-row">
          <span>Remaining</span>
          <strong>${format_number(data.remaining)}</strong>
        </div>

        <div class="isd-weekly-progress-text">
          ${format_percent(data.progress)} of monthly target
        </div>

        <div class="isd-weekly-progress-bg">
          <div class="isd-weekly-progress-fill" style="width: ${progress}%"></div>
        </div>
      </div>
    `;
  }

  function render_diesel_card(data) {
    data = data || {};

    return `
      <div class="isd-weekly-card">
        <h2>Diesel Usage Update</h2>

        <div class="isd-weekly-metric-row">
          <span>Month-to-date diesel usage</span>
          <strong>${format_number(data.usage, 1)} L</strong>
        </div>

        <div class="isd-weekly-metric-row isd-weekly-diesel-cap">
          <span>Diesel Cap</span>
          <strong>${format_number(data.cap, 2)}</strong>
        </div>
      </div>
    `;
  }

  function render_equipment_table(equipment) {
    equipment = Array.isArray(equipment) ? equipment : [];

    if (!equipment.length) {
      return `
        <div class="isd-weekly-empty">
          No equipment data found from Avail and Util summary.
        </div>
      `;
    }

    const rows = equipment.map((row) => {
      return `
        <tr>
          <td>${escape_html(row.equipment)}</td>
          <td>${format_percent(row.availability)}</td>
          <td>${format_percent(row.utilisation)}</td>
        </tr>
      `;
    }).join("");

    return `
      <table class="isd-weekly-equipment-table">
        <thead>
          <tr>
            <th>Equipment</th>
            <th>Avail</th>
            <th>Utt</th>
          </tr>
        </thead>
        <tbody>
          ${rows}
        </tbody>
      </table>
    `;
  }

  function render_recommendations(bcm, coal, diesel, equipment, filters) {
    bcm = bcm || {};
    coal = coal || {};
    diesel = diesel || {};
    equipment = Array.isArray(equipment) ? equipment : [];
    filters = filters || {};

    const recommendations = [];
    const exclude_coal_recommendations = is_coal_excluded_site(filters);

    const bcm_progress = as_number(bcm.progress);
    const coal_progress = as_number(coal.progress);
    const bcm_remaining = Math.abs(as_number(bcm.remaining));
    const coal_remaining = Math.abs(as_number(coal.remaining));

    if (exclude_coal_recommendations) {
      if (bcm_progress < 90) {
        recommendations.push(
          `Production is behind: BCM is at ${format_percent(bcm_progress)} of monthly target. Create a catch-up plan for remaining ${format_number(bcm_remaining)} BCM.`
        );
      } else if (bcm_progress >= 100) {
        recommendations.push(
          `Production is above target: BCM is at ${format_percent(bcm_progress)} of monthly target. Maintain the current production rate and monitor equipment availability, utilisation, and diesel usage.`
        );
      } else {
        recommendations.push(
          `Production is tracking close to target: BCM is at ${format_percent(bcm_progress)} of monthly target. Continue monitoring daily production, equipment availability, utilisation, and diesel usage.`
        );
      }
    } else {
      if (bcm_progress < 90 && coal_progress < 90) {
        recommendations.push(
          `Production is behind: BCM is at ${format_percent(bcm_progress)} and Coal is at ${format_percent(coal_progress)} of monthly target. Create a catch-up plan for remaining ${format_number(bcm_remaining)} BCM and ${format_number(coal_remaining)} tons coal.`
        );
      } else if (bcm_progress < 90 && coal_progress >= 100) {
        recommendations.push(
          `BCM production is behind at ${format_percent(bcm_progress)} of monthly target, while Coal is above target at ${format_percent(coal_progress)}. Create a BCM catch-up plan for remaining ${format_number(bcm_remaining)} BCM and maintain coal performance.`
        );
      } else if (bcm_progress >= 100 && coal_progress < 90) {
        recommendations.push(
          `BCM production is above target at ${format_percent(bcm_progress)}, but Coal is behind at ${format_percent(coal_progress)} of monthly target. Prioritise coal exposure and coal hauling to recover remaining ${format_number(coal_remaining)} tons coal.`
        );
      } else if (bcm_progress >= 100 && coal_progress >= 100) {
        recommendations.push(
          `Production is above target: BCM is at ${format_percent(bcm_progress)} and Coal is at ${format_percent(coal_progress)} of monthly target. Maintain the current production rate and keep monitoring equipment and diesel performance.`
        );
      } else {
        recommendations.push(
          `Production is tracking close to target: BCM is at ${format_percent(bcm_progress)} and Coal is at ${format_percent(coal_progress)} of monthly target. Continue monitoring daily targets, coal movement, equipment availability, utilisation, and diesel usage.`
        );
      }

      if (coal_progress < bcm_progress && coal_progress < 90) {
        recommendations.push(
          "Prioritise coal exposure and coal hauling; review drill/blast, loading areas, tip availability, and shift targets daily."
        );
      }
    }

    if (equipment.length) {
      const lowest_util = equipment.reduce((lowest, row) => {
        return as_number(row.utilisation) < as_number(lowest.utilisation) ? row : lowest;
      }, equipment[0]);

      recommendations.push(
        `Review ${lowest_util.equipment} utilisation; ${lowest_util.equipment} utilisation is lowest at ${format_percent(lowest_util.utilisation)}. Check queuing, road conditions, dispatching, and idle time.`
      );

      equipment.forEach((row) => {
        if (as_number(row.availability) < 85) {
          recommendations.push(
            `${row.equipment} utilisation is ${format_percent(row.utilisation)} and availability is ${format_percent(row.availability)}; plan maintenance windows and standby support to avoid breakdown losses.`
          );
        }

        if (as_number(row.availability) >= 90 && as_number(row.utilisation) < 85) {
          recommendations.push(
            `${row.equipment} availability is good at ${format_percent(row.availability)} but utilisation is ${format_percent(row.utilisation)}; align machines to critical production areas and minimise idle time.`
          );
        }
      });
    }

    if (as_number(diesel.usage) > 0) {
      recommendations.push(
        `Diesel usage is ${format_number(diesel.usage, 1)} L; keep monitoring litres/BCM, idling, fuel issue controls, and investigate any abnormal consumption.`
      );
    }

    if (!recommendations.length) {
      if (exclude_coal_recommendations) {
        recommendations.push(
          "Production and equipment performance are tracking within expected limits. Continue monitoring daily BCM targets, equipment availability, utilisation, and diesel usage."
        );
      } else {
        recommendations.push(
          "Production and equipment performance are tracking within expected limits. Continue monitoring daily targets, equipment availability, utilisation, coal movement, and diesel usage."
        );
      }
    }

    return `
      <ul class="isd-weekly-recommendations">
        ${recommendations.map((item) => `<li>${escape_html(item)}</li>`).join("")}
      </ul>
    `;
  }

  function render_dashboard(dashboard_data) {
    if (!dashboard_data) {
      $dash.html(`
        <div class="isd-weekly-error">
          Dashboard data did not load. Change filters or click Load Dashboard.
        </div>
      `);
      return;
    }

    const filters = dashboard_data.filters || get_filters();
    const bcm = dashboard_data.bcm || {};
    const coal = dashboard_data.coal || {};
    const diesel = dashboard_data.diesel || {};
    const equipment = Array.isArray(dashboard_data.equipment)
      ? dashboard_data.equipment
      : [];

    const site_name = String(filters.site || "").toUpperCase();

    $dash.html(`
      <div class="isd-weekly-shell">
        <div class="isd-weekly-header">
          <div>
            <h1>${escape_html(site_name)} Weekly Production Meeting</h1>
          </div>

          <div class="isd-weekly-date">
            ${escape_html(filters.start_date)} to ${escape_html(filters.end_date)}
          </div>
        </div>

        <div class="isd-weekly-top-grid">
          ${render_progress_card("Monthly BCM Progress", bcm)}
          ${render_progress_card("Monthly Coal Progress", coal)}
          ${render_diesel_card(diesel)}
        </div>

        <div class="isd-weekly-bottom-grid">
          <div class="isd-weekly-card">
            <h2>Availability & Utilisation</h2>
            <div class="isd-weekly-section-title">Equipment Performance</div>
            ${render_equipment_table(equipment)}
          </div>

          <div class="isd-weekly-card">
            <h2>Recommendations</h2>
            ${render_recommendations(bcm, coal, diesel, equipment, filters)}
          </div>
        </div>
      </div>
    `);
  }

  function load_and_render(is_auto) {
    const filters = get_filters();

    if (!has_required_filters(filters)) {
      $status.text("Select Start Date, End Date, and Site to load the dashboard.");
      $dash.empty();
      return;
    }

    if (_refreshing) {
      return;
    }

    _refreshing = true;
    $status.text(is_auto ? "Refreshing..." : "Loading...");

    run_report(filters)
      .then((res) => {
        const dashboard_data = extract_dashboard_data(res);

        render_dashboard(dashboard_data);

        const time = new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit"
        });

        $status.text(`Last updated: ${time}`);

        if (is_auto) {
          frappe.show_alert(
            {
              message: `Weekly Production Dashboard updated at ${time}`,
              indicator: "green"
            },
            5
          );
        }

        _refreshing = false;
      })
      .catch((e) => {
        console.error(e);

        $status.text("Error loading Weekly Production Dashboard.");
        $dash.html(`
          <div class="isd-weekly-error">
            Could not load dashboard. Check console / server logs.
          </div>
        `);

        _refreshing = false;
      });
  }

  // -------------------------
  // Initial load
  // -------------------------
  restore_filters();

  setTimeout(() => {
    const filters = get_filters();

    if (has_required_filters(filters)) {
      load_and_render(false);
    } else {
      $status.text("Select Start Date, End Date, and Site to load the dashboard.");
    }
  }, 0);

  // -------------------------
  // Cleanup
  // -------------------------
  frappe.pages["weekly-production-da"].on_page_unload = function () {
    if (_auto_load_timer) {
      clearTimeout(_auto_load_timer);
      _auto_load_timer = null;
    }

    _refreshing = false;
  };
}