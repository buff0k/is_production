import frappe
from frappe import _

MACHINE_ORDER = ["EX01", "ADT01", "ADT02", "ADT03", "ADT04"]
SHIFT_ORDER = ["Day", "Night"]


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not (filters.start_date and filters.end_date and filters.site):
        return [], [], None, None, []

    columns = get_columns()
    data = get_data(filters)

    return columns, data, None, None, []


def get_columns():
    return [
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Data", "width": 120, "group": 1},
        {"label": _("Machine"), "fieldname": "machine", "fieldtype": "Data", "width": 120},
        {"label": _("Start Hours"), "fieldname": "start_hours", "fieldtype": "Float", "width": 120},
        {"label": _("End Hours"), "fieldname": "end_hours", "fieldtype": "Float", "width": 120},
        {"label": _("Working Hours"), "fieldname": "working_hours", "fieldtype": "Float", "width": 120},
        {"label": _("Shift"), "fieldname": "shift", "fieldtype": "Data", "width": 80},
        {"label": _("Site"), "fieldname": "site", "fieldtype": "Data", "width": 120},
    ]


def get_data(filters):
    values = {
        "start_date": filters.start_date,
        "end_date": filters.end_date,
        "site": filters.site,
    }

    machine_condition = ""
    if filters.get("machine"):
        machine_condition = "AND pa.asset_name = %(machine)s"
        values["machine"] = filters.machine

    shift_condition = ""
    if filters.get("shift"):
        shift_condition = "AND ph.shift = %(shift)s"
        values["shift"] = filters.shift

    rows = frappe.db.sql(f"""
        SELECT
            ph.shift_date AS date,
            pa.asset_name AS machine,
            pa.eng_hrs_start AS start_hours,
            pa.eng_hrs_end AS end_hours,
            pa.working_hours AS working_hours,
            ph.shift AS shift,
            ph.location AS site
        FROM `tabPre-Use Hours` ph
        JOIN `tabPre-use Assets` pa ON pa.parent = ph.name
        WHERE ph.shift_date BETWEEN %(start_date)s AND %(end_date)s
          AND ph.location = %(site)s
          {machine_condition}
          {shift_condition}
        ORDER BY ph.shift_date ASC
    """, values, as_dict=True)

    # Group by date
    by_date = {}
    for r in rows:
        by_date.setdefault(r.date, []).append(r)

    output = []

    for date in sorted(by_date.keys()):
        # ---------------------------------------------------------
        # COLLAPSED DATE ROW — remove ALL the 0s
        # ---------------------------------------------------------
        output.append({
            "date": date,
            "indent": 0,
            "machine": "",
            "start_hours": "",
            "end_hours": "",
            "working_hours": "",
            "shift": "",
            "site": ""
        })

        records = by_date[date]

        # Index rows by (machine, shift)
        index = {(r.machine, r.shift): r for r in records}

        # Enforced ordering
        for machine in MACHINE_ORDER:
            for shift in SHIFT_ORDER:
                key = (machine, shift)
                if key in index:
                    r = index[key]
                    r.indent = 1
                    output.append(r)

    return output
