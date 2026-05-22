import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class MiningScheduleSelection(Document):
    def before_insert(self):
        if not self.selection_status:
            self.selection_status = "Draft"

        if not self.selected_on:
            self.selected_on = now_datetime()

        if not self.selected_by:
            self.selected_by = frappe.session.user

        if not self.created_from_page:
            self.created_from_page = "Mining Block Selector"

    def validate(self):
        self.validate_required_links()
        self.validate_block_rows()
        self.validate_duplicate_blocks()
        self.recalculate_totals()

    def validate_required_links(self):
        if not self.geo_project:
            frappe.throw(_("Geo Project is required."))

        if not self.geo_pit_layout:
            frappe.throw(_("Geo Pit Layout is required."))

        if not self.material_stack:
            frappe.throw(_("Material Stack is required."))

    def validate_block_rows(self):
        for row in self.blocks or []:
            if row.geo_project and row.geo_project != self.geo_project:
                frappe.throw(
                    _("Block row {0} belongs to Geo Project {1}, not {2}.").format(
                        row.idx, row.geo_project, self.geo_project
                    )
                )

            if row.source_pit_layout and row.source_pit_layout != self.geo_pit_layout:
                frappe.throw(
                    _("Block row {0} belongs to Geo Pit Layout {1}, not {2}.").format(
                        row.idx, row.source_pit_layout, self.geo_pit_layout
                    )
                )

    def validate_duplicate_blocks(self):
        seen = set()
        duplicates = []

        for row in self.blocks or []:
            if not row.mining_block:
                continue

            if row.mining_block in seen:
                duplicates.append(row.mining_block)

            seen.add(row.mining_block)

        if duplicates:
            frappe.throw(
                _("Duplicate Mining Blocks found in selection: {0}").format(
                    ", ".join(sorted(set(duplicates))[:20])
                )
            )

    def recalculate_totals(self):
        self.selected_block_count = len(self.blocks or [])

        self.total_effective_area = sum_float(
            row.effective_area for row in self.blocks or []
        )

        self.total_volume = sum_float(
            row.volume
            for row in self.materials or []
            if row.value_type in ("Thickness", None, "")
        )

        self.total_tonnes = sum_float(
            row.tonnes
            for row in self.materials or []
            if row.value_type in ("Thickness", None, "")
        )

        if not self.total_volume:
            self.total_volume = sum_float(
                row.total_volume for row in self.blocks or []
            )

        if not self.total_tonnes:
            self.total_tonnes = sum_float(
                row.total_tonnes for row in self.blocks or []
            )

        self.average_density = 0
        if self.total_volume:
            self.average_density = self.total_tonnes / self.total_volume

        cv_values = []

        for row in self.materials or []:
            variable_code = (row.variable_code or "").upper()
            value_type = row.value_type or ""

            if value_type == "Quality" and "CV" in variable_code:
                if row.avg_value is not None:
                    cv_values.append(row.avg_value)

        self.average_cv = 0
        if cv_values:
            self.average_cv = sum_float(cv_values) / len(cv_values)


@frappe.whitelist()
def recalculate_selection_doc(name):
    doc = frappe.get_doc("Mining Schedule Selection", name)
    doc.recalculate_totals()
    doc.save()

    return {
        "name": doc.name,
        "selected_block_count": doc.selected_block_count,
        "total_effective_area": doc.total_effective_area,
        "total_volume": doc.total_volume,
        "total_tonnes": doc.total_tonnes,
        "average_density": doc.average_density,
        "average_cv": doc.average_cv,
    }


