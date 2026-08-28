import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
    filters = frappe._dict(filters or {})

    validate_filters(filters)

    view = filters.get("view") or "Hourly Summary"

    if view == "Daily Summary":
        return get_daily_summary(filters)

    if view == "Machine Totals":
        return get_machine_totals(filters)


    if view == "Combined ADT Totals":
        return get_combined_adt_totals(filters)
    return get_hourly_summary(filters)


# ============================================================
# VALIDATION
# ============================================================

def validate_filters(filters):
    if not filters.get("from_date"):
        frappe.throw(_("Start Date is required."))

    if not filters.get("to_date"):
        frappe.throw(_("End Date is required."))

    if getdate(filters.from_date) > getdate(filters.to_date):
        frappe.throw(_("Start Date cannot be after End Date."))


# ============================================================
# COMMON CONDITIONS
# ============================================================

def get_conditions(filters):
    conditions = [
        "hp.prod_date BETWEEN %(from_date)s AND %(to_date)s",

        "tl.parenttype = 'Hourly Production'",
        "tl.parentfield = 'truck_loads'",

        # ----------------------------------------------------
        # CRITICAL PRODUCTIVITY RULE
        # ----------------------------------------------------
        # Only count an ADT when it ACTUALLY loaded.
        # Selected trucks with zero loads are excluded.
        # ----------------------------------------------------
        "COALESCE(tl.loads, 0) > 0",

        # Must be attached to both an Excavator and ADT.
        "COALESCE(tl.asset_name_shoval, '') != ''",
        "COALESCE(tl.asset_name_truck, '') != ''",
    ]

    values = {
        "from_date": filters.from_date,
        "to_date": filters.to_date,
    }

    if filters.get("site"):
        conditions.append("hp.location = %(site)s")
        values["site"] = filters.site

    if filters.get("excavator"):
        conditions.append(
            "tl.asset_name_shoval = %(excavator)s"
        )
        values["excavator"] = filters.excavator

    if filters.get("adt"):
        conditions.append(
            "tl.asset_name_truck = %(adt)s"
        )
        values["adt"] = filters.adt

    return " AND ".join(conditions), values


# ============================================================
# DAILY BY MACHINE
# Date -> Excavator -> ADT
# ============================================================

def get_daily_by_machine(filters):
    columns = [
        {
            "label": _("Date"),
            "fieldname": "prod_date",
            "fieldtype": "Date",
            "width": 105,
        },
        {
            "label": _("Site"),
            "fieldname": "site",
            "fieldtype": "Link",
            "options": "Location",
            "width": 145,
        },
        {
            "label": _("Excavator"),
            "fieldname": "excavator",
            "fieldtype": "Link",
            "options": "Asset",
            "width": 120,
        },
        {
            "label": _("Excavator Model"),
            "fieldname": "excavator_model",
            "fieldtype": "Data",
            "width": 165,
        },
        {
            "label": _("ADT"),
            "fieldname": "adt",
            "fieldtype": "Link",
            "options": "Asset",
            "width": 115,
        },
        {
            "label": _("ADT Model"),
            "fieldname": "adt_model",
            "fieldtype": "Data",
            "width": 155,
        },
        {
            "label": _("Material"),
            "fieldname": "material",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": _("Loads"),
            "fieldname": "loads",
            "fieldtype": "Int",
            "width": 80,
        },
        {
            "label": _("BCM"),
            "fieldname": "bcms",
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "label": _("Loading Hrs"),
            "fieldname": "loading_hours",
            "fieldtype": "Int",
            "width": 105,
        },
        {
            "label": _("BCM/Hr"),
            "fieldname": "bcm_per_hour",
            "fieldtype": "Float",
            "precision": 2,
            "width": 95,
        },
        {
            "label": _("Loads/Hr"),
            "fieldname": "loads_per_hour",
            "fieldtype": "Float",
            "precision": 2,
            "width": 95,
        },
        {
            "label": _("Avg BCM/Load"),
            "fieldname": "bcm_per_load",
            "fieldtype": "Float",
            "precision": 2,
            "width": 110,
        },
    ]

    # ========================================================
    # DETAIL CONDITIONS
    #
    # These obey ALL filters, including ADT.
    # ========================================================

    detail_conditions, detail_values = get_conditions(filters)

    detail_data = frappe.db.sql(
        f"""
        SELECT
            hp.prod_date AS prod_date,
            hp.location AS site,

            tl.asset_name_shoval AS excavator,

            MAX(
                COALESCE(
                    NULLIF(asset_exc.item_name, ''),
                    NULLIF(tl.item_name_excavator, ''),
                    ''
                )
            ) AS excavator_model,

            tl.asset_name_truck AS adt,

            MAX(
                COALESCE(
                    NULLIF(tl.item_name, ''),
                    ''
                )
            ) AS adt_model,

            GROUP_CONCAT(
                DISTINCT NULLIF(tl.mat_type, '')
                ORDER BY tl.mat_type
                SEPARATOR ', '
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT hp.name
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        LEFT JOIN `tabAsset` asset_exc
            ON asset_exc.name = tl.asset_name_shoval

        WHERE
            {detail_conditions}

        GROUP BY
            hp.prod_date,
            hp.location,
            tl.asset_name_shoval,
            tl.asset_name_truck

        ORDER BY
            hp.prod_date,
            hp.location,
            tl.asset_name_shoval,
            tl.asset_name_truck
        """,
        detail_values,
        as_dict=True,
    )

    calculate_productivity(detail_data)

    # ========================================================
    # TRUE EXCAVATOR TOTAL CONDITIONS
    #
    # IMPORTANT:
    #
    # The ADT filter is intentionally removed here.
    #
    # If user selects IS614:
    #
    # Detail:
    #   Only IS614 rows
    #
    # Excavator TOTAL:
    #   ALL ADTs that actually loaded on that excavator
    #
    # Date, Site and Excavator filters still apply.
    # ========================================================

    total_filters = frappe._dict({
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date"),
        "site": filters.get("site"),
        "excavator": filters.get("excavator"),

        # Intentionally ignored for excavator totals
        "adt": None,
    })

    total_conditions, total_values = get_conditions(
        total_filters
    )

    excavator_totals = frappe.db.sql(
        f"""
        SELECT
            hp.prod_date AS prod_date,
            hp.location AS site,

            tl.asset_name_shoval AS excavator,

            MAX(
                COALESCE(
                    NULLIF(asset_exc.item_name, ''),
                    NULLIF(tl.item_name_excavator, ''),
                    ''
                )
            ) AS excavator_model,

            COUNT(
                DISTINCT tl.asset_name_truck
            ) AS adt_count,

            GROUP_CONCAT(
                DISTINCT NULLIF(tl.mat_type, '')
                ORDER BY tl.mat_type
                SEPARATOR ', '
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT hp.name
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        LEFT JOIN `tabAsset` asset_exc
            ON asset_exc.name = tl.asset_name_shoval

        WHERE
            {total_conditions}

        GROUP BY
            hp.prod_date,
            hp.location,
            tl.asset_name_shoval

        ORDER BY
            hp.prod_date,
            hp.location,
            tl.asset_name_shoval
        """,
        total_values,
        as_dict=True,
    )

    calculate_productivity(excavator_totals)

    totals_map = {}

    for total in excavator_totals:
        key = (
            str(total.get("prod_date") or ""),
            str(total.get("site") or ""),
            str(total.get("excavator") or ""),
        )

        totals_map[key] = total

    # ========================================================
    # DISPLAY LOGIC
    # ========================================================
    #
    # If ADT filter is selected:
    #
    #   Show only the ADT detail rows.
    #   Do NOT show Excavator TOTAL rows.
    #   Add ONE ADT TOTAL row at the bottom.
    #
    # If no ADT filter:
    #
    #   Keep the Excavator TOTAL rows.
    # ========================================================

    if filters.get("adt"):
        final_data = list(detail_data)

        adt_total = get_selected_adt_total(
            filters
        )

        if adt_total:
            final_data.append(adt_total)

        return columns, final_data

    final_data = []

    current_key = None

    for row in detail_data:
        key = (
            str(row.get("prod_date") or ""),
            str(row.get("site") or ""),
            str(row.get("excavator") or ""),
        )

        if (
            current_key is not None
            and key != current_key
        ):
            total = totals_map.get(current_key)

            if total:
                final_data.append(
                    make_excavator_total_row(total)
                )

        final_data.append(row)
        current_key = key

    if current_key is not None:
        total = totals_map.get(current_key)

        if total:
            final_data.append(
                make_excavator_total_row(total)
            )

    return columns, final_data



def get_selected_adt_total(filters):
    """
    Return ONE total row for the selected ADT.

    Important:
    Loading hours are unique Hourly Production records.

    Therefore if the same ADT somehow appears against more
    than one excavator in the same hour, that hour is counted
    only once in the ADT TOTAL.
    """

    conditions, values = get_conditions(filters)

    rows = frappe.db.sql(
        f"""
        SELECT
            MIN(hp.prod_date) AS prod_date,

            CASE
                WHEN COUNT(
                    DISTINCT hp.prod_date
                ) = 1
                THEN MIN(hp.prod_date)
                ELSE NULL
            END AS single_date,

            CASE
                WHEN COUNT(
                    DISTINCT hp.location
                ) = 1
                THEN MAX(hp.location)
                ELSE 'Multiple Sites'
            END AS site,

            tl.asset_name_truck AS adt,

            MAX(
                COALESCE(
                    NULLIF(tl.item_name, ''),
                    ''
                )
            ) AS adt_model,

            GROUP_CONCAT(
                DISTINCT NULLIF(tl.mat_type, '')
                ORDER BY tl.mat_type
                SEPARATOR ', '
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT hp.name
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        LEFT JOIN `tabAsset` asset_exc
            ON asset_exc.name = tl.asset_name_shoval

        WHERE
            {conditions}

        GROUP BY
            tl.asset_name_truck
        """,
        values,
        as_dict=True,
    )

    if not rows:
        return None

    total = rows[0]

    calculate_productivity([total])

    selected_adt = (
        filters.get("adt")
        or total.get("adt")
        or ""
    )

    return {
        "prod_date": (
            total.get("single_date")
            or None
        ),

        "site": total.get("site"),

        "excavator": (
            f"{selected_adt} TOTAL"
        ),

        "excavator_model": "",

        "adt": "",

        "adt_model": total.get(
            "adt_model"
        ),

        "material": total.get(
            "material"
        ),

        "loads": total.get(
            "loads"
        ),

        "bcms": total.get(
            "bcms"
        ),

        "loading_hours": total.get(
            "loading_hours"
        ),

        "bcm_per_hour": total.get(
            "bcm_per_hour"
        ),

        "loads_per_hour": total.get(
            "loads_per_hour"
        ),

        "bcm_per_load": total.get(
            "bcm_per_load"
        ),

        "is_excavator_total": 1,
        "is_adt_total": 1,
    }


