# apps/is_production/is_production/geo_planning/report/mining_schedule_scenario_comparison/mining_schedule_scenario_comparison.py

from __future__ import annotations

import json

import frappe
from frappe import _


def execute(filters=None):
    filters = frappe._dict(filters or {})

    columns = get_columns()
    data = get_data(filters)
    message = get_message(filters, data)
    report_summary = get_report_summary(data)

    return columns, data, message, None, report_summary


def _to_float(value) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _to_int(value) -> int:
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def _fmt(value) -> str:
    try:
        return f"{float(value):,.2f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value or "")


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


def _has_field(doctype: str, fieldname: str) -> bool:
    try:
        return frappe.get_meta(doctype).has_field(fieldname)
    except Exception:
        return False


def get_columns():
    return [
        {
            "label": _("Scenario"),
            "fieldname": "scenario",
            "fieldtype": "Link",
            "options": "Mining Schedule Scenario",
            "width": 220,
        },
        {
            "label": _("Scenario Name"),
            "fieldname": "scenario_name",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": _("Source Selection"),
            "fieldname": "mining_schedule_selection",
            "fieldtype": "Link",
            "options": "Mining Schedule Selection",
            "width": 200,
        },
        {
            "label": _("Geo Project"),
            "fieldname": "geo_project",
            "fieldtype": "Link",
            "options": "Geo Project",
            "width": 160,
        },
        {
            "label": _("Geo Pit Layout"),
            "fieldname": "geo_pit_layout",
            "fieldtype": "Link",
            "options": "Geo Pit Layout",
            "width": 160,
        },
        {
            "label": _("Schedule Status"),
            "fieldname": "schedule_status",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": _("Rule Parse Status"),
            "fieldname": "rule_parse_status",
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "label": _("Engine Mode"),
            "fieldname": "engine_mode",
            "fieldtype": "Data",
            "width": 110,
        },
        {
            "label": _("Start Date"),
            "fieldname": "start_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": _("End Date"),
            "fieldname": "end_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": _("Latest Engine Run"),
            "fieldname": "latest_engine_run",
            "fieldtype": "Link",
            "options": "Mining Schedule Engine Run",
            "width": 190,
        },
        {
            "label": _("Run Status"),
            "fieldname": "run_status",
            "fieldtype": "Data",
            "width": 110,
        },
        {
            "label": _("Completed On"),
            "fieldname": "completed_on",
            "fieldtype": "Datetime",
            "width": 160,
        },
        {
            "label": _("Total Tasks"),
            "fieldname": "total_tasks",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": _("Allocated Tasks"),
            "fieldname": "allocated_tasks",
            "fieldtype": "Int",
            "width": 120,
        },
        {
            "label": _("Complete Tasks"),
            "fieldname": "complete_tasks",
            "fieldtype": "Int",
            "width": 120,
        },
        {
            "label": _("In Progress Tasks"),
            "fieldname": "in_progress_tasks",
            "fieldtype": "Int",
            "width": 130,
        },
        {
            "label": _("Blocked Tasks"),
            "fieldname": "blocked_tasks",
            "fieldtype": "Int",
            "width": 120,
        },
        {
            "label": _("Pending Tasks"),
            "fieldname": "pending_tasks",
            "fieldtype": "Int",
            "width": 120,
        },
        {
            "label": _("Allocation Rows"),
            "fieldname": "allocation_rows",
            "fieldtype": "Int",
            "width": 120,
        },
        {
            "label": _("Partial Allocations"),
            "fieldname": "partial_allocations",
            "fieldtype": "Int",
            "width": 140,
        },
        {
            "label": _("Scheduled BCM"),
            "fieldname": "scheduled_bcm",
            "fieldtype": "Float",
            "width": 130,
        },
        {
            "label": _("Scheduled Tonnes"),
            "fieldname": "scheduled_tonnes",
            "fieldtype": "Float",
            "width": 140,
        },
        {
            "label": _("Remaining BCM Capacity"),
            "fieldname": "remaining_bcm_capacity",
            "fieldtype": "Float",
            "width": 170,
        },
        {
            "label": _("Remaining Tonnes Capacity"),
            "fieldname": "remaining_tonnes_capacity",
            "fieldtype": "Float",
            "width": 185,
        },
        {
            "label": _("Finish Date"),
            "fieldname": "finish_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": _("First Allocation Date"),
            "fieldname": "first_allocation_date",
            "fieldtype": "Date",
            "width": 150,
        },
        {
            "label": _("Warnings"),
            "fieldname": "warnings",
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "label": _("Errors"),
            "fieldname": "errors",
            "fieldtype": "Int",
            "width": 80,
        },
        {
            "label": _("Rule Set"),
            "fieldname": "rule_set",
            "fieldtype": "Link",
            "options": "Mining Schedule Rule Set",
            "width": 190,
        },
    ]


