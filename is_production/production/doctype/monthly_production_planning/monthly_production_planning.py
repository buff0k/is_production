# apps/is_production/is_production/production/doctype/monthly_production_planning/monthly_production_planning.py

# Copyright (c) 2024, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import datetime
from frappe.exceptions import TimestampMismatchError

class MonthlyProductionPlanning(Document):
    def update_mtd_production(self):
        """
        Server-side Month-to-Date update: aggregates Hourly Production and Survey data
        and updates child table (month_prod_days) and parent fields accordingly.
        """
        # 1. Gather references from child table
        refs = [row.hourly_production_reference for row in self.month_prod_days if row.hourly_production_reference]
        if not refs:
            return

        # 2. Fetch Hourly Production aggregates
        hp_records = frappe.get_all('Hourly Production',
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

        # 3. Fetch Survey data
        srv_records = frappe.get_all('Survey',
            filters=[
                ['hourly_prod_ref', 'in', refs],
                ['docstatus', '=', 1]
            ],
            fields=['hourly_prod_ref', 'total_ts_bcm', 'total_dozing_bcm']
        )
        survey_map = {}
        for rec in srv_records:
            ref = rec['hourly_prod_ref']
            ts = rec.get('total_ts_bcm') or 0
            dz = rec.get('total_dozing_bcm') or 0
            survey_map[ref] = {'ts': ts, 'dz': dz}

        # 4. Identify latest survey reference
        survey_rows = [row for row in self.month_prod_days if row.hourly_production_reference in survey_map]
        last_ref = None
        if survey_rows:
            last_row = max(survey_rows, key=lambda r: r.shift_start_date)
            last_ref = last_row.hourly_production_reference

        # 5. Update child table rows
        cum_ts = 0
        cum_dz = 0
        for row in sorted(self.month_prod_days, key=lambda r: r.shift_start_date):
            ref = row.hourly_production_reference
            # Hourly Production totals
            hp = hp_map.get(ref, {'ts': 0, 'dz': 0})
            row.total_ts_bcms = hp['ts']
            row.total_dozing_bcms = hp['dz']
            # cumulative running totals
            cum_ts += row.total_ts_bcms or 0
            cum_dz += row.total_dozing_bcms or 0
            row.cum_ts_bcms = cum_ts
            row.tot_cumulative_dozing_bcms = cum_dz
            # survey and variances
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

        # Completed days & hours up to yesterday
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

        # Set virtual fields
        self.month_act_ts_bcm_tallies = total_ts
        self.month_act_dozing_bcm_tallies = total_dz
        self.monthly_act_tally_survey_variance = survey_var
        self.month_actual_bcm = actual
        self.prod_days_completed = done_days
        self.month_prod_hours_completed = done_hours
        self.month_remaining_production_days = (self.num_prod_days or 0) - done_days
        self.month_remaining_prod_hours = (self.total_month_prod_hours or 0) - done_hours
        self.mtd_bcm_day = mtd_day
        self.mtd_bcm_hour = mtd_hour
        self.month_forecated_bcm = forecast
        # targets
        if self.num_prod_days:
            self.target_bcm_day = self.monthly_target_bcm / self.num_prod_days
        if self.total_month_prod_hours:
            self.target_bcm_hour = self.monthly_target_bcm / self.total_month_prod_hours

        # Safely save without raising TimestampMismatchError
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
