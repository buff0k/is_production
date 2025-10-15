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

    for row in rows:
        # Compute Cum Total BCM
        ts = row.get("cum_ts_bcms") or 0
        dz = row.get("tot_cumulative_dozing_bcms") or 0
        row["cum_total_bcm"] = ts + dz

        # Format all numeric fields
        row.update(format_numbers(row))

    return rows


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
