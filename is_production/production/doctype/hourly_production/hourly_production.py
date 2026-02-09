# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from frappe.model.document import Document
import frappe
from frappe import _
from frappe.utils import getdate, add_to_date, nowdate


class HourlyProduction(Document):
    def validate(self):
        """
        General validation before save
        - v16-safe: ensure Link -> Asset fields store Asset.name (PK), not Plant No (asset.asset_name)
        - populate display-only Plant No fields (if you added them)
        - run your existing validations and calculations
        """
        self.normalize_asset_links_and_display_fields()
        self.validate_truck_loads()
        self.validate_dozer_production()
        self.before_save_logic()

    # -------------------------------------------------------------------------
    # Asset link normalization + Plant No display population (v16 migration-safe)
    # -------------------------------------------------------------------------
    def normalize_asset_links_and_display_fields(self):
        """
        Ensure Asset Link fields store Asset.name, not Asset.asset_name (Plant No).
        Also populates display-only Data fields (if you added them) such as:
          - Truck Loads: truck_plant_no, excavator_plant_no
          - Dozer Production: dozer_plant_no
        """

        def _fetch_assets(values):
            values = [v for v in set(values or []) if v]
            if not values:
                return {"by_name": {}, "by_code": {}}

            # match by Asset.name
            by_name = {
                d["name"]: d
                for d in frappe.get_all(
                    "Asset",
                    filters={"name": ["in", values]},
                    fields=["name", "asset_name"],
                )
            }

            # match by Asset.asset_name (Plant No / code)
            by_code = {
                d["asset_name"]: d
                for d in frappe.get_all(
                    "Asset",
                    filters={"asset_name": ["in", values]},
                    fields=["name", "asset_name"],
                )
                if d.get("asset_name")
            }

            return {"by_name": by_name, "by_code": by_code}

        # -------------------------
        # Truck Loads child table
        # -------------------------
        truck_vals = []
        excav_vals = []
        for row in (getattr(self, "truck_loads", None) or []):
            if getattr(row, "asset_name_truck", None):
                truck_vals.append(row.asset_name_truck)
            if getattr(row, "asset_name_shoval", None):
                excav_vals.append(row.asset_name_shoval)

        truck_maps = _fetch_assets(truck_vals)
        excav_maps = _fetch_assets(excav_vals)

        for row in (getattr(self, "truck_loads", None) or []):
            # Normalize truck link
            v = getattr(row, "asset_name_truck", None)
            if v and v not in truck_maps["by_name"] and v in truck_maps["by_code"]:
                row.asset_name_truck = truck_maps["by_code"][v]["name"]

            # Normalize excavator link
            v = getattr(row, "asset_name_shoval", None)
            if v and v not in excav_maps["by_name"] and v in excav_maps["by_code"]:
                row.asset_name_shoval = excav_maps["by_code"][v]["name"]

            # Populate display Plant No fields (if present)
            truck_name = getattr(row, "asset_name_truck", None)
            if hasattr(row, "truck_plant_no") and truck_name and truck_name in truck_maps["by_name"]:
                row.truck_plant_no = truck_maps["by_name"][truck_name].get("asset_name") or ""

            excav_name = getattr(row, "asset_name_shoval", None)
            if hasattr(row, "excavator_plant_no") and excav_name and excav_name in excav_maps["by_name"]:
                row.excavator_plant_no = excav_maps["by_name"][excav_name].get("asset_name") or ""

        # -------------------------
        # Dozer Production child table
        # -------------------------
        dozer_vals = [
            r.asset_name
            for r in (getattr(self, "dozer_production", None) or [])
            if getattr(r, "asset_name", None)
        ]
        dozer_maps = _fetch_assets(dozer_vals)

        for row in (getattr(self, "dozer_production", None) or []):
            v = getattr(row, "asset_name", None)
            if v and v not in dozer_maps["by_name"] and v in dozer_maps["by_code"]:
                row.asset_name = dozer_maps["by_code"][v]["name"]

            if hasattr(row, "dozer_plant_no") and row.asset_name and row.asset_name in dozer_maps["by_name"]:
                row.dozer_plant_no = dozer_maps["by_name"][row.asset_name].get("asset_name") or ""

    # -------------------------------------------------------------------------
    # Validations (these MUST be methods on the class)
    # -------------------------------------------------------------------------
    def validate_truck_loads(self):
        for row in (getattr(self, "truck_loads", None) or []):
            if (row.loads or 0) > 0:
                if not row.geo_mat_layer_truck:
                    frappe.throw(
                        _("Row {0}: Please select a Geo Material Layer for truck {1}").format(
                            row.idx, row.asset_name_truck or ""
                        )
                    )
                if not row.mining_areas_trucks:
                    frappe.throw(
                        _("Row {0}: Please select a Mining Area for truck {1}").format(
                            row.idx, row.asset_name_truck or ""
                        )
                    )

    def validate_dozer_production(self):
        for row in (getattr(self, "dozer_production", None) or []):
            if (row.bcm_hour or 0) > 0:
                if not row.dozer_geo_mat_layer:
                    frappe.throw(
                        _("Row {0}: Please select a Geo Material Layer for dozer {1}").format(
                            row.idx, row.asset_name or ""
                        )
                    )
                if not row.mining_areas_dozer_child:
                    frappe.throw(
                        _("Row {0}: Please select a Mining Area for dozer {1}").format(
                            row.idx, row.asset_name or ""
                        )
                    )

    # -------------------------------------------------------------------------
    # BEFORE SAVE LOGIC (your existing calculations, kept intact)
    # -------------------------------------------------------------------------
    def before_save_logic(self):
        """
        Ensures all child tables and derived fields are updated before saving
        the parent document. Also validates Dozer Production entries based on
        the Dozer Service selected. Always recalculates hour_sort_key and
        hour_slot from shift_num_hour.
        """

        # Coal ton calculation
        if self.total_coal_bcm is not None:
            self.coal_tons_total = self.total_coal_bcm * 1.5
        else:
            self.coal_tons_total = 0

        # --- Truck Loads Calculations ---
        total_softs_bcm = total_hards_bcm = total_coal_bcm = total_ts_bcm = 0.0
        num_prod_trucks = 0

        if hasattr(self, "truck_loads"):
            for row in self.truck_loads:
                if row.geo_mat_layer_truck and not row.mat_type:
                    mpp = frappe.get_doc("Monthly Production Planning", self.month_prod_planning)
                    for geo_row in mpp.geo_mat_layer:
                        if geo_row.geo_ref_description == row.geo_mat_layer_truck:
                            row.mat_type = geo_row.custom_material_type
                            break

        if hasattr(self, "truck_loads"):
            for row in self.truck_loads:
                # SPECIAL RULE FOR KRIEL REHABILITATION
                if self.location == "Kriel Rehabilitation":
                    row.tub_factor = 16
                    row.tub_factor_doc_lookup = None
                else:
                    tf = frappe.get_all(
                        "Tub Factor",
                        filters={"item_name": row.item_name, "mat_type": row.mat_type},
                        fields=["name", "tub_factor"],
                        limit=1,
                    )
                    if tf:
                        row.tub_factor_doc_lookup = tf[0]["name"]
                        row.tub_factor = tf[0]["tub_factor"]
                    else:
                        row.tub_factor_doc_lookup = None
                        row.tub_factor = None

                # BCM Calculation
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
        allowed_bcm_values = [0, 100, 110, 120, 130, 140, 150, 180, 190, 200]

        if hasattr(self, "dozer_production"):
            for row in self.dozer_production:
                if row.dozer_service in ["No Dozing", "Tip Dozing", "Levelling"]:
                    if row.bcm_hour != 0:
                        frappe.throw(
                            _("For Dozer Service '{0}', only a BCM in Hour value of 0 is allowed.").format(
                                row.dozer_service
                            )
                        )
                elif row.dozer_service in ["Production Dozing-50m", "Production Dozing-100m"]:
                    if row.bcm_hour not in allowed_bcm_values:
                        frappe.throw(
                            _("For Dozer Service '{0}', BCM in Hour value must be one of {1}.").format(
                                row.dozer_service, allowed_bcm_values
                            )
                        )
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

        # --- Recompute hour_sort_key & hour_slot ---
        if self.shift_num_hour:
            try:
                _, idx_str = self.shift_num_hour.split("-", 1)
                idx = int(idx_str)

                self.hour_sort_key = idx
                base = (
                    6
                    if self.shift in ("Day", "Morning")
                    else 14
                    if self.shift == "Afternoon"
                    else 18
                    if self.shift == "Night" and self.shift_system == "2x12Hour"
                    else 22
                )
                start = (base + (idx - 1)) % 24
                end = (start + 1) % 24
                self.hour_slot = f"{start}:00-{end}:00"
            except (ValueError, IndexError):
                self.hour_sort_key = None
                self.hour_slot = None

    def calculate_day_total_bcm(self):
        """Calculate and set the day_total_bcm from all hourly entries for this location and date"""
        if not self.prod_date or not self.location:
            return

        day_total = frappe.db.sql(
            """
            SELECT SUM(hour_total_bcm)
            FROM `tabHourly Production`
            WHERE location = %s
              AND prod_date = %s
              AND docstatus < 2
              AND name != %s
            """,
            (self.location, self.prod_date, self.name),
            as_list=True,
        )

        current_hour_total = self.hour_total_bcm or 0
        self.day_total_bcm = (day_total[0][0] or 0) + current_hour_total

    def before_print(self, print_settings):
        if getattr(self, "month_prod_planning", None):
            frappe.get_attr(
                "is_production.production.doctype.monthly_production_planning."
                "monthly_production_planning.update_mtd_production"
            )(name=self.month_prod_planning)

            mpp = frappe.get_doc("Monthly Production Planning", self.month_prod_planning)
            for field in [
                "monthly_target_bcm",
                "target_bcm_day",
                "target_bcm_hour",
                "month_act_ts_bcm_tallies",
                "month_act_dozing_bcm_tallies",
                "monthly_act_tally_survey_variance",
                "month_actual_bcm",
                "mtd_bcm_day",
                "mtd_bcm_hour",
                "month_forecated_bcm",
            ]:
                setattr(self, field, getattr(mpp, field))

    @frappe.whitelist()
    def send_whatsapp_notification(self):
        try:
            notification = frappe.get_doc("WhatsApp Notification", "Hourly Production Indiv.")
            if notification.disabled:
                frappe.msgprint("WhatsApp notification is disabled", indicator="orange")
                return
            notification.send_template_message(self)
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "WhatsApp Notification Error")
            frappe.msgprint(f"Failed to send WhatsApp notification: {str(e)}", indicator="red")

    def on_update(self):
        if not self.month_prod_planning:
            return

        try:
            frappe.get_attr(
                "is_production.production.doctype.monthly_production_planning."
                "monthly_production_planning.update_mtd_production"
            )(name=self.month_prod_planning)

            frappe.msgprint(_("Month-to-Date Production updated automatically."), alert=True, indicator="green")
        except Exception as e:
            frappe.log_error(
                message=f"Auto MTD update failed for Hourly Production {self.name}: {e}",
                title="Hourly Production Auto MTD Update",
            )


