# production_shift_report.py
# Production Report for Hourly Production data (with Diesel and Fuel Cap)
# Supports different time dimensions and separate indent structures for BCMs, Diesel, and Fuel Cap.
# Fuel Cap is calculated as (Diesel Litres) / (BCM).
# Time buckets are generated from the date range filters.
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, formatdate
import datetime

### ---------------- Time Columns ----------------

def get_time_columns(filters):
    tc = filters.get("time_column", "Month Only")
    fd = getdate(filters.get("from_date"))
    td = getdate(filters.get("to_date"))

    if tc == "Month Only":
        return get_month_columns_from_date_range(fd, td)
    if tc == "Days and Month":
        return get_day_columns_from_date_range(fd, td)
    if tc == "Weeks and Month":
        return get_week_columns_from_date_range(fd, td)
    if tc == "Days Only":
        return get_day_columns_from_date_range_days_only(fd, td)
    if tc == "Weeks Only":
        return get_week_columns_from_date_range_weeks_only(fd, td)
    return get_month_columns_from_date_range(fd, td)

def get_month_columns_from_date_range(from_date, to_date):
    columns = []
    current = from_date.replace(day=1)
    while current <= to_date:
        key = current.strftime("%b_%Y").lower()
        label = current.strftime("%b %Y")
        columns.append({"key": key, "label": label})
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    return columns

def get_day_columns_from_date_range(from_date, to_date):
    columns = []
    month_order = []
    current = from_date
    while current <= to_date:
        key = current.strftime("%Y-%m-%d")
        label = current.strftime("%d %b")
        columns.append({"key": key, "label": label})
        month_key = current.strftime("%b_%Y").lower()
        if month_key not in month_order:
            month_order.append(month_key)
        current += datetime.timedelta(days=1)
    for month_key in month_order:
        columns.append({
            "key": f"month_total_{month_key}",
            "label": _(f"{month_key.split('_')[0]} Total")
        })
    return columns

def get_week_columns_from_date_range(from_date, to_date):
    weeks = {}
    month_order = []
    current = from_date
    while current <= to_date:
        iso_week = current.isocalendar()[1]
        week_key = f"{current.year}-W{iso_week:02d}"
        if week_key not in weeks:
            weeks[week_key] = f"W{iso_week:02d} ({current.year})"
        month_key = current.strftime("%b_%Y").lower()
        if month_key not in month_order:
            month_order.append(month_key)
        current += datetime.timedelta(days=1)
    columns = [{"key": k, "label": weeks[k]} for k in sorted(weeks)]
    for month_key in month_order:
        columns.append({
            "key": f"month_total_{month_key}",
            "label": _(f"{month_key.split('_')[0]} Total")
        })
    return columns

def get_day_columns_from_date_range_days_only(from_date, to_date):
    columns = []
    current = from_date
    while current <= to_date:
        key = current.strftime("%Y-%m-%d")
        label = current.strftime("%d %b")
        columns.append({"key": key, "label": label})
        current += datetime.timedelta(days=1)
    return columns

def get_week_columns_from_date_range_weeks_only(from_date, to_date):
    weeks = {}
    current = from_date
    while current <= to_date:
        iso_week = current.isocalendar()[1]
        week_key = f"{current.year}-W{iso_week:02d}"
        if week_key not in weeks:
            weeks[week_key] = f"W{iso_week:02d} ({current.year})"
        current += datetime.timedelta(days=1)
    return [{"key": k, "label": weeks[k]} for k in sorted(weeks)]

### ---------------- Aggregation Functions ----------------

