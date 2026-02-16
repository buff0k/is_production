# daily_lost_hours_recon.py

import frappe
import datetime
from frappe.model.document import Document


class DailyLostHoursRecon(Document):
    def validate(self):
        self.set_day_of_week_if_missing()
        self.calculate_parent_total_general_lost_hours()
        self.copy_parent_general_hours_to_child_rows()
        self.validate_child_rows_hours()

    def set_day_of_week_if_missing(self):
        if not self.day_of_week and self.shift_date:
            dt = datetime.datetime.strptime(self.shift_date, "%Y-%m-%d").date()
            self.day_of_week = dt.strftime("%A")

    def calculate_parent_total_general_lost_hours(self):
        """
        Includes blasting in calculation.
        """
        self.total_general_lost_hours = (
            (self.gen_training_hours or 0)
            + (self.weather_non_work_hours or 0)
            + (self.vfl_non_work_hours or 0)
            + (self.other_non_work_hours or 0)
            + (self.diesel_or_diesel_bowser_hours or 0)
            + (self.dust_water_bowser_issues_hours or 0)
            + (self.blasting or 0)
        )

    def copy_parent_general_hours_to_child_rows(self):
        for row in self.daily_lost_hours_assets_table:
            row.gen_training_hours_child = self.gen_training_hours or 0
            row.weather_non_work_hours_child = self.weather_non_work_hours or 0
            row.vfl_non_work_hours_child = self.vfl_non_work_hours or 0
            row.other_non_work_hours_child = self.other_non_work_hours or 0
            row.diesel_or_diesel_bowser_hours_child = self.diesel_or_diesel_bowser_hours or 0
            row.dust_water_bowser_issues_hours_child = self.dust_water_bowser_issues_hours or 0
            row.blasting_child = self.blasting or 0

            row.total_general_lost_hours_child = (
                (row.gen_training_hours_child or 0)
                + (row.weather_non_work_hours_child or 0)
                + (row.vfl_non_work_hours_child or 0)
                + (row.other_non_work_hours_child or 0)
                + (row.diesel_or_diesel_bowser_hours_child or 0)
                + (row.dust_water_bowser_issues_hours_child or 0)
                + (row.blasting_child or 0)
            )

    def validate_child_rows_hours(self):
        if self.day_of_week in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
            required_hours = self.weekday_required_hours or 0
        elif self.day_of_week == "Saturday":
            required_hours = self.sat_required_shift_hours or 0
        else:
            required_hours = 9999  # Sunday / disable validation

        for row in self.daily_lost_hours_assets_table:
            plant_specific = row.total_plant_specific_lost_hours or 0
            child_general = row.total_general_lost_hours_child or 0
            total_for_row = plant_specific + child_general

            if total_for_row > required_hours:
                frappe.throw(
                    f"Row #{row.idx}: (Plant Specific Lost Hours: {plant_specific} "
                    f"+ General Lost Hours Child: {child_general}) = {total_for_row} "
                    f"exceeds the required hours ({required_hours}) on {self.day_of_week}."
                )


# ------------------------------------------------------------------
# WHITELIST METHODS
# ------------------------------------------------------------------

@frappe.whitelist()
def get_monthly_production_planning(location, shift_date):
    """
    Auto-select Monthly Production Planning based on:
      - same location
      - prod_month_start_date <= shift_date <= prod_month_end_date
    Returns the plan name or None.
    """
    if not location or not shift_date:
        return None

    plan_name = frappe.db.get_value(
        "Monthly Production Planning",
        filters={
            "location": location,
            "prod_month_start_date": ["<=", shift_date],
            "prod_month_end_date": [">=", shift_date],
        },
        fieldname="name",
        order_by="prod_month_start_date desc",
    )

    return plan_name


@frappe.whitelist()
def get_shift_system(monthly_production_planning):
    if monthly_production_planning:
        return frappe.db.get_value(
            "Monthly Production Planning",
            monthly_production_planning,
            "shift_system"
        )
    return None


@frappe.whitelist()
def get_assets(location):
    asset_location_field = None
    doctype_meta = frappe.get_doc("DocType", "Asset")

    for field in doctype_meta.fields:
        if "location" in (field.fieldname or "").lower():
            asset_location_field = field.fieldname
            break

    if not asset_location_field:
        frappe.throw("No location field found in 'Asset'. Please check the Doctype configuration.")

    return frappe.db.get_all(
        "Asset",
        filters={asset_location_field: location, "docstatus": 1},
        fields=["name as asset_name", "item_name", "asset_category"],
        order_by="asset_category ASC"
    ) or []
