# apps/is_production/is_production/geo_planning/services/mining_schedule_rule_parser_service.py

from __future__ import annotations

import hashlib
import re
from typing import Any

import frappe
from frappe import _

from is_production.geo_planning.services.mining_schedule_rule_models import (
    ConstraintRule,
    DayRule,
    FleetRule,
    ScheduleRules,
    SequenceRule,
)
from is_production.geo_planning.services.mining_schedule_rule_preview_service import (
    build_rule_preview_html,
)


DAY_ALIASES = {
    "weekday": "weekday",
    "weekdays": "weekday",
    "monday to friday": "weekday",
    "mon to fri": "weekday",
    "saturday": "saturday",
    "saturdays": "saturday",
    "sunday": "sunday",
    "sundays": "sunday",
}


def _normalise_text(text: str) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", (line or "").strip())


def _split_lines(rule_text: str) -> list[str]:
    text = _normalise_text(rule_text)
    raw_lines = []

    for line in text.split("\n"):
        parts = [p.strip() for p in line.split(";") if p.strip()]
        raw_lines.extend(parts or [line.strip()])

    return [_clean_line(line) for line in raw_lines if _clean_line(line)]


def _default_calendar() -> dict[str, DayRule]:
    return {
        "weekday": DayRule(shifts=0, production_hours=0, working=False),
        "saturday": DayRule(shifts=0, production_hours=0, working=False),
        "sunday": DayRule(shifts=0, production_hours=0, working=False),
    }


def _parse_day_rule(line: str, calendar: dict[str, DayRule]) -> bool:
    lower = line.lower().strip().rstrip(".")

    matched_day = None

    for alias, day_key in DAY_ALIASES.items():
        if lower.startswith(alias):
            matched_day = day_key
            break

    if not matched_day:
        return False

    if "off" in lower or "no work" in lower or "non working" in lower or "non-working" in lower:
        calendar[matched_day] = DayRule(shifts=0, production_hours=0, working=False)
        return True

    shifts = 1
    hours = 0.0

    shift_match = re.search(r"(\d+(?:\.\d+)?)\s*shifts?", lower)
    if shift_match:
        shifts = float(shift_match.group(1))

    hour_match = re.search(r"(\d+(?:\.\d+)?)\s*(production\s*)?hours?", lower)
    if hour_match:
        hours = float(hour_match.group(1))

    if hours <= 0:
        raise ValueError(f"Could not find production hours in line: {line}")

    calendar[matched_day] = DayRule(shifts=shifts, production_hours=hours, working=True)
    return True


def _parse_fleet_rule(line: str, fleet: list[FleetRule]) -> bool:
    lower = line.lower().strip().rstrip(".")

    if not lower.startswith("use "):
        return False

    pattern = (
        r"use\s+"
        r"(?P<count>\d+(?:\.\d+)?)\s+"
        r"(?P<equipment>[a-zA-Z\s]+?)"
        r"\s+at\s+"
        r"(?P<capacity>\d+(?:\.\d+)?)\s*"
        r"(?P<unit>bcm|tonnes|tons|t)\s*(per\s*)?(hour|hr|h)"
    )

    match = re.search(pattern, lower)

    if not match:
        raise ValueError(f"Could not parse fleet rule: {line}")

    unit_raw = match.group("unit")
    unit = "tonnes_per_hour" if unit_raw in ("tonnes", "tons", "t") else "bcm_per_hour"

    equipment = match.group("equipment").strip()

    if equipment.endswith("s"):
        equipment = equipment[:-1]

    fleet.append(
        FleetRule(
            equipment_type=equipment,
            count=float(match.group("count")),
            capacity_per_hour=float(match.group("capacity")),
            unit=unit,
        )
    )

    return True


