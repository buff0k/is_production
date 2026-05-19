import frappe
from frappe.model.document import Document


class GeoPitLayoutGeologyRun(Document):
    def validate(self):
        self.set_defaults()
        self.validate_source()

    def set_defaults(self):
        if not self.processing_status:
            self.processing_status = "Draft"

        if not self.run_status:
            self.run_status = "Draft"

        if self.geo_pit_layout and not self.geo_project:
            self.geo_project = frappe.db.get_value("Geo Pit Layout", self.geo_pit_layout, "geo_project")

        if not self.value_meaning:
            self.value_meaning = "Other"

    def validate_source(self):
        if not self.run_name:
            frappe.throw("Run Name is required.")

        if not self.geo_pit_layout:
            frappe.throw("Geo Pit Layout is required.")

        if not self.geo_project:
            frappe.throw("Geo Project is required.")

        if not self.source_type:
            frappe.throw("Source Type is required.")

        if self.source_type == "Geo Import Batch" and not self.geo_import_batch:
            frappe.throw("Geo Import Batch is required when Source Type is Geo Import Batch.")

        if self.source_type == "Geo Calculation Batch" and not self.geo_calculation_batch:
            frappe.throw("Geo Calculation Batch is required when Source Type is Geo Calculation Batch.")

        if self.rule_enabled:
            if not self.rule_operator:
                frappe.throw("Rule Operator is required when Rule Enabled is checked.")

            if self.rule_value in (None, ""):
                frappe.throw("Rule Value is required when Rule Enabled is checked.")

            if self.rule_operator in ("Between", "Outside") and self.rule_value_to in (None, ""):
                frappe.throw("Rule Value To is required for Between/Outside rules.")