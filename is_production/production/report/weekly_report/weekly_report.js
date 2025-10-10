frappe.query_reports["Production Summary"] = {
  filters: [
    {
      fieldname: "end_date",
      label: __("Report Date"),
      fieldtype: "Date",
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
    console.log("✅ Production Summary loaded — 2x1 cm week box active.");

    // Make the manual week box interactive visually
    setTimeout(() => {
      const weekBox = document.querySelector(".week-input");
      if (weekBox) {
        weekBox.addEventListener("focus", () => (weekBox.style.backgroundColor = "#ffffcc"));
        weekBox.addEventListener("blur", () => (weekBox.style.backgroundColor = "#fff"));
      }
    }, 800);
  }
};
