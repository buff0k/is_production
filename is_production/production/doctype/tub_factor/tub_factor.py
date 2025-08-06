# Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

from frappe.model.document import Document

class TubFactor(Document):
    def before_save(self):
        # Combine item_name and mat_type to set tub_factor_lookup
        if self.item_name and self.mat_type:
            self.tub_factor_lookup = f"{self.item_name}-{self.mat_type}"
        else:
            self.tub_factor_lookup = ""
