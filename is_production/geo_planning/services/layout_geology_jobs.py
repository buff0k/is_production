import json

import frappe
from frappe.utils import now

from is_production.geo_planning.services.layout_geology_service import (
    run_geology_assignment,
)


def _int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _has_field(doctype, fieldname):
    try:
        return frappe.get_meta(doctype).has_field(fieldname)
    except Exception:
        return False


def _set_doc_field(doc, fieldname, value):
    if _has_field(doc.doctype, fieldname):
        setattr(doc, fieldname, value)


def _safe_json(value):
    try:
        return json.dumps(value, default=str, indent=2)
    except Exception:
        return "{}"


def _db_set_if_field(doctype, name, fieldname, value, update_modified=False):
    if _has_field(doctype, fieldname):
        frappe.db.set_value(
            doctype,
            name,
            fieldname,
            value,
            update_modified=update_modified,
        )


def _update_run_assignment_state(
    geology_run,
    status=None,
    batch=None,
    job_id=None,
    started_on=None,
    completed_on=None,
    error=None,
):
    if not geology_run:
        return

    values = {}

    if status:
        values["processing_status"] = status

    if batch and _has_field("Geo Pit Layout Geology Run", "latest_assignment_batch"):
        values["latest_assignment_batch"] = batch

    if job_id and _has_field("Geo Pit Layout Geology Run", "assignment_job_id"):
        values["assignment_job_id"] = job_id

    if started_on and _has_field("Geo Pit Layout Geology Run", "assignment_started_on"):
        values["assignment_started_on"] = started_on

    if completed_on and _has_field("Geo Pit Layout Geology Run", "assignment_completed_on"):
        values["assignment_completed_on"] = completed_on

    if error is not None and _has_field("Geo Pit Layout Geology Run", "assignment_error"):
        values["assignment_error"] = error

    if values:
        frappe.db.set_value(
            "Geo Pit Layout Geology Run",
            geology_run,
            values,
            update_modified=False,
        )


def _create_batch_from_run(geology_run, clear_existing_results=0, overwrite_existing=1):
    run = frappe.get_doc("Geo Pit Layout Geology Run", geology_run)

    batch = frappe.new_doc("Geo Layout Geology Assignment Batch")
    batch.batch_name = f"Assign Geology - {run.run_name or run.name}"
    batch.geo_project = run.geo_project
    batch.geo_pit_layout = run.geo_pit_layout
    batch.geology_run = run.name
    batch.source_type = run.source_type
    batch.geo_import_batch = run.geo_import_batch
    batch.geo_calculation_batch = run.geo_calculation_batch
    batch.variable_name = run.variable_name
    batch.variable_code = run.get("variable_code")
    batch.value_meaning = run.value_meaning
    batch.rule_enabled = run.rule_enabled
    batch.rule_operator = run.rule_operator
    batch.rule_value = run.rule_value
    batch.rule_value_to = run.rule_value_to
    batch.status = "Queued"
    batch.queued_on = now()
    batch.clear_existing_results = _int(clear_existing_results, 0)
    batch.overwrite_existing = _int(overwrite_existing, 1)
    batch.insert(ignore_permissions=True)

    return batch


@frappe.whitelist()
def enqueue_run_geology_assignment(
    geology_run,
    clear_existing_results=0,
    overwrite_existing=1,
):
    if not geology_run:
        frappe.throw("Geology Run is required.")

    batch = _create_batch_from_run(
        geology_run=geology_run,
        clear_existing_results=clear_existing_results,
        overwrite_existing=overwrite_existing,
    )

    job = frappe.enqueue(
        "is_production.geo_planning.services.layout_geology_jobs.run_geology_assignment_job",
        queue="long",
        timeout=6000,
        batch_name=batch.name,
        geology_run=geology_run,
        clear_existing_results=clear_existing_results,
        overwrite_existing=overwrite_existing,
    )

    job_id = getattr(job, "id", None) or str(job)

    # Important:
    # Do not call batch.save() after enqueue.
    # The background worker may already have opened and saved this batch.
    # Using db.set_value with update_modified=False avoids the Frappe modified-after-open race.
    _db_set_if_field(
        "Geo Layout Geology Assignment Batch",
        batch.name,
        "job_id",
        job_id,
        update_modified=False,
    )

    _update_run_assignment_state(
        geology_run=geology_run,
        status="Queued",
        batch=batch.name,
        job_id=job_id,
        error=None,
    )

    frappe.db.commit()

    return {
        "batch": batch.name,
        "job_id": job_id,
        "status": "Queued",
    }


def run_geology_assignment_job(
    batch_name,
    geology_run,
    clear_existing_results=0,
    overwrite_existing=1,
):
    batch = frappe.get_doc("Geo Layout Geology Assignment Batch", batch_name)

    try:
        batch.status = "Running"
        batch.started_on = now()
        batch.save(ignore_permissions=True)

        _update_run_assignment_state(
            geology_run=geology_run,
            status="Running",
            batch=batch.name,
            started_on=batch.started_on,
            error=None,
        )

        result = run_geology_assignment(
            geology_run=geology_run,
            clear_existing_results=clear_existing_results,
            overwrite_existing=overwrite_existing,
        )

        # Re-read the batch because long-running assignment may have changed timestamps.
        batch = frappe.get_doc("Geo Layout Geology Assignment Batch", batch_name)

        batch.status = "Complete"
        batch.completed_on = now()
        batch.total_blocks = result.get("block_count", 0)
        batch.processed_blocks = result.get("results_checked", 0)
        batch.total_points = result.get("total_points", 0)
        batch.assigned_points = result.get("assigned_points", 0)
        batch.results_created = result.get("results_created", 0)
        batch.results_updated = result.get("results_updated", 0)
        batch.passing_blocks = result.get("passing_blocks", 0)
        batch.failing_blocks = result.get("failing_blocks", 0)
        batch.no_data_blocks = result.get("no_data_blocks", 0)
        batch.progress_percent = 100
        batch.result_json = _safe_json(result)

        if frappe.get_meta(batch.doctype).has_field("remarks"):
            if result.get("update_in_place"):
                batch.remarks = (
                    "Assignment completed in update-in-place mode because downstream "
                    "material values are linked to existing geology results."
                )
            else:
                batch.remarks = "Assignment completed."

        batch.save(ignore_permissions=True)

        _update_run_assignment_state(
            geology_run=geology_run,
            status="Complete",
            batch=batch.name,
            completed_on=batch.completed_on,
            error=None,
        )

        frappe.db.commit()
        return result

    except Exception:
        error = frappe.get_traceback()

        try:
            batch = frappe.get_doc("Geo Layout Geology Assignment Batch", batch_name)
            batch.status = "Error"
            batch.completed_on = now()
            batch.error_count = 1
            batch.error_log = error
            batch.save(ignore_permissions=True)
        except Exception:
            frappe.log_error(error, "Geo Layout Geology Assignment Batch Error")

        _update_run_assignment_state(
            geology_run=geology_run,
            status="Error",
            batch=batch_name,
            completed_on=now(),
            error=error,
        )

        frappe.db.commit()
        raise


@frappe.whitelist()
def run_geology_assignment_now(
    geology_run,
    clear_existing_results=0,
    overwrite_existing=1,
):
    """
    Synchronous helper for development/testing.
    """
    batch = _create_batch_from_run(
        geology_run=geology_run,
        clear_existing_results=clear_existing_results,
        overwrite_existing=overwrite_existing,
    )

    return run_geology_assignment_job(
        batch_name=batch.name,
        geology_run=geology_run,
        clear_existing_results=clear_existing_results,
        overwrite_existing=overwrite_existing,
    )