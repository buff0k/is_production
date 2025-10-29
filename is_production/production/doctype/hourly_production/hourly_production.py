# apps/is_production/is_production/production/doctype/hourly_production/hourly_production.py

# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

from frappe.model.document import Document
import frappe
from frappe import _
from frappe.utils import getdate, add_to_date, nowdate


class HourlyProduction(Document):

    def validate(self):
        """General validation before save"""
        self.validate_truck_loads()
        self.validate_dozer_production()

    def validate_truck_loads(self):
        for row in getattr(self, "truck_loads", []):
            if (row.loads or 0) > 0:
                if not row.geo_mat_layer_truck:
                    frappe.throw(
                        _("Row {0}: Please select a Geo Material Layer for truck {1}")
                        .format(row.idx, row.asset_name_truck or "")
                    )
                if not row.mining_areas_trucks:
                    frappe.throw(
                        _("Row {0}: Please select a Mining Area for truck {1}")
                        .format(row.idx, row.asset_name_truck or "")
                    )

    def validate_dozer_production(self):
        for row in getattr(self, "dozer_production", []):
            if (row.bcm_hour or 0) > 0:
                if not row.dozer_geo_mat_layer:
                    frappe.throw(
                        _("Row {0}: Please select a Geo Material Layer for dozer {1}")
                        .format(row.idx, row.asset_name or "")
                    )
                if not row.mining_areas_dozer_child:
                    frappe.throw(
                        _("Row {0}: Please select a Mining Area for dozer {1}")
                        .format(row.idx, row.asset_name or "")
                    )

    @frappe.whitelist()
    def before_save(self):
        """
        Ensures all child tables and derived fields are updated before saving the parent document.
        Also validates Dozer Production entries based on the Dozer Service selected.
        Always recalculates hour_sort_key (and hour_slot) from shift_num_hour.
        """
        if self.total_coal_bcm is not None:
            self.coal_tons_total = self.total_coal_bcm * 1.5
        else:
            self.coal_tons_total = 0

        # --- Truck Loads Calculations ---
        total_softs_bcm = total_hards_bcm = total_coal_bcm = total_ts_bcm = 0.0
        num_prod_trucks = 0

        if hasattr(self, 'truck_loads'):
            for row in self.truck_loads:
                if row.geo_mat_layer_truck and not row.mat_type:
                    mpp = frappe.get_doc("Monthly Production Planning", self.month_prod_planning)
                    for geo_row in mpp.geo_mat_layer:
                        if geo_row.geo_ref_description == row.geo_mat_layer_truck:
                            row.mat_type = geo_row.custom_material_type
                            break

        if hasattr(self, 'truck_loads'):
            for row in self.truck_loads:
                tf = frappe.get_all(
                    "Tub Factor",
                    filters={"item_name": row.item_name, "mat_type": row.mat_type},
                    fields=["name", "tub_factor"],
                    limit=1
                )
                if tf:
                    row.tub_factor_doc_lookup = tf[0]["name"]
                    row.tub_factor = tf[0]["tub_factor"]
                else:
                    row.tub_factor_doc_lookup = None
                    row.tub_factor = None

                try:
                    row.bcms = float(row.loads or 0) * float(row.tub_factor or 0)
                except Exception:
                    row.bcms = None

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
        allowed_bcm_values = [0,100,110,120,130,140,150,180,190,200]

        if hasattr(self, 'dozer_production'):
            for row in self.dozer_production:
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

        hour_total_bcm = total_ts_bcm + total_dozing_bcm
        self.hour_total_bcm = hour_total_bcm
        self.ts_percent = (total_ts_bcm / hour_total_bcm * 100) if hour_total_bcm else 0
        self.dozing_percent = (total_dozing_bcm / hour_total_bcm * 100) if hour_total_bcm else 0
        self.ave_bcm_dozer = (total_dozing_bcm / num_prod_dozers) if num_prod_dozers else 0
        self.ave_bcm_prod_truck = (total_ts_bcm / num_prod_trucks) if num_prod_trucks else 0
        self.calculate_day_total_bcm()

                # --- Recompute hour_sort_key & hour_slot using actual shift start times ---
        if self.shift_num_hour:
            try:
                shift_label, idx_str = self.shift_num_hour.split("-", 1)
                idx = int(idx_str)
                self.hour_sort_key = idx

                # ✅ Determine base start hour dynamically from the real shift fields
                base_hour = 6  # default fallback
                if self.shift in ("Day", "Morning") and getattr(self, "day_shift_start", None):
                    base_hour = int(str(self.day_shift_start).split(":")[0])
                elif self.shift == "Afternoon" and hasattr(self, "afternoon_shift_start"):
                    base_hour = int(str(self.afternoon_shift_start).split(":")[0])
                elif self.shift == "Night" and getattr(self, "night_shift_start", None):
                    base_hour = int(str(self.night_shift_start).split(":")[0])

                # ✅ Calculate start and end hours for this hourly slot
                start = (base_hour + (idx - 1)) % 24
                end = (start + 1) % 24

                # ✅ Format as 24-hour with leading zeros
                start_label = f"{start:02d}:00"
                end_label = f"{end:02d}:00"

                # ✅ Only overwrite if slot is blank or incorrect
                if not self.hour_slot or len(self.hour_slot.strip()) < 5:
                    self.hour_slot = f"{start_label}-{end_label}"

            except Exception as e:
                frappe.log_error(
                    f"Hour slot computation failed for {self.name}: {e}",
                    "Hourly Production before_save hour_slot"
                )
                self.hour_sort_key = None
     


    def calculate_day_total_bcm(self):
        """Calculate and set the day_total_bcm from all hourly entries for this location and date"""
        if not self.prod_date or not self.location:
            return

        day_total = frappe.db.sql("""
            SELECT SUM(hour_total_bcm)
            FROM `tabHourly Production`
            WHERE location = %s
            AND prod_date = %s
            AND docstatus < 2
            AND name != %s
        """, (self.location, self.prod_date, self.name), as_list=True)

        current_hour_total = self.hour_total_bcm or 0
        self.day_total_bcm = (day_total[0][0] or 0) + current_hour_total

    def before_print(self, print_settings):
        """
        Hook to sync MTD values just before printing (preview or PDF).
        """
        if getattr(self, 'month_prod_planning', None):
            frappe.get_attr(
                "is_production.production.doctype.monthly_production_planning."
                "monthly_production_planning.update_mtd_production"
            )(name=self.month_prod_planning)

            mpp = frappe.get_doc("Monthly Production Planning", self.month_prod_planning)
            for field in [
                'monthly_target_bcm', 'target_bcm_day', 'target_bcm_hour',
                'month_act_ts_bcm_tallies', 'month_act_dozing_bcm_tallies',
                'monthly_act_tally_survey_variance', 'month_actual_bcm',
                'mtd_bcm_day', 'mtd_bcm_hour', 'month_forecated_bcm'
            ]:
                setattr(self, field, getattr(mpp, field))

    @frappe.whitelist()
    def send_whatsapp_notification(self):
        """Send WhatsApp notification when button is clicked"""
        try:
            notification = frappe.get_doc("WhatsApp Notification", "Hourly Production Indiv.")
            if notification.disabled:
                frappe.msgprint("WhatsApp notification is disabled", indicator="orange")
                return
            notification.send_template_message(self)
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "WhatsApp Notification Error")
            frappe.msgprint(f"Failed to send WhatsApp notification: {str(e)}", indicator="red")

    # ✅ NEW SECTION: automatic MTD update
    def on_update(self):
        """
        Automatically update Month-to-Date (MTD) Production whenever this record is saved.
        """
        if not self.month_prod_planning:
            return

        try:
            # Run the MTD update immediately after save
            frappe.get_attr(
                "is_production.production.doctype.monthly_production_planning."
                "monthly_production_planning.update_mtd_production"
            )(name=self.month_prod_planning)

            frappe.msgprint(
                _("Month-to-Date Production updated automatically."),
                alert=True,
                indicator="green"
            )

        except Exception as e:
            frappe.log_error(
                message=f"Auto MTD update failed for Hourly Production {self.name}: {e}",
                title="Hourly Production Auto MTD Update"
            )


