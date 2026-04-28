import frappe
from frappe import _


def get_context(context):
    context.no_cache = 1
    context.show_sidebar = True
    context.title = "Hourly Dashboard"

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/portal_hourly_dashboard"
        raise frappe.Redirect

    allowed_roles = [
        "Production Manager",
        "Production User",
        "Engineering Manager",
        "Engineering User",
        "Control Clerk",
        "All",
    ]

    user_roles = frappe.get_roles(frappe.session.user)

    if not any(role in user_roles for role in allowed_roles):
        frappe.throw(_("Not permitted."), frappe.PermissionError)