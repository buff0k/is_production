from frappe.model.document import Document
import frappe
from frappe import _

class HourlyProduction(Document):
    def before_save(self):
        """
        Ensures all child tables and derived fields are updated before saving the parent document.
        Also validates Dozer Production entries based on the Dozer Service selected.
        """
        # --- Truck Loads Calculations ---
        total_softs_bcm = 0.0
        total_hards_bcm = 0.0
        total_coal_bcm = 0.0
        total_ts_bcm = 0.0
        num_prod_trucks = 0

        if hasattr(self, 'truck_loads'):
            for row in self.truck_loads:
                # Set `tub_factor_doc_lookup` as `<item_name>-<mat_type>`
                if row.item_name and row.mat_type:
                    row.tub_factor_doc_lookup = f"{row.item_name}-{row.mat_type}"
                    row.tub_factor = frappe.db.get_value(
                        "Tub Factor",
                        {"tub_factor_lookup": row.tub_factor_doc_lookup},
                        "tub_factor"
                    )
                else:
                    row.tub_factor_doc_lookup = None
                    row.tub_factor = None

                # Calculate `bcms`
                row.bcms = (row.loads * row.tub_factor) if row.loads and row.tub_factor else None

                # Summing totals
                if row.bcms:
                    total_ts_bcm += row.bcms
                    if row.mat_type == "Softs":
                        total_softs_bcm += row.bcms
                    elif row.mat_type == "Hards":
                        total_hards_bcm += row.bcms
                    elif row.mat_type == "Coal":
                        total_coal_bcm += row.bcms
                    if row.bcms > 0:
                        num_prod_trucks += 1

        # --- Dozer Production Calculations & Validation ---
        total_dozing_bcm = 0.0
        num_prod_dozers = 0
        # Allowed values for bcm_hour when Production Dozing is selected
        allowed_bcm_values = [0, 100, 110, 120, 130, 140, 150, 180, 190, 200]

        if hasattr(self, 'dozer_production'):
            for row in self.dozer_production:
                # Validate bcm_hour based on the selected dozer_service
                if row.dozer_service in ["No Dozing", "Tip Dozing", "Levelling"]:
                    if row.bcm_hour != 0:
                        frappe.throw(_(
                            "For Dozer Service '{0}', only a BCM in Hour value of 0 is allowed."
                        ).format(row.dozer_service))
                elif row.dozer_service in ["Production Dozing-50m", "Production Dozing-100m"]:
                    if row.bcm_hour not in allowed_bcm_values:
                        frappe.throw(_(
                            "For Dozer Service '{0}', BCM in Hour value must be one of {1}."
                        ).format(row.dozer_service, allowed_bcm_values))
                else:
                    frappe.throw(_("Invalid Dozer Service value: {0}.").format(row.dozer_service))

                # Accumulate totals for dozer production if bcm_hour is greater than 0
                if row.bcm_hour and row.bcm_hour > 0:
                    total_dozing_bcm += row.bcm_hour
                    num_prod_dozers += 1

        # --- Set Calculated Values ---
        self.total_softs_bcm = total_softs_bcm
        self.total_hards_bcm = total_hards_bcm
        self.total_coal_bcm = total_coal_bcm
        self.total_ts_bcm = total_ts_bcm
        self.num_prod_trucks = num_prod_trucks
        self.total_dozing_bcm = total_dozing_bcm
        self.num_prod_dozers = num_prod_dozers

        # Hour Total BCM
        hour_total_bcm = total_ts_bcm + total_dozing_bcm
        self.hour_total_bcm = hour_total_bcm

        # Percentages
        self.ts_percent = (total_ts_bcm / hour_total_bcm * 100) if hour_total_bcm else 0
        self.dozing_percent = (total_dozing_bcm / hour_total_bcm * 100) if hour_total_bcm else 0

        # Averages
        self.ave_bcm_dozer = (total_dozing_bcm / num_prod_dozers) if num_prod_dozers else 0
        self.ave_bcm_prod_truck = (total_ts_bcm / num_prod_trucks) if num_prod_trucks else 0


@frappe.whitelist()
def fetch_monthly_production_plan(location, prod_date):
    """
    Fetch the name of the Monthly Production Planning document for a given location and production date.
    """
    from frappe.utils import getdate, get_last_day
    if location and prod_date:
        prod_date = getdate(prod_date)
        last_day_of_month = get_last_day(prod_date)
        monthly_plan_name = f"{last_day_of_month}-{location}"
        return frappe.get_value("Monthly Production Planning", {"name": monthly_plan_name}, "name")
    return None


@frappe.whitelist()
def get_tub_factor(item_name, mat_type):
    """
    Fetch tub factor and its linked document for a given `item_name` and `mat_type`.
    """
    if item_name and mat_type:
        tub_factor_lookup = f"{item_name}-{mat_type}"  # No spaces around the hyphen
        return frappe.get_value("Tub Factor", {"tub_factor_lookup": tub_factor_lookup}, "tub_factor")
    return None


@frappe.whitelist()
def fetch_dozer_production_assets(location):
    """
    Fetch all Dozer assets for a given location.
    """
    if not location:
        return []

    # Fetch assets with category 'Dozer' and matching location
    assets = frappe.get_all(
        "Asset",
        filters={
            "location": location,
            "asset_category": "Dozer",
            "docstatus": 1
        },
        fields=["name as asset_name"]
    )

    return assets
