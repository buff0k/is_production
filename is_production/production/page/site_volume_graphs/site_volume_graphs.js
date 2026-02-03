frappe.pages["site-volume-graphs"].on_page_load = function (wrapper) {
  const REPORT_NAME = "CEO Dashboard One Graphs";
  const STORAGE_KEY = "site_volume_graphs_monthly_production_plan";

  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Site Volume Graphs",
    single_column: true
  });

  // Render the filter in the page body (reliable on /desk/* pages)
  const $filter_row = $(`
    <div style="margin-top: 12px; margin-bottom: 8px;">
      <div class="text-muted" style="margin-bottom: 6px;">
        Select a Monthly Production Plan. The graphs report will open automatically.
      </div>
      <div class="isd-filter-control"></div>
    </div>
  `).appendTo(page.main);

  const plan_ctrl = frappe.ui.form.make_control({
    parent: $filter_row.find(".isd-filter-control"),
    df: {
      fieldtype: "Link",
      label: __("Monthly Production Plan"),
      fieldname: "monthly_production_plan",
      options: "Define Monthly Production",
      reqd: 1,
      change: () => {
        const val = plan_ctrl.get_value();
        if (!val) return;

        // remember last selection
        localStorage.setItem(STORAGE_KEY, val);

        // ✅ Open the REAL report full page with the correct filter fieldname
        frappe.set_route("query-report", REPORT_NAME, {
          monthly_production_plan: val
        });
      }
    },
    render_input: true
  });

  plan_ctrl.refresh();

  // Optional: restore last selection (does NOT auto-navigate)
  const last = localStorage.getItem(STORAGE_KEY);
  if (last) {
    plan_ctrl.set_value(last);

    // If you want it to auto-open immediately on page load, uncomment:
    // frappe.set_route("query-report", REPORT_NAME, { monthly_production_plan: last });
  }
};
