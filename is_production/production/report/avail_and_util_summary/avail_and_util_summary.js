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
        }
    ],

    onload: function(report) {
        report.page.set_primary_action(__("Refresh"), function() {
            report.refresh();
        });

        setTimeout(function() {
            apply_avail_util_summary_freeze_columns();
        }, 1000);

        setTimeout(function() {
            apply_avail_util_summary_freeze_columns();
        }, 2500);
    },

    get_datatable_options(options) {
        return Object.assign(options, {
            // Freeze first 5 visible columns:
            // Row No | Asset Category | Shift Date | Asset Name | Location
            freezeColumns: 5
        });
    },

    after_datatable_render: function(datatable) {
        setTimeout(function() {
            apply_avail_util_summary_freeze_columns();
        }, 300);
    },

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        setTimeout(function() {
            apply_avail_util_summary_freeze_columns();
        }, 100);

        return value;
    }
};

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
        /*
            Freeze only attached summary columns:
            col 0 = Row number
            col 1 = Asset Category
            col 2 = Shift Date
            col 3 = Asset Name
            col 4 = Location
        */

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
    `;

    document.head.appendChild(style);

    console.log("Avail and Util summary: freeze columns applied");
}

$(document).on("page-change", function() {
    setTimeout(function() {
        apply_avail_util_summary_freeze_columns();
    }, 1200);
});

$(document).on("click", ".query-report button, .query-report .btn", function() {
    setTimeout(function() {
        apply_avail_util_summary_freeze_columns();
    }, 1200);
});
