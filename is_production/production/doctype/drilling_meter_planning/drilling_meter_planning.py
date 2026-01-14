# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate, date_diff


class DrillingMeterPlanning(Document):
    def validate(self):
        self.validate_dates()
        self.set_planned_drilling_days_if_missing()
        self.set_drilling_month_label()     # ✅ Data field: "January 2026" / "Jan 2026 - Feb 2026"
        self.calculate_all()

    def validate_dates(self):
        if self.start_date and self.end_date:
            sd = getdate(self.start_date)
            ed = getdate(self.end_date)
            if ed < sd:
                frappe.throw("End Date cannot be earlier than Start Date.")

    def set_planned_drilling_days_if_missing(self):
        # Optional: auto-fill planned_drilling_days from start/end date if user left it empty/0
        if self.start_date and self.end_date and not flt(self.planned_drilling_days):
            self.planned_drilling_days = date_diff(self.end_date, self.start_date) + 1

    def set_drilling_month_label(self):
        """
        drilling_month is a Data field (text).
        Output:
          - 'January 2026' (if same month)
          - 'Jan 2026 - Feb 2026' (if different months)
        """
        if not (self.start_date and self.end_date):
            return

        sd = getdate(self.start_date)
        ed = getdate(self.end_date)

        if sd.year == ed.year and sd.month == ed.month:
            self.drilling_month = sd.strftime("%B %Y")
        else:
            self.drilling_month = f"{sd.strftime('%b %Y')} - {ed.strftime('%b %Y')}"

    def calculate_all(self):
        planned_days = flt(self.planned_drilling_days)
        worked_days = flt(self.worked_days)

        monthly_target_m = flt(self.monthly_target_meters)
        mtd_m = flt(self.mtd_drills_meter)

        total_hours = flt(self.total_monthly_drilling_hours)
        completed_hours = flt(self.monthly_drilling_hours_completed)

        # 1) remaining_days
        self.remaining_days = int(max(planned_days - worked_days, 0))

        # 2) remaining_meter
        self.remaining_meter = max(monthly_target_m - mtd_m, 0)

        # 3) monthly_remaining_drilling_hours
        self.monthly_remaining_drilling_hours = max(total_hours - completed_hours, 0)

        # 4) required_hourly_rate (meters/hour)
        if flt(self.monthly_remaining_drilling_hours) > 0:
            self.required_hourly_rate = flt(self.remaining_meter) / flt(self.monthly_remaining_drilling_hours)
        else:
            self.required_hourly_rate = 0

        # 5) drilling_meters_forecast
        # forecast = MTD meters + (current_rate * remaining_hours)
        current_rate = flt(self.current_rate)
        self.drilling_meters_forecast = flt(self.mtd_drills_meter) + (current_rate * flt(self.monthly_remaining_drilling_hours))
