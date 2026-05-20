import json

import frappe
from frappe.utils import now

from is_production.geo_planning.services.material_stack_service import (
    attach_material_stack_to_mining_blocks,
)
from is_production.geo_planning.services.material_calculation_service import (
    calculate_material_stack,
)


OP_ATTACH = "Attach Stack"
OP_CALCULATE = "Calculate Values"
OP_ATTACH_AND_CALCULATE = "Attach And Calculate"


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


def _set_if_field(doc, fieldname, value):
    if _has_field(doc.doctype, fieldname):
        setattr(doc, fieldname, value)


def _update_stack_state(
    material_stack,
    operation_type,
    status=None,
    batch=None,
    job_id=None,
    error=None,
):
    if not material_stack:
        return

    values = {}

    if operation_type in (OP_ATTACH, OP_ATTACH_AND_CALCULATE):
        if status and _has_field("Geo Pit Layout Material Stack", "attach_status"):
            values["attach_status"] = status

    if operation_type in (OP_CALCULATE, OP_ATTACH_AND_CALCULATE):
        if status and _has_field("Geo Pit Layout Material Stack", "calculation_status"):
            values["calculation_status"] = status

    if batch and _has_field("Geo Pit Layout Material Stack", "latest_calculation_batch"):
        values["latest_calculation_batch"] = batch

    if job_id and _has_field("Geo Pit Layout Material Stack", "background_job_id"):
        values["background_job_id"] = job_id

    if error is not None and _has_field("Geo Pit Layout Material Stack", "error_log"):
        values["error_log"] = error

    if values:
        frappe.db.set_value(
            "Geo Pit Layout Material Stack",
            material_stack,
            values,
            update_modified=False,
        )


def _create_batch_from_stack(
    material_stack,
    operation_type=OP_ATTACH_AND_CALCULATE,
    create_missing_mining_blocks=1,
    overwrite_existing=0,
    update_block_status=1,
    mineable_only=0,
):
    stack = frappe.get_doc("Geo Pit Layout Material Stack", material_stack)

    batch = frappe.new_doc("Mining Block Material Calculation Batch")
    batch.batch_name = f"{operation_type} - {stack.stack_name or stack.name}"
    batch.geo_project = stack.geo_project
    batch.geo_pit_layout = stack.geo_pit_layout
    batch.material_stack = stack.name
    batch.operation_type = operation_type
    batch.status = "Queued"
    batch.queued_on = now()

    _set_if_field(batch, "create_missing_mining_blocks", _int(create_missing_mining_blocks, 1))
    _set_if_field(batch, "overwrite_existing", _int(overwrite_existing, 0))
    _set_if_field(batch, "update_block_status", _int(update_block_status, 1))
    _set_if_field(batch, "mineable_only", _int(mineable_only, 0))

    batch.insert(ignore_permissions=True)
    return batch


