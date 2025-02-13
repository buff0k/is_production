import frappe
import datetime
from frappe.model.document import Document

class DailyLostHoursRecon(Document):
    def validate(self):
        """
        1) Set day_of_week if missing.
        2) Calculate total_general_lost_hours (parent).
        3) Copy parent's general lost hour fields (including diesel/dust bowser hours) to child fields.
        4) Compute total_general_lost_hours_child in each row.
        5) Validate that (total_plant_specific_lost_hours + total_general_lost_hours_child) 
           does not exceed required weekday or Saturday hours.
        """
        self.set_day_of_week_if_missing()
        self.calculate_parent_total_general_lost_hours()
        self.copy_parent_general_hours_to_child_rows()
        self.validate_child_rows_hours()

    def set_day_of_week_if_missing(self):
        """If 'day_of_week' is missing but shift_date is set, populate it from shift_date."""
        if not self.day_of_week and self.shift_date:
            dt = datetime.datetime.strptime(self.shift_date, '%Y-%m-%d').date()
            self.day_of_week = dt.strftime('%A')

    def calculate_parent_total_general_lost_hours(self):
        """
        Compute total_general_lost_hours as the sum of:
        - gen_training_hours
        - weather_non_work_hours
        - vfl_non_work_hours
        - other_non_work_hours
        - diesel_or_diesel_bowser_hours (NEW)
        - dust_water_bowser_issues_hours (NEW)
        """
        self.total_general_lost_hours = (
            (self.gen_training_hours or 0)
            + (self.weather_non_work_hours or 0)
            + (self.vfl_non_work_hours or 0)
            + (self.other_non_work_hours or 0)
            + (self.diesel_or_diesel_bowser_hours or 0)
            + (self.dust_water_bowser_issues_hours or 0)
        )

    def copy_parent_general_hours_to_child_rows(self):
        """
        For each row in daily_lost_hours_assets_table:
            1) Copy parent fields into matching child fields:
               - gen_training_hours -> gen_training_hours_child
               - weather_non_work_hours -> weather_non_work_hours_child
               - vfl_non_work_hours -> vfl_non_work_hours_child
               - other_non_work_hours -> other_non_work_hours_child
               - diesel_or_diesel_bowser_hours -> diesel_or_diesel_bowser_hours_child
               - dust_water_bowser_issues_hours -> dust_water_bowser_issues_hours_child

            2) Recompute row.total_general_lost_hours_child as the sum of those values.
        """
        for row in self.daily_lost_hours_assets_table:
            # 1) Copy values from parent
            row.gen_training_hours_child = self.gen_training_hours or 0
            row.weather_non_work_hours_child = self.weather_non_work_hours or 0
            row.vfl_non_work_hours_child = self.vfl_non_work_hours or 0
            row.other_non_work_hours_child = self.other_non_work_hours or 0
            row.diesel_or_diesel_bowser_hours_child = self.diesel_or_diesel_bowser_hours or 0
            row.dust_water_bowser_issues_hours_child = self.dust_water_bowser_issues_hours or 0

            # 2) Compute total_general_lost_hours_child
            row.total_general_lost_hours_child = (
                row.gen_training_hours_child
                + row.weather_non_work_hours_child
                + row.vfl_non_work_hours_child
                + row.other_non_work_hours_child
                + row.diesel_or_diesel_bowser_hours_child
                + row.dust_water_bowser_issues_hours_child
            )

    def validate_child_rows_hours(self):
        """
        Validate each child row to ensure:
        (total_plant_specific_lost_hours + total_general_lost_hours_child) ≤ required_hours.
        """
        # Determine the required hours based on the day of the week
        if self.day_of_week in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
            required_hours = self.weekday_required_hours or 0
        elif self.day_of_week == "Saturday":
            required_hours = self.sat_required_shift_hours or 0
        else:
            required_hours = 9999  # Handle Sunday/other days if needed

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


@frappe.whitelist()
def get_monthly_production_planning(location, shift_date):
    """
    Fetch the latest Monthly Production Planning that covers the given shift_date.
    """
    monthly_plan = frappe.db.sql(
        """
        SELECT name
        FROM `tabMonthly Production Planning`
        WHERE location = %s
          AND prod_month_start_date <= %s
          AND prod_month_end_date >= %s
        ORDER BY prod_month_start_date DESC
        LIMIT 1
        """,
        (location, shift_date, shift_date),
        as_dict=True
    )
    return monthly_plan[0]["name"] if monthly_plan else None


@frappe.whitelist()
def get_shift_system(monthly_production_planning):
    """
    Return the shift system from the Monthly Production Planning document.
    """
    if monthly_production_planning:
        return frappe.db.get_value(
            "Monthly Production Planning", 
            monthly_production_planning, 
            "shift_system"
        )
    return None


@frappe.whitelist()
def get_assets(location):
    """
    Retrieve assets that belong to the specified location and have docstatus=1.
    Each asset contains:
      - asset_name
      - item_name
      - asset_category
    """
    asset_location_field = None
    doctype_meta = frappe.get_doc("DocType", "Asset")
    for field in doctype_meta.fields:
        if "location" in field.fieldname.lower():
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