def _parse_percent_rule(line: str, values: dict[str, float]) -> bool:
    lower = line.lower().strip().rstrip(".")

    if "availability" in lower:
        match = re.search(r"availability\s*(\d+(?:\.\d+)?)\s*%", lower)

        if not match:
            raise ValueError(f"Could not parse availability percentage: {line}")

        values["availability_percent"] = float(match.group(1))
        return True

    if "utilisation" in lower or "utilization" in lower:
        match = re.search(r"utili[sz]ation\s*(\d+(?:\.\d+)?)\s*%", lower)

        if not match:
            raise ValueError(f"Could not parse utilisation percentage: {line}")

        values["utilisation_percent"] = float(match.group(1))
        return True

    return False


def _parse_sequence_rule(line: str, sequence_data: dict[str, Any]) -> bool:
    lower = line.lower().strip().rstrip(".")

    if "mine selected blocks in order" in lower:
        sequence_data["block_order"] = "selected_order"
        return True

    if "cut order" in lower or "mine cuts in order" in lower:
        sequence_data["block_order"] = "cut_order"
        return True

    if "allow partial blocks" in lower or "allow partial block" in lower:
        sequence_data["allow_partial_blocks"] = True
        return True

    if "do not allow partial blocks" in lower or "no partial blocks" in lower:
        sequence_data["allow_partial_blocks"] = False
        return True

    return False


def _parse_material_rule(line: str, sequence_data: dict[str, Any]) -> bool:
    lower = line.lower().strip().rstrip(".")

    if not lower.startswith("mine materials"):
        return False

    raw = re.sub(r"^mine materials", "", line, flags=re.IGNORECASE).strip(" :.")
    materials = [m.strip() for m in re.split(r",| then ", raw) if m.strip()]

    if not materials:
        raise ValueError(f"Could not parse material order: {line}")

    sequence_data["material_order"] = materials
    return True


def _parse_constraint_rule(line: str, constraints_data: dict[str, Any]) -> bool:
    lower = line.lower().strip().rstrip(".")

    active_match = re.search(r"maximum\s+(\d+)\s+active blocks?", lower)

    if active_match:
        constraints_data["max_active_blocks_per_period"] = int(active_match.group(1))
        return True

    minimum_match = re.search(r"minimum task quantity\s+(\d+(?:\.\d+)?)", lower)

    if minimum_match:
        constraints_data["minimum_task_quantity"] = float(minimum_match.group(1))
        return True

    return False


def parse_rule_text(rule_text: str) -> tuple[ScheduleRules, list[dict[str, Any]]]:
    lines = _split_lines(rule_text)

    if not lines:
        raise ValueError("Schedule Rule Text is empty.")

    calendar = _default_calendar()
    fleet: list[FleetRule] = []
    values = {
        "availability_percent": 100.0,
        "utilisation_percent": 100.0,
    }
    sequence_data: dict[str, Any] = {
        "block_order": "selected_order",
        "material_order": [],
        "allow_partial_blocks": True,
    }
    constraints_data: dict[str, Any] = {
        "max_active_blocks_per_period": None,
        "minimum_task_quantity": 0,
    }

    parse_log: list[dict[str, Any]] = []

    for idx, line in enumerate(lines, start=1):
        try:
            parsed = (
                _parse_day_rule(line, calendar)
                or _parse_fleet_rule(line, fleet)
                or _parse_percent_rule(line, values)
                or _parse_sequence_rule(line, sequence_data)
                or _parse_material_rule(line, sequence_data)
                or _parse_constraint_rule(line, constraints_data)
            )

            if parsed:
                parse_log.append(
                    {
                        "line_no": idx,
                        "source_text": line,
                        "status": "Parsed",
                        "message": "Parsed successfully.",
                    }
                )
            else:
                parse_log.append(
                    {
                        "line_no": idx,
                        "source_text": line,
                        "status": "Warning",
                        "message": "Unsupported rule line. It was not used by the scheduler.",
                    }
                )

        except Exception as exc:
            parse_log.append(
                {
                    "line_no": idx,
                    "source_text": line,
                    "status": "Error",
                    "message": str(exc),
                }
            )

    errors = [row for row in parse_log if row["status"] == "Error"]

    if errors:
        message = "\n".join(
            f"Line {row['line_no']}: {row['message']}" for row in errors
        )
        raise ValueError(message)

    rules = ScheduleRules(
        calendar=calendar,
        fleet=fleet,
        availability_percent=values["availability_percent"],
        utilisation_percent=values["utilisation_percent"],
        sequence=SequenceRule(**sequence_data),
        constraints=ConstraintRule(**constraints_data),
    )

    return rules, parse_log


