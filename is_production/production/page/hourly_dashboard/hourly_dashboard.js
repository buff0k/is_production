frappe.pages["hourly-dashboard"].on_page_load = function (wrapper) {
  const REPORT_NAME = "Hourly Dashboard";
  const STORAGE_KEY = "hourly_dash_define_monthly_production";

  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Hourly Dashboard",
    single_column: true
  });

  // --- Build a visible filter row in the page body (reliable everywhere) ---
  const $filter_row = $(`
    <div class="isd-filter-row" style="margin-top: 12px; margin-bottom: 8px;">
      <div class="text-muted" style="margin-bottom: 6px;">
        Select a Monthly Production Definition. The Hourly Dashboard report will open automatically.
      </div>
      <div class="isd-filter-control"></div>
    </div>
  `).appendTo(page.main);

  const dmp_ctrl = frappe.ui.form.make_control({
    parent: $filter_row.find(".isd-filter-control"),
    df: {
      fieldtype: "Link",
      label: __("Define Monthly Production"),
      fieldname: "define_monthly_production",
      options: "Define Monthly Production",
      reqd: 1,
      change: () => {
        const val = dmp_ctrl.get_value();
        if (!val) return;

        localStorage.setItem(STORAGE_KEY, val);

        // ✅ Open the REAL report full page with the filter applied
        frappe.set_route("query-report", REPORT_NAME, {
          define_monthly_production: val
        });
      }
    },
    render_input: true
  });

  dmp_ctrl.refresh();

  // Restore last selection (optional)
  const last = localStorage.getItem(STORAGE_KEY);
  if (last) {
    dmp_ctrl.set_value(last);

    // If you want auto-open on page load, uncomment:
    // frappe.set_route("query-report", REPORT_NAME, { define_monthly_production: last });
  }
};