def get_data(filters):
    scenarios = _get_scenarios(filters)

    rows = []

    for scenario in scenarios:
        latest_run = _get_latest_engine_run(scenario)

        if filters.get("show_only_with_runs") and not latest_run:
            continue

        if filters.get("engine_run_status"):
            selected_status = filters.get("engine_run_status")

            if selected_status == "No Run":
                if latest_run:
                    continue
            elif not latest_run or latest_run.get("run_status") != selected_status:
                continue

        task_summary = _get_task_summary(scenario.name)
        allocation_summary = _get_allocation_summary(
            scenario_name=scenario.name,
            engine_run_name=latest_run.name if latest_run else None,
        )
        capacity_summary = _get_capacity_summary(scenario.name)

        warnings = []
        errors = []

        if latest_run:
            warnings = _safe_json(latest_run.get("warnings_json"), [])
            errors = _safe_json(latest_run.get("errors_json"), [])

        if filters.get("show_only_with_warnings") and not warnings:
            continue

        if filters.get("show_only_with_errors") and not errors:
            continue

        rows.append(
            {
                "scenario": scenario.name,
                "scenario_name": scenario.get("scenario_name"),
                "mining_schedule_selection": scenario.get("mining_schedule_selection"),
                "geo_project": scenario.get("geo_project"),
                "geo_pit_layout": scenario.get("geo_pit_layout"),
                "schedule_status": scenario.get("schedule_status"),
                "rule_parse_status": scenario.get("rule_parse_status"),
                "engine_mode": scenario.get("engine_mode"),
                "start_date": scenario.get("start_date"),
                "end_date": scenario.get("end_date"),
                "latest_engine_run": latest_run.name if latest_run else "",
                "run_status": latest_run.get("run_status") if latest_run else "No Run",
                "completed_on": latest_run.get("completed_on") if latest_run else None,
                "total_tasks": task_summary.get("total_tasks"),
                "allocated_tasks": task_summary.get("allocated_tasks"),
                "complete_tasks": task_summary.get("complete_tasks"),
                "in_progress_tasks": task_summary.get("in_progress_tasks"),
                "blocked_tasks": task_summary.get("blocked_tasks"),
                "pending_tasks": task_summary.get("pending_tasks"),
                "allocation_rows": allocation_summary.get("allocation_rows"),
                "partial_allocations": allocation_summary.get("partial_allocations"),
                "scheduled_bcm": allocation_summary.get("scheduled_bcm"),
                "scheduled_tonnes": allocation_summary.get("scheduled_tonnes"),
                "remaining_bcm_capacity": capacity_summary.get("remaining_bcm_capacity"),
                "remaining_tonnes_capacity": capacity_summary.get("remaining_tonnes_capacity"),
                "finish_date": allocation_summary.get("finish_date"),
                "first_allocation_date": allocation_summary.get("first_allocation_date"),
                "warnings": len(warnings),
                "errors": len(errors),
                "rule_set": scenario.get("active_rule_set"),
            }
        )

    return rows


