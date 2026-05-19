import frappe
from frappe.model.document import Document


class GeoLayoutGenerationBatch(Document):
    def validate(self):
        self.set_defaults()
        self.validate_links()

    def set_defaults(self):
        if not self.status:
            self.status = "Draft"

        if self.clear_existing_blocks in (None, ""):
            self.clear_existing_blocks = 1

        if self.overwrite_existing in (None, ""):
            self.overwrite_existing = 1

    def validate_links(self):
        if not self.geo_project:
            frappe.throw("Geo Project is required.")

        if not self.geo_pit_layout:
            frappe.throw("Geo Pit Layout is required.")

        if not self.pit_outline_batch:
            frappe.throw("Pit Outline Batch is required.")