# apps/is_production/is_production/geo_planning/services/mining_schedule_calendar_service.py

from __future__ import annotations

from datetime import timedelta

import frappe
from frappe import _

from is_production.geo_planning.services.mining_schedule_rule_models import ScheduleRules


def _as_date(value):
    if not value:
        return None
    return frappe.utils.getdate(value)


def _day_key(date_value) -> str:
    weekday = date_value.weekday()

    if weekday == 5:
        return "saturday"

    if weekday == 6:
        return "sunday"

    return "weekday"


def _day_type_label(day_key: str) -> str:
    return {
        "weekday": "Weekday",
        "saturday": "Saturday",
        "sunday": "Sunday",
    }.get(day_key, "Custom")


def _capacity_unit_label(unit: str) -> str:
    if unit == "tonnes_per_hour":
        return "Tonnes per Hour"

    if unit == "blocks_per_hour":
        return "Blocks per Hour"

    return "BCM per Hour"


def _equipment_type_label(equipment_type: str) -> str:
    value = (equipment_type or "").strip().lower().replace("_", " ")

    mapping = {
        "excavator": "Excavator",
        "dozer": "Dozer",
        "truck fleet": "Truck Fleet",
        "truck": "Truck Fleet",
        "drill": "Drill",
        "coal fleet": "Coal Fleet",
    }

    return mapping.get(value, "Other")


def _get_approved_rule_set(scenario):
    if not scenario.get("active_rule_set"):
        frappe.throw(_("Please parse and approve schedule rules first. No Active Rule Set is linked."))

    rule_set = frappe.get_doc("Mining Schedule Rule Set", scenario.active_rule_set)

    if rule_set.get("parser_status") != "Approved":
        frappe.throw(_("The Active Rule Set must be Approved before building the capacity calendar."))

    if not rule_set.get("parsed_rules_json"):
        frappe.throw(_("The Active Rule Set has no Parsed Rules JSON."))

    return rule_set


def _delete_existing_capacity_rows(scenario_name: str):
    existing_calendar_days = frappe.get_all(
        "Mining Schedule Calendar Day",
        filters={"schedule_scenario": scenario_name},
        pluck="name",
    )

    for name in existing_calendar_days:
        frappe.delete_doc(
            "Mining Schedule Calendar Day",
            name,
            ignore_permissions=True,
            force=True,
        )

    existing_fleet_rows = frappe.get_all(
        "Mining Schedule Fleet Resource",
        filters={"schedule_scenario": scenario_name},
        pluck="name",
    )

    for name in existing_fleet_rows:
        frappe.delete_doc(
            "Mining Schedule Fleet Resource",
            name,
            ignore_permissions=True,
            force=True,
        )


def _build_fleet_resources(scenario, rule_set, rules: ScheduleRules) -> list[dict]:
    created_rows = []

    for fleet_rule in rules.fleet:
        doc = frappe.new_doc("Mining Schedule Fleet Resource")
        doc.schedule_scenario = scenario.name
        doc.rule_set = rule_set.name
        doc.equipment_type = _equipment_type_label(fleet_rule.equipment_type)
        doc.equipment_name = ""
        doc.quantity = fleet_rule.count
        doc.capacity_per_hour = fleet_rule.capacity_per_hour
        doc.capacity_unit = _capacity_unit_label(fleet_rule.unit)
        doc.availability_percent = rules.availability_percent
        doc.utilisation_percent = rules.utilisation_percent
        doc.applies_to_materials = ""
        doc.resource_status = "Active"
        doc.source_rule_hash = rule_set.get("rule_hash")
        doc.insert(ignore_permissions=True)

        created_rows.append(
            {
                "name": doc.name,
                "equipment_type": doc.equipment_type,
                "quantity": doc.quantity,
                "capacity_per_hour": doc.capacity_per_hour,
                "capacity_unit": doc.capacity_unit,
            }
        )

    return created_rows


def _get_capacity_per_hour(rules: ScheduleRules) -> tuple[float, float, float]:
    fleet_count = 0.0
    bcm_capacity_per_hour = 0.0
    tonnes_capacity_per_hour = 0.0

    for fleet_rule in rules.fleet:
        fleet_count += float(fleet_rule.count or 0)

        if fleet_rule.unit == "tonnes_per_hour":
            tonnes_capacity_per_hour += float(fleet_rule.count or 0) * float(fleet_rule.capacity_per_hour or 0)
        else:
            bcm_capacity_per_hour += float(fleet_rule.count or 0) * float(fleet_rule.capacity_per_hour or 0)

    return fleet_count, bcm_capacity_per_hour, tonnes_capacity_per_hour


