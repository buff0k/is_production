frappe.query_reports["Avail and Util report"] = {
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
            apply_avail_util_freeze_columns();
        }, 1000);

        setTimeout(function() {
            apply_avail_util_freeze_columns();
        }, 2500);
    },

    get_datatable_options(options) {
        return Object.assign(options, {
            // 6 because the table also has the row number column on the far left.
            // This freezes:
            // Row No | Asset Category | Shift Date | Asset Name | Shift | Location
            freezeColumns: 6
        });
    },

    after_datatable_render: function(datatable) {
        setTimeout(function() {
            apply_avail_util_freeze_columns();
        }, 300);
    },

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        setTimeout(function() {
            apply_avail_util_freeze_columns();
        }, 100);

        if (column.fieldname === "breakdown_reason" && data.breakdown_reason) {
            value = `<span style="color:#d9534f;font-weight:600;" title="${data.breakdown_reason}">
                        ${data.breakdown_reason}
                     </span>`;
        }

        if (column.fieldname === "other_delay_reason" && data.other_delay_reason) {
            value = `<span style="color:#f0ad4e;" title="${data.other_delay_reason}">
                        ${data.other_delay_reason}
                     </span>`;
        }

        return value;
    }
};

function apply_avail_util_freeze_columns() {
    if (!frappe.query_report || !frappe.query_report.datatable) {
        return;
    }

    if (frappe.query_report.report_name !== "Avail and Util report") {
        return;
    }

    const datatable = frappe.query_report.datatable;

    datatable.options.freezeColumns = 6;

    const style_id = "avail-util-freeze-columns-style";
    const old_style = document.getElementById(style_id);

    if (old_style) {
        old_style.remove();
    }

    const style = document.createElement("style");
    style.id = style_id;

    style.innerHTML = `
        /*
            Freeze first 6 datatable columns:
            col 0 = Row number
            col 1 = Asset Category
            col 2 = Shift Date
            col 3 = Asset Name
            col 4 = Shift
            col 5 = Location
        */

        .dt-cell--col-0,
        .dt-cell--col-1,
        .dt-cell--col-2,
        .dt-cell--col-3,
        .dt-cell--col-4,
        .dt-cell--col-5 {
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
        .dt-header .dt-cell--col-5,
        .dt-cell--header.dt-cell--col-0,
        .dt-cell--header.dt-cell--col-1,
        .dt-cell--header.dt-cell--col-2,
        .dt-cell--header.dt-cell--col-3,
        .dt-cell--header.dt-cell--col-4,
        .dt-cell--header.dt-cell--col-5 {
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

        .dt-cell--col-5 {
            left: 438px !important;
        }
    `;

    document.head.appendChild(style);

    console.log("Avail and Util report: freeze columns applied");
}

$(document).on("page-change", function() {
    setTimeout(function() {
        apply_avail_util_freeze_columns();
    }, 1200);
});

$(document).on("click", ".query-report button, .query-report .btn", function() {
    setTimeout(function() {
        apply_avail_util_freeze_columns();
    }, 1200);
});