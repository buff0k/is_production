import json
import frappe
from frappe import _


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
    context.title = "Site Volume Tracking"

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/portal_site_volume_tracking"
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


def _get_active_employee_count(site):
    site = (site or "").strip()
    if not site:
        return 0

    return frappe.db.count(
        "Employee",
        filters={
            "status": "Active",
            "branch": site,
        },
    )


def _get_monthly_production_metrics(site, prod_end):
    site = (site or "").strip()
    if not site:
        return {
            "month_actual_bcm": 0,
            "month_forecated_bcm": 0,
        }

    fields = ["name", "month_actual_bcm", "month_forecated_bcm"]

    rows = []
    if prod_end:
        rows = frappe.get_all(
            "Monthly Production Planning",
            fields=fields,
            filters={
                "location": site,
                "prod_month_end_date": prod_end,
            },
            order_by="modified desc",
            limit_page_length=1,
        )

    if not rows and prod_end:
        rows = frappe.get_all(
            "Monthly Production Planning",
            fields=fields,
            filters={
                "location": site,
                "prod_month_end": prod_end,
            },
            order_by="modified desc",
            limit_page_length=1,
        )

    if not rows:
        rows = frappe.get_all(
            "Monthly Production Planning",
            fields=fields,
            filters={
                "location": site,
            },
            order_by="modified desc",
            limit_page_length=1,
        )

    row = rows[0] if rows else {}

    return {
        "month_actual_bcm": float(row.get("month_actual_bcm") or 0),
        "month_forecated_bcm": float(row.get("month_forecated_bcm") or 0),
    }


def _enrich_row(row):
    row = frappe._dict(row)

    site = (row.get("site") or "").strip()
    prod_end = row.get("prod_end")

    employee_count = _get_active_employee_count(site)
    metrics = _get_monthly_production_metrics(site, prod_end)

    month_actual_bcm = float(metrics.get("month_actual_bcm") or 0)
    month_forecated_bcm = float(metrics.get("month_forecated_bcm") or 0)

    row.employee_count = employee_count
    row.month_actual_bcm_source = month_actual_bcm
    row.month_forecated_bcm_source = month_forecated_bcm
    row.bcm_per_man = month_actual_bcm / employee_count if employee_count else 0
    row.projected_bcm_per_man = month_forecated_bcm / employee_count if employee_count else 0

    return dict(row)


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
def run_portal_report(define_monthly_production):
    _check_access()

    define_monthly_production = (define_monthly_production or "").strip()
    if not define_monthly_production:
        frappe.throw(_("Define Monthly Production is required."))

    run = frappe.get_attr("frappe.desk.query_report.run")

    payload = run(
        report_name="CEO DASHBOARD",
        filters=json.dumps({
            "define_monthly_production": define_monthly_production
        })
    )

    rows = payload.get("result") or []
    enriched_rows = [_enrich_row(row) for row in rows]

    return {
        "rows": enriched_rows,
        "site_order_map": _get_site_order_map(define_monthly_production),
    }