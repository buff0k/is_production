// Copyright (c) 2026, Isambane Mining (Pty) Ltd
// CEO Dashboard 1

frappe.query_reports["CEO Dashboard 1"] = {
  filters: [
    {
      fieldname: "define_monthly_production",
      label: __("Define Monthly Production"),
      fieldtype: "Link",
      options: "Define Monthly Production",
      reqd: 1
    }
  ]
};