# apps/is_production/is_production/geo_planning/services/mining_schedule_engine_service.py

from __future__ import annotations

import hashlib
import json

import frappe
from frappe import _

from is_production.geo_planning.services.mining_schedule_rule_models import ScheduleRules


EPSILON = 0.000001


def _to_float(value) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _safe_json(value, fallback=None):
    if fallback is None:
        fallback = []

    if not value:
        return fallback

    if isinstance(value, (dict, list)):
        return value

    try:
        return json.loads(value)
    except Exception:
        return fallback


def _hash_payload(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _delete_docs(doctype: str, names: list[str]):
    for name in names:
        if frappe.db.exists(doctype, name):
            frappe.delete_doc(
                doctype,
                name,
                ignore_permissions=True,
                force=True,
            )


def _delete_existing_allocations_for_scenario(scenario_name: str):
    """
    Rebuild safety.

    When the rule schedule is regenerated, old allocation rows for the same
    scenario must be removed first. Otherwise Frappe can hit duplicate names.
    """

    allocation_names = frappe.get_all(
        "Mining Schedule Allocation",
        filters={"schedule_scenario": scenario_name},
        pluck="name",
    )

    _delete_docs("Mining Schedule Allocation", allocation_names)

    frappe.db.commit()


def _get_approved_rule_set(scenario):
    if not scenario.get("active_rule_set"):
        frappe.throw(_("Please parse and approve schedule rules first. No Active Rule Set is linked."))

    rule_set = frappe.get_doc("Mining Schedule Rule Set", scenario.active_rule_set)

    if rule_set.get("parser_status") != "Approved":
        frappe.throw(_("The Active Rule Set must be Approved before generating a rule schedule."))

    if not rule_set.get("parsed_rules_json"):
        frappe.throw(_("The Active Rule Set has no Parsed Rules JSON."))

    return rule_set


def _get_calendar_days(scenario_name: str) -> list:
    names = frappe.get_all(
        "Mining Schedule Calendar Day",
        filters={"schedule_scenario": scenario_name},
        order_by="calendar_date asc",
        pluck="name",
    )

    if not names:
        frappe.throw(_("Please build the capacity calendar before generating the rule schedule."))

    return [frappe.get_doc("Mining Schedule Calendar Day", name) for name in names]


def _get_tasks(scenario_name: str) -> list:
    names = frappe.get_all(
        "Mining Schedule Task",
        filters={"schedule_scenario": scenario_name},
        order_by="sequence_no asc, material_order asc, creation asc",
        pluck="name",
    )

    if not names:
        frappe.throw(_("Please generate schedule tasks before generating the rule schedule."))

    return [frappe.get_doc("Mining Schedule Task", name) for name in names]


def _reset_calendar_days(calendar_days: list):
    for day in calendar_days:
        day.scheduled_bcm = 0
        day.scheduled_tonnes = 0
        day.remaining_bcm_capacity = _to_float(day.get("available_bcm_capacity"))
        day.remaining_tonnes_capacity = _to_float(day.get("available_tonnes_capacity"))
        day.save(ignore_permissions=True)


def _reset_tasks(tasks: list):
    for task in tasks:
        task.remaining_quantity = _to_float(task.get("original_quantity"))
        task.task_status = "Pending"
        task.save(ignore_permissions=True)


def _create_engine_run(scenario, rule_set, input_hash: str):
    run = frappe.new_doc("Mining Schedule Engine Run")
    run.run_name = f"{scenario.name} Rule Based Run"
    run.schedule_scenario = scenario.name
    run.rule_set = rule_set.name
    run.engine_mode = "Rule Based"
    run.run_status = "Running"
    run.started_on = frappe.utils.now_datetime()
    run.started_by = frappe.session.user
    run.input_hash = input_hash
    run.insert(ignore_permissions=True)
    return run


def _fail_engine_run(run, error_message: str):
    run.run_status = "Failed"
    run.completed_on = frappe.utils.now_datetime()
    run.errors_json = json.dumps([error_message], indent=2)
    run.save(ignore_permissions=True)
    frappe.db.commit()


def _complete_engine_run(run, summary: dict, warnings: list[str], output_hash: str):
    run.run_status = "Complete"
    run.completed_on = frappe.utils.now_datetime()
    run.total_tasks = summary.get("total_tasks", 0)
    run.allocated_tasks = summary.get("allocated_tasks", 0)
    run.total_scheduled_bcm = summary.get("total_scheduled_bcm", 0)
    run.total_scheduled_tonnes = summary.get("total_scheduled_tonnes", 0)
    run.warnings_json = json.dumps(warnings, indent=2)
    run.errors_json = json.dumps([], indent=2)
    run.summary_json = json.dumps(summary, indent=2, default=str)
    run.output_hash = output_hash
    run.save(ignore_permissions=True)


def _remaining_capacity(day, unit: str) -> float:
    if unit == "Tonnes":
        return _to_float(day.get("remaining_tonnes_capacity"))

    return _to_float(day.get("remaining_bcm_capacity"))


def _available_capacity(day, unit: str) -> float:
    if unit == "Tonnes":
        return _to_float(day.get("available_tonnes_capacity"))

    return _to_float(day.get("available_bcm_capacity"))


def _capacity_per_hour(day, unit: str) -> float:
    production_hours = _to_float(day.get("production_hours"))

    if production_hours <= 0:
        return 0.0

    available = _available_capacity(day, unit)

    if available <= 0:
        return 0.0

    return available / production_hours


def _use_capacity(day, unit: str, quantity: float):
    quantity = _to_float(quantity)

    if unit == "Tonnes":
        day.scheduled_tonnes = _to_float(day.get("scheduled_tonnes")) + quantity
        day.remaining_tonnes_capacity = max(
            _to_float(day.get("remaining_tonnes_capacity")) - quantity,
            0,
        )
    else:
        day.scheduled_bcm = _to_float(day.get("scheduled_bcm")) + quantity
        day.remaining_bcm_capacity = max(
            _to_float(day.get("remaining_bcm_capacity")) - quantity,
            0,
        )

    day.save(ignore_permissions=True)


def _create_allocation(run, scenario, task, day, sequence_no: int, scheduled_quantity: float, opening_quantity: float):
    closing_quantity = max(opening_quantity - scheduled_quantity, 0)
    capacity_per_hour = _capacity_per_hour(day, task.unit)
    required_hours = scheduled_quantity / capacity_per_hour if capacity_per_hour > 0 else 0

    available_capacity = _available_capacity(day, task.unit)
    capacity_used_percent = (
        (scheduled_quantity / available_capacity) * 100
        if available_capacity > 0
        else 0
    )

    allocation = frappe.new_doc("Mining Schedule Allocation")
    allocation.schedule_scenario = scenario.name
    allocation.engine_run = run.name
    allocation.calendar_day = day.name
    allocation.schedule_task = task.name
    allocation.mining_block = task.get("mining_block")
    allocation.mining_block_code = task.get("mining_block_code")
    allocation.material_seam = task.get("material_seam")
    allocation.allocation_date = day.get("calendar_date")
    allocation.allocation_sequence = sequence_no
    allocation.opening_quantity = opening_quantity
    allocation.scheduled_quantity = scheduled_quantity
    allocation.closing_quantity = closing_quantity
    allocation.unit = task.get("unit")
    allocation.required_hours = required_hours
    allocation.capacity_used_percent = capacity_used_percent
    allocation.is_partial = 1 if closing_quantity > EPSILON else 0
    allocation.allocation_status = "Planned"
    allocation.insert(ignore_permissions=True)

    return allocation


def _predecessors_complete(task, completed_task_keys: set[str]) -> bool:
    predecessors = _safe_json(task.get("predecessor_task_keys"), [])

    for predecessor in predecessors:
        if predecessor not in completed_task_keys:
            return False

    return True


def _update_task_after_allocation(task, remaining_quantity: float, had_allocation: bool):
    task.remaining_quantity = max(remaining_quantity, 0)

    if task.remaining_quantity <= EPSILON:
        task.task_status = "Complete"
    elif had_allocation:
        task.task_status = "In Progress"
    else:
        task.task_status = "Pending"

    task.save(ignore_permissions=True)


def _allocate_task_split_allowed(run, scenario, task, calendar_days: list, allocation_sequence_start: int):
    remaining = _to_float(task.get("remaining_quantity"))
    allocation_sequence = allocation_sequence_start
    had_allocation = False
    allocations = []

    for day in calendar_days:
        if remaining <= EPSILON:
            break

        if not day.get("is_working_day"):
            continue

        day_remaining = _remaining_capacity(day, task.unit)

        if day_remaining <= EPSILON:
            continue

        scheduled_quantity = min(remaining, day_remaining)
        opening_quantity = remaining

        allocation_sequence += 1

        allocation = _create_allocation(
            run=run,
            scenario=scenario,
            task=task,
            day=day,
            sequence_no=allocation_sequence,
            scheduled_quantity=scheduled_quantity,
            opening_quantity=opening_quantity,
        )

        _use_capacity(day, task.unit, scheduled_quantity)

        remaining = max(remaining - scheduled_quantity, 0)
        had_allocation = True
        allocations.append(allocation.name)

    _update_task_after_allocation(task, remaining, had_allocation)

    return {
        "allocation_sequence": allocation_sequence,
        "remaining_quantity": remaining,
        "had_allocation": had_allocation,
        "allocation_names": allocations,
    }


def _allocate_task_no_split(run, scenario, task, calendar_days: list, allocation_sequence_start: int):
    remaining = _to_float(task.get("remaining_quantity"))
    allocation_sequence = allocation_sequence_start
    allocations = []

    for day in calendar_days:
        if not day.get("is_working_day"):
            continue

        day_remaining = _remaining_capacity(day, task.unit)

        if day_remaining + EPSILON < remaining:
            continue

        allocation_sequence += 1

        allocation = _create_allocation(
            run=run,
            scenario=scenario,
            task=task,
            day=day,
            sequence_no=allocation_sequence,
            scheduled_quantity=remaining,
            opening_quantity=remaining,
        )

        _use_capacity(day, task.unit, remaining)

        remaining = 0
        allocations.append(allocation.name)

        break

    _update_task_after_allocation(task, remaining, bool(allocations))

    return {
        "allocation_sequence": allocation_sequence,
        "remaining_quantity": remaining,
        "had_allocation": bool(allocations),
        "allocation_names": allocations,
    }


def generate_rule_schedule_for_scenario(scenario_name: str) -> dict:
    scenario = frappe.get_doc("Mining Schedule Scenario", scenario_name)
    rule_set = _get_approved_rule_set(scenario)
    rules = ScheduleRules.model_validate_json(rule_set.parsed_rules_json)

    calendar_days = _get_calendar_days(scenario.name)
    tasks = _get_tasks(scenario.name)

    input_hash = _hash_payload(
        {
            "scenario": scenario.name,
            "rule_set": rule_set.name,
            "rule_hash": rule_set.get("rule_hash"),
            "calendar_days": [day.name for day in calendar_days],
            "tasks": [task.name for task in tasks],
        }
    )

    _delete_existing_allocations_for_scenario(scenario.name)

    run = _create_engine_run(scenario, rule_set, input_hash)

    warnings = []
    allocations_created = []
    completed_task_keys: set[str] = set()
    allocation_sequence = 0

    try:
        _reset_calendar_days(calendar_days)
        _reset_tasks(tasks)

        allow_split = bool(rules.sequence.allow_partial_blocks)

        for task in tasks:
            if not _predecessors_complete(task, completed_task_keys):
                task.task_status = "Blocked"
                task.save(ignore_permissions=True)
                warnings.append(
                    f"Task {task.task_key} was blocked because predecessor tasks are not complete."
                )
                continue

            if allow_split:
                result = _allocate_task_split_allowed(
                    run=run,
                    scenario=scenario,
                    task=task,
                    calendar_days=calendar_days,
                    allocation_sequence_start=allocation_sequence,
                )
            else:
                result = _allocate_task_no_split(
                    run=run,
                    scenario=scenario,
                    task=task,
                    calendar_days=calendar_days,
                    allocation_sequence_start=allocation_sequence,
                )

            allocation_sequence = result["allocation_sequence"]
            allocations_created.extend(result["allocation_names"])

            task.reload()

            if _to_float(task.get("remaining_quantity")) <= EPSILON:
                completed_task_keys.add(task.get("task_key"))
            else:
                warnings.append(
                    f"Task {task.task_key} was not fully allocated. Remaining quantity: {task.remaining_quantity} {task.unit}."
                )

        total_scheduled_bcm = sum(
            _to_float(
                frappe.db.get_value("Mining Schedule Allocation", name, "scheduled_quantity")
            )
            for name in allocations_created
            if frappe.db.get_value("Mining Schedule Allocation", name, "unit") == "BCM"
        )

        total_scheduled_tonnes = sum(
            _to_float(
                frappe.db.get_value("Mining Schedule Allocation", name, "scheduled_quantity")
            )
            for name in allocations_created
            if frappe.db.get_value("Mining Schedule Allocation", name, "unit") == "Tonnes"
        )

        allocated_tasks = len(
            [
                task.name
                for task in tasks
                if frappe.db.get_value("Mining Schedule Task", task.name, "task_status")
                in ("Complete", "In Progress")
            ]
        )

        summary = {
            "scenario": scenario.name,
            "rule_set": rule_set.name,
            "engine_run": run.name,
            "total_tasks": len(tasks),
            "allocated_tasks": allocated_tasks,
            "allocation_count": len(allocations_created),
            "total_scheduled_bcm": total_scheduled_bcm,
            "total_scheduled_tonnes": total_scheduled_tonnes,
            "warnings_count": len(warnings),
        }

        output_hash = _hash_payload(
            {
                "summary": summary,
                "allocations": allocations_created,
            }
        )

        _complete_engine_run(run, summary, warnings, output_hash)

        if frappe.get_meta("Mining Schedule Scenario").has_field("latest_engine_run"):
            scenario.latest_engine_run = run.name

        scenario.schedule_status = "Generated"
        scenario.generated_on = frappe.utils.now_datetime()
        scenario.generated_by = frappe.session.user
        scenario.save(ignore_permissions=True)

        frappe.db.commit()

        return {
            "scenario": scenario.name,
            "engine_run": run.name,
            "summary": summary,
            "warnings": warnings,
        }

    except Exception as exc:
        _fail_engine_run(run, str(exc))
        frappe.throw(_(str(exc)))


def _fmt(value) -> str:
    try:
        return f"{float(value):,.2f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value or "")


def build_rule_schedule_result_html(result: dict) -> str:
    summary = result.get("summary") or {}

    warning_html = ""

    if result.get("warnings"):
        warning_html = "<h4>Warnings</h4><ul>"
        for warning in result.get("warnings", []):
            warning_html += f"<li>{frappe.utils.escape_html(warning)}</li>"
        warning_html += "</ul>"

    return f"""
    <div>
        <h3>Rule Schedule Generated</h3>

        <p><b>Scenario:</b> {frappe.utils.escape_html(result.get("scenario"))}</p>
        <p><b>Engine Run:</b> {frappe.utils.escape_html(result.get("engine_run"))}</p>

        <table class="table table-bordered table-sm">
            <tbody>
                <tr>
                    <td><b>Total Tasks</b></td>
                    <td>{_fmt(summary.get("total_tasks"))}</td>
                </tr>
                <tr>
                    <td><b>Allocated Tasks</b></td>
                    <td>{_fmt(summary.get("allocated_tasks"))}</td>
                </tr>
                <tr>
                    <td><b>Allocation Rows Created</b></td>
                    <td>{_fmt(summary.get("allocation_count"))}</td>
                </tr>
                <tr>
                    <td><b>Total Scheduled BCM</b></td>
                    <td>{_fmt(summary.get("total_scheduled_bcm"))}</td>
                </tr>
                <tr>
                    <td><b>Total Scheduled Tonnes</b></td>
                    <td>{_fmt(summary.get("total_scheduled_tonnes"))}</td>
                </tr>
                <tr>
                    <td><b>Warnings</b></td>
                    <td>{_fmt(summary.get("warnings_count"))}</td>
                </tr>
            </tbody>
        </table>

        {warning_html}

        <p>
            The rule-based schedule has been generated. Review the allocation rows before approving the scenario.
        </p>
    </div>
    """


@frappe.whitelist()
def generate_rule_schedule(scenario_name: str) -> dict:
    return generate_rule_schedule_for_scenario(scenario_name)


@frappe.whitelist()
def generate_rule_schedule_html(scenario_name: str) -> str:
    result = generate_rule_schedule_for_scenario(scenario_name)
    return build_rule_schedule_result_html(result)