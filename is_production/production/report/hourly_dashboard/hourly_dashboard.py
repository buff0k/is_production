# Copyright (c) 2026, Isambane Mining (Pty) Ltd
# CEO Dashboard Two – Hourly Excavator Production (Optimised)

import frappe
from datetime import datetime, timedelta


# =========================================================
# OPERATIONAL DAY (06:00 → 05:59)
# =========================================================
def get_operational_day():
    now = datetime.now()
    return now.date() - timedelta(days=1) if now.hour < 6 else now.date()


SITE_HEADER_COLOURS = {
    "Klipfontein": "#EBF9FF",
    "Gwab": "#f7d8ff",
    "Kriel Rehabilitation": "#E6D3B1",
    "Koppie": "#feff8d",
    "Uitgevallen": "#ffd37f",
    "Bankfontein": "#e3e3e3",
}

SLOT_LABELS = [
    "06-07", "07-08", "08-09", "09-10", "10-11", "11-12", "12-13",
    "13-14", "14-15", "15-16", "16-17", "17-18",
    "18-19", "19-20", "20-21", "21-22", "22-23", "23-24",
    "24-01", "01-02", "02-03", "03-04", "04-05", "05-06"
]

HOUR_SLOT_MAP = {
    "6:00-7:00": 1,
    "7:00-8:00": 2,
    "8:00-9:00": 3,
    "9:00-10:00": 4,
    "10:00-11:00": 5,
    "11:00-12:00": 6,
    "12:00-13:00": 7,
    "13:00-14:00": 8,
    "14:00-15:00": 9,
    "15:00-16:00": 10,
    "16:00-17:00": 11,
    "17:00-18:00": 12,
    "18:00-19:00": 13,
    "19:00-20:00": 14,
    "20:00-21:00": 15,
    "21:00-22:00": 16,
    "22:00-23:00": 17,
    "23:00-0:00": 18,
    "0:00-1:00": 19,
    "1:00-2:00": 20,
    "2:00-3:00": 21,
    "3:00-4:00": 22,
    "4:00-5:00": 23,
    "5:00-6:00": 24,
}


def execute(filters=None):
    if not filters or not filters.get("define_monthly_production"):
        return [], None, "<b>Please select a Monthly Production Plan</b>"

    plan = frappe.get_doc(
        "Define Monthly Production",
        filters.get("define_monthly_production")
    )

    prod_date = get_operational_day()

    excavators_by_site = get_all_excavators()
    hourly_data = get_all_hourly_data(prod_date)

    site_blocks = []
    for row in plan.define:
        site_blocks.append(
            build_site_block(
                site=row.site,
                prod_date=prod_date,
                excavators_by_site=excavators_by_site,
                hourly_data=hourly_data
            )
        )

    html = f"""
    <div class="isd-hourly-dashboard">
        <div class="isd-grid">
            {''.join(site_blocks)}
        </div>
    </div>
    """

    # Dummy row so Frappe doesn't show "Nothing to show"
    columns = [{"fieldname": "noop", "label": "", "fieldtype": "Data", "width": 1}]
    data = [{"noop": ""}]
    return columns, data, html


def build_site_block(site, prod_date, excavators_by_site, hourly_data):
    excavators = excavators_by_site.get(site, [])
    site_data = hourly_data.get(site, {})
    header_colour = SITE_HEADER_COLOURS.get(site, "#FFFFFF")

    def _hour_label_html(label: str) -> str:
        return frappe.utils.escape_html(label).replace("-", "<br>")

    header = "<tr><th>Excavator</th>" + "".join(
        f"<th title='{label}'>{_hour_label_html(label)}</th>" for label in SLOT_LABELS
    ) + "</tr>"

    rows = []
    for ex in excavators:
        cells = [f"<td class='isd-ex' title='{ex}'>{ex}</td>"]
        ex_data = site_data.get(ex, {})

        for slot in range(1, 25):
            value = int(ex_data.get(str(slot), 0))
            css_class, display, title = get_cell_display(value)
            title_attr = f" title='{title}'" if title else ""
            cells.append(f"<td class='{css_class}'{title_attr}>{display}</td>")

        rows.append("<tr>" + "".join(cells) + "</tr>")

    return f"""
    <div class="isd-site">
        <div class="isd-site-header" style="background-color: {header_colour};">
            <div>Site: {site}</div>
            <div class="isd-site-sub">Production Day: {prod_date}</div>
        </div>

        <div class="isd-table-wrap">
            <table>
                {header}
                {''.join(rows)}
            </table>
        </div>
    </div>
    """


def get_cell_display(value):
    if value == 0:
        return "isd-blank", "", ""
    elif 1 <= value <= 199:
        return "isd-low", value, f"{value} bcm"
    elif 200 <= value <= 219:
        return "isd-medium", value, f"{value} bcm"
    else:
        return "isd-high", value, f"{value} bcm"


def get_all_excavators():
    rows = frappe.get_all(
        "Asset",
        filters={"asset_category": "Excavator", "docstatus": 1},
        fields=["name", "location"]
    )

    excavators = {}
    for r in rows:
        if r.location:
            excavators.setdefault(r.location, []).append(r.name)

    # stable order helps readability
    for k in excavators:
        excavators[k].sort()

    return excavators


def get_all_hourly_data(prod_date):
    rows = frappe.db.sql("""
        SELECT
            hp.location AS site,
            tl.asset_name_shoval AS excavator,
            hp.hour_slot AS hour_slot,
            SUM(tl.bcms) AS bcm
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.prod_date = %s
          AND tl.asset_name_shoval IS NOT NULL
        GROUP BY
            hp.location,
            tl.asset_name_shoval,
            hp.hour_slot
    """, prod_date, as_dict=True)

    data = {}

    for r in rows:
        slot = HOUR_SLOT_MAP.get(r.hour_slot)
        if not slot:
            continue

        data.setdefault(r.site, {}).setdefault(r.excavator, {})[str(slot)] = int(r.bcm or 0)

    return data
