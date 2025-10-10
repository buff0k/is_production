# Copyright (c) 2025, Isambane Mining (Pty) Ltd
# For license information, please see license.txt

import frappe
from frappe.utils import format_date, getdate


def execute(filters=None):
    if not filters:
        filters = {}

    site = filters.get("site")
    end_date = filters.get("end_date")
    shift = filters.get("shift") or ""

    formatted_date = format_date(end_date) if end_date else ""
    date_obj = getdate(end_date) if end_date else None

    # ===== Monthly Plan =====
    mpp = get_monthly_plan(site, end_date)
    month_start = getdate(mpp.prod_month_start_date) if mpp else None

    # ✅ MTD Actual BCMs
    mtd_actual_bcms = get_actual_bcms_for_date(site, getdate(end_date), month_start, shift) if mpp else 0

    # ✅ MTD Coal
    mtd_coal = get_mtd_coal_dynamic(site, getdate(end_date), month_start, shift)

    # ✅ Actual TS & Dozing for the Day
    actual_ts_day = get_actual_ts_for_day(site, end_date, shift)
    actual_dozer_day = get_actual_dozer_for_day(site, end_date, shift)

    # ✅ Daily Achieved = TS + Dozing
    daily_achieved = actual_ts_day + actual_dozer_day

    # ===== Target Hours per shift/day type =====
    day_type = date_obj.strftime("%A") if date_obj else ""
    base_target_hours = get_target_hours(day_type)
    target_hours = base_target_hours / 2 if shift in ["Day", "Night"] else base_target_hours

    # ===== Equipment Data =====
    excavators = get_asset_data(site, end_date, "Excavator", shift)
    dozers = get_asset_data(site, end_date, "Dozer", shift)

    for ex in excavators:
        ex_name = ex["asset_name"]
        ex["target"] = target_hours
        ex["actual"] = int(round(ex.get("working_hours", 0)))
        ex["mtd_hours"] = get_mtd_hours(site, ex_name, month_start, end_date, "Excavator")
        ex["comment"] = ""

    for dz in dozers:
        dz_name = dz["asset_name"]
        dz["target"] = target_hours
        dz["actual"] = int(round(dz.get("working_hours", 0)))
        dz["mtd_hours"] = get_mtd_hours(site, dz_name, month_start, end_date, "Dozer")
        dz["comment"] = ""

    # ===== Metrics =====
    mtd_waste = mtd_actual_bcms - (mtd_coal / 1.5)

    # ===== Daily Productivity =====
    excavator_prod, dozer_prod = get_daily_productivity(site, getdate(end_date), shift)

    # ===== Build HTML =====
    def fmt(num):
        return f"{int(round(num)):,}" if isinstance(num, (int, float)) else (num or "")

    html = build_html(
        site, shift, formatted_date, mpp,
        excavators, dozers, fmt,
        mtd_coal, mtd_waste,
        actual_ts_day, actual_dozer_day, mtd_actual_bcms,
        excavator_prod, dozer_prod
    )
    return [], None, html


# ---------------------------------------------------------
# Monthly Plan
# ---------------------------------------------------------
def get_monthly_plan(site, date):
    if not site or not date:
        return None
    plan_name = frappe.db.get_value(
        "Monthly Production Planning",
        {"location": site, "prod_month_start_date": ["<=", date], "prod_month_end_date": [">=", date]},
        "name",
    )
    return frappe.get_doc("Monthly Production Planning", plan_name) if plan_name else None


# ---------------------------------------------------------
# Asset Data
# ---------------------------------------------------------
def get_asset_data(site, date, category, shift=None):
    if not site or not date:
        return []

    filters = {"location": site, "shift_date": date, "docstatus": ["<", 2]}
    if shift:
        filters["shift"] = shift

    pre_use_names = frappe.get_all("Pre-Use Hours", filters=filters, fields=["name"])
    if not pre_use_names:
        return []

    pre_use_list = [p.name for p in pre_use_names]
    assets = frappe.get_all(
        "Pre-use Assets",
        filters={"parent": ["in", pre_use_list], "asset_category": category},
        fields=["asset_name", "working_hours"]
    )

    combined = {}
    for a in assets:
        if not a.asset_name:
            continue
        combined[a.asset_name] = combined.get(a.asset_name, 0) + (a.working_hours or 0)

    return [{"asset_name": k, "working_hours": v} for k, v in combined.items()]


# ---------------------------------------------------------
# Target Hours per Day Type
# ---------------------------------------------------------
def get_target_hours(day_name):
    day_name = (day_name or "").lower()
    if day_name in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
        return 18
    elif day_name == "saturday":
        return 14
    elif day_name == "sunday":
        return 7
    return 0


