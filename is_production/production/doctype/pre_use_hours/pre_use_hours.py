# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from datetime import datetime, timedelta, date
from frappe.utils import flt
from frappe.utils.data import getdate


class PreUseHours(Document):
    def before_validate(self):
        """
        Ensure child row `asset_name` (Link -> Asset) stores Asset.name.
        If any existing rows contain the Plant No / code (Asset.asset_name),
        convert them to Asset.name BEFORE Frappe link validation runs.
        """
        self._normalize_asset_links()

    def _normalize_asset_links(self):
        rows = self.get("pre_use_assets") or []
        values = sorted({r.asset_name for r in rows if getattr(r, "asset_name", None)})
        if not values:
            return

        # Values that already exist as Asset.name
        existing_names = set(
            frappe.get_all("Asset", filters={"name": ["in", values]}, pluck="name")
        )

        # Anything not a valid Asset.name: try match against Asset.asset_name (Plant No.)
        unknown = [v for v in values if v not in existing_names]
        if not unknown:
            return

        matches = frappe.get_all(
            "Asset",
            filters={"asset_name": ["in", unknown]},
            fields=["name", "asset_name"],
        )
        code_to_name = {m.asset_name: m.name for m in matches if m.get("asset_name")}

        if not code_to_name:
            return

        for r in rows:
            v = getattr(r, "asset_name", None)
            if v and v in code_to_name:
                r.asset_name = code_to_name[v]

    def before_save(self):
        """
        Called before saving the 'Pre-Use Hours' document.
        Performs integrity checks on the current and validates the previous record.
        """
        try:
            # normalize early for all downstream logic
            self.shift_date = getdate(self.shift_date)
            monthly_plan = get_monthly_production_plan(self.location, self.shift_date)
            if not monthly_plan:
                frappe.throw(
                    "No Monthly Production Planning data found for the selected location and shift date."
                )

            validate_shift_date(self, monthly_plan)
            check_previous_record_sequence(self, monthly_plan)
            self.validate_previous_shift_hours()
            self.evaluate_data_integrity()
            self.update_previous_eng_hrs_end()

        except Exception as e:
            frappe.log_error(message=frappe.get_traceback(), title="Pre-Use Hours Validation Error")
            raise

    def validate_previous_shift_hours(self):
        """
        Ensures that when opening a new shift, the calculated working hours for
        the previous shift (using new eng_hrs_start values) are not negative
        or greater than 12. If invalid, throw error with asset details.
        """
        prev_doc = get_previous_document(self.location, self.creation)
        if not prev_doc:
            return

        bad_assets = []
        current_assets_map = {r.asset_name: r for r in self.pre_use_assets if r.asset_name}

        for pr in prev_doc.pre_use_assets:
            cr = current_assets_map.get(pr.asset_name)
            if cr and cr.eng_hrs_start is not None and pr.eng_hrs_start is not None:
                eng_hrs_end = cr.eng_hrs_start
                working_hours = round(flt(eng_hrs_end) - flt(pr.eng_hrs_start), 1)

                if working_hours < 0 or working_hours > 12:
                    bad_assets.append({
                        "asset": pr.asset_name,
                        "prev_start": pr.eng_hrs_start,
                        "new_start": cr.eng_hrs_start,
                        "wh": working_hours
                    })

        if bad_assets:
            rows_html = "".join(
                f"<tr><td>{b['asset']}</td><td>{b['prev_start']}</td>"
                f"<td>{b['new_start']}</td><td>{b['wh']}</td></tr>"
                for b in bad_assets
            )
            table_html = f"""
                <h4>❌ Cannot save this shift</h4>
                <p>The following assets would create invalid working hours in the previous shift:</p>
                <table class="table table-bordered" style="width:100%; border-collapse: collapse;">
                    <tr>
                        <th>Asset</th>
                        <th>Previous Start</th>
                        <th>Current Start</th>
                        <th>Calculated Hours</th>
                    </tr>
                    {rows_html}
                </table>
                <p style="color:gray; margin-top:10px;">
                    Please adjust the <b>engine start hours</b> in the current shift so that the
                    previous shift's working hours are valid (0–12).
                </p>
            """
            frappe.throw(table_html)

    def update_previous_eng_hrs_end(self):
        """
        Copy eng_hrs_end/working_hours into the previous record and re-run its integrity.
        """
        try:
            prev_name = frappe.db.get_value(
                "Pre-Use Hours",
                {"location": self.location, "creation": ["<", self.creation]},
                "name",
                order_by="creation desc"
            )
            if not prev_name:
                return

            prev = frappe.get_doc("Pre-Use Hours", prev_name)
            current_assets_map = {r.asset_name: r for r in self.pre_use_assets if r.asset_name}

            for pr in prev.pre_use_assets:
                cr = current_assets_map.get(pr.asset_name)
                if cr and cr.eng_hrs_start is not None:
                    pr.eng_hrs_end = cr.eng_hrs_start
                    if pr.eng_hrs_start is not None:
                        pr.working_hours = round(flt(pr.eng_hrs_end) - flt(pr.eng_hrs_start), 1)
                    frappe.db.set_value(
                        "Pre-use Assets", pr.name,
                        {
                            "eng_hrs_end": pr.eng_hrs_end,
                            "working_hours": pr.working_hours
                        },
                        update_modified=False
                    )

            prev.evaluate_data_integrity()
            frappe.db.set_value(
                "Pre-Use Hours", prev.name,
                {
                    "data_integrity_summary": prev.data_integrity_summary,
                    "data_integ_indicator": prev.data_integ_indicator
                },
                update_modified=False
            )

            frappe.publish_realtime("preuse:reload_doc", {
                "doctype": "Pre-Use Hours", "name": prev.name
            })

            # Merge summaries
            nav_buttons = """
                <div style="margin-bottom:10px;">
                  <button class="btn btn-sm btn-secondary" id="prev_record_top">⬅️ Previous</button>
                  <button class="btn btn-sm btn-secondary" id="next_record_top">Next ➡️</button>
                </div>
            """

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

            self.set("data_integrity_summary", merged)
            self.flags.dirty = True

        except Exception as e:
            frappe.log_error(message=frappe.get_traceback(), title="Engine Hours Update Error")
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
                working_hours = round(flt(eng_hrs_end) - flt(eng_hrs_start), 1)
                row.working_hours = working_hours

                if working_hours < 0:
                    row_issues.append("❌ <span style='color:red;'>Negative Working Hours</span>")
                elif working_hours > 12:
                    row_issues.append("❌ <span style='color:red;'>Unrealistic Working Hours &gt; 12</span>")
                elif working_hours == 0:
                    row_issues.append("⚠️ <span style='color:orange;'>Zero Working Hours</span>")

            if row_issues:
                warning_count += sum("⚠️" in i or "orange" in i for i in row_issues)
                error_count += sum("❌" in i or "red" in i for i in row_issues)

                errors.append({
                    "row": idx,
                    "asset": row.asset_name,
                    "issues": row_issues
                })

        indicator = "🟢"
        if error_count > 0:
            indicator = "🔴"
        elif warning_count > 0:
            indicator = "🟠"

        # Build the HTML summary table
        if errors:
            rows_html = "".join(
                f"<tr><td>Row #{e['row']}</td><td>{e['asset']}</td><td>{'<br>'.join(e['issues'])}</td></tr>"
                for e in errors
            )
            self.data_integrity_summary = f"""
                <table class="table table-bordered">
                    <tr><th>Row</th><th>Asset</th><th>Issues</th></tr>
                    {rows_html}
                </table>
            """
        else:
            self.data_integrity_summary = "<p><b>✅ No integrity issues found.</b></p>"

        self.data_integ_indicator = indicator


