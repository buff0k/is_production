# Copyright (c) 2026, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ProductionDashboardSetup(Document):
    pass


@frappe.whitelist()
def get_site_colour_map():
    """
    Return the global production dashboard site colour mapping.

    This method intentionally exposes only the safe dashboard colour map:
        {
            "<Location>": "<Colour>"
        }

    The browser should call this instead of reading the singleton directly,
    because normal dashboard users may not have read permission on
    Production Dashboard Setup.
    """
    colour_map = {}

    try:
        setup = frappe.get_single("Production Dashboard Setup")
    except Exception:
        frappe.log_error(
            title="Production Dashboard Setup Colour Map Error",
            message=frappe.get_traceback(),
        )
        return colour_map

    for row in setup.get("site_colour_mapping") or []:
        location = (row.location or "").strip()
        colour = (row.colour or "").strip()

        if location and colour:
            colour_map[location] = colour

    return colour_map