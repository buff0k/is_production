frappe.pages["esd-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "ESD Dashboard",
        single_column: true
    });

    const main = page.main.get(0);

    // -----------------------------
    // FILTER BAR
    // -----------------------------
    const start = page.add_field({
        label: "Start Date",
        fieldname: "start_date",
        fieldtype: "Date",
        default: frappe.datetime.get_today()
    });

    const end = page.add_field({
        label: "End Date",
        fieldname: "end_date",
        fieldtype: "Date",
        default: frappe.datetime.get_today()
    });

    const site = page.add_field({
        label: "Site",
        fieldname: "site",
        fieldtype: "Link",
        options: "Location"
    });

    const machine = page.add_field({
        label: "Machine",
        fieldname: "machine",
        fieldtype: "Select",
        options: ["", "EX01", "ADT01", "ADT02", "ADT03", "ADT04"].join("\n")
    });

    const shift = page.add_field({
        label: "Shift",
        fieldname: "shift",
        fieldtype: "Select",
        options: ["", "Day", "Night"].join("\n")
    });

    page.set_primary_action("Run Dashboard", function () {
        load_all_reports();
    });

    // -----------------------------
    // REPORT CONTAINERS
    // -----------------------------
    main.innerHTML = `
        <h3>ESD Production</h3>
        <div id="esd_prod"></div>

        <h3>ESD Hours</h3>
        <div id="esd_hours"></div>

        <h3>ESD Diesel</h3>
        <div id="esd_diesel"></div>
    `;

    // -----------------------------
    // COLLECT FILTERS
    // -----------------------------
    function get_filters() {
        return {
            start_date: start.get_value(),
            end_date: end.get_value(),
            site: site.get_value(),
            machine: machine.get_value(),
            shift: shift.get_value()
        };
    }

    // -----------------------------
    // LOAD ALL 3 REPORTS
    // -----------------------------
    function load_all_reports() {
        const f = get_filters();

        frappe.query_reports["ESD Production"].load_report_to_div(
            document.getElementById("esd_prod"),
            f
        );

        frappe.query_reports["ESD Hours"].load_report_to_div(
            document.getElementById("esd_hours"),
            f
        );

        frappe.query_reports["ESD DIESEL"].load_report_to_div(
            document.getElementById("esd_diesel"),
            f
        );
    }

    // Auto-load once
    setTimeout(load_all_reports, 500);
};