def make_excavator_total_row(total):
    excavator = total.get("excavator") or ""

    return {
        "prod_date": total.get("prod_date"),

        "site": total.get("site"),

        "excavator": (
            f"{excavator} TOTAL"
        ),

        "excavator_model": total.get(
            "excavator_model"
        ),

        "adt": "",

        "adt_model": (
            f"{int(total.get('adt_count') or 0)} ADTs"
        ),

        "material": total.get("material"),

        "loads": total.get("loads"),

        "bcms": total.get("bcms"),

        # This is actual EXCAVATOR ACTIVE HOURS.
        "loading_hours": total.get(
            "loading_hours"
        ),

        "bcm_per_hour": total.get(
            "bcm_per_hour"
        ),

        "loads_per_hour": total.get(
            "loads_per_hour"
        ),

        "bcm_per_load": total.get(
            "bcm_per_load"
        ),

        "is_excavator_total": 1,
    }


# ============================================================
# DAILY SUMMARY
# Date -> Excavator
#
# Important:
# Excavator Active Hrs is NOT the sum of ADT hours.
#
# Example:
# 6 ADTs loading on EX01 during 10:00-11:00
#
# Excavator Active Hrs = 1
# not 6
# ============================================================

def get_daily_summary(filters):
    """
    Tree structure:

    Date
        Excavator TOTAL FULL DAY
            Day
            Night
    """

    columns = [
        {
            "label": _("Date"),
            "fieldname": "prod_date",
            "fieldtype": "Date",
            "width": 105,
        },
        {
            "label": _("Site"),
            "fieldname": "site",
            "fieldtype": "Link",
            "options": "Location",
            "width": 130,
        },
        {
            "label": _("Excavator"),
            "fieldname": "excavator",
            "fieldtype": "Data",
            "width": 175,
        },
        {
            "label": _("Excavator Plant No"),
            "fieldname": "excavator_plant_no",
            "fieldtype": "Data",
            "width": 125,
        },
        {
            "label": _("Excavator Model"),
            "fieldname": "excavator_model",
            "fieldtype": "Data",
            "width": 170,
        },
        {
            "label": _("Unique ADTs Loaded"),
            "fieldname": "adt_count",
            "fieldtype": "Int",
            "width": 95,
        },
        {
            "label": _("Materials"),
            "fieldname": "material",
            "fieldtype": "Data",
            "width": 125,
        },
        {
            "label": _("Loads"),
            "fieldname": "loads",
            "fieldtype": "Int",
            "width": 80,
        },
        {
            "label": _("BCM"),
            "fieldname": "bcms",
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "label": _("Excavator Active Hrs"),
            "fieldname": "loading_hours",
            "fieldtype": "Int",
            "width": 140,
        },
        {
            "label": _("BCM/Exc Hr"),
            "fieldname": "bcm_per_hour",
            "fieldtype": "Float",
            "precision": 2,
            "width": 100,
        },
        {
            "label": _("Loads/Exc Hr"),
            "fieldname": "loads_per_hour",
            "fieldtype": "Float",
            "precision": 2,
            "width": 100,
        },
        {
            "label": _("Avg BCM/Load"),
            "fieldname": "bcm_per_load",
            "fieldtype": "Float",
            "precision": 2,
            "width": 105,
        },
    ]

    conditions, values = get_conditions(filters)

    # ========================================================
    # DATE TOTALS
    # ========================================================

    date_rows = frappe.db.sql(
        f"""
        SELECT
            hp.prod_date AS prod_date,
            hp.location AS site,

            COUNT(
                DISTINCT tl.asset_name_shoval
            ) AS excavator_count,

            COUNT(
                DISTINCT tl.asset_name_truck
            ) AS adt_count,

            GROUP_CONCAT(
                DISTINCT NULLIF(tl.mat_type, '')
                ORDER BY tl.mat_type
                SEPARATOR ', '
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT CONCAT(
                    hp.name,
                    '|',
                    tl.asset_name_shoval
                )
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        WHERE
            {conditions}

        GROUP BY
            hp.prod_date,
            hp.location

        ORDER BY
            hp.prod_date,
            hp.location
        """,
        values,
        as_dict=True,
    )

    calculate_productivity(date_rows)

    # ========================================================
    # FULL DAY TOTAL PER EXCAVATOR
    # ========================================================

    full_day_rows = frappe.db.sql(
        f"""
        SELECT
            hp.prod_date AS prod_date,
            hp.location AS site,

            tl.asset_name_shoval AS excavator,

            tl.asset_name_shoval AS excavator_plant_no,

            MAX(
                COALESCE(
                    NULLIF(asset_exc.item_name, ''),
                    NULLIF(tl.item_name_excavator, ''),
                    ''
                )
            ) AS excavator_model,

            COUNT(
                DISTINCT tl.asset_name_truck
            ) AS adt_count,

            GROUP_CONCAT(
                DISTINCT NULLIF(tl.mat_type, '')
                ORDER BY tl.mat_type
                SEPARATOR ', '
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT hp.name
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        LEFT JOIN `tabAsset` asset_exc
            ON asset_exc.name = tl.asset_name_shoval

        WHERE
            {conditions}

        GROUP BY
            hp.prod_date,
            hp.location,
            tl.asset_name_shoval

        ORDER BY
            hp.prod_date,
            hp.location,
            tl.asset_name_shoval
        """,
        values,
        as_dict=True,
    )

    calculate_productivity(full_day_rows)

    # ========================================================
    # DAY / NIGHT PER EXCAVATOR
    # ========================================================

    shift_rows = frappe.db.sql(
        f"""
        SELECT
            hp.prod_date AS prod_date,
            hp.location AS site,
            hp.shift AS shift,

            tl.asset_name_shoval AS excavator,

            tl.asset_name_shoval AS excavator_plant_no,

            MAX(
                COALESCE(
                    NULLIF(asset_exc.item_name, ''),
                    NULLIF(tl.item_name_excavator, ''),
                    ''
                )
            ) AS excavator_model,

            COUNT(
                DISTINCT tl.asset_name_truck
            ) AS adt_count,

            GROUP_CONCAT(
                DISTINCT NULLIF(tl.mat_type, '')
                ORDER BY tl.mat_type
                SEPARATOR ', '
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT hp.name
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        LEFT JOIN `tabAsset` asset_exc
            ON asset_exc.name = tl.asset_name_shoval

        WHERE
            {conditions}

        GROUP BY
            hp.prod_date,
            hp.location,
            tl.asset_name_shoval,
            hp.shift

        ORDER BY
            hp.prod_date,
            hp.location,
            tl.asset_name_shoval,

            CASE
                WHEN hp.shift = 'Day' THEN 1
                WHEN hp.shift = 'Morning' THEN 1
                WHEN hp.shift = 'Afternoon' THEN 2
                WHEN hp.shift = 'Night' THEN 3
                ELSE 9
            END,

            hp.shift
        """,
        values,
        as_dict=True,
    )

    calculate_productivity(shift_rows)

    # ========================================================
    # MAP FULL-DAY EXCAVATORS BY DATE
    # ========================================================

    full_day_map = {}

    for row in full_day_rows:

        key = (
            str(row.get("prod_date") or ""),
            str(row.get("site") or ""),
        )

        full_day_map.setdefault(
            key,
            []
        ).append(row)

    # ========================================================
    # MAP SHIFTS BY DATE + SITE + EXCAVATOR
    # ========================================================

    shift_map = {}

    for row in shift_rows:

        key = (
            str(row.get("prod_date") or ""),
            str(row.get("site") or ""),
            str(row.get("excavator") or ""),
        )

        shift_map.setdefault(
            key,
            []
        ).append(row)

    # ========================================================
    # BUILD TREE
    #
    # DATE
    #   EX01 TOTAL FULL DAY
    #       Day
    #       Night
    #
    #   IS0330 TOTAL FULL DAY
    #       Day
    #       Night
    # ========================================================

    data = []

    for day in date_rows:

        prod_date = str(
            day.get("prod_date")
            or ""
        )

        site = str(
            day.get("site")
            or ""
        )

        date_key = (
            "DATE|"
            + prod_date
            + "|"
            + site
        )

        # ----------------------------------------------------
        # DATE PARENT
        # ----------------------------------------------------

        data.append({
            "prod_date": day.get("prod_date"),

            "site": site,

            "excavator": (
                f"{int(day.get('excavator_count') or 0)} Excavators"
            ),

            "excavator_plant_no": "",

            "excavator_model": "",

            "adt_count": int(
                day.get("adt_count")
                or 0
            ),

            "material": day.get(
                "material"
            ) or "",

            "loads": day.get(
                "loads"
            ) or 0,

            "bcms": day.get(
                "bcms"
            ) or 0,

            "loading_hours": day.get(
                "loading_hours"
            ) or 0,

            "bcm_per_hour": day.get(
                "bcm_per_hour"
            ) or 0,

            "loads_per_hour": day.get(
                "loads_per_hour"
            ) or 0,

            "bcm_per_load": day.get(
                "bcm_per_load"
            ) or 0,

            "indent": 0,

            "is_group": 1,

            "tree_key": date_key,

            "parent_tree_key": None,

            "is_date_total": 1,
        })

        # ----------------------------------------------------
        # EXCAVATOR FULL DAY
        # ----------------------------------------------------

        excavators = full_day_map.get(
            (
                prod_date,
                site,
            ),
            []
        )

        for excavator_row in excavators:

            excavator = str(
                excavator_row.get("excavator")
                or ""
            )

            full_day_key = (
                date_key
                + "|EXC|"
                + excavator
            )

            shifts = shift_map.get(
                (
                    prod_date,
                    site,
                    excavator,
                ),
                []
            )

            data.append({
                "prod_date": None,

                "site": site,

                "excavator": (
                    excavator
                    + " TOTAL FULL DAY"
                ),

                "excavator_plant_no":
                    excavator,

                "excavator_model":
                    excavator_row.get(
                        "excavator_model"
                    ) or "",

                "adt_count": int(
                    excavator_row.get(
                        "adt_count"
                    ) or 0
                ),

                "material":
                    excavator_row.get(
                        "material"
                    ) or "",

                "loads":
                    excavator_row.get(
                        "loads"
                    ) or 0,

                "bcms":
                    excavator_row.get(
                        "bcms"
                    ) or 0,

                "loading_hours":
                    excavator_row.get(
                        "loading_hours"
                    ) or 0,

                "bcm_per_hour":
                    excavator_row.get(
                        "bcm_per_hour"
                    ) or 0,

                "loads_per_hour":
                    excavator_row.get(
                        "loads_per_hour"
                    ) or 0,

                "bcm_per_load":
                    excavator_row.get(
                        "bcm_per_load"
                    ) or 0,

                "indent": 1,

                "is_group": (
                    1
                    if shifts
                    else 0
                ),

                "tree_key":
                    full_day_key,

                "parent_tree_key":
                    date_key,

                "is_excavator_full_day":
                    1,
            })

            # ------------------------------------------------
            # DAY / NIGHT CHILDREN
            # ------------------------------------------------

            for shift_row in shifts:

                shift = str(
                    shift_row.get("shift")
                    or "Unknown"
                )

                shift_key = (
                    full_day_key
                    + "|SHIFT|"
                    + shift
                )

                data.append({
                    "prod_date": None,

                    "site": "",

                    "excavator": (
                        "↳ "
                        + shift
                    ),

                    "excavator_plant_no":
                        excavator,

                    "excavator_model":
                        shift_row.get(
                            "excavator_model"
                        ) or "",

                    "adt_count": int(
                        shift_row.get(
                            "adt_count"
                        ) or 0
                    ),

                    "material":
                        shift_row.get(
                            "material"
                        ) or "",

                    "loads":
                        shift_row.get(
                            "loads"
                        ) or 0,

                    "bcms":
                        shift_row.get(
                            "bcms"
                        ) or 0,

                    "loading_hours":
                        shift_row.get(
                            "loading_hours"
                        ) or 0,

                    "bcm_per_hour":
                        shift_row.get(
                            "bcm_per_hour"
                        ) or 0,

                    "loads_per_hour":
                        shift_row.get(
                            "loads_per_hour"
                        ) or 0,

                    "bcm_per_load":
                        shift_row.get(
                            "bcm_per_load"
                        ) or 0,

                    "indent": 2,

                    "is_group": 0,

                    "tree_key":
                        shift_key,

                    "parent_tree_key":
                        full_day_key,

                    "shift":
                        shift,
                })

    # ========================================================
    
    # ========================================================
    # MAXIMUM UNIQUE ADTs LOADED ON ANY SINGLE DAY
    #
    # Example July Klipfontein:
    # monthly distinct machines = 46
    # maximum actually loaded on one day = 41
    #
    # Daily Summary Grand Total uses 41.
    # ========================================================

    max_daily_adt_rows = frappe.db.sql(
        f"""
        SELECT
            MAX(day_data.unique_adts) AS max_unique_adts
        FROM (
            SELECT
                hp.prod_date,

                COUNT(
                    DISTINCT tl.asset_name_truck
                ) AS unique_adts

            FROM `tabTruck Loads` tl

            INNER JOIN `tabHourly Production` hp
                ON hp.name = tl.parent

            WHERE
                {conditions}

            GROUP BY
                hp.prod_date
        ) day_data
        """,
        values,
        as_dict=True,
    )

    max_daily_adts = 0

    if max_daily_adt_rows:
        max_daily_adts = int(
            max_daily_adt_rows[0].get(
                "max_unique_adts"
            )
            or 0
        )

