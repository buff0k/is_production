frappe.query_reports["Avail and Util summary"] = {
    filters: [
        {
            fieldname: "start_date",
            label: __("Start Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.add_days(frappe.datetime.nowdate(), -7)
        },
        {
            fieldname: "end_date",
            label: __("End Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.nowdate()
        },
        {
            fieldname: "location",
            label: __("Site"),
            fieldtype: "Link",
            options: "Location",
            reqd: 0
        },
        {
            fieldname: "machine_scope",
            label: __("Production Machines, Swing/Spare Machines AND Include Swing/Spare"),
            fieldtype: "Select",
            options: [
                "Production Machines",
                "Swing/Spare Machines",
                "Include Swing/Spare"
            ].join("\n"),
            default: "Include Swing/Spare",
            reqd: 1
        }
    ],

    onload: function(report) {
        report.page.set_primary_action(__("Refresh"), function() {
            report.refresh();
        });

        setTimeout(function() {
            apply_avail_util_summary_freeze_columns();
            colour_avail_util_summary_spare_swing_asset_names();
        }, 1000);

        setTimeout(function() {
            apply_avail_util_summary_freeze_columns();
            colour_avail_util_summary_spare_swing_asset_names();
        }, 2500);
    },

    get_datatable_options(options) {
        return Object.assign(options, {
            freezeColumns: 5
        });
    },

    after_datatable_render: function(datatable) {
        setTimeout(function() {
            apply_avail_util_summary_freeze_columns();
            colour_avail_util_summary_spare_swing_asset_names();
        }, 300);

        setTimeout(function() {
            colour_avail_util_summary_spare_swing_asset_names();
        }, 1000);
    },

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        setTimeout(function() {
            apply_avail_util_summary_freeze_columns();
            colour_avail_util_summary_spare_swing_asset_names();
        }, 100);

        return value;
    }
};

function colour_avail_util_summary_spare_swing_asset_names() {
    if (!frappe.query_report || frappe.query_report.report_name !== "Avail and Util summary") {
        return;
    }

    const data = frappe.query_report.data || [];

    if (!data.length) {
        return;
    }

    /*
        Column positions:
        0 = row number
        1 = Asset Category
        2 = Shift Date
        3 = Asset Name
        4 = Location

        We colour only column 3, not the whole row.
    */

    data.forEach(function(row, index) {
        const is_spare = Number(row.is_spare_swing_unit || 0) === 1;
        const has_asset_name = row.asset_name && String(row.asset_name).trim() !== "";

        if (!is_spare || !has_asset_name) {
            return;
        }

        const reason = row.spare_swing_reason || "Spare/Swing unit in Monthly Production Planning";

        const possible_row_indexes = [
            index,
            index + 1
        ];

        possible_row_indexes.forEach(function(row_index) {
            const selectors = [
                `.dt-cell--row-${row_index}.dt-cell--col-3`,
                `.dt-cell[data-row-index="${row_index}"][data-col-index="3"]`,
                `.dt-row-${row_index} .dt-cell--col-3`
            ];

            selectors.forEach(function(selector) {
                document.querySelectorAll(selector).forEach(function(cell) {
                    cell.classList.add("avail-util-summary-spare-swing-asset-cell");
                    cell.setAttribute("title", reason);

                    const content = cell.querySelector(".dt-cell__content");

                    if (content) {
                        content.classList.add("avail-util-summary-spare-swing-asset-content");
                        content.setAttribute("title", reason);
                    }
                });
            });
        });
    });
}

function apply_avail_util_summary_freeze_columns() {
    if (!frappe.query_report || !frappe.query_report.datatable) {
        return;
    }

    if (frappe.query_report.report_name !== "Avail and Util summary") {
        return;
    }

    const datatable = frappe.query_report.datatable;

    datatable.options.freezeColumns = 5;

    const style_id = "avail-util-summary-freeze-columns-style";
    const old_style = document.getElementById(style_id);

    if (old_style) {
        old_style.remove();
    }

    const style = document.createElement("style");
    style.id = style_id;

    style.innerHTML = `
        .dt-cell--col-0,
        .dt-cell--col-1,
        .dt-cell--col-2,
        .dt-cell--col-3,
        .dt-cell--col-4 {
            position: sticky !important;
            background: #ffffff !important;
            z-index: 30 !important;
            box-shadow: 1px 0 0 #d1d8dd !important;
        }

        .dt-header .dt-cell--col-0,
        .dt-header .dt-cell--col-1,
        .dt-header .dt-cell--col-2,
        .dt-header .dt-cell--col-3,
        .dt-header .dt-cell--col-4,
        .dt-cell--header.dt-cell--col-0,
        .dt-cell--header.dt-cell--col-1,
        .dt-cell--header.dt-cell--col-2,
        .dt-cell--header.dt-cell--col-3,
        .dt-cell--header.dt-cell--col-4 {
            position: sticky !important;
            background: #f8f8f8 !important;
            z-index: 60 !important;
            box-shadow: 1px 0 0 #d1d8dd !important;
        }

        .dt-cell--col-0 {
            left: 0px !important;
        }

        .dt-cell--col-1 {
            left: 38px !important;
        }

        .dt-cell--col-2 {
            left: 168px !important;
        }

        .dt-cell--col-3 {
            left: 258px !important;
        }

        .dt-cell--col-4 {
            left: 378px !important;
        }

        .avail-util-summary-spare-swing-asset-cell {
            background: #e6d6ff !important;
            color: #4b0082 !important;
            font-weight: 700 !important;
            border-left: 3px solid #7b2cbf !important;
        }

        .avail-util-summary-spare-swing-asset-cell .dt-cell__content,
        .avail-util-summary-spare-swing-asset-content,
        .avail-util-summary-spare-swing-asset-content a {
            background: #e6d6ff !important;
            color: #4b0082 !important;
            font-weight: 700 !important;
        }
    `;

    document.head.appendChild(style);
}

$(document).on("page-change", function() {
    setTimeout(function() {
        apply_avail_util_summary_freeze_columns();
        colour_avail_util_summary_spare_swing_asset_names();
    }, 1200);
});

$(document).on("click", ".query-report button, .query-report .btn", function() {
    setTimeout(function() {
        apply_avail_util_summary_freeze_columns();
        colour_avail_util_summary_spare_swing_asset_names();
    }, 1200);
});

$(document).on("scroll", ".dt-scrollable", function() {
    setTimeout(function() {
        colour_avail_util_summary_spare_swing_asset_names();
    }, 100);
});
