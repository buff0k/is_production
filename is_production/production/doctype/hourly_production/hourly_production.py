# Copyright (c) 2024, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

from frappe.model.document import Document
import frappe
from frappe.utils import getdate, get_last_day

class HourlyProduction(Document):
    pass


@frappe.whitelist()
def fetch_monthly_production_plan(location, prod_date):
    """
    Fetch the Monthly Production Planning document based on the last day of the month and location.
    """
    if location and prod_date:
        prod_date = getdate(prod_date)
        last_day_of_month = get_last_day(prod_date)
        monthly_plan_name = f"{last_day_of_month}-{location}"
        
        # Fetch the document name
        plan = frappe.get_value("Monthly Production Planning", {"name": monthly_plan_name}, "name")
        return plan

    return None


@frappe.whitelist()
def get_hour_slot(shift, shift_num_hour):
    """
    Return the time slot based on the shift and shift_num_hour.
    """
    hour_slots = {
        "A-1": "06:00-07:00", "A-2": "07:00-08:00", "A-3": "08:00-09:00",
        "A-4": "09:00-10:00", "A-5": "10:00-11:00", "A-6": "11:00-12:00",
        "A-7": "12:00-13:00", "A-8": "13:00-14:00", "A-9": "14:00-15:00",
        "A-10": "15:00-16:00", "A-11": "16:00-17:00", "A-12": "17:00-18:00",
        "B-1": "18:00-19:00", "B-2": "19:00-20:00", "B-3": "20:00-21:00",
        "B-4": "21:00-22:00", "B-5": "22:00-23:00", "B-6": "23:00-00:00",
        "B-7": "00:00-01:00", "B-8": "01:00-02:00", "B-9": "02:00-03:00",
        "B-10": "03:00-04:00", "B-11": "04:00-05:00", "B-12": "05:00-06:00"
    }

    slot = hour_slots.get(f"{shift}-{shift_num_hour}", None)
    if not slot:
        frappe.throw(_("Invalid shift or shift number hour selected."))
    
    return slot