# GRAND TOTAL
    # ========================================================

    grand_rows = frappe.db.sql(
        f"""
        SELECT
            COUNT(
                DISTINCT tl.asset_name_shoval
            ) AS excavator_count,

            COUNT(
                DISTINCT tl.asset_name_truck
            ) AS adt_count,

            GROUP_CONCAT(
                DISTINCT NULLIF(tl.mat_type, '')
                ORDER BY tl.mat_type
                SEPARATOR ', '
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT CONCAT(
                    hp.name,
                    '|',
                    tl.asset_name_shoval
                )
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        WHERE
            {conditions}
        """,
        values,
        as_dict=True,
    )

    if grand_rows:

        grand = grand_rows[0]

        calculate_productivity(
            [grand]
        )

        data.append({
            "prod_date": None,

            "site": "",

            "excavator":
                "GRAND TOTAL",

            "excavator_plant_no": "",

            "excavator_model": (
                f"{int(grand.get('excavator_count') or 0)} "
                "Unique Excavators"
            ),

            "adt_count":
                max_daily_adts,

            "material":
                grand.get(
                    "material"
                ) or "",

            "loads":
                grand.get(
                    "loads"
                ) or 0,

            "bcms":
                grand.get(
                    "bcms"
                ) or 0,

            "loading_hours":
                grand.get(
                    "loading_hours"
                ) or 0,

            "bcm_per_hour":
                grand.get(
                    "bcm_per_hour"
                ) or 0,

            "loads_per_hour":
                grand.get(
                    "loads_per_hour"
                ) or 0,

            "bcm_per_load":
                grand.get(
                    "bcm_per_load"
                ) or 0,

            "indent": 0,

            "is_group": 0,

            "tree_key":
                "DAILY-GRAND-TOTAL",

            "parent_tree_key":
                None,

            "is_grand_total": 1,
        })

    return columns, data

