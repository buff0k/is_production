# Copyright (c) 2024, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class PreUseHours(Document):
    def before_save(self):
        # Automatically set Engine Hours End for the previous record
        update_previous_eng_hrs_end(self)

@frappe.whitelist()
def get_previous_document(location, current_creation):
    """
    Fetch the last created Pre-Use Hours document for the given location
    that was created before the current document's creation timestamp.
    """
    previous_doc_name = frappe.db.get_value(
        "Pre-Use Hours",
        filters={
            "location": location,
            "creation": ["<", current_creation]
        },
        fieldname="name",
        order_by="creation desc"
    )

    if previous_doc_name:
        return frappe.get_doc("Pre-Use Hours", previous_doc_name)
    return None

def update_previous_eng_hrs_end(current_doc):
    """
    Update the Engine Hours End for the previous Pre-Use Hours document
    based on the current document's Engine Hours Start.
    """
    # Fetch the last document created before the current document for the same location
    previous_doc_name = frappe.db.get_value(
        "Pre-Use Hours",
        filters={
            "location": current_doc.location,
            "creation": ["<", current_doc.creation]
        },
        fieldname="name",
        order_by="creation desc"
    )

    if previous_doc_name:
        previous_doc = frappe.get_doc("Pre-Use Hours", previous_doc_name)

        # Update eng_hrs_end for matching assets in the previous document
        for prev_row in previous_doc.pre_use_assets:
            current_row = next(
                (row for row in current_doc.pre_use_assets if row.asset_name == prev_row.asset_name),
                None
            )
            if current_row:
                prev_row.eng_hrs_end = current_row.eng_hrs_start

        previous_doc.save(ignore_permissions=True)