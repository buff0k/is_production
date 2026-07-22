import re

import frappe

def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    """Compact columns — no Hourly Ref column."""
    return [
        {"label": "Parent Plan", "fieldname": "parent", "fieldtype": "Link", "options": "Monthly Production Planning", "width": 120},
        {"label": "Shift Date", "fieldname": "shift_start_date", "fieldtype": "Date", "width": 95},
        {"label": "Day", "fieldname": "day_week", "fieldtype": "Data", "width": 70},
        {"label": "Day Hrs", "fieldname": "shift_day_hours", "fieldtype": "Data", "width": 70},
        {"label": "Night Hrs", "fieldname": "shift_night_hours", "fieldtype": "Data", "width": 70},
        {"label": "Daily BCMs", "fieldname": "total_daily_bcms", "fieldtype": "Data", "width": 95},
        {"label": "Day Shift Material Loaded", "fieldname": "day_material_loaded", "fieldtype": "Data", "width": 210},
        {"label": "Night Shift Material Loaded", "fieldname": "night_material_loaded", "fieldtype": "Data", "width": 210},
        {"label": "Both Shift Material Loaded", "fieldname": "both_shift_material_loaded", "fieldtype": "Data", "width": 230},
        {"label": "TS BCMs", "fieldname": "total_ts_bcms", "fieldtype": "Data", "width": 90},
        {"label": "Dozing BCMs", "fieldname": "total_dozing_bcms", "fieldtype": "Data", "width": 100},
        {"label": "Cum TS BCMs", "fieldname": "cum_ts_bcms", "fieldtype": "Data", "width": 100},
        {"label": "Cum Dozing BCMs", "fieldname": "tot_cumulative_dozing_bcms", "fieldtype": "Data", "width": 110},
        {"label": "Cum Total BCM", "fieldname": "cum_total_bcm", "fieldtype": "Data", "width": 110}
    ]


def get_data(filters):
    """Flat expanded report — all child table rows visible."""
    conditions, params = [], {}

    if filters.get("monthly_production"):
        conditions.append("parent = %(monthly_production)s")
        params["monthly_production"] = filters["monthly_production"]

    if filters.get("site"):
        conditions.append("""
            parent IN (
                SELECT name FROM `tabMonthly Production Planning`
                WHERE location = %(site)s
            )
        """)
        params["site"] = filters["site"]

    if filters.get("start_date"):
        conditions.append("shift_start_date >= %(start_date)s")
        params["start_date"] = filters["start_date"]

    if filters.get("end_date"):
        conditions.append("shift_start_date <= %(end_date)s")
        params["end_date"] = filters["end_date"]

    if filters.get("shift"):
        shift = filters["shift"].lower()
        if shift == "day":
            conditions.append("shift_day_hours > 0")
        elif shift == "night":
            conditions.append("shift_night_hours > 0")

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # --- Query only relevant fields (no hourly_production_reference) ---
    rows = frappe.db.sql(f"""
        SELECT
            parent,
            shift_start_date,
            day_week,
            shift_day_hours,
            shift_night_hours,
            total_daily_bcms,
            total_ts_bcms,
            total_dozing_bcms,
            cum_ts_bcms,
            tot_cumulative_dozing_bcms
        FROM `tabMonthly Production Days`
        WHERE {where_clause}
        ORDER BY parent, shift_start_date ASC
    """, params, as_dict=True)

    material_map = get_material_loaded(rows, filters)

    for row in rows:
        # Compute Cum Total BCM
        ts = row.get("cum_ts_bcms") or 0
        dz = row.get("tot_cumulative_dozing_bcms") or 0
        row["cum_total_bcm"] = ts + dz

        material_date = str(row.get("shift_start_date"))

        day_material = material_map.get(
            (row.get("parent"), material_date, "Day"),
            ""
        )

        night_material = material_map.get(
            (row.get("parent"), material_date, "Night"),
            ""
        )

        row["day_material_loaded"] = day_material
        row["night_material_loaded"] = night_material

        row["both_shift_material_loaded"] = combine_shift_materials(
            day_material,
            night_material
        )

        # Format all numeric fields
        row.update(format_numbers(row))

    return rows


