import frappe
from frappe.model.document import Document


class DefineMonthlyProduction(Document):

    @frappe.whitelist()
    def get_monthly_production_plans(self, site):
        return frappe.get_all(
            "Monthly Production Planning",
            filters={
                "location": site
            },
            pluck="name"
        )

    @frappe.whitelist()
    def get_plan_dates(self, plan):
        doc = frappe.get_doc("Monthly Production Planning", plan)
        return {
            "start_date": doc.prod_month_start_date,
            "end_date": doc.prod_month_end_date
        }
