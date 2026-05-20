import frappe
from frappe.model.document import Document


class MiningBlockMaterialCalculationBatch(Document):
    def validate(self):
        self.set_defaults()
        self.validate_links()

    def has_field(self, fieldname):
        return frappe.get_meta(self.doctype).has_field(fieldname)

    def get_safe(self, fieldname, default=None):
        if self.has_field(fieldname):
            return self.get(fieldname)
        return default

    def set_defaults(self):
        if self.has_field("status") and not self.get("status"):
            self.status = "Draft"

        if self.has_field("operation_type") and not self.get("operation_type"):
            self.operation_type = "Attach And Calculate"

        if self.has_field("create_missing_mining_blocks") and self.get("create_missing_mining_blocks") in (None, ""):
            self.create_missing_mining_blocks = 1

        if self.has_field("overwrite_existing") and self.get("overwrite_existing") in (None, ""):
            self.overwrite_existing = 0

        if self.has_field("update_block_status") and self.get("update_block_status") in (None, ""):
            self.update_block_status = 1

        if self.has_field("mineable_only") and self.get("mineable_only") in (None, ""):
            self.mineable_only = 0

        if self.has_field("progress_percent") and self.get("progress_percent") in (None, ""):
            self.progress_percent = 0

    def validate_links(self):
        if self.has_field("geo_project") and not self.get_safe("geo_project"):
            frappe.throw("Geo Project is required.")

        if self.has_field("geo_pit_layout") and not self.get_safe("geo_pit_layout"):
            frappe.throw("Geo Pit Layout is required.")

        if self.has_field("material_stack") and not self.get_safe("material_stack"):
            frappe.throw("Material Stack is required.")

        operation_type = self.get_safe("operation_type")

        if self.has_field("operation_type") and operation_type not in (
            "Attach Stack",
            "Calculate Values",
            "Attach And Calculate",
        ):
            frappe.throw("Invalid Operation Type.")