frappe.pages['ceo-dashboard'].on_page_load = function (wrapper) {
    // Create the page shell
    frappe.ui.make_app_page({
        parent: wrapper,
        title: 'CEO Dashboard',
        single_column: true
    });

    // Main content area
    const $main = $(wrapper).find('.layout-main-section');

    // Basic layout container
    $main.html(`
        <div id="site-grid"
             style="
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
                gap: 16px;
             ">
        </div>
    `);

    // Load data
    load_sites_from_prepared_report();
};

// --------------------------------------------------
// Call Python API
// --------------------------------------------------
function load_sites_from_prepared_report() {
    frappe.call({
        method: "is_production.production.api.ceo_dashboard.get_latest_sites_from_prepared_report",
        callback: function (r) {
            if (!r.message || !r.message.length) {
                frappe.msgprint("No Site data found in latest Prepared Report");
                return;
            }

            render_sites(r.message);
        }
    });
}

// --------------------------------------------------
// Render Site blocks
// --------------------------------------------------
function render_sites(sites) {
    const container = document.getElementById("site-grid");
    container.innerHTML = "";

    sites.forEach(site => {
        const card = document.createElement("div");

        card.style.border = "1px solid #d1d8dd";
        card.style.borderRadius = "6px";
        card.style.padding = "20px";
        card.style.background = "#ffffff";
        card.style.fontSize = "16px";
        card.style.fontWeight = "600";
        card.style.textAlign = "center";

        card.innerText = site;

        container.appendChild(card);
    });
}
