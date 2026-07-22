frappe.query_reports["Monthly Production"] = {
    filters: [
        {
            fieldname: "monthly_production",
            label: __("Monthly Production"),
            fieldtype: "Link",
            options: "Monthly Production Planning"
        },
        {
            fieldname: "site",
            label: __("Site"),
            fieldtype: "Link",
            options: "Location"
        },
        {
            fieldname: "start_date",
            label: __("Start Date"),
            fieldtype: "Date"
        },
        {
            fieldname: "end_date",
            label: __("End Date"),
            fieldtype: "Date"
        },
        {
            fieldname: "shift",
            label: __("Shift"),
            fieldtype: "Select",
            options: "\nDay\nNight"
        }
    ],

    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname === "material_loaded") {
            return `
                <div style="
                    white-space: normal;
                    overflow-wrap: anywhere;
                    word-break: normal;
                    line-height: 1.35;
                    min-width: 190px;
                    max-width: 240px;
                    padding: 2px 4px;
                ">
                    ${value || ""}
                </div>
            `;
        }

        return value;
    }
};
