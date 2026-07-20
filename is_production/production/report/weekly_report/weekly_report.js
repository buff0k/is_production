// Copyright (c) 2025, Isambane Mining (Pty) Ltd
// For license information, please see license.txt

frappe.query_reports["Weekly Report"] = {
  filters: [
    {
      fieldname: "end_date",
      label: __("Report Date"),
      fieldtype: "Date",
      default: frappe.datetime.get_today(),
      reqd: 1
    },
    {
      fieldname: "site",
      label: __("Site"),
      fieldtype: "Link",
      options: "Location",
      reqd: 1
    }
  ],

  onload: function (report) {
    setTimeout(() => {
      const weekBox = document.querySelector(".week-input");

      if (weekBox) {
        weekBox.addEventListener("focus", () => {
          weekBox.style.backgroundColor = "#ffffcc";
        });

        weekBox.addEventListener("blur", () => {
          weekBox.style.backgroundColor = "#fff";
        });
      }
    }, 800);
  }
};
