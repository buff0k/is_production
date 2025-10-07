/* eslint-disable */

frappe.query_reports["Rental Equipment Hours"] = {
    filters: [
        {
            fieldname: "start_date",
            label: __("Start Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.add_days(frappe.datetime.get_today(), -7)
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
            reqd: 1
        },
        {
            fieldname: "shift",
            label: __("Shift"),
            fieldtype: "Select",
            options: ["", "Day", "Night"],
            reqd: 0
        }
    ],

    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname === "working_hours" && data && data.working_hours > 100) {
            value = "<span style='color:green; font-weight:bold'>" + value + "</span>";
        }

        if (data && data.asset_name === "🔢 Grand Total") {
            value = "<span style='font-weight:bold'>" + value + "</span>";
        }

        return value;
    }
};


