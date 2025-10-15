frappe.query_reports["Monthly Production"] = {
  "filters": [
    {
      fieldname: "start_date",
      label: "Start Date",
      fieldtype: "Date",
      reqd: 0
    },
    {
      fieldname: "end_date",
      label: "End Date",
      fieldtype: "Date",
      reqd: 0
    },
    {
      fieldname: "site",
      label: "Site",
      fieldtype: "Link",
      options: "Location",
      reqd: 0
    },
    {
      fieldname: "monthly_production",
      label: "Monthly Production",
      fieldtype: "Link",
      options: "Monthly Production Planning",
      reqd: 1,
      get_query: () => {
        const site = frappe.query_report.get_filter_value('site');
        if (!site) {
          frappe.msgprint(__('Please select a Site first.'));
          return { filters: [] };
        }
        return {
          filters: { location: site },
          order_by: 'creation desc'
        };
      }
    },
    {
      fieldname: "shift",
      label: "Shift",
      fieldtype: "Select",
      options: ["", "Day", "Night"],
      reqd: 0
    }
  ]
};
