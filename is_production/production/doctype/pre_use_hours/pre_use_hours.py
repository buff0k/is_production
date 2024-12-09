import frappe
from frappe.model.document import Document
from datetime import datetime, timedelta, date
from calendar import monthrange

class PreUseHours(Document):
    def before_save(self):
        try:
            # Fetch Monthly Production Planning data
            monthly_plan = get_monthly_production_plan(self.location, self.shift_date)
            if not monthly_plan:
                frappe.throw("No Monthly Production Planning data found for the selected location and shift_date.")

            # Validate Shift Date
            validate_shift_date(self, monthly_plan)

            # Validate Shift Sequence
            check_previous_record_sequence(self, monthly_plan)

            # Update Engine Hours End for the previous record
            self.update_previous_eng_hrs_end()
        except Exception:
            frappe.log_error(title="Pre-Use Hours Validation Error")
            raise

    def update_previous_eng_hrs_end(self):
        """
        Update Engine Hours End for the previous record within `before_save`.
        """
        try:
            previous_doc_name = frappe.db.get_value(
                "Pre-Use Hours",
                filters={"location": self.location, "creation": ["<", self.creation]},
                fieldname="name",
                order_by="creation desc"
            )

            if previous_doc_name:
                previous_doc = frappe.get_doc("Pre-Use Hours", previous_doc_name)

                for prev_row in previous_doc.pre_use_assets:
                    # Match asset names to update engine hours
                    current_row = next(
                        (row for row in self.pre_use_assets if row.asset_name == prev_row.asset_name), None
                    )
                    if current_row:
                        prev_row.eng_hrs_end = current_row.eng_hrs_start

                previous_doc.save(ignore_permissions=True)
        except Exception:
            frappe.log_error(title="Engine Hours Update Error")
            raise


def normalize_to_db_date(date_input):
    """
    Normalize a date to database format (yyyy-mm-dd).
    """
    if isinstance(date_input, str):
        try:
            return datetime.strptime(date_input, "%d-%m-%Y").strftime("%Y-%m-%d")
        except ValueError:
            return datetime.strptime(date_input, "%Y-%m-%d").strftime("%Y-%m-%d")
    elif isinstance(date_input, date):
        return date_input.strftime("%Y-%m-%d")
    else:
        frappe.throw("Invalid date format.")


def normalize_to_ui_date(date_input):
    """
    Normalize a date to UI format (dd-mm-yyyy).
    """
    if isinstance(date_input, str):
        try:
            return datetime.strptime(date_input, "%Y-%m-%d").strftime("%d-%m-%Y")
        except ValueError:
            return datetime.strptime(date_input, "%d-%m-%Y").strftime("%d-%m-%Y")
    elif isinstance(date_input, date):
        return date_input.strftime("%d-%m-%Y")
    else:
        frappe.throw("Invalid date format.")


def get_monthly_production_plan(location, shift_date):
    """
    Fetch Monthly Production Planning data for the given location and shift_date.
    """
    try:
        normalized_date = normalize_to_db_date(shift_date)
        shift_date_obj = datetime.strptime(normalized_date, "%Y-%m-%d")

        month_start = shift_date_obj.replace(day=1)
        month_end = shift_date_obj.replace(day=monthrange(shift_date_obj.year, shift_date_obj.month)[1])

        query_result = frappe.db.sql(
            """
            SELECT name, location, prod_month_end, shift_system, site_status
            FROM `tabMonthly Production Planning`
            WHERE location = %(location)s
              AND prod_month_end BETWEEN %(month_start)s AND %(month_end)s
              AND site_status = 'Producing'
            LIMIT 1
            """,
            {"location": location, "month_start": month_start, "month_end": month_end},
            as_dict=True
        )

        return query_result[0] if query_result else None
    except Exception:
        frappe.log_error(title="SQL Execution Error")
        return None


def validate_shift_date(doc, monthly_plan):
    """
    Validate general rules for shift_date.
    """
    try:
        normalized_date = normalize_to_ui_date(doc.shift_date)

        # Ensure shift_date is not a Sunday
        if datetime.strptime(normalized_date, "%d-%m-%Y").weekday() == 6:
            frappe.throw("Shift Date cannot be a Sunday.")

        # Ensure site status is 'Producing'
        if monthly_plan["site_status"] != "Producing":
            frappe.throw("Pre-Use Hours can only be saved if the site's status is 'Producing'.")
    except Exception:
        frappe.log_error(title="Shift Date Validation Error")
        raise


def check_previous_record_sequence(doc, monthly_plan):
    """
    Check shift sequence and validate continuity.
    """
    try:
        previous_doc = get_previous_document(doc.location, doc.creation)
        if not previous_doc:
            return

        validate_next_shift_and_sequence(doc, previous_doc, monthly_plan)
    except Exception:
        frappe.log_error(title="Shift Sequence Validation Error")
        raise


def validate_next_shift_and_sequence(doc, previous_doc, monthly_plan):
    """
    Validate shift system and ensure correct shift sequence.
    """
    try:
        shift_system = monthly_plan.get("shift_system")
        if not shift_system:
            frappe.throw("Shift System is not defined in the Monthly Production Planning for this location.")

        shift_sequence = {
            "2x12Hour": {"Day": "Night", "Night": "Day"},
            "3x8Hour": {"Morning": "Afternoon", "Afternoon": "Night", "Night": "Morning"}
        }

        previous_shift = previous_doc.shift
        required_shift = shift_sequence.get(shift_system, {}).get(previous_shift)

        if not required_shift:
            frappe.throw(f"Invalid shift system '{shift_system}' or previous shift '{previous_shift}'.")

        if doc.shift != required_shift:
            frappe.throw(f"Invalid shift sequence: Expected '{required_shift}' after '{previous_shift}'.")

        previous_date = datetime.strptime(normalize_to_db_date(previous_doc.shift_date), "%Y-%m-%d").date()
        current_date = datetime.strptime(normalize_to_db_date(doc.shift_date), "%Y-%m-%d").date()

        if previous_shift == "Night" and required_shift in ["Day", "Morning"]:
            expected_date = previous_date + timedelta(days=1)
            if expected_date.weekday() == 6:  # Sunday
                expected_date += timedelta(days=1)

            if current_date != expected_date:
                frappe.throw(f"{required_shift} shift must occur on {expected_date.strftime('%d-%m-%Y')}.")

        elif doc.shift in ["Afternoon", "Night"] and current_date != previous_date:
            frappe.throw(f"{doc.shift} shift must occur on the same date as the previous record.")
    except Exception:
        frappe.log_error(title="Shift System Validation Error")
        raise


@frappe.whitelist()
def get_previous_document(location, current_creation):
    """
    Fetch the last Pre-Use Hours document before the current creation timestamp.
    """
    try:
        previous_doc_name = frappe.db.get_value(
            "Pre-Use Hours",
            filters={"location": location, "creation": ["<", current_creation]},
            fieldname="name",
            order_by="creation desc"
        )
        return frappe.get_doc("Pre-Use Hours", previous_doc_name) if previous_doc_name else None
    except Exception:
        frappe.log_error(title="Previous Document Fetch Error")
        return None