def compute_time_sum(entries, field, columns, filters):
    tc = filters.get("time_column", "Month Only")
    sums = {col['key']: 0 for col in columns}

    for e in entries:
        pd = e.get("prod_date")
        if not pd:
            continue
        d = getdate(pd)
        if tc == "Month Only":
            key = d.strftime("%b_%Y").lower()
        elif tc == "Days and Month":
            key = d.strftime("%Y-%m-%d")
            month_key = f"month_total_{d.strftime('%b_%Y').lower()}"
        elif tc == "Days Only":
            key = d.strftime("%Y-%m-%d")
        elif tc == "Weeks and Month":
            key = f"{d.year}-W{d.isocalendar()[1]:02d}"
            month_key = f"month_total_{d.strftime('%b_%Y').lower()}"
        elif tc == "Weeks Only":
            key = f"{d.year}-W{d.isocalendar()[1]:02d}"
        else:
            key = d.strftime("%b_%Y").lower()

        if key in sums:
            sums[key] += flt(e.get(field, 0))
        if tc in ("Days and Month", "Weeks and Month") and month_key in sums:
            sums[month_key] += flt(e.get(field, 0))

    return {k: int(round(v)) for k, v in sums.items()}

def compute_diesel_sum(entries, columns, filters):
    tc = filters.get("time_column", "Month Only")
    sums = {col['key']: 0 for col in columns}

    for e in entries:
        pd = e.get("diesel_date")
        if not pd:
            continue
        d = getdate(pd)
        if tc == "Month Only":
            key = d.strftime("%b_%Y").lower()
        elif tc == "Days and Month":
            key = d.strftime("%Y-%m-%d")
            month_key = f"month_total_{d.strftime('%b_%Y').lower()}"
        elif tc == "Days Only":
            key = d.strftime("%Y-%m-%d")
        elif tc == "Weeks and Month":
            key = f"{d.year}-W{d.isocalendar()[1]:02d}"
            month_key = f"month_total_{d.strftime('%b_%Y').lower()}"
        elif tc == "Weeks Only":
            key = f"{d.year}-W{d.isocalendar()[1]:02d}"
        else:
            key = d.strftime("%b_%Y").lower()

        if key in sums:
            sums[key] += flt(e.get("litres", 0))
        if tc in ("Days and Month", "Weeks and Month") and month_key in sums:
            sums[month_key] += flt(e.get("litres", 0))

    return {k: int(round(v)) for k, v in sums.items()}

def compute_fuelcap(bcm, diesel, columns):
    out = {}
    for col in columns:
        k = col['key']
        out[k] = round(diesel.get(k, 0) / bcm.get(k, 0), 2) if bcm.get(k) else 0
    return out

### ---------------- Report Builder ----------------

