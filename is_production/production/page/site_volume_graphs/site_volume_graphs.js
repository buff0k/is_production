(function () {
  const PAGE_KEYS = ["site-volume-graphs", "site_volume_graphs"];

  PAGE_KEYS.forEach((pageKey) => {
    frappe.pages[pageKey] = frappe.pages[pageKey] || {};

    frappe.pages[pageKey].on_page_load = function (wrapper) {
      render_site_volume_graphs_page(wrapper, pageKey);
    };
  });
})();

function render_site_volume_graphs_page(wrapper, pageKey) {
  const REPORT_NAME = "CEO Dashboard One Graphs";
  const STORAGE_KEY = "site_volume_graphs_define_monthly_production";
  const SITE_COLOUR_METHOD =
    "is_production.production.doctype.production_dashboard_setup.production_dashboard_setup.get_site_colour_map";

  const TARGET_LINE_COLOR = "#9E9E9E";
  const ACTUAL_ABOVE_TARGET_COLOR = "#2fb344";
  const ACTUAL_BELOW_TARGET_COLOR = "#e24c4c";
  const CURRENT_DATE_POINT_COLOR = "#2fb344";

  const TARGET_POINT_RADIUS = 3;
  const ACTUAL_POINT_RADIUS = 3;
  const CURRENT_DATE_POINT_RADIUS = 3.75;

  const DEFAULT_Y_AXIS_STEP = 10000;

  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Site Volume Graphs",
    single_column: true
  });

  let _site_colour_map = null;
  let _charts = [];
  let _auto_refresh_started = false;
  let _refreshing = false;
  let _timer = null;

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
        destroy_charts();
        $status.text("Select a Define Monthly Production to load the graphs.");
        $dash.empty();
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
  const $wrap = $(`<div class="isd-dashboard isd-dashboard--ceo-graphs"></div>`).appendTo(page.main);
  const $status = $(`<div class="isd-dashboard-status text-muted"></div>`).appendTo($wrap);
  const $dash = $(`<div class="isd-dashboard-grid"></div>`).appendTo($wrap);

  // -------------------------
  // Global site colours
  // -------------------------
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

  function get_header_background_style(site, siteColourMap) {
    const mappedColour = siteColourMap && siteColourMap[site]
      ? String(siteColourMap[site]).trim()
      : "";

    if (!mappedColour) {
      return "background:transparent;";
    }

    return `background:${mappedColour};`;
  }

  // -------------------------
  // Refresh scheduler (:10 and :30)
  // -------------------------
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

  function clear_existing_timer() {
    if (_timer) {
      clearTimeout(_timer);
      _timer = null;
    }
  }

  function start_aligned_refresh() {
    if (_auto_refresh_started) {
      return;
    }

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

  // -------------------------
  // Chart.js loader
  // -------------------------
  function ensure_chartjs() {
    if (window.Chart) {
      return Promise.resolve();
    }

    if (window._isd_chartjs_promise) {
      return window._isd_chartjs_promise;
    }

    window._isd_chartjs_promise = new Promise((resolve, reject) => {
      const existing = document.querySelector('script[data-isd-chartjs="1"]');

      if (existing) {
        existing.addEventListener("load", () => resolve());
        existing.addEventListener("error", () => reject(new Error("Chart.js failed to load")));
        return;
      }

      const script = document.createElement("script");
      script.src = "https://cdn.jsdelivr.net/npm/chart.js";
      script.dataset.isdChartjs = "1";
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Chart.js failed to load"));
      document.head.appendChild(script);
    });

    return window._isd_chartjs_promise;
  }

  function destroy_charts() {
    _charts.forEach((chart) => {
      try {
        chart.destroy();
      } catch (e) {
        // ignore stale chart instances
      }
    });

    _charts = [];
  }

  function render_charts(chartConfigs) {
    if (!window.Chart) {
      return;
    }

    destroy_charts();

    $dash.find("canvas[data-chart-index]").each(function () {
      const canvas = this;
      const idx = parseInt(canvas.dataset.chartIndex, 10);
      const config = chartConfigs[idx];

      if (!config) {
        return;
      }

      try {
        const chart = new Chart(canvas.getContext("2d"), config);
        _charts.push(chart);

        setTimeout(() => chart.resize(), 50);
        setTimeout(() => chart.resize(), 150);
      } catch (e) {
        console.error("Could not render site volume chart", e);
      }
    });
  }

  // -------------------------
  // Formatting helpers
  // -------------------------
  function escape_html(value) {
    return frappe.utils.escape_html(value == null ? "" : String(value));
  }

  function normalise_int(value) {
    const parsed = parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function normalise_float(value) {
    const parsed = parseFloat(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function parse_json_array(value) {
    if (Array.isArray(value)) {
      return value;
    }

    if (value == null || value === "") {
      return [];
    }

    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  function get_current_actual_index(actualData) {
    if (!Array.isArray(actualData)) {
      return -1;
    }

    for (let i = actualData.length - 1; i >= 0; i--) {
      const value = actualData[i];

      if (value !== null && value !== undefined && value !== "") {
        const numericValue = Number(value);

        if (Number.isFinite(numericValue)) {
          return i;
        }
      }
    }

    return -1;
  }

  function get_y_axis_step(rows) {
    if (!Array.isArray(rows) || !rows.length) {
      return DEFAULT_Y_AXIS_STEP;
    }

    for (const row of rows) {
      const step = normalise_int(row.y_axis_step);

      if (step > 0) {
        return step;
      }
    }

    return DEFAULT_Y_AXIS_STEP;
  }

  function get_max_numeric_value(values) {
    if (!Array.isArray(values)) {
      return 0;
    }

    let maxValue = 0;

    values.forEach((value) => {
      if (value === null || value === undefined || value === "") {
        return;
      }

      const numericValue = Number(value);

      if (Number.isFinite(numericValue) && numericValue > maxValue) {
        maxValue = numericValue;
      }
    });

    return maxValue;
  }

  function compute_shared_y_axis_max(rows) {
    const yAxisStep = get_y_axis_step(rows);
    let maxValue = 0;

    rows.forEach((row) => {
      const targetData = parse_json_array(row.mtd_target_data);
      const actualData = parse_json_array(row.mtd_actual_data);

      maxValue = Math.max(
        maxValue,
        get_max_numeric_value(targetData),
        get_max_numeric_value(actualData),
        normalise_float(row.monthly_target_bcm)
      );
    });

    if (!maxValue || maxValue <= 0) {
      return yAxisStep;
    }

    return Math.ceil(maxValue / yAxisStep) * yAxisStep;
  }

  // -------------------------
  // Chart config
  // -------------------------
  function build_chart_config(labels, targetData, actualData, sharedYAxisMax, yAxisStep) {
    const currentActualIndex = get_current_actual_index(actualData);

    function actual_point_colour(index) {
      const actual = Number(actualData[index]);
      const target = Number(targetData[index]);

      if (!Number.isFinite(actual)) {
        return ACTUAL_BELOW_TARGET_COLOR;
      }

      if (!Number.isFinite(target)) {
        return ACTUAL_ABOVE_TARGET_COLOR;
      }

      return actual >= target
        ? ACTUAL_ABOVE_TARGET_COLOR
        : ACTUAL_BELOW_TARGET_COLOR;
    }

    function actual_segment_colour(ctx) {
      const index = ctx.p1DataIndex;

      if (index == null) {
        return ACTUAL_BELOW_TARGET_COLOR;
      }

      return actual_point_colour(index);
    }

    return {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "MTD Target",
            data: targetData,
            borderColor: TARGET_LINE_COLOR,
            backgroundColor: TARGET_LINE_COLOR,
            pointBackgroundColor: TARGET_LINE_COLOR,
            pointBorderColor: TARGET_LINE_COLOR,
            borderWidth: 2,
            tension: 0.25,
            pointRadius: TARGET_POINT_RADIUS,
            pointHoverRadius: TARGET_POINT_RADIUS + 2,
            pointBorderWidth: 1
          },
          {
            label: "MTD Actual",
            data: actualData,

            // Fallback. Segment colouring below handles the actual line colour.
            borderColor: ACTUAL_BELOW_TARGET_COLOR,

            segment: {
              borderColor: actual_segment_colour
            },

            backgroundColor: function (ctx) {
              return actual_point_colour(ctx.dataIndex);
            },

            pointBackgroundColor: function (ctx) {
              if (ctx.dataIndex === currentActualIndex) {
                return CURRENT_DATE_POINT_COLOR;
              }

              return actual_point_colour(ctx.dataIndex);
            },

            pointBorderColor: function (ctx) {
              if (ctx.dataIndex === currentActualIndex) {
                return CURRENT_DATE_POINT_COLOR;
              }

              return actual_point_colour(ctx.dataIndex);
            },

            pointRadius: function (ctx) {
              return ctx.dataIndex === currentActualIndex
                ? CURRENT_DATE_POINT_RADIUS
                : ACTUAL_POINT_RADIUS;
            },

            pointHoverRadius: function (ctx) {
              return ctx.dataIndex === currentActualIndex
                ? CURRENT_DATE_POINT_RADIUS + 2
                : ACTUAL_POINT_RADIUS + 2;
            },

            borderWidth: 2,
            tension: 0.25,
            pointBorderWidth: 1,
            spanGaps: false
          }
        ]
      },
      options: {
        animation: false,
        maintainAspectRatio: false,
        layout: {
          padding: {
            left: 32,
            right: 12,
            top: 10,
            bottom: 10
          }
        },
        plugins: {
          legend: {
            display: false
          }
        },
        scales: {
          x: {
            ticks: {
              autoSkip: true,
              font: {
                size: 11
              }
            }
          },
          y: {
            beginAtZero: true,
            max: sharedYAxisMax,
            ticks: {
              stepSize: yAxisStep,
              font: {
                size: 11
              },
              padding: 6
            }
          }
        }
      }
    };
  }

  // -------------------------
  // Rendering
  // -------------------------
  function build_site_card(row, siteColourMap, idx) {
    const site = String(row.site || "").trim();
    const prodStart = row.prod_start || "";
    const prodEnd = row.prod_end || "";
    const mtdUpto = row.mtd_upto || "";
    const headerBackground = get_header_background_style(site, siteColourMap);

    return `
      <div class="isd-dashboard-card">
        <div class="isd-dashboard-card-header" style="${headerBackground}">
          <div class="isd-dashboard-card-title">Site: ${escape_html(site)}</div>
          <div class="isd-dashboard-card-subtitle">
            Production Period: ${escape_html(prodStart)} → ${escape_html(prodEnd)}<br>
            MTD up to: ${escape_html(mtdUpto)}
          </div>
        </div>

        <div class="isd-dashboard-chart">
          <canvas data-chart-index="${idx}"></canvas>
        </div>
      </div>
    `;
  }

  function render_dashboard(rows, siteColourMap) {
    destroy_charts();

    if (!rows.length) {
      $dash.html(`<div class="text-muted">No graph data for the selected filter.</div>`);
      return;
    }

    const sorted = [...rows].sort((a, b) => {
      const aOrder = normalise_int(a.site_order);
      const bOrder = normalise_int(b.site_order);

      if (aOrder !== bOrder) {
        return aOrder - bOrder;
      }

      return String(a.site || "").localeCompare(String(b.site || ""));
    });

    const yAxisStep = get_y_axis_step(sorted);
    const sharedYAxisMax = compute_shared_y_axis_max(sorted);

    const chartConfigs = sorted.map((row) => {
      const labels = parse_json_array(row.chart_labels);
      const targetData = parse_json_array(row.mtd_target_data);
      const actualData = parse_json_array(row.mtd_actual_data);

      return build_chart_config(
        labels,
        targetData,
        actualData,
        sharedYAxisMax,
        yAxisStep
      );
    });

    $dash.html(
      sorted.map((row, idx) => build_site_card(row, siteColourMap, idx)).join("")
    );

    render_charts(chartConfigs);
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

    return Promise.all([
      ensure_chartjs(),
      run_report({ define_monthly_production: val }),
      get_site_colour_map()
    ])
      .then(([, res, siteColourMap]) => {
        const rows = extract_rows_from_response(res);

        render_dashboard(rows, siteColourMap);

        const time = new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit"
        });

        $status.text(`Last updated: ${time} (refreshes at :10 and :30)`);

        if (is_auto) {
          frappe.show_alert(
            {
              message: `Site Volume Graphs updated at ${time}`,
              indicator: "green"
            },
            5
          );
        }
      })
      .catch((e) => {
        console.error(e);
        $status.text("Error loading Site Volume Graphs.");
        $dash.html(`<div class="text-danger">Could not load graphs. Check console / server logs.</div>`);
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
    $status.text("Select a Define Monthly Production to load the graphs.");
  }

  // -------------------------
  // Cleanup
  // -------------------------
  frappe.pages[pageKey].on_page_unload = function () {
    clear_existing_timer();
    destroy_charts();
    _auto_refresh_started = false;
    _refreshing = false;
  };
}