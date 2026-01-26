import frappe
from frappe.model.document import Document
from frappe.utils import getdate, add_days


def _date_range(start, end):
    d = start
    while d <= end:
        yield d
        d = add_days(d, 1)


def _counts(start_date, end_date):
    """
    Returns (weekday_count_mon_fri, saturday_count, sunday_count)
    """
    wd = sat = sun = 0
    for d in _date_range(start_date, end_date):
        w = getdate(d).weekday()  # Mon=0 ... Sun=6
        if w <= 4:
            wd += 1
        elif w == 5:
            sat += 1
        else:
            sun += 1
    return wd, sat, sun


def _clamp0(x):
    return x if x and x > 0 else 0


class DrillingMeterPlanning(Document):
    def validate(self):
        """
        - Normal UI/manual saves: calculate KPIs.
        - Hourly Drill Report updates:
            - If Hourly Drill Report uses db.set_value: validate() won't run anyway.
            - If Hourly Drill Report uses save(): it MUST set frappe.flags.from_hourly_drill_report = True
              to prevent overwriting calculations.
        """
        if frappe.flags.get("from_hourly_drill_report"):
            return

        self.calculate_kpis()

    def calculate_kpis(self):
        # --- Validate dates ---
        if self.start_date and self.end_date and getdate(self.end_date) < getdate(self.start_date):
            frappe.throw("End Date cannot be before Start Date.")

        # --- Drilling month label ---
        if self.start_date:
            sd = getdate(self.start_date)
            self.drilling_month = sd.strftime("%b %Y")

        weekday_count = saturday_count = sunday_count = 0

        # --- Planned drilling days (Mon–Sat) ---
        if self.start_date and self.end_date:
            sd = getdate(self.start_date)
            ed = getdate(self.end_date)
            weekday_count, saturday_count, sunday_count = _counts(sd, ed)
            self.planned_drilling_days = weekday_count + saturday_count
        else:
            self.planned_drilling_days = 0

        # --- Remaining days ---
        worked = self.worked_days or 0
        self.remaining_days = _clamp0((self.planned_drilling_days or 0) - worked)

        # --- Daily target ---
        if (self.planned_drilling_days or 0) > 0:
            self.daily_target = (self.monthly_target_meters or 0) / self.planned_drilling_days
        else:
            self.daily_target = 0

        # --- Shifts / hours ---
        try:
            shifts = int(self.no_of_shifts or 0)
        except Exception:
            shifts = 0

        weekday_shift_hours = self.weekday_shift_hours or 0
        saturday_shift_hours = self.saturday_shift_hours or 0

        # Total monthly drilling hours
        if self.start_date and self.end_date and shifts > 0:
            self.total_monthly_drilling_hours = (
                (weekday_count * weekday_shift_hours) +
                (saturday_count * saturday_shift_hours)
            ) * shifts
        else:
            self.total_monthly_drilling_hours = 0

        # --- Hours completed proxy (avg hours/day * worked days) ---
        planned_days = self.planned_drilling_days or 0
        total_hours = self.total_monthly_drilling_hours or 0
        avg_daily_hours = (total_hours / planned_days) if planned_days > 0 else 0

        self.monthly_drilling_hours_completed = worked * avg_daily_hours
        self.monthly_remaining_drilling_hours = _clamp0(
            total_hours - (self.monthly_drilling_hours_completed or 0)
        )

        # --- Meters ---
        target = self.monthly_target_meters or 0
        mtd = self.mtd_drills_meter or 0

        self.remaining_meter = _clamp0(target - mtd)

        # Required hourly rate (remaining meters / remaining hours)
        rem_hours = self.monthly_remaining_drilling_hours or 0
        self.required_hourly_rate = (self.remaining_meter / rem_hours) if rem_hours > 0 else 0

        # Current rate (meters per hour so far)
        comp_hours = self.monthly_drilling_hours_completed or 0
        self.current_rate = (mtd / comp_hours) if comp_hours > 0 else 0

        # Meters per drill
        drills = self.number_of_drills or 0
        self.meters_per_drill = (target / drills) if drills > 0 else 0

        # Forecast (pace-based)
        self.drilling_meters_forecast = (
            ((mtd / worked) * planned_days) if worked > 0 and planned_days > 0 else 0
        )
