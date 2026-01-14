# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate
from datetime import timedelta


class DrillingMeterPlanning(Document):
    def validate(self):
        self.validate_dates()
        self.set_drilling_month_label()   # drilling_month is Data
        self.calculate_all()

    def validate_dates(self):
        if self.start_date and self.end_date:
            sd = getdate(self.start_date)
            ed = getdate(self.end_date)
            if ed < sd:
                frappe.throw("End Date cannot be earlier than Start Date.")

    def set_drilling_month_label(self):
        # Data field: "January 2026" or "Jan 2026 - Feb 2026"
        if not (self.start_date and self.end_date):
            self.drilling_month = ""
            return

        sd = getdate(self.start_date)
        ed = getdate(self.end_date)

        if sd.year == ed.year and sd.month == ed.month:
            self.drilling_month = sd.strftime("%B %Y")
        else:
            self.drilling_month = f"{sd.strftime('%b %Y')} - {ed.strftime('%b %Y')}"

    # ---------- core calcs ----------

    def calculate_all(self):
        # Inputs
        no_shifts = int(flt(self.no_of_shifts) or 0)  # select values are strings ("1","2","3")
        no_shifts = max(no_shifts, 0)

        weekday_hours = flt(self.weekday_shift_hours)
        saturday_hours = flt(self.saturday_shift_hours)

        monthly_target = flt(self.monthly_target_meters)
        worked_days = flt(self.worked_days)
        number_of_drills = flt(self.number_of_drills)

        # 1) Planned drilling days from date range (weekdays + Saturdays, no Sundays)
        planned_weekdays = 0
        planned_saturdays = 0
        planned_days = 0

        if self.start_date and self.end_date:
            planned_weekdays, planned_saturdays = count_weekdays_and_saturdays(self.start_date, self.end_date)
            planned_days = planned_weekdays + planned_saturdays

        # store planned_drilling_days as calculated (if you want it always system-driven)
        self.planned_drilling_days = int(planned_days)

        # clamp worked days
        worked_days = min(worked_days, flt(self.planned_drilling_days))
        self.worked_days = int(worked_days)

        # 2) Total monthly drilling hours
        total_hours_per_shift = (planned_weekdays * weekday_hours) + (planned_saturdays * saturday_hours)
        self.total_monthly_drilling_hours = max(total_hours_per_shift * no_shifts, 0)

        # 3) Monthly drilling hours completed (based on planned weekday/sat mix)
        avg_hours_per_day_one_shift = 0
        if planned_days > 0:
            avg_hours_per_day_one_shift = total_hours_per_shift / planned_days

        completed_hours = worked_days * avg_hours_per_day_one_shift * no_shifts
        self.monthly_drilling_hours_completed = max(completed_hours, 0)

        # 4) Monthly remaining hours
        self.monthly_remaining_drilling_hours = max(
            flt(self.total_monthly_drilling_hours) - flt(self.monthly_drilling_hours_completed),
            0
        )

        # 5) MTD drilled meters (linear progress vs worked days)
        if planned_days > 0:
            mtd_meters = (worked_days / planned_days) * monthly_target
        else:
            mtd_meters = 0

        # clamp to [0, target]
        mtd_meters = max(min(mtd_meters, monthly_target), 0)
        self.mtd_drills_meter = mtd_meters

        # 6) Remaining meters
        self.remaining_meter = max(monthly_target - flt(self.mtd_drills_meter), 0)

        # 7) Current rate (m/h)
        if flt(self.monthly_drilling_hours_completed) > 0:
            self.current_rate = flt(self.mtd_drills_meter) / flt(self.monthly_drilling_hours_completed)
        else:
            self.current_rate = 0

        # 8) Required hourly rate to hit target
        if flt(self.monthly_remaining_drilling_hours) > 0:
            self.required_hourly_rate = flt(self.remaining_meter) / flt(self.monthly_remaining_drilling_hours)
        else:
            self.required_hourly_rate = 0

        # 9) Meters per drill
        if number_of_drills > 0:
            self.meters_per_drill = monthly_target / number_of_drills
        else:
            self.meters_per_drill = 0

        # 10) Forecast meters by month end
        forecast = flt(self.mtd_drills_meter) + (flt(self.current_rate) * flt(self.monthly_remaining_drilling_hours))
        # clamp to [0, target]
        self.drilling_meters_forecast = max(min(forecast, monthly_target), 0)


def count_weekdays_and_saturdays(start_date, end_date):
    """
    Inclusive count of:
      - weekdays: Mon-Fri
      - Saturdays
    Sundays ignored (0)
    """
    sd = getdate(start_date)
    ed = getdate(end_date)

    weekdays = 0
    saturdays = 0

    d = sd
    while d <= ed:
        wd = d.weekday()  # Mon=0 ... Sun=6
        if wd <= 4:
            weekdays += 1
        elif wd == 5:
            saturdays += 1
        d = d + timedelta(days=1)

    return weekdays, saturdays
