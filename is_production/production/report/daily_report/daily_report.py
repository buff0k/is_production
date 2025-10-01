import frappe
from frappe import _
from frappe.model.document import Document
from datetime import datetime, timedelta, date

class PreUseHours(Document):
    def before_save(self):
        """
        Called before saving the 'Pre-Use Hours' document.
        Performs integrity checks on the current and updates the previous record.
        """
        try:
            monthly_plan = get_monthly_production_plan(self.location, self.shift_date)
            if not monthly_plan:
                frappe.throw(
                    "No Monthly Production Planning data found for the selected location and shift date."
                )

            validate_shift_date(self, monthly_plan)
            check_previous_record_sequence(self, monthly_plan)

            # Run integrity on current
            self.evaluate_data_integrity()
            # Then update previous and merge summaries
            self.update_previous_eng_hrs_end()

        except Exception:
            frappe.log_error(title="Pre-Use Hours Validation Error")
            raise

    def update_previous_eng_hrs_end(self):
        """
        1) Copy eng_hrs_end/working_hours into the previous record via db.set_value
        2) Re-run its integrity check in‑memory
        3) Persist its child & parent changes, reload previous doc in any open form
        4) Render a two‑column Current vs Previous summary with nav buttons at top
           and a legend at the bottom.
        """
        try:
            # 1) find previous record
            prev_name = frappe.db.get_value(
                "Pre-Use Hours",
                {"location": self.location, "creation": ["<", self.creation]},
                "name",
                order_by="creation desc"
            )
            if not prev_name:
                return

            prev = frappe.get_doc("Pre-Use Hours", prev_name)

            # 2) copy engine‑end into its child rows & persist
            for pr in prev.pre_use_assets:
                cr = next((r for r in self.pre_use_assets if r.asset_name == pr.asset_name), None)
                if cr and cr.eng_hrs_start is not None:
                    pr.eng_hrs_end = cr.eng_hrs_start
                    if pr.eng_hrs_start is not None:
                        pr.working_hours = round(pr.eng_hrs_end - pr.eng_hrs_start, 1)
                    frappe.db.set_value(
                        "Pre-use Assets", pr.name,
                        {
                            "eng_hrs_end": pr.eng_hrs_end,
                            "working_hours": pr.working_hours
                        },
                        update_modified=False
                    )

            # 3) re‑evaluate previous’s integrity, persist its summary & indicator
            prev.evaluate_data_integrity()
            frappe.db.set_value(
                "Pre-Use Hours", prev.name,
                {
                    "data_integrity_summary": prev.data_integrity_summary,
                    "data_integ_indicator": prev.data_integ_indicator
                },
                update_modified=False
            )

            # 4) commit and trigger any open form of that record to reload
            frappe.db.commit()
            frappe.publish_realtime("preuse:reload_doc", {
                "doctype": "Pre-Use Hours", "name": prev.name
            })

            # 5) build nav buttons, two‑column summaries and legend
            nav_buttons = """
                <div style="margin-bottom:10px;">
                  <button class="btn btn-sm btn-secondary" id="prev_record_top">⬅️ Previous</button>
                  <button class="btn btn-sm btn-secondary" id="next_record_top">Next ➡️</button>
                </div>
            """

            # use whatever evaluate_data_integrity already set on this doc
            current_html = self.data_integrity_summary or "<p><b>No issues in current shift.</b></p>"
            previous_html = prev.data_integrity_summary or "<p><b>No issues in previous shift.</b></p>"

            legend = """
                <hr>
                <h5>Legend & Help</h5>
                <p>
                  <b>🔴 Red (Critical):</b> Negative or unrealistic working hours (&gt;12 hrs).<br>
                  <b>🟠 Yellow (Warning):</b> Missing data or zero hours.<br>
                  <b>🟢 Green (Valid):</b> All data checks passed.
                </p>
                <p style="color:gray; font-size:90%;">🔁 Save to refresh this summary.</p>
            """

            merged = f"""
                {nav_buttons}
                <div style="display:flex; gap:20px;">
                  <div style="flex:1; border-right:1px solid #ddd; padding-right:10px;">
                    <h4>Current Shift Integrity</h4>
                    {current_html}
                  </div>
                  <div style="flex:1; padding-left:10px;">
                    <h4>Previous Shift Integrity</h4>
                    {previous_html}
                  </div>
                </div>
                {legend}
            """

            # 6) overwrite this doc’s summary field & mark dirty
            self.set("data_integrity_summary", merged)
            # leave data_integ_indicator alone (it still reflects current-shift status)
            self.flags.dirty = True

        except Exception as e:
            frappe.log_error(title="Engine Hours Update Error", message=str(e))
            frappe.throw(_("Error updating previous engine hours: {0}").format(e))


    def evaluate_data_integrity(self):
        errors = []
        warning_count = 0
        error_count = 0

        for idx, row in enumerate(self.get("pre_use_assets", []), start=1):
            row_issues = []
            eng_hrs_start = row.eng_hrs_start
            eng_hrs_end = row.eng_hrs_end
            working_hours = None

            if eng_hrs_start is None:
                row_issues.append("❗ <span style='color:orange;'>Missing Engine Hours Start</span>")
            if eng_hrs_end is None:
                row_issues.append("❗ <span style='color:orange;'>Missing Engine Hours End</span>")

            if eng_hrs_start is not None and eng_hrs_end is not None:
                working_hours = round(eng_hrs_end - eng_hrs_start, 1)
                row.working_hours = working_hours

                if working_hours < 0:
                    row_issues.append("❌ <span style='color:red;'>Negative Working Hours</span>")
                    error_count += 1
                elif working_hours == 0:
                    row_issues.append("⚠️ <span style='color:orange;'>Zero Working Hours</span>")
                    warning_count += 1
                elif working_hours > 12:
                    row_issues.append(f"❌ <span style='color:red;'>Unusually High Working Hours ({working_hours})</span>")
                    error_count += 1

            if not row.pre_use_avail_status:
                row_issues.append("⚠️ <span style='color:orange;'>Missing Availability Status</span>")
                warning_count += 1

            if row_issues:
                errors.append(f"""
                    <li>
                        <b>Row {idx} – {row.asset_name or 'Unnamed Asset'}</b><br>
                        <ul>
                            <li><b>Engine Start:</b> {eng_hrs_start or '<i>Missing</i>'}</li>
                            <li><b>Engine End:</b> {eng_hrs_end or '<i>Missing</i>'}</li>
                            <li><b>Working Hours:</b> {working_hours or '<i>N/A</i>'}</li>
                        </ul>
                        <b>Issues:</b>
                        <ul>{"".join(f"<li>{issue}</li>" for issue in row_issues)}</ul>
                    </li>
                """)

        if errors:
            summary = (
                "<h4>⚠️ Data Integrity Check Summary</h4>"
                "<ul>" + "".join(errors) + "</ul>"
                "<hr><h5>Legend & Help</h5>"
                "<p><b>🔴 Red (Critical):</b> Negative or unrealistic working hours (&gt;12 hrs).<br>"
                "<b>🟠 Yellow (Warning):</b> Missing data or zero hours.<br>"
                "<b>🟢 Green (Valid):</b> All data checks passed.</p>"
                "<p><i>Tip: Update engine hours and availability status before saving.</i></p>"
                "<p style='color:gray; margin-top:10px;'>🔁 This summary updates after saving.</p>"
            )
            indicator = "Red" if error_count else "Yellow"
        else:
            summary = (
                "<p><b>✅ All Pre-Use entries passed integrity checks. No issues found.</b></p>"
                "<p style='color:gray;'>🔁 Summary updates after saving.</p>"
            )
            indicator = "Green"

        self.set("data_integrity_summary", summary)
        self.set("data_integ_indicator", indicator)
        self.flags.dirty = True


