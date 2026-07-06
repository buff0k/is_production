# apps/is_production/is_production/geo_planning/services/mining_schedule_task_service.py

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _

from is_production.geo_planning.services.mining_schedule_rule_models import ScheduleRules


BLOCK_FIELD_CANDIDATES = [
    "mining_block",
    "block",
    "block_name",
    "mining_block_name",
    "selected_block",
]

BLOCK_CODE_FIELD_CANDIDATES = [
    "mining_block_code",
    "block_code",
    "block_name",
    "block",
]

SEQUENCE_FIELD_CANDIDATES = [
    "sequence_no",
    "selected_order",
    "selection_order",
    "idx",
]

CUT_FIELD_CANDIDATES = [
    "cut_no",
    "cut",
]

MATERIAL_BLOCK_FIELD_CANDIDATES = [
    "mining_block",
    "block",
    "block_name",
    "mining_block_code",
    "block_code",
]

MATERIAL_NAME_FIELD_CANDIDATES = [
    "material_seam",
    "material",
    "seam",
    "material_code",
    "geo_ref_description",
]

VOLUME_FIELD_CANDIDATES = [
    "volume",
    "bcm",
    "total_volume",
    "material_volume",
    "volume_bcm",
]

TONNES_FIELD_CANDIDATES = [
    "tonnes",
    "tons",
    "total_tonnes",
    "material_tonnes",
]


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


def _get_first_value(row, candidates: list[str]):
    for fieldname in candidates:
        try:
            value = row.get(fieldname)
        except Exception:
            value = getattr(row, fieldname, None)

        if value not in (None, ""):
            return value

    return None


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


def _clean_key(value) -> str:
    return str(value or "").strip()


def _get_approved_rule_set(scenario):
    if not scenario.get("active_rule_set"):
        frappe.throw(_("Please parse and approve schedule rules first. No Active Rule Set is linked."))

    rule_set = frappe.get_doc("Mining Schedule Rule Set", scenario.active_rule_set)

    if rule_set.get("parser_status") != "Approved":
        frappe.throw(_("The Active Rule Set must be Approved before generating schedule tasks."))

    if not rule_set.get("parsed_rules_json"):
        frappe.throw(_("The Active Rule Set has no Parsed Rules JSON."))

    return rule_set


def _get_source_selection(scenario):
    if not scenario.get("mining_schedule_selection"):
        frappe.throw(_("Mining Schedule Scenario must have a Source Selection."))

    return frappe.get_doc("Mining Schedule Selection", scenario.mining_schedule_selection)


def _delete_docs(doctype: str, names: list[str]):
    for name in names:
        if frappe.db.exists(doctype, name):
            frappe.delete_doc(
                doctype,
                name,
                ignore_permissions=True,
                force=True,
            )


def _delete_existing_tasks_and_downstream_rows(scenario_name: str):
    """
    Safe rebuild cleanup.

    If tasks are regenerated, old allocations and engine runs for this scenario
    should not remain connected to stale task rows.
    """

    allocation_names = frappe.get_all(
        "Mining Schedule Allocation",
        filters={"schedule_scenario": scenario_name},
        pluck="name",
    )
    _delete_docs("Mining Schedule Allocation", allocation_names)

    engine_run_names = frappe.get_all(
        "Mining Schedule Engine Run",
        filters={"schedule_scenario": scenario_name},
        pluck="name",
    )
    _delete_docs("Mining Schedule Engine Run", engine_run_names)

    task_names = frappe.get_all(
        "Mining Schedule Task",
        filters={"schedule_scenario": scenario_name},
        pluck="name",
    )
    _delete_docs("Mining Schedule Task", task_names)

    scenario = frappe.get_doc("Mining Schedule Scenario", scenario_name)

    if frappe.get_meta("Mining Schedule Scenario").has_field("latest_engine_run"):
        scenario.latest_engine_run = None

    if scenario.get("schedule_status") == "Generated":
        scenario.schedule_status = "Draft"

    scenario.save(ignore_permissions=True)

    frappe.db.commit()


def _get_selection_rows(selection, table_fieldname: str) -> list:
    rows = selection.get(table_fieldname) or []
    return list(rows)


def _find_block_child_table(selection) -> str:
    if selection.get("blocks") is not None:
        return "blocks"

    meta = frappe.get_meta("Mining Schedule Selection")
    for field in meta.fields:
        if field.fieldtype == "Table" and "block" in field.fieldname.lower():
            return field.fieldname

    frappe.throw(_("Could not find selected blocks child table on Mining Schedule Selection."))


