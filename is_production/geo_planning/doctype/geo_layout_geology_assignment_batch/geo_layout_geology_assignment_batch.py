import frappe
from frappe.model.document import Document


class GeoLayoutGeologyAssignmentBatch(Document):
    def validate(self):
        self.set_defaults()
        self.validate_links()

    def has_field(self, fieldname):
        return frappe.get_meta(self.doctype).has_field(fieldname)

    def get_safe(self, fieldname, default=None):
        if self.has_field(fieldname):
            return self.get(fieldname)
        return default

    def set_safe(self, fieldname, value):
        if self.has_field(fieldname):
            self.set(fieldname, value)

    def set_defaults(self):
        if self.has_field("status") and not self.get("status"):
            self.status = "Draft"

        if self.has_field("clear_existing_results") and self.get("clear_existing_results") in (None, ""):
            self.clear_existing_results = 0

        if self.has_field("overwrite_existing") and self.get("overwrite_existing") in (None, ""):
            self.overwrite_existing = 1

        if self.has_field("progress_percent") and self.get("progress_percent") in (None, ""):
            self.progress_percent = 0

    def validate_links(self):
        geo_project = self.get_safe("geo_project")
        geo_pit_layout = self.get_safe("geo_pit_layout")
        geology_run = self.get_safe("geology_run")
        source_type = self.get_safe("source_type")
        geo_import_batch = self.get_safe("geo_import_batch")
        geo_calculation_batch = self.get_safe("geo_calculation_batch")

        if self.has_field("geo_project") and not geo_project:
            frappe.throw("Geo Project is required.")

        if self.has_field("geo_pit_layout") and not geo_pit_layout:
            frappe.throw("Geo Pit Layout is required.")

        if self.has_field("geology_run") and not geology_run:
            frappe.throw("Geology Run is required.")

        if self.has_field("source_type") and not source_type:
            frappe.throw("Source Type is required.")

        if source_type == "Geo Import Batch" and self.has_field("geo_import_batch") and not geo_import_batch:
            frappe.throw("Geo Import Batch is required for Geo Import Batch assignments.")

        if source_type == "Geo Calculation Batch" and self.has_field("geo_calculation_batch") and not geo_calculation_batch:
            frappe.throw("Geo Calculation Batch is required for Geo Calculation Batch assignments.")