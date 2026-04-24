# Copyright (c) 2026
# For license information, please see license.txt

# apps/is_production/is_production/production/doctype/machine_availability_hourly/machine_availability_hourly.py

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class MachineAvailabilityHourly(Document):
    def validate(self):
        self.set_day_number()
        self.set_hour_fields()

    def before_save(self):
        self.set_day_number()
        self.set_hour_fields()

    def set_day_number(self):
        if not self.date:
            self.day_number = None
            return

        parsed_date = self.parse_date_value(self.date)

        if parsed_date:
            self.day_number = parsed_date.day
        else:
            self.day_number = None

    def set_hour_fields(self):
        if not self.shift_num_hour:
            self.hour_sort_key = None
            self.hour_slot = None
            return

        try:
            shift_label, idx_str = self.shift_num_hour.split("-", 1)
            idx = int(idx_str)
        except Exception:
            frappe.throw("Shift Number Hours must be in the format Shift-Number, for example Day-1.")

        if idx < 1:
            frappe.throw("Shift Number Hours must use a number greater than 0.")

        self.hour_sort_key = idx

        base_hour = self.get_base_hour(shift_label)
        start_hour = (base_hour + (idx - 1)) % 24
        end_hour = (start_hour + 1) % 24

        self.hour_slot = f"{start_hour:02d}:00-{end_hour:02d}:00"

    def get_base_hour(self, shift_label):
        if shift_label in ("Day", "Morning"):
            return 6

        if shift_label == "Afternoon":
            return 14

        if shift_label == "Night":
            return 18

        return 6

    def parse_date_value(self, value):
        if not value:
            return None

        try:
            return getdate(value)
        except Exception:
            pass

        try:
            parts = str(value).split("-")

            if len(parts) == 3 and len(parts[0]) == 2 and len(parts[2]) == 4:
                day, month, year = parts
                return getdate(f"{year}-{month}-{day}")
        except Exception:
            pass

        return None


@frappe.whitelist()
def get_assets_for_site_and_category(site, asset_category):
    if not site:
        frappe.throw("Please select a Site first.")

    if not asset_category:
        frappe.throw("Please select an Asset Category first.")

    return frappe.get_all(
        "Asset",
        filters={
            "location": site,
            "asset_category": asset_category
        },
        fields=[
            "name",
            "asset_name",
            "location",
            "asset_category"
        ],
        order_by="name asc"
    )