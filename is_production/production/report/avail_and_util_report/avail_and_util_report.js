function format_avail_util_pbm_time(hours_value) {
    const total_minutes = Math.round(
        flt(hours_value || 0) * 60
    );

    const hours = Math.floor(
        total_minutes / 60
    );

    const minutes = (
        total_minutes % 60
    );

    if (hours && minutes) {
        return `${hours}h ${minutes}m`;
    }

    if (hours) {
        return `${hours}h`;
    }

    return `${minutes}m`;
}


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
        },
        {
            fieldname: "asset_name",
            label: __("Asset"),
            fieldtype: "Link",
            options: "Asset",
            reqd: 0,
            get_query: function() {
                const location = frappe.query_report.get_filter_value("location");

                return {
                    filters: location
                        ? {
                            location: location
                        }
                        : {}
                };
            }
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
            apply_avail_util_freeze_columns();
        }, 1000);

        setTimeout(function() {
            apply_avail_util_freeze_columns();
        }, 2500);
    },

    get_datatable_options(options) {
        return Object.assign(options, {
            freezeColumns: 6
        });
    },

    after_datatable_render: function(datatable) {
        setTimeout(function() {
            apply_avail_util_freeze_columns();
        }, 300);
    },

    formatter: function(value, row, column, data, default_formatter) {
        const utilisation_fields = [
            "plant_shift_utilisation",
            "plant_shift_utilisation_above_100",
            "true_utilisation_percent"
        ];

        const raw_value = data
            ? data[column.fieldname]
            : null;

        const is_na_utilisation = (
            data
            && utilisation_fields.includes(
                column.fieldname
            )
            && (
                raw_value === null
                || raw_value === undefined
                || raw_value === ""
            )
        );

        value = default_formatter(
            value,
            row,
            column,
            data
        );

        if (is_na_utilisation) {
            value = `
                <span style="
                    display:inline-block;
                    min-width:55px;
                    text-align:center;
                    padding:3px 9px;
                    border-radius:999px;
                    background:#e5e7eb;
                    color:#4b5563;
                    font-weight:700;
                ">
                    N/A
                </span>
            `;
        }

        const pbm_time_fields = [
            "pbm_elapsed_time",
            "pbm_startup_fatigue_time",
            "pbm_sunday_time",
            "pbm_total_downtime"
        ];

        if (
            data
            && pbm_time_fields.includes(
                column.fieldname
            )
        ) {
            value = format_avail_util_pbm_time(
                raw_value
            );
        }

        setTimeout(function() {
            apply_avail_util_freeze_columns();
        }, 100);

        if (data && column.fieldname === "breakdown_reason" && data.breakdown_reason) {
            const reason = escape_avail_util_html(data.breakdown_reason);
            value = `<span style="color:#d9534f;font-weight:600;" title="${reason}">${reason}</span>`;
        }

        if (data && column.fieldname === "other_delay_reason" && data.other_delay_reason) {
            const reason = escape_avail_util_html(data.other_delay_reason);
            value = `<span style="color:#f0ad4e;" title="${reason}">${reason}</span>`;
        }

        if (data && Number(data.is_spare_swing_unit || 0) === 1) {
            const spare_reason = data.spare_swing_reason || "Spare/Swing unit in Monthly Production Planning";
            value = apply_spare_swing_purple_highlight(value, spare_reason);
        }

        return value;
    }
};

function escape_avail_util_html(value) {
    if (value === null || value === undefined) {
        return "";
    }

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function apply_spare_swing_purple_highlight(value, reason) {
    const safe_reason = escape_avail_util_html(reason || "Spare/Swing unit in Monthly Production Planning");

    return `<span class="avail-util-spare-swing-cell"
                  title="${safe_reason}"
                  style="display:block;margin:-8px -10px;padding:8px 10px;
                         background:#e6d6ff;color:#4b0082;font-weight:600;
                         min-height:100%;border-left:3px solid #7b2cbf;">
                ${value || ""}
            </span>`;
}

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

        .avail-util-spare-swing-cell {
            background: #e6d6ff !important;
            color: #4b0082 !important;
            font-weight: 600 !important;
            border-left: 3px solid #7b2cbf !important;
        }

        .dt-header .dt-cell--col-14,
        .dt-header .dt-cell--col-15,
        .dt-header .dt-cell--col-16,
        .dt-header .dt-cell--col-17,
        .dt-cell--header.dt-cell--col-14,
        .dt-cell--header.dt-cell--col-15,
        .dt-cell--header.dt-cell--col-16,
        .dt-cell--header.dt-cell--col-17 {
            background: #dcfce7 !important;
            color: #166534 !important;
            font-weight: 800 !important;
            border-bottom: 2px solid #16a34a !important;
        }
    `;

    document.head.appendChild(style);
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


const avail_util_tree_arrow_style = document.createElement('style');
avail_util_tree_arrow_style.innerHTML = `
/* Keep tree dropdown arrows visible on purple Swing/Spare rows */
.query-report[data-report-name="Avail and Util report"] .dt-cell__tree-node,
.query-report[data-report-name="Avail and Util report"] .dt-tree-node,
.query-report[data-report-name="Avail and Util report"] .dt-row-tree-node,
.query-report[data-report-name="Avail and Util report"] .tree-node,
.query-report[data-report-name="Avail and Util report"] .dt-cell__toggle,
.query-report[data-report-name="Avail and Util report"] .dt-toggle,
.query-report[data-report-name="Avail and Util report"] .octicon,
.query-report[data-report-name="Avail and Util report"] .indicator-pill {
    position: relative !important;
    z-index: 20 !important;
    color: #111111 !important;
    opacity: 1 !important;
    visibility: visible !important;
}

.query-report[data-report-name="Avail and Util report"] .avail-util-spare-swing-cell {
    position: relative !important;
    z-index: 1 !important;
}
`;
document.head.appendChild(avail_util_tree_arrow_style);
