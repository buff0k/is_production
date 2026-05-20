import frappe
from frappe.model.document import Document


class MiningBlockGenerationBatch(Document):
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

        if self.has_field("require_final") and self.get("require_final") in (None, ""):
            self.require_final = 1

        if self.has_field("overwrite_existing") and self.get("overwrite_existing") in (None, ""):
            self.overwrite_existing = 0

        if self.has_field("update_existing") and self.get("update_existing") in (None, ""):
            self.update_existing = 1

        if self.has_field("progress_percent") and self.get("progress_percent") in (None, ""):
            self.progress_percent = 0

    def validate_links(self):
        if self.has_field("geo_project") and not self.get_safe("geo_project"):
            frappe.throw("Geo Project is required.")

        if self.has_field("geo_pit_layout") and not self.get_safe("geo_pit_layout"):
            frappe.throw("Geo Pit Layout is required.")