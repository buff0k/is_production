import frappe
from frappe.model.document import Document


class DefineMonthlyProduction(Document):
    pass


@frappe.whitelist()
def get_plan_dates(plan_name):
    plan = frappe.get_value(
        "Monthly Production Planning",
        plan_name,
        ["prod_month_start_date", "prod_month_end_date"],
        as_dict=True
    )

    if not plan:
        return {}

    return {
        "start_date": plan.prod_month_start_date,
        "end_date": plan.prod_month_end_date
    }