def build_report_with_total_bcm_and_diesel(
    production_entries,
    diesel_entries,
    monthly_days_entries,
    columns,
    filters
):
    data = []

    # Overall BCM Total = Truck & Shoval + Dozing + Survey Dozing + Survey TS across all sites
    mapped_all = [
        {
            "prod_date": m["shift_start_date"],
            "cum_dozing_variance": m.get("cum_dozing_variance", 0),
            "cum_ts_variance": m.get("cum_ts_variance", 0),
        }
        for m in monthly_days_entries
    ]
    ts_total  = compute_time_sum(production_entries, "total_ts_bcm",    columns, filters)
    doz_total = compute_time_sum(production_entries, "total_dozing_bcm", columns, filters)
    surv_doz  = compute_time_sum(mapped_all,            "cum_dozing_variance", columns, filters)
    surv_ts   = compute_time_sum(mapped_all,            "cum_ts_variance",     columns, filters)
    combined  = {
        k: ts_total.get(k, 0)
           + doz_total.get(k,   0)
           + surv_doz.get(k,    0)
           + surv_ts.get(k,     0)
        for k in ts_total
    }
    data.append({"label": "BCM Total", "indent": 0, "is_group": True, "time_sums": combined})

    # Group hourly production by site
    sites = {}
    for e in production_entries:
        site = e.get("location")
        if site:
            sites.setdefault(site, []).append(e)

    # Group survey by site
    survey = {}
    for m in monthly_days_entries:
        site = m.get("location")
        if site:
            survey.setdefault(site, []).append(m)

    site_bcm_totals = {}
    site_diesel_totals = {}

    # Per-site breakdown
    for site in sorted(sites):
        entries = sites[site]

        ts_sums  = compute_time_sum(entries, "total_ts_bcm",    columns, filters)
        doz_sums = compute_time_sum(entries, "total_dozing_bcm", columns, filters)

        mapped_site = [
            {
                "prod_date":           m.get("shift_start_date"),
                "cum_dozing_variance": m.get("cum_dozing_variance", 0),
                "cum_ts_variance":     m.get("cum_ts_variance", 0),
            }
            for m in survey.get(site, [])
        ]
        surv_doz_site = compute_time_sum(mapped_site, "cum_dozing_variance", columns, filters)
        surv_ts_site  = compute_time_sum(mapped_site, "cum_ts_variance",     columns, filters)

        # Site total = sum of all four child rows
        site_combined = {
            k: ts_sums.get(k, 0)
               + doz_sums.get(k, 0)
               + surv_doz_site.get(k, 0)
               + surv_ts_site.get(k, 0)
            for k in [col['key'] for col in columns]
        }
        data.append({"label": site, "indent": 1, "is_group": True, "time_sums": site_combined})
        site_bcm_totals[site] = site_combined

        # Child rows at indent=2
        data.append({"label": "Truck and Shoval BCM",   "indent": 2, "is_group": False, "time_sums": ts_sums})
        data.append({"label": "Dozing BCM",             "indent": 2, "is_group": False, "time_sums": doz_sums})
        data.append({"label": "Survey Dozing Variance", "indent": 2, "is_group": False, "time_sums": surv_doz_site})
        data.append({"label": "Survey TS Variance",     "indent": 2, "is_group": False, "time_sums": surv_ts_site})

    # Diesel Total
    diesel_total = compute_diesel_sum(diesel_entries, columns, filters)
    data.append({"label": "Diesel Total", "indent": 0, "is_group": True, "time_sums": diesel_total})

    # Per-site diesel
    diesel_by_site = {}
    for d in diesel_entries:
        site = d.get("location")
        if site:
            diesel_by_site.setdefault(site, []).append(d)

    for site in sorted(diesel_by_site):
        d_list = diesel_by_site[site]
        sums   = compute_diesel_sum(d_list, columns, filters)
        data.append({"label": site, "indent": 1, "is_group": False, "time_sums": sums})
        site_diesel_totals[site] = sums

    # Fuel Cap Total & per-site
    fc_total = compute_fuelcap(combined, diesel_total, columns)
    data.append({"label": "Fuel Cap Total", "indent": 0, "is_group": True, "time_sums": fc_total})
    for site in sorted(set(site_bcm_totals) | set(site_diesel_totals)):
        bcm_vals    = site_bcm_totals.get(site,    {col['key']: 0 for col in columns})
        diesel_vals = site_diesel_totals.get(site, {col['key']: 0 for col in columns})
        fc = compute_fuelcap(bcm_vals, diesel_vals, columns)
        data.append({"label": f"Fuel Cap - {site}", "indent": 1, "is_group": False, "time_sums": fc})

    # Flatten time_sums into row keys
    for row in data:
        row.update(row.pop("time_sums", {}))

    return data

### ---------------- Table & Chart Helpers ----------------

def get_columns(columns):
    cols = [{
        "fieldname": "label",
        "label": _("Group"),
        "fieldtype": "Data",
        "width": 300
    }]
    for c in columns:
        cols.append({
            "fieldname": c["key"],
            "label": c["label"],
            "fieldtype": "Float",
            "width": 150,
            "precision": 0
        })
    return cols

def get_chart_data(columns, production_entries, filters):
    tc = filters.get("time_column", "Month Only")
    chart_map = {}
    for e in production_entries:
        site = e.get("location")
        pd = e.get("prod_date")
        if not site or not pd:
            continue
        d = getdate(pd)
        if tc == "Month Only":
            key = d.strftime("%b_%Y").lower()
        elif tc in ("Days and Month", "Days Only"):
            key = d.strftime("%Y-%m-%d")
        else:
            key = f"{d.year}-W{d.isocalendar()[1]:02d}"

        chart_map.setdefault(site, {col['key']: 0 for col in columns})
        if key in chart_map[site]:
            chart_map[site][key] += flt(e.get("hour_total_bcm", 0))
        if tc in ("Days and Month", "Weeks and Month"):
            mk = f"month_total_{d.strftime('%b_%Y').lower()}"
            if mk in chart_map[site]:
                chart_map[site][mk] += flt(e.get("hour_total_bcm", 0))

    labels = [col['label'] for col in columns]
    datasets = [{"name": site, "values": [chart_map[site][c['key']] for c in columns]}
                for site in sorted(chart_map)]
    return {
        "data": {"labels": labels, "datasets": datasets},
        "type": "line",
        "fieldtype": "Float",
        "options": ""
    }

