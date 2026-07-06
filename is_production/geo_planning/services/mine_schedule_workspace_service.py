# apps/is_production/is_production/geo_planning/services/mine_schedule_workspace_service.py

from __future__ import annotations

import json
from collections import defaultdict

import frappe
from frappe import _


COAL_KEYWORDS = [
    "coal",
    "2u",
    "2l",
    "s2u",
    "s2l",
]

BUCKET_ORDER = [
    "Topsoil",
    "Softs",
    "Hards",
    "Parting",
    "Coal",
    "Other",
]


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


def _is_coal_material(material_name: str) -> bool:
    material = (material_name or "").strip().lower()
    return any(keyword in material for keyword in COAL_KEYWORDS)


def _get_material_bucket(material_name: str) -> str:
    material = (material_name or "").strip()

    if not material:
        return "Other"

    lower = material.lower()

    if "top" in lower or "soil" in lower:
        return "Topsoil"

    if "soft" in lower:
        return "Softs"

    if "hard" in lower or "burden" in lower:
        return "Hards"

    if "part" in lower:
        return "Parting"

    if _is_coal_material(material):
        return "Coal"

    return "Other"


def _get_latest_engine_run(scenario, engine_run_name=None):
    if engine_run_name:
        if not frappe.db.exists("Mining Schedule Engine Run", engine_run_name):
            frappe.throw(_("Selected Engine Run does not exist."))

        engine_run = frappe.get_doc("Mining Schedule Engine Run", engine_run_name)

        if engine_run.get("schedule_scenario") != scenario.name:
            frappe.throw(_("Selected Engine Run does not belong to this Schedule Scenario."))

        return engine_run

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
        frappe.throw(_("No Engine Run found for this Schedule Scenario. Please generate a rule schedule first."))

    return frappe.get_doc("Mining Schedule Engine Run", run_name)


