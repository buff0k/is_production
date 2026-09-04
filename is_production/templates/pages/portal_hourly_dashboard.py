import json
import frappe
from frappe import _
from frappe.utils import formatdate


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

SITE_ORDER = [
    "Klipfontein",
    "Uitgevallen",
    "Gwab",
    "Koppie",
    "Kriel Rehabilitation",
    "Bankfontein",
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


def _get_site_order_map():
    return {site: index for index, site in enumerate(SITE_ORDER)}


def _get_default_month():
    latest = frappe.get_all(
        "Monthly Production Planning",
        filters={
            "location": ["in", SITE_ORDER],
            "docstatus": ["<", 2],
        },
        fields=["prod_month_end_date"],
        order_by="prod_month_end_date desc, modified desc",
        limit_page_length=1,
    )

    if not latest or not latest[0].prod_month_end_date:
        return ""

    return formatdate(latest[0].prod_month_end_date, "MMMM yyyy")


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


def _run_hourly_dashboard_report():
    try:
        run_report = frappe.get_attr("frappe.desk.query_report.run")

        try:
            return run_report(
                report_name=REPORT_NAME,
                filters={},
            )
        except TypeError:
            return run_report(
                REPORT_NAME,
                {},
            )

    except Exception:
        frappe.log_error(
            title="Portal Hourly Dashboard Report Error",
            message=frappe.get_traceback(),
        )
        raise


@frappe.whitelist()
def run_portal_report():
    _check_access()
    payload = _run_hourly_dashboard_report()

    return {
        "payload": payload,
        "site_order_map": _get_site_order_map(),
        "site_colour_map": _get_site_colour_map(),
        "default_month": _get_default_month(),
    }
