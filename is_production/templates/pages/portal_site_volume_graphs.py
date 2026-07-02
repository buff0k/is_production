import json

import frappe
from frappe import _


REPORT_NAME = "CEO Dashboard One Graphs"

ALLOWED_ROLES = [
    "Production Manager",
    "Production User",
    "Engineering Manager",
    "Engineering User",
    "Control Clerk",
    "All",
]


SITE_COLOUR_METHOD = (
    "is_production.production.doctype.production_dashboard_setup."
    "production_dashboard_setup.get_site_colour_map"
)


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


def _get_site_colour_map():
    try:
        method = frappe.get_attr(SITE_COLOUR_METHOD)
        result = method()
        return result if isinstance(result, dict) else {}
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Portal Site Volume Graphs: could not load site colour map",
        )
        return {}


def _run_report(selected_plan):
    run = frappe.get_attr("frappe.desk.query_report.run")

    filters = {
        "define_monthly_production": selected_plan,
    }

    try:
        return run(
            report_name=REPORT_NAME,
            filters=filters,
        )
    except TypeError:
        return run(
            report_name=REPORT_NAME,
            filters=json.dumps(filters),
        )


@frappe.whitelist()
def search_define_monthly_production(txt=""):
    _check_access()

    txt = (txt or "").strip()
    filters = {}

    if txt:
        filters = {
            "name": ["like", f"%{txt}%"],
        }

    return frappe.get_all(
        "Define Monthly Production",
        filters=filters,
        pluck="name",
        order_by="modified desc",
        limit_page_length=20,
    )


@frappe.whitelist()
def run_portal_report(define_monthly_production=None, monthly_production_plan=None):
    _check_access()

    selected_plan = (define_monthly_production or monthly_production_plan or "").strip()

    if not selected_plan:
        frappe.throw(_("Define Monthly Production is required."))

    try:
        payload = _run_report(selected_plan)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Portal Site Volume Graphs: report run failed",
        )
        raise

    return {
        "payload": payload,
        "site_order_map": _get_site_order_map(selected_plan),
        "site_colour_map": _get_site_colour_map(),
    }