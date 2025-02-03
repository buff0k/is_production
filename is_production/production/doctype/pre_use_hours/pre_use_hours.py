import frappe
from frappe.model.document import Document
from datetime import datetime, timedelta, date

class PreUseHours(Document):
    def before_save(self):
        """
        Called before saving the 'Pre-Use Hours' document.
        Performs:
          - Monthly Production Planning check
          - Shift date validation (not Sunday, site is Producing, etc.)
          - Shift sequence check (ensure correct shift order)
          - Update engine hours on the previous record
        """
        try:
            # Fetch the relevant Monthly Production Planning record
            monthly_plan = get_monthly_production_plan(self.location, self.shift_date)
            if not monthly_plan:
                frappe.throw(
                    "No Monthly Production Planning data found for the selected location and shift date."
                )

            # Validate the shift date (e.g. no Sundays, site must be Producing)
            validate_shift_date(self, monthly_plan)

            # Validate shift sequence continuity with the previous document
            check_previous_record_sequence(self, monthly_plan)

            # Update Engine Hours End for the previous record
            self.update_previous_eng_hrs_end()

        except Exception:
            frappe.log_error(title="Pre-Use Hours Validation Error")
            raise

    def update_previous_eng_hrs_end(self):
        """
        Update the 'Engine Hours End' (eng_hrs_end) in the previously created 'Pre-Use Hours' record,
        matching assets by name, so that eng_hrs_end matches the current eng_hrs_start.
        """
        try:
            previous_doc_name = frappe.db.get_value(
                "Pre-Use Hours",
                filters={
                    "location": self.location,
                    "creation": ["<", self.creation]
                },
                fieldname="name",
                order_by="creation desc"
            )

            if previous_doc_name:
                previous_doc = frappe.get_doc("Pre-Use Hours", previous_doc_name)

                for prev_row in previous_doc.pre_use_assets:
                    # Find matching asset in current doc
                    current_row = next(
                        (row for row in self.pre_use_assets if row.asset_name == prev_row.asset_name),
                        None
                    )
                    if current_row:
                        # Update the previous doc's eng_hrs_end
                        prev_row.eng_hrs_end = current_row.eng_hrs_start

                previous_doc.save(ignore_permissions=True)

        except Exception:
            frappe.log_error(title="Engine Hours Update Error")
            raise


def normalize_to_db_date(date_input):
    """
    Convert various date formats to a standard DB format (YYYY-MM-DD).
    """
    if isinstance(date_input, str):
        for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_input, fmt).strftime("%Y-%m-%d")
            except ValueError:
                pass
        frappe.throw("Invalid date format string for DB conversion.")
    elif isinstance(date_input, date):
        return date_input.strftime("%Y-%m-%d")
    else:
        frappe.throw("Invalid date format type.")


def normalize_to_ui_date(date_input):
    """
    Convert various date formats to a standard UI format (DD-MM-YYYY).
    """
    if isinstance(date_input, str):
        for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(date_input, fmt).strftime("%d-%m-%Y")
            except ValueError:
                pass
        frappe.throw("Invalid date format string for UI conversion.")
    elif isinstance(date_input, date):
        return date_input.strftime("%d-%m-%Y")
    else:
        frappe.throw("Invalid date format type.")


def get_monthly_production_plan(location, shift_date):
    """
    Fetch a single Monthly Production Planning record where:
      - location matches
      - site_status = 'Producing'
      - shift_date is between prod_month_start_date and prod_month_end_date (inclusive)
    """
    try:
        normalized_date = normalize_to_db_date(shift_date)
        shift_date_obj = datetime.strptime(normalized_date, "%Y-%m-%d")

        query_result = frappe.db.sql(
            """
            SELECT
                name,
                location,
                prod_month_start_date,
                prod_month_end_date,
                shift_system,
                site_status
            FROM `tabMonthly Production Planning`
            WHERE location = %(location)s
              AND site_status = 'Producing'
              AND %(shift_date)s BETWEEN prod_month_start_date AND prod_month_end_date
            LIMIT 1
            """,
            {"location": location, "shift_date": shift_date_obj},
            as_dict=True
        )

        return query_result[0] if query_result else None

    except Exception:
        frappe.log_error(title="SQL Execution Error")
        return None