def _get_allocations(scenario_name: str, engine_run_name: str, filters: dict) -> list[dict]:
    query_filters = {
        "schedule_scenario": scenario_name,
        "engine_run": engine_run_name,
        "allocation_status": ["!=", "Cancelled"],
    }

    if filters.get("from_date") and filters.get("to_date"):
        query_filters["allocation_date"] = [
            "between",
            [filters.get("from_date"), filters.get("to_date")],
        ]
    elif filters.get("from_date"):
        query_filters["allocation_date"] = [">=", filters.get("from_date")]
    elif filters.get("to_date"):
        query_filters["allocation_date"] = ["<=", filters.get("to_date")]

    if filters.get("material_seam"):
        query_filters["material_seam"] = filters.get("material_seam")

    if filters.get("mining_block_code"):
        query_filters["mining_block_code"] = filters.get("mining_block_code")

    return frappe.get_all(
        "Mining Schedule Allocation",
        filters=query_filters,
        fields=[
            "name",
            "engine_run",
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


def _get_calendar_rows(scenario_name: str) -> dict:
    rows = frappe.get_all(
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
    )

    return {row.name: row for row in rows}


def _get_task_rows(allocation_rows: list[dict]) -> dict:
    task_names = list({row.get("schedule_task") for row in allocation_rows if row.get("schedule_task")})

    if not task_names:
        return {}

    rows = frappe.get_all(
        "Mining Schedule Task",
        filters={"name": ["in", task_names]},
        fields=[
            "name",
            "task_key",
            "task_status",
            "original_quantity",
            "remaining_quantity",
            "predecessor_task_keys",
        ],
    )

    return {row.name: row for row in rows}


def _get_profile_tasks(scenario_name: str, filters: dict) -> list[dict]:
    query_filters = {
        "schedule_scenario": scenario_name,
    }

    if filters.get("material_seam"):
        query_filters["material_seam"] = filters.get("material_seam")

    if filters.get("mining_block_code"):
        query_filters["mining_block_code"] = filters.get("mining_block_code")

    return frappe.get_all(
        "Mining Schedule Task",
        filters=query_filters,
        fields=[
            "name",
            "mining_block_code",
            "material_seam",
            "unit",
            "original_quantity",
            "remaining_quantity",
            "task_status",
        ],
        order_by="sequence_no asc, material_order asc, creation asc",
    )


def _build_volume_profile(allocation_rows: list[dict], calendar_map: dict) -> list[dict]:
    grouped = {}

    for row in allocation_rows:
        allocation_date = row.get("allocation_date")

        if not allocation_date:
            continue

        date_key = str(allocation_date)

        if date_key not in grouped:
            calendar_row = calendar_map.get(row.get("calendar_day")) or {}

            grouped[date_key] = {
                "allocation_date": allocation_date,
                "day_type": calendar_row.get("day_type"),
                "is_working_day": calendar_row.get("is_working_day"),
                "production_hours": calendar_row.get("production_hours"),
                "topsoil_bcm": 0.0,
                "softs_bcm": 0.0,
                "hards_bcm": 0.0,
                "parting_bcm": 0.0,
                "coal_bcm": 0.0,
                "coal_tonnes": 0.0,
                "other_bcm": 0.0,
                "scheduled_bcm": 0.0,
                "scheduled_tonnes": 0.0,
                "allocation_rows": 0,
                "remaining_bcm_capacity": calendar_row.get("remaining_bcm_capacity"),
                "remaining_tonnes_capacity": calendar_row.get("remaining_tonnes_capacity"),
            }

        qty = _to_float(row.get("scheduled_quantity"))
        material_bucket = _get_material_bucket(row.get("material_seam"))

        grouped[date_key]["allocation_rows"] += 1

        if row.get("unit") == "Tonnes":
            grouped[date_key]["scheduled_tonnes"] += qty

            if material_bucket == "Coal":
                grouped[date_key]["coal_tonnes"] += qty

            continue

        grouped[date_key]["scheduled_bcm"] += qty

        if material_bucket == "Topsoil":
            grouped[date_key]["topsoil_bcm"] += qty
        elif material_bucket == "Softs":
            grouped[date_key]["softs_bcm"] += qty
        elif material_bucket == "Hards":
            grouped[date_key]["hards_bcm"] += qty
        elif material_bucket == "Parting":
            grouped[date_key]["parting_bcm"] += qty
        elif material_bucket == "Coal":
            grouped[date_key]["coal_bcm"] += qty
            grouped[date_key]["coal_tonnes"] += qty * 1.5
        else:
            grouped[date_key]["other_bcm"] += qty

    rows = list(grouped.values())
    rows.sort(key=lambda row: row.get("allocation_date"))

    cumulative_bcm = 0.0
    cumulative_coal_tonnes = 0.0

    for row in rows:
        cumulative_bcm += _to_float(row.get("scheduled_bcm"))
        cumulative_coal_tonnes += _to_float(row.get("coal_tonnes"))
        row["cumulative_bcm"] = cumulative_bcm
        row["cumulative_coal_tonnes"] = cumulative_coal_tonnes

    return rows


def _build_spreadsheet_profile(
    allocation_rows: list[dict],
    profile_tasks: list[dict],
    profile_rows: list[dict],
) -> dict:
    date_columns = [str(row.get("allocation_date")) for row in profile_rows if row.get("allocation_date")]

    moved_by_date_bucket = defaultdict(lambda: defaultdict(float))
    coal_tonnes_by_date = defaultdict(float)
    daily_total_bcm = defaultdict(float)

    for row in allocation_rows:
        allocation_date = row.get("allocation_date")

        if not allocation_date:
            continue

        date_key = str(allocation_date)
        bucket = _get_material_bucket(row.get("material_seam"))
        qty = _to_float(row.get("scheduled_quantity"))

        if row.get("unit") == "Tonnes":
            if bucket == "Coal":
                coal_tonnes_by_date[date_key] += qty
            continue

        moved_by_date_bucket[date_key][bucket] += qty
        daily_total_bcm[date_key] += qty

        if bucket == "Coal":
            coal_tonnes_by_date[date_key] += qty * 1.5

    original_bcm_by_bucket = defaultdict(float)
    original_coal_tonnes = 0.0

    for task in profile_tasks:
        bucket = _get_material_bucket(task.get("material_seam"))
        original_qty = _to_float(task.get("original_quantity"))

        if task.get("unit") == "Tonnes":
            if bucket == "Coal":
                original_coal_tonnes += original_qty
            continue

        original_bcm_by_bucket[bucket] += original_qty

        if bucket == "Coal":
            original_coal_tonnes += original_qty * 1.5

    rows = []

    def add_row(label, row_type, bucket=None, values=None):
        rows.append(
            {
                "label": label,
                "row_type": row_type,
                "bucket": bucket or "",
                "values": values or {},
            }
        )

    add_row(
        "Daily Total BCM",
        "summary",
        values={date: daily_total_bcm.get(date, 0.0) for date in date_columns},
    )

    cumulative_bcm = 0.0
    cumulative_values = {}

    for date in date_columns:
        cumulative_bcm += daily_total_bcm.get(date, 0.0)
        cumulative_values[date] = cumulative_bcm

    add_row("Cumulative BCM", "summary", values=cumulative_values)

    add_row(
        "Coal Tonnes",
        "summary",
        "Coal",
        values={date: coal_tonnes_by_date.get(date, 0.0) for date in date_columns},
    )

    cumulative_coal = 0.0
    cumulative_coal_values = {}

    for date in date_columns:
        cumulative_coal += coal_tonnes_by_date.get(date, 0.0)
        cumulative_coal_values[date] = cumulative_coal

    add_row("Cumulative Coal Tonnes", "summary", "Coal", cumulative_coal_values)

    for bucket in BUCKET_ORDER:
        original_bcm = original_bcm_by_bucket.get(bucket, 0.0)

        if original_bcm <= 0 and bucket != "Coal":
            continue

        moved_values = {}
        remaining_values = {}
        cumulative_moved = 0.0

        for date in date_columns:
            moved = moved_by_date_bucket[date].get(bucket, 0.0)
            cumulative_moved += moved

            moved_values[date] = moved
            remaining_values[date] = max(original_bcm - cumulative_moved, 0.0)

        add_row(f"{bucket} Volume Moved", "moved", bucket, moved_values)
        add_row(f"{bucket} Volume Remaining", "remaining", bucket, remaining_values)

    coal_remaining_values = {}
    cumulative_coal_tonnes = 0.0

    for date in date_columns:
        cumulative_coal_tonnes += coal_tonnes_by_date.get(date, 0.0)
        coal_remaining_values[date] = max(original_coal_tonnes - cumulative_coal_tonnes, 0.0)

    if original_coal_tonnes > 0:
        add_row("Coal Tonnes Remaining", "remaining", "Coal", coal_remaining_values)

    return {
        "date_columns": date_columns,
        "rows": rows,
    }


def _build_schedule_detail(allocation_rows: list[dict], calendar_map: dict, task_map: dict) -> list[dict]:
    detail_rows = []

    for row in allocation_rows:
        calendar_row = calendar_map.get(row.get("calendar_day")) or {}
        task_row = task_map.get(row.get("schedule_task")) or {}

        detail_rows.append(
            {
                "allocation": row.get("name"),
                "allocation_date": row.get("allocation_date"),
                "day_type": calendar_row.get("day_type"),
                "mining_block_code": row.get("mining_block_code"),
                "material_seam": row.get("material_seam"),
                "material_bucket": _get_material_bucket(row.get("material_seam")),
                "opening_quantity": row.get("opening_quantity"),
                "scheduled_quantity": row.get("scheduled_quantity"),
                "closing_quantity": row.get("closing_quantity"),
                "unit": row.get("unit"),
                "is_partial": row.get("is_partial"),
                "required_hours": row.get("required_hours"),
                "capacity_used_percent": row.get("capacity_used_percent"),
                "allocation_status": row.get("allocation_status"),
                "schedule_task": row.get("schedule_task"),
                "task_status": task_row.get("task_status"),
                "task_key": task_row.get("task_key"),
            }
        )

    return detail_rows


def _build_material_summary(allocation_rows: list[dict]) -> list[dict]:
    grouped = defaultdict(
        lambda: {
            "material_seam": "",
            "material_bucket": "",
            "scheduled_bcm": 0.0,
            "scheduled_tonnes": 0.0,
            "allocation_rows": 0,
        }
    )

    for row in allocation_rows:
        material = row.get("material_seam") or "Unknown"
        bucket = _get_material_bucket(material)
        key = material

        grouped[key]["material_seam"] = material
        grouped[key]["material_bucket"] = bucket
        grouped[key]["allocation_rows"] += 1

        qty = _to_float(row.get("scheduled_quantity"))

        if row.get("unit") == "Tonnes":
            grouped[key]["scheduled_tonnes"] += qty
        else:
            grouped[key]["scheduled_bcm"] += qty

            if bucket == "Coal":
                grouped[key]["scheduled_tonnes"] += qty * 1.5

    rows = list(grouped.values())
    rows.sort(key=lambda row: row.get("material_seam") or "")

    return rows


def _build_kpis(scenario, engine_run, profile_rows: list[dict], detail_rows: list[dict]) -> dict:
    total_bcm = sum(_to_float(row.get("scheduled_bcm")) for row in profile_rows)
    total_coal_tonnes = sum(_to_float(row.get("coal_tonnes")) for row in profile_rows)
    total_allocations = len(detail_rows)
    partial_allocations = len([row for row in detail_rows if row.get("is_partial")])
    finish_date = None

    for row in profile_rows:
        if row.get("allocation_date"):
            finish_date = row.get("allocation_date")

    warnings = _safe_json(engine_run.get("warnings_json"), [])
    errors = _safe_json(engine_run.get("errors_json"), [])

    return {
        "scenario": scenario.name,
        "scenario_name": scenario.get("scenario_name"),
        "schedule_status": scenario.get("schedule_status"),
        "engine_run": engine_run.name,
        "run_status": engine_run.get("run_status"),
        "total_scheduled_bcm": total_bcm,
        "total_coal_tonnes": total_coal_tonnes,
        "allocation_rows": total_allocations,
        "partial_allocations": partial_allocations,
        "finish_date": finish_date,
        "warnings": len(warnings),
        "errors": len(errors),
    }


def _build_chart_data(profile_rows: list[dict]) -> dict:
    labels = [str(row.get("allocation_date")) for row in profile_rows]

    return {
        "labels": labels,
        "daily_material_bcm": {
            "labels": labels,
            "datasets": [
                {"name": "Topsoil", "values": [_to_float(row.get("topsoil_bcm")) for row in profile_rows]},
                {"name": "Softs", "values": [_to_float(row.get("softs_bcm")) for row in profile_rows]},
                {"name": "Hards", "values": [_to_float(row.get("hards_bcm")) for row in profile_rows]},
                {"name": "Parting", "values": [_to_float(row.get("parting_bcm")) for row in profile_rows]},
                {"name": "Coal BCM", "values": [_to_float(row.get("coal_bcm")) for row in profile_rows]},
                {"name": "Other", "values": [_to_float(row.get("other_bcm")) for row in profile_rows]},
            ],
        },
        "cumulative_bcm": {
            "labels": labels,
            "datasets": [
                {"name": "Cumulative BCM", "values": [_to_float(row.get("cumulative_bcm")) for row in profile_rows]},
            ],
        },
        "coal_tonnes": {
            "labels": labels,
            "datasets": [
                {"name": "Coal Tonnes", "values": [_to_float(row.get("coal_tonnes")) for row in profile_rows]},
            ],
        },
    }


@frappe.whitelist()
def get_workspace_data(
    schedule_scenario: str,
    engine_run: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    material_seam: str | None = None,
    mining_block_code: str | None = None,
) -> dict:
    if not schedule_scenario:
        frappe.throw(_("Schedule Scenario is required."))

    scenario = frappe.get_doc("Mining Schedule Scenario", schedule_scenario)
    selected_engine_run = _get_latest_engine_run(scenario, engine_run)

    filters = {
        "from_date": from_date,
        "to_date": to_date,
        "material_seam": material_seam,
        "mining_block_code": mining_block_code,
    }

    allocation_rows = _get_allocations(
        scenario_name=scenario.name,
        engine_run_name=selected_engine_run.name,
        filters=filters,
    )

    calendar_map = _get_calendar_rows(scenario.name)
    task_map = _get_task_rows(allocation_rows)
    profile_tasks = _get_profile_tasks(scenario.name, filters)

    profile_rows = _build_volume_profile(allocation_rows, calendar_map)
    spreadsheet_profile = _build_spreadsheet_profile(allocation_rows, profile_tasks, profile_rows)
    detail_rows = _build_schedule_detail(allocation_rows, calendar_map, task_map)
    material_summary = _build_material_summary(allocation_rows)
    kpis = _build_kpis(scenario, selected_engine_run, profile_rows, detail_rows)
    chart_data = _build_chart_data(profile_rows)

    return {
        "kpis": kpis,
        "spreadsheet_profile": spreadsheet_profile,
        "volume_profile": profile_rows,
        "schedule_detail": detail_rows,
        "material_summary": material_summary,
        "chart_data": chart_data,
    }


@frappe.whitelist()
def get_engine_run_options(schedule_scenario: str) -> list[dict]:
    if not schedule_scenario:
        return []

    rows = frappe.get_all(
        "Mining Schedule Engine Run",
        filters={"schedule_scenario": schedule_scenario},
        fields=[
            "name",
            "run_status",
            "started_on",
            "completed_on",
        ],
        order_by="creation desc",
        limit_page_length=50,
    )

    return rows