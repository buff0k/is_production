# apps/is_production/is_production/geo_planning/services/mining_schedule_foundation_service.py

from __future__ import annotations

import frappe

from is_production.geo_planning.services.mining_schedule_contracts import (
    MATERIAL_DOCTYPE_CANDIDATES,
    PHASE_0_GOVERNANCE_RULES,
    REQUIRED_MATERIAL_FIELDS,
    REQUIRED_SOURCE_OBJECTS,
)


def _doctype_exists(doctype: str) -> bool:
    return bool(frappe.db.exists("DocType", doctype))


def _get_fieldnames(doctype: str) -> set[str]:
    meta = frappe.get_meta(doctype)
    return {field.fieldname for field in meta.fields}


def _get_child_table_fields(doctype: str) -> set[str]:
    meta = frappe.get_meta(doctype)
    return {
        field.fieldname
        for field in meta.fields
        if field.fieldtype == "Table"
    }


def _check_required_fields(doctype: str, required_fields: list[str]) -> list[str]:
    existing_fields = _get_fieldnames(doctype)
    return [
        fieldname
        for fieldname in required_fields
        if fieldname not in existing_fields
    ]


def _check_required_child_tables(doctype: str, required_tables: list[str]) -> list[str]:
    existing_tables = _get_child_table_fields(doctype)
    return [
        fieldname
        for fieldname in required_tables
        if fieldname not in existing_tables
    ]


def run_schedule_foundation_validation() -> dict:
    """
    Validates whether the existing mine scheduling foundation is ready.

    This function does not create DocTypes.
    This function does not add fields.
    This function does not generate schedules.
    """

    results = {
        "status": "Passed",
        "missing_doctypes": [],
        "missing_fields": {},
        "missing_child_tables": {},
        "material_doctype_found": None,
        "material_missing_fields": {},
        "governance_rules": PHASE_0_GOVERNANCE_RULES,
    }

    for doctype, contract in REQUIRED_SOURCE_OBJECTS.items():
        if not _doctype_exists(doctype):
            results["missing_doctypes"].append(doctype)
            results["status"] = "Failed"
            continue

        missing_fields = _check_required_fields(
            doctype,
            contract.get("fields", []),
        )
        if missing_fields:
            results["missing_fields"][doctype] = missing_fields
            results["status"] = "Failed"

        missing_child_tables = _check_required_child_tables(
            doctype,
            contract.get("child_tables", []),
        )
        if missing_child_tables:
            results["missing_child_tables"][doctype] = missing_child_tables
            results["status"] = "Failed"

    for material_doctype in MATERIAL_DOCTYPE_CANDIDATES:
        if not _doctype_exists(material_doctype):
            continue

        results["material_doctype_found"] = material_doctype

        missing_material_fields = _check_required_fields(
            material_doctype,
            REQUIRED_MATERIAL_FIELDS,
        )
        if missing_material_fields:
            results["material_missing_fields"][material_doctype] = missing_material_fields
            results["status"] = "Failed"

        break

    if not results["material_doctype_found"]:
        results["missing_doctypes"].append(
            "Mining Block Material Summary or Mining Block Material Value"
        )
        results["status"] = "Failed"

    return results


@frappe.whitelist()
def validate_schedule_foundation() -> dict:
    return run_schedule_foundation_validation()


@frappe.whitelist()
def validate_schedule_foundation_html() -> str:
    result = run_schedule_foundation_validation()

    status = result.get("status")
    indicator = "green" if status == "Passed" else "red"

    html = f"""
    <div>
        <h3>Schedule Foundation Validation</h3>
        <p>
            <b>Status:</b>
            <span class="indicator {indicator}">
                {frappe.utils.escape_html(status)}
            </span>
        </p>
    """

    if result.get("missing_doctypes"):
        html += "<h4>Missing DocTypes</h4><ul>"
        for doctype in result["missing_doctypes"]:
            html += f"<li>{frappe.utils.escape_html(doctype)}</li>"
        html += "</ul>"

    if result.get("missing_fields"):
        html += "<h4>Missing Fields</h4>"
        for doctype, fields in result["missing_fields"].items():
            html += f"<p><b>{frappe.utils.escape_html(doctype)}</b></p><ul>"
            for fieldname in fields:
                html += f"<li>{frappe.utils.escape_html(fieldname)}</li>"
            html += "</ul>"

    if result.get("missing_child_tables"):
        html += "<h4>Missing Child Tables</h4>"
        for doctype, fields in result["missing_child_tables"].items():
            html += f"<p><b>{frappe.utils.escape_html(doctype)}</b></p><ul>"
            for fieldname in fields:
                html += f"<li>{frappe.utils.escape_html(fieldname)}</li>"
            html += "</ul>"

    if result.get("material_doctype_found"):
        html += f"""
        <p>
            <b>Material DocType Found:</b>
            {frappe.utils.escape_html(result["material_doctype_found"])}
        </p>
        """

    if result.get("material_missing_fields"):
        html += "<h4>Material Missing Fields</h4>"
        for doctype, fields in result["material_missing_fields"].items():
            html += f"<p><b>{frappe.utils.escape_html(doctype)}</b></p><ul>"
            for fieldname in fields:
                html += f"<li>{frappe.utils.escape_html(fieldname)}</li>"
            html += "</ul>"

    html += "<h4>Foundation Rules</h4><ul>"
    for rule in result.get("governance_rules", []):
        html += f"<li>{frappe.utils.escape_html(rule)}</li>"
    html += "</ul>"

    html += """
        <p>
            <b>Meaning:</b>
            If this validation passes, the base source documents are ready for rule-driven scheduling.
            If it fails, fix the missing DocTypes, fields or child tables before moving to Phase 1.
        </p>
    </div>
    """

    return html