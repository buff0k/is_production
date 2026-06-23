// Copyright (c) 2026, Isambane Mining (Pty) Ltd
// For license information, please see license.txt

frappe.query_reports["Weekly Production Dashboard"] = {
  filters: [
    {
      fieldname: "start_date",
      label: __("Start Date"),
      fieldtype: "Date",
      reqd: 1,
      default: frappe.datetime.month_start()
    },
    {
      fieldname: "end_date",
      label: __("End Date"),
      fieldtype: "Date",
      reqd: 1,
      default: frappe.datetime.get_today()
    },
    {
      fieldname: "site",
      label: __("Site"),
      fieldtype: "Link",
      options: "Location",
      reqd: 1,
      default: "Klipfontein"
    }
  ]
};