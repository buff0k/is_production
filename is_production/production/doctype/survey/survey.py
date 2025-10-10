# Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Survey(Document):
    def validate(self):
        """Aggregate surveyed values into parent fields (BCM + Coal)."""
        self.calculate_totals()

    def calculate_totals(self):
        total_surveyed = 0
        total_ts = 0
        total_dozing = 0
        total_coal = 0

        for row in self.surveyed_values or []:
            bcm = row.bcm or 0
            mt = row.metric_tonnes or 0
            total_surveyed += bcm

            # Truck & Shovel BCMs
            if row.handling_method == "Truck and Shovel":
                total_ts += bcm
            elif row.handling_method == "Dozing":
                total_dozing += bcm

            # Coal → metric tonnes (using fieldname mat_type)
            if row.mat_type == "Coal":
                total_coal += mt

        # Set parent fields
        self.total_surveyed_bcm = total_surveyed
        self.total_ts_bcm = total_ts
        self.total_dozing_bcm = total_dozing
        self.total_surveyed_coal_tons = total_coal