def _get_scenarios(filters):
    conditions = []
    values = {}

    select_fields = [
        "name",
        "scenario_name",
        "mining_schedule_selection",
        "schedule_status",
        "rule_parse_status",
        "start_date",
        "end_date",
        "active_rule_set",
    ]

    if _has_field("Mining Schedule Scenario", "latest_engine_run"):
        select_fields.append("latest_engine_run")
    else:
        select_fields.append("NULL AS latest_engine_run")

    if _has_field("Mining Schedule Scenario", "engine_mode"):
        select_fields.append("engine_mode")
    else:
        select_fields.append("NULL AS engine_mode")

    if _has_field("Mining Schedule Scenario", "geo_project"):
        select_fields.append("geo_project")
    else:
        select_fields.append("NULL AS geo_project")

    if _has_field("Mining Schedule Scenario", "geo_pit_layout"):
        select_fields.append("geo_pit_layout")
    else:
        select_fields.append("NULL AS geo_pit_layout")

    if filters.get("from_date"):
        conditions.append("start_date >= %(from_date)s")
        values["from_date"] = filters.from_date

    if filters.get("to_date"):
        conditions.append("end_date <= %(to_date)s")
        values["to_date"] = filters.to_date

    if filters.get("schedule_status"):
        conditions.append("schedule_status = %(schedule_status)s")
        values["schedule_status"] = filters.schedule_status

    if filters.get("rule_parse_status"):
        conditions.append("rule_parse_status = %(rule_parse_status)s")
        values["rule_parse_status"] = filters.rule_parse_status

    if filters.get("engine_mode") and _has_field("Mining Schedule Scenario", "engine_mode"):
        conditions.append("engine_mode = %(engine_mode)s")
        values["engine_mode"] = filters.engine_mode

    if filters.get("rule_set"):
        conditions.append("active_rule_set = %(rule_set)s")
        values["rule_set"] = filters.rule_set

    if filters.get("mining_schedule_selection"):
        conditions.append("mining_schedule_selection = %(mining_schedule_selection)s")
        values["mining_schedule_selection"] = filters.mining_schedule_selection

    if filters.get("geo_project") and _has_field("Mining Schedule Scenario", "geo_project"):
        conditions.append("geo_project = %(geo_project)s")
        values["geo_project"] = filters.geo_project

    if filters.get("geo_pit_layout") and _has_field("Mining Schedule Scenario", "geo_pit_layout"):
        conditions.append("geo_pit_layout = %(geo_pit_layout)s")
        values["geo_pit_layout"] = filters.geo_pit_layout

    where_clause = ""

    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    rows = frappe.db.sql(
        f"""
        SELECT
            {", ".join(select_fields)}
        FROM `tabMining Schedule Scenario`
        {where_clause}
        ORDER BY
            creation DESC
        """,
        values,
        as_dict=True,
    )

    if (filters.get("geo_project") or filters.get("geo_pit_layout")) and not (
        _has_field("Mining Schedule Scenario", "geo_project")
        and _has_field("Mining Schedule Scenario", "geo_pit_layout")
    ):
        rows = _filter_by_source_selection(rows, filters)

    return rows


def _filter_by_source_selection(rows, filters):
    filtered_rows = []

    geo_project_filter = filters.get("geo_project")
    geo_pit_layout_filter = filters.get("geo_pit_layout")

    for row in rows:
        selection_name = row.get("mining_schedule_selection")

        if not selection_name or not frappe.db.exists("Mining Schedule Selection", selection_name):
            continue

        selection_values = frappe.db.get_value(
            "Mining Schedule Selection",
            selection_name,
            ["geo_project", "geo_pit_layout"],
            as_dict=True,
        ) or {}

        if geo_project_filter and selection_values.get("geo_project") != geo_project_filter:
            continue

        if geo_pit_layout_filter and selection_values.get("geo_pit_layout") != geo_pit_layout_filter:
            continue

        row["geo_project"] = selection_values.get("geo_project")
        row["geo_pit_layout"] = selection_values.get("geo_pit_layout")

        filtered_rows.append(row)

    return filtered_rows