def validate_shift_date(doc, monthly_plan):
    """
    Validate that the shift_date is not a Sunday and that the site is Producing.
    (Any additional date rules can be added here.)
    """
    try:
        # Check if shift_date is Sunday
        normalized_date = normalize_to_ui_date(doc.shift_date)
        if datetime.strptime(normalized_date, "%d-%m-%Y").weekday() == 6:
            frappe.throw("Shift Date cannot be a Sunday.")

        # Check site_status
        if monthly_plan["site_status"] != "Producing":
            frappe.throw("Pre-Use Hours can only be saved if the site's status is 'Producing'.")

    except Exception:
        frappe.log_error(title="Shift Date Validation Error")
        raise


def check_previous_record_sequence(doc, monthly_plan):
    """
    Check if there is a previous 'Pre-Use Hours' record and validate
    shift continuity based on the shift_system from Monthly Production Planning.
    """
    try:
        previous_doc = get_previous_document(doc.location, doc.creation)
        if not previous_doc:
            return  # No previous record, no sequence checks needed

        validate_next_shift_and_sequence(doc, previous_doc, monthly_plan)

    except Exception:
        frappe.log_error(title="Shift Sequence Validation Error")
        raise


def validate_next_shift_and_sequence(doc, previous_doc, monthly_plan):
    """
    Ensure that the next shift is correct based on the shift_system.
    For example, in a 2x12Hour system, after Day comes Night, etc.
    Also check if the shift_date transitions correctly from the previous record.
    """
    try:
        shift_system = monthly_plan.get("shift_system")
        if not shift_system:
            frappe.throw(
                "Shift System is not defined in the Monthly Production Planning for this location."
            )

        # Define valid sequences
        shift_sequence = {
            "2x12Hour": {"Day": "Night", "Night": "Day"},
            "3x8Hour": {"Morning": "Afternoon", "Afternoon": "Night", "Night": "Morning"},
        }

        previous_shift = previous_doc.shift
        required_shift = shift_sequence.get(shift_system, {}).get(previous_shift)

        if not required_shift:
            frappe.throw(
                f"Invalid shift system '{shift_system}' or unrecognized previous shift '{previous_shift}'."
            )

        if doc.shift != required_shift:
            frappe.throw(
                f"Invalid shift sequence: Expected '{required_shift}' after '{previous_shift}'."
            )

        # Check date transition logic
        prev_date = datetime.strptime(normalize_to_db_date(previous_doc.shift_date), "%Y-%m-%d").date()
        current_date = datetime.strptime(normalize_to_db_date(doc.shift_date), "%Y-%m-%d").date()

        # If previous shift = Night and new shift = Day/Morning, typically the date increments by 1
        if previous_shift == "Night" and required_shift in ["Day", "Morning"]:
            expected_date = prev_date + timedelta(days=1)

            # If the next day is a Sunday, your custom rule might skip to Monday:
            if expected_date.weekday() == 6:  # Sunday
                expected_date += timedelta(days=1)

            if current_date != expected_date:
                frappe.throw(
                    f"{required_shift} shift must occur on {expected_date.strftime('%d-%m-%Y')}."
                )

        # For 3x8Hour system: if the shift is Afternoon or Night, it happens on the same calendar date
        elif doc.shift in ["Afternoon", "Night"] and current_date != prev_date:
            frappe.throw(
                f"{doc.shift} shift must occur on the same date as the previous record."
            )

    except Exception:
        frappe.log_error(title="Shift System Validation Error")
        raise


@frappe.whitelist()
def get_previous_document(location, current_creation):
    """
    Return the last 'Pre-Use Hours' document before this one (by creation timestamp).
    """
    try:
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

    except Exception:
        frappe.log_error(title="Previous Document Fetch Error")
        return None
