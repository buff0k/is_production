import frappe 

def execute(filters=None):
    filters = filters or {}
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    site = filters.get("site")

    if not start_date or not end_date or not site:
        frappe.throw("Start Date, End Date and Site are required filters.")

    # --- Get the matching Monthly Production Plan ---
    plans = frappe.get_all(
        "Monthly Production Planning",
        filters={
            "location": site,
            "prod_month_start_date": ["<=", end_date],
            "prod_month_end_date": [">=", start_date],
        },
        fields=[
            "name", "location",
            "monthly_target_bcm", "coal_tons_planned", "coal_planned_bcm", "waste_bcms_planned",
            "total_ts_planned_volumes", "planned_dozer_volumes",
            "num_prod_days", "total_month_prod_hours",
            "month_forecated_bcm",
            "month_actual_coal"   # ✅ coal actual only at parent level
        ],
        order_by="creation desc",
        limit_page_length=1
    )
    if not plans:
        return get_columns(), [{"metric": "No data found", "value": ""}]

    d = plans[0]

    # --- Helper formatter ---
    def fmt_int(val):
        return f"{int(val or 0):,}"

    # --- Tallies (unchanged) ---
    ts_tallies = frappe.db.sql("""
        SELECT COALESCE(SUM(tl.bcms),0)
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.prod_date BETWEEN %s AND %s
          AND hp.location = %s
    """, (start_date, end_date, site))[0][0]

    dozing_tallies = frappe.db.sql("""
        SELECT COALESCE(SUM(dp.bcm_hour),0)
        FROM `tabHourly Production` hp
        JOIN `tabDozer Production` dp ON dp.parent = hp.name
        WHERE hp.prod_date BETWEEN %s AND %s
          AND hp.location = %s
    """, (start_date, end_date, site))[0][0]

    tallies_total = (ts_tallies or 0) + (dozing_tallies or 0)

    coal_bcm_rows = frappe.db.sql("""
        SELECT SUM(tl.bcms) AS coal_bcm
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.prod_date BETWEEN %s AND %s
          AND hp.location = %s
          AND LOWER(tl.mat_type) LIKE '%%coal%%'
    """, (start_date, end_date, site), as_dict=True)

    coal_bcm = coal_bcm_rows[0]["coal_bcm"] or 0
    coal_tons_hp = coal_bcm * 1.5
    coal_bcm_tallies = coal_bcm
    waste_bcm_tallies = tallies_total - coal_bcm_tallies

    # --- Actuals ---
    # BCMs directly from child table
    child_rows = frappe.get_all(
        "Monthly Production Days",
        filters={
            "parent": d.name,
            "shift_start_date": ["between", [start_date, end_date]]
        },
        fields=[
            "shift_start_date",
            "total_ts_bcms", "total_dozing_bcms",
            "shift_day_hours", "shift_night_hours", "shift_morning_hours", "shift_afternoon_hours"
        ]
    )

    ts_actual_bcm = sum(r.get("total_ts_bcms") or 0 for r in child_rows)
    dozing_actual_bcm = sum(r.get("total_dozing_bcms") or 0 for r in child_rows)
    actual_bcm = ts_actual_bcm + dozing_actual_bcm

    # Coal tons from parent (set by update_mtd_production)
    coal_tons_actual = d.month_actual_coal or 0
    coal_bcm_actual = coal_tons_actual / 1.5 if coal_tons_actual else 0
    waste_bcm_actual = actual_bcm - coal_bcm_actual

    # --- Calendar days/hours ---
    from datetime import datetime

    total_days = d.num_prod_days or 0
    total_hours = d.total_month_prod_hours or 0

    completed_days = 0
    completed_hours = 0
    for r in child_rows:
        dt = r.get("shift_start_date")
        if isinstance(dt, str):
            dt = datetime.strptime(dt, "%Y-%m-%d").date()
        if dt and dt.weekday() != 6:  # exclude Sundays
            hrs = (r.get("shift_day_hours") or 0) + (r.get("shift_night_hours") or 0) \
                  + (r.get("shift_morning_hours") or 0) + (r.get("shift_afternoon_hours") or 0)
            if hrs:
                completed_days += 1
                completed_hours += hrs

    remaining_days = total_days - completed_days
    remaining_hours = total_hours - completed_hours

    # --- Build data matrix ---
    data = []

    def add_section(title):
        data.append({"metric": f"<b>{title}</b>", "value": ""})

    # Planning
    add_section("Planning Targets")
    data += [
        {"metric": "Target BCM Total", "value": fmt_int(d.monthly_target_bcm)},
        {"metric": "Target Truck & Shovel BCM", "value": fmt_int(d.total_ts_planned_volumes)},
        {"metric": "Target Dozing BCM", "value": fmt_int(d.planned_dozer_volumes)},
        {"metric": "Waste Planned BCM", "value": fmt_int(d.waste_bcms_planned)},
        {"metric": "Coal Planned BCM", "value": fmt_int(d.coal_planned_bcm)},
        {"metric": "Coal Tons Planned", "value": fmt_int(d.coal_tons_planned)},
    ]

    # Tallies
    add_section("MTD Tallies")
    data += [
        {"metric": "Total Tallies BCMs", "value": fmt_int(tallies_total)},
        {"metric": "TS Tallies BCMs", "value": fmt_int(ts_tallies)},
        {"metric": "Dozing Tallies BCMs", "value": fmt_int(dozing_tallies)},
        {"metric": "Waste Tallies BCMs", "value": fmt_int(waste_bcm_tallies)},
        {"metric": "Coal Tallies BCMs", "value": fmt_int(coal_bcm_tallies)},
        {"metric": "Coal Tallies Tons", "value": fmt_int(coal_tons_hp)},
    ]

    # Actuals (corrected)
    add_section("MTD Actuals")
    data += [
        {"metric": "Actual BCMs", "value": fmt_int(actual_bcm)},
        {"metric": "TS Actual BCMs", "value": fmt_int(ts_actual_bcm)},
        {"metric": "Dozing Actual BCMs", "value": fmt_int(dozing_actual_bcm)},
        {"metric": "Actual Waste BCMs", "value": fmt_int(waste_bcm_actual)},
        {"metric": "Actual Coal BCMs", "value": fmt_int(coal_bcm_actual)},
        {"metric": "Actual Coal Tons", "value": fmt_int(coal_tons_actual)},
    ]

    # Forecast
    add_section("Forecast")
    data.append({"metric": "Forecast BCM", "value": fmt_int(d.month_forecated_bcm)})

    # Calendar Days
    add_section("Calendar (Days)")
    data += [
        {"metric": "Available Days", "value": fmt_int(total_days)},
        {"metric": "Worked Days", "value": fmt_int(completed_days)},
        {"metric": "Remaining Days", "value": fmt_int(remaining_days)},
    ]

    # Calendar Hours
    add_section("Calendar (Hours)")
    data += [
        {"metric": "Available Hours", "value": fmt_int(total_hours)},
        {"metric": "Worked Hours", "value": fmt_int(completed_hours)},
        {"metric": "Remaining Hours", "value": fmt_int(remaining_hours)},
    ]

    # --- Top header message ---
    message = f"<div style='text-align:center; font-size:14px; margin:10px 0;'>" \
              f"<b>Planning Ref:</b> {d.name} &nbsp;&nbsp; | &nbsp;&nbsp; " \
              f"<b>Location:</b> {d.location}</div>"

    return get_columns(), data, None, message


def get_columns():
    return [
        {"label": "Metric", "fieldname": "metric", "fieldtype": "HTML", "width": 300},
        {"label": "Value", "fieldname": "value", "fieldtype": "Data", "width": 200},
    ]


