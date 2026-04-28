import frappe
from frappe import _
from frappe.utils import now_datetime
from werkzeug.utils import redirect


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    roles = frappe.get_roles(frappe.session.user)
    if "Supplier" not in roles:
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    context.no_cache = 1
    context.title = "Survey Portal"

    context.locations = frappe.get_all(
        "Location",
        fields=["name"],
        order_by="name asc",
        limit_page_length=500,
    )

    context.draft_name = frappe.form_dict.get("draft")
    context.draft = None

    if context.draft_name:
        context.draft = get_supplier_draft(context.draft_name)

    return context


def get_supplier_draft(draft_name):
    draft = frappe.get_doc("Survey Portal Draft", draft_name)

    if draft.portal_user != frappe.session.user:
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    return draft


@frappe.whitelist(allow_guest=False)
def save_survey_draft():
    validate_supplier_user()

    data = frappe.form_dict

    draft_name = data.get("draft_name")

    if draft_name:
        draft = get_supplier_draft(draft_name)
        if draft.sent:
            frappe.throw(_("This survey has already been sent to ERP."))
    else:
        draft = frappe.new_doc("Survey Portal Draft")
        draft.portal_user = frappe.session.user

    draft.last_production_shift_start_date = data.get("last_production_shift_start_date")
    draft.location = data.get("location")
    draft.sub_site_description = data.get("sub_site_description")
    draft.survey_datetime = data.get("survey_datetime") or now_datetime()
    draft.survey_report_notes = data.get("survey_report_notes")

    draft.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "ok": True,
        "draft_name": draft.name,
    }


@frappe.whitelist(allow_guest=False)
def send_survey_to_erp(draft_name):
    validate_supplier_user()

    draft = get_supplier_draft(draft_name)

    if draft.sent:
        frappe.throw(_("This survey has already been sent to ERP."))

    survey = frappe.new_doc("Survey")
    survey.last_production_shift_start_date = draft.last_production_shift_start_date
    survey.location = draft.location
    survey.sub_site_description = draft.sub_site_description
    survey.survey_datetime = draft.survey_datetime
    survey.survey_report_notes = draft.survey_report_notes

    # Child rows will be added once Surveyed Values child DocType fields are confirmed.
    # survey.append("surveyed_values", {...})

    survey.insert(ignore_permissions=True)

    draft.sent = 1
    draft.sent_datetime = now_datetime()
    draft.erp_survey_ref = survey.name
    draft.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "ok": True,
        "survey_name": survey.name,
    }


def validate_supplier_user():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    if "Supplier" not in frappe.get_roles(frappe.session.user):
        frappe.throw(_("Not permitted"), frappe.PermissionError)