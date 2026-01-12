import frappe
from datetime import datetime, timedelta

# =========================================================
# OPERATIONAL DAY (06:00 → 05:59)
# =========================================================
def get_operational_day():
    now = datetime.now()
    return now.date() - timedelta(days=1) if now.hour < 6 else now.date()


# =========================================================
# SITE HEADER COLOURS
# =========================================================
SITE_HEADER_COLOURS = {
    "Klipfontein": "#E6F0FA",
    "Gwab": "#F2F2F2",
    "Kriel Rehabilitation": "#E9F5EC",
    "Koppie": "#F7F3E8",
    "Uitgevallen": "#F1ECF8",
    "Bankfontein": "#FCEEE6"
}


# =========================================================
# MAIN EXECUTE
# =========================================================
def execute(filters=None):
    if not filters or not filters.get("monthly_production_plan"):
        return [], None, "<b>Please select a Monthly Production Plan</b>"

    plan = frappe.get_doc(
        "Define Monthly Production",
        filters.get("monthly_production_plan")
    )

    prod_date = get_operational_day()

    site_blocks = [
        build_site_block(row.site, prod_date)
        for row in plan.define
    ]

    html = f"""
    <style>
        body {{
            font-family: Arial, Helvetica, sans-serif;
        }}

        .dashboard {{
            display: grid;
            gap: 4px;
        }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 4px;
        }}

        .site {{
            border: 2px solid #003366;
            padding: 4px;
        }}

        .site-header {{
            text-align: center;
            font-weight: bold;
            font-size: 11px;
            margin-bottom: 2px;
            color: #003366;
            padding: 4px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
        }}

        th, td {{
            border: 1px solid #ccc;
            text-align: center;
            font-size: 10px;
            padding: 4px;
            height: 32px;
        }}

        th {{
            background: #EAF3FA;
            font-weight: bold;
        }}

        th.slot {{
            min-width: 34px;
        }}

        th:first-child,
        td:first-child {{
            text-align: left;
            font-weight: bold;
            width: 100px;
        }}

        /* BCM CELL COLOURS */
        .low {{
            background-color: #f8d7da;
        }}

        .medium {{
            background-color: #fff3cd;
        }}

        .high {{
            background-color: #d4edda;
        }}
    </style>

    <div class="dashboard">
        <div class="grid">
            {''.join(site_blocks)}
        </div>
    </div>
    """

    return [], None, html


# =========================================================
# SITE BLOCK
# =========================================================
def build_site_block(site, prod_date):
    slots = [str(i) for i in range(1, 25)]
    excavators = get_excavators(site)
    data = get_hourly_data(site, prod_date)

    header_colour = SITE_HEADER_COLOURS.get(site, "#FFFFFF")

    header = "<tr><th>Excavator</th>" + "".join(
        f"<th class='slot'>{s}</th>" for s in slots
    ) + "</tr>"

    rows = ""
    for ex in excavators:
        rows += f"<tr><td>{ex}</td>"
        for s in slots:
            value = int(data.get(ex, {}).get(s, 0))
            css_class = get_cell_class(value)
            rows += f"<td class='{css_class}'>{value}</td>"
        rows += "</tr>"

    return f"""
    <div class="site">
        <div class="site-header" style="background-color: {header_colour};">
            Site: {site}<br>
            Production Day: {prod_date}
        </div>
        <table>
            {header}
            {rows}
        </table>
    </div>
    """


# =========================================================
# CELL COLOUR LOGIC
# =========================================================
def get_cell_class(value):
    if value < 200:
        return "low"
    elif 200 <= value <= 219:
        return "medium"
    else:
        return "high"


# =========================================================
# EXCAVATORS
# =========================================================
def get_excavators(site):
    return [
        a.name for a in frappe.get_all(
            "Asset",
            filters={
                "location": site,
                "asset_category": "Excavator"
            },
            fields=["name"]
        )
    ]


# =========================================================
# DATA → SLOT MAPPING
# =========================================================
def get_hourly_data(site, prod_date):
    results = {}

    rows = frappe.db.sql("""
        SELECT
            tl.asset_name_shoval AS excavator,
            HOUR(tl.creation) AS hour,
            SUM(tl.bcms) AS bcm
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.location = %s
          AND hp.prod_date = %s
          AND tl.asset_name_shoval IS NOT NULL
        GROUP BY tl.asset_name_shoval, HOUR(tl.creation)
    """, (site, prod_date), as_dict=True)

    for r in rows:
        slot = ((r.hour - 6) % 24) + 1
        results.setdefault(r.excavator, {})[str(slot)] = int(r.bcm or 0)

    return results
