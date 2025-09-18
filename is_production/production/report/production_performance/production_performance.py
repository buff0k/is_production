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
            "month_actual_coal", "month_actual_bcm", "monthly_act_tally_survey_variance",
            "month_forecated_bcm",
            "num_prod_days", "prod_days_completed", "month_remaining_production_days",
            "total_month_prod_hours", "month_prod_hours_completed", "month_remaining_prod_hours"
        ],
        order_by="creation desc",
        limit_page_length=1
    )
    if not plans:
        return get_columns(), [["No data found", "", "", ""]]
    d = plans[0]

    # --- Helper formatter ---
    def fmt_int(val):
        return f"{int(val or 0):,}"

    # --- TS Tallies BCMs (Production Shift Teams logic) ---
    ts_tallies = frappe.db.sql("""
        SELECT COALESCE(SUM(tl.bcms),0) AS val
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.prod_date BETWEEN %s AND %s
          AND hp.location = %s
    """, (start_date, end_date, site))[0][0]

    # --- Dozing Tallies BCMs (Production Shift Dozing logic) ---
    dozing_tallies = frappe.db.sql("""
        SELECT COALESCE(SUM(dp.bcm_hour),0) AS val
        FROM `tabHourly Production` hp
        JOIN `tabDozer Production` dp ON dp.parent = hp.name
        WHERE hp.prod_date BETWEEN %s AND %s
          AND hp.location = %s
    """, (start_date, end_date, site))[0][0]

    # --- MTD Tallies Total ---
    tallies_total = (ts_tallies or 0) + (dozing_tallies or 0)

    # --- Coal BCMs and Tons (from Truck Loads) ---
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

    # --- Survey refs ---
    survey_refs = frappe.get_all(
        "Survey",
        filters={"monthly_production_plan_ref": d.name, "docstatus": 1},
        fields=["hourly_prod_ref", "total_ts_bcm", "total_dozing_bcm"]
    )
    survey_map = {s["hourly_prod_ref"]: s for s in survey_refs}

    # --- TS & Dozing Actual BCMs (same as Monthly Actual BCMs logic) ---
    ts_actual_bcm = 0
    dozing_actual_bcm = 0

    if survey_map:
        child_rows = frappe.get_all(
            "Monthly Production Days",
            filters={"parent": d.name, "hourly_production_reference": ["in", list(survey_map.keys())]},
            fields=["hourly_production_reference", "shift_start_date"],
        )
        if child_rows:
            latest_row = max(child_rows, key=lambda r: r["shift_start_date"])
            latest_survey_ref = latest_row["hourly_production_reference"]
            latest_survey_date = latest_row["shift_start_date"]

            # Survey base values
            ts_actual_bcm = survey_map[latest_survey_ref]["total_ts_bcm"] or 0
            dozing_actual_bcm = survey_map[latest_survey_ref]["total_dozing_bcm"] or 0

            # Add Hourly Production after survey
            ts_after = frappe.db.sql("""
                SELECT COALESCE(SUM(total_ts_bcm),0)
                FROM `tabHourly Production`
                WHERE month_prod_planning = %s
                  AND prod_date > %s
            """, (d.name, latest_survey_date))[0][0]

            dz_after = frappe.db.sql("""
                SELECT COALESCE(SUM(total_dozing_bcm),0)
                FROM `tabHourly Production`
                WHERE month_prod_planning = %s
                  AND prod_date > %s
            """, (d.name, latest_survey_date))[0][0]

            ts_actual_bcm += ts_after or 0
            dozing_actual_bcm += dz_after or 0
    else:
        # No survey → take all Hourly Production
        ts_actual_bcm = frappe.db.sql("""
            SELECT COALESCE(SUM(total_ts_bcm),0)
            FROM `tabHourly Production`
            WHERE month_prod_planning = %s
              AND prod_date BETWEEN %s AND %s
        """, (d.name, start_date, end_date))[0][0]

        dozing_actual_bcm = frappe.db.sql("""
            SELECT COALESCE(SUM(total_dozing_bcm),0)
            FROM `tabHourly Production`
            WHERE month_prod_planning = %s
              AND prod_date BETWEEN %s AND %s
        """, (d.name, start_date, end_date))[0][0]

    # --- Actual BCMs (from MPP) ---
    actual_bcm = d.month_actual_bcm or 0
    coal_tons_actual = d.month_actual_coal or 0
    coal_bcm_actual = coal_tons_actual / 1.5 if coal_tons_actual else 0
    waste_bcm_actual = actual_bcm - coal_bcm_actual

    # --- Build data matrix ---
    data = [
        ["--- Planning Targets ---", "--- MTD Tallies ---", "--- MTD Actuals ---", ""],

        [f"Target BCM Total: {fmt_int(d.monthly_target_bcm)}",
         f"Total Tallies BCMs: {fmt_int(tallies_total)}",
         f"Actual BCMs: {fmt_int(actual_bcm)}", ""],

        [f"Target Truck & Shovel BCM: {fmt_int(d.total_ts_planned_volumes)}",
         f"TS Tallies BCMs: {fmt_int(ts_tallies)}",
         f"TS Actual BCMs: {fmt_int(ts_actual_bcm)}", ""],

        [f"Target Dozing BCM: {fmt_int(d.planned_dozer_volumes)}",
         f"Dozing Tallies BCMs: {fmt_int(dozing_tallies)}",
         f"Dozing Actual BCMs: {fmt_int(dozing_actual_bcm)}", ""],

        [f"Waste Planned BCM: {fmt_int(d.waste_bcms_planned)}",
         f"Waste Tallies BCMs: {fmt_int(waste_bcm_tallies)}",
         f"Actual Waste BCMs: {fmt_int(waste_bcm_actual)}", ""],

        [f"Coal Planned BCM: {fmt_int(d.coal_planned_bcm)}",
         f"Coal Tallies BCMs: {fmt_int(coal_bcm_tallies)}",
         f"Actual Coal BCMs: {fmt_int(coal_bcm_actual)}", ""],

        [f"Coal Tons Planned: {fmt_int(d.coal_tons_planned)}",
         f"Coal Tallies Tons: {fmt_int(coal_tons_hp)}",
         f"Actual Coal Tons: {fmt_int(coal_tons_actual)}", ""],

        ["", "", "", ""],  # spacer row

        ["--- Forecast ---", "--- Calendar (Days) ---", "--- Calendar (Hours) ---", ""],
        [f"Forecast BCM: {fmt_int(d.month_forecated_bcm)}",
         f"Available: {fmt_int(d.num_prod_days)}",
         f"Available: {fmt_int(d.total_month_prod_hours)}", ""],
        ["",
         f"Worked: {fmt_int(d.prod_days_completed)}",
         f"Worked: {fmt_int(d.month_prod_hours_completed)}", ""],
        ["",
         f"Remaining: {fmt_int(d.month_remaining_production_days)}",
         f"Remaining: {fmt_int(d.month_remaining_prod_hours)}", ""],
    ]

    # --- Top header message ---
    message = f"<div style='text-align:center; font-size:14px; margin:10px 0;'>" \
              f"<b>Planning Ref:</b> {d.name} &nbsp;&nbsp; | &nbsp;&nbsp; " \
              f"<b>Location:</b> {d.location}</div>"

    return get_columns(), data, None, message


def get_columns():
    return [
        {"label": "Planning Targets", "fieldname": "col1", "fieldtype": "Data", "width": 250},
        {"label": "MTD Tallies", "fieldname": "col2", "fieldtype": "Data", "width": 250},
        {"label": "MTD Actuals", "fieldname": "col3", "fieldtype": "Data", "width": 250},
        {"label": "", "fieldname": "col4", "fieldtype": "Data", "width": 50},
    ]