def get_machine_totals(filters):
    columns = [
        {
            "label": _("Site"),
            "fieldname": "site",
            "fieldtype": "Link",
            "options": "Location",
            "width": 135,
        },
        {
            "label": _("Excavator"),
            "fieldname": "excavator",
            "fieldtype": "Link",
            "options": "Asset",
            "width": 120,
        },
        {
            "label": _("Excavator Model"),
            "fieldname": "excavator_model",
            "fieldtype": "Data",
            "width": 175,
        },
        {
            "label": _("ADT"),
            "fieldname": "adt",
            "fieldtype": "Data",
            "width": 115,
        },
        {
            "label": _("ADT Model"),
            "fieldname": "adt_model",
            "fieldtype": "Data",
            "width": 160,
        },
        {
            "label": _("Material"),
            "fieldname": "material",
            "fieldtype": "Data",
            "width": 110,
        },
        {
            "label": _("Loads"),
            "fieldname": "loads",
            "fieldtype": "Int",
            "width": 80,
        },
        {
            "label": _("BCM"),
            "fieldname": "bcms",
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "label": _("Loading Hrs"),
            "fieldname": "loading_hours",
            "fieldtype": "Int",
            "width": 105,
        },
        {
            "label": _("BCM/Hr"),
            "fieldname": "bcm_per_hour",
            "fieldtype": "Float",
            "precision": 2,
            "width": 95,
        },
        {
            "label": _("Loads/Hr"),
            "fieldname": "loads_per_hour",
            "fieldtype": "Float",
            "precision": 2,
            "width": 95,
        },
        {
            "label": _("Avg BCM/Load"),
            "fieldname": "bcm_per_load",
            "fieldtype": "Float",
            "precision": 2,
            "width": 110,
        },
    ]

    conditions, values = get_conditions(filters)

    # ========================================================
    # DETAIL
    #
    # Site -> Excavator -> ADT -> Material
    #
    # Material stays split:
    #
    # IS0331
    #   IS0604 | Coal
    #           | Hards
    # ========================================================

    detail_data = frappe.db.sql(
        f"""
        SELECT
            hp.location AS site,

            tl.asset_name_shoval AS excavator,

            MAX(
                COALESCE(
                    NULLIF(asset_exc.item_name, ''),
                    NULLIF(tl.item_name_excavator, ''),
                    ''
                )
            ) AS excavator_model,

            tl.asset_name_truck AS adt,

            MAX(
                COALESCE(
                    NULLIF(asset_adt.item_name, ''),
                    NULLIF(tl.item_name, ''),
                    ''
                )
            ) AS adt_model,

            COALESCE(
                GROUP_CONCAT(
                    DISTINCT NULLIF(tl.mat_type, '')
                    ORDER BY tl.mat_type
                    SEPARATOR ', '
                ),
                'Unknown'
            ) AS material,

            COUNT(
                DISTINCT NULLIF(tl.mat_type, '')
            ) AS material_count,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT hp.name
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        LEFT JOIN `tabAsset` asset_exc
            ON asset_exc.name = tl.asset_name_shoval

        LEFT JOIN `tabAsset` asset_adt
            ON asset_adt.name = tl.asset_name_truck

        WHERE
            {conditions}

        GROUP BY
            hp.location,
            tl.asset_name_shoval,
            tl.asset_name_truck

        ORDER BY
            hp.location,
            tl.asset_name_shoval,
            tl.asset_name_truck
        """,
        values,
        as_dict=True,
    )

    calculate_productivity(detail_data)

    if not detail_data:
        return columns, []

    # ========================================================
    # EXCAVATOR TOTAL
    #
    # One subtotal after all ADTs for that excavator.
    #
    # Active hours:
    # Count each Hourly Production slot once for excavator.
    # ========================================================

    excavator_totals = frappe.db.sql(
        f"""
        SELECT
            hp.location AS site,

            tl.asset_name_shoval AS excavator,

            MAX(
                COALESCE(
                    NULLIF(asset_exc.item_name, ''),
                    NULLIF(tl.item_name_excavator, ''),
                    ''
                )
            ) AS excavator_model,

            COUNT(
                DISTINCT tl.asset_name_truck
            ) AS adt_count,

            GROUP_CONCAT(
                DISTINCT NULLIF(tl.mat_type, '')
                ORDER BY tl.mat_type
                SEPARATOR ', '
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT hp.name
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        LEFT JOIN `tabAsset` asset_exc
            ON asset_exc.name = tl.asset_name_shoval

        WHERE
            {conditions}

        GROUP BY
            hp.location,
            tl.asset_name_shoval

        ORDER BY
            hp.location,
            tl.asset_name_shoval
        """,
        values,
        as_dict=True,
    )

    calculate_productivity(excavator_totals)

    totals_map = {}

    for total in excavator_totals:
        key = (
            str(total.get("site") or ""),
            str(total.get("excavator") or ""),
        )

        totals_map[key] = total

    # ========================================================
    # BUILD:
    #
    # EX01
    #   ADT01
    #   ADT02
    #   ...
    # EX01 TOTAL
    #
    # IS0330
    #   ...
    # IS0330 TOTAL
    # ========================================================

    final_data = []

    current_key = None

    for row in detail_data:
        key = (
            str(row.get("site") or ""),
            str(row.get("excavator") or ""),
        )

        if current_key is not None and key != current_key:
            total = totals_map.get(current_key)

            if total:
                final_data.append(
                    make_machine_excavator_total_row(total)
                )

        final_data.append(row)
        current_key = key

    if current_key is not None:
        total = totals_map.get(current_key)

        if total:
            final_data.append(
                make_machine_excavator_total_row(total)
            )

    # ========================================================
    # GRAND TOTAL
    #
    # Loads / BCM / Hours:
    # Add EXCAVATOR SUBTOTALS only.
    #
    # Unique ADTs:
    # same ADT on several excavators counts ONCE.
    # ========================================================

    unique_adts = {
        str(row.get("adt") or "").strip()
        for row in detail_data
        if str(row.get("adt") or "").strip()
    }

    unique_excavators = {
        str(row.get("excavator") or "").strip()
        for row in detail_data
        if str(row.get("excavator") or "").strip()
    }

    materials = sorted({
        material.strip()
        for row in excavator_totals
        for material in str(
            row.get("material") or ""
        ).split(",")
        if material.strip()
    })

    grand_total = {
        "site": (
            filters.get("site")
            or "ALL SITES"
        ),

        "excavator": "GRAND TOTAL",

        "excavator_model": (
            f"{len(unique_excavators)} Unique Excavators"
        ),

        "adt": "",

        "adt_model": (
            f"{len(unique_adts)} Unique ADTs"
        ),

        "material": ", ".join(materials),

        "loads": sum(
            flt(row.get("loads"))
            for row in excavator_totals
        ),

        "bcms": sum(
            flt(row.get("bcms"))
            for row in excavator_totals
        ),

        "loading_hours": sum(
            flt(row.get("loading_hours"))
            for row in excavator_totals
        ),

        "is_excavator_total": 1,
        "is_grand_total": 1,
    }

    calculate_productivity([grand_total])

    final_data.append(grand_total)

    # Clean repeated labels
    final_data = align_machine_totals_excavator_first(
        final_data
    )

    # ========================================================
    # NATIVE MATERIAL CHILD ROWS
    #
    # Only ADTs with >1 material get expandable children.
    # Single-material ADTs remain normal rows.
    # ========================================================

    material_rows = frappe.db.sql(
        f"""
        SELECT
            hp.location AS site,

            tl.asset_name_shoval AS excavator,

            tl.asset_name_truck AS adt,

            COALESCE(
                NULLIF(tl.mat_type, ''),
                'Unknown'
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT hp.name
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        WHERE
            {conditions}

        GROUP BY
            hp.location,
            tl.asset_name_shoval,
            tl.asset_name_truck,
            tl.mat_type

        ORDER BY
            hp.location,
            tl.asset_name_shoval,
            tl.asset_name_truck,
            tl.mat_type
        """,
        values,
        as_dict=True,
    )

    calculate_productivity(
        material_rows
    )

    material_map = {}

    for material_row in material_rows:
        key = (
            str(
                material_row.get("site")
                or ""
            ),
            str(
                material_row.get("excavator")
                or ""
            ),
            str(
                material_row.get("adt")
                or ""
            ),
        )

        material_map.setdefault(
            key,
            []
        ).append(
            material_row
        )

    tree_data = []

    for row in final_data:
        new_row = dict(row)

        # ----------------------------------------------------
        # Leave subtotal / grand total rows unchanged.
        # ----------------------------------------------------

        if (
            new_row.get("is_excavator_total")
            or new_row.get("is_grand_total")
        ):
            new_row["indent"] = 0

            tree_data.append(
                new_row
            )

            continue

        real_excavator = str(
            new_row.get("source_excavator")
            or new_row.get("excavator")
            or ""
        ).strip()

        real_adt = str(
            new_row.get("adt")
            or ""
        ).strip()

        key = (
            str(
                new_row.get("site")
                or ""
            ),
            real_excavator,
            real_adt,
        )

        children = material_map.get(
            key,
            []
        )

        # ----------------------------------------------------
        # MULTI MATERIAL
        #
        # Parent gets tree arrow.
        # ----------------------------------------------------

        if len(children) > 1:
            new_row["indent"] = 0

            new_row["is_group"] = 1

            # Unique ID so Frappe can relate children.
            parent_key = (
                "MAT|"
                + str(
                    new_row.get("site")
                    or ""
                )
                + "|"
                + real_excavator
                + "|"
                + real_adt
            )

            new_row["tree_key"] = parent_key
            new_row["parent_tree_key"] = None

            tree_data.append(
                new_row
            )

            for child in children:
                child_row = {
                    "site": "",

                    "excavator": "",

                    "excavator_model": "",

                    "adt": (
                        "↳ "
                        + str(
                            child.get("material")
                            or ""
                        )
                    ),

                    "adt_model": "",

                    "material": child.get(
                        "material"
                    ),

                    "loads": child.get(
                        "loads"
                    ),

                    "bcms": child.get(
                        "bcms"
                    ),

                    "loading_hours": child.get(
                        "loading_hours"
                    ),

                    "bcm_per_hour": child.get(
                        "bcm_per_hour"
                    ),

                    "loads_per_hour": child.get(
                        "loads_per_hour"
                    ),

                    "bcm_per_load": child.get(
                        "bcm_per_load"
                    ),

                    "indent": 1,

                    "is_group": 0,

                    "tree_key": (
                        parent_key
                        + "|"
                        + str(
                            child.get("material")
                            or ""
                        )
                    ),

                    "parent_tree_key":
                        parent_key,
                }

                tree_data.append(
                    child_row
                )

        # ----------------------------------------------------
        # SINGLE MATERIAL
        #
        # No arrow.
        # ----------------------------------------------------

        else:
            new_row["indent"] = 0
            new_row["is_group"] = 0
            new_row["tree_key"] = None
            new_row["parent_tree_key"] = None

            tree_data.append(
                new_row
            )

    return columns, tree_data


def make_machine_excavator_total_row(total):
    excavator = total.get("excavator") or ""

    return {
        "site": total.get("site"),

        "excavator": (
            f"{excavator} TOTAL"
        ),

        "excavator_model": total.get(
            "excavator_model"
        ),

        "adt": "",

        "adt_model": (
            f"{int(total.get('adt_count') or 0)} ADTs"
        ),

        "material": total.get(
            "material"
        ),

        "loads": total.get(
            "loads"
        ),

        "bcms": total.get(
            "bcms"
        ),

        "loading_hours": total.get(
            "loading_hours"
        ),

        "bcm_per_hour": total.get(
            "bcm_per_hour"
        ),

        "loads_per_hour": total.get(
            "loads_per_hour"
        ),

        "bcm_per_load": total.get(
            "bcm_per_load"
        ),

        "is_excavator_total": 1,
    }


def align_machine_totals_excavator_first(rows):
    """
    Visual grouping:

    EX01 | Model | ADT01 | Model | Softs
         |       | ADT02 | Model | Softs

    If same ADT has more than one material:

    IS0331 | Model | IS0604 | Model | Coal
           |       |        |       | Hards

    Totals always display normally.
    """

    aligned = []

    previous_site = None
    previous_excavator = None
    previous_adt = None

    for row in rows:
        new_row = dict(row)

        is_total = bool(
            new_row.get("is_excavator_total")
            or new_row.get("is_grand_total")
        )

        if is_total:
            aligned.append(new_row)

            previous_site = None
            previous_excavator = None
            previous_adt = None

            continue

        site = str(
            new_row.get("site") or ""
        ).strip()

        excavator = str(
            new_row.get("excavator") or ""
        ).strip()

        adt = str(
            new_row.get("adt") or ""
        ).strip()

        # Keep the real excavator value for drill-down clicks.
        # The visible excavator field may be blanked below only
        # for cleaner report presentation.
        new_row["source_excavator"] = excavator

        same_excavator = (
            site == previous_site
            and excavator == previous_excavator
        )

        same_adt = (
            same_excavator
            and adt == previous_adt
        )

        # Show Excavator only once for its whole group.
        if same_excavator:
            new_row["excavator"] = ""
            new_row["excavator_model"] = ""

        # Show ADT only once if it has multiple material rows.
        if same_adt:
            new_row["adt"] = ""
            new_row["adt_model"] = ""

        aligned.append(new_row)

        previous_site = site
        previous_excavator = excavator
        previous_adt = adt

    return aligned


