import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class MiningScheduleScenario(Document):
    def before_insert(self):
        if not self.schedule_status:
            self.schedule_status = "Draft"

        if not self.generated_on:
            self.generated_on = now_datetime()

        if not self.generated_by:
            self.generated_by = frappe.session.user

    def validate(self):
        self.validate_required_fields()
        self.recalculate_totals()

    def validate_required_fields(self):
        if not self.scenario_name:
            frappe.throw(_("Scenario Name is required."))

        if not self.mining_schedule_selection:
            frappe.throw(_("Source Selection is required."))

        if not self.period_type:
            frappe.throw(_("Period Type is required."))

        if not self.start_date:
            frappe.throw(_("Start Date is required."))

    def recalculate_totals(self):
        self.total_periods = len(self.periods or [])
        self.total_blocks = sum_float(row.planned_block_count for row in self.periods or [])
        self.total_effective_area = sum_float(row.planned_effective_area for row in self.periods or [])
        self.total_volume = sum_float(row.planned_volume for row in self.periods or [])
        self.total_tonnes = sum_float(row.planned_tonnes for row in self.periods or [])

        self.average_density = 0
        if self.total_volume:
            self.average_density = self.total_tonnes / self.total_volume

        cv_values = []

        for row in self.period_materials or []:
            variable_code = (row.variable_code or "").upper()
            if row.value_type == "Quality" and "CV" in variable_code and row.average_value is not None:
                cv_values.append(row.average_value)

        self.average_cv = average(cv_values)

        capacity_values = [
            row.capacity_used_percent
            for row in self.periods or []
            if row.capacity_used_percent is not None
        ]

        self.capacity_used_percent = average(capacity_values)

        if self.periods:
            self.end_date = self.periods[-1].period_end_date


@frappe.whitelist()
def update_scenario_status(name, status):
    allowed = ["Draft", "Generated", "Reviewed", "Approved", "Cancelled"]

    if status not in allowed:
        frappe.throw(_("Invalid status: {0}").format(status))

    doc = frappe.get_doc("Mining Schedule Scenario", name)

    if doc.schedule_status == "Cancelled":
        frappe.throw(_("Cancelled scenarios cannot be updated."))

    doc.schedule_status = status
    doc.save()

    return {
        "name": doc.name,
        "schedule_status": doc.schedule_status,
    }


@frappe.whitelist()
def get_scenario_source_settings(name):
    doc = frappe.get_doc("Mining Schedule Scenario", name)

    if not doc.source_filters_json:
        return {}

    try:
        return json.loads(doc.source_filters_json)
    except Exception:
        return {"raw": doc.source_filters_json}


@frappe.whitelist()
def recalculate_scenario_doc(name):
    doc = frappe.get_doc("Mining Schedule Scenario", name)
    doc.recalculate_totals()
    doc.save()

    return {
        "name": doc.name,
        "total_periods": doc.total_periods,
        "total_blocks": doc.total_blocks,
        "total_volume": doc.total_volume,
        "total_tonnes": doc.total_tonnes,
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


def average(values):
    clean = []

    for value in values:
        if value is None:
            continue

        try:
            clean.append(float(value))
        except Exception:
            continue

    if not clean:
        return 0

    return sum(clean) / len(clean)