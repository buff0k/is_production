import frappe
from frappe.model.document import Document
from frappe.utils import flt


class DailyDrillingReport(Document):
    def validate(self):
        self.set_totals()

    def before_save(self):
        # extra safety
        self.set_totals()

    def set_totals(self):
        # (closing - opening)
        self.total_drilling_hrs = flt(self.closing_drilling_hrs) - flt(self.opening_drilling_hrs)

        total_meters = 0.0
        total_holes = 0.0

        for row in (self.get("holes_and_meter") or []):
            total_meters += flt(row.meters)
            total_holes += flt(row.no_of_holes)

        self.total_meters = total_meters
        self.total_holes = total_holes
