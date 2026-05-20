import json

import frappe
from frappe.utils import now

from is_production.geo_planning.services.mining_block_service import (
    generate_mining_blocks_from_layout,
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


def _update_batch_field(batch, fieldname, value):
    if _has_field(batch.doctype, fieldname):
        setattr(batch, fieldname, value)


def _create_batch_from_layout(geo_pit_layout, require_final=1, overwrite_existing=0):
    layout = frappe.get_doc("Geo Pit Layout", geo_pit_layout)

    batch = frappe.new_doc("Mining Block Generation Batch")
    batch.batch_name = f"Generate Mining Blocks - {layout.layout_code or layout.name}"
    batch.geo_project = layout.geo_project
    batch.geo_pit_layout = layout.name

    if _has_field(batch.doctype, "require_final"):
        batch.require_final = _int(require_final, 1)

    if _has_field(batch.doctype, "overwrite_existing"):
        batch.overwrite_existing = _int(overwrite_existing, 0)

    if _has_field(batch.doctype, "update_existing"):
        batch.update_existing = 1 if _int(overwrite_existing, 0) else 0

    batch.status = "Queued"
    batch.queued_on = now()
    batch.insert(ignore_permissions=True)

    return batch


@frappe.whitelist()
def enqueue_generate_mining_blocks(
    geo_pit_layout,
    require_final=1,
    overwrite_existing=0,
):
    if not geo_pit_layout:
        frappe.throw("Geo Pit Layout is required.")

    batch = _create_batch_from_layout(
        geo_pit_layout=geo_pit_layout,
        require_final=require_final,
        overwrite_existing=overwrite_existing,
    )

    job = frappe.enqueue(
        "is_production.geo_planning.services.mining_block_jobs.run_generate_mining_blocks",
        queue="long",
        timeout=6000,
        batch_name=batch.name,
        geo_pit_layout=geo_pit_layout,
        require_final=require_final,
        overwrite_existing=overwrite_existing,
    )

    job_id = getattr(job, "id", None) or str(job)

    _db_set_if_field(
        "Mining Block Generation Batch",
        batch.name,
        "job_id",
        job_id,
        update_modified=False,
    )

    frappe.db.commit()

    return {
        "batch": batch.name,
        "job_id": job_id,
        "status": "Queued",
    }


def run_generate_mining_blocks(
    batch_name,
    geo_pit_layout,
    require_final=1,
    overwrite_existing=0,
):
    batch = frappe.get_doc("Mining Block Generation Batch", batch_name)

    try:
        batch.status = "Running"
        batch.started_on = now()
        batch.save(ignore_permissions=True)

        result = generate_mining_blocks_from_layout(
            geo_pit_layout=geo_pit_layout,
            geology_run=None,
            require_final=require_final,
            overwrite_existing=overwrite_existing,
        )

        batch = frappe.get_doc("Mining Block Generation Batch", batch_name)

        batch.status = "Complete"
        batch.completed_on = now()

        _update_batch_field(batch, "total_layout_blocks", result.get("layout_block_count", 0))
        _update_batch_field(batch, "processed_layout_blocks", result.get("layout_block_count", 0))
        _update_batch_field(batch, "mining_blocks_created", result.get("mining_blocks_created", 0))
        _update_batch_field(batch, "mining_blocks_updated", result.get("mining_blocks_updated", 0))
        _update_batch_field(batch, "mining_blocks_skipped", result.get("mining_blocks_skipped", 0))
        _update_batch_field(batch, "error_count", 0)
        _update_batch_field(batch, "progress_percent", 100)
        _update_batch_field(batch, "total_area", result.get("total_area", 0))
        _update_batch_field(batch, "effective_area", result.get("effective_area", 0))
        _update_batch_field(batch, "result_json", _safe_json(result))

        if _has_field(batch.doctype, "remarks"):
            batch.remarks = "Mining Block generation completed."

        batch.save(ignore_permissions=True)

        frappe.db.commit()
        return result

    except Exception:
        error = frappe.get_traceback()

        try:
            batch = frappe.get_doc("Mining Block Generation Batch", batch_name)
            batch.status = "Error"
            batch.completed_on = now()

            if _has_field(batch.doctype, "error_count"):
                batch.error_count = 1

            if _has_field(batch.doctype, "error_log"):
                batch.error_log = error

            batch.save(ignore_permissions=True)
        except Exception:
            frappe.log_error(error, "Mining Block Generation Batch Error")

        frappe.db.commit()
        raise


@frappe.whitelist()
def run_generate_mining_blocks_now(
    geo_pit_layout,
    require_final=1,
    overwrite_existing=0,
):
    batch = _create_batch_from_layout(
        geo_pit_layout=geo_pit_layout,
        require_final=require_final,
        overwrite_existing=overwrite_existing,
    )

    return run_generate_mining_blocks(
        batch_name=batch.name,
        geo_pit_layout=geo_pit_layout,
        require_final=require_final,
        overwrite_existing=overwrite_existing,
    )