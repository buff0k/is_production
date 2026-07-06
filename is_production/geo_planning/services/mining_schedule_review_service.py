# apps/is_production/is_production/geo_planning/services/mining_schedule_review_service.py

from __future__ import annotations

import json
from collections import defaultdict

import frappe
from frappe import _


def _to_float(value) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _fmt(value) -> str:
    try:
        return f"{float(value):,.2f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value or "")


def _safe(value) -> str:
    return frappe.utils.escape_html(str(value or ""))


def _safe_json(value, fallback=None):
    if fallback is None:
        fallback = []

    if not value:
        return fallback

    if isinstance(value, (list, dict)):
        return value

    try:
        return json.loads(value)
    except Exception:
        return fallback


def _get_latest_engine_run(scenario):
    latest_engine_run = scenario.get("latest_engine_run")

    if latest_engine_run and frappe.db.exists("Mining Schedule Engine Run", latest_engine_run):
        return frappe.get_doc("Mining Schedule Engine Run", latest_engine_run)

    run_name = frappe.db.get_value(
        "Mining Schedule Engine Run",
        {
            "schedule_scenario": scenario.name,
            "run_status": "Complete",
        },
        "name",
        order_by="creation desc",
    )

    if not run_name:
        frappe.throw(_("No completed Engine Run found for this scenario. Please generate the rule schedule first."))

    return frappe.get_doc("Mining Schedule Engine Run", run_name)


def _get_allocations(scenario_name: str, engine_run: str) -> list[dict]:
    return frappe.get_all(
        "Mining Schedule Allocation",
        filters={
            "schedule_scenario": scenario_name,
            "engine_run": engine_run,
            "allocation_status": ["!=", "Cancelled"],
        },
        fields=[
            "name",
            "calendar_day",
            "schedule_task",
            "mining_block",
            "mining_block_code",
            "material_seam",
            "allocation_date",
            "allocation_sequence",
            "opening_quantity",
            "scheduled_quantity",
            "closing_quantity",
            "unit",
            "required_hours",
            "capacity_used_percent",
            "is_partial",
            "allocation_status",
        ],
        order_by="allocation_date asc, allocation_sequence asc, creation asc",
    )


def _get_calendar_days(scenario_name: str) -> list[dict]:
    return frappe.get_all(
        "Mining Schedule Calendar Day",
        filters={"schedule_scenario": scenario_name},
        fields=[
            "name",
            "calendar_date",
            "day_type",
            "is_working_day",
            "production_hours",
            "available_bcm_capacity",
            "available_tonnes_capacity",
            "scheduled_bcm",
            "scheduled_tonnes",
            "remaining_bcm_capacity",
            "remaining_tonnes_capacity",
        ],
        order_by="calendar_date asc",
    )


def _get_tasks(scenario_name: str) -> list[dict]:
    return frappe.get_all(
        "Mining Schedule Task",
        filters={"schedule_scenario": scenario_name},
        fields=[
            "name",
            "task_key",
            "mining_block_code",
            "material_seam",
            "unit",
            "original_quantity",
            "remaining_quantity",
            "task_status",
        ],
        order_by="sequence_no asc, material_order asc, creation asc",
    )