@frappe.whitelist()
def get_user_whatsapp_number(user):
    if not user:
        return None
    try:
        user_doc = frappe.get_doc("User", user)
        return user_doc.get("whatsapp_number") or user_doc.get("mobile_no")
    except frappe.DoesNotExistError:
        return None


@frappe.whitelist()
def update_hourly_references():
    threshold = add_to_date(nowdate(), days=-30)
    recs = frappe.get_all(
        "Hourly Production",
        filters={"prod_date": [">=", threshold]},
        fields=["name", "prod_date", "location", "shift", "shift_system", "shift_num_hour"],
    )

    updated_entries = []
    for r in recs:
        pd = getdate(r.prod_date)
        plans = frappe.get_all(
            "Monthly Production Planning",
            filters=[
                ["location", "=", r.location],
                ["prod_month_start_date", "<=", pd],
                ["prod_month_end_date", ">=", pd],
            ],
            fields=["name"],
            order_by="prod_month_start_date asc",
            limit_page_length=1,
        )
        if not plans:
            continue

        mpp = frappe.get_doc("Monthly Production Planning", plans[0].name)
        ref = next(
            (row.hourly_production_reference for row in mpp.month_prod_days if row.shift_start_date == pd),
            None,
        )

        values = {}
        if ref:
            values["monthly_production_child_ref"] = ref
        try:
            _, idx_str = r.shift_num_hour.split("-")
            idx = int(idx_str)
            base = (
                6
                if r.shift in ("Day", "Morning")
                else 14
                if r.shift == "Afternoon"
                else 18
                if r.shift == "Night" and r.shift_system == "2x12Hour"
                else 22
            )
            start = (base + (idx - 1)) % 24
            end = (start + 1) % 24
            values["hour_sort_key"] = idx
            values["hour_slot"] = f"{start}:00-{end}:00"
        except Exception:
            pass

        if values:
            frappe.db.set_value("Hourly Production", r.name, values)
            updated_entries.append(f"{r.name} → {values}")

    frappe.db.commit()

    if updated_entries:
        frappe.log_error(
            message=(
                f"update_hourly_references synced the following Hourly Production records\n"
                f"(prod_date ≥ {threshold}):\n\n" + "\n".join(updated_entries)
            ),
            title="update_hourly_references",
        )

    return {"updated": len(updated_entries)}


@frappe.whitelist()
def get_day_total_bcm(location, prod_date, exclude_name=None):
    if not location or not prod_date:
        return 0

    cond = ""
    params = [location, prod_date]

    if exclude_name:
        cond = " AND name != %s"
        params.append(exclude_name)

    res = frappe.db.sql(
        f"""
        SELECT COALESCE(SUM(hour_total_bcm), 0)
        FROM `tabHourly Production`
        WHERE location = %s
          AND prod_date = %s
          AND docstatus < 2
          {cond}
        """,
        params,
    )
    return res[0][0] if res else 0
