import json

import frappe

from is_production.geo_planning.services.mining_schedule_selection_service import (
    create_selection_from_blocks,
    load_selector_data,
)
from is_production.geo_planning.services.mining_spatial_selection_service import (
    get_spatial_overlay as get_spatial_overlay_data,
)


@frappe.whitelist()
def get_selector_data(
    geo_project,
    geo_pit_layout,
    material_stack=None,
    material_seam=None,
):
    return load_selector_data(
        geo_project=geo_project,
        geo_pit_layout=geo_pit_layout,
        material_stack=material_stack,
        material_seam=material_seam,
    )


@frappe.whitelist()
def get_spatial_overlay(
    source_type=None,
    geo_project=None,
    geo_import_batch=None,
    pit_outline_batch=None,
    geo_pit_layout=None,
    outline_mode="Point Order",
):
    return get_spatial_overlay_data(
        source_type=source_type,
        geo_project=geo_project,
        geo_import_batch=geo_import_batch,
        pit_outline_batch=pit_outline_batch,
        geo_pit_layout=geo_pit_layout,
        outline_mode=outline_mode,
    )


@frappe.whitelist()
def save_selection(
    selection_name,
    selection_type,
    geo_project,
    geo_pit_layout,
    material_stack,
    selected_blocks,
    material_seam=None,
    remarks=None,
):
    return create_selection_from_blocks(
        selection_name=selection_name,
        selection_type=selection_type,
        geo_project=geo_project,
        geo_pit_layout=geo_pit_layout,
        material_stack=material_stack,
        material_seam=material_seam,
        remarks=remarks,
        selected_blocks=json.loads(selected_blocks)
        if isinstance(selected_blocks, str)
        else selected_blocks,
    )