def _build_overall_summary(engine_run, allocations: list[dict], calendar_days: list[dict], tasks: list[dict]) -> dict:
    total_bcm = 0.0
    total_tonnes = 0.0
    partial_allocations = 0

    for row in allocations:
        qty = _to_float(row.get("scheduled_quantity"))

        if row.get("unit") == "Tonnes":
            total_tonnes += qty
        else:
            total_bcm += qty

        if row.get("is_partial"):
            partial_allocations += 1

    total_available_bcm = sum(_to_float(row.get("available_bcm_capacity")) for row in calendar_days)
    total_available_tonnes = sum(_to_float(row.get("available_tonnes_capacity")) for row in calendar_days)
    total_remaining_bcm = sum(_to_float(row.get("remaining_bcm_capacity")) for row in calendar_days)
    total_remaining_tonnes = sum(_to_float(row.get("remaining_tonnes_capacity")) for row in calendar_days)

    complete_tasks = len([row for row in tasks if row.get("task_status") == "Complete"])
    in_progress_tasks = len([row for row in tasks if row.get("task_status") == "In Progress"])
    blocked_tasks = len([row for row in tasks if row.get("task_status") == "Blocked"])
    pending_tasks = len([row for row in tasks if row.get("task_status") == "Pending"])

    return {
        "engine_run": engine_run.name,
        "run_status": engine_run.get("run_status"),
        "started_on": engine_run.get("started_on"),
        "completed_on": engine_run.get("completed_on"),
        "total_tasks": len(tasks),
        "complete_tasks": complete_tasks,
        "in_progress_tasks": in_progress_tasks,
        "blocked_tasks": blocked_tasks,
        "pending_tasks": pending_tasks,
        "allocation_count": len(allocations),
        "partial_allocations": partial_allocations,
        "total_scheduled_bcm": total_bcm,
        "total_scheduled_tonnes": total_tonnes,
        "total_available_bcm": total_available_bcm,
        "total_available_tonnes": total_available_tonnes,
        "total_remaining_bcm": total_remaining_bcm,
        "total_remaining_tonnes": total_remaining_tonnes,
    }


def _build_daily_summary(calendar_days: list[dict], allocations: list[dict]) -> list[dict]:
    allocation_count_by_day = defaultdict(int)

    for row in allocations:
        allocation_count_by_day[str(row.get("allocation_date"))] += 1

    rows = []

    for day in calendar_days:
        calendar_date = str(day.get("calendar_date"))

        rows.append(
            {
                "calendar_date": calendar_date,
                "day_type": day.get("day_type"),
                "is_working_day": day.get("is_working_day"),
                "production_hours": day.get("production_hours"),
                "available_bcm_capacity": day.get("available_bcm_capacity"),
                "scheduled_bcm": day.get("scheduled_bcm"),
                "remaining_bcm_capacity": day.get("remaining_bcm_capacity"),
                "available_tonnes_capacity": day.get("available_tonnes_capacity"),
                "scheduled_tonnes": day.get("scheduled_tonnes"),
                "remaining_tonnes_capacity": day.get("remaining_tonnes_capacity"),
                "allocation_count": allocation_count_by_day.get(calendar_date, 0),
            }
        )

    return rows


def _build_block_summary(allocations: list[dict]) -> list[dict]:
    grouped = {}

    for row in allocations:
        key = row.get("mining_block_code") or "Unknown Block"

        if key not in grouped:
            grouped[key] = {
                "mining_block_code": key,
                "allocation_count": 0,
                "scheduled_bcm": 0.0,
                "scheduled_tonnes": 0.0,
                "materials": set(),
                "first_date": None,
                "last_date": None,
            }

        grouped[key]["allocation_count"] += 1
        grouped[key]["materials"].add(row.get("material_seam") or "")

        if row.get("unit") == "Tonnes":
            grouped[key]["scheduled_tonnes"] += _to_float(row.get("scheduled_quantity"))
        else:
            grouped[key]["scheduled_bcm"] += _to_float(row.get("scheduled_quantity"))

        allocation_date = row.get("allocation_date")

        if allocation_date:
            if not grouped[key]["first_date"] or allocation_date < grouped[key]["first_date"]:
                grouped[key]["first_date"] = allocation_date

            if not grouped[key]["last_date"] or allocation_date > grouped[key]["last_date"]:
                grouped[key]["last_date"] = allocation_date

    rows = []

    for block_code, data in grouped.items():
        rows.append(
            {
                "mining_block_code": block_code,
                "allocation_count": data["allocation_count"],
                "scheduled_bcm": data["scheduled_bcm"],
                "scheduled_tonnes": data["scheduled_tonnes"],
                "materials": ", ".join(sorted([m for m in data["materials"] if m])),
                "first_date": data["first_date"],
                "last_date": data["last_date"],
            }
        )

    rows.sort(key=lambda row: row.get("mining_block_code") or "")

    return rows


