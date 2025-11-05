import frappe
from frappe.model.document import Document

class DrillPlanning(Document):
    def validate(self):
        """Automatically calculate rates and set start/end dates from linked Monthly Production Plan"""
        if self.monthly_production_plan and self.monthly_target:
            plan = frappe.get_doc('Monthly Production Planning', self.monthly_production_plan)

            # Fetch required fields
            total_month_prod_hours = plan.get('total_month_prod_hours') or 0
            num_prod_days = plan.get('num_prod_days') or 0

            # Calculate Hourly Required Rate
            if total_month_prod_hours > 0:
                self.hourly_required_rate = round(self.monthly_target / total_month_prod_hours, 1)
            else:
                self.hourly_required_rate = 0

            # Calculate Daily Required Rate
            if num_prod_days > 0:
                self.daily_required_rate = round(self.monthly_target / num_prod_days, 1)
            else:
                self.daily_required_rate = 0

            # Auto-populate Start and End Dates
            if not self.start_date:
                self.start_date = plan.start_date
            if not self.end_date:
                self.end_date = plan.end_date