@frappe.whitelist()
def validate_selection_integrity(name):
    doc = frappe.get_doc("Mining Schedule Selection", name)

    critical_issues = []
    warnings = []

    selected_blocks = [
        row.mining_block
        for row in doc.blocks or []
        if row.mining_block
    ]

    selected_block_set = set(selected_blocks)

    if not selected_blocks:
        critical_issues.append("No selected block rows found.")

    if len(selected_blocks) != len(selected_block_set):
        critical_issues.append("Duplicate selected block rows found.")

    material_blocks = {
        row.mining_block
        for row in doc.materials or []
        if row.mining_block
    }

    if not doc.materials:
        critical_issues.append("No material package rows found.")

    missing_material_blocks = sorted(selected_block_set - material_blocks)

    if missing_material_blocks:
        critical_issues.append(
            "Blocks missing material package rows: {0}".format(
                ", ".join(missing_material_blocks[:20])
            )
        )

    blocks_missing_volume = [
        row.mining_block
        for row in doc.blocks or []
        if row.mining_block and not row.total_volume
    ]

    if blocks_missing_volume:
        warnings.append(
            "Block snapshot total volume is empty for {0} block(s). This is acceptable if material package volume is populated.".format(
                len(blocks_missing_volume)
            )
        )

    blocks_missing_tonnes = [
        row.mining_block
        for row in doc.blocks or []
        if row.mining_block and not row.total_tonnes
    ]

    if blocks_missing_tonnes:
        warnings.append(
            "Block snapshot total tonnes is empty for {0} block(s). This is acceptable if material package tonnes is populated.".format(
                len(blocks_missing_tonnes)
            )
        )

    material_thickness_rows = [
        row
        for row in doc.materials or []
        if row.value_type == "Thickness"
    ]

    material_rows_missing_tonnes = [
        row.mining_block
        for row in material_thickness_rows
        if row.mining_block and not row.tonnes
    ]

    if material_thickness_rows and len(material_rows_missing_tonnes) == len(material_thickness_rows):
        critical_issues.append(
            "All thickness material rows are missing tonnes. Check the Material Stack calculation."
        )
    elif material_rows_missing_tonnes:
        warnings.append(
            "Some thickness material rows are missing tonnes: {0}".format(
                ", ".join(sorted(set(material_rows_missing_tonnes))[:20])
            )
        )

    doc.recalculate_totals()

    if not doc.total_tonnes:
        critical_issues.append("Selection total tonnes is zero after recalculation.")

    if not doc.total_volume:
        critical_issues.append("Selection total volume is zero after recalculation.")

    status = "Passed"

    if critical_issues:
        status = "Failed"
    elif warnings:
        status = "Passed With Warnings"

    return {
        "name": doc.name,
        "status": status,
        "issue_count": len(critical_issues),
        "warning_count": len(warnings),
        "critical_issues": critical_issues,
        "warnings": warnings,
        "issues": critical_issues + warnings,
    }


@frappe.whitelist()
def update_selection_status(name, status):
    allowed_statuses = [
        "Draft",
        "Reviewed",
        "Approved",
        "Sent To Scheduler",
        "Cancelled",
    ]

    if status not in allowed_statuses:
        frappe.throw(_("Invalid status: {0}").format(status))

    doc = frappe.get_doc("Mining Schedule Selection", name)

    if doc.selection_status == "Cancelled":
        frappe.throw(_("Cancelled selections cannot be updated."))

    if status == "Approved":
        result = validate_selection_integrity(name)

        if result.get("issue_count"):
            frappe.throw(
                _("Selection cannot be approved because critical integrity checks found issues.")
            )

    doc.selection_status = status
    doc.save()

    return {
        "name": doc.name,
        "selection_status": doc.selection_status,
    }


@frappe.whitelist()
def get_source_filters(name):
    doc = frappe.get_doc("Mining Schedule Selection", name)

    if not doc.source_filters_json:
        return {}

    try:
        return json.loads(doc.source_filters_json)
    except Exception:
        return {
            "raw": doc.source_filters_json,
        }


def sum_float(values):
    total = 0.0

    for value in values:
        if value is None:
            continue

        try:
            total += float(value)
        except Exception:
            continue

    return total