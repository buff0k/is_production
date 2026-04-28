import json
import frappe
from frappe import _


ALLOWED_ROLES = [
    "Production Manager",
    "Production User",
    "Engineering Manager",
    "Engineering User",
    "Control Clerk",
    "All",
]


def _check_access():
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in first."), frappe.PermissionError)

    user_roles = frappe.get_roles(frappe.session.user)

    if not any(role in user_roles for role in ALLOWED_ROLES):
        frappe.throw(_("Not permitted."), frappe.PermissionError)


def get_context(context):
    context.no_cache = 1
    context.show_sidebar = False
    context.title = "Site Volume Graphs"

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/portal_site_volume_graphs"
        raise frappe.Redirect

    _check_access()


def _get_site_order_map(docname):
    if not docname:
        return {}

    try:
        doc = frappe.get_doc("Define Monthly Production", docname)
    except Exception:
        return {}

    rows = doc.get("define") or []
    order_map = {}

    for idx, row in enumerate(rows):
        site = (row.get("site") or "").strip()
        if site and site not in order_map:
            order_map[site] = idx

    return order_map


@frappe.whitelist()
def search_define_monthly_production(txt=""):
    _check_access()

    txt = (txt or "").strip()

    filters = {}
    if txt:
        filters = {
            "name": ["like", f"%{txt}%"]
        }

    return frappe.get_all(
        "Define Monthly Production",
        filters=filters,
        pluck="name",
        order_by="modified desc",
        limit_page_length=20,
    )


@frappe.whitelist()
def run_portal_report(monthly_production_plan):
    _check_access()

    monthly_production_plan = (monthly_production_plan or "").strip()
    if not monthly_production_plan:
        frappe.throw(_("Monthly Production Plan is required."))

    run = frappe.get_attr("frappe.desk.query_report.run")

    payload = run(
        report_name="CEO Dashboard One Graphs",
        filters=json.dumps({
            "monthly_production_plan": monthly_production_plan
        })
    )

    return {
        "payload": payload,
        "site_order_map": _get_site_order_map(monthly_production_plan),
    }