### ---------------- Execute ----------------

def execute(filters=None):
    filters = filters or {}

    # Hourly Production query
    prod_sql, prod_params = _build_prod_query(filters)
    production_entries = frappe.db.sql(prod_sql, prod_params, as_dict=1)

    # Diesel query
    diesel_sql, diesel_params = _build_diesel_query(filters)
    diesel_entries = frappe.db.sql(diesel_sql, diesel_params, as_dict=1)

    # Survey variances
    monthly_days_entries = get_monthly_planning_records(filters.get("from_date"), filters.get("to_date"))

    # Build report
    time_columns   = get_time_columns(filters)
    primary_data   = build_report_with_total_bcm_and_diesel(
        production_entries,
        diesel_entries,
        monthly_days_entries,
        time_columns,
        filters
    )
    primary_columns = get_columns(time_columns)
    primary_chart   = get_chart_data(time_columns, production_entries, filters)

    return primary_columns, primary_data, None, primary_chart, [], None

def _build_prod_query(filters):
    cond, params = "WHERE 1=1", {}
    if filters.get("from_date") and filters.get("to_date"):
        cond += " AND prod_date BETWEEN %(from_date)s AND %(to_date)s"
        params["from_date"], params["to_date"] = filters["from_date"], filters["to_date"]
    if filters.get("site"):
        cond += " AND location = %(site)s"
        params["site"] = filters["site"]
    sql = f"""
        SELECT location,
               prod_date,
               day_number,
               shift,
               hour_total_bcm,
               total_ts_bcm,
               total_dozing_bcm,
               monthly_production_child_ref
        FROM `tabHourly Production`
        {cond}
        ORDER BY location, prod_date, shift
    """
    return sql, params

def _build_diesel_query(filters):
    cond, params = "WHERE 1=1", {}
    if filters.get("from_date") and filters.get("to_date"):
        cond += " AND p.daily_sheet_date BETWEEN %(from_date)s AND %(to_date)s"
        params["from_date"], params["to_date"] = filters["from_date"], filters["to_date"]
    if filters.get("site"):
        cond += " AND p.location = %(site)s"
        params["site"] = filters["site"]
    if filters.get("exclude_assets"):
        cond += " AND c.asset_name NOT IN %(excluded)s"
        params["excluded"] = tuple(filters["exclude_assets"])
    sql = f"""
        SELECT p.location,
               p.daily_sheet_date AS diesel_date,
               SUM(c.litres_issued) AS litres
        FROM `tabDaily Diesel Sheet` p
        JOIN `tabDaily Diesel Entries` c ON c.parent = p.name
        {cond}
        GROUP BY p.location, p.daily_sheet_date
        ORDER BY p.location, p.daily_sheet_date
    """
    return sql, params

@frappe.whitelist()
def get_monthly_planning_records(from_date, to_date):
    """
    Return MPP parent, location, shift_start_date,
    hourly_production_reference, cum_dozing_variance, cum_ts_variance.
    """
    return frappe.db.sql("""
        SELECT
            p.name                        AS parent_name,
            p.location                    AS location,
            m.shift_start_date            AS shift_start_date,
            m.hourly_production_reference AS hourly_production_reference,
            m.cum_dozing_variance         AS cum_dozing_variance,
            m.cum_ts_variance             AS cum_ts_variance
        FROM `tabMonthly Production Planning` p
        JOIN `tabMonthly Production Days` m ON m.parent = p.name
        WHERE m.shift_start_date BETWEEN %(from_date)s AND %(to_date)s
    """, {"from_date": from_date, "to_date": to_date}, as_dict=1)
