import frappe
from frappe import _

# Enforced allowed machines
MACHINE_ORDER = ["EX01", "ADT01", "ADT02", "ADT03", "ADT04"]
SHIFT_ORDER = ["Day", "Night"]


def execute(filters=None):
    filters = frappe._dict(filters or {})

    if not (filters.start_date and filters.end_date):
        return [], [], None, None, []

    columns = get_columns()
    data = get_data(filters)
    return columns, data, None, None, []


# -----------------------------
# Columns (Shift removed)
# -----------------------------
def get_columns():
    return [
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Data", "width": 120, "group": 1},
        {"label": _("Machine"), "fieldname": "machine", "fieldtype": "Data", "width": 140},
        {"label": _("Litres Issued"), "fieldname": "litres_issued", "fieldtype": "Float", "width": 140},
        {"label": _("Site"), "fieldname": "site", "fieldtype": "Data", "width": 120},
    ]


# -----------------------------
# Data Builder
# -----------------------------
def get_data(filters):
    values = {
        "start_date": filters.start_date,
        "end_date": filters.end_date,
    }

    site_condition = ""
    if filters.get("site"):
        site_condition = "AND ph.location = %(site)s"
        values["site"] = filters.site

    shift_condition = ""
    if filters.get("shift"):
        shift_condition = "AND ph.shift = %(shift)s"
        values["shift"] = filters.shift

    machine_condition = ""
    if filters.get("machine"):
        machine_condition = "AND de.asset_name = %(machine)s"
        values["machine"] = filters.machine

    # Pull diesel entries
    rows = frappe.db.sql(f"""
        SELECT
            ph.daily_sheet_date AS date,
            de.asset_name AS machine,
            de.litres_issued AS litres_issued,
            ph.location AS site,
            ph.shift AS shift
        FROM `tabDaily Diesel Sheet` ph
        JOIN `tabDaily Diesel Entries` de ON de.parent = ph.name
        WHERE ph.daily_sheet_date BETWEEN %(start_date)s AND %(end_date)s
          {site_condition}
          {shift_condition}
          {machine_condition}
        ORDER BY ph.daily_sheet_date ASC
    """, values, as_dict=True)

    # Group entries per date
    grouped = {}
    for r in rows:
        grouped.setdefault(r.date, []).append(r)

    output = []

    for date in sorted(grouped.keys()):
        records = grouped[date]

        # Only sum litres for allowed machines
        total_litres = sum(
            (r.litres_issued or 0)
            for r in records
            if r.machine in MACHINE_ORDER
        )

        # Header row (collapsed)
        output.append({
            "date": date,
            "indent": 0,
            "machine": "",
            "litres_issued": total_litres,
            "site": ""
        })

        # Prepare lookup for fast indexing
        index = {(r.machine, r.shift): r for r in records}

        # Detail rows
        for machine in MACHINE_ORDER:
            for shift in SHIFT_ORDER:
                key = (machine, shift)
                if key in index:
                    r = index[key]
                    output.append({
                        "indent": 1,
                        "date": "",
                        "machine": r.machine,
                        "litres_issued": r.litres_issued,
                        "site": r.site
                    })

    return output