def _build_calendar_days(scenario, rule_set, rules: ScheduleRules) -> tuple[list[dict], dict]:
    start_date = _as_date(scenario.get("start_date"))
    end_date = _as_date(scenario.get("end_date"))

    if not start_date:
        frappe.throw(_("Start Date is required before building the capacity calendar."))

    if not end_date:
        frappe.throw(_("End Date is required before building the capacity calendar."))

    if end_date < start_date:
        frappe.throw(_("End Date cannot be before Start Date."))

    fleet_count, bcm_capacity_per_hour, tonnes_capacity_per_hour = _get_capacity_per_hour(rules)

    factor = (float(rules.availability_percent or 0) / 100) * (
        float(rules.utilisation_percent or 0) / 100
    )

    current_date = start_date
    created_rows = []

    totals = {
        "calendar_days": 0,
        "working_days": 0,
        "available_bcm_capacity": 0.0,
        "available_tonnes_capacity": 0.0,
    }

    while current_date <= end_date:
        key = _day_key(current_date)
        day_rule = rules.calendar.get(key)

        is_working_day = bool(day_rule and day_rule.working)
        production_hours = float(day_rule.production_hours or 0) if day_rule else 0.0
        shifts = float(day_rule.shifts or 0) if day_rule else 0.0

        if is_working_day:
            available_bcm_capacity = production_hours * bcm_capacity_per_hour * factor
            available_tonnes_capacity = production_hours * tonnes_capacity_per_hour * factor
        else:
            available_bcm_capacity = 0.0
            available_tonnes_capacity = 0.0

        doc = frappe.new_doc("Mining Schedule Calendar Day")
        doc.schedule_scenario = scenario.name
        doc.rule_set = rule_set.name
        doc.calendar_date = current_date
        doc.day_type = _day_type_label(key)
        doc.is_working_day = 1 if is_working_day else 0
        doc.shifts = shifts
        doc.production_hours = production_hours
        doc.fleet_count = fleet_count
        doc.bcm_capacity_per_hour = bcm_capacity_per_hour
        doc.tonnes_capacity_per_hour = tonnes_capacity_per_hour
        doc.availability_percent = rules.availability_percent
        doc.utilisation_percent = rules.utilisation_percent
        doc.available_bcm_capacity = available_bcm_capacity
        doc.available_tonnes_capacity = available_tonnes_capacity
        doc.scheduled_bcm = 0
        doc.scheduled_tonnes = 0
        doc.remaining_bcm_capacity = available_bcm_capacity
        doc.remaining_tonnes_capacity = available_tonnes_capacity
        doc.calendar_note = ""
        doc.source_rule_hash = rule_set.get("rule_hash")
        doc.insert(ignore_permissions=True)

        created_rows.append(
            {
                "name": doc.name,
                "calendar_date": str(current_date),
                "day_type": doc.day_type,
                "is_working_day": doc.is_working_day,
                "production_hours": doc.production_hours,
                "available_bcm_capacity": doc.available_bcm_capacity,
                "available_tonnes_capacity": doc.available_tonnes_capacity,
            }
        )

        totals["calendar_days"] += 1

        if is_working_day:
            totals["working_days"] += 1

        totals["available_bcm_capacity"] += available_bcm_capacity
        totals["available_tonnes_capacity"] += available_tonnes_capacity

        current_date += timedelta(days=1)

    return created_rows, totals


def build_capacity_calendar_for_scenario(scenario_name: str) -> dict:
    scenario = frappe.get_doc("Mining Schedule Scenario", scenario_name)
    rule_set = _get_approved_rule_set(scenario)
    rules = ScheduleRules.model_validate_json(rule_set.parsed_rules_json)

    _delete_existing_capacity_rows(scenario.name)

    fleet_rows = _build_fleet_resources(scenario, rule_set, rules)
    calendar_rows, totals = _build_calendar_days(scenario, rule_set, rules)

    frappe.db.commit()

    return {
        "scenario": scenario.name,
        "rule_set": rule_set.name,
        "fleet_count": len(fleet_rows),
        "calendar_day_count": len(calendar_rows),
        "totals": totals,
        "fleet_rows": fleet_rows,
        "calendar_rows": calendar_rows,
    }


def _fmt(value) -> str:
    try:
        return f"{float(value):,.2f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value or "")


def build_capacity_calendar_result_html(result: dict) -> str:
    totals = result.get("totals") or {}

    return f"""
    <div>
        <h3>Capacity Calendar Built</h3>

        <p><b>Scenario:</b> {frappe.utils.escape_html(result.get("scenario"))}</p>
        <p><b>Rule Set:</b> {frappe.utils.escape_html(result.get("rule_set"))}</p>

        <table class="table table-bordered table-sm">
            <tbody>
                <tr>
                    <td><b>Fleet Rows Created</b></td>
                    <td>{_fmt(result.get("fleet_count"))}</td>
                </tr>
                <tr>
                    <td><b>Calendar Days Created</b></td>
                    <td>{_fmt(result.get("calendar_day_count"))}</td>
                </tr>
                <tr>
                    <td><b>Working Days</b></td>
                    <td>{_fmt(totals.get("working_days"))}</td>
                </tr>
                <tr>
                    <td><b>Total Available BCM Capacity</b></td>
                    <td>{_fmt(totals.get("available_bcm_capacity"))}</td>
                </tr>
                <tr>
                    <td><b>Total Available Tonnes Capacity</b></td>
                    <td>{_fmt(totals.get("available_tonnes_capacity"))}</td>
                </tr>
            </tbody>
        </table>

        <p>
            Capacity rows are now ready for task allocation in the next phases.
        </p>
    </div>
    """


@frappe.whitelist()
def build_capacity_calendar(scenario_name: str) -> dict:
    return build_capacity_calendar_for_scenario(scenario_name)


@frappe.whitelist()
def build_capacity_calendar_html(scenario_name: str) -> str:
    result = build_capacity_calendar_for_scenario(scenario_name)
    return build_capacity_calendar_result_html(result)