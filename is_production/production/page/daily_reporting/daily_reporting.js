frappe.pages["daily-reporting"].on_page_load = function (wrapper) {
  const REPORT_NAME = "Daily Reporting";
  const STORAGE_KEY = "daily_reporting_filters";

  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Daily Reporting",
    single_column: true
  });

  // ---------- UI container ----------
  const $wrap = $(`
    <div style="margin-top: 12px;">
      <div class="text-muted" style="margin-bottom: 8px;">
        Choose Report Date and Site (required). Shift is optional. The Daily Reporting report will open automatically.
      </div>

      <div class="row" style="margin: 0;">
        <div class="col-sm-4" style="padding-left:0;">
          <div class="dr-end-date"></div>
        </div>
        <div class="col-sm-4" style="padding-left:0;">
          <div class="dr-site"></div>
        </div>
        <div class="col-sm-4" style="padding-left:0;">
          <div class="dr-shift"></div>
        </div>
      </div>

      <div style="margin-top: 10px;">
        <button class="btn btn-primary dr-run">Open Report</button>
        <button class="btn btn-default dr-clear" style="margin-left: 6px;">Clear</button>
      </div>
    </div>
  `).appendTo(page.main);

  // ---------- Controls (reliable on /desk/* pages) ----------
  const end_date_ctrl = frappe.ui.form.make_control({
    parent: $wrap.find(".dr-end-date"),
    df: {
      fieldtype: "Date",
      label: __("Report Date"),
      fieldname: "end_date",
      reqd: 1
    },
    render_input: true
  });

  const site_ctrl = frappe.ui.form.make_control({
    parent: $wrap.find(".dr-site"),
    df: {
      fieldtype: "Link",
      label: __("Site"),
      fieldname: "site",
      options: "Location",
      reqd: 1
    },
    render_input: true
  });

  const shift_ctrl = frappe.ui.form.make_control({
    parent: $wrap.find(".dr-shift"),
    df: {
      fieldtype: "Select",
      label: __("Shift"),
      fieldname: "shift",
      options: ["", "Day", "Night"],
      default: ""
    },
    render_input: true
  });

  end_date_ctrl.refresh();
  site_ctrl.refresh();
  shift_ctrl.refresh();

  // Default date = today (or keep empty if you prefer)
  if (!end_date_ctrl.get_value()) {
    end_date_ctrl.set_value(frappe.datetime.get_today());
  }

  function get_filters() {
    return {
      end_date: end_date_ctrl.get_value(),
      site: site_ctrl.get_value(),
      shift: shift_ctrl.get_value() || ""
    };
  }

  function save_filters(f) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(f));
  }

  function load_saved_filters() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    } catch (e) {
      return {};
    }
  }

  function clear_filters() {
    end_date_ctrl.set_value(frappe.datetime.get_today());
    site_ctrl.set_value("");
    shift_ctrl.set_value("");
    localStorage.removeItem(STORAGE_KEY);
  }

  function open_report_if_ready() {
    const f = get_filters();

    // Required checks
    if (!f.end_date || !f.site) return;

    save_filters(f);

    // ✅ Open the REAL report full page with filters
    frappe.set_route("query-report", REPORT_NAME, f);
  }

  // Auto-open when required fields are set/changed
  end_date_ctrl.$input && end_date_ctrl.$input.on("change", open_report_if_ready);
  site_ctrl.$input && site_ctrl.$input.on("change", open_report_if_ready);
  shift_ctrl.$input && shift_ctrl.$input.on("change", () => {
    // shift is optional; if date+site already filled, opening again is fine
    open_report_if_ready();
  });

  // Buttons
  $wrap.find(".dr-run").on("click", open_report_if_ready);
  $wrap.find(".dr-clear").on("click", clear_filters);

  // Restore last selection (nice UX)
  const saved = load_saved_filters();
  if (saved.end_date) end_date_ctrl.set_value(saved.end_date);
  if (saved.site) site_ctrl.set_value(saved.site);
  if (typeof saved.shift !== "undefined") shift_ctrl.set_value(saved.shift);

  // If saved has required fields, auto-open immediately
  if (saved.end_date && saved.site) {
    open_report_if_ready();
  }
};
