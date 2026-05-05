import frappe
from frappe import _
from werkzeug.utils import redirect


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    roles = frappe.get_roles(frappe.session.user)
    if "External Surveyor" not in roles and "System Manager" not in roles:
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    context.no_cache = 1
    context.title = "Survey Portal List"

    filters = {}

    if "System Manager" not in roles:
        filters["owner"] = frappe.session.user

    context.records = frappe.get_all(
        "Survey",
        filters=filters,
        fields=[
            "name",
            "last_production_shift_start_date",
            "location",
            "sub_site_description",
            "survey_datetime",
            "total_surveyed_bcm",
            "total_ts_bcm",
            "total_dozing_bcm",
            "total_surveyed_coal_tons",
            "docstatus",
            "modified",
        ],
        order_by="modified desc",
        limit_page_length=100,
    )

    return context