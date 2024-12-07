import frappe
from frappe.model.document import Document
from datetime import datetime, timedelta, date  # Ensure `date` is explicitly imported

class PreUseHours(Document):
    def before_save(self):
        # Fetch Monthly Production Planning data
        monthly_plan = get_monthly_production_plan(self.location, self.shift_date)
        if not monthly_plan:
            frappe.throw("No Monthly Production Planning data found for the selected location and shift_date.")

        # Validate Shift Date
        validate_shift_date(self, monthly_plan)

        # Validate Shift Sequence
        check_previous_record_sequence(self, monthly_plan)

        # Update Engine Hours End for the previous record
        update_previous_eng_hrs_end(self)

def get_monthly_production_plan(location, shift_date):
    """
    Fetch Monthly Production Planning data for the given location and shift_date.
    """
    if isinstance(shift_date, str):
        shift_date_obj = datetime.strptime(shift_date, "%Y-%m-%d")
    elif isinstance(shift_date, date):
        shift_date_obj = datetime.combine(shift_date, datetime.min.time())
    else:
        frappe.throw("Invalid shift_date format. It must be a valid date.")

    month_start = shift_date_obj.replace(day=1)
    month_end = (shift_date_obj.replace(day=1).replace(month=shift_date_obj.month + 1) - timedelta(days=1))

    return frappe.db.get_value(
        "Monthly Production Planning",
        {
            "location": location,
            "prod_month_end": [">=", month_end],
            "site_status": "Producing"
        },
        ["prod_month_end", "site_status", "shift_system", "name"],
        as_dict=True
    )

def validate_shift_date(doc, monthly_plan):
    """
    Validate general rules for shift_date.
    """
    shift_date = doc.shift_date
    if isinstance(shift_date, date):
        shift_date = shift_date.strftime("%Y-%m-%d")

    if datetime.strptime(shift_date, "%Y-%m-%d").weekday() == 6:
        frappe.throw("Shift Date cannot be a Sunday.")

    if monthly_plan["site_status"] != "Producing":
        frappe.throw("Pre-Use Hours can only be saved if the site's status is 'Producing'.")

def check_previous_record_sequence(doc, monthly_plan):
    """
    Check shift sequence and validate continuity.
    """
    previous_doc = get_previous_document(doc.location, doc.creation)
    if not previous_doc:
        return  # No previous record

    validate_next_shift_and_sequence(doc, previous_doc, monthly_plan)

from datetime import datetime, date

def validate_next_shift_and_sequence(doc, location, shift_date):
    """
    Validate shift system, fetch Monthly Production Planning data, and ensure correct shift sequence.
    """
    # Ensure shift_date is not None and in correct format
    if not shift_date:
        frappe.throw("Shift Date is required for validation.")

    # Convert shift_date to datetime object (dd-mm-yyyy format)
    if isinstance(shift_date, str):
        try:
            shift_date_obj = datetime.strptime(shift_date, "%d-%m-%Y")
        except ValueError:
            frappe.throw(f"Shift Date '{shift_date}' is invalid. Expected format: dd-mm-yyyy.")
    elif isinstance(shift_date, date):
        shift_date_obj = datetime.combine(shift_date, datetime.min.time())
    else:
        frappe.throw(f"Shift Date '{shift_date}' is invalid.")

    # Convert shift_date to yyyy-mm-dd string for database query
    shift_date_str = shift_date_obj.strftime("%Y-%m-%d")

    # Fetch Monthly Production Planning document where shift_date falls in the relevant month
    monthly_plan = frappe.db.sql("""
        SELECT name, shift_system, prod_month_end 
        FROM `tabMonthly Production Planning`
        WHERE location = %s
          AND %s BETWEEN DATE_ADD(prod_month_end, INTERVAL -DAY(prod_month_end)+1 DAY) AND prod_month_end
          AND site_status = 'Producing'
        LIMIT 1
    """, (location, shift_date_str), as_dict=True)

    if not monthly_plan:
        frappe.throw("No Monthly Production Planning data found for the selected location and shift_date.")

    monthly_plan = monthly_plan[0]  # Get the first match
    shift_system = monthly_plan.get("shift_system")
    if not shift_system:
        frappe.throw("Shift System is not defined in the Monthly Production Planning for this location.")

    # Fetch the previous Pre-Use Hours document
    previous_doc = frappe.db.get_value(
        "Pre-Use Hours",
        filters={"location": location, "creation": ["<", doc.creation]},
        fieldname="name",
        order_by="creation desc"
    )
    
    if not previous_doc:
        return  # No previous record to validate against

    previous_doc = frappe.get_doc("Pre-Use Hours", previous_doc)
    previous_shift = previous_doc.shift
    previous_shift_date = previous_doc.shift_date

    # Define shift sequence logic
    shift_sequence = {
        "2x12Hour": {"Day": "Night", "Night": "Day"},
        "3x8Hour": {"Morning": "Afternoon", "Afternoon": "Night", "Night": "Morning"}
    }

    # Determine the required shift based on the shift system
    required_shift = shift_sequence.get(shift_system, {}).get(previous_shift)
    if not required_shift:
        frappe.throw(f"Invalid shift system '{shift_system}' or previous shift '{previous_shift}'. Unable to determine the next shift.")

    # Validate current shift matches expected shift
    if doc.shift != required_shift:
        frappe.throw(f"Invalid shift sequence: Expected '{required_shift}' after '{previous_shift}'.")

    # Validate date continuity based on shift sequence
    previous_date = datetime.strptime(previous_shift_date, "%d-%m-%Y").date()
    current_date = shift_date_obj.date()

    if previous_shift == "Night" and doc.shift == "Morning":
        # Night → Morning transition must occur on the next day
        if current_date != previous_date + timedelta(days=1):
            frappe.throw("Morning shift must occur on the next day after a Night shift.")
    elif doc.shift in ["Afternoon", "Night"]:
        # Same-day shifts for Afternoon and Night
        if current_date != previous_date:
            frappe.throw(f"{doc.shift} shift must occur on the same date as the previous record.")
    else:
        # Validate same-day continuity for all other cases
        if current_date != previous_date:
            frappe.throw("Shift date continuity is invalid.")

def update_previous_eng_hrs_end(current_doc):
    """
    Update Engine Hours End for the previous record.
    """
    previous_doc_name = frappe.db.get_value(
        "Pre-Use Hours",
        filters={"location": current_doc.location, "creation": ["<", current_doc.creation]},
        fieldname="name",
        order_by="creation desc"
    )

    if previous_doc_name:
        previous_doc = frappe.get_doc("Pre-Use Hours", previous_doc_name)
        for prev_row in previous_doc.pre_use_assets:
            current_row = next(
                (row for row in current_doc.pre_use_assets if row.asset_name == prev_row.asset_name), None
            )
            if current_row:
                prev_row.eng_hrs_end = current_row.eng_hrs_start

        previous_doc.save(ignore_permissions=True)

@frappe.whitelist()
def get_previous_document(location, current_creation):
    """
    Fetch the last Pre-Use Hours document before the current creation timestamp.
    """
    previous_doc_name = frappe.db.get_value(
        "Pre-Use Hours",
        filters={"location": location, "creation": ["<", current_creation]},
        fieldname="name",
        order_by="creation desc"
    )
    if previous_doc_name:
        return frappe.get_doc("Pre-Use Hours", previous_doc_name)
    return None
