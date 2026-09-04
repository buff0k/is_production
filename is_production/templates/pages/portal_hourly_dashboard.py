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


def _get_latest_plan_name():
    latest = frappe.get_all(
        "Monthly Production Planning",
        filters={"docstatus": ["<", 2]},
        fields=["name"],
        order_by="prod_month_end_date desc, modified desc",
        limit_page_length=1,
    )
    return latest[0].name if latest else ""


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


def _run_hourly_dashboard_report(monthly_production_planning=None):
    filters = {
        "monthly_production_planning": monthly_production_planning or "",
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
def run_portal_report(monthly_production_planning=None):
    _check_access()
    selected_plan = monthly_production_planning or _get_latest_plan_name()
    payload = _run_hourly_dashboard_report(selected_plan)

    return {
        "payload": payload,
        "site_order_map": _get_site_order_map(),
        "site_colour_map": _get_site_colour_map(),
        "default_month": _get_default_month(),
        "selected_plan": selected_plan,
    }


@frappe.whitelist()
def search_monthly_production_planning(txt=None):
    _check_access()
    filters = [["name", "like", f"%{(txt or '').strip()}%"]] if txt else []
    rows = frappe.get_all(
        "Monthly Production Planning",
        filters=filters,
        fields=["name"],
        order_by="prod_month_end_date desc, modified desc",
        limit_page_length=20,
    )
    return [row.name for row in rows]
