# Copyright (c) 2024, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PreUseHours(Document):
	pass

@frappe.whitelist()
def get_assets_by_location(location):
    # Fetch all assets based on location, ignoring ownership and permissions
    assets = frappe.get_all(
        'Asset',
        filters={'location': location},
        fields=['name as asset_name', 'item_name'],
        ignore_permissions=True
    )
    return assets