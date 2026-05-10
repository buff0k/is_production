# apps/is_production/is_production/production/doctype/monthly_production_planning/monthly_production_planning.py

# Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import datetime
from frappe.exceptions import TimestampMismatchError
from frappe.utils import add_days, flt, get_datetime, getdate


class MonthlyProductionPlanning(Document):
    def validate(self):
        """
        Validate document before saving.
        Only sync month_prod_days when production date/shift setup changed.
        """
        self.validate_shift_hours()

        if self.should_sync_month_prod_days():
            self.sync_month_prod_days()
        
    def validate_shift_hours(self):
        """
        Validate that shift hours don't exceed 12
        """
        if self.weekday_shift_hours and self.weekday_shift_hours > 12:
            frappe.throw(
                "Weekday Shift Hours cannot be more than 12",
                title="Invalid Shift Hours"
            )

        if self.saturday_shift_hours and self.saturday_shift_hours > 12:
            frappe.throw(
                "Saturday Shift Hours cannot be more than 12",
                title="Invalid Shift Hours"
            )


    def should_sync_month_prod_days(self):
        """
        Only run month_prod_days sync when setup fields changed.
        Avoid heavy child-table rebuild on every normal save.
        """
        if self.is_new():
            return True

        before = self.get_doc_before_save()

        if not before:
            return True

        sync_fields = [
            "prod_month_start_date",
            "prod_month_end_date",
            "shift_system",
            "weekday_shift_hours",
            "saturday_shift_hours",
            "num_sat_shifts",
            "num_excavators",
        ]

        return any(self.has_value_changed(fieldname) for fieldname in sync_fields)


    def sync_month_prod_days(self):
        """
        Ensure month_prod_days matches the configured production date range.

        This keeps existing row data for dates already present, creates any
        missing rows when the plan range is extended, and removes rows that
        fall outside the configured range.
        """
        if not self.prod_month_start_date or not self.prod_month_end_date:
            return

        start_date = getdate(self.prod_month_start_date)
        end_date = getdate(self.prod_month_end_date)

        if not start_date or not end_date or start_date > end_date:
            return

        existing_by_date = {}
        for row in self.month_prod_days or []:
            if row.shift_start_date:
                existing_by_date[getdate(row.shift_start_date)] = row.as_dict()

        rows = []
        totals = {"day": 0, "night": 0, "morning": 0, "afternoon": 0}
        shift_date = start_date

        while shift_date <= end_date:
            hours = self.get_shift_hours_for_date(shift_date)
            row_data = existing_by_date.get(shift_date, {})

            production_excavators = row_data.get("production_excavators")
            if production_excavators in (None, ""):
                production_excavators = self.num_excavators or 0

            total_shift_hours = sum(hours.values())
            bcm_per_day = (flt(production_excavators) if production_excavators else 0) * total_shift_hours * 220

            row_data.update({
                "doctype": "Monthly Production Days",
                "shift_start_date": shift_date,
                "day_week": shift_date.strftime("%A"),
                "shift_day_hours": hours["day"],
                "shift_night_hours": hours["night"],
                "shift_morning_hours": hours["morning"],
                "shift_afternoon_hours": hours["afternoon"],
                "production_excavators": production_excavators,
                "bcm_per_day": bcm_per_day,
            })

            if self.name:
                row_data["hourly_production_reference"] = f"{self.name}-{shift_date}"

            rows.append(row_data)

            totals["day"] += hours["day"]
            totals["night"] += hours["night"]
            totals["morning"] += hours["morning"]
            totals["afternoon"] += hours["afternoon"]
            shift_date = add_days(shift_date, 1)

        self.set("month_prod_days", [])
        for row_data in rows:
            self.append("month_prod_days", row_data)

        total_hours = totals["day"] + totals["night"] + totals["morning"] + totals["afternoon"]
        self.tot_shift_day_hours = totals["day"]
        self.tot_shift_night_hours = totals["night"]
        self.tot_shift_morning_hours = totals["morning"]
        self.tot_shift_afternoon_hours = totals["afternoon"]
        self.total_month_prod_hours = total_hours
        self.num_prod_days = sum(
            1 for row in self.month_prod_days
            if any([
                row.shift_day_hours,
                row.shift_night_hours,
                row.shift_morning_hours,
                row.shift_afternoon_hours,
            ])
        )

        if self.monthly_target_bcm:
            self.target_bcm_day = self.monthly_target_bcm / self.num_prod_days if self.num_prod_days else 0
            self.target_bcm_hour = self.monthly_target_bcm / total_hours if total_hours else 0

    def get_shift_hours_for_date(self, shift_date):
        weekday_shift_hours = self.weekday_shift_hours or 0
        saturday_shift_hours = self.saturday_shift_hours or 0
        num_sat_shifts = int(self.num_sat_shifts or 0)
        day_name = shift_date.strftime("%A")

        hours = {"day": 0, "night": 0, "morning": 0, "afternoon": 0}

        if self.shift_system == "2x12Hour":
            if day_name == "Saturday":
                hours["day"] = saturday_shift_hours
                hours["night"] = saturday_shift_hours if num_sat_shifts > 1 else 0
            elif day_name != "Sunday":
                hours["day"] = weekday_shift_hours
                hours["night"] = weekday_shift_hours
        else:
            if day_name == "Saturday":
                hours["morning"] = saturday_shift_hours
                hours["afternoon"] = saturday_shift_hours if num_sat_shifts > 1 else 0
                hours["night"] = saturday_shift_hours if num_sat_shifts > 2 else 0
            elif day_name != "Sunday":
                hours["morning"] = weekday_shift_hours
                hours["afternoon"] = weekday_shift_hours
                hours["night"] = weekday_shift_hours

        return hours
    
    def update_mtd_production(self):
        """
        Server-side Month-to-Date update: aggregates Hourly Production and Survey data
        and updates child table (month_prod_days) and parent fields accordingly.
        """
        # 1. Gather references from child table
        refs = [row.hourly_production_reference for row in self.month_prod_days if row.hourly_production_reference]
        
        # 2. Fetch Hourly Production aggregates
        hp_records = frappe.get_all(
            'Hourly Production',
            filters=[
                ['month_prod_planning', '=', self.name],
                ['monthly_production_child_ref', 'in', refs]
            ],
            fields=['monthly_production_child_ref', 'total_ts_bcm', 'total_dozing_bcm']
        )

        hp_map = {}
        for rec in hp_records:
            ref = rec['monthly_production_child_ref']
            ts = rec.get('total_ts_bcm') or 0
            dz = rec.get('total_dozing_bcm') or 0
            hp_map.setdefault(ref, {'ts': 0, 'dz': 0})
            hp_map[ref]['ts'] += ts
            hp_map[ref]['dz'] += dz

        # 3. Fetch Survey data (for TS / dozing variances)
        srv_records = frappe.get_all(
            'Survey',
            filters=[
                ['hourly_prod_ref', 'in', refs],
                ['docstatus', '=', 1]
            ],
            fields=['hourly_prod_ref', 'total_ts_bcm', 'total_dozing_bcm']
        )

        survey_map = {}
        for rec in srv_records:
            ref = rec['hourly_prod_ref']
            survey_map[ref] = {
                'ts': rec.get('total_ts_bcm') or 0,
                'dz': rec.get('total_dozing_bcm') or 0
            }

        # 4. Identify latest survey reference
        survey_rows = [row for row in self.month_prod_days if row.hourly_production_reference in survey_map]
        last_ref = None
        if survey_rows:
            last_row = max(survey_rows, key=lambda r: r.shift_start_date)
            last_ref = last_row.hourly_production_reference

        # ─────────────────────────────────────────────
        # MONTH ACTUAL COAL (MATCHES PRODUCTION SUMMARY)
        # ─────────────────────────────────────────────

        COAL_CONVERSION = 1.5
        month_actual_coal = 0

        start_dt = get_datetime(self.prod_month_start_date)
        end_dt   = get_datetime(f"{self.prod_month_end_date} 23:59:59")

        # 1️⃣ Get latest survey ≤ month end
        survey = frappe.get_all(
            "Survey",
            filters={
                "location": self.location,
                "last_production_shift_start_date": ["<=", end_dt],
                "docstatus": 1
            },
            fields=[
                "last_production_shift_start_date",
                "total_surveyed_coal_tons"
            ],
            order_by="last_production_shift_start_date desc",
            limit_page_length=1
        )

        if survey:
            survey_date = survey[0]["last_production_shift_start_date"]
            if isinstance(survey_date, datetime.datetime):
                survey_date = survey_date.date()


            # Ensure survey is inside the month
            if self.prod_month_start_date <= survey_date <= self.prod_month_end_date:
                month_actual_coal = survey[0]["total_surveyed_coal_tons"] or 0

                coal_after = frappe.db.sql("""
                    SELECT COALESCE(SUM(tl.bcms),0)
                    FROM `tabHourly Production` hp
                    JOIN `tabTruck Loads` tl ON tl.parent = hp.name
                    WHERE hp.location = %s
                      AND hp.prod_date > %s
                      AND hp.prod_date <= %s
                      AND LOWER(tl.mat_type) LIKE '%%coal%%'
                """, (self.location, survey_date, end_dt))[0][0]

                month_actual_coal += (coal_after or 0) * COAL_CONVERSION
            else:
                survey = None

        # 2️⃣ No valid survey → use all HP coal for month
        if not survey:
            coal_bcm = frappe.db.sql("""
                SELECT COALESCE(SUM(tl.bcms),0)
                FROM `tabHourly Production` hp
                JOIN `tabTruck Loads` tl ON tl.parent = hp.name
                WHERE hp.location = %s
                  AND hp.prod_date BETWEEN %s AND %s
                  AND LOWER(tl.mat_type) LIKE '%%coal%%'
            """, (self.location, start_dt, end_dt))[0][0]

            month_actual_coal = (coal_bcm or 0) * COAL_CONVERSION

        self.month_actual_coal = month_actual_coal

        # 5. Update child table rows
        cum_ts = 0
        cum_dz = 0
        for row in sorted(self.month_prod_days, key=lambda r: r.shift_start_date):
            ref = row.hourly_production_reference
            hp = hp_map.get(ref, {'ts': 0, 'dz': 0})

            row.total_ts_bcms = hp['ts']
            row.total_dozing_bcms = hp['dz']

            cum_ts += row.total_ts_bcms or 0
            cum_dz += row.total_dozing_bcms or 0

            row.cum_ts_bcms = cum_ts
            row.tot_cumulative_dozing_bcms = cum_dz

            sv = survey_map.get(ref, {'ts': 0, 'dz': 0})
            if ref == last_ref:
                row.tot_cum_ts_survey = sv['ts']
                row.tot_cum_dozing_survey = sv['dz']
                row.cum_ts_variance = sv['ts'] - cum_ts
                row.cum_dozing_variance = sv['dz'] - cum_dz
            else:
                row.tot_cum_ts_survey = 0
                row.tot_cum_dozing_survey = 0
                row.cum_ts_variance = 0
                row.cum_dozing_variance = 0

        # 6. Parent-level totals and MTD summary
        total_ts = sum(row.total_ts_bcms or 0 for row in self.month_prod_days)
        total_dz = sum(row.total_dozing_bcms or 0 for row in self.month_prod_days)

        survey_var = 0
        if last_ref:
            base_row = next((r for r in self.month_prod_days if r.hourly_production_reference == last_ref), None)
            if base_row:
                sv = survey_map.get(last_ref, {'ts': 0, 'dz': 0})
                survey_var = (sv['dz'] - base_row.tot_cumulative_dozing_bcms) + (sv['ts'] - base_row.cum_ts_bcms)

        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)

        done_days = 0
        done_hours = 0
        for r in self.month_prod_days:
            if r.shift_start_date and r.shift_start_date <= yesterday:
                hrs = (
                    (r.shift_day_hours or 0) +
                    (r.shift_night_hours or 0) +
                    (r.shift_morning_hours or 0) +
                    (r.shift_afternoon_hours or 0)
                )
                if hrs:
                    done_days += 1
                    done_hours += hrs

        actual = total_ts + total_dz + survey_var
        mtd_day = actual / done_days if done_days else 0
        mtd_hour = actual / done_hours if done_hours else 0
        forecast = mtd_hour * (self.total_month_prod_hours or 0)

        self.month_act_ts_bcm_tallies = total_ts
        self.month_act_dozing_bcm_tallies = total_dz
        self.monthly_act_tally_survey_variance = survey_var
        self.month_actual_bcm = actual

        if self.month_actual_coal:
            try:
                self.split_ratio = (
                    self.month_actual_bcm
                    - (self.month_actual_coal / 1.5)
                ) / self.month_actual_coal
            except ZeroDivisionError:
                self.split_ratio = 0
        else:
            self.split_ratio = 0

        self.prod_days_completed = done_days
        self.month_prod_hours_completed = done_hours
        self.month_remaining_production_days = (self.num_prod_days or 0) - done_days
        self.month_remaining_prod_hours = (self.total_month_prod_hours or 0) - done_hours
        self.mtd_bcm_day = mtd_day
        self.mtd_bcm_hour = mtd_hour
        self.month_forecated_bcm = forecast

        if self.num_prod_days:
            self.target_bcm_day = self.monthly_target_bcm / self.num_prod_days
        if self.total_month_prod_hours:
            self.target_bcm_hour = self.monthly_target_bcm / self.total_month_prod_hours

        try:
            self.save()
        except TimestampMismatchError as e:
            frappe.log_error(
                message=f"TimestampMismatchError in update_mtd_production for {self.name}: {e}",
                title="update_mtd_production"
            )


@frappe.whitelist()
def update_mtd_production(name):
    """
    RPC wrapper so Hourly Production can trigger the MPP MTD update.
    """
    try:
        doc = frappe.get_doc('Monthly Production Planning', name)
        doc.update_mtd_production()
        return {"status": "success", "name": name}
    except Exception as e:
        frappe.log_error(
            message=f"Error in RPC update_mtd_production for {name}: {e}",
            title="update_mtd_production RPC"
        )
        return {"status": "error", "message": str(e)}
