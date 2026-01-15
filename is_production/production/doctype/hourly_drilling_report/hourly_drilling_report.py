import re
import frappe
from frappe.model.document import Document
from frappe.utils import flt
from datetime import datetime, timedelta


class HourlyDrillingReport(Document):
    def on_update(self):
        self.push_mtd_meters_and_completed_hours()

    def on_trash(self):
        self.push_mtd_meters_and_completed_hours()

    def push_mtd_meters_and_completed_hours(self):
        """
        Push to linked Drilling Meter Planning:
          - mtd_drills_meter = SUM(hourly_entries.meters)
          - monthly_drilling_hours_completed = SUM(hours from hourly_slot)
            counting DISTINCT hourly_slot per report to avoid double counting same hour
        """
        if not self.drilling_meter_planning:
            return

        try:
            planning = frappe.get_doc("Drilling Meter Planning", self.drilling_meter_planning)

            # 1) MTD meters: sum meters from all linked reports in planning date range
            total_meters = frappe.db.sql(
                """
                SELECT SUM(COALESCE(he.meters, 0))
                FROM `tabHourly Drilling Report` hdr
                JOIN `tabHourly Entries` he
                  ON he.parent = hdr.name
                 AND he.parenttype = 'Hourly Drilling Report'
                 AND he.parentfield = 'hourly_entries'
                WHERE hdr.drilling_meter_planning = %s
                  AND hdr.docstatus < 2
                  AND hdr.date BETWEEN %s AND %s
                """,
                (planning.name, planning.start_date, planning.end_date),
            )[0][0] or 0

            # 2) Completed hours: distinct slots per report
            slots = frappe.db.sql(
                """
                SELECT DISTINCT hdr.name AS report_name, he.hourly_slot
                FROM `tabHourly Drilling Report` hdr
                JOIN `tabHourly Entries` he
                  ON he.parent = hdr.name
                 AND he.parenttype = 'Hourly Drilling Report'
                 AND he.parentfield = 'hourly_entries'
                WHERE hdr.drilling_meter_planning = %s
                  AND hdr.docstatus < 2
                  AND hdr.date BETWEEN %s AND %s
                  AND COALESCE(he.hourly_slot, '') != ''
                """,
                (planning.name, planning.start_date, planning.end_date),
                as_dict=True
            )

            total_hours = 0.0
            for s in slots:
                total_hours += flt(slot_to_hours(s.get("hourly_slot")))

            # Push without calling planning.save first (we will save after db_set)
            planning.db_set("mtd_drills_meter", flt(total_meters), update_modified=True)
            planning.db_set("monthly_drilling_hours_completed", flt(total_hours), update_modified=True)

            # Save planning so the rest of its calculations update
            planning = frappe.get_doc("Drilling Meter Planning", planning.name)
            planning.save(ignore_permissions=True)

        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                "Hourly Drilling Report -> push meters & completed hours failed"
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

    # Extract first 2 HH:MM tokens robustly
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