def _get_latest_engine_run(scenario):
    if scenario.get("latest_engine_run") and frappe.db.exists(
        "Mining Schedule Engine Run",
        scenario.latest_engine_run,
    ):
        return frappe.get_doc("Mining Schedule Engine Run", scenario.latest_engine_run)

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
        run_name = frappe.db.get_value(
            "Mining Schedule Engine Run",
            {
                "schedule_scenario": scenario.name,
            },
            "name",
            order_by="creation desc",
        )

    if not run_name:
        return None

    return frappe.get_doc("Mining Schedule Engine Run", run_name)


def _get_task_summary(scenario_name: str) -> dict:
    rows = frappe.get_all(
        "Mining Schedule Task",
        filters={"schedule_scenario": scenario_name},
        fields=["task_status", "name"],
    )

    complete = len([row for row in rows if row.get("task_status") == "Complete"])
    in_progress = len([row for row in rows if row.get("task_status") == "In Progress"])
    blocked = len([row for row in rows if row.get("task_status") == "Blocked"])
    pending = len([row for row in rows if row.get("task_status") == "Pending"])

    return {
        "total_tasks": len(rows),
        "allocated_tasks": complete + in_progress,
        "complete_tasks": complete,
        "in_progress_tasks": in_progress,
        "blocked_tasks": blocked,
        "pending_tasks": pending,
    }


def _get_allocation_summary(scenario_name: str, engine_run_name: str | None) -> dict:
    if not engine_run_name:
        return {
            "allocation_rows": 0,
            "partial_allocations": 0,
            "scheduled_bcm": 0.0,
            "scheduled_tonnes": 0.0,
            "finish_date": None,
            "first_allocation_date": None,
        }

    rows = frappe.get_all(
        "Mining Schedule Allocation",
        filters={
            "schedule_scenario": scenario_name,
            "engine_run": engine_run_name,
            "allocation_status": ["!=", "Cancelled"],
        },
        fields=[
            "scheduled_quantity",
            "unit",
            "is_partial",
            "allocation_date",
        ],
    )

    scheduled_bcm = 0.0
    scheduled_tonnes = 0.0
    partial_allocations = 0
    first_allocation_date = None
    finish_date = None

    for row in rows:
        if row.get("unit") == "Tonnes":
            scheduled_tonnes += _to_float(row.get("scheduled_quantity"))
        else:
            scheduled_bcm += _to_float(row.get("scheduled_quantity"))

        if row.get("is_partial"):
            partial_allocations += 1

        allocation_date = row.get("allocation_date")

        if allocation_date:
            if not first_allocation_date or allocation_date < first_allocation_date:
                first_allocation_date = allocation_date

            if not finish_date or allocation_date > finish_date:
                finish_date = allocation_date

    return {
        "allocation_rows": len(rows),
        "partial_allocations": partial_allocations,
        "scheduled_bcm": scheduled_bcm,
        "scheduled_tonnes": scheduled_tonnes,
        "finish_date": finish_date,
        "first_allocation_date": first_allocation_date,
    }


def _get_capacity_summary(scenario_name: str) -> dict:
    rows = frappe.get_all(
        "Mining Schedule Calendar Day",
        filters={"schedule_scenario": scenario_name},
        fields=[
            "remaining_bcm_capacity",
            "remaining_tonnes_capacity",
        ],
    )

    return {
        "remaining_bcm_capacity": sum(_to_float(row.get("remaining_bcm_capacity")) for row in rows),
        "remaining_tonnes_capacity": sum(_to_float(row.get("remaining_tonnes_capacity")) for row in rows),
    }