@frappe.whitelist()
def get_user_whatsapp_number(user):
    """Get WhatsApp number from user profile (mobile_no fallback)"""
    if not user:
        return None
    try:
        user_doc = frappe.get_doc("User", user)
        return user_doc.get("whatsapp_number") or user_doc.get("mobile_no")
    except frappe.DoesNotExistError:
        return None

@frappe.whitelist()
def update_hourly_references():
    """
    Sync Hourly Production references from Monthly Production Planning and update slot keys.
    Only fills missing hour_slot values — never overwrites existing ones.
    """
    threshold = add_to_date(nowdate(), days=-30)
    recs = frappe.get_all(
        'Hourly Production',
        filters={'prod_date': ['>=', threshold]},
        fields=['name', 'prod_date', 'location', 'shift', 'shift_system', 'shift_num_hour']
    )

    updated_entries = []

    for r in recs:
        pd = getdate(r.prod_date)
        plans = frappe.get_all(
            'Monthly Production Planning',
            filters=[
                ['location', '=', r.location],
                ['prod_month_start_date', '<=', pd],
                ['prod_month_end_date', '>=', pd]
            ],
            fields=['name'],
            order_by='prod_month_start_date asc',
            limit_page_length=1
        )
        if not plans:
            continue

        # Get Monthly Production Planning document
        mpp = frappe.get_doc('Monthly Production Planning', plans[0].name)
        ref = next(
            (row.hourly_production_reference for row in mpp.month_prod_days if row.shift_start_date == pd),
            None
        )

        values = {}
        if ref:
            values['monthly_production_child_ref'] = ref

        try:
            # Calculate new hour_sort_key
            _, idx_str = r.shift_num_hour.split("-")
            idx = int(idx_str)
            base = (
                6 if r.shift in ("Day", "Morning") else
                14 if r.shift == "Afternoon" else
                18 if r.shift == "Night" and r.shift_system == "2x12Hour" else
                22
            )
            start = (base + (idx - 1)) % 24
            end = (start + 1) % 24
            values['hour_sort_key'] = idx

            # ✅ Only fill hour_slot if it's missing in the DB
            existing_slot = frappe.db.get_value('Hourly Production', r.name, 'hour_slot')
            if not existing_slot or existing_slot.strip() == "":
                values['hour_slot'] = f"{start:02d}:00-{end:02d}:00"

        except Exception as e:
            frappe.log_error(f"update_hourly_references error on {r.name}: {e}")

        # Update only if there’s something to change
        if values:
            frappe.db.set_value('Hourly Production', r.name, values)
            updated_entries.append(f"{r.name} → {values}")

    frappe.db.commit()

    if updated_entries:
        frappe.log_error(
            message=(
                f"update_hourly_references updated these Hourly Production records "
                f"(prod_date ≥ {threshold}):\n\n" + "\n".join(updated_entries)
            ),
            title="update_hourly_references"
        )

    return {'updated': len(updated_entries)}


