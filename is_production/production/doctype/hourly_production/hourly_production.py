from frappe.model.document import Document
import frappe
from frappe.utils import getdate, get_last_day
from frappe import _

class HourlyProduction(Document):
    pass

#import frappe
from frappe.utils import getdate, get_last_day

@frappe.whitelist()
def fetch_monthly_production_plan(location, prod_date):
    """
    Fetch the name of the Monthly Production Planning document for a given location and production date.
    """
    if location and prod_date:
        prod_date = getdate(prod_date)
        last_day_of_month = get_last_day(prod_date)
        monthly_plan_name = f"{last_day_of_month}-{location}"
        return frappe.get_value("Monthly Production Planning", {"name": monthly_plan_name}, "name")
    return None

@frappe.whitelist()
def get_hour_slot(shift, shift_num_hour):
    """
    Return the time slot based on the shift and shift_num_hour.
    Supports 2x12Hour and 3x8Hour systems.
    """
    shift_timings = {
        # 2x12Hour System
        **{f"Day-{i+1}": f"{6+i:02d}:00-{7+i:02d}:00" for i in range(12)},
        **{f"Night-{i+1}": f"{18+i:02d}:00-{19+i:02d}:00" if 18+i < 24 else f"{(18+i-24):02d}:00-{(19+i-24):02d}:00" for i in range(12)},
        # 3x8Hour System
        **{f"Morning-{i+1}": f"{6+i:02d}:00-{7+i:02d}:00" for i in range(8)},
        **{f"Afternoon-{i+1}": f"{14+i:02d}:00-{15+i:02d}:00" for i in range(8)},
        **{f"Night-{i+1}": f"{22+i:02d}:00-{23+i:02d}:00" if 22+i < 24 else f"{(22+i-24):02d}:00-{(23+i-24):02d}:00" for i in range(8)}
    }
    return shift_timings.get(shift_num_hour, None)

@frappe.whitelist()
def get_assets(doctype, txt, searchfield, start, page_len, filters):
    """
    Fetch assets filtered by location and asset_category with the correct structure.
    """
    # Parse filters (ensure JSON string is converted to dictionary)
    if isinstance(filters, str):
        filters = frappe.parse_json(filters)

    location = filters.get("location")
    asset_category = filters.get("asset_category")

    # Build the query
    query = """
        SELECT name, asset_name
        FROM `tabAsset`
        WHERE docstatus = 1
        AND location = %s
        AND asset_category = %s
        AND (name LIKE %s OR asset_name LIKE %s)
        LIMIT %s OFFSET %s
    """

    # Prepare parameters
    params = [
        location, asset_category, f"%{txt}%", f"%{txt}%", page_len, start
    ]

    # Execute the query
    result = frappe.db.sql(query, params)

    # Ensure the result includes the correct structure (name and description)
    return [{"value": row[0], "description": row[1]} for row in result]

@frappe.whitelist()
def get_tub_factor(item_name, mat_type):
    """
    Fetch tub factor and its linked document for a given item_name and mat_type.
    """
    if item_name and mat_type:
        return frappe.get_value("Tub Factor", {"item_name": item_name, "mat_type": mat_type}, ["tub_factor", "name"])
    return None





