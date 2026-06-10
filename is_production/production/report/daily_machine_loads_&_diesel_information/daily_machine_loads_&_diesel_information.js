// Copyright (c) 2026, Isambane
// For license information, please see license.txt

frappe.query_reports["Daily Machine Loads & Diesel Information"] = {
  filters: [
    {
      fieldname: "from_date",
      label: __("From Date"),
      fieldtype: "Date",
      reqd: 1,
      default: frappe.datetime.month_start()
    },
    {
      fieldname: "to_date",
      label: __("To Date"),
      fieldtype: "Date",
      reqd: 1,
      default: frappe.datetime.month_end()
    },
    {
      fieldname: "location",
      label: __("Site"),
      fieldtype: "Link",
      options: "Location"
    },
    {
      fieldname: "shift",
      label: __("Shift"),
      fieldtype: "Select",
      options: "\nDay\nNight\nMorning\nAfternoon"
    },
    {
      fieldname: "asset",
      label: __("Machine"),
      fieldtype: "Link",
      options: "Asset",
      get_query: function () {
        const location = frappe.query_report.get_filter_value("location");

        if (!location) return {};

        return {
          filters: {
            location: location,
            docstatus: 1
          }
        };
      }
    },
    {
      fieldname: "material_type",
      label: __("Material Type"),
      fieldtype: "Select",
      options: "\nSofts\nHards\nCoal"
    }
  ]
};