@frappe.whitelist()
def enqueue_material_stack_job(
    material_stack,
    operation_type=OP_ATTACH_AND_CALCULATE,
    create_missing_mining_blocks=1,
    overwrite_existing=0,
    update_block_status=1,
    mineable_only=0,
):
    if not material_stack:
        frappe.throw("Material Stack is required.")

    batch = _create_batch_from_stack(
        material_stack=material_stack,
        operation_type=operation_type,
        create_missing_mining_blocks=create_missing_mining_blocks,
        overwrite_existing=overwrite_existing,
        update_block_status=update_block_status,
        mineable_only=mineable_only,
    )

    job = frappe.enqueue(
        "is_production.geo_planning.services.material_stack_jobs.run_material_stack_job",
        queue="long",
        timeout=6000,
        batch_name=batch.name,
        material_stack=material_stack,
        operation_type=operation_type,
        create_missing_mining_blocks=create_missing_mining_blocks,
        overwrite_existing=overwrite_existing,
        update_block_status=update_block_status,
        mineable_only=mineable_only,
    )

    job_id = getattr(job, "id", None) or str(job)

    _db_set_if_field(
        "Mining Block Material Calculation Batch",
        batch.name,
        "job_id",
        job_id,
        update_modified=False,
    )

    _update_stack_state(
        material_stack=material_stack,
        operation_type=operation_type,
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


def run_material_stack_job(
    batch_name,
    material_stack,
    operation_type=OP_ATTACH_AND_CALCULATE,
    create_missing_mining_blocks=1,
    overwrite_existing=0,
    update_block_status=1,
    mineable_only=0,
):
    batch = frappe.get_doc("Mining Block Material Calculation Batch", batch_name)

    attach_result = {}
    calculation_result = {}

    try:
        batch.status = "Running"
        batch.started_on = now()
        batch.save(ignore_permissions=True)

        _update_stack_state(
            material_stack=material_stack,
            operation_type=operation_type,
            status="Running",
            batch=batch.name,
            error=None,
        )

        if operation_type in (OP_ATTACH, OP_ATTACH_AND_CALCULATE):
            attach_result = attach_material_stack_to_mining_blocks(
                material_stack=material_stack,
                create_missing_mining_blocks=create_missing_mining_blocks,
                overwrite_existing=overwrite_existing,
            )

        if operation_type in (OP_CALCULATE, OP_ATTACH_AND_CALCULATE):
            calculation_result = calculate_material_stack(
                material_stack=material_stack,
                mineable_only=mineable_only,
                update_block_status=update_block_status,
            )

        result = {
            "operation_type": operation_type,
            "attach": attach_result,
            "calculation": calculation_result,
        }

        batch = frappe.get_doc("Mining Block Material Calculation Batch", batch_name)

        batch.status = "Complete"
        batch.completed_on = now()

        _set_if_field(batch, "total_mining_blocks", attach_result.get("mining_block_count", 0))
        _set_if_field(batch, "processed_mining_blocks", calculation_result.get("blocks_touched", 0))
        _set_if_field(batch, "total_stack_items", attach_result.get("stack_item_count", 0))
        _set_if_field(batch, "processed_stack_items", attach_result.get("stack_item_count", 0))
        _set_if_field(batch, "material_values_created", attach_result.get("material_values_created", 0))
        _set_if_field(batch, "material_values_updated", attach_result.get("material_values_updated", 0))
        _set_if_field(batch, "material_values_skipped", attach_result.get("material_values_skipped", 0))
        _set_if_field(batch, "missing_mining_block", attach_result.get("missing_mining_block", 0))
        _set_if_field(batch, "summary_rows_created", calculation_result.get("summary_rows_created", 0))
        _set_if_field(batch, "summary_rows_updated", calculation_result.get("summary_rows_updated", 0))
        _set_if_field(batch, "no_data_count", calculation_result.get("no_data_count", 0))
        _set_if_field(batch, "error_count", calculation_result.get("error_count", 0))
        _set_if_field(batch, "progress_percent", 100)
        _set_if_field(batch, "total_volume", calculation_result.get("total_volume", 0))
        _set_if_field(batch, "total_tonnes", calculation_result.get("total_tonnes", 0))
        _set_if_field(batch, "total_mineable_volume", calculation_result.get("total_mineable_volume", 0))
        _set_if_field(batch, "total_mineable_tonnes", calculation_result.get("total_mineable_tonnes", 0))
        _set_if_field(batch, "result_json", _safe_json(result))

        if _has_field(batch.doctype, "remarks"):
            batch.remarks = "Material stack job completed."

        batch.save(ignore_permissions=True)

        _update_stack_state(
            material_stack=material_stack,
            operation_type=operation_type,
            status="Complete",
            batch=batch.name,
            error=None,
        )

        frappe.db.commit()
        return result

    except Exception:
        error = frappe.get_traceback()

        try:
            batch = frappe.get_doc("Mining Block Material Calculation Batch", batch_name)
            batch.status = "Error"
            batch.completed_on = now()
            _set_if_field(batch, "error_count", 1)
            _set_if_field(batch, "error_log", error)
            batch.save(ignore_permissions=True)
        except Exception:
            frappe.log_error(error, "Mining Block Material Calculation Batch Error")

        _update_stack_state(
            material_stack=material_stack,
            operation_type=operation_type,
            status="Error",
            batch=batch_name,
            error=error,
        )

        frappe.db.commit()
        raise


@frappe.whitelist()
def run_material_stack_job_now(
    material_stack,
    operation_type=OP_ATTACH_AND_CALCULATE,
    create_missing_mining_blocks=1,
    overwrite_existing=0,
    update_block_status=1,
    mineable_only=0,
):
    batch = _create_batch_from_stack(
        material_stack=material_stack,
        operation_type=operation_type,
        create_missing_mining_blocks=create_missing_mining_blocks,
        overwrite_existing=overwrite_existing,
        update_block_status=update_block_status,
        mineable_only=mineable_only,
    )

    return run_material_stack_job(
        batch_name=batch.name,
        material_stack=material_stack,
        operation_type=operation_type,
        create_missing_mining_blocks=create_missing_mining_blocks,
        overwrite_existing=overwrite_existing,
        update_block_status=update_block_status,
        mineable_only=mineable_only,
    )