def _build_material_summary(allocations: list[dict]) -> list[dict]:
    grouped = {}

    for row in allocations:
        key = row.get("material_seam") or "Unknown Material"

        if key not in grouped:
            grouped[key] = {
                "material_seam": key,
                "allocation_count": 0,
                "scheduled_bcm": 0.0,
                "scheduled_tonnes": 0.0,
            }

        grouped[key]["allocation_count"] += 1

        if row.get("unit") == "Tonnes":
            grouped[key]["scheduled_tonnes"] += _to_float(row.get("scheduled_quantity"))
        else:
            grouped[key]["scheduled_bcm"] += _to_float(row.get("scheduled_quantity"))

    rows = list(grouped.values())
    rows.sort(key=lambda row: row.get("material_seam") or "")

    return rows


def get_schedule_review_data(scenario_name: str) -> dict:
    scenario = frappe.get_doc("Mining Schedule Scenario", scenario_name)
    engine_run = _get_latest_engine_run(scenario)

    allocations = _get_allocations(scenario.name, engine_run.name)
    calendar_days = _get_calendar_days(scenario.name)
    tasks = _get_tasks(scenario.name)

    if not allocations:
        frappe.throw(_("No allocation rows found for the latest Engine Run."))

    warnings = _safe_json(engine_run.get("warnings_json"), [])
    errors = _safe_json(engine_run.get("errors_json"), [])

    overall = _build_overall_summary(engine_run, allocations, calendar_days, tasks)
    daily_summary = _build_daily_summary(calendar_days, allocations)
    block_summary = _build_block_summary(allocations)
    material_summary = _build_material_summary(allocations)

    return {
        "scenario": scenario.name,
        "scenario_name": scenario.get("scenario_name"),
        "schedule_status": scenario.get("schedule_status"),
        "engine_run": engine_run.name,
        "overall": overall,
        "daily_summary": daily_summary,
        "block_summary": block_summary,
        "material_summary": material_summary,
        "warnings": warnings,
        "errors": errors,
    }


def _overall_table(overall: dict) -> str:
    return f"""
    <table class="table table-bordered table-sm">
        <tbody>
            <tr>
                <td><b>Engine Run</b></td>
                <td>{_safe(overall.get("engine_run"))}</td>
            </tr>
            <tr>
                <td><b>Run Status</b></td>
                <td>{_safe(overall.get("run_status"))}</td>
            </tr>
            <tr>
                <td><b>Total Tasks</b></td>
                <td>{_fmt(overall.get("total_tasks"))}</td>
            </tr>
            <tr>
                <td><b>Complete Tasks</b></td>
                <td>{_fmt(overall.get("complete_tasks"))}</td>
            </tr>
            <tr>
                <td><b>In Progress Tasks</b></td>
                <td>{_fmt(overall.get("in_progress_tasks"))}</td>
            </tr>
            <tr>
                <td><b>Blocked Tasks</b></td>
                <td>{_fmt(overall.get("blocked_tasks"))}</td>
            </tr>
            <tr>
                <td><b>Pending Tasks</b></td>
                <td>{_fmt(overall.get("pending_tasks"))}</td>
            </tr>
            <tr>
                <td><b>Allocation Rows</b></td>
                <td>{_fmt(overall.get("allocation_count"))}</td>
            </tr>
            <tr>
                <td><b>Partial Allocations</b></td>
                <td>{_fmt(overall.get("partial_allocations"))}</td>
            </tr>
            <tr>
                <td><b>Total Scheduled BCM</b></td>
                <td>{_fmt(overall.get("total_scheduled_bcm"))}</td>
            </tr>
            <tr>
                <td><b>Total Scheduled Tonnes</b></td>
                <td>{_fmt(overall.get("total_scheduled_tonnes"))}</td>
            </tr>
            <tr>
                <td><b>Total Remaining BCM Capacity</b></td>
                <td>{_fmt(overall.get("total_remaining_bcm"))}</td>
            </tr>
            <tr>
                <td><b>Total Remaining Tonnes Capacity</b></td>
                <td>{_fmt(overall.get("total_remaining_tonnes"))}</td>
            </tr>
        </tbody>
    </table>
    """