# ============================================================
# PRODUCTIVITY CALCULATIONS
# ============================================================

def calculate_productivity(data):
    for row in data:
        loads = flt(row.get("loads"))
        bcms = flt(row.get("bcms"))
        hours = flt(row.get("loading_hours"))

        if hours > 0:
            row["bcm_per_hour"] = round(
                bcms / hours,
                2,
            )

            row["loads_per_hour"] = round(
                loads / hours,
                2,
            )
        else:
            row["bcm_per_hour"] = 0
            row["loads_per_hour"] = 0

        if loads > 0:
            row["bcm_per_load"] = round(
                bcms / loads,
                2,
            )
        else:
            row["bcm_per_load"] = 0


# ============================================================
# DAILY SUMMARY - CLICK MATERIAL BREAKDOWN
# ============================================================

@frappe.whitelist()
def get_material_breakdown(
    from_date,
    to_date,
    site,
    excavator,
    adt=None,
):
    """
    Breakdown one Excavator into Material totals.

    Used by Daily Summary popup.

    Only rows where actual Loads > 0 are included.
    """

    filters = frappe._dict({
        "from_date": from_date,
        "to_date": to_date,
        "site": site,
        "excavator": excavator,
        "adt": adt,
    })

    conditions, values = get_conditions(filters)

    rows = frappe.db.sql(
        f"""
        SELECT
            COALESCE(
                NULLIF(tl.mat_type, ''),
                'Unknown'
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            /*
             * Excavator active hours for THIS material.
             * Multiple ADTs in the same hour count once.
             */
            COUNT(
                DISTINCT hp.name
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        WHERE
            {conditions}

        GROUP BY
            tl.mat_type

        ORDER BY
            FIELD(
                tl.mat_type,
                'Coal',
                'Hards',
                'Softs'
            ),
            tl.mat_type
        """,
        values,
        as_dict=True,
    )

    calculate_productivity(rows)

    # --------------------------------------------------------
    # TRUE TOTAL
    #
    # Calculate separately from raw records.
    # Do NOT add material hours together because Coal and
    # Hards can overlap within the same excavator hour.
    # --------------------------------------------------------

    total_rows = frappe.db.sql(
        f"""
        SELECT
            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT hp.name
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        WHERE
            {conditions}
        """,
        values,
        as_dict=True,
    )

    total = total_rows[0] if total_rows else frappe._dict()

    calculate_productivity([total])

    return {
        "excavator": excavator,
        "site": site,
        "rows": rows,
        "total": {
            "material": "TOTAL",
            "loads": total.get("loads") or 0,
            "bcms": total.get("bcms") or 0,
            "loading_hours": total.get("loading_hours") or 0,
            "bcm_per_hour": total.get("bcm_per_hour") or 0,
            "loads_per_hour": total.get("loads_per_hour") or 0,
            "bcm_per_load": total.get("bcm_per_load") or 0,
        },
    }



# ============================================================
# MACHINE TOTALS - ADT MATERIAL BREAKDOWN
# ============================================================

@frappe.whitelist()
def get_adt_material_breakdown(
    from_date,
    to_date,
    site,
    excavator,
    adt,
):
    """
    Show the material split for one ADT under one Excavator.

    Example collapsed row:
        IS0601 | Coal, Hards | 40 | 518 | 10 hrs

    Popup:
        Coal
        Hards
        TOTAL

    Total Loading Hrs is calculated separately using unique
    Hourly Production records so material hours cannot
    double-count overlapping hours.
    """

    filters = frappe._dict({
        "from_date": from_date,
        "to_date": to_date,
        "site": site,
        "excavator": excavator,
        "adt": adt,
    })

    conditions, values = get_conditions(filters)

    rows = frappe.db.sql(
        f"""
        SELECT
            COALESCE(
                NULLIF(tl.mat_type, ''),
                'Unknown'
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT hp.name
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        WHERE
            {conditions}

        GROUP BY
            tl.mat_type

        ORDER BY
            FIELD(
                tl.mat_type,
                'Coal',
                'Hards',
                'Softs'
            ),
            tl.mat_type
        """,
        values,
        as_dict=True,
    )

    calculate_productivity(rows)

    total_rows = frappe.db.sql(
        f"""
        SELECT
            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT hp.name
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        WHERE
            {conditions}
        """,
        values,
        as_dict=True,
    )

    total = (
        total_rows[0]
        if total_rows
        else frappe._dict()
    )

    calculate_productivity([total])

    return {
        "site": site,
        "excavator": excavator,
        "adt": adt,
        "rows": rows,
        "total": {
            "material": "TOTAL",
            "loads": total.get("loads") or 0,
            "bcms": total.get("bcms") or 0,
            "loading_hours": total.get("loading_hours") or 0,
            "bcm_per_hour": total.get("bcm_per_hour") or 0,
            "loads_per_hour": total.get("loads_per_hour") or 0,
            "bcm_per_load": total.get("bcm_per_load") or 0,
        },
    }


# ============================================================
# COMBINED ADT TOTALS
# ============================================================

