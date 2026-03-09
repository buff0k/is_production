frappe.pages["hourly-dashboard"].on_page_load = function (wrapper) {
  const REPORT_NAME = "Hourly Dashboard";
  const STORAGE_KEY = "hourly_dash_define_monthly_production";

  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Hourly Dashboard",
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
  const $dash = $(`<div class="isd-hourly-dashboard-page"></div>`).appendTo($wrap);

  // -------------------------
  // Refresh scheduler (:10 and :30)
  // Same pattern as the working CEO page / report JS
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
  // Helpers
  // -------------------------
  function escape_html(text) {
    return frappe.utils.escape_html(text == null ? "" : String(text));
  }

  function extract_report_html(payload) {
    // Be defensive because Frappe response shape can differ slightly
    if (!payload) return "";

    // common possibilities
    if (typeof payload.html === "string" && payload.html.trim()) return payload.html;
    if (typeof payload.message === "string" && payload.message.trim()) return payload.message;

    // sometimes message can itself be an object
    if (payload.message && typeof payload.message.html === "string" && payload.message.html.trim()) {
      return payload.message.html;
    }

    // some versions may expose the third return value differently
    if (typeof payload.report_html === "string" && payload.report_html.trim()) return payload.report_html;

    return "";
  }

  function render_dashboard(payload) {
    const html = extract_report_html(payload);

    if (html) {
      $dash.html(html);
      return;
    }

    const rows = payload.result || [];
    if (!rows.length) {
      $dash.html(`<div class="text-muted">No data for the selected filter.</div>`);
      return;
    }

    // Fallback only if HTML was not returned for some reason
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
    const val = dmp.get_value();
    if (!val) return Promise.resolve();

    $status.text(is_auto ? "Refreshing…" : "Loading…");

    return run_report({ define_monthly_production: val })
      .then((res) => {
        const payload = res.message || {};
        render_dashboard(payload);

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
    if (_timer) clearTimeout(_timer);
    _timer = null;
    _auto_refresh_started = false;
    _refreshing = false;
  };
};