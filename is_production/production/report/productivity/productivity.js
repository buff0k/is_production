frappe.query_reports["Productivity"] = {
    "filters": [
        {
            "fieldname": "start_date",
            "label": __("Start Date"),
            "fieldtype": "Date",
            "reqd": 1
        },
        {
            "fieldname": "end_date",
            "label": __("End Date"),
            "fieldtype": "Date",
            "reqd": 1
        },
        {
            "fieldname": "site",
            "label": __("Site"),
            "fieldtype": "Link",
            "options": "Location",
            "reqd": 1
        },
        {
            "fieldname": "shift",
            "label": __("Shift"),
            "fieldtype": "Select",
            "options": "\nDay\nNight\nMorning\nAfternoon"
        },
        {
            "fieldname": "machine_type",
            "label": __("Machine Type"),
            "fieldtype": "Select",
            "options": "\nExcavator\nDozer\nADT"
        }
    ],

    // 🔴 Formatter to highlight invalid rows
    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (data && (data.working_hours <= 0 || parseFloat(data.output.replace(/,/g, "")) === 0)) {
            value = `<span style="background-color:#f8d7da; display:block; width:100%;">${value}</span>`;
        }

        return value;
    }
};

