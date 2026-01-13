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
    "Klipfontein": "#4DA3FF",
    "Gwab": "#00B3A4",
    "Kriel Rehabilitation": "#2ECC71",
    "Koppie": "#F39C12",
    "Uitgevallen": "#9B59B6",
    "Bankfontein": "#E74C3C"
}


# =========================================================
# HEADER SLOT LABELS (06:00 → 05:59)
# =========================================================
SLOT_LABELS = [
    "6", "7", "8", "9", "10", "11", "12",
    "1", "2", "3", "4", "5",
    "6", "7", "8", "9", "10", "11", "12",
    "1", "2", "3", "4", "5"
]


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
            padding: 6px;
            color: #000000;
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

        /* CELL COLOURS */
        .low {{ background-color: #f8d7da; }}      /* Red */
        .medium {{ background-color: #fff3cd; }}   /* Yellow */
        .high {{ background-color: #d4edda; }}     /* Green */
        .blank {{ background-color: #ffffff; }}    /* White */
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
    excavators = get_excavators(site)
    data = get_hourly_data(site, prod_date)
    header_colour = SITE_HEADER_COLOURS.get(site, "#FFFFFF")

    header = "<tr><th>Excavator</th>" + "".join(
        f"<th class='slot'>{label}</th>" for label in SLOT_LABELS
    ) + "</tr>"

    rows = ""
    for ex in excavators:
        rows += f"<tr><td>{ex}</td>"
        for slot in range(1, 25):
            value = int(data.get(ex, {}).get(str(slot), 0))
            css_class, display = get_cell_display(value)
            rows += f"<td class='{css_class}'>{display}</td>"
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
# CELL DISPLAY + COLOUR RULES
# =========================================================
def get_cell_display(value):
    if value == 0:
        return "blank", ""
    elif 1 <= value <= 199:
        return "low", value
    elif 200 <= value <= 219:
        return "medium", value
    else:
        return "high", value


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
# DATA → SLOT MAPPING (06:00 → 05:59)
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
