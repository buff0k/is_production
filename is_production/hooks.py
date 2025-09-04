app_name = "is_production"
app_title = "Production"
app_publisher = "Isambane Mining (Pty) Ltd"
app_description = "Isambane Mining Frappe App for Production Records"
app_email = "eben@isambane.co.za"
app_license = "mit"
required_apps = ["frappe/erpnext", "shridarpatil/frappe_whatsapp"]
source_link = "http://github.com/buff0k/is_production"
app_logo_url = "/assets/is_production/images/is-logo.svg"
app_home = "/app/production"
add_to_apps_screen = [
    {
        "name": "is_production",
        "logo": "/assets/is_production/images/is-logo.svg",
        "title": "Production",
        "route": "/app/production",
        "has_permission": "is_production.production.utils.check_app_permission",
    }
]
fixtures = [
    {"dt": "Role", "filters": [["name", "in", ["Production Manager", "Production User", "Control Clerk", "External Surveryor"]]]},
    {"dt": "Custom DocPerm", "filters": [["role", "in", ["Production Manager", "Production User", "Control Clerk", "External Surveryor"]]]},
    {"dt": "Asset Category", "filters": [["name", "in", ["Dozer", "ADT", "Rigid", "Excavator"]]]}
]

override_whitelisted_methods = {
    # Override the PDF‐body renderer
    "frappe.utils.pdf.pdf_body_html": "is_production.utils.pdf.pdf_body_html"
}

# ------------------------------------------------------------------------
# Include external JS/CSS in Desk <head>
# ------------------------------------------------------------------------

# Load Sortable.js from CDN across all Desk pages
app_include_js = [
    "https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js",
]

# ------------------------------------------------------------------------
# Include doctype-specific JS
# ------------------------------------------------------------------------

# Load your custom form script only for Jorrie Test Nested
doctype_js = {
    "Monthly Production Planning": "production/doctype/monthly_production_planning/monthly_production_planning.js"
}

#offline code
app_include_js = [
  #  "/assets/is_production/js/offline_db.js",
    "/assets/is_production/js/hourly_production_ui.js"
]

app_include_css = [
   # "/assets/is_production/css/offline.css",
    "/assets/is_production/css/hourly_production_ui.css"
]

page_js = {
    "production-dashboard": "public/js/production_dashboard.js",
}