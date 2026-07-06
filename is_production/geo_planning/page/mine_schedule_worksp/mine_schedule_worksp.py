# apps/is_production/is_production/geo_planning/page/mine_schedule_worksp/mine_schedule_worksp.py

import frappe


def get_context(context):
    context.no_cache = 1
    context.title = "Mine Schedule Workspace"