def make_rule_hash(rule_text: str, parsed_json: str) -> str:
    raw = f"{rule_text or ''}\n{parsed_json or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@frappe.whitelist()
def parse_rules_for_scenario(scenario_name: str) -> dict[str, Any]:
    scenario = frappe.get_doc("Mining Schedule Scenario", scenario_name)

    try:
        rules, parse_log = parse_rule_text(scenario.get("schedule_rule_text") or "")
        parsed_json = rules.model_dump_json(indent=2)
        preview_html = build_rule_preview_html(rules, parse_log)

        rule_set_name = scenario.get("active_rule_set")

        if rule_set_name:
            rule_set = frappe.get_doc("Mining Schedule Rule Set", rule_set_name)
        else:
            rule_set = frappe.new_doc("Mining Schedule Rule Set")
            rule_set.rule_set_name = f"{scenario.name} Rule Set"
            rule_set.scenario = scenario.name
            rule_set.mining_schedule_selection = scenario.get("mining_schedule_selection")

        rule_set.rule_text = scenario.get("schedule_rule_text")
        rule_set.parsed_rules_json = parsed_json
        rule_set.parser_status = (
            "Warning"
            if any(row["status"] == "Warning" for row in parse_log)
            else "Parsed"
        )
        rule_set.parser_error = ""
        rule_set.rule_hash = make_rule_hash(rule_set.rule_text, parsed_json)
        rule_set.save(ignore_permissions=True)

        scenario.active_rule_set = rule_set.name
        scenario.parsed_schedule_rules_json = parsed_json
        scenario.rule_parse_status = rule_set.parser_status
        scenario.rule_parse_error = ""
        scenario.rule_preview_html = preview_html

        if not scenario.get("engine_mode"):
            scenario.engine_mode = "Rule Based"

        scenario.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": scenario.rule_parse_status,
            "rule_set": rule_set.name,
            "parsed_rules_json": parsed_json,
            "preview_html": preview_html,
            "parse_log": parse_log,
        }

    except Exception as exc:
        scenario.rule_parse_status = "Error"
        scenario.rule_parse_error = str(exc)
        scenario.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.throw(_(str(exc)))


@frappe.whitelist()
def preview_rules_for_scenario(scenario_name: str) -> dict[str, Any]:
    scenario = frappe.get_doc("Mining Schedule Scenario", scenario_name)

    if scenario.get("parsed_schedule_rules_json"):
        rules = ScheduleRules.model_validate_json(scenario.parsed_schedule_rules_json)
        parse_log = []
    else:
        rules, parse_log = parse_rule_text(scenario.get("schedule_rule_text") or "")

    preview_html = build_rule_preview_html(rules, parse_log)

    scenario.rule_preview_html = preview_html
    scenario.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "preview_html": preview_html,
    }


@frappe.whitelist()
def approve_active_rule_set(scenario_name: str) -> dict[str, Any]:
    scenario = frappe.get_doc("Mining Schedule Scenario", scenario_name)

    if not scenario.get("active_rule_set"):
        frappe.throw(_("Please parse rules first. No Active Rule Set is linked."))

    rule_set = frappe.get_doc("Mining Schedule Rule Set", scenario.active_rule_set)

    if not rule_set.get("parsed_rules_json"):
        frappe.throw(_("Rule Set has no Parsed Rules JSON. Please parse rules first."))

    if rule_set.get("parser_status") == "Error":
        frappe.throw(_("Cannot approve a Rule Set with parser errors."))

    rule_set.parser_status = "Approved"
    rule_set.approved_by = frappe.session.user
    rule_set.approved_on = frappe.utils.now_datetime()
    rule_set.save(ignore_permissions=True)

    scenario.rule_parse_status = "Approved"
    scenario.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "status": "Approved",
        "rule_set": rule_set.name,
    }