def get_combined_adt_totals(filters):
    """
    Native tree:

    Level 0
        EX01
        IS EXCAVATORS

    Level 1
        Daily totals

    Level 2
        Day Shift
        Night Shift

    Only Truck Loads rows with Loads > 0 are included.
    """

    columns = [
        {
            "label": _("Excavators"),
            "fieldname": "excavators",
            "fieldtype": "Data",
            "width": 165,
        },
        {
            "label": _("Date"),
            "fieldname": "prod_date",
            "fieldtype": "Date",
            "width": 105,
        },
        {
            "label": _("Shift"),
            "fieldname": "shift",
            "fieldtype": "Data",
            "width": 90,
        },
        {
            "label": _("Excavator Model"),
            "fieldname": "excavator_model",
            "fieldtype": "Data",
            "width": 170,
        },
        {
            "label": _("ADTs"),
            "fieldname": "adts",
            "fieldtype": "Data",
            "width": 235,
        },
        {
            "label": _("Materials"),
            "fieldname": "material",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": _("ADT Count"),
            "fieldname": "adt_count",
            "fieldtype": "Int",
            "width": 85,
        },
        {
            "label": _("Loads"),
            "fieldname": "loads",
            "fieldtype": "Int",
            "width": 80,
        },
        {
            "label": _("BCM"),
            "fieldname": "bcms",
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "label": _("Loading Hrs"),
            "fieldname": "loading_hours",
            "fieldtype": "Int",
            "width": 105,
        },
        {
            "label": _("BCM/Hr"),
            "fieldname": "bcm_per_hour",
            "fieldtype": "Float",
            "precision": 2,
            "width": 95,
        },
        {
            "label": _("Loads/Hr"),
            "fieldname": "loads_per_hour",
            "fieldtype": "Float",
            "precision": 2,
            "width": 95,
        },
        {
            "label": _("Avg BCM/Load"),
            "fieldname": "bcm_per_load",
            "fieldtype": "Float",
            "precision": 2,
            "width": 110,
        },
    ]

    values = {
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date"),
        "site": filters.get("site"),
    }

    conditions = [
        "hp.prod_date BETWEEN %(from_date)s AND %(to_date)s",
        "tl.parenttype = 'Hourly Production'",
        "tl.parentfield = 'truck_loads'",
        "COALESCE(tl.loads, 0) > 0",
        "COALESCE(tl.asset_name_shoval, '') != ''",
        "COALESCE(tl.asset_name_truck, '') != ''",
    ]

    if filters.get("site"):
        conditions.append(
            "hp.location = %(site)s"
        )

    base_sql = " AND ".join(
        conditions
    )

    # ========================================================
    # HELPER
    # ========================================================

    def prep_rows(rows):
        calculate_productivity(rows)

        for row in rows:
            row["loads"] = flt(
                row.get("loads")
            )

            row["bcms"] = flt(
                row.get("bcms")
            )

            row["loading_hours"] = flt(
                row.get("loading_hours")
            )

            row["adt_count"] = int(
                row.get("adt_count") or 0
            )

        return rows

    # ========================================================
    # EX01 - PARENT TOTAL
    # ========================================================

    ex01_parent_rows = frappe.db.sql(
        f"""
        SELECT
            COUNT(
                DISTINCT tl.asset_name_truck
            ) AS adt_count,

            GROUP_CONCAT(
                DISTINCT tl.asset_name_truck
                ORDER BY tl.asset_name_truck
                SEPARATOR ', '
            ) AS adts,

            GROUP_CONCAT(
                DISTINCT NULLIF(tl.mat_type, '')
                ORDER BY tl.mat_type
                SEPARATOR ', '
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT CONCAT(
                    hp.name,
                    '|',
                    tl.asset_name_truck
                )
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        WHERE
            {base_sql}

            AND tl.asset_name_shoval = 'EX01'

            AND tl.asset_name_truck LIKE 'IS%%'
        """,
        values,
        as_dict=True,
    )

    ex01_parent = (
        ex01_parent_rows[0]
        if ex01_parent_rows
        else frappe._dict()
    )

    ex01_parent.update({
        "excavators": "EX01",
        "prod_date": None,
        "shift": "",
        "excavator_model": "",
        "indent": 0,
        "parent_excavator": None,
        "is_group": 1,
    })

    prep_rows(
        [ex01_parent]
    )

    # ========================================================
    # EX01 - DAILY TOTALS
    # ========================================================

    ex01_daily = frappe.db.sql(
        f"""
        SELECT
            hp.prod_date AS prod_date,

            tl.asset_name_shoval AS excavators,

            MAX(
                COALESCE(
                    NULLIF(asset_exc.item_name, ''),
                    NULLIF(tl.item_name_excavator, ''),
                    ''
                )
            ) AS excavator_model,

            GROUP_CONCAT(
                DISTINCT tl.asset_name_truck
                ORDER BY tl.asset_name_truck
                SEPARATOR ', '
            ) AS adts,

            COUNT(
                DISTINCT tl.asset_name_truck
            ) AS adt_count,

            GROUP_CONCAT(
                DISTINCT NULLIF(tl.mat_type, '')
                ORDER BY tl.mat_type
                SEPARATOR ', '
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT hp.name
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        LEFT JOIN `tabAsset` asset_exc
            ON asset_exc.name = tl.asset_name_shoval

        WHERE
            {base_sql}

            AND tl.asset_name_shoval = 'EX01'

            AND tl.asset_name_truck LIKE 'IS%%'

        GROUP BY
            hp.prod_date,
            tl.asset_name_shoval

        ORDER BY
            hp.prod_date,
            tl.asset_name_shoval
        """,
        values,
        as_dict=True,
    )

    prep_rows(
        ex01_daily
    )

    # ========================================================
    # EX01 - DAY / NIGHT
    # ========================================================

    ex01_shift = frappe.db.sql(
        f"""
        SELECT
            hp.prod_date AS prod_date,

            hp.shift AS shift,

            tl.asset_name_shoval AS excavators,

            MAX(
                COALESCE(
                    NULLIF(asset_exc.item_name, ''),
                    NULLIF(tl.item_name_excavator, ''),
                    ''
                )
            ) AS excavator_model,

            GROUP_CONCAT(
                DISTINCT tl.asset_name_truck
                ORDER BY tl.asset_name_truck
                SEPARATOR ', '
            ) AS adts,

            COUNT(
                DISTINCT tl.asset_name_truck
            ) AS adt_count,

            GROUP_CONCAT(
                DISTINCT NULLIF(tl.mat_type, '')
                ORDER BY tl.mat_type
                SEPARATOR ', '
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT hp.name
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        LEFT JOIN `tabAsset` asset_exc
            ON asset_exc.name = tl.asset_name_shoval

        WHERE
            {base_sql}

            AND tl.asset_name_shoval = 'EX01'

            AND tl.asset_name_truck LIKE 'IS%%'

        GROUP BY
            hp.prod_date,
            hp.shift,
            tl.asset_name_shoval

        ORDER BY
            hp.prod_date,

            CASE
                WHEN hp.shift = 'Day' THEN 1
                WHEN hp.shift = 'Night' THEN 2
                ELSE 3
            END,

            hp.shift
        """,
        values,
        as_dict=True,
    )

    prep_rows(
        ex01_shift
    )

    # ========================================================
    # IS EXCAVATORS - PARENT
    # ========================================================

    is_parent_rows = frappe.db.sql(
        f"""
        SELECT
            GROUP_CONCAT(
                DISTINCT tl.asset_name_shoval
                ORDER BY tl.asset_name_shoval
                SEPARATOR ', '
            ) AS excavator_list,

            COUNT(
                DISTINCT tl.asset_name_truck
            ) AS adt_count,

            GROUP_CONCAT(
                DISTINCT tl.asset_name_truck
                ORDER BY tl.asset_name_truck
                SEPARATOR ', '
            ) AS adts,

            GROUP_CONCAT(
                DISTINCT NULLIF(tl.mat_type, '')
                ORDER BY tl.mat_type
                SEPARATOR ', '
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT CONCAT(
                    hp.name,
                    '|',
                    tl.asset_name_truck
                )
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        WHERE
            {base_sql}

            AND tl.asset_name_shoval LIKE 'IS%%'

            AND tl.asset_name_truck IN (
                'ADT01',
                'ADT02',
                'ADT03',
                'ADT04'
            )
        """,
        values,
        as_dict=True,
    )

    is_parent = (
        is_parent_rows[0]
        if is_parent_rows
        else frappe._dict()
    )

    is_parent.update({
        "excavators": "IS EXCAVATORS",
        "prod_date": None,
        "shift": "",
        "excavator_model": (
            is_parent.get("excavator_list")
            or ""
        ),
        "indent": 0,
        "parent_excavator": None,
        "is_group": 1,
    })

    prep_rows(
        [is_parent]
    )

    # ========================================================
    # IS EXCAVATORS - DAILY TOTALS
    # ========================================================

    is_daily = frappe.db.sql(
        f"""
        SELECT
            hp.prod_date AS prod_date,

            tl.asset_name_shoval AS excavators,

            MAX(
                COALESCE(
                    NULLIF(asset_exc.item_name, ''),
                    NULLIF(tl.item_name_excavator, ''),
                    ''
                )
            ) AS excavator_model,

            GROUP_CONCAT(
                DISTINCT tl.asset_name_truck
                ORDER BY tl.asset_name_truck
                SEPARATOR ', '
            ) AS adts,

            COUNT(
                DISTINCT tl.asset_name_truck
            ) AS adt_count,

            GROUP_CONCAT(
                DISTINCT NULLIF(tl.mat_type, '')
                ORDER BY tl.mat_type
                SEPARATOR ', '
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT hp.name
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        LEFT JOIN `tabAsset` asset_exc
            ON asset_exc.name = tl.asset_name_shoval

        WHERE
            {base_sql}

            AND tl.asset_name_shoval LIKE 'IS%%'

            AND tl.asset_name_truck IN (
                'ADT01',
                'ADT02',
                'ADT03',
                'ADT04'
            )

        GROUP BY
            hp.prod_date,
            tl.asset_name_shoval

        ORDER BY
            hp.prod_date,
            tl.asset_name_shoval
        """,
        values,
        as_dict=True,
    )

    prep_rows(
        is_daily
    )

    # ========================================================
    # IS EXCAVATORS - DAY / NIGHT
    # ========================================================

    is_shift = frappe.db.sql(
        f"""
        SELECT
            hp.prod_date AS prod_date,

            hp.shift AS shift,

            tl.asset_name_shoval AS excavators,

            MAX(
                COALESCE(
                    NULLIF(asset_exc.item_name, ''),
                    NULLIF(tl.item_name_excavator, ''),
                    ''
                )
            ) AS excavator_model,

            GROUP_CONCAT(
                DISTINCT tl.asset_name_truck
                ORDER BY tl.asset_name_truck
                SEPARATOR ', '
            ) AS adts,

            COUNT(
                DISTINCT tl.asset_name_truck
            ) AS adt_count,

            GROUP_CONCAT(
                DISTINCT NULLIF(tl.mat_type, '')
                ORDER BY tl.mat_type
                SEPARATOR ', '
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT hp.name
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        LEFT JOIN `tabAsset` asset_exc
            ON asset_exc.name = tl.asset_name_shoval

        WHERE
            {base_sql}

            AND tl.asset_name_shoval LIKE 'IS%%'

            AND tl.asset_name_truck IN (
                'ADT01',
                'ADT02',
                'ADT03',
                'ADT04'
            )

        GROUP BY
            hp.prod_date,
            hp.shift,
            tl.asset_name_shoval

        ORDER BY
            hp.prod_date,
            tl.asset_name_shoval,

            CASE
                WHEN hp.shift = 'Day' THEN 1
                WHEN hp.shift = 'Night' THEN 2
                ELSE 3
            END,

            hp.shift
        """,
        values,
        as_dict=True,
    )

    prep_rows(
        is_shift
    )

    # ========================================================
    # INDEX SHIFT ROWS
    # ========================================================

    ex01_shift_map = {}

    for row in ex01_shift:
        key = (
            str(row.get("prod_date") or ""),
            str(row.get("excavators") or ""),
        )

        ex01_shift_map.setdefault(
            key,
            []
        ).append(row)

    is_shift_map = {}

    for row in is_shift:
        key = (
            str(row.get("prod_date") or ""),
            str(row.get("excavators") or ""),
        )

        is_shift_map.setdefault(
            key,
            []
        ).append(row)

    # ========================================================
    # BUILD TREE
    # ========================================================

    data = []

    # --------------------------------------------------------
    # EX01
    # --------------------------------------------------------

    if flt(
        ex01_parent.get("loads")
    ) > 0:

        data.append(
            ex01_parent
        )

        for daily in ex01_daily:
            daily["indent"] = 1
            daily["shift"] = "Full Day"
            daily["parent_excavator"] = "EX01"
            daily["is_group"] = 1

            data.append(
                daily
            )

            key = (
                str(
                    daily.get("prod_date")
                    or ""
                ),
                str(
                    daily.get("excavators")
                    or ""
                ),
            )

            for shift_row in ex01_shift_map.get(
                key,
                []
            ):
                shift_row["indent"] = 2
                shift_row["parent_excavator"] = (
                    str(
                        daily.get("prod_date")
                        or ""
                    )
                    + "|EX01"
                )
                shift_row["is_group"] = 0

                data.append(
                    shift_row
                )

    # --------------------------------------------------------
    # IS EXCAVATORS
    # --------------------------------------------------------

    if flt(
        is_parent.get("loads")
    ) > 0:

        data.append(
            is_parent
        )

        for daily in is_daily:
            daily["indent"] = 1
            daily["shift"] = "Full Day"
            daily["parent_excavator"] = (
                "IS EXCAVATORS"
            )
            daily["is_group"] = 1

            data.append(
                daily
            )

            key = (
                str(
                    daily.get("prod_date")
                    or ""
                ),
                str(
                    daily.get("excavators")
                    or ""
                ),
            )

            for shift_row in is_shift_map.get(
                key,
                []
            ):
                shift_row["indent"] = 2
                shift_row["parent_excavator"] = (
                    str(
                        daily.get("prod_date")
                        or ""
                    )
                    + "|"
                    + str(
                        daily.get("excavators")
                        or ""
                    )
                )
                shift_row["is_group"] = 0

                data.append(
                    shift_row
                )

    return columns, data


