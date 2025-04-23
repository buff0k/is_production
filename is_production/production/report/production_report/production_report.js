// production_report.js
// Updated configuration for the Production Report with extra filters
frappe.query_reports["Production Report"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "site",
            "label": __("Site"),
            "fieldtype": "Link",
            "options": "Location",
            "reqd": 0
        },
        {
            "fieldname": "time_column",
            "label": __("Time Column Parameter"),
            "fieldtype": "Select",
            "options": "\nMonth Only\nDays and Month\nWeek and Month\nDays Only\nWeeks Only",
            "default": "Month Only"
        },
        {
            "fieldname": "exclude_assets",
            "label": __("Exclude Assets"),
            "fieldtype": "MultiSelectList",
            "get_data": function(txt) {
                return frappe.db.get_link_options("Asset", txt);
            },
            "description": __("Select assets to exclude from diesel calculations.")
        }
    ],  // ←–– Notice this comma

    // This runs after the report is rendered (and filters are in place)
    onload: function(report) {
        const vals = report.get_values();
        if (!vals.from_date || !vals.to_date) return;

        frappe.call({
            method: "is_production.production.report.production_report.production_report.get_monthly_planning_records",
            args: {
                from_date: vals.from_date,
                to_date:   vals.to_date
            },
            callback: function(r) {
                if (r.message) {
                    // group by location, now capturing the two variances
                    const byLocation = r.message.reduce((acc, row) => {
                        const loc = row.location || "—";
                        acc[loc] = acc[loc] || [];
                        acc[loc].push({
                            shift_start_date:               row.shift_start_date,
                            cum_dozing_variance:            row.cum_dozing_variance,
                            cum_ts_variance:                row.cum_ts_variance,
                            hourly_production_reference:    row.hourly_production_reference,
                        });
                        return acc;
                    }, {});

                    console.log(
                        "↳ Monthly Production Planning records by location for",
                        vals.from_date, "to", vals.to_date,
                        "(including cum_dozing_variance & cum_ts_variance):\n",
                        byLocation
                    );
                }
            }
        });
    }
};