def _find_material_child_table(selection) -> str:
    if selection.get("materials") is not None:
        return "materials"

    meta = frappe.get_meta("Mining Schedule Selection")
    for field in meta.fields:
        if field.fieldtype == "Table" and (
            "material" in field.fieldname.lower()
            or "seam" in field.fieldname.lower()
        ):
            return field.fieldname

    frappe.throw(_("Could not find materials child table on Mining Schedule Selection."))


def _load_blocks(selection) -> list[dict[str, Any]]:
    table_fieldname = _find_block_child_table(selection)
    rows = _get_selection_rows(selection, table_fieldname)

    blocks = []

    for row in rows:
        block_value = _get_first_value(row, BLOCK_FIELD_CANDIDATES)
        block_code = _get_first_value(row, BLOCK_CODE_FIELD_CANDIDATES) or block_value
        sequence_no = _get_first_value(row, SEQUENCE_FIELD_CANDIDATES)
        cut_no = _get_first_value(row, CUT_FIELD_CANDIDATES)

        if not block_value and not block_code:
            continue

        mining_block = None

        if block_value and frappe.db.exists("Mining Block", block_value):
            mining_block = block_value
        elif block_code and frappe.db.exists("Mining Block", block_code):
            mining_block = block_code

        if mining_block:
            block_doc = frappe.get_doc("Mining Block", mining_block)
            block_code = block_doc.get("mining_block_code") or block_code or mining_block
            cut_no = cut_no if cut_no not in (None, "") else block_doc.get("cut_no")

        blocks.append(
            {
                "mining_block": mining_block,
                "mining_block_code": str(block_code or block_value),
                "sequence_no": _to_int(sequence_no) or row.idx,
                "cut_no": _to_int(cut_no),
                "source_block_row": row.name,
            }
        )

    blocks.sort(key=lambda item: (item.get("sequence_no") or 0, item.get("mining_block_code") or ""))

    return blocks


def _load_materials(selection) -> list[dict[str, Any]]:
    table_fieldname = _find_material_child_table(selection)
    rows = _get_selection_rows(selection, table_fieldname)

    materials = []

    for row in rows:
        block_value = _get_first_value(row, MATERIAL_BLOCK_FIELD_CANDIDATES)
        material_name = _get_first_value(row, MATERIAL_NAME_FIELD_CANDIDATES)

        volume = _to_float(_get_first_value(row, VOLUME_FIELD_CANDIDATES))
        tonnes = _to_float(_get_first_value(row, TONNES_FIELD_CANDIDATES))

        if not material_name:
            continue

        if volume <= 0 and tonnes <= 0:
            continue

        materials.append(
            {
                "block_value": str(block_value or ""),
                "material_seam": str(material_name),
                "volume": volume,
                "tonnes": tonnes,
                "source_material_row": row.name,
            }
        )

    return materials


def _material_matches_block(material: dict, block: dict) -> bool:
    block_value = (material.get("block_value") or "").strip()

    if not block_value:
        return True

    block_code = (block.get("mining_block_code") or "").strip()
    mining_block = (block.get("mining_block") or "").strip()

    return block_value in {block_code, mining_block}


def _get_material_order_map(rules: ScheduleRules) -> dict[str, int]:
    order_map = {}

    for index, material_name in enumerate(rules.sequence.material_order or [], start=1):
        order_map[material_name.strip().lower()] = index

    return order_map


def _get_material_order(material_name: str, order_map: dict[str, int]) -> int:
    key = (material_name or "").strip().lower()
    return order_map.get(key, 999)


def _get_unit_and_quantity(material: dict) -> tuple[str, float]:
    tonnes = _to_float(material.get("tonnes"))
    volume = _to_float(material.get("volume"))

    if tonnes > 0 and volume <= 0:
        return "Tonnes", tonnes

    return "BCM", volume


def _make_task_key(block: dict, material_name: str, counter: int) -> str:
    block_code = _clean_key(block.get("mining_block_code") or block.get("mining_block") or "UNKNOWN-BLOCK")
    material = _clean_key(material_name or "UNKNOWN-MATERIAL")
    return f"{block_code}|{material}|{counter}"


def _build_predecessor_map(block_material_tasks: list[dict]) -> list[dict]:
    previous_task_key = None

    for task in block_material_tasks:
        predecessors = []

        if previous_task_key:
            predecessors.append(previous_task_key)

        task["predecessor_task_keys"] = json.dumps(predecessors)
        previous_task_key = task["task_key"]

    return block_material_tasks


def _insert_task(task_data: dict):
    doc = frappe.new_doc("Mining Schedule Task")

    for fieldname, value in task_data.items():
        doc.set(fieldname, value)

    doc.insert(ignore_permissions=True)

    return doc