# ---------------------------------------------------------
# Get MTD Hours for an Asset
# ---------------------------------------------------------
def get_mtd_hours(site, asset_name, month_start, end_date, category):
    if not (site and asset_name and month_start and end_date):
        return 0

    pre_use_docs = frappe.get_all(
        "Pre-Use Hours",
        filters={"location": site, "shift_date": ["between", [month_start, end_date]], "docstatus": ["<", 2]},
        fields=["name"]
    )
    if not pre_use_docs:
        return 0

    pre_use_names = [p.name for p in pre_use_docs]
    assets = frappe.get_all(
        "Pre-use Assets",
        filters={"parent": ["in", pre_use_names], "asset_name": asset_name, "asset_category": category},
        fields=["working_hours"]
    )

    return sum(a.working_hours or 0 for a in assets)


# ---------------------------------------------------------
# ✅ MTD Actual BCMs
# ---------------------------------------------------------
def get_actual_bcms_for_date(site, end_date, month_start, shift=None):
    if not site or not end_date:
        return 0

    ts_actual_bcm = frappe.db.sql("""
        SELECT COALESCE(SUM(tl.bcms),0)
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.prod_date BETWEEN %s AND %s
          AND hp.location = %s
    """, (month_start, end_date, site))[0][0]

    dozing_actual_bcm = frappe.db.sql("""
        SELECT COALESCE(SUM(dp.bcm_hour),0)
        FROM `tabHourly Production` hp
        JOIN `tabDozer Production` dp ON dp.parent = hp.name
        WHERE hp.prod_date BETWEEN %s AND %s
          AND hp.location = %s
    """, (month_start, end_date, site))[0][0]

    return (ts_actual_bcm or 0) + (dozing_actual_bcm or 0)


# ---------------------------------------------------------
# ✅ MTD Coal
# ---------------------------------------------------------
def get_mtd_coal_dynamic(site, end_date, month_start, shift=None):
    if not site or not end_date:
        return 0
    COAL_CONVERSION = 1.5
    coal_after = frappe.db.sql("""
        SELECT COALESCE(SUM(tl.bcms),0)
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.prod_date BETWEEN %s AND %s
          AND hp.location = %s
          AND LOWER(tl.mat_type) LIKE '%%coal%%'
    """, (month_start, end_date, site))[0][0]
    return (coal_after or 0) * COAL_CONVERSION


# ---------------------------------------------------------
# ✅ Actual TS and Dozing for the Day
# ---------------------------------------------------------
def get_actual_ts_for_day(site, date, shift=None):
    if not site or not date:
        return 0
    shift_condition = "AND shift = %s" if shift else ""
    shift_params = (shift,) if shift else ()
    result = frappe.db.sql(
        f"""
        SELECT SUM(total_ts_bcm) AS total_bcm
        FROM `tabHourly Production`
        WHERE location = %s AND prod_date = %s {shift_condition}
        """,
        (site, date, *shift_params),
        as_dict=True
    )
    return result[0].total_bcm or 0


def get_actual_dozer_for_day(site, date, shift=None):
    if not site or not date:
        return 0
    shift_condition = "AND shift = %s" if shift else ""
    shift_params = (shift,) if shift else ()
    result = frappe.db.sql(
        f"""
        SELECT SUM(total_dozing_bcm) AS total_bcm
        FROM `tabHourly Production`
        WHERE location = %s AND prod_date = %s {shift_condition}
        """,
        (site, date, *shift_params),
        as_dict=True
    )
    return result[0].total_bcm or 0


