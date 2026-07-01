import inspect
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


REPORT_NAME = "Hourly Dashboard"

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
    context.title = "Hourly Dashboard"

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/portal_hourly_dashboard"
        raise frappe.Redirect

    _check_access()


def _get_site_order_map(docname):
    if not docname:
        return {}

    try:
        doc = frappe.get_doc("Define Monthly Production", docname)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Portal Hourly Dashboard: could not load site order map",
        )
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
        return method() or {}
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Portal Hourly Dashboard: could not load site colour map",
        )
        return {}


def _run_query_report(report_name, filters):
    run = frappe.get_attr("frappe.desk.query_report.run")
    signature = inspect.signature(run)

    kwargs = {
        "report_name": report_name,
        "filters": json.dumps(filters),
    }

    if "ignore_prepared_report" in signature.parameters:
        kwargs["ignore_prepared_report"] = True

    if "are_default_filters" in signature.parameters:
        kwargs["are_default_filters"] = False

    return run(**kwargs)


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
def run_portal_report(define_monthly_production, request_time=None):
    _check_access()

    define_monthly_production = (define_monthly_production or "").strip()
    if not define_monthly_production:
        frappe.throw(_("Define Monthly Production is required."))

    filters = {
        "define_monthly_production": define_monthly_production,
    }

    try:
        payload = _run_query_report(REPORT_NAME, filters)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Portal Hourly Dashboard: report run failed",
        )
        frappe.throw(
            _("Could not run {0}. Please check the report error log.").format(REPORT_NAME)
        )

    return {
        "payload": payload,
        "site_order_map": _get_site_order_map(define_monthly_production),
        "site_colour_map": _get_site_colour_map(),
        "generated_at": frappe.utils.now(),
        "request_time": request_time,
    }