def _daily_table(rows: list[dict]) -> str:
    body = ""

    for row in rows[:31]:
        body += f"""
        <tr>
            <td>{_safe(row.get("calendar_date"))}</td>
            <td>{_safe(row.get("day_type"))}</td>
            <td>{"Yes" if row.get("is_working_day") else "No"}</td>
            <td>{_fmt(row.get("production_hours"))}</td>
            <td>{_fmt(row.get("scheduled_bcm"))}</td>
            <td>{_fmt(row.get("remaining_bcm_capacity"))}</td>
            <td>{_fmt(row.get("scheduled_tonnes"))}</td>
            <td>{_fmt(row.get("remaining_tonnes_capacity"))}</td>
            <td>{_fmt(row.get("allocation_count"))}</td>
        </tr>
        """

    return f"""
    <h4>Daily Review</h4>
    <p class="text-muted">Showing first 31 calendar days.</p>
    <table class="table table-bordered table-sm">
        <thead>
            <tr>
                <th>Date</th>
                <th>Day Type</th>
                <th>Working</th>
                <th>Hours</th>
                <th>Scheduled BCM</th>
                <th>Remaining BCM Capacity</th>
                <th>Scheduled Tonnes</th>
                <th>Remaining Tonnes Capacity</th>
                <th>Allocations</th>
            </tr>
        </thead>
        <tbody>{body}</tbody>
    </table>
    """


def _block_table(rows: list[dict]) -> str:
    body = ""

    for row in rows[:50]:
        body += f"""
        <tr>
            <td>{_safe(row.get("mining_block_code"))}</td>
            <td>{_safe(row.get("materials"))}</td>
            <td>{_safe(row.get("first_date"))}</td>
            <td>{_safe(row.get("last_date"))}</td>
            <td>{_fmt(row.get("scheduled_bcm"))}</td>
            <td>{_fmt(row.get("scheduled_tonnes"))}</td>
            <td>{_fmt(row.get("allocation_count"))}</td>
        </tr>
        """

    return f"""
    <h4>Block Review</h4>
    <p class="text-muted">Showing first 50 blocks.</p>
    <table class="table table-bordered table-sm">
        <thead>
            <tr>
                <th>Block</th>
                <th>Materials</th>
                <th>First Date</th>
                <th>Last Date</th>
                <th>Scheduled BCM</th>
                <th>Scheduled Tonnes</th>
                <th>Allocations</th>
            </tr>
        </thead>
        <tbody>{body}</tbody>
    </table>
    """


def _material_table(rows: list[dict]) -> str:
    body = ""

    for row in rows:
        body += f"""
        <tr>
            <td>{_safe(row.get("material_seam"))}</td>
            <td>{_fmt(row.get("scheduled_bcm"))}</td>
            <td>{_fmt(row.get("scheduled_tonnes"))}</td>
            <td>{_fmt(row.get("allocation_count"))}</td>
        </tr>
        """

    return f"""
    <h4>Material Review</h4>
    <table class="table table-bordered table-sm">
        <thead>
            <tr>
                <th>Material / Seam</th>
                <th>Scheduled BCM</th>
                <th>Scheduled Tonnes</th>
                <th>Allocations</th>
            </tr>
        </thead>
        <tbody>{body}</tbody>
    </table>
    """


def _messages_table(title: str, rows: list) -> str:
    if not rows:
        return ""

    body = ""

    for row in rows:
        body += f"<li>{_safe(row)}</li>"

    return f"""
    <h4>{_safe(title)}</h4>
    <ul>{body}</ul>
    """


def build_schedule_review_html(data: dict) -> str:
    return f"""
    <div>
        <h3>Rule Schedule Review</h3>

        <p><b>Scenario:</b> {_safe(data.get("scenario"))}</p>
        <p><b>Status:</b> {_safe(data.get("schedule_status"))}</p>

        <h4>Overall Summary</h4>
        {_overall_table(data.get("overall") or {})}

        {_messages_table("Warnings", data.get("warnings") or [])}
        {_messages_table("Errors", data.get("errors") or [])}

        {_material_table(data.get("material_summary") or [])}
        {_daily_table(data.get("daily_summary") or [])}
        {_block_table(data.get("block_summary") or [])}

        <p>
            Review these totals before marking the scenario as Reviewed or Approved.
        </p>
    </div>
    """


@frappe.whitelist()
def review_rule_schedule(scenario_name: str) -> dict:
    return get_schedule_review_data(scenario_name)


@frappe.whitelist()
def review_rule_schedule_html(scenario_name: str) -> str:
    data = get_schedule_review_data(scenario_name)
    return build_schedule_review_html(data)