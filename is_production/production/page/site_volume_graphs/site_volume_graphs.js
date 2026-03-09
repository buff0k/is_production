frappe.pages["site-volume-graphs"].on_page_load = function (wrapper) {
  const REPORT_NAME = "CEO Dashboard One Graphs";
  const STORAGE_KEY = "site_volume_graphs_monthly_production_plan";

  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Site Volume Graphs",
    single_column: true
  });

  // -------------------------
  // Filter
  // -------------------------
  const plan_ctrl = page.add_field({
    fieldtype: "Link",
    label: __("Monthly Production Plan"),
    fieldname: "monthly_production_plan",
    options: "Define Monthly Production",
    reqd: 1,
    change: () => {
      const val = plan_ctrl.get_value();
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
  const $dash = $(`<div class="isd-site-volume-graphs-page"></div>`).appendTo($wrap);

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

      if (!plan_ctrl.get_value()) {
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
  // Define Monthly Production order
  // -------------------------
  function get_site_order_map(docname) {
    if (!docname) return Promise.resolve({});

    return frappe.db.get_doc("Define Monthly Production", docname)
      .then((doc) => {
        const rows = Array.isArray(doc.define) ? doc.define : [];
        const orderMap = {};

        rows.forEach((row, idx) => {
          const site = (row.site || "").trim();
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
  // Helpers
  // -------------------------
  function extract_report_html(payload) {
    if (!payload) return "";

    if (typeof payload.html === "string" && payload.html.trim()) return payload.html;
    if (typeof payload.message === "string" && payload.message.trim()) return payload.message;

    if (payload.message && typeof payload.message.html === "string" && payload.message.html.trim()) {
      return payload.message.html;
    }

    if (typeof payload.report_html === "string" && payload.report_html.trim()) return payload.report_html;

    return "";
  }

  function load_chartjs() {
    if (window.Chart) return Promise.resolve();

    if (window._isd_chartjs_loading_promise) {
      return window._isd_chartjs_loading_promise;
    }

    window._isd_chartjs_loading_promise = new Promise((resolve, reject) => {
      const existing = document.querySelector('script[data-isd-chartjs="1"]');
      if (existing) {
        existing.addEventListener("load", () => resolve(), { once: true });
        existing.addEventListener("error", () => reject(new Error("Chart.js failed to load")), { once: true });
        return;
      }

      const s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/chart.js";
      s.dataset.isdChartjs = "1";
      s.onload = () => resolve();
      s.onerror = () => reject(new Error("Chart.js failed to load"));
      document.head.appendChild(s);
    });

    return window._isd_chartjs_loading_promise;
  }

  function destroy_charts(root) {
    try {
      (root || document).querySelectorAll("canvas[data-chart]").forEach((canvas) => {
        if (canvas._isd_chart) {
          canvas._isd_chart.destroy();
          canvas._isd_chart = null;
        }
      });
    } catch (e) {
      console.error("Chart destroy failed", e);
    }
  }

  function render_all_charts(root) {
    if (!window.Chart || !root) return;

    root.querySelectorAll("canvas[data-chart]").forEach((canvas) => {
      if (canvas._isd_chart) {
        try {
          canvas._isd_chart.resize();
          setTimeout(() => canvas._isd_chart && canvas._isd_chart.resize(), 80);
        } catch (e) {
          // ignore
        }
        return;
      }

      try {
        const config = JSON.parse(canvas.dataset.chart);
        const chart = new Chart(canvas.getContext("2d"), config);
        canvas._isd_chart = chart;
        canvas.dataset.rendered = "1";

        setTimeout(() => chart.resize(), 50);
        setTimeout(() => chart.resize(), 150);
      } catch (e) {
        console.error("Chart render failed", e);
      }
    });
  }

  function extract_site_name_from_card(el) {
    const bannerText = $(el).find(".isd-banner").first().text().trim();
    const match = bannerText.match(/Site:\s*(.+)/i);
    return match ? match[1].trim() : "";
  }

  function reorder_graph_cards(siteOrderMap) {
    const $grid = $dash.find(".isd-ceo-graphs .isd-grid").first();
    if (!$grid.length) return;

    const cards = $grid.children(".isd-card").get();
    if (!cards.length) return;

    cards.sort((a, b) => {
      const aSite = extract_site_name_from_card(a);
      const bSite = extract_site_name_from_card(b);

      const aHasOrder = Object.prototype.hasOwnProperty.call(siteOrderMap, aSite);
      const bHasOrder = Object.prototype.hasOwnProperty.call(siteOrderMap, bSite);

      if (aHasOrder && bHasOrder) {
        return siteOrderMap[aSite] - siteOrderMap[bSite];
      }

      if (aHasOrder) return -1;
      if (bHasOrder) return 1;

      return aSite.localeCompare(bSite);
    });

    cards.forEach((card) => $grid.append(card));
  }

  function render_dashboard(payload, siteOrderMap) {
    const html = extract_report_html(payload);

    destroy_charts($dash.get(0));

    if (html) {
      $dash.html(html);
      reorder_graph_cards(siteOrderMap);

      load_chartjs()
        .then(() => {
          render_all_charts($dash.get(0));
        })
        .catch((e) => {
          console.error(e);
          frappe.show_alert({
            message: __("Could not load chart library."),
            indicator: "red"
          }, 5);
        });

      return;
    }

    const rows = payload.result || [];
    if (!rows.length) {
      $dash.html(`<div class="text-muted">No data for the selected filter.</div>`);
      return;
    }

    $dash.html(`
      <div class="text-warning">
        Report returned data, but no HTML block was found in the response.
      </div>
    `);
  }

  // -------------------------
  // Main loader
  // -------------------------
  function load_and_render(is_auto) {
    const val = plan_ctrl.get_value();
    if (!val) return Promise.resolve();

    $status.text(is_auto ? "Refreshing…" : "Loading…");

    return Promise.all([
      run_report({ monthly_production_plan: val }),
      get_site_order_map(val)
    ])
      .then(([res, siteOrderMap]) => {
        const payload = res.message || {};
        render_dashboard(payload, siteOrderMap);

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
        $status.text("Error loading graph data.");
        $dash.html(`<div class="text-danger">Could not load data. Check console / server logs.</div>`);
      });
  }

  // -------------------------
  // Restore last selection
  // -------------------------
  const last = localStorage.getItem(STORAGE_KEY);
  if (last) {
    plan_ctrl.set_value(last);
    setTimeout(() => {
      if (plan_ctrl.get_value()) {
        load_and_render(false);
        start_aligned_refresh();
      }
    }, 0);
  } else {
    $status.text("Select a Monthly Production Plan to load the graphs.");
  }

  // -------------------------
  // Cleanup
  // -------------------------
  frappe.pages["site-volume-graphs"].on_page_unload = function () {
    if (_timer) clearTimeout(_timer);
    _timer = null;
    _auto_refresh_started = false;
    _refreshing = false;
    destroy_charts($dash.get(0));
  };
};