frappe.query_reports["Truck and Shovel Productivity"] = {

    // Native Frappe tree configuration
    tree: true,
    treeView: true,
    name_field: "tree_key",
    parent_field: "parent_tree_key",
    initial_depth: 0,


    onload: function(report) {
        if (report.tsp_material_click_installed) {
            return;
        }

        report.tsp_material_click_installed = true;

        $(document).off(
            "click.tsp_combined_adt_detail",
            ".tsp-combined-adt-detail"
        );

        $(document).on(
            "click.tsp_combined_adt_detail",
            ".tsp-combined-adt-detail",
            function(event) {
                event.preventDefault();
                event.stopPropagation();

                const groupKey =
                    $(this).attr(
                        "data-group-key"
                    ) || "";

                frappe.query_reports[
                    "Truck and Shovel Productivity"
                ].show_combined_adt_detail(
                    groupKey
                );
            }
        );


        $(document).on(
            "click.tsp_material_breakdown",
            ".tsp-adt-material-breakdown",
            function(event) {
                event.preventDefault();

                const link = $(this);

                const site =
                    link.attr("data-site") || "";

                const excavator =
                    link.attr("data-excavator") || "";

                const adt =
                    link.attr("data-adt") || "";

                frappe.query_reports[
                    "Truck and Shovel Productivity"
                ].show_adt_material_breakdown(
                    site,
                    excavator,
                    adt
                );
            }
        );
    },


    filters: [
        {
            fieldname: "from_date",
            label: __("Start Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_days(
                frappe.datetime.get_today(),
                -7
            ),
            reqd: 1
        },

        {
            fieldname: "to_date",
            label: __("End Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1
        },

        {
            fieldname: "site",
            label: __("Site"),
            fieldtype: "Link",
            options: "Location"
        },

        {
            fieldname: "excavator",
            label: __("Excavator"),
            fieldtype: "Link",
            options: "Asset",

            get_query: function () {
                return {
                    filters: {
                        asset_category: "Excavator"
                    }
                };
            }
        },

        {
            fieldname: "adt",
            label: __("ADT"),
            fieldtype: "Link",
            options: "Asset",

            get_query: function () {
                return {
                    filters: {
                        asset_category: "ADT"
                    }
                };
            }
        },

        {
            fieldname: "view",
            label: __("View"),
            fieldtype: "Select",
            options: [
                "Hourly Summary",
                "Daily Summary",
                "Machine Totals",
            "Combined ADT Totals"
        ],
            default: "Hourly Summary",
            reqd: 1
        }
    ],

    formatter: function (
        value,
        row,
        column,
        data,
        default_formatter
    ) {
        value = default_formatter(
            value,
            row,
            column,
            data
        );

        if (
            data &&
            data.is_excavator_total
        ) {
            value =
                '<div style="' +
                'font-weight:700;' +
                'background:#eef4f8;' +
                'border-top:1px solid #9aa7b2;' +
                'padding:2px 4px;' +
                '">' +
                value +
                '</div>';
        }

        


        // ====================================================
        // HOURLY SUMMARY - LAZY HOURS BUTTON
        // ====================================================

        if (
            data &&
            column &&
            column.fieldname === "adt" &&
            frappe.query_report.get_filter_value("view") === "Hourly Summary" &&
            data.is_adt_total &&
            data.hourly_date &&
            data.hourly_excavator &&
            data.hourly_adt
        ) {
            const dateValue =
                frappe.utils.escape_html(
                    String(data.hourly_date || "")
                );

            const siteValue =
                frappe.utils.escape_html(
                    String(data.hourly_site || "")
                );

            const excavatorValue =
                frappe.utils.escape_html(
                    String(data.hourly_excavator || "")
                );

            const adtValue =
                frappe.utils.escape_html(
                    String(data.hourly_adt || "")
                );

            value =
                '<span style="' +
                    'display:inline-flex;' +
                    'align-items:center;' +
                    'gap:6px;' +
                '">' +

                    value +

                    '<button ' +
                        'type="button" ' +
                        'class="' +
                            'btn btn-xs btn-default ' +
                            'tsp-hourly-detail-btn' +
                        '" ' +

                        'data-date="' +
                            dateValue +
                        '" ' +

                        'data-site="' +
                            siteValue +
                        '" ' +

                        'data-excavator="' +
                            excavatorValue +
                        '" ' +

                        'data-adt="' +
                            adtValue +
                        '" ' +

                        'style="' +
                            'height:18px;' +
                            'min-height:18px;' +
                            'padding:0 5px;' +
                            'font-size:10px;' +
                        '">' +

                        'Hours' +

                    '</button>' +

                '</span>';
        }

        return value;
    },


    show_adt_material_breakdown: function(
        site,
        excavator,
        adt
    ) {
        const from_date =
            frappe.query_report.get_filter_value(
                "from_date"
            );

        const to_date =
            frappe.query_report.get_filter_value(
                "to_date"
            );

        frappe.call({
            method:
                "is_production.production.report." +
                "truck_and_shovel_productivity." +
                "truck_and_shovel_productivity." +
                "get_adt_material_breakdown",

            args: {
                from_date: from_date,
                to_date: to_date,
                site: site,
                excavator: excavator,
                adt: adt
            },

            freeze: true,

            freeze_message:
                __("Loading material breakdown..."),

            callback: function(r) {
                const result = r.message || {};
                const rows = result.rows || [];
                const total = result.total || {};

                const formatNumber = function(
                    value,
                    decimals
                ) {
                    return Number(
                        value || 0
                    ).toLocaleString(
                        undefined,
                        {
                            minimumFractionDigits:
                                decimals,
                            maximumFractionDigits:
                                decimals
                        }
                    );
                };

                let body = "";

                rows.forEach(function(row) {
                    body +=
                        "<tr>" +
                            "<td>" +
                                frappe.utils.escape_html(
                                    row.material || ""
                                ) +
                            "</td>" +

                            '<td style="text-align:right">' +
                                formatNumber(
                                    row.loads,
                                    0
                                ) +
                            "</td>" +

                            '<td style="text-align:right">' +
                                formatNumber(
                                    row.bcms,
                                    0
                                ) +
                            "</td>" +

                            '<td style="text-align:right">' +
                                formatNumber(
                                    row.loading_hours,
                                    0
                                ) +
                            "</td>" +

                            '<td style="text-align:right">' +
                                formatNumber(
                                    row.bcm_per_hour,
                                    2
                                ) +
                            "</td>" +

                            '<td style="text-align:right">' +
                                formatNumber(
                                    row.loads_per_hour,
                                    2
                                ) +
                            "</td>" +

                            '<td style="text-align:right">' +
                                formatNumber(
                                    row.bcm_per_load,
                                    2
                                ) +
                            "</td>" +
                        "</tr>";
                });

                body +=
                    '<tr style="' +
                        'font-weight:700;' +
                        'background:#eef4f8;' +
                        'border-top:2px solid #888;' +
                    '">' +

                        "<td>TOTAL</td>" +

                        '<td style="text-align:right">' +
                            formatNumber(
                                total.loads,
                                0
                            ) +
                        "</td>" +

                        '<td style="text-align:right">' +
                            formatNumber(
                                total.bcms,
                                0
                            ) +
                        "</td>" +

                        '<td style="text-align:right">' +
                            formatNumber(
                                total.loading_hours,
                                0
                            ) +
                        "</td>" +

                        '<td style="text-align:right">' +
                            formatNumber(
                                total.bcm_per_hour,
                                2
                            ) +
                        "</td>" +

                        '<td style="text-align:right">' +
                            formatNumber(
                                total.loads_per_hour,
                                2
                            ) +
                        "</td>" +

                        '<td style="text-align:right">' +
                            formatNumber(
                                total.bcm_per_load,
                                2
                            ) +
                        "</td>" +

                    "</tr>";

                const html =
                    '<div style="overflow-x:auto;">' +

                    '<div style="' +
                        'margin-bottom:12px;' +
                        'font-weight:600;' +
                    '">' +
                        "Excavator: " +
                        frappe.utils.escape_html(
                            excavator
                        ) +
                        " &nbsp;&nbsp; ADT: " +
                        frappe.utils.escape_html(
                            adt
                        ) +
                    "</div>" +

                    '<table class="table table-bordered">' +

                        "<thead>" +
                            "<tr>" +
                                "<th>Material</th>" +
                                '<th style="text-align:right">Loads</th>' +
                                '<th style="text-align:right">BCM</th>' +
                                '<th style="text-align:right">Loading Hrs</th>' +
                                '<th style="text-align:right">BCM/Hr</th>' +
                                '<th style="text-align:right">Loads/Hr</th>' +
                                '<th style="text-align:right">Avg BCM/Load</th>' +
                            "</tr>" +
                        "</thead>" +

                        "<tbody>" +
                            body +
                        "</tbody>" +

                    "</table>" +
                    "</div>";

                const dialog =
                    new frappe.ui.Dialog({
                        title:
                            __("Material Breakdown") +
                            " - " +
                            adt,

                        size: "extra-large",

                        fields: [
                            {
                                fieldtype: "HTML",
                                fieldname:
                                    "material_breakdown"
                            }
                        ]
                    });

                dialog.fields_dict
                    .material_breakdown
                    .$wrapper
                    .html(html);

                dialog.show();
            }
        });
    },

    show_combined_adt_detail: function(
        groupKey
    ) {
        const fromDate =
            frappe.query_report.get_filter_value(
                "from_date"
            );

        const toDate =
            frappe.query_report.get_filter_value(
                "to_date"
            );

        const site =
            frappe.query_report.get_filter_value(
                "site"
            );

        frappe.call({
            method:
                "is_production.production.report." +
                "truck_and_shovel_productivity." +
                "truck_and_shovel_productivity." +
                "get_combined_adt_detail",

            args: {
                from_date: fromDate,
                to_date: toDate,
                site: site || null,
                group_key: groupKey
            },

            freeze: true,

            freeze_message:
                __("Loading ADT details..."),

            callback: function(r) {
                const result =
                    r.message || {};

                const rows =
                    result.rows || [];

                const fmt = function(
                    value,
                    decimals
                ) {
                    return Number(
                        value || 0
                    ).toLocaleString(
                        undefined,
                        {
                            minimumFractionDigits:
                                decimals,
                            maximumFractionDigits:
                                decimals
                        }
                    );
                };

                let body = "";

                rows.forEach(function(row) {
                    body +=
                        "<tr>" +

                            "<td>" +
                                frappe.utils.escape_html(
                                    row.adt || ""
                                ) +
                            "</td>" +

                            "<td>" +
                                frappe.utils.escape_html(
                                    row.adt_model || ""
                                ) +
                            "</td>" +

                            "<td>" +
                                frappe.utils.escape_html(
                                    row.excavators || ""
                                ) +
                            "</td>" +

                            "<td>" +
                                frappe.utils.escape_html(
                                    row.material || ""
                                ) +
                            "</td>" +

                            '<td style="text-align:right">' +
                                fmt(
                                    row.loads,
                                    0
                                ) +
                            "</td>" +

                            '<td style="text-align:right">' +
                                fmt(
                                    row.bcms,
                                    0
                                ) +
                            "</td>" +

                            '<td style="text-align:right">' +
                                fmt(
                                    row.loading_hours,
                                    0
                                ) +
                            "</td>" +

                            '<td style="text-align:right">' +
                                fmt(
                                    row.bcm_per_hour,
                                    2
                                ) +
                            "</td>" +

                            '<td style="text-align:right">' +
                                fmt(
                                    row.loads_per_hour,
                                    2
                                ) +
                            "</td>" +

                            '<td style="text-align:right">' +
                                fmt(
                                    row.bcm_per_load,
                                    2
                                ) +
                            "</td>" +

                        "</tr>";
                });

                const html =
                    '<div style="overflow-x:auto;">' +

                    '<table class="table table-bordered">' +

                        "<thead>" +
                            "<tr>" +
                                "<th>ADT</th>" +
                                "<th>ADT Model</th>" +
                                "<th>Excavator(s)</th>" +
                                "<th>Material</th>" +

                                '<th style="text-align:right">' +
                                    "Loads" +
                                "</th>" +

                                '<th style="text-align:right">' +
                                    "BCM" +
                                "</th>" +

                                '<th style="text-align:right">' +
                                    "Loading Hrs" +
                                "</th>" +

                                '<th style="text-align:right">' +
                                    "BCM/Hr" +
                                "</th>" +

                                '<th style="text-align:right">' +
                                    "Loads/Hr" +
                                "</th>" +

                                '<th style="text-align:right">' +
                                    "Avg BCM/Load" +
                                "</th>" +

                            "</tr>" +
                        "</thead>" +

                        "<tbody>" +
                            body +
                        "</tbody>" +

                    "</table>" +
                    "</div>";

                const dialog =
                    new frappe.ui.Dialog({
                        title:
                            result.title ||
                            __("ADT Details"),

                        size: "extra-large",

                        fields: [
                            {
                                fieldtype: "HTML",
                                fieldname:
                                    "combined_adt_detail"
                            }
                        ]
                    });

                dialog.fields_dict
                    .combined_adt_detail
                    .$wrapper
                    .html(html);

                dialog.show();
            }
        });
    },

};

// ============================================================


// ============================================================
// TRUCK AND SHOVEL PRODUCTIVITY - FULL PAGE WIDTH
// ============================================================

(function () {
    const STYLE_ID = "tsp-full-page-width-style";

    function install_tsp_full_width_style() {
        if (document.getElementById(STYLE_ID)) {
            return;
        }

        const style = document.createElement("style");

        style.id = STYLE_ID;

        style.innerHTML = `
            /* Full available page width */
            body[data-route^="query-report/Truck and Shovel Productivity"]
            .layout-main-section,

            body[data-route^="query-report/Truck%20and%20Shovel%20Productivity"]
            .layout-main-section {
                width: 100% !important;
                max-width: none !important;
            }

            body[data-route^="query-report/Truck and Shovel Productivity"]
            .report-wrapper,

            body[data-route^="query-report/Truck%20and%20Shovel%20Productivity"]
            .report-wrapper {
                width: 100% !important;
                max-width: none !important;
            }

            body[data-route^="query-report/Truck and Shovel Productivity"]
            .datatable,

            body[data-route^="query-report/Truck%20and%20Shovel%20Productivity"]
            .datatable {
                width: 100% !important;
                max-width: none !important;
            }

            body[data-route^="query-report/Truck and Shovel Productivity"]
            .dt-scrollable,

            body[data-route^="query-report/Truck%20and%20Shovel%20Productivity"]
            .dt-scrollable {
                width: 100% !important;
                max-width: none !important;
            }

            body[data-route^="query-report/Truck and Shovel Productivity"]
            .dt-header,

            body[data-route^="query-report/Truck%20and%20Shovel%20Productivity"]
            .dt-header {
                width: 100% !important;
            }

            /* Reduce unnecessary left/right page padding */
            body[data-route^="query-report/Truck and Shovel Productivity"]
            .page-body,

            body[data-route^="query-report/Truck%20and%20Shovel%20Productivity"]
            .page-body {
                padding-left: 8px !important;
                padding-right: 8px !important;
            }
        `;

        document.head.appendChild(style);
    }

    function stretch_tsp_columns() {
        if (
            !frappe.query_report ||
            !frappe.query_report.datatable
        ) {
            return;
        }

        const datatable =
            frappe.query_report.datatable;

        const wrapper =
            datatable.wrapper
                ? $(datatable.wrapper)
                : $(".report-wrapper .datatable").first();

        if (!wrapper.length) {
            return;
        }

        const availableWidth =
            wrapper.parent().innerWidth() ||
            $(window).width();

        const cells =
            wrapper
                .find(".dt-header .dt-cell")
                .filter(function () {
                    return $(this).is(":visible");
                });

        if (!cells.length) {
            return;
        }

        let totalWidth = 0;

        cells.each(function () {
            totalWidth +=
                $(this).outerWidth() || 0;
        });

        if (
            !totalWidth ||
            availableWidth <= totalWidth
        ) {
            return;
        }

        const scale =
            availableWidth / totalWidth;

        // Avoid making columns excessively wide.
        const safeScale =
            Math.min(
                scale,
                1.75
            );

        cells.each(function (index) {
            const currentWidth =
                $(this).outerWidth() || 80;

            const newWidth =
                Math.round(
                    currentWidth * safeScale
                );

            try {
                if (
                    datatable.columnmanager &&
                    typeof datatable.columnmanager
                        .setColumnWidth === "function"
                ) {
                    datatable.columnmanager
                        .setColumnWidth(
                            index,
                            newWidth
                        );
                }
            } catch (e) {
                // Safe fallback: CSS below still gives
                // the report full available width.
            }
        });
    }

    install_tsp_full_width_style();

    // Run after report/DataTable has rendered.
    setTimeout(
        stretch_tsp_columns,
        500
    );

    setTimeout(
        stretch_tsp_columns,
        1200
    );

    $(window)
        .off("resize.tsp_full_width")
        .on(
            "resize.tsp_full_width",
            function () {
                clearTimeout(
                    window.tspFullWidthResizeTimer
                );

                window.tspFullWidthResizeTimer =
                    setTimeout(
                        stretch_tsp_columns,
                        250
                    );
            }
        );
})();


// ============================================================
// TRUCK AND SHOVEL PRODUCTIVITY
// FULL PAGE WIDTH - V2
//
// Stretch the REAL DataTable columns to fill available width.
// ============================================================

(function () {
    const STYLE_ID = "tsp-full-width-v2-style";

    function tsp_is_this_report() {
        const route = frappe.get_route();

        return (
            route &&
            route[0] === "query-report" &&
            route[1] === "Truck and Shovel Productivity"
        );
    }

    function tsp_install_base_css() {
        if (document.getElementById(STYLE_ID)) {
            return;
        }

        const style = document.createElement("style");

        style.id = STYLE_ID;

        style.innerHTML = `
            body .page-container,
            body .page-body,
            body .layout-main,
            body .layout-main-section,
            body .report-wrapper {
                max-width: none !important;
            }

            body .report-wrapper {
                width: 100% !important;
            }

            body .report-wrapper .datatable {
                width: 100% !important;
                max-width: none !important;
            }

            body .report-wrapper .dt-scrollable {
                width: 100% !important;
                max-width: none !important;
            }

            body .report-wrapper .dt-header {
                width: 100% !important;
            }
        `;

        document.head.appendChild(style);
    }

    function tsp_fit_columns_to_page() {
        if (!tsp_is_this_report()) {
            return;
        }

        const $datatable = $(
            ".report-wrapper .datatable:visible"
        ).first();

        if (!$datatable.length) {
            return;
        }

        const $headerRow = $datatable
            .find(".dt-header .dt-row")
            .first();

        if (!$headerRow.length) {
            return;
        }

        const $headerCells = $headerRow
            .children(".dt-cell");

        if (!$headerCells.length) {
            return;
        }

        // Available width of the actual report area.
        const $reportArea = $datatable.parent();

        let availableWidth =
            $reportArea.innerWidth() ||
            $(".layout-main-section").innerWidth() ||
            $(window).width();

        // Small allowance for vertical scrollbar / borders.
        availableWidth =
            Math.max(
                500,
                availableWidth - 12
            );

        let currentTotal = 0;
        const widths = [];

        $headerCells.each(function () {
            const width =
                $(this).outerWidth() || 80;

            widths.push(width);
            currentTotal += width;
        });

        if (!currentTotal) {
            return;
        }

        // If report already fills the screen, don't shrink it.
        if (currentTotal >= availableWidth) {
            return;
        }

        const scale =
            availableWidth / currentTotal;

        const newWidths = widths.map(
            function (width) {
                return Math.max(
                    55,
                    Math.floor(
                        width * scale
                    )
                );
            }
        );

        // Correct rounding so total width lands exactly
        // on the available report width.
        let calculatedTotal =
            newWidths.reduce(
                function (sum, width) {
                    return sum + width;
                },
                0
            );

        if (newWidths.length) {
            newWidths[
                newWidths.length - 1
            ] += (
                availableWidth -
                calculatedTotal
            );
        }

        newWidths.forEach(
            function (width, index) {

                const nth =
                    index + 1;

                $datatable
                    .find(
                        ".dt-row > .dt-cell:nth-child(" +
                        nth +
                        ")"
                    )
                    .css({
                        width:
                            width + "px",

                        "min-width":
                            width + "px",

                        "max-width":
                            width + "px",

                        flex:
                            "0 0 " +
                            width +
                            "px"
                    });
            }
        );

        $datatable
            .find(".dt-row")
            .css({
                width:
                    availableWidth + "px",

                "min-width":
                    availableWidth + "px"
            });

        $datatable
            .find(".dt-header")
            .css({
                width:
                    availableWidth + "px"
            });
    }

    function tsp_schedule_fit() {
        [
            100,
            350,
            700,
            1200
        ].forEach(
            function (delay) {
                setTimeout(
                    tsp_fit_columns_to_page,
                    delay
                );
            }
        );
    }

    tsp_install_base_css();
    tsp_schedule_fit();

    // --------------------------------------------------------
    // REFIT WHEN REPORT DATA CHANGES
    // --------------------------------------------------------

    $(document)
        .off(
            "click.tsp_full_width_v2",
            ".page-form .btn, " +
            ".page-form input, " +
            ".page-form select"
        )
        .on(
            "click.tsp_full_width_v2",
            ".page-form .btn, " +
            ".page-form input, " +
            ".page-form select",
            function () {
                tsp_schedule_fit();
            }
        );

    // --------------------------------------------------------
    // REFIT WHEN TREE ROWS EXPAND / COLLAPSE
    // --------------------------------------------------------

    $(document)
        .off(
            "click.tsp_tree_width_v2",
            ".dt-tree-node__toggle"
        )
        .on(
            "click.tsp_tree_width_v2",
            ".dt-tree-node__toggle",
            function () {
                tsp_schedule_fit();
            }
        );

    // --------------------------------------------------------
    // REFIT WHEN WINDOW SIZE CHANGES
    // --------------------------------------------------------

    $(window)
        .off(
            "resize.tsp_full_width_v2"
        )
        .on(
            "resize.tsp_full_width_v2",
            function () {
                clearTimeout(
                    window.tspFullWidthV2Timer
                );

                window.tspFullWidthV2Timer =
                    setTimeout(
                        tsp_schedule_fit,
                        200
                    );
            }
        );

})();

// ============================================================
// TSP PERSISTENT FULL WIDTH REFRESH
// Re-apply width every time Frappe rebuilds the report.
// ============================================================

(function () {

    function tsp_refit_after_refresh() {
        [
            50,
            200,
            500,
            900,
            1400
        ].forEach(function(delay) {
            setTimeout(function() {

                if (
                    typeof tsp_fit_columns_to_page === "function"
                ) {
                    tsp_fit_columns_to_page();
                    return;
                }

                const $datatable =
                    $(".report-wrapper .datatable:visible").first();

                if (!$datatable.length) {
                    return;
                }

                const $headerRow =
                    $datatable
                        .find(".dt-header .dt-row")
                        .first();

                const $headerCells =
                    $headerRow.children(".dt-cell");

                if (!$headerCells.length) {
                    return;
                }

                const $area =
                    $datatable.parent();

                let availableWidth =
                    $area.innerWidth() ||
                    $(".layout-main-section").innerWidth() ||
                    $(window).width();

                availableWidth =
                    Math.max(
                        500,
                        availableWidth - 12
                    );

                const widths = [];
                let total = 0;

                $headerCells.each(function() {
                    const width =
                        $(this).outerWidth() || 80;

                    widths.push(width);
                    total += width;
                });

                if (!total) {
                    return;
                }

                const scale =
                    availableWidth / total;

                const newWidths =
                    widths.map(function(width) {
                        return Math.max(
                            55,
                            Math.floor(
                                width * scale
                            )
                        );
                    });

                let calculated =
                    newWidths.reduce(
                        function(sum, width) {
                            return sum + width;
                        },
                        0
                    );

                if (newWidths.length) {
                    newWidths[
                        newWidths.length - 1
                    ] += (
                        availableWidth -
                        calculated
                    );
                }

                newWidths.forEach(
                    function(width, index) {
                        const nth =
                            index + 1;

                        $datatable
                            .find(
                                ".dt-row > .dt-cell:nth-child(" +
                                nth +
                                ")"
                            )
                            .css({
                                width:
                                    width + "px",
                                "min-width":
                                    width + "px",
                                "max-width":
                                    width + "px",
                                flex:
                                    "0 0 " +
                                    width +
                                    "px"
                            });
                    }
                );

                $datatable
                    .find(".dt-row")
                    .css({
                        width:
                            availableWidth + "px",
                        "min-width":
                            availableWidth + "px"
                    });

            }, delay);
        });
    }


    const report =
        frappe.query_reports[
            "Truck and Shovel Productivity"
        ];

    if (!report) {
        return;
    }

    const oldRefresh =
        report.refresh;

    report.refresh = function(reportObj) {

        let result;

        if (
            typeof oldRefresh === "function"
        ) {
            result =
                oldRefresh.apply(
                    this,
                    arguments
                );
        }

        tsp_refit_after_refresh();

        return result;
    };


    const oldOnload =
        report.onload;

    report.onload = function(reportObj) {

        let result;

        if (
            typeof oldOnload === "function"
        ) {
            result =
                oldOnload.apply(
                    this,
                    arguments
                );
        }

        tsp_refit_after_refresh();

        return result;
    };


    // Also catch direct Frappe DataTable rebuilds.
    $(document)
        .off(
            "click.tsp_persistent_tree_fit",
            ".dt-tree-node__toggle"
        )
        .on(
            "click.tsp_persistent_tree_fit",
            ".dt-tree-node__toggle",
            function() {
                tsp_refit_after_refresh();
            }
        );

})();



// ============================================================
// TSP FULL PAGE WIDTH - FINAL
//
// Uses CSS flex sizing so Frappe refresh/rebuild does not
// return the report to the old narrow fixed widths.
// ============================================================

(function () {

    const STYLE_ID =
        "tsp-full-width-final-style";

    function install_tsp_full_width_final() {

        if (
            document.getElementById(
                STYLE_ID
            )
        ) {
            return;
        }

        const style =
            document.createElement(
                "style"
            );

        style.id =
            STYLE_ID;

        style.innerHTML = `

        /* ====================================================
           TRUCK AND SHOVEL PRODUCTIVITY
           FULL AVAILABLE PAGE WIDTH
           ==================================================== */

        .page-container .layout-main-section {
            max-width: none !important;
            width: 100% !important;
        }

        .report-wrapper {
            max-width: none !important;
            width: 100% !important;
        }

        .report-wrapper .datatable {
            width: 100% !important;
            max-width: none !important;
        }

        .report-wrapper .dt-scrollable {
            width: 100% !important;
            max-width: none !important;
        }

        .report-wrapper .dt-header {
            width: 100% !important;
            max-width: none !important;
        }


        /* ====================================================
           MAKE EVERY DATATABLE ROW USE FULL WIDTH
           ==================================================== */

        .report-wrapper .dt-row {
            display: flex !important;
            width: 100% !important;
            min-width: 100% !important;
            max-width: 100% !important;
        }


        /* ====================================================
           GENERAL CELL RULE
           ==================================================== */

        .report-wrapper .dt-row > .dt-cell {
            min-width: 0 !important;
            max-width: none !important;
            box-sizing: border-box !important;
        }


        /* Row-number / checkbox area */
        .report-wrapper
        .dt-row
        > .dt-cell:nth-child(1) {
            flex:
                0 0 34px !important;
            width:
                34px !important;
        }


        /* Date */
        .report-wrapper
        .dt-row
        > .dt-cell:nth-child(2) {
            flex:
                1.05 1 0 !important;
            width:
                auto !important;
        }


        /* Site */
        .report-wrapper
        .dt-row
        > .dt-cell:nth-child(3) {
            flex:
                1.15 1 0 !important;
            width:
                auto !important;
        }


        /* Excavator */
        .report-wrapper
        .dt-row
        > .dt-cell:nth-child(4) {
            flex:
                1.55 1 0 !important;
            width:
                auto !important;
        }


        /* Excavator Plant No */
        .report-wrapper
        .dt-row
        > .dt-cell:nth-child(5) {
            flex:
                1.10 1 0 !important;
            width:
                auto !important;
        }


        /* Excavator Model */
        .report-wrapper
        .dt-row
        > .dt-cell:nth-child(6) {
            flex:
                1.55 1 0 !important;
            width:
                auto !important;
        }


        /* ADTs Loaded */
        .report-wrapper
        .dt-row
        > .dt-cell:nth-child(7) {
            flex:
                0.85 1 0 !important;
            width:
                auto !important;
        }


        /* Materials */
        .report-wrapper
        .dt-row
        > .dt-cell:nth-child(8) {
            flex:
                1.20 1 0 !important;
            width:
                auto !important;
        }


        /* Loads */
        .report-wrapper
        .dt-row
        > .dt-cell:nth-child(9) {
            flex:
                0.75 1 0 !important;
            width:
                auto !important;
        }


        /* BCM */
        .report-wrapper
        .dt-row
        > .dt-cell:nth-child(10) {
            flex:
                0.85 1 0 !important;
            width:
                auto !important;
        }


        /* Excavator Active Hrs */
        .report-wrapper
        .dt-row
        > .dt-cell:nth-child(11) {
            flex:
                1.15 1 0 !important;
            width:
                auto !important;
        }


        /* BCM/Exc Hr */
        .report-wrapper
        .dt-row
        > .dt-cell:nth-child(12) {
            flex:
                0.95 1 0 !important;
            width:
                auto !important;
        }


        /* Loads/Exc Hr */
        .report-wrapper
        .dt-row
        > .dt-cell:nth-child(13) {
            flex:
                0.95 1 0 !important;
            width:
                auto !important;
        }


        /* Avg BCM/Load */
        .report-wrapper
        .dt-row
        > .dt-cell:nth-child(14) {
            flex:
                1.00 1 0 !important;
            width:
                auto !important;
        }


        /* Keep text readable */
        .report-wrapper .dt-cell__content {
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            white-space: nowrap !important;
        }

        `;

        document.head.appendChild(
            style
        );
    }


    install_tsp_full_width_final();


    // Frappe can rebuild the page during route/report refresh.
    // Reinstall safely if needed.
    const observer =
        new MutationObserver(
            function () {
                install_tsp_full_width_final();
            }
        );

    observer.observe(
        document.body,
        {
            childList: true,
            subtree: true
        }
    );

})();


// ============================================================
// DAILY SUMMARY - START COLLAPSED
// ============================================================

(function () {

    function collapse_daily_summary_tree() {

        if (
            !frappe.query_report ||
            frappe.query_report.get_filter_value("view")
                !== "Daily Summary"
        ) {
            return;
        }

        const datatable =
            frappe.query_report.datatable;

        if (!datatable) {
            return;
        }

        // Frappe DataTable normally respects initial_depth: 0.
        // This fallback collapses visible open nodes after render.
        $(".report-wrapper .dt-tree-node__toggle")
            .each(function () {

                const $toggle = $(this);

                const expanded =
                    $toggle.attr("aria-expanded");

                if (expanded === "true") {
                    $toggle.trigger("click");
                }
            });
    }

    [
        300,
        700,
        1200
    ].forEach(function(delay) {
        setTimeout(
            collapse_daily_summary_tree,
            delay
        );
    });

})();


// ============================================================
// DAILY SUMMARY - START COLLAPSED
// ============================================================

(function () {

    function collapse_daily_summary_tree() {

        if (
            !frappe.query_report ||
            frappe.query_report.get_filter_value("view")
                !== "Daily Summary"
        ) {
            return;
        }

        const datatable =
            frappe.query_report.datatable;

        if (!datatable) {
            return;
        }

        // Frappe DataTable normally respects initial_depth: 0.
        // This fallback collapses visible open nodes after render.
        $(".report-wrapper .dt-tree-node__toggle")
            .each(function () {

                const $toggle = $(this);

                const expanded =
                    $toggle.attr("aria-expanded");

                if (expanded === "true") {
                    $toggle.trigger("click");
                }
            });
    }

    [
        300,
        700,
        1200
    ].forEach(function(delay) {
        setTimeout(
            collapse_daily_summary_tree,
            delay
        );
    });

})();














// ============================================================
// HOURLY SUMMARY - CLEAN NAVIGATION V1
//
// Date:
//      click Date OR arrow -> open/close date
//
// Excavator:
//      click EX01 TOTAL OR arrow -> open/close excavator
//
// ADT:
//      click ADT01 TOTAL -> fetch hourly detail
//
// Only one DATE remains open.
// ============================================================

(function () {

    const NS =
        ".tsp_hourly_clean_navigation";

    // Remove delegated handlers from this clean namespace
    // before reinstalling.
    $(document).off(NS);


    // ========================================================
    // FIND DATATABLE ROW INDEX
    // ========================================================

    function getRowIndex($row) {

        if (!$row || !$row.length) {
            return null;
        }

        const className =
            $row.attr("class") || "";

        const match =
            className.match(
                /(?:^|\s)dt-row-(\d+)(?:\s|$)/
            );

        if (match) {
            return Number(match[1]);
        }

        const attr =
            $row.attr("data-row-index");

        if (
            attr !== undefined &&
            attr !== null &&
            attr !== ""
        ) {
            const parsed =
                Number(attr);

            if (Number.isInteger(parsed)) {
                return parsed;
            }
        }

        return null;
    }


    // ========================================================
    // GET REPORT DATA
    // ========================================================

    function getReportData(rowIndex) {

        const report =
            frappe.query_report;

        if (!report) {
            return null;
        }

        const data =
            report.data || [];

        return (
            Number.isInteger(rowIndex)
                ? data[rowIndex] || null
                : null
        );
    }


    // ========================================================
    // GET DATATABLE META ROW
    // ========================================================

    function getMetaRow(rowIndex) {

        const report =
            frappe.query_report;

        if (
            !report ||
            !report.datatable ||
            !report.datatable.datamanager
        ) {
            return null;
        }

        try {
            return report
                .datatable
                .datamanager
                .getRow(rowIndex);
        } catch (e) {
            return null;
        }
    }


    // ========================================================
    // CLOSE OTHER DATE PARENTS
    // ========================================================

    function closeOtherDates(
        clickedIndex
    ) {

        const report =
            frappe.query_report;

        if (
            !report ||
            !report.datatable ||
            !report.datatable.rowmanager ||
            !report.datatable.datamanager
        ) {
            return;
        }

        const rowmanager =
            report.datatable.rowmanager;

        const datamanager =
            report.datatable.datamanager;

        const rows =
            datamanager.getRows() || [];

        rows.forEach(
            function(metaRow) {

                if (
                    !metaRow ||
                    !metaRow.meta
                ) {
                    return;
                }

                const index =
                    Number(
                        metaRow.meta.rowIndex
                    );

                if (
                    !Number.isInteger(index) ||
                    index === clickedIndex
                ) {
                    return;
                }

                const reportRow =
                    getReportData(index);

                if (!reportRow) {
                    return;
                }

                if (
                    Number(
                        reportRow.indent || 0
                    ) !== 0
                ) {
                    return;
                }

                if (!reportRow.prod_date) {
                    return;
                }

                // true = currently collapsed
                if (
                    metaRow.meta.isTreeNodeClose
                    === true
                ) {
                    return;
                }

                try {
                    rowmanager.closeSingleNode(
                        index
                    );
                } catch (e) {
                    console.warn(
                        "Could not close date:",
                        index,
                        e
                    );
                }
            }
        );
    }


    // ========================================================
    // TOGGLE NATIVE TREE ROW
    // ========================================================

    function toggleTreeRow(
        rowIndex,
        closeOtherRootDates
    ) {

        const report =
            frappe.query_report;

        if (
            !report ||
            !report.datatable ||
            !report.datatable.rowmanager
        ) {
            return;
        }

        const metaRow =
            getMetaRow(rowIndex);

        if (
            !metaRow ||
            !metaRow.meta ||
            metaRow.meta.isLeaf
        ) {
            return;
        }

        const rowmanager =
            report.datatable.rowmanager;

        const isClosed =
            metaRow.meta.isTreeNodeClose
            === true;

        if (isClosed) {

            if (closeOtherRootDates) {
                closeOtherDates(
                    rowIndex
                );
            }

            rowmanager.openSingleNode(
                rowIndex
            );

        } else {

            rowmanager.closeSingleNode(
                rowIndex
            );
        }
    }


    // ========================================================
    // LOAD ONE ADT'S HOURS
    // ========================================================

    function showHourlyDetail(
        rowData
    ) {

        const prodDate =
            rowData.hourly_date || "";

        const site =
            rowData.hourly_site || "";

        const excavator =
            rowData.hourly_excavator || "";

        const adt =
            rowData.hourly_adt || "";

        if (
            !prodDate ||
            !site ||
            !excavator ||
            !adt
        ) {
            frappe.msgprint(
                __(
                    "Hourly information is missing for this ADT."
                )
            );

            return;
        }

        frappe.call({

            method:
                "is_production.production.report." +
                "truck_and_shovel_productivity." +
                "truck_and_shovel_productivity." +
                "get_hourly_adt_detail",

            args: {
                prod_date:
                    prodDate,

                site:
                    site,

                excavator:
                    excavator,

                adt:
                    adt
            },

            freeze: true,

            freeze_message:
                __("Loading hourly detail..."),

            callback: function(r) {

                const result =
                    r.message || {};

                const rows =
                    result.rows || [];

                const totals =
                    result.totals || {};

                const fmt =
                    function(
                        value,
                        decimals
                    ) {

                        return Number(
                            value || 0
                        ).toLocaleString(
                            undefined,
                            {
                                minimumFractionDigits:
                                    decimals,

                                maximumFractionDigits:
                                    decimals
                            }
                        );
                    };

                let body = "";

                rows.forEach(
                    function(row) {

                        body +=
                            "<tr>" +

                            "<td>" +
                                frappe.utils.escape_html(
                                    row.hour_slot || ""
                                ) +
                            "</td>" +

                            "<td>" +
                                frappe.utils.escape_html(
                                    row.material || ""
                                ) +
                            "</td>" +

                            '<td style="text-align:right;">' +
                                fmt(
                                    row.loads,
                                    0
                                ) +
                            "</td>" +

                            '<td style="text-align:right;">' +
                                fmt(
                                    row.bcms,
                                    0
                                ) +
                            "</td>" +

                            '<td style="text-align:right;">' +
                                fmt(
                                    row.bcm_per_hour,
                                    2
                                ) +
                            "</td>" +

                            '<td style="text-align:right;">' +
                                fmt(
                                    row.loads_per_hour,
                                    2
                                ) +
                            "</td>" +

                            '<td style="text-align:right;">' +
                                fmt(
                                    row.bcm_per_load,
                                    2
                                ) +
                            "</td>" +

                            "</tr>";
                    }
                );

                body +=
                    '<tr style="' +
                        'font-weight:700;' +
                        'background:#eef4f8;' +
                    '">' +

                    "<td>TOTAL</td>" +

                    "<td></td>" +

                    '<td style="text-align:right;">' +
                        fmt(
                            totals.loads,
                            0
                        ) +
                    "</td>" +

                    '<td style="text-align:right;">' +
                        fmt(
                            totals.bcms,
                            0
                        ) +
                    "</td>" +

                    '<td style="text-align:right;">' +
                        fmt(
                            totals.bcm_per_hour,
                            2
                        ) +
                    "</td>" +

                    '<td style="text-align:right;">' +
                        fmt(
                            totals.loads_per_hour,
                            2
                        ) +
                    "</td>" +

                    '<td style="text-align:right;">' +
                        fmt(
                            totals.bcm_per_load,
                            2
                        ) +
                    "</td>" +

                    "</tr>";

                const dialog =
                    new frappe.ui.Dialog({
                        title:
                            frappe.datetime
                                .str_to_user(
                                    prodDate
                                )
                            + " | "
                            + excavator
                            + " | "
                            + adt,

                        size:
                            "large",

                        fields: [
                            {
                                fieldname:
                                    "hourly_html",

                                fieldtype:
                                    "HTML"
                            }
                        ]
                    });

                dialog
                    .fields_dict
                    .hourly_html
                    .$wrapper
                    .html(
                        '<div style="overflow:auto;">' +

                        '<table class="' +
                            'table table-bordered ' +
                            'table-condensed' +
                        '">' +

                        "<thead>" +

                        "<tr>" +
                            "<th>Hour</th>" +
                            "<th>Material</th>" +
                            "<th>Loads</th>" +
                            "<th>BCM</th>" +
                            "<th>BCM/Hr</th>" +
                            "<th>Loads/Hr</th>" +
                            "<th>Avg BCM/Load</th>" +
                        "</tr>" +

                        "</thead>" +

                        "<tbody>" +
                            body +
                        "</tbody>" +

                        "</table>" +

                        "</div>"
                    );

                dialog.show();
            }
        });
    }


    // ========================================================
    // ONE CLICK HANDLER
    // ========================================================

    $(document).on(
        "click" + NS,
        ".report-wrapper .dt-row .dt-cell",
        function(event) {

            if (
                !frappe.query_report ||
                frappe.query_report
                    .get_filter_value(
                        "view"
                    )
                    !== "Hourly Summary"
            ) {
                return;
            }

            const $cell =
                $(this);

            const $row =
                $cell.closest(
                    ".dt-row"
                );

            const rowIndex =
                getRowIndex(
                    $row
                );

            if (
                rowIndex === null
            ) {
                return;
            }

            const rowData =
                getReportData(
                    rowIndex
                );

            if (!rowData) {
                return;
            }

            const indent =
                Number(
                    rowData.indent || 0
                );

            const $cells =
                $row.children(
                    ".dt-cell"
                );

            const cellIndex =
                $cells.index(
                    $cell
                );


            // ------------------------------------------------
            // DATE
            //
            // Allow clicking anywhere in Date cell/tree cell.
            // ------------------------------------------------

            if (
                indent === 0 &&
                rowData.prod_date &&
                (
                    cellIndex === 0 ||
                    cellIndex === 1
                )
            ) {

                event.preventDefault();
                event.stopPropagation();

                toggleTreeRow(
                    rowIndex,
                    true
                );

                return false;
            }


            // ------------------------------------------------
            // EXCAVATOR TOTAL
            //
            // Clicking Excavator column expands ADTs.
            // ------------------------------------------------

            if (
                indent === 1 &&
                rowData.is_excavator_total
            ) {

                const fieldname =
                    $cell.attr(
                        "data-fieldname"
                    );

                if (
                    fieldname === "excavator" ||
                    cellIndex === 4
                ) {

                    event.preventDefault();
                    event.stopPropagation();

                    toggleTreeRow(
                        rowIndex,
                        false
                    );

                    return false;
                }
            }


            // ------------------------------------------------
            // ADT TOTAL
            //
            // Clicking ADT itself opens hourly detail.
            // ------------------------------------------------

            if (
                indent === 2 &&
                rowData.is_adt_total
            ) {

                const fieldname =
                    $cell.attr(
                        "data-fieldname"
                    );

                if (
                    fieldname === "adt" ||
                    cellIndex === 6
                ) {

                    event.preventDefault();
                    event.stopPropagation();

                    showHourlyDetail(
                        rowData
                    );

                    return false;
                }
            }
        }
    );


    // ========================================================
    // STYLE
    // ========================================================

    if (
        !document.getElementById(
            "tsp-hourly-clean-nav-style"
        )
    ) {

        const style =
            document.createElement(
                "style"
            );

        style.id =
            "tsp-hourly-clean-nav-style";

        style.innerHTML = `

            /* Old Hours button no longer needed */
            .tsp-hourly-detail-btn {
                display:none !important;
            }

        `;

        document.head.appendChild(
            style
        );
    }

})();


// ============================================================
// TRUCK AND SHOVEL PRODUCTIVITY
// PRINT CURRENT SELECTED REPORT
// ============================================================

(function () {

    const reportSettings =
        frappe.query_reports[
            "Truck and Shovel Productivity"
        ];

    if (!reportSettings) {
        return;
    }

    const oldOnload =
        reportSettings.onload;

    reportSettings.onload =
        function(report) {

            if (
                typeof oldOnload
                === "function"
            ) {
                oldOnload.apply(
                    this,
                    arguments
                );
            }

            install_print_button(
                report
            );
        };


    function install_print_button(
        report
    ) {

        if (
            !report ||
            !report.page
        ) {
            return;
        }

        if (
            report.tsp_print_button_installed
        ) {
            return;
        }

        report.tsp_print_button_installed =
            true;

        report.page.add_inner_button(
            __("Print Report"),
            function() {
                print_current_report();
            }
        );
    }


    function esc(value) {

        return frappe.utils.escape_html(
            String(
                value === null ||
                value === undefined
                    ? ""
                    : value
            )
        );
    }


    function filter_value(
        fieldname
    ) {

        return (
            frappe.query_report
                .get_filter_value(
                    fieldname
                )
            || ""
        );
    }


    function user_date(
        value
    ) {

        if (!value) {
            return "";
        }

        try {
            return frappe.datetime
                .str_to_user(
                    value
                );
        } catch (e) {
            return value;
        }
    }


    function build_filters() {

        return `
            <div class="print-filters">

                <div>
                    <b>From:</b>
                    ${esc(
                        user_date(
                            filter_value(
                                "from_date"
                            )
                        )
                    )}
                </div>

                <div>
                    <b>To:</b>
                    ${esc(
                        user_date(
                            filter_value(
                                "to_date"
                            )
                        )
                    )}
                </div>

                <div>
                    <b>Site:</b>
                    ${esc(
                        filter_value("site")
                        || "All"
                    )}
                </div>

                <div>
                    <b>Excavator:</b>
                    ${esc(
                        filter_value(
                            "excavator"
                        )
                        || "All"
                    )}
                </div>

                <div>
                    <b>ADT:</b>
                    ${esc(
                        filter_value("adt")
                        || "All"
                    )}
                </div>

                <div>
                    <b>View:</b>
                    ${esc(
                        filter_value("view")
                    )}
                </div>

            </div>
        `;
    }



    function get_table_html() {

        const $datatable =
            $(".report-wrapper .datatable:visible")
                .first();

        if (!$datatable.length) {
            return "";
        }


        // ====================================================
        // HEADER
        // ====================================================

        const headers = [];

        const $headerRow =
            $datatable
                .find(
                    ".dt-header .dt-row"
                )
                .first();

        $headerRow
            .children(".dt-cell")
            .each(function(index) {

                // Skip DataTable row-number/tree utility column.
                if (index === 0) {
                    return;
                }

                const text =
                    $(this)
                        .find(
                            ".dt-cell__content"
                        )
                        .first()
                        .text()
                        .trim();

                headers.push(
                    text || ""
                );
            });


        // ====================================================
        // VISIBLE BODY ROWS ONLY
        // ====================================================

        const rows = [];

        $datatable
            .find(
                ".dt-scrollable .dt-row:visible"
            )
            .each(function() {

                const $row =
                    $(this);

                // Ignore header/filter rows.
                if (
                    $row.closest(
                        ".dt-header"
                    ).length
                ) {
                    return;
                }

                const cells = [];

                $row
                    .children(
                        ".dt-cell"
                    )
                    .each(
                        function(index) {

                            // Skip row-number/tree utility column.
                            if (index === 0) {
                                return;
                            }

                            const $content =
                                $(this)
                                    .find(
                                        ".dt-cell__content"
                                    )
                                    .first();

                            let value =
                                $content
                                    .text()
                                    .trim();

                            cells.push(
                                value
                            );
                        }
                    );

                if (
                    cells.length
                ) {
                    rows.push(
                        cells
                    );
                }
            });


        // ====================================================
        // BUILD CLEAN PRINT TABLE
        // ====================================================

        let html =
            '<table class="tsp-print-table">';


        html += "<thead><tr>";

        headers.forEach(
            function(header) {

                html +=
                    "<th>" +
                    esc(header) +
                    "</th>";
            }
        );

        html += "</tr></thead>";


        html += "<tbody>";

        rows.forEach(
            function(cells) {

                html += "<tr>";

                cells.forEach(
                    function(value) {

                        html +=
                            "<td>" +
                            esc(value) +
                            "</td>";
                    }
                );

                html += "</tr>";
            }
        );

        html += "</tbody>";

        html += "</table>";

        return html;
    }


    function print_current_report() {

        const tableHtml =
            get_table_html();

        if (!tableHtml) {

            frappe.msgprint(
                __(
                    "No report data is visible to print."
                )
            );

            return;
        }

        const view =
            filter_value(
                "view"
            );

        const printWindow =
            window.open(
                "",
                "_blank",
                "width=1500,height=900"
            );

        if (!printWindow) {

            frappe.msgprint(
                __(
                    "Please allow pop-ups for this site."
                )
            );

            return;
        }

        const html = `
<!DOCTYPE html>
<html>

<head>

<meta charset="utf-8">

<title>
Truck and Shovel Productivity - ${esc(view)}
</title>

<style>

@page {
    size: A3 landscape;
    margin: 10mm;
}

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    padding: 12px;
    font-family: Arial, sans-serif;
    font-size: 13px;
    color: #111;
    background: #fff;
    overflow-x: auto !important;
}

h1 {
    margin: 0 0 6px 0;
    font-size: 24px;
    line-height: 1.2;
}

.subtitle {
    margin-bottom: 12px;
    font-size: 15px;
    font-weight: 700;
}

.print-filters {
    display: grid;
    grid-template-columns:
        repeat(
            3,
            minmax(260px, 1fr)
        );
    gap: 8px;
    padding: 10px;
    margin-bottom: 12px;
    border: 1px solid #999;
    background: #f5f5f5;
    font-size: 13px;
    line-height: 1.4;
}

.generated {
    margin-bottom: 8px;
    text-align: right;
    font-size: 11px;
}

.tsp-print-table {
    width: 100%;
    min-width: 1800px;
    border-collapse: collapse;
    table-layout: auto;
    font-size: 13px;
    margin: 0;
}

.tsp-print-table th {
    background: #e6e6e6;
    font-weight: 700;
    border: 1px solid #777;
    padding: 7px 6px;
    text-align: left;
    white-space: nowrap;
    line-height: 1.25;
    font-size: 13px;
}

.tsp-print-table td {
    border: 1px solid #aaa;
    padding: 6px;
    vertical-align: middle;
    white-space: nowrap;
    line-height: 1.3;
    font-size: 13px;
}

.tsp-print-table tbody tr {
    page-break-inside: avoid;
}

.tsp-print-table th:nth-last-child(-n+6),
.tsp-print-table td:nth-last-child(-n+6) {
    text-align: right;
}

.datatable,
.dt-scrollable,
.dt-header,
.dt-body {
    width: 100% !important;
    max-width: none !important;
    height: auto !important;
    max-height: none !important;
    overflow: visible !important;
}

.dt-row {
    display: flex !important;
    width: 100% !important;
    page-break-inside: avoid;
}

.dt-cell {
    min-width: 0 !important;
    max-width: none !important;
    padding: 3px !important;
    border-right: 1px solid #ddd !important;
    border-bottom: 1px solid #ddd !important;
    white-space: normal !important;
    overflow: visible !important;
}

.dt-header .dt-cell {
    font-weight: 700 !important;
    background: #ececec !important;
    border-top: 1px solid #aaa !important;
}

.dt-cell__content {
    font-size: 9px !important;
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: clip !important;
}

button,
.btn,
.tsp-hourly-detail-btn {
    display: none !important;
}


.tsp-print-table thead {
    display: table-header-group;
}

@media screen {

    body {
        min-width: 1850px !important;
    }

    .tsp-print-table {
        min-width: 1800px !important;
    }
}


.tsp-print-table tfoot {
    display: table-footer-group;
}

.tsp-print-table tr {
    page-break-inside: avoid;
}

/* Wider text columns */
.tsp-print-table th:nth-child(1),
.tsp-print-table td:nth-child(1) {
    width: 8%;
}

.tsp-print-table th:nth-child(2),
.tsp-print-table td:nth-child(2) {
    width: 8%;
}

.tsp-print-table th:nth-child(3),
.tsp-print-table td:nth-child(3) {
    width: 12%;
}

.tsp-print-table th:nth-child(4),
.tsp-print-table td:nth-child(4) {
    width: 10%;
}

.tsp-print-table th:nth-child(5),
.tsp-print-table td:nth-child(5) {
    width: 12%;
}

.tsp-print-table th:nth-child(6),
.tsp-print-table td:nth-child(6) {
    width: 9%;
}

.tsp-print-table th:nth-child(7),
.tsp-print-table td:nth-child(7) {
    width: 10%;
}

/* Numeric columns */
.tsp-print-table th:nth-child(n+8),
.tsp-print-table td:nth-child(n+8) {
    text-align: right;
}


html,
body {
    height: auto !important;
    min-height: 0 !important;
    max-height: none !important;
    overflow: visible !important;
}

body {
    display: block !important;
}

.tsp-print-table {
    margin-bottom: 0 !important;
}

.tsp-print-table tbody {
    height: auto !important;
    min-height: 0 !important;
}

.tsp-print-table tr:last-child td {
    border-bottom: 1px solid #777;
}

.datatable,
.dt-scrollable,
.dt-body,
.dt-header {
    height: auto !important;
    min-height: 0 !important;
    max-height: none !important;
    overflow: visible !important;
}

@media print {

    body {
        font-size: 11pt !important;
    }

    .tsp-print-table {
        font-size: 9pt !important;
        min-width: 0 !important;
        width: 100% !important;
    }

    .tsp-print-table th,
    .tsp-print-table td {
        font-size: 9pt !important;
        padding: 4px !important;
    }



    html,
    body {
        height: auto !important;
        min-height: 0 !important;
        max-height: none !important;
        overflow: visible !important;
    }

    body {
        padding: 0;
        margin: 0;
    }

    .tsp-print-table {
        margin-bottom: 0 !important;
    }
}

</style>

</head>

<body>

<h1>
Truck and Shovel Productivity
</h1>

<div class="subtitle">
${esc(view)}
</div>

${build_filters()}

<div class="generated">
Generated:
${esc(
    frappe.datetime.now_datetime()
)}
</div>

${tableHtml}

<script>
window.onload = function() {

    setTimeout(
        function() {

            try {
                document.documentElement.style.height =
                    "auto";

                document.body.style.height =
                    "auto";

                document.body.style.minHeight =
                    "0";

                const contentHeight =
                    document.body.scrollHeight;

                if (
                    contentHeight &&
                    window.resizeTo
                ) {
                    window.resizeTo(
                        Math.max(
                            1200,
                            window.outerWidth
                        ),
                        Math.min(
                            contentHeight + 100,
                            screen.availHeight
                        )
                    );
                }

            } catch (e) {
                console.warn(
                    "Could not resize print window",
                    e
                );
            }

            window.print();

        },
        400
    );
};
<\/script>

</body>

</html>
        `;

        printWindow.document.open();
        printWindow.document.write(
            html
        );
        printWindow.document.close();
    }

})();


// ============================================================
// TRUCK AND SHOVEL PRODUCTIVITY
// DOWNLOAD CURRENT REPORT AS STANDALONE HTML
// ============================================================

(function () {

    const reportSettings =
        frappe.query_reports[
            "Truck and Shovel Productivity"
        ];

    if (!reportSettings) {
        return;
    }


    const oldOnloadDownload =
        reportSettings.onload;


    reportSettings.onload =
        function(report) {

            if (
                typeof oldOnloadDownload
                === "function"
            ) {
                oldOnloadDownload.apply(
                    this,
                    arguments
                );
            }

            install_download_button(
                report
            );
        };


    function install_download_button(
        report
    ) {

        if (
            !report ||
            !report.page
        ) {
            return;
        }

        if (
            report.tsp_download_button_installed
        ) {
            return;
        }

        report.tsp_download_button_installed =
            true;


        report.page.add_inner_button(
            __("Download Report"),
            function() {

                download_current_report();
            }
        );
    }


    function d_esc(value) {

        return frappe.utils.escape_html(
            String(
                value === null ||
                value === undefined
                    ? ""
                    : value
            )
        );
    }


    function d_filter_value(
        fieldname
    ) {

        return (
            frappe.query_report
                .get_filter_value(
                    fieldname
                )
            || ""
        );
    }


    function d_user_date(
        value
    ) {

        if (!value) {
            return "";
        }

        try {

            return frappe.datetime
                .str_to_user(
                    value
                );

        } catch (e) {

            return value;
        }
    }


    function d_build_filters() {

        return `
            <div class="print-filters">

                <div>
                    <b>From:</b>
                    ${d_esc(
                        d_user_date(
                            d_filter_value(
                                "from_date"
                            )
                        )
                    )}
                </div>

                <div>
                    <b>To:</b>
                    ${d_esc(
                        d_user_date(
                            d_filter_value(
                                "to_date"
                            )
                        )
                    )}
                </div>

                <div>
                    <b>Site:</b>
                    ${d_esc(
                        d_filter_value(
                            "site"
                        )
                        || "All"
                    )}
                </div>

                <div>
                    <b>Excavator:</b>
                    ${d_esc(
                        d_filter_value(
                            "excavator"
                        )
                        || "All"
                    )}
                </div>

                <div>
                    <b>ADT:</b>
                    ${d_esc(
                        d_filter_value(
                            "adt"
                        )
                        || "All"
                    )}
                </div>

                <div>
                    <b>View:</b>
                    ${d_esc(
                        d_filter_value(
                            "view"
                        )
                    )}
                </div>

            </div>
        `;
    }


    function d_get_table_html() {

        if (
            typeof get_table_html
            === "function"
        ) {

            return get_table_html();
        }


        const $datatable =
            $(".report-wrapper .datatable:visible")
                .first();

        if (!$datatable.length) {
            return "";
        }


        const headers = [];

        const $headerRow =
            $datatable
                .find(
                    ".dt-header .dt-row"
                )
                .first();


        $headerRow
            .children(".dt-cell")
            .each(function(index) {

                if (index === 0) {
                    return;
                }

                const value =
                    $(this)
                        .find(
                            ".dt-cell__content"
                        )
                        .first()
                        .text()
                        .trim();

                headers.push(
                    value || ""
                );
            });


        const rows = [];

        $datatable
            .find(
                ".dt-scrollable .dt-row:visible"
            )
            .each(function() {

                const $row =
                    $(this);

                if (
                    $row.closest(
                        ".dt-header"
                    ).length
                ) {
                    return;
                }

                const cells = [];

                $row
                    .children(
                        ".dt-cell"
                    )
                    .each(
                        function(index) {

                            if (
                                index === 0
                            ) {
                                return;
                            }

                            const value =
                                $(this)
                                    .find(
                                        ".dt-cell__content"
                                    )
                                    .first()
                                    .text()
                                    .trim();

                            cells.push(
                                value
                            );
                        }
                    );

                if (
                    cells.length
                ) {
                    rows.push(
                        cells
                    );
                }
            });


        let html =
            '<table class="tsp-print-table">';

        html +=
            "<thead><tr>";

        headers.forEach(
            function(header) {

                html +=
                    "<th>" +
                    d_esc(header) +
                    "</th>";
            }
        );

        html +=
            "</tr></thead>";

        html +=
            "<tbody>";


        rows.forEach(
            function(cells) {

                html +=
                    "<tr>";

                cells.forEach(
                    function(value) {

                        html +=
                            "<td>" +
                            d_esc(value) +
                            "</td>";
                    }
                );

                html +=
                    "</tr>";
            }
        );

        html +=
            "</tbody>";

        html +=
            "</table>";

        return html;
    }


    function download_current_report() {

        const tableHtml =
            d_get_table_html();

        if (!tableHtml) {

            frappe.msgprint(
                __(
                    "No report data is visible to download."
                )
            );

            return;
        }


        const view =
            d_filter_value(
                "view"
            );


        const fromDate =
            d_filter_value(
                "from_date"
            );


        const toDate =
            d_filter_value(
                "to_date"
            );


        const site =
            d_filter_value(
                "site"
            );


        const generated =
            frappe.datetime
                .now_datetime();


        const html = `
<!DOCTYPE html>
<html>

<head>

<meta charset="utf-8">

<title>
Truck and Shovel Productivity - ${d_esc(view)}
</title>

<style>

@page {
    size: A3 landscape;
    margin: 10mm;
}

* {
    box-sizing: border-box;
}

html,
body {
    height: auto;
    min-height: 0;
}

body {
    margin: 0;
    padding: 12px;
    font-family: Arial, sans-serif;
    font-size: 13px;
    color: #111;
    background: #fff;
    overflow-x: auto;
}

h1 {
    margin: 0 0 6px 0;
    font-size: 24px;
    line-height: 1.2;
}

.subtitle {
    margin-bottom: 12px;
    font-size: 15px;
    font-weight: 700;
}

.print-filters {
    display: grid;

    grid-template-columns:
        repeat(
            3,
            minmax(
                260px,
                1fr
            )
        );

    gap: 8px;

    padding: 10px;

    margin-bottom: 12px;

    border: 1px solid #999;

    background: #f5f5f5;

    font-size: 13px;

    line-height: 1.4;
}

.generated {
    margin-bottom: 8px;
    text-align: right;
    font-size: 11px;
}

.tsp-print-table {
    width: 100%;
    min-width: 1800px;
    border-collapse: collapse;
    table-layout: auto;
    font-size: 13px;
    margin: 0;
}

.tsp-print-table thead {
    display: table-header-group;
}

.tsp-print-table th {
    background: #e6e6e6;
    font-weight: 700;
    border: 1px solid #777;
    padding: 7px 6px;
    text-align: left;
    white-space: nowrap;
    line-height: 1.25;
    font-size: 13px;
}

.tsp-print-table td {
    border: 1px solid #aaa;
    padding: 6px;
    vertical-align: middle;
    white-space: nowrap;
    line-height: 1.3;
    font-size: 13px;
}

.tsp-print-table tr {
    page-break-inside: avoid;
}

.tsp-print-table th:nth-last-child(-n+6),
.tsp-print-table td:nth-last-child(-n+6) {
    text-align: right;
}

@media print {

    body {
        padding: 0;
    }

    .tsp-print-table {
        min-width: 0;
        width: 100%;
        font-size: 9pt;
    }

    .tsp-print-table th,
    .tsp-print-table td {
        font-size: 9pt;
        padding: 4px;
    }
}

</style>

</head>

<body>

<h1>
Truck and Shovel Productivity
</h1>

<div class="subtitle">
${d_esc(view)}
</div>

${d_build_filters()}

<div class="generated">
Generated:
${d_esc(generated)}
</div>

${tableHtml}

</body>

</html>
        `;


        const blob =
            new Blob(
                [html],
                {
                    type:
                        "text/html;charset=utf-8"
                }
            );


        const url =
            URL.createObjectURL(
                blob
            );


        const filename =
            (
                "Truck_and_Shovel_Productivity_"
                +
                String(view || "Report")
                    .replace(
                        /[^a-zA-Z0-9_-]+/g,
                        "_"
                    )
                +
                "_"
                +
                String(fromDate || "")
                +
                "_to_"
                +
                String(toDate || "")
                +
                (
                    site
                        ? "_"
                          +
                          String(site)
                              .replace(
                                  /[^a-zA-Z0-9_-]+/g,
                                  "_"
                              )
                        : ""
                )
                +
                ".html"
            );


        const link =
            document.createElement(
                "a"
            );


        link.href =
            url;

        link.download =
            filename;


        document.body.appendChild(
            link
        );


        link.click();


        document.body.removeChild(
            link
        );


        setTimeout(
            function() {

                URL.revokeObjectURL(
                    url
                );
            },
            1000
        );
    }

})();
