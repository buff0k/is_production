import json

import frappe
from frappe.utils import now

from is_production.geo_planning.services.pit_layout_service import (
    create_or_update_layout_blocks,
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


def _update_layout_generation_state(
    geo_pit_layout,
    status=None,
    batch=None,
    job_id=None,
    started_on=None,
    completed_on=None,
    error=None,
):
    if not geo_pit_layout:
        return

    values = {}

    if status and _has_field("Geo Pit Layout", "generation_status"):
        values["generation_status"] = status

    if batch and _has_field("Geo Pit Layout", "latest_generation_batch"):
        values["latest_generation_batch"] = batch

    if job_id and _has_field("Geo Pit Layout", "generation_job_id"):
        values["generation_job_id"] = job_id

    if started_on and _has_field("Geo Pit Layout", "generation_started_on"):
        values["generation_started_on"] = started_on

    if completed_on and _has_field("Geo Pit Layout", "generation_completed_on"):
        values["generation_completed_on"] = completed_on

    if error is not None and _has_field("Geo Pit Layout", "generation_error"):
        values["generation_error"] = error

    if values:
        frappe.db.set_value(
            "Geo Pit Layout",
            geo_pit_layout,
            values,
            update_modified=False,
        )


def _create_batch_from_layout(geo_pit_layout, clear_existing_blocks=0, overwrite_existing=1):
    layout = frappe.get_doc("Geo Pit Layout", geo_pit_layout)

    batch = frappe.new_doc("Geo Layout Generation Batch")
    batch.batch_name = f"Generate Blocks - {layout.layout_code or layout.name}"
    batch.geo_project = layout.geo_project
    batch.geo_pit_layout = layout.name
    batch.pit_outline_batch = layout.pit_outline_batch
    batch.block_size_x = layout.block_size_x
    batch.block_size_y = layout.block_size_y
    batch.block_angle_degrees = layout.block_angle_degrees
    batch.minimum_inside_percent = layout.minimum_inside_percent
    batch.default_cut_no = layout.default_cut_no
    batch.numbering_style = layout.numbering_style
    batch.status = "Queued"
    batch.queued_on = now()
    batch.clear_existing_blocks = _int(clear_existing_blocks, 0)
    batch.overwrite_existing = _int(overwrite_existing, 1)
    batch.insert(ignore_permissions=True)

    return batch


@frappe.whitelist()
def enqueue_generate_layout_blocks(
    geo_pit_layout,
    clear_existing_blocks=0,
    overwrite_existing=1,
):
    if not geo_pit_layout:
        frappe.throw("Geo Pit Layout is required.")

    batch = _create_batch_from_layout(
        geo_pit_layout=geo_pit_layout,
        clear_existing_blocks=clear_existing_blocks,
        overwrite_existing=overwrite_existing,
    )

    job = frappe.enqueue(
        "is_production.geo_planning.services.pit_layout_jobs.run_generate_layout_blocks",
        queue="long",
        timeout=6000,
        batch_name=batch.name,
        geo_pit_layout=geo_pit_layout,
        clear_existing_blocks=clear_existing_blocks,
        overwrite_existing=overwrite_existing,
    )

    job_id = getattr(job, "id", None) or str(job)

    # Important:
    # Do not call batch.save() after enqueue.
    # The background worker may already have opened and saved this batch.
    # Using db.set_value with update_modified=False avoids the Frappe
    # "document modified after you opened it" race condition.
    _db_set_if_field(
        "Geo Layout Generation Batch",
        batch.name,
        "job_id",
        job_id,
        update_modified=False,
    )

    _update_layout_generation_state(
        geo_pit_layout=geo_pit_layout,
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


def run_generate_layout_blocks(
    batch_name,
    geo_pit_layout,
    clear_existing_blocks=0,
    overwrite_existing=1,
):
    batch = frappe.get_doc("Geo Layout Generation Batch", batch_name)

    try:
        batch.status = "Running"
        batch.started_on = now()
        batch.save(ignore_permissions=True)

        _update_layout_generation_state(
            geo_pit_layout=geo_pit_layout,
            status="Running",
            batch=batch.name,
            started_on=batch.started_on,
            error=None,
        )

        result = create_or_update_layout_blocks(
            geo_pit_layout=geo_pit_layout,
            clear_existing_blocks=clear_existing_blocks,
            overwrite_existing=overwrite_existing,
        )

        # Re-read the batch because the request/job may have touched it while running.
        batch = frappe.get_doc("Geo Layout Generation Batch", batch_name)

        batch.status = "Complete"
        batch.completed_on = now()
        batch.total_records = result.get("blocks_generated", 0)
        batch.processed_records = result.get("blocks_generated", 0)
        batch.success_count = result.get("blocks_created", 0) + result.get("blocks_updated", 0)
        batch.error_count = 0
        batch.blocks_created = result.get("blocks_created", 0)
        batch.total_area = result.get("total_area", 0)
        batch.effective_area = result.get("effective_area", 0)
        batch.progress_percent = 100
        batch.result_json = _safe_json(result)

        if frappe.get_meta(batch.doctype).has_field("remarks"):
            if result.get("update_in_place"):
                batch.remarks = (
                    "Generation completed in update-in-place mode because downstream "
                    "records are linked to existing layout blocks. Rerun geology assignment "
                    "if block geometry changed."
                )
            else:
                batch.remarks = "Generation completed."

        batch.save(ignore_permissions=True)

        _update_layout_generation_state(
            geo_pit_layout=geo_pit_layout,
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
            batch = frappe.get_doc("Geo Layout Generation Batch", batch_name)
            batch.status = "Error"
            batch.completed_on = now()
            batch.error_count = 1
            batch.error_log = error
            batch.save(ignore_permissions=True)
        except Exception:
            frappe.log_error(error, "Geo Layout Generation Batch Error")

        _update_layout_generation_state(
            geo_pit_layout=geo_pit_layout,
            status="Error",
            batch=batch_name,
            completed_on=now(),
            error=error,
        )

        frappe.db.commit()
        raise


@frappe.whitelist()
def run_generate_layout_blocks_now(
    geo_pit_layout,
    clear_existing_blocks=0,
    overwrite_existing=1,
):
    """
    Synchronous helper for development/testing only.
    """
    batch = _create_batch_from_layout(
        geo_pit_layout=geo_pit_layout,
        clear_existing_blocks=clear_existing_blocks,
        overwrite_existing=overwrite_existing,
    )

    return run_generate_layout_blocks(
        batch_name=batch.name,
        geo_pit_layout=geo_pit_layout,
        clear_existing_blocks=clear_existing_blocks,
        overwrite_existing=overwrite_existing,
    )