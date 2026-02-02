# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import re
import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate
from datetime import datetime, timedelta


class HourlyDrillingReport(Document):
    def on_update(self):
        self.push_planning_rollups()

    def on_trash(self):
        # When a report is deleted, recompute the planning rollups as well
        self.push_planning_rollups()

    def push_planning_rollups(self):
        """
        Push rollups into the linked Drilling Meter Planning (if any).

        What this updates (only if the target field exists on Drilling Meter Planning):
          - MTD meters:
              * mtd_drills_meter and/or mtd_drilled_meters (both supported)
          - Monthly hours completed:
              * monthly_drilling_hours_completed
          - Current day meters (for this report's date):
              * current_daily_meters
          - Current hourly rate:
              * current_hourly_rate = current_daily_meters / current_daily_hours
          - Required hourly rate:
              * required_hourly_rate = daily_target_meters / current_daily_hours
          - Remaining meters:
              * remaining_meter = monthly_target_meters - mtd
          - Forecast:
              * drilling_meters_forecast = mtd * (plan_days / days_elapsed)

        Notes:
          - Uses SQL joins (child table is NOT a standalone table; it is tabHourly Entries,
            which is why attempting to query a fake table name breaks).
          - Uses meta checks so it won't crash if a field doesn't exist.
        """
        if not self.drilling_meter_planning:
            return

        try:
            planning = frappe.get_doc("Drilling Meter Planning", self.drilling_meter_planning)
            pmeta = frappe.get_meta("Drilling Meter Planning")

            start_date = getdate(planning.start_date) if planning.get("start_date") else None
            end_date = getdate(planning.end_date) if planning.get("end_date") else None

            # If planning has no dates, we still compute totals across ALL linked HDRs (docstatus < 2)
            date_filter_sql = ""
            date_filter_params = []
            if start_date and end_date:
                date_filter_sql = " AND hdr.date BETWEEN %s AND %s "
                date_filter_params = [start_date, end_date]

            # -------------------------
            # 1) MTD meters (sum of meters across all linked HDRs within planning range)
            # -------------------------
            total_meters = frappe.db.sql(
                f"""
                SELECT SUM(COALESCE(he.meters, 0))
                FROM `tabHourly Drilling Report` hdr
                JOIN `tabHourly Entries` he
                  ON he.parent = hdr.name
                 AND he.parenttype = 'Hourly Drilling Report'
                 AND he.parentfield = 'hourly_entries'
                WHERE hdr.drilling_meter_planning = %s
                  AND hdr.docstatus < 2
                  {date_filter_sql}
                """,
                [planning.name] + date_filter_params,
            )[0][0] or 0

            # -------------------------
            # 2) Monthly hours completed (sum DISTINCT hourly_slot per report)
            #    (we keep your original intent: avoid double counting repeated slots)
            # -------------------------
            slots = frappe.db.sql(
                f"""
                SELECT DISTINCT hdr.name AS report_name, he.hourly_slot
                FROM `tabHourly Drilling Report` hdr
                JOIN `tabHourly Entries` he
                  ON he.parent = hdr.name
                 AND he.parenttype = 'Hourly Drilling Report'
                 AND he.parentfield = 'hourly_entries'
                WHERE hdr.drilling_meter_planning = %s
                  AND hdr.docstatus < 2
                  {date_filter_sql}
                  AND COALESCE(he.hourly_slot, '') != ''
                """,
                [planning.name] + date_filter_params,
                as_dict=True,
            )

            total_hours = 0.0
            for s in slots:
                total_hours += flt(slot_to_hours(s.get("hourly_slot")))

            # -------------------------
            # 3) Current day meters + hours (for THIS report's date)
            # -------------------------
            report_date = getdate(self.date) if self.get("date") else None

            daily_meters = 0.0
            daily_hours = 0.0
            if report_date:
                daily_meters = frappe.db.sql(
                    """
                    SELECT SUM(COALESCE(he.meters, 0))
                    FROM `tabHourly Drilling Report` hdr
                    JOIN `tabHourly Entries` he
                      ON he.parent = hdr.name
                     AND he.parenttype = 'Hourly Drilling Report'
                     AND he.parentfield = 'hourly_entries'
                    WHERE hdr.drilling_meter_planning = %s
                      AND hdr.docstatus < 2
                      AND hdr.date = %s
                    """,
                    (planning.name, report_date),
                )[0][0] or 0

                daily_slots = frappe.db.sql(
                    """
                    SELECT DISTINCT he.hourly_slot
                    FROM `tabHourly Drilling Report` hdr
                    JOIN `tabHourly Entries` he
                      ON he.parent = hdr.name
                     AND he.parenttype = 'Hourly Drilling Report'
                     AND he.parentfield = 'hourly_entries'
                    WHERE hdr.drilling_meter_planning = %s
                      AND hdr.docstatus < 2
                      AND hdr.date = %s
                      AND COALESCE(he.hourly_slot, '') != ''
                    """,
                    (planning.name, report_date),
                    as_dict=True,
                )

                for r in daily_slots:
                    daily_hours += flt(slot_to_hours(r.get("hourly_slot")))

            current_hourly_rate = (flt(daily_meters) / flt(daily_hours)) if daily_hours else 0.0

            # Required hourly rate: daily_target_meters / daily_hours (if possible)
            daily_target = flt(planning.get("daily_target_meters")) if pmeta.has_field("daily_target_meters") else 0.0
            required_hourly_rate = (daily_target / flt(daily_hours)) if (daily_target and daily_hours) else 0.0

            # -------------------------
            # Forecast: simple linear projection from MTD rate
            # forecast = mtd * (plan_days / days_elapsed)
            # -------------------------
            drilling_meters_forecast = 0.0
            if start_date and end_date:
                plan_days = (end_date - start_date).days + 1
                # days elapsed = from start to min(report_date/end_date), inclusive
                anchor = report_date or end_date
                if anchor < start_date:
                    days_elapsed = 0
                else:
                    anchor = min(anchor, end_date)
                    days_elapsed = (anchor - start_date).days + 1

                if plan_days > 0 and days_elapsed > 0:
                    drilling_meters_forecast = flt(total_meters) * (flt(plan_days) / flt(days_elapsed))

            # Remaining meters: monthly_target_meters - mtd (if exists)
            remaining_meter = None
            if pmeta.has_field("monthly_target_meters"):
                monthly_target = flt(planning.get("monthly_target_meters"))
                remaining_meter = monthly_target - flt(total_meters)

            # -------------------------
            # Push updates (ONLY where fields exist)
            # -------------------------

            # MTD meters: support BOTH possible fieldnames.
            if pmeta.has_field("mtd_drills_meter"):
                planning.db_set("mtd_drills_meter", flt(total_meters), update_modified=True)
            if pmeta.has_field("mtd_drilled_meters"):
                planning.db_set("mtd_drilled_meters", flt(total_meters), update_modified=True)

            if pmeta.has_field("monthly_drilling_hours_completed"):
                planning.db_set("monthly_drilling_hours_completed", flt(total_hours), update_modified=True)

            if pmeta.has_field("current_daily_meters"):
                planning.db_set("current_daily_meters", flt(daily_meters), update_modified=True)

            if pmeta.has_field("current_hourly_rate"):
                planning.db_set("current_hourly_rate", flt(current_hourly_rate), update_modified=True)

            if pmeta.has_field("required_hourly_rate"):
                planning.db_set("required_hourly_rate", flt(required_hourly_rate), update_modified=True)

            if pmeta.has_field("drilling_meters_forecast"):
                planning.db_set("drilling_meters_forecast", flt(drilling_meters_forecast), update_modified=True)

            if remaining_meter is not None and pmeta.has_field("remaining_meter"):
                planning.db_set("remaining_meter", flt(remaining_meter), update_modified=True)

            # Re-load + save to allow any additional planning-side logic to run
            planning = frappe.get_doc("Drilling Meter Planning", planning.name)
            planning.save(ignore_permissions=True)

        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                "Hourly Drilling Report -> push planning rollups failed",
            )


def slot_to_hours(slot: str) -> float:
    """
    Converts hourly_slot like:
      - "06:00-07:00" => 1
      - "23:00-00:00" => 1 (wrap midnight)
      - "00:00-12:00" => 12
    If invalid => 1 hour
    """
    if not slot:
        return 1.0

    times = re.findall(r"\b(\d{2}:\d{2})(?::\d{2})?\b", slot)
    if len(times) < 2:
        return 1.0

    start_str, end_str = times[0], times[1]

    try:
        start = datetime.strptime(start_str, "%H:%M").time()
        end = datetime.strptime(end_str, "%H:%M").time()

        base = datetime(2000, 1, 1)
        start_dt = datetime.combine(base.date(), start)
        end_dt = datetime.combine(base.date(), end)

        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        hours = (end_dt - start_dt).total_seconds() / 3600.0
        if hours <= 0 or hours > 24:
            return 1.0
        return hours

    except Exception:
        return 1.0
