import frappe
from frappe import _
from werkzeug.utils import redirect


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    roles = frappe.get_roles(frappe.session.user)
    if "Supplier" not in roles:
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    context.no_cache = 1
    context.title = "Survey Portal List"

    context.records = frappe.get_all(
        "Survey Portal Draft",
        filters={
            "portal_user": frappe.session.user,
        },
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
            "sent",
            "sent_datetime",
            "erp_survey_ref",
            "modified",
        ],
        order_by="modified desc",
        limit_page_length=100,
    )

    return context