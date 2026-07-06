# apps/is_production/is_production/geo_planning/services/mining_schedule_rule_preview_service.py

from __future__ import annotations

import frappe

from is_production.geo_planning.services.mining_schedule_rule_models import ScheduleRules


def _fmt_number(value: float) -> str:
    try:
        return f"{float(value):,.2f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value)


def _safe(value) -> str:
    return frappe.utils.escape_html(str(value or ""))


def _calculate_day_capacity(rules: ScheduleRules, day_key: str) -> tuple[float, float]:
    day_rule = rules.calendar.get(day_key)

    if not day_rule or not day_rule.working:
        return 0.0, 0.0

    bcm_capacity_per_hour = sum(
        row.count * row.capacity_per_hour
        for row in rules.fleet
        if row.unit == "bcm_per_hour"
    )

    tonnes_capacity_per_hour = sum(
        row.count * row.capacity_per_hour
        for row in rules.fleet
        if row.unit == "tonnes_per_hour"
    )

    factor = (rules.availability_percent / 100) * (rules.utilisation_percent / 100)

    bcm_capacity = day_rule.production_hours * bcm_capacity_per_hour * factor
    tonnes_capacity = day_rule.production_hours * tonnes_capacity_per_hour * factor

    return bcm_capacity, tonnes_capacity


def build_rule_preview_html(rules: ScheduleRules, parse_log: list[dict] | None = None) -> str:
    parse_log = parse_log or []

    calendar_rows = []

    for day_key, label in [
        ("weekday", "Weekday"),
        ("saturday", "Saturday"),
        ("sunday", "Sunday"),
    ]:
        day_rule = rules.calendar.get(day_key)
        bcm_capacity, tonnes_capacity = _calculate_day_capacity(rules, day_key)

        calendar_rows.append(
            f"""
            <tr>
                <td>{_safe(label)}</td>
                <td>{"Yes" if day_rule and day_rule.working else "No"}</td>
                <td>{_fmt_number(day_rule.shifts if day_rule else 0)}</td>
                <td>{_fmt_number(day_rule.production_hours if day_rule else 0)}</td>
                <td>{_fmt_number(bcm_capacity)}</td>
                <td>{_fmt_number(tonnes_capacity)}</td>
            </tr>
            """
        )

    fleet_rows = []

    for row in rules.fleet:
        fleet_rows.append(
            f"""
            <tr>
                <td>{_safe(row.equipment_type)}</td>
                <td>{_fmt_number(row.count)}</td>
                <td>{_fmt_number(row.capacity_per_hour)}</td>
                <td>{_safe(row.unit)}</td>
            </tr>
            """
        )

    material_order = ", ".join(rules.sequence.material_order) or "Not specified"

    warning_rows = []

    for row in parse_log:
        if row.get("status") in ("Warning", "Error"):
            warning_rows.append(
                f"""
                <tr>
                    <td>{_safe(row.get("line_no"))}</td>
                    <td>{_safe(row.get("status"))}</td>
                    <td>{_safe(row.get("source_text"))}</td>
                    <td>{_safe(row.get("message"))}</td>
                </tr>
                """
            )

    warnings_html = ""

    if warning_rows:
        warnings_html = f"""
        <h4>Warnings / Errors</h4>
        <table class="table table-bordered table-sm">
            <thead>
                <tr>
                    <th>Line</th>
                    <th>Status</th>
                    <th>Text</th>
                    <th>Message</th>
                </tr>
            </thead>
            <tbody>{''.join(warning_rows)}</tbody>
        </table>
        """

    return f"""
    <div class="rule-preview">
        <h4>Schedule Rule Preview</h4>

        <h5>Calendar and Capacity</h5>
        <table class="table table-bordered table-sm">
            <thead>
                <tr>
                    <th>Day Type</th>
                    <th>Working</th>
                    <th>Shifts</th>
                    <th>Production Hours</th>
                    <th>Available BCM Capacity</th>
                    <th>Available Tonnes Capacity</th>
                </tr>
            </thead>
            <tbody>{''.join(calendar_rows)}</tbody>
        </table>

        <h5>Fleet</h5>
        <table class="table table-bordered table-sm">
            <thead>
                <tr>
                    <th>Equipment Type</th>
                    <th>Count</th>
                    <th>Capacity / Hour</th>
                    <th>Unit</th>
                </tr>
            </thead>
            <tbody>{''.join(fleet_rows)}</tbody>
        </table>

        <h5>Sequence</h5>
        <p>
            <b>Block Order:</b> {_safe(rules.sequence.block_order)}<br>
            <b>Material Order:</b> {_safe(material_order)}<br>
            <b>Allow Partial Blocks:</b> {"Yes" if rules.sequence.allow_partial_blocks else "No"}
        </p>

        <h5>Factors</h5>
        <p>
            <b>Availability:</b> {_fmt_number(rules.availability_percent)}%<br>
            <b>Utilisation:</b> {_fmt_number(rules.utilisation_percent)}%
        </p>

        {warnings_html}
    </div>
    """