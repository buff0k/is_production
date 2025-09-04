# Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

# import frappe
# apps/is_production/is_production/production/report/production_shift_dozing/production_shift_dozing.py

import frappe

def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Date", "fieldname": "prod_date", "fieldtype": "Date", "width": 100},
        {"label": "Shift", "fieldname": "shift", "fieldtype": "Data", "width": 100},
        {"label": "Dozer", "fieldname": "dozer", "fieldtype": "Data", "width": 180},
        {"label": "Cumulative BCM", "fieldname": "cumulative_bcm", "fieldtype": "Float", "width": 150},
    ]


def get_data(filters):
    if not (filters.start_date and filters.end_date and filters.site):
        return []

    # --- Query all dozer production grouped by date, shift, dozer ---
    rows = frappe.db.sql(
        """
        SELECT hp.prod_date, hp.shift,
               dp.asset_name AS dozer,
               SUM(dp.bcm_hour) AS bcm_total
        FROM `tabHourly Production` hp
        JOIN `tabDozer Production` dp ON dp.parent = hp.name
        WHERE hp.location = %(site)s
          AND hp.prod_date BETWEEN %(start_date)s AND %(end_date)s
          AND hp.docstatus < 2
        GROUP BY hp.prod_date, hp.shift, dp.asset_name
        ORDER BY hp.prod_date, hp.shift, dp.asset_name
        """,
        {
            "site": filters.site,
            "start_date": filters.start_date,
            "end_date": filters.end_date,
        },
        as_dict=True,
    )

    results = []
    shift_totals = {}
    day_night_totals = {"Day": 0, "Night": 0}

    # Per-dozer rows
    for r in rows:
        results.append({
            "prod_date": r.prod_date,
            "shift": r.shift,
            "dozer": r.dozer,
            "cumulative_bcm": r.bcm_total or 0,
        })

        # Per-shift totals
        shift_totals.setdefault((r.prod_date, r.shift), 0)
        shift_totals[(r.prod_date, r.shift)] += r.bcm_total or 0

        # Global Day/Night totals
        if r.shift in day_night_totals:
            day_night_totals[r.shift] += r.bcm_total or 0

    # Add total rows per shift/date
    for (prod_date, shift), total in shift_totals.items():
        results.append({
            "prod_date": prod_date,
            "shift": shift,
            "dozer": "TOTAL",
            "cumulative_bcm": total,
        })

    # Add final Day and Night totals (spanning all dates in range)
    for shift in ["Day", "Night"]:
        if day_night_totals[shift] > 0:
            results.append({
                "prod_date": None,
                "shift": f"TOTAL {shift.upper()}",
                "dozer": "",
                "cumulative_bcm": day_night_totals[shift],
            })

    return results



