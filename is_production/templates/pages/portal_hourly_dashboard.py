import json
import frappe
from frappe import _


REPORT_NAME = "Hourly Dashboard"

SITE_COLOUR_METHOD = (
    "is_production.production.doctype.production_dashboard_setup."
    "production_dashboard_setup.get_site_colour_map"
)

ALLOWED_ROLES = [
    "Production Manager",
    "Production User",
    "Engineering Manager",
    "Engineering User",
    "Safety Manager",
    "Safety User",
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
    context.title = "Hourly Dashboard"

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/portal_hourly_dashboard"
        raise frappe.Redirect

    _check_access()


def _as_dict(value):
    if not value:
        return {}

    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    return {}


def _get_site_order_map(docname):
    if not docname:
        return {}

    try:
        doc = frappe.get_doc("Define Monthly Production", docname)
    except Exception:
        return {}

    site_order_map = {}

    possible_tables = [
        "sites",
        "site_table",
        "production_sites",
        "monthly_production_sites",
        "define_monthly_production_sites",
    ]

    for table_name in possible_tables:
        rows = doc.get(table_name) or []

        for idx, row in enumerate(rows, start=1):
            site = (
                row.get("site")
                or row.get("location")
                or row.get("mining_site")
                or row.get("production_site")
            )

            if site and site not in site_order_map:
                site_order_map[site] = idx

    return site_order_map


def _get_site_colour_map():
    try:
        method = frappe.get_attr(SITE_COLOUR_METHOD)
        result = method()
        return result if isinstance(result, dict) else {}
    except Exception:
        frappe.log_error(
            title="Portal Hourly Dashboard Site Colour Error",
            message=frappe.get_traceback(),
        )
        return {}


def _run_hourly_dashboard_report(define_monthly_production):
    filters = {
        "define_monthly_production": define_monthly_production,
    }

    try:
        run_report = frappe.get_attr("frappe.desk.query_report.run")

        try:
            return run_report(
                report_name=REPORT_NAME,
                filters=filters,
            )
        except TypeError:
            return run_report(
                REPORT_NAME,
                filters,
            )

    except Exception:
        frappe.log_error(
            title="Portal Hourly Dashboard Report Error",
            message=frappe.get_traceback(),
        )
        raise


@frappe.whitelist()
def run_portal_report(define_monthly_production):
    _check_access()

    if not define_monthly_production:
        frappe.throw(_("Define Monthly Production is required."))

    payload = _run_hourly_dashboard_report(define_monthly_production)

    return {
        "payload": payload,
        "site_order_map": _get_site_order_map(define_monthly_production),
        "site_colour_map": _get_site_colour_map(),
    }


@frappe.whitelist()
def search_define_monthly_production(txt=None):
    _check_access()

    txt = (txt or "").strip()

    filters = []

    if txt:
        filters.append(["name", "like", f"%{txt}%"])

    rows = frappe.get_all(
        "Define Monthly Production",
        filters=filters,
        fields=["name"],
        order_by="modified desc",
        limit_page_length=20,
    )

    return [row.name for row in rows]