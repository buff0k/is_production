frappe.query_reports["Mining Block Material Report"] = {
    tree: true,
    name_field: "tree_node",
    parent_field: "parent_node",
    initial_depth: 1,

    filters: [
        {
            fieldname: "geo_project",
            label: "Geo Project",
            fieldtype: "Link",
            options: "Geo Project"
        },
        {
            fieldname: "source_pit_layout",
            label: "Source Pit Layout",
            fieldtype: "Link",
            options: "Geo Pit Layout",
            get_query: function () {
                const geo_project = frappe.query_report.get_filter_value("geo_project");
                return geo_project ? { filters: { geo_project: geo_project } } : {};
            }
        },
        {
            fieldname: "material_stack",
            label: "Material Stack",
            fieldtype: "Link",
            options: "Geo Pit Layout Material Stack",
            get_query: function () {
                const geo_project = frappe.query_report.get_filter_value("geo_project");
                const source_pit_layout = frappe.query_report.get_filter_value("source_pit_layout");

                const filters = {};

                if (geo_project) filters.geo_project = geo_project;
                if (source_pit_layout) filters.geo_pit_layout = source_pit_layout;

                return { filters: filters };
            }
        },
        {
            fieldname: "mining_block",
            label: "Mining Block",
            fieldtype: "Link",
            options: "Mining Block",
            get_query: function () {
                const geo_project = frappe.query_report.get_filter_value("geo_project");
                const source_pit_layout = frappe.query_report.get_filter_value("source_pit_layout");

                const filters = {};

                if (geo_project) filters.geo_project = geo_project;
                if (source_pit_layout) filters.source_pit_layout = source_pit_layout;

                return { filters: filters };
            }
        },
        {
            fieldname: "material_seam",
            label: "Material / Seam",
            fieldtype: "Data"
        },
        {
            fieldname: "material_status",
            label: "Material Status",
            fieldtype: "Select",
            options: "\nMineable\nWaste\nExcluded\nReview\nNo Data"
        },
        {
            fieldname: "planning_status",
            label: "Planning Status",
            fieldtype: "Select",
            options: "\nNot Evaluated\nMineable\nNot Mineable\nReview"
        },
        {
            fieldname: "block_status",
            label: "Block Status",
            fieldtype: "Select",
            options: "\nDraft\nAvailable\nPlanned\nScheduled\nMining\nComplete\nExcluded"
        },
        {
            fieldname: "show_only_mineable",
            label: "Show Only Mineable",
            fieldtype: "Check",
            default: 0
        },
        {
            fieldname: "include_qualities",
            label: "Include Qualities / Other Values",
            fieldtype: "Check",
            default: 1
        },
        {
            fieldname: "include_source_values",
            label: "Include All Source Values",
            fieldtype: "Check",
            default: 0
        },
        {
            fieldname: "hide_zero_rows",
            label: "Hide Zero Rows",
            fieldtype: "Check",
            default: 0
        }
    ],

    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (!data) return value;

        if (column.fieldname === "tree_node") {
            const label = frappe.utils.escape_html(data.tree_label || data.tree_node || "");

            if (data.row_type === "Block") {
                return `<b>${label}</b>`;
            }

            if (data.row_type === "Material") {
                return `<span style="font-weight:600;">${label}</span>`;
            }

            if (data.row_type === "Metric") {
                return `<span style="color: var(--text-muted);">${label}</span>`;
            }

            return label;
        }

        if (column.fieldname === "material_status") {
            const color_map = {
                "Mineable": "green",
                "Review": "orange",
                "No Data": "gray",
                "Excluded": "red",
                "Waste": "red"
            };

            const color = color_map[data.material_status] || "gray";

            if (data.material_status) {
                return `<span class="indicator-pill ${color}">${value}</span>`;
            }
        }

        if (column.fieldname === "planning_status") {
            const color_map = {
                "Mineable": "green",
                "Review": "orange",
                "Not Evaluated": "gray",
                "Not Mineable": "red"
            };

            const color = color_map[data.planning_status] || "gray";

            if (data.planning_status) {
                return `<span class="indicator-pill ${color}">${value}</span>`;
            }
        }

        if (["volume", "tonnes", "metric_value"].includes(column.fieldname)) {
            const numeric_value = flt(data[column.fieldname] || 0);

            if (numeric_value > 0 && data.row_type !== "Metric") {
                return `<b>${value}</b>`;
            }
        }

        return value;
    },

    onload: function (report) {
        report.page.add_inner_button("Open Mining Blocks", function () {
            frappe.set_route("List", "Mining Block");
        }, "View");

        report.page.add_inner_button("Open Material Summaries", function () {
            frappe.set_route("List", "Mining Block Material Summary");
        }, "View");

        report.page.add_inner_button("Open Material Values", function () {
            frappe.set_route("List", "Mining Block Material Value");
        }, "View");

        report.page.add_inner_button("Open Material Stacks", function () {
            frappe.set_route("List", "Geo Pit Layout Material Stack");
        }, "View");
    }
};