@frappe.whitelist()
def get_combined_adt_detail(
    from_date,
    to_date,
    site=None,
    group_key=None,
):
    """
    Drill-down for Combined ADT Totals.

    Group 1:
        EX01 + all IS-numbered ADTs

    Group 2:
        all IS-numbered Excavators +
        ADT01, ADT02, ADT03, ADT04
    """

    values = {
        "from_date": from_date,
        "to_date": to_date,
        "site": site,
    }

    base_conditions = [
        "hp.prod_date BETWEEN %(from_date)s AND %(to_date)s",
        "tl.parenttype = 'Hourly Production'",
        "tl.parentfield = 'truck_loads'",
        "COALESCE(tl.loads, 0) > 0",
        "COALESCE(tl.asset_name_shoval, '') != ''",
        "COALESCE(tl.asset_name_truck, '') != ''",
    ]

    if site:
        base_conditions.append(
            "hp.location = %(site)s"
        )

    if group_key == "ex01_is_adts":
        base_conditions.extend([
            "tl.asset_name_shoval = 'EX01'",
            "tl.asset_name_truck LIKE 'IS%%'",
        ])

        title = "EX01 - IS ADTs"

    elif group_key == "is_excavators_adt01_04":
        base_conditions.extend([
            "tl.asset_name_shoval LIKE 'IS%%'",
            """
            tl.asset_name_truck IN (
                'ADT01',
                'ADT02',
                'ADT03',
                'ADT04'
            )
            """,
        ])

        title = "IS Excavators - ADT01 to ADT04"

    else:
        frappe.throw(
            _("Invalid Combined ADT group.")
        )

    conditions = " AND ".join(
        base_conditions
    )

    rows = frappe.db.sql(
        f"""
        SELECT
            tl.asset_name_truck AS adt,

            MAX(
                COALESCE(
                    NULLIF(asset_adt.item_name, ''),
                    NULLIF(tl.item_name, ''),
                    ''
                )
            ) AS adt_model,

            GROUP_CONCAT(
                DISTINCT tl.asset_name_shoval
                ORDER BY tl.asset_name_shoval
                SEPARATOR ', '
            ) AS excavators,

            GROUP_CONCAT(
                DISTINCT NULLIF(tl.mat_type, '')
                ORDER BY tl.mat_type
                SEPARATOR ', '
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT CONCAT(
                    hp.name,
                    '|',
                    tl.asset_name_truck
                )
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        LEFT JOIN `tabAsset` asset_adt
            ON asset_adt.name = tl.asset_name_truck

        WHERE
            {conditions}

        GROUP BY
            tl.asset_name_truck

        ORDER BY
            tl.asset_name_truck
        """,
        values,
        as_dict=True,
    )

    calculate_productivity(rows)

    return {
        "title": title,
        "rows": rows,
    }


# ============================================================
# COMBINED ADT TOTALS - EXCAVATOR DETAIL
# ============================================================

@frappe.whitelist()
def get_combined_excavator_detail(
    from_date,
    to_date,
    site=None,
    group_key=None,
):
    """
    Drill-down used by Combined ADT Totals.

    Group 1:
        EX01 + IS-numbered ADTs

    Group 2:
        IS-numbered Excavators +
        ADT01, ADT02, ADT03, ADT04
    """

    values = {
        "from_date": from_date,
        "to_date": to_date,
        "site": site,
    }

    conditions = [
        "hp.prod_date BETWEEN %(from_date)s AND %(to_date)s",
        "tl.parenttype = 'Hourly Production'",
        "tl.parentfield = 'truck_loads'",
        "COALESCE(tl.loads, 0) > 0",
        "COALESCE(tl.asset_name_shoval, '') != ''",
        "COALESCE(tl.asset_name_truck, '') != ''",
    ]

    if site:
        conditions.append(
            "hp.location = %(site)s"
        )

    if group_key == "ex01_is_adts":

        conditions.extend([
            "tl.asset_name_shoval = 'EX01'",
            "tl.asset_name_truck LIKE 'IS%%'",
        ])

        title = "EX01 - IS ADTs Loaded"

    elif group_key == "is_excavators_adt01_04":

        conditions.extend([
            "tl.asset_name_shoval LIKE 'IS%%'",
            """
            tl.asset_name_truck IN (
                'ADT01',
                'ADT02',
                'ADT03',
                'ADT04'
            )
            """,
        ])

        title = (
            "IS Excavators - "
            "ADT01 to ADT04 Loaded"
        )

    else:
        frappe.throw(
            _("Invalid Combined ADT group.")
        )

    where_sql = " AND ".join(
        conditions
    )

    rows = frappe.db.sql(
        f"""
        SELECT
            hp.prod_date AS prod_date,

            tl.asset_name_shoval AS excavator,

            MAX(
                COALESCE(
                    NULLIF(asset_exc.item_name, ''),
                    NULLIF(tl.item_name_excavator, ''),
                    ''
                )
            ) AS excavator_model,

            GROUP_CONCAT(
                DISTINCT tl.asset_name_truck
                ORDER BY tl.asset_name_truck
                SEPARATOR ', '
            ) AS adts,

            COUNT(
                DISTINCT tl.asset_name_truck
            ) AS adt_count,

            GROUP_CONCAT(
                DISTINCT NULLIF(tl.mat_type, '')
                ORDER BY tl.mat_type
                SEPARATOR ', '
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT hp.name
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        LEFT JOIN `tabAsset` asset_exc
            ON asset_exc.name = tl.asset_name_shoval

        WHERE
            {where_sql}

        GROUP BY
            hp.prod_date,
            tl.asset_name_shoval

        ORDER BY
            hp.prod_date,
            tl.asset_name_shoval
        """,
        values,
        as_dict=True,
    )

    calculate_productivity(rows)

    return {
        "title": title,
        "rows": rows,
    }


# ============================================================
# HOURLY SUMMARY
#
# TREE:
#
# DATE
#   EXCAVATOR TOTAL
#       ADT TOTAL
#           HOUR
# ============================================================