def build_tasks_from_selection_for_scenario(scenario_name: str) -> dict:
    scenario = frappe.get_doc("Mining Schedule Scenario", scenario_name)
    rule_set = _get_approved_rule_set(scenario)
    rules = ScheduleRules.model_validate_json(rule_set.parsed_rules_json)
    selection = _get_source_selection(scenario)

    blocks = _load_blocks(selection)
    materials = _load_materials(selection)
    material_order_map = _get_material_order_map(rules)

    if not blocks:
        frappe.throw(_("No selected blocks found in the Source Selection."))

    if not materials:
        frappe.throw(_("No material rows with positive quantities found in the Source Selection."))

    _delete_existing_tasks_and_downstream_rows(scenario.name)

    created_tasks = []
    warnings = []
    task_counter = 0

    for block in blocks:
        block_materials = [
            material
            for material in materials
            if _material_matches_block(material, block)
        ]

        block_materials.sort(
            key=lambda material: (
                _get_material_order(material.get("material_seam"), material_order_map),
                material.get("material_seam") or "",
            )
        )

        staged_tasks = []

        for material in block_materials:
            unit, quantity = _get_unit_and_quantity(material)

            if quantity <= 0:
                warnings.append(
                    f"Skipped {block.get('mining_block_code')} | {material.get('material_seam')} because quantity is zero."
                )
                continue

            task_counter += 1

            task_key = _make_task_key(
                block=block,
                material_name=material.get("material_seam"),
                counter=task_counter,
            )
            material_order = _get_material_order(material.get("material_seam"), material_order_map)

            staged_tasks.append(
                {
                    "schedule_scenario": scenario.name,
                    "rule_set": rule_set.name,
                    "source_selection": selection.name,
                    "mining_block": block.get("mining_block"),
                    "mining_block_code": block.get("mining_block_code"),
                    "sequence_no": block.get("sequence_no"),
                    "cut_no": block.get("cut_no"),
                    "material_seam": material.get("material_seam"),
                    "material_order": material_order,
                    "unit": unit,
                    "original_quantity": quantity,
                    "remaining_quantity": quantity,
                    "task_status": "Pending",
                    "task_key": task_key,
                    "source_block_row": block.get("source_block_row"),
                    "source_material_row": material.get("source_material_row"),
                    "source_rule_hash": rule_set.get("rule_hash"),
                }
            )

        staged_tasks = _build_predecessor_map(staged_tasks)

        for task_data in staged_tasks:
            doc = _insert_task(task_data)

            created_tasks.append(
                {
                    "name": doc.name,
                    "task_key": doc.task_key,
                    "mining_block_code": doc.mining_block_code,
                    "material_seam": doc.material_seam,
                    "unit": doc.unit,
                    "original_quantity": doc.original_quantity,
                    "predecessor_task_keys": doc.predecessor_task_keys,
                }
            )

    frappe.db.commit()

    return {
        "scenario": scenario.name,
        "rule_set": rule_set.name,
        "source_selection": selection.name,
        "block_count": len(blocks),
        "material_row_count": len(materials),
        "task_count": len(created_tasks),
        "warnings": warnings,
        "tasks": created_tasks,
    }


def _fmt(value) -> str:
    try:
        return f"{float(value):,.2f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value or "")


def build_task_result_html(result: dict) -> str:
    warning_html = ""

    if result.get("warnings"):
        warning_html = "<h4>Warnings</h4><ul>"
        for warning in result.get("warnings", []):
            warning_html += f"<li>{frappe.utils.escape_html(warning)}</li>"
        warning_html += "</ul>"

    return f"""
    <div>
        <h3>Schedule Tasks Generated</h3>

        <p><b>Scenario:</b> {frappe.utils.escape_html(result.get("scenario"))}</p>
        <p><b>Rule Set:</b> {frappe.utils.escape_html(result.get("rule_set"))}</p>
        <p><b>Source Selection:</b> {frappe.utils.escape_html(result.get("source_selection"))}</p>

        <table class="table table-bordered table-sm">
            <tbody>
                <tr>
                    <td><b>Selected Blocks Read</b></td>
                    <td>{_fmt(result.get("block_count"))}</td>
                </tr>
                <tr>
                    <td><b>Material Rows Read</b></td>
                    <td>{_fmt(result.get("material_row_count"))}</td>
                </tr>
                <tr>
                    <td><b>Schedule Tasks Created</b></td>
                    <td>{_fmt(result.get("task_count"))}</td>
                </tr>
            </tbody>
        </table>

        {warning_html}

        <p>
            Tasks are now ready for allocation into the capacity calendar.
        </p>
    </div>
    """


@frappe.whitelist()
def build_schedule_tasks(scenario_name: str) -> dict:
    return build_tasks_from_selection_for_scenario(scenario_name)


@frappe.whitelist()
def build_schedule_tasks_html(scenario_name: str) -> str:
    result = build_tasks_from_selection_for_scenario(scenario_name)
    return build_task_result_html(result)