def get_monthly_production_plan(location, shift_date):
    """
    Fetch Monthly Production Planning record for this site + date.
    """
    records = frappe.get_all(
        "Monthly Production Planning",
        filters={
            "location": location,
            "prod_month_start_date": ["<=", shift_date],
            "prod_month_end_date": [">=", shift_date],
            "site_status": "Producing"
        },
        fields=["name", "prod_month_start_date", "prod_month_end_date", "shift_system"],
        limit=1
    )
    return records[0] if records else None


def validate_shift_date(doc, monthly_plan):
    """
    v16-safe: normalize values to datetime.date before comparing.
    Frappe may supply doc.shift_date as a string on new/unsaved docs.
    """
    shift_date = getdate(doc.shift_date)
    start_date = getdate(monthly_plan.prod_month_start_date)
    end_date = getdate(monthly_plan.prod_month_end_date)

    if not shift_date:
        frappe.throw(_("Shift Date is required."))

    if shift_date < start_date or shift_date > end_date:
        frappe.throw(_("Shift Date is outside the producing month range."))


def check_previous_record_sequence(doc, monthly_plan):
    """
    Ensure the previous shift record exists and sequencing is correct.
    """
    prev_doc = get_previous_document(doc.location, doc.creation)
    if not prev_doc:
        return

    # Enforce that shift date is not going backwards
    if prev_doc.shift_date and doc.shift_date and doc.shift_date < prev_doc.shift_date:
        frappe.throw("Shift Date cannot be before the previous record's shift date.")


def get_previous_document(location, creation_dt):
    """
    Get the previous Pre-Use Hours doc (by creation timestamp) for a location.
    """
    prev_name = frappe.db.get_value(
        "Pre-Use Hours",
        {"location": location, "creation": ["<", creation_dt]},
        "name",
        order_by="creation desc"
    )
    if not prev_name:
        return None
    return frappe.get_doc("Pre-Use Hours", prev_name)
