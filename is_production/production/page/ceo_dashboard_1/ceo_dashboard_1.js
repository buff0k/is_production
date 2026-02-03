frappe.pages["ceo-dashboard-1"].on_page_load = function (wrapper) {
  const REPORT_NAME = "CEO Dashboard 1";
  const STORAGE_KEY = "ceo_dash_1_define_monthly_production";

  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Site Volume Tracking",
    single_column: true
  });

  const dmp = page.add_field({
    fieldtype: "Link",
    label: __("Define Monthly Production"),
    fieldname: "define_monthly_production",
    options: "Define Monthly Production",
    reqd: 1,
    change: () => {
      const val = dmp.get_value();
      if (!val) return;

      // remember selection
      localStorage.setItem(STORAGE_KEY, val);

      // ✅ Go to the REAL report page (full screen, normal UI)
      // and pass the filter value to the report.
      frappe.set_route("query-report", REPORT_NAME, {
        define_monthly_production: val
      });
    }
  });

  // Optional helper text
  page.main.html(`
    <div class="text-muted" style="margin-top: 12px;">
      Select a Monthly Production Definition. The dashboard report will open automatically.
    </div>
  `);

  // Optional: auto-open last selected report immediately when page opens
  const last = localStorage.getItem(STORAGE_KEY);
  if (last) {
    dmp.set_value(last);

    // If you want it to auto-navigate immediately, uncomment:
    // frappe.set_route("query-report", REPORT_NAME, { define_monthly_production: last });
  }
};
