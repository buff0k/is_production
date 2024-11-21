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

    validate_next_shift_in_sequence(doc, previous_doc, monthly_plan)

def validate_next_shift_in_sequence(doc, previous_doc, monthly_plan):
    """
    Ensure correct shift sequence and continuity of shift dates.
    """
    shift_sequence = {
        "2x12Hour": {"Day": "Night", "Night": "Day"},
        "3x8Hour": {"Morning": "Afternoon", "Afternoon": "Night", "Night": "Morning"}
    }
    
    required_shift = shift_sequence.get(monthly_plan["shift_system"], {}).get(previous_doc.shift)
    if not required_shift:
        frappe.throw(f"Invalid shift system or previous shift '{previous_doc.shift}'. Unable to determine the next shift.")

    if doc.shift != required_shift:
        frappe.throw(f"Invalid shift sequence: Expected '{required_shift}' after '{previous_doc.shift}'.")

    if doc.shift in ["Afternoon", "Night"]:
        if str(doc.shift_date) != str(previous_doc.shift_date):
            frappe.throw(f"{doc.shift} shift must occur on the same date as the previous record.")
    elif doc.shift == "Morning":
        previous_date = datetime.strptime(str(previous_doc.shift_date), "%Y-%m-%d").date()
        current_date = datetime.strptime(str(doc.shift_date), "%Y-%m-%d").date()
        if current_date != previous_date + timedelta(days=1):
            frappe.throw("Morning shift must occur on the next day.")

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
