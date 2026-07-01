# apps/is_production/is_production/geo_planning/services/mining_schedule_contracts.py

from __future__ import annotations


REQUIRED_SOURCE_OBJECTS = {
    "Mining Schedule Selection": {
        "fields": [
            "geo_project",
            "geo_pit_layout",
            "material_stack",
            "source_filters_json",
        ],
        "child_tables": [
            "blocks",
            "materials",
        ],
    },
    "Mining Schedule Scenario": {
        "fields": [
            "scenario_name",
            "start_date",
            "period_type",
            "status",
        ],
        "child_tables": [],
    },
    "Mining Block": {
        "fields": [
            "mining_block_code",
            "source_pit_layout",
            "cut_no",
            "block_no",
            "row_no",
            "column_no",
            "centroid_x",
            "centroid_y",
            "polygon_geojson",
            "effective_area",
        ],
        "child_tables": [],
    },
}


MATERIAL_DOCTYPE_CANDIDATES = [
    "Mining Block Material Summary",
    "Mining Block Material Value",
]


REQUIRED_MATERIAL_FIELDS = [
    "material_seam",
    "value_type",
    "volume",
    "tonnes",
    "density",
    "material_status",
    "effective_area",
]


PHASE_0_GOVERNANCE_RULES = [
    "Mining Block Selector remains the visual source of selected blocks and mining order.",
    "Mining Schedule Selection remains the frozen saved package of selected blocks and materials.",
    "Mining Schedule Scenario remains the user-facing planning document.",
    "The scheduler must consume saved Mining Schedule Selection rows, not live selector clicks.",
    "Original Mining Block volumes must never be overwritten.",
    "Scheduling and progress must write allocations, ledger rows, and snapshots later.",
]