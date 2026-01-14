import frappe
from frappe.model.document import Document
from frappe.utils import getdate, date_diff

DEFAULT_SHIFT_HOURS = 8.0


class DrillPlanning(Document):
    def validate(self):
        self._validate_dates()
        self._validate_non_negative()
        self._pull_from_monthly_plan()
        self._calculate_rates()

    def _validate_dates(self):
        if not (self.start_date and self.end_date):
            return

        start = getdate(self.start_date)
        end = getdate(self.end_date)

        if end < start:
            frappe.throw("End Date cannot be before Start Date.")

    def _validate_non_negative(self):
        for fieldname, label in [
            ("monthly_target", "Monthly Target"),
            ("number_of_drills", "Number of Drills"),
        ]:
            val = self.get(fieldname)
            if val is not None and float(val) < 0:
                frappe.throw(f"{label} cannot be negative.")

    def _pull_from_monthly_plan(self):
        """
        Keep number_of_drills in sync from the linked Monthly Drill Planning doc
        (in case fetch_from did not run, or values changed).
        """
        if not self.monthly_drill_planning:
            return

        # Only set if empty / zero OR always enforce (choose one behaviour)
        doc = frappe.get_doc("Monthly Drill Planning", self.monthly_drill_planning)

        # If your Monthly Drill Planning uses a different fieldname, change here:
        plan_drills = doc.get("number_of_drills")

        if plan_drills is not None:
            # Enforce sync always:
            self.number_of_drills = plan_drills

    def _calculate_rates(self):
        if not (self.start_date and self.end_date and self.monthly_target is not None):
            return

        start = getdate(self.start_date)
        end = getdate(self.end_date)

        days = date_diff(end, start) + 1  # inclusive
        if days <= 0:
            self.daily_required_rate = 0
            self.hourly_required_rate = 0
            return

        monthly_target = float(self.monthly_target or 0)

        # DAILY/HOUR calculation (calendar days)
        daily = monthly_target / float(days)

        shift_hours = DEFAULT_SHIFT_HOURS if DEFAULT_SHIFT_HOURS > 0 else 8.0
        hourly = daily / float(shift_hours)

        # OPTIONAL: If you want rate PER DRILL, uncomment:
        # drills = float(self.number_of_drills or 0)
        # if drills > 0:
        #     daily = daily / drills
        #     hourly = hourly / drills

        self.daily_required_rate = round(daily, 1)
        self.hourly_required_rate = round(hourly, 1)