# ---------------------------------------------------------
# ✅ Daily Productivity (summarized)
# ---------------------------------------------------------
def get_daily_productivity(site, date, shift=None):
    if not (site and date):
        return [], []

    COAL_CONVERSION = 1.5
    values = {"date": date, "site": site, "shift": shift}

    shift_condition_hp = "AND hp.shift = %(shift)s" if shift else ""
    shift_condition_pu = "AND pu.shift = %(shift)s" if shift else ""

    truck_rows = frappe.db.sql(f"""
        SELECT
            tl.asset_name_shoval AS excavator,
            SUM(tl.bcms) AS bcm_output,
            GROUP_CONCAT(DISTINCT tl.mat_type) AS mat_types
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.prod_date = %(date)s
          AND hp.location = %(site)s
          {shift_condition_hp}
        GROUP BY tl.asset_name_shoval
    """, values, as_dict=True)

    dozer_rows = frappe.db.sql(f"""
        SELECT
            dp.asset_name AS dozer,
            SUM(dp.bcm_hour) AS bcm_output,
            GROUP_CONCAT(DISTINCT dp.dozer_geo_mat_layer) AS mat_types
        FROM `tabHourly Production` hp
        JOIN `tabDozer Production` dp ON dp.parent = hp.name
        WHERE hp.prod_date = %(date)s
          AND hp.location = %(site)s
          {shift_condition_hp}
        GROUP BY dp.asset_name
    """, values, as_dict=True)

    preuse_rows = frappe.db.sql(f"""
        SELECT pa.asset_name, pa.asset_category, SUM(pa.working_hours) AS working_hours
        FROM `tabPre-Use Hours` pu
        JOIN `tabPre-use Assets` pa ON pa.parent = pu.name
        WHERE pu.shift_date = %(date)s
          AND pu.location = %(site)s
          {shift_condition_pu}
        GROUP BY pa.asset_name, pa.asset_category
    """, values, as_dict=True)

    hours_map = {(r.asset_name or "").strip(): r.working_hours or 0 for r in preuse_rows if r.asset_name}

    excavator_data, dozer_data = [], []

    for r in truck_rows:
        name = (r.excavator or "").strip()
        if not name:
            continue
        output = r.bcm_output or 0
        if r.mat_types and "coal" in r.mat_types.lower():
            output *= COAL_CONVERSION
        hours = hours_map.get(name, 0)
        prod = round(output / hours, 2) if hours > 0 else 0
        excavator_data.append({"asset_name": name, "hours": hours, "output": output, "productivity": prod})

    for r in dozer_rows:
        name = (r.dozer or "").strip()
        if not name:
            continue
        output = r.bcm_output or 0
        if r.mat_types and "coal" in r.mat_types.lower():
            output *= COAL_CONVERSION
        hours = hours_map.get(name, 0)
        prod = round(output / hours, 2) if hours > 0 else 0
        dozer_data.append({"asset_name": name, "hours": hours, "output": output, "productivity": prod})

    return excavator_data, dozer_data


# ---------------------------------------------------------
# ✅ HTML Layout
# ---------------------------------------------------------
def build_html(site, shift, formatted_date, mpp, excavators, dozers, fmt,
               mtd_coal, mtd_waste,
               actual_ts_day, actual_dozer_day, mtd_actual_bcms,
               excavator_prod, dozer_prod):
    dark_blue = "#003366"
    light_blue = "#EAF3FA"
    gray_border = "#CCCCCC"
    divider_color = "#666666"
    red = "#b30000"
    green = "#006600"

    style = f"""
    <style>
    @page {{ size: landscape; margin: 10mm; }}
    body {{ font-weight: bold; }}
    table td:nth-child(n+2), table th:nth-child(n+2) {{ text-align: right !important; }}
    .report-container {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; }}
    .left-section {{ width: 45%; }}
    .right-section {{ width: 55%; }}
    hr.full-line {{
        border: none;
        border-top: 2px solid {divider_color};
        margin: 25px 0 15px 0;
        width: 100%;
    }}
    .bottom-prod {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 30px;
        width: 100%;
    }}
    .prod-table {{ width: 48%; }}
    </style>
    """

    section = f"font-weight:bold; font-size:15px; margin-top:10px; margin-bottom:4px; color:{dark_blue};"
    table = f"width:100%; border-collapse:collapse; font-size:13px; border:1px solid {gray_border}; table-layout:fixed; font-weight:bold;"
    th = f"border:1px solid {gray_border}; padding:5px; background-color:{light_blue}; font-weight:bold; color:{dark_blue};"
    td = f"border:1px solid {gray_border}; padding:5px; font-weight:bold;"

    shift_color = "#006600" if shift.lower() == "day" else "#003366" if shift.lower() == "night" else "#000000"
    shift_label = shift if shift else "Full Day"
    shift_html = f"<span style='font-style:italic; color:{shift_color}; font-weight:bold;'> - {shift_label}</span>"

    summary_html = f"""
    <div class="left-section">
        <div style="{section}">Summary</div>
        <table style="{table}">
            <tr><td style="{td}">Monthly Target</td><td style="{td}">{fmt(mpp.monthly_target_bcm if mpp else 0)}</td></tr>
            <tr><td style="{td}">Monthly Coal Target</td><td style="{td}">{fmt(mpp.coal_tons_planned if mpp else 0)}</td></tr>
            <tr><td style="{td}">MTD Coal (tons)</td><td style="{td}">{fmt(mtd_coal)}</td></tr>
            <tr><td style="{td}">MTD Waste</td><td style="{td}">{fmt(mtd_waste)}</td></tr>
            <tr><td style="{td}">MTD Actual BCM's</td><td style="{td}">{fmt(mtd_actual_bcms)}</td></tr>
            <tr><td style="{td}">Remaining Volumes</td><td style="{td}">{fmt((mpp.monthly_target_bcm if mpp else 0) - mtd_actual_bcms)}</td></tr>
            <tr><td style="{td}">Daily Target</td><td style="{td}">{fmt(mpp.target_bcm_day if mpp else 0)}</td></tr>
            <tr><td style="{td}">Daily TS BCMs</td><td style="{td}">{fmt(actual_ts_day)}</td></tr>
            <tr><td style="{td}">Daily Dozing BCMs</td><td style="{td}">{fmt(actual_dozer_day)}</td></tr>
            <tr><td style="{td}">Daily Achieved</td><td style="{td}">{fmt(actual_ts_day + actual_dozer_day)}</td></tr>
            <tr><td style="{td}">Daily Average BCM per Hour</td><td style="{td}" contenteditable="true"></td></tr>
        </table>
    </div>
    """

    exc_table, dozer_table = build_machine_tables(excavators, dozers, fmt, td, th, section, table)

    right_html = f"""
    <div class="right-section">
        {exc_table}
        {dozer_table}
    </div>
    """

    bottom_html = f"""
    <hr class='full-line'>
    <div class='bottom-prod'>
        <div class='prod-table'>
            {build_prod_table("Excavator Productivity (Day Tallies)", excavator_prod, fmt, td, th, section, table, red, green)}
        </div>
        <div class='prod-table'>
            {build_prod_table("Dozer Productivity (Day Tallies)", dozer_prod, fmt, td, th, section, table, red, green)}
        </div>
    </div>
    """

    return f"""{style}
    <div style="text-align:center;">
        <h3 style="margin-bottom:2px; color:{dark_blue}; font-size:16px;"><strong>{site}</strong>{shift_html}</h3>
        <div style="font-size:13px; font-weight:bold;">{formatted_date}</div>
    </div>
    <div class="report-container">{summary_html}{right_html}</div>
    {bottom_html}
    """