# Utility functions

def normalize_to_db_date(date_input):
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
    try:
        normalized_date = normalize_to_db_date(shift_date)
        shift_date_obj = datetime.strptime(normalized_date, "%Y-%m-%d")
        query_result = frappe.db.sql(
            """
            SELECT name, location, prod_month_start_date, prod_month_end_date,
                   shift_system, site_status
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
    try:
        # Keep normalization to ensure date is valid, but no Sunday restriction
        normalize_to_ui_date(doc.shift_date)

        if monthly_plan["site_status"] != "Producing":
            frappe.throw("Pre-Use Hours can only be saved if the site's status is 'Producing'.")
    except Exception:
        frappe.log_error(title="Shift Date Validation Error")
        raise



def check_previous_record_sequence(doc, monthly_plan):
    try:
        previous_doc = get_previous_document(doc.location, doc.creation)
        if previous_doc:
            validate_next_shift_and_sequence(doc, previous_doc, monthly_plan)
    except Exception:
        frappe.log_error(title="Shift Sequence Validation Error")
        raise


def validate_next_shift_and_sequence(doc, previous_doc, monthly_plan):
    try:
        shift_system = monthly_plan.get("shift_system")
        if not shift_system:
            frappe.throw("Shift System is not defined in the Monthly Production Planning.")

        shift_sequence = {
            "2x12Hour": {"Day": "Night", "Night": "Day"},
            "3x8Hour": {"Morning": "Afternoon", "Afternoon": "Night", "Night": "Morning"},
        }
        previous_shift = previous_doc.shift
        required_shift = shift_sequence.get(shift_system, {}).get(previous_shift)
        if not required_shift:
            frappe.throw(f"Invalid shift sequence for system '{shift_system}' after '{previous_shift}'.")
        if doc.shift != required_shift:
            frappe.throw(f"Expected '{required_shift}' after '{previous_shift}'.")

        prev_date = datetime.strptime(normalize_to_db_date(previous_doc.shift_date), "%Y-%m-%d").date()
        curr_date = datetime.strptime(normalize_to_db_date(doc.shift_date), "%Y-%m-%d").date()
        if previous_shift == "Night" and required_shift in ("Day", "Morning"):
            expected = prev_date + timedelta(days=1)
            if curr_date != expected:
                frappe.throw(f"{required_shift} shift must occur on {expected.strftime('%d-%m-%Y')}.")

        elif doc.shift in ("Afternoon", "Night") and curr_date != prev_date:
            frappe.throw(f"{doc.shift} shift must occur on the same date as the previous record.")
    except Exception:
        frappe.log_error(title="Shift System Validation Error")
        raise


@frappe.whitelist()
def get_previous_document(location, current_creation):
    try:
        name = frappe.db.get_value(
            "Pre-Use Hours",
            {"location": location, "creation": ["<", current_creation]},
            "name",
            order_by="creation desc"
        )
        return frappe.get_doc("Pre-Use Hours", name) if name else None
    except Exception:
        frappe.log_error(title="Previous Document Fetch Error")
        return None