def get_material_loaded(rows, filters):
    """
    Return loaded material and BCM totals for each Monthly Production day.

    Example:
        2 - Hards: 4,320 | 8 - Upper Coal: 1,115
    """
    if not rows:
        return {}

    parents = sorted({
        row.get("parent")
        for row in rows
        if row.get("parent")
    })

    dates = sorted({
        str(row.get("shift_start_date"))
        for row in rows
        if row.get("shift_start_date")
    })

    if not parents or not dates:
        return {}

    conditions = [
        "tl.parenttype = 'Hourly Production'",
        "hp.docstatus < 2",
        "hp.month_prod_planning IN %(parents)s",
        "hp.prod_date BETWEEN %(start_date)s AND %(end_date)s",
        "IFNULL(tl.bcms, 0) > 0"
    ]

    params = {
        "parents": tuple(parents),
        "start_date": dates[0],
        "end_date": dates[-1]
    }

    shift = (filters.get("shift") or "").strip().lower()

    if shift == "day":
        conditions.append("hp.shift IN ('Day', 'Morning')")
    elif shift == "night":
        conditions.append("hp.shift IN ('Night', 'Afternoon')")

    material_rows = frappe.db.sql(
        f"""
        SELECT
            hp.month_prod_planning AS parent_plan,
            hp.prod_date,
            hp.shift,
            COALESCE(
                NULLIF(tl.geo_mat_layer_truck, ''),
                NULLIF(tl.mat_type, ''),
                'Unassigned'
            ) AS material,
            SUM(IFNULL(tl.bcms, 0)) AS total_bcm
        FROM `tabTruck Loads` tl
        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent
        WHERE {" AND ".join(conditions)}
        GROUP BY
            hp.month_prod_planning,
            hp.prod_date,
            hp.shift,
            COALESCE(
                NULLIF(tl.geo_mat_layer_truck, ''),
                NULLIF(tl.mat_type, ''),
                'Unassigned'
            )
        ORDER BY
            hp.month_prod_planning,
            hp.prod_date,
            material
        """,
        params,
        as_dict=True
    )

    grouped = {}

    for item in material_rows:
        raw_shift = (item.get("shift") or "").strip().lower()

        if raw_shift in ("day", "morning"):
            shift_name = "Day"
        elif raw_shift in ("night", "afternoon"):
            shift_name = "Night"
        else:
            shift_name = raw_shift.title() or "Unknown"

        key = (
            item.get("parent_plan"),
            str(item.get("prod_date")),
            shift_name
        )

        total_bcm = int(round(item.get("total_bcm") or 0))
        material = item.get("material") or "Unassigned"

        # Remove prefixes such as "1 - ", "3 - ", or "10 - ".
        material = re.sub(r"^\s*\d+\s*-\s*", "", material).strip()

        grouped.setdefault(key, []).append(
            f"{material}: {total_bcm:,}"
        )

    return {
        key: " | ".join(values)
        for key, values in grouped.items()
    }


def combine_shift_materials(day_material, night_material):
    """
    Combine Day and Night material totals by material name.

    Example:
        Day:   Top Soil: 2,756 | Coal: 742
        Night: Top Soil: 1,937
        Both:  Top Soil: 4,693 | Coal: 742
    """
    combined = {}

    for shift_value in (day_material, night_material):
        if not shift_value:
            continue

        for material_item in shift_value.split(" | "):
            material_item = material_item.strip()

            if not material_item or ":" not in material_item:
                continue

            material, bcm_value = material_item.rsplit(":", 1)
            material = material.strip()

            try:
                bcm = float(
                    bcm_value.strip().replace(",", "")
                )
            except (TypeError, ValueError):
                bcm = 0

            combined[material] = combined.get(material, 0) + bcm

    return " | ".join(
        f"{material}: {int(round(total)):,}"
        for material, total in combined.items()
    )


def format_numbers(row):
    """Format numeric fields with thousand separators and no decimals."""
    numeric_fields = [
        "shift_day_hours", "shift_night_hours",
        "total_daily_bcms", "total_ts_bcms", "total_dozing_bcms",
        "cum_ts_bcms", "tot_cumulative_dozing_bcms", "cum_total_bcm"
    ]
    formatted = {}
    for field in numeric_fields:
        val = row.get(field)
        if val is None:
            formatted[field] = ""
        else:
            try:
                formatted[field] = f"{int(round(val)):,}"
            except Exception:
                formatted[field] = val
    return formatted