def get_report_summary(data):
    scenario_count = len(data)
    generated_count = len([row for row in data if row.get("schedule_status") == "Generated"])
    reviewed_count = len([row for row in data if row.get("schedule_status") == "Reviewed"])
    approved_count = len([row for row in data if row.get("schedule_status") == "Approved"])
    no_run_count = len([row for row in data if row.get("run_status") == "No Run"])

    total_bcm = sum(_to_float(row.get("scheduled_bcm")) for row in data)
    total_tonnes = sum(_to_float(row.get("scheduled_tonnes")) for row in data)

    total_allocations = sum(_to_int(row.get("allocation_rows")) for row in data)
    total_blocked = sum(_to_int(row.get("blocked_tasks")) for row in data)
    total_pending = sum(_to_int(row.get("pending_tasks")) for row in data)
    total_warnings = sum(_to_int(row.get("warnings")) for row in data)
    total_errors = sum(_to_int(row.get("errors")) for row in data)

    return [
        {
            "label": _("Scenarios"),
            "value": scenario_count,
            "indicator": "Blue",
        },
        {
            "label": _("Generated"),
            "value": generated_count,
            "indicator": "Blue",
        },
        {
            "label": _("Reviewed"),
            "value": reviewed_count,
            "indicator": "Purple",
        },
        {
            "label": _("Approved"),
            "value": approved_count,
            "indicator": "Green",
        },
        {
            "label": _("No Run"),
            "value": no_run_count,
            "indicator": "Gray" if no_run_count else "Green",
        },
        {
            "label": _("Allocations"),
            "value": total_allocations,
            "indicator": "Blue",
        },
        {
            "label": _("Scheduled BCM"),
            "value": _fmt(total_bcm),
            "indicator": "Green",
        },
        {
            "label": _("Scheduled Tonnes"),
            "value": _fmt(total_tonnes),
            "indicator": "Green",
        },
        {
            "label": _("Blocked"),
            "value": total_blocked,
            "indicator": "Red" if total_blocked else "Green",
        },
        {
            "label": _("Pending"),
            "value": total_pending,
            "indicator": "Orange" if total_pending else "Green",
        },
        {
            "label": _("Warnings"),
            "value": total_warnings,
            "indicator": "Orange" if total_warnings else "Green",
        },
        {
            "label": _("Errors"),
            "value": total_errors,
            "indicator": "Red" if total_errors else "Green",
        },
    ]


def get_message(filters, data):
    if not data:
        return """
        <div>
            <b>No scenarios found.</b><br>
            Try widening the date range or clearing some filters.
        </div>
        """

    active_filters = []

    for label, fieldname in [
        ("From Date", "from_date"),
        ("To Date", "to_date"),
        ("Geo Project", "geo_project"),
        ("Geo Pit Layout", "geo_pit_layout"),
        ("Source Selection", "mining_schedule_selection"),
        ("Schedule Status", "schedule_status"),
        ("Rule Parse Status", "rule_parse_status"),
        ("Engine Run Status", "engine_run_status"),
        ("Engine Mode", "engine_mode"),
        ("Rule Set", "rule_set"),
    ]:
        if filters.get(fieldname):
            active_filters.append(
                f"<b>{frappe.utils.escape_html(label)}:</b> {frappe.utils.escape_html(filters.get(fieldname))}"
            )

    if filters.get("show_only_with_runs"):
        active_filters.append("<b>Only Scenarios With Engine Runs:</b> Yes")

    if filters.get("show_only_with_warnings"):
        active_filters.append("<b>Only Scenarios With Warnings:</b> Yes")

    if filters.get("show_only_with_errors"):
        active_filters.append("<b>Only Scenarios With Errors:</b> Yes")

    if not active_filters:
        return """
        <div>
            Showing all Mining Schedule Scenarios.
        </div>
        """

    return f"""
    <div>
        Showing Mining Schedule Scenario comparison for:<br>
        {"<br>".join(active_filters)}
    </div>
    """