def get_hourly_summary(filters):

    columns = [
        {
            "label": _("Date"),
            "fieldname": "prod_date",
            "fieldtype": "Date",
            "width": 105,
        },
        {
            "label": _("Hour"),
            "fieldname": "hour_slot",
            "fieldtype": "Data",
            "width": 115,
        },
        {
            "label": _("Site"),
            "fieldname": "site",
            "fieldtype": "Link",
            "options": "Location",
            "width": 125,
        },
        {
            "label": _("Excavator"),
            "fieldname": "excavator",
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "label": _("Excavator Model"),
            "fieldname": "excavator_model",
            "fieldtype": "Data",
            "width": 165,
        },
        {
            "label": _("ADT"),
            "fieldname": "adt",
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "label": _("ADT Model"),
            "fieldname": "adt_model",
            "fieldtype": "Data",
            "width": 155,
        },
        {
            "label": _("Material"),
            "fieldname": "material",
            "fieldtype": "Data",
            "width": 115,
        },
        {
            "label": _("Loads"),
            "fieldname": "loads",
            "fieldtype": "Int",
            "width": 75,
        },
        {
            "label": _("BCM"),
            "fieldname": "bcms",
            "fieldtype": "Int",
            "width": 85,
        },
        {
            "label": _("Loading Hrs"),
            "fieldname": "loading_hours",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": _("BCM/Hr"),
            "fieldname": "bcm_per_hour",
            "fieldtype": "Float",
            "precision": 2,
            "width": 90,
        },
        {
            "label": _("Loads/Hr"),
            "fieldname": "loads_per_hour",
            "fieldtype": "Float",
            "precision": 2,
            "width": 90,
        },
        {
            "label": _("Avg BCM/Load"),
            "fieldname": "bcm_per_load",
            "fieldtype": "Float",
            "precision": 2,
            "width": 105,
        },
    ]

    conditions, values = get_conditions(filters)

    # ========================================================
    # DATE TOTALS
    # ========================================================

    date_rows = frappe.db.sql(
        f"""
        SELECT
            hp.prod_date AS prod_date,
            hp.location AS site,

            COUNT(
                DISTINCT tl.asset_name_shoval
            ) AS excavator_count,

            COUNT(
                DISTINCT tl.asset_name_truck
            ) AS adt_count,

            GROUP_CONCAT(
                DISTINCT NULLIF(tl.mat_type, '')
                ORDER BY tl.mat_type
                SEPARATOR ', '
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT CONCAT(
                    hp.name,
                    '|',
                    tl.asset_name_shoval
                )
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        WHERE
            {conditions}

        GROUP BY
            hp.prod_date,
            hp.location

        ORDER BY
            hp.prod_date,
            hp.location
        """,
        values,
        as_dict=True,
    )

    calculate_productivity(date_rows)

    # ========================================================
    # EXCAVATOR TOTALS PER DATE
    # ========================================================

    excavator_rows = frappe.db.sql(
        f"""
        SELECT
            hp.prod_date AS prod_date,
            hp.location AS site,

            tl.asset_name_shoval AS excavator,

            MAX(
                COALESCE(
                    NULLIF(asset_exc.item_name, ''),
                    NULLIF(tl.item_name_excavator, ''),
                    ''
                )
            ) AS excavator_model,

            COUNT(
                DISTINCT tl.asset_name_truck
            ) AS adt_count,

            GROUP_CONCAT(
                DISTINCT NULLIF(tl.mat_type, '')
                ORDER BY tl.mat_type
                SEPARATOR ', '
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT hp.name
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        LEFT JOIN `tabAsset` asset_exc
            ON asset_exc.name = tl.asset_name_shoval

        WHERE
            {conditions}

        GROUP BY
            hp.prod_date,
            hp.location,
            tl.asset_name_shoval

        ORDER BY
            hp.prod_date,
            hp.location,
            tl.asset_name_shoval
        """,
        values,
        as_dict=True,
    )

    calculate_productivity(excavator_rows)

    # ========================================================
    # ADT TOTAL PER DATE + EXCAVATOR
    # ========================================================

    adt_rows = frappe.db.sql(
        f"""
        SELECT
            hp.prod_date AS prod_date,
            hp.location AS site,

            tl.asset_name_shoval AS excavator,

            MAX(
                COALESCE(
                    NULLIF(asset_exc.item_name, ''),
                    NULLIF(tl.item_name_excavator, ''),
                    ''
                )
            ) AS excavator_model,

            tl.asset_name_truck AS adt,

            MAX(
                COALESCE(
                    NULLIF(asset_adt.item_name, ''),
                    NULLIF(tl.item_name, ''),
                    ''
                )
            ) AS adt_model,

            GROUP_CONCAT(
                DISTINCT NULLIF(tl.mat_type, '')
                ORDER BY tl.mat_type
                SEPARATOR ', '
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            COUNT(
                DISTINCT hp.name
            ) AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        LEFT JOIN `tabAsset` asset_exc
            ON asset_exc.name = tl.asset_name_shoval

        LEFT JOIN `tabAsset` asset_adt
            ON asset_adt.name = tl.asset_name_truck

        WHERE
            {conditions}

        GROUP BY
            hp.prod_date,
            hp.location,
            tl.asset_name_shoval,
            tl.asset_name_truck

        ORDER BY
            hp.prod_date,
            hp.location,
            tl.asset_name_shoval,
            tl.asset_name_truck
        """,
        values,
        as_dict=True,
    )

    calculate_productivity(adt_rows)

    # ========================================================
    # BUILD LOOKUPS
    # ========================================================

    excavator_map = {}

    for row in excavator_rows:
        key = (
            str(row.get("prod_date") or ""),
            str(row.get("site") or ""),
        )

        excavator_map.setdefault(
            key,
            []
        ).append(row)

    adt_map = {}

    for row in adt_rows:
        key = (
            str(row.get("prod_date") or ""),
            str(row.get("site") or ""),
            str(row.get("excavator") or ""),
        )

        adt_map.setdefault(
            key,
            []
        ).append(row)

    # ========================================================
    # BUILD TREE
    # ========================================================

    data = []

    for date_row in date_rows:

        prod_date = str(
            date_row.get("prod_date")
            or ""
        )

        site = str(
            date_row.get("site")
            or ""
        )

        date_key = (
            "HDATE|"
            + prod_date
            + "|"
            + site
        )

        # ----------------------------------------------------
        # LEVEL 0 - DATE
        # ----------------------------------------------------

        data.append({
            "prod_date":
                date_row.get("prod_date"),

            "hour_slot": "",

            "site":
                site,

            "excavator": (
                f"{int(date_row.get('excavator_count') or 0)} Excavators"
            ),

            "excavator_model": "",

            "adt": (
                f"{int(date_row.get('adt_count') or 0)} Unique ADTs"
            ),

            "adt_model": "",

            "material":
                date_row.get("material") or "",

            "loads":
                date_row.get("loads") or 0,

            "bcms":
                date_row.get("bcms") or 0,

            "loading_hours":
                date_row.get("loading_hours") or 0,

            "bcm_per_hour":
                date_row.get("bcm_per_hour") or 0,

            "loads_per_hour":
                date_row.get("loads_per_hour") or 0,

            "bcm_per_load":
                date_row.get("bcm_per_load") or 0,

            "indent": 0,
            "is_group": 1,

            "tree_key":
                date_key,

            "parent_tree_key":
                None,

            "is_date_total": 1,
        })

        # ----------------------------------------------------
        # LEVEL 1 - EXCAVATOR TOTAL
        # ----------------------------------------------------

        excavators = excavator_map.get(
            (
                prod_date,
                site,
            ),
            []
        )

        for exc in excavators:

            excavator = str(
                exc.get("excavator")
                or ""
            )

            exc_key = (
                date_key
                + "|EXC|"
                + excavator
            )

            adts = adt_map.get(
                (
                    prod_date,
                    site,
                    excavator,
                ),
                []
            )

            data.append({
                "prod_date": None,
                "hour_slot": "",
                "site": site,

                "excavator":
                    excavator + " TOTAL",

                "excavator_model":
                    exc.get("excavator_model")
                    or "",

                "adt": (
                    f"{int(exc.get('adt_count') or 0)} ADTs"
                ),

                "adt_model": "",

                "material":
                    exc.get("material")
                    or "",

                "loads":
                    exc.get("loads")
                    or 0,

                "bcms":
                    exc.get("bcms")
                    or 0,

                "loading_hours":
                    exc.get("loading_hours")
                    or 0,

                "bcm_per_hour":
                    exc.get("bcm_per_hour")
                    or 0,

                "loads_per_hour":
                    exc.get("loads_per_hour")
                    or 0,

                "bcm_per_load":
                    exc.get("bcm_per_load")
                    or 0,

                "indent": 1,

                "is_group":
                    1 if adts else 0,

                "tree_key":
                    exc_key,

                "parent_tree_key":
                    date_key,

                "is_excavator_total": 1,
            })

            # ------------------------------------------------
            # LEVEL 2 - ADT TOTAL
            # ------------------------------------------------

            for adt_row in adts:

                adt = str(
                    adt_row.get("adt")
                    or ""
                )

                adt_key = (
                    exc_key
                    + "|ADT|"
                    + adt
                )

                data.append({
                    "prod_date": None,
                    "hour_slot": "",
                    "site": "",

                    "excavator": "",

                    "excavator_model": "",

                    "adt":
                        adt + " TOTAL",

                    "adt_model":
                        adt_row.get(
                            "adt_model"
                        ) or "",

                    "material":
                        adt_row.get(
                            "material"
                        ) or "",

                    "loads":
                        adt_row.get(
                            "loads"
                        ) or 0,

                    "bcms":
                        adt_row.get(
                            "bcms"
                        ) or 0,

                    "loading_hours":
                        adt_row.get(
                            "loading_hours"
                        ) or 0,

                    "bcm_per_hour":
                        adt_row.get(
                            "bcm_per_hour"
                        ) or 0,

                    "loads_per_hour":
                        adt_row.get(
                            "loads_per_hour"
                        ) or 0,

                    "bcm_per_load":
                        adt_row.get(
                            "bcm_per_load"
                        ) or 0,

                    "indent": 2,

                    "is_group": 0,

                    "tree_key":
                        adt_key,

                    "parent_tree_key":
                        exc_key,

                    "is_adt_total": 1,

                    # Used by JS for lazy hourly fetch.
                    "hourly_date":
                        prod_date,

                    "hourly_site":
                        site,

                    "hourly_excavator":
                        excavator,

                    "hourly_adt":
                        adt,
                })

    return columns, data


# ============================================================
# HOURLY SUMMARY - LAZY ADT DETAIL
# ============================================================

@frappe.whitelist()
def get_hourly_adt_detail(
    prod_date,
    site,
    excavator,
    adt,
):
    """
    Fetch hourly rows only for one selected:
        Date + Site + Excavator + ADT

    Loads must be > 0.
    """

    values = {
        "prod_date": prod_date,
        "site": site,
        "excavator": excavator,
        "adt": adt,
    }

    rows = frappe.db.sql(
        """
        SELECT
            hp.hour_slot AS hour_slot,

            GROUP_CONCAT(
                DISTINCT NULLIF(tl.mat_type, '')
                ORDER BY tl.mat_type
                SEPARATOR ', '
            ) AS material,

            SUM(
                COALESCE(tl.loads, 0)
            ) AS loads,

            SUM(
                COALESCE(tl.bcms, 0)
            ) AS bcms,

            1 AS loading_hours

        FROM `tabTruck Loads` tl

        INNER JOIN `tabHourly Production` hp
            ON hp.name = tl.parent

        WHERE
            hp.prod_date = %(prod_date)s

            AND hp.location = %(site)s

            AND tl.parenttype = 'Hourly Production'

            AND tl.parentfield = 'truck_loads'

            AND COALESCE(tl.loads, 0) > 0

            AND tl.asset_name_shoval = %(excavator)s

            AND tl.asset_name_truck = %(adt)s

        GROUP BY
            hp.name,
            hp.hour_slot

        ORDER BY
            CASE
                WHEN hp.hour_slot LIKE '6:00%%' THEN 1
                WHEN hp.hour_slot LIKE '7:00%%' THEN 2
                WHEN hp.hour_slot LIKE '8:00%%' THEN 3
                WHEN hp.hour_slot LIKE '9:00%%' THEN 4
                WHEN hp.hour_slot LIKE '10:00%%' THEN 5
                WHEN hp.hour_slot LIKE '11:00%%' THEN 6
                WHEN hp.hour_slot LIKE '12:00%%' THEN 7
                WHEN hp.hour_slot LIKE '13:00%%' THEN 8
                WHEN hp.hour_slot LIKE '14:00%%' THEN 9
                WHEN hp.hour_slot LIKE '15:00%%' THEN 10
                WHEN hp.hour_slot LIKE '16:00%%' THEN 11
                WHEN hp.hour_slot LIKE '17:00%%' THEN 12
                WHEN hp.hour_slot LIKE '18:00%%' THEN 13
                WHEN hp.hour_slot LIKE '19:00%%' THEN 14
                WHEN hp.hour_slot LIKE '20:00%%' THEN 15
                WHEN hp.hour_slot LIKE '21:00%%' THEN 16
                WHEN hp.hour_slot LIKE '22:00%%' THEN 17
                WHEN hp.hour_slot LIKE '23:00%%' THEN 18
                WHEN hp.hour_slot LIKE '0:00%%' THEN 19
                WHEN hp.hour_slot LIKE '1:00%%' THEN 20
                WHEN hp.hour_slot LIKE '2:00%%' THEN 21
                WHEN hp.hour_slot LIKE '3:00%%' THEN 22
                WHEN hp.hour_slot LIKE '4:00%%' THEN 23
                WHEN hp.hour_slot LIKE '5:00%%' THEN 24
                ELSE 99
            END
        """,
        values,
        as_dict=True,
    )

    calculate_productivity(rows)

    totals = {
        "loads": sum(
            flt(row.get("loads"))
            for row in rows
        ),

        "bcms": sum(
            flt(row.get("bcms"))
            for row in rows
        ),

        "loading_hours": len(rows),
    }

    calculate_productivity(
        [totals]
    )

    return {
        "date": prod_date,
        "site": site,
        "excavator": excavator,
        "adt": adt,
        "rows": rows,
        "totals": totals,
    }

