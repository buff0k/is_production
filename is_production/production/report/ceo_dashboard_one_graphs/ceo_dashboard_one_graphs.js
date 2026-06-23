// Copyright (c) 2026, Isambane Mining (Pty) Ltd
// For license information, please see license.txt


frappe.query_reports["CEO Dashboard One Graphs"] = {
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