# Copyright (c) 2025, Isambane Mining (Pty) Ltd
# For license information, please see license.txt

import frappe
from frappe.utils import flt, format_date, getdate


def execute(filters=None):
    if not filters:
        filters = {}

    site = filters.get("site")
    end_date = filters.get("end_date")
    formatted_date = format_date(end_date, "dd/MM/yyyy") if end_date else ""

    # ---- Fetch Monthly Production Plan ----
    mpp = get_monthly_plan(site, end_date)
    month_start = getdate(mpp.prod_month_start_date) if mpp else None

    data = {
        "monthly_target": 0,
        "waste_bcms_planned": 0,
        "coal_tons_planned": 0,
        "num_prod_days": 0,
        "num_prod_days_completed": 0,
        "month_remaining_prod_days": 0,
        "mtd_actual_bcms": 0,
        "mtd_prog_actual_coal": 0,
        "mtd_prog_actual_waste": 0,
    }

    if mpp:
        data.update({
            "monthly_target": flt(mpp.monthly_target_bcm),
            "waste_bcms_planned": flt(mpp.waste_bcms_planned),
            "coal_tons_planned": flt(mpp.coal_tons_planned),
            "num_prod_days": flt(mpp.num_prod_days),
            "num_prod_days_completed": flt(mpp.prod_days_completed),
            "month_remaining_prod_days": flt(mpp.month_remaining_production_days),
        })

        # ---- Actuals ----
        mtd_actual_bcms = get_actual_bcms_for_date(site, getdate(end_date), month_start)
        mtd_prog_actual_coal = get_mtd_coal_dynamic(site, getdate(end_date), month_start)
        mtd_prog_actual_waste = mtd_actual_bcms - (mtd_prog_actual_coal / 1.5)

        data["mtd_actual_bcms"] = mtd_actual_bcms
        data["mtd_prog_actual_coal"] = mtd_prog_actual_coal
        data["mtd_prog_actual_waste"] = mtd_prog_actual_waste

        # ---- Derived metrics ----
        data["mtd_prog_target_waste"] = (
            (data["waste_bcms_planned"] / data["num_prod_days"]) * data["num_prod_days_completed"]
            if data["num_prod_days"] else 0
        )
        data["short_over_waste"] = data["mtd_prog_target_waste"] - data["mtd_prog_actual_waste"]

        data["mtd_prog_target_coal"] = (
            (data["coal_tons_planned"] / data["num_prod_days"]) * data["num_prod_days_completed"]
            if data["num_prod_days"] else 0
        )
        data["short_over_coal"] = data["mtd_prog_target_coal"] - data["mtd_prog_actual_coal"]

        data["remaining_volume"] = data["monthly_target"] - data["mtd_actual_bcms"]

        data["daily_required"] = (
            data["remaining_volume"] / max((data["month_remaining_prod_days"], 1))
        )
        data["actual_daily"] = (
            data["mtd_actual_bcms"] / max((data["num_prod_days_completed"], 1))
        )

        monthly_days = data["num_prod_days"]
        worked_days = data["num_prod_days_completed"]
        data["days_left"] = max(monthly_days - worked_days, 0)

        data["forecast"] = (
            (data["mtd_actual_bcms"] / worked_days) * data["days_left"] + data["mtd_actual_bcms"]
            if worked_days else 0
        )
        data["short_over_forecast"] = data["monthly_target"] - data["mtd_actual_bcms"]

        data["strip_ratio"] = round(
            (data["mtd_prog_actual_waste"] / data["mtd_prog_actual_coal"])
            if data["mtd_prog_actual_coal"] else 0,
            1
        )

    html = build_html(site, formatted_date, data)
    return [], None, html


# ----------------------------------------------------------
# Helper functions
# ----------------------------------------------------------
def get_monthly_plan(site, date):
    if not site or not date:
        return None
    plan_name = frappe.db.get_value(
        "Monthly Production Planning",
        {"location": site, "prod_month_start_date": ["<=", date], "prod_month_end_date": [">=", date]},
        "name",
    )
    return frappe.get_doc("Monthly Production Planning", plan_name) if plan_name else None


def get_actual_bcms_for_date(site, end_date, month_start):
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


def get_mtd_coal_dynamic(site, end_date, month_start):
    if not site or not end_date:
        return 0
    coal_after = frappe.db.sql("""
        SELECT COALESCE(SUM(tl.bcms),0)
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.prod_date BETWEEN %s AND %s
          AND hp.location = %s
          AND LOWER(tl.mat_type) LIKE '%%coal%%'
    """, (month_start, end_date, site))[0][0]
    return (coal_after or 0) * 1.5


# ----------------------------------------------------------
# HTML layout builder
# ----------------------------------------------------------
def build_html(site, formatted_date, d):
    def fmt(value, decimals=0):
        return f"{flt(value, decimals):,.{decimals}f}"

    def color_num(value):
        val = fmt(abs(value))
        if value > 0:
            return f"<span style='color:red;'>{val}</span>"
        elif value < 0:
            return f"<span style='color:green;'>{val}</span>"
        else:
            return val

    style = """
    <style>
        @page { size: portrait; margin: 10mm; }
        body { font-family: Arial, sans-serif; font-size: 11.5px; }
        .report-container {
            width: 70%;
            margin: 0 auto;
            border: 1px solid #BFBFBF;
            padding-bottom: 5px;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            table-layout: fixed;
        }
        th, td {
            border: 1px solid #BFBFBF;
            padding: 4px 6px;
        }
        th {
            background-color: #F9F9F9;
            text-align: left;
            font-weight: bold;
        }
        td.label {
            text-align: left;
            width: 60%;
            word-wrap: break-word;
        }
        td.num {
            text-align: right;
            width: 25%;
        }
        td.unit {
            width: 15%;
            text-align: left;
        }
        .bold { font-weight: bold; }
        .header-title {
            background-color: #4FA7FF;
            color: white;
            font-weight: bold;
            text-align: center;
            padding: 6px;
            font-size: 14px;
        }
        .week-input {
            width: 2cm;
            height: 1cm;
            border: 1px solid black;
            text-align: center;
            font-weight: bold;
            background-color: #fff;
            margin-left: 5px;
        }
    </style>
    """

    html = f"""
    {style}
    <div class="report-container">
        <div class="header-title">
            {site.upper()}<br>
            PRODUCTION SUMMARY – {formatted_date}
            <input type="text" class="week-input" placeholder="" />
        </div>

        <table>
            <tr><th>Description</th><th>Unit</th><th class="num">Value</th></tr>

            <tr><td class="label bold">Monthly Target</td><td class="unit">BCM</td><td class="num">{fmt(d["monthly_target"])}</td></tr>
            <tr><td colspan="3" style="height:12px; border:none;"></td></tr>

            <tr><td class="label bold">Monthly Waste Target</td><td class="unit">BCM</td><td class="num">{fmt(d["waste_bcms_planned"])}</td></tr>
            <tr><td class="label">MTD Prog Actual Waste</td><td class="unit">BCM</td><td class="num">{fmt(d["mtd_prog_actual_waste"])}</td></tr>
            <tr><td class="label">MTD Prog Target Waste</td><td class="unit">BCM</td><td class="num">{fmt(d["mtd_prog_target_waste"])}</td></tr>
            <tr><td class="label bold">SHORT / OVER</td><td class="unit">BCM</td><td class="num">{color_num(d["short_over_waste"])}</td></tr>
            <tr><td colspan="3" style="height:12px; border:none;"></td></tr>

            <tr><td class="label bold">Monthly Coal Target</td><td class="unit">TONS</td><td class="num">{fmt(d["coal_tons_planned"])}</td></tr>
            <tr><td class="label">MTD Prog Actual COAL</td><td class="unit">TONS</td><td class="num">{fmt(d["mtd_prog_actual_coal"])}</td></tr>
            <tr><td class="label">MTD Prog Target COAL</td><td class="unit">TONS</td><td class="num">{fmt(d["mtd_prog_target_coal"])}</td></tr>
            <tr><td class="label bold">SHORT / OVER</td><td class="unit">TONS</td><td class="num">{color_num(d["short_over_coal"])}</td></tr>
            <tr><td colspan="3" style="height:12px; border:none;"></td></tr>

            <tr><td class="label">MTD Prog Actual BCM’s</td><td class="unit">BCM</td><td class="num">{fmt(d["mtd_actual_bcms"])}</td></tr>
            <tr><td class="label bold">Remaining Volume</td><td class="unit">BCM</td><td class="num">{fmt(d["remaining_volume"])}</td></tr>
            <tr><td class="label">Daily required to reach Target</td><td class="unit">BCM</td><td class="num">{fmt(d["daily_required"])}</td></tr>
            <tr><td class="label">Actual Daily Achieved</td><td class="unit">BCM</td><td class="num">{fmt(d["actual_daily"])}</td></tr>
            <tr><td colspan="3" style="height:12px; border:none;"></td></tr>

            <tr><td class="label">Monthly Available Days</td><td class="unit"></td><td class="num">{fmt(d["num_prod_days"])}</td></tr>
            <tr><td class="label">Worked Days</td><td class="unit"></td><td class="num">{fmt(d["num_prod_days_completed"])}</td></tr>
            <tr><td class="label">Days Left</td><td class="unit"></td><td class="num">{fmt(d["days_left"])}</td></tr>
            <tr><td colspan="3" style="height:12px; border:none;"></td></tr>

            <tr><td class="label bold">Forecast on Current Rate</td><td class="unit">BCM</td><td class="num">{fmt(d["forecast"])}</td></tr>
            <tr><td class="label bold">SHORT / OVER</td><td class="unit">BCM</td><td class="num">{color_num(d["short_over_forecast"])}</td></tr>
            <tr><td colspan="3" style="height:12px; border:none;"></td></tr>

            <tr><td class="label bold">Strip Ratio</td><td class="unit"></td><td class="num">{fmt(d["strip_ratio"], 1)}</td></tr>
        </table>
    </div>
    """
    return html