# ---------------------------------------------------------
# Tables (totals + coloring)
# ---------------------------------------------------------
def build_machine_tables(excavators, dozers, fmt, td, th, section, table):
    def build_rows(data):
        return "".join(
            f"<tr><td style='{td}'>{d['asset_name']}</td>"
            f"<td style='{td}'>{fmt(d['target'])}</td>"
            f"<td style='{td}'>{fmt(d['actual'])}</td>"
            f"<td style='{td}'>{fmt(d['mtd_hours'])}</td>"
            f"<td style='{td}' contenteditable='true'></td></tr>"
            for d in data
        )

    def total_row(data):
        if not data:
            return ""
        total_target = sum(d["target"] for d in data)
        total_actual = sum(d["actual"] for d in data)
        total_mtd = sum(d["mtd_hours"] for d in data)
        return f"<tr style='background-color:#f2f2f2;font-weight:bold;'><td style='{td}'>Total</td><td style='{td}'>{fmt(total_target)}</td><td style='{td}'>{fmt(total_actual)}</td><td style='{td}'>{fmt(total_mtd)}</td><td style='{td}'></td></tr>"

    exc_table = f"""
    <div style="{section}">Excavator Hours</div>
    <table style="{table}">
        <tr><th style="{th}">Excavator</th><th style="{th}">Target</th><th style="{th}">Actual</th><th style="{th}">MTD</th><th style="{th}">Comment</th></tr>
        {build_rows(excavators)}
        {total_row(excavators)}
    </table>"""

    dozer_table = f"""
    <div style="{section}">Dozer Hours</div>
    <table style="{table}">
        <tr><th style="{th}">Dozer</th><th style="{th}">Target</th><th style="{th}">Actual</th><th style="{th}">MTD</th><th style="{th}">Comment</th></tr>
        {build_rows(dozers)}
        {total_row(dozers)}
    </table>"""
    return exc_table, dozer_table


def build_prod_table(title, rows, fmt, td, th, section, table, red, green):
    prod_rows = "".join(
        f"<tr><td style='{td}'>{r['asset_name']}</td>"
        f"<td style='{td}'>{fmt(r['hours'])}</td>"
        f"<td style='{td}'>{fmt(r['output'])}</td>"
        f"<td style='{td};color:{green if r['productivity']>=220 else red};'>{fmt(r['productivity'])}</td></tr>"
        for r in rows
    )

    if rows:
        total_hours = sum(r["hours"] for r in rows)
        total_output = sum(r["output"] for r in rows)
        avg_prod = round(total_output / total_hours, 2) if total_hours else 0
        color = green if avg_prod >= 220 else red
        prod_rows += f"<tr style='background-color:#f2f2f2;font-weight:bold;'><td style='{td}'>Total</td><td style='{td}'>{fmt(total_hours)}</td><td style='{td}'>{fmt(total_output)}</td><td style='{td};color:{color};'>{fmt(avg_prod)}</td></tr>"
    else:
        prod_rows = f"<tr><td colspan='4' style='{td}'>No data found</td></tr>"

    return f"""
    <div style="{section} margin-top:10px;">{title}</div>
    <table style="{table}">
        <tr><th style="{th}">Machine</th><th style="{th}">Hours</th><th style="{th}">BCM's</th><th style="{th}">BCM per Hour</th></tr>
        {prod_rows}
    </table>
    """
