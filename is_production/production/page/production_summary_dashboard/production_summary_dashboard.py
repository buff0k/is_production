import frappe
from frappe import _


REPORT_DOCTYPE = "Monthly Production Planning"

PLANNING_GROUPS = [
    {
        "key": "group_1",
        "label": "Koppie / Uitgevallen / Bankfontein",
        "sites": ["Koppie", "Uitgevallen", "Bankfontein"],
    },
    {
        "key": "group_2",
        "label": "Klipfontein / Gwab",
        "sites": ["Klipfontein", "Gwab"],
    },
    {
        "key": "group_3",
        "label": "Kriel Rehabilitation",
        "sites": ["Kriel Rehabilitation"],
    },
]


@frappe.whitelist()
def get_dashboard_data(
    group_1_start_date=None,
    group_1_end_date=None,
    group_2_start_date=None,
    group_2_end_date=None,
    group_3_start_date=None,
    group_3_end_date=None,
):
    if not frappe.db.exists("DocType", REPORT_DOCTYPE):
        frappe.throw(_("DocType {0} does not exist").format(REPORT_DOCTYPE))

    validate_date_range(group_1_start_date, group_1_end_date, "Koppie / Uitgevallen / Bankfontein")
    validate_date_range(group_2_start_date, group_2_end_date, "Klipfontein / Gwab")
    validate_date_range(group_3_start_date, group_3_end_date, "Kriel Rehabilitation")

    group_date_map = {
        "group_1": {
            "start_date": group_1_start_date,
            "end_date": group_1_end_date,
        },
        "group_2": {
            "start_date": group_2_start_date,
            "end_date": group_2_end_date,
        },
        "group_3": {
            "start_date": group_3_start_date,
            "end_date": group_3_end_date,
        },
    }

    all_rows = []
    groups_meta = []

    for group in PLANNING_GROUPS:
        dates = group_date_map.get(group["key"], {})
        start_date = dates.get("start_date")
        end_date = dates.get("end_date")

        # Only load a group when BOTH dates are selected
        if not (start_date and end_date):
            groups_meta.append(
                {
                    "key": group["key"],
                    "label": group["label"],
                    "sites": group["sites"],
                    "start_date": start_date,
                    "end_date": end_date,
                    "row_count": 0,
                    "is_active": False,
                }
            )
            continue

        rows = get_group_rows(
            sites=group["sites"],
            start_date=start_date,
            end_date=end_date,
            planning_group=group["label"],
        )

        all_rows.extend(rows)
        groups_meta.append(
            {
                "key": group["key"],
                "label": group["label"],
                "sites": group["sites"],
                "start_date": start_date,
                "end_date": end_date,
                "row_count": len(rows),
                "is_active": True,
            }
        )

    summary = {
        "total_monthly_target_bcm": sum((row.get("monthly_target_bcm") or 0) for row in all_rows),
        "total_forecast_bcm": sum((row.get("forecast_bcm") or 0) for row in all_rows),
        "total_forecast_variance_bcm": sum((row.get("forecast_variance_bcm") or 0) for row in all_rows),
        "total_waste_variance_bcm": sum((row.get("waste_variance_bcm") or 0) for row in all_rows),
        "total_coal_variance_tons": sum((row.get("coal_variance_tons") or 0) for row in all_rows),
        "site_count": len(all_rows),
    }

    return {
        "rows": all_rows,
        "summary": summary,
        "groups": groups_meta,
    }


def validate_date_range(start_date, end_date, group_label):
    if start_date and end_date and start_date > end_date:
        frappe.throw(
            _("Start Date cannot be after End Date for {0}.").format(group_label)
        )


def get_group_rows(sites, start_date=None, end_date=None, planning_group=None):
    if not sites or not start_date or not end_date:
        return []

    site_sql = ", ".join(frappe.db.escape(site) for site in sites)

    values = {
        "start_date": start_date,
        "end_date": end_date,
    }

    rows = frappe.db.sql(
        f"""
        SELECT
            t1.name,
            t1.location AS site,
            t1.prod_month_start_date,
            t1.prod_month_end_date,
            IFNULL(t1.monthly_target_bcm, 0) AS monthly_target_bcm,
            IFNULL(t1.month_forecated_bcm, 0) AS forecast_bcm,
            (IFNULL(t1.month_forecated_bcm, 0) - IFNULL(t1.monthly_target_bcm, 0)) AS forecast_variance_bcm,

            (
                (
                    IFNULL(t1.month_actual_bcm, 0)
                    - (IFNULL(t1.month_actual_coal, 0) / 1.5)
                )
                - IFNULL(t1.waste_bcms_planned, 0)
            ) AS waste_variance_bcm,

            (
                IFNULL(t1.month_actual_coal, 0)
                - IFNULL(t1.coal_tons_planned, 0)
            ) AS coal_variance_tons,

            IFNULL(t1.target_bcm_day, 0) AS daily_required_bcm,
            IFNULL(t1.mtd_bcm_day, 0) AS daily_achieved_bcm,
            IFNULL(t1.prod_days_completed, 0) AS days_worked,
            IFNULL(t1.month_remaining_production_days, 0) AS days_left,
            IFNULL(t1.month_actual_bcm, 0) AS actual_bcm,
            IFNULL(t1.month_actual_coal, 0) AS actual_coal_tons,
            IFNULL(t1.split_ratio, IFNULL(t1.planned_strip_ratio, 0)) AS strip_ratio,

            CASE
                WHEN IFNULL(t1.monthly_target_bcm, 0) = 0 THEN 0
                ELSE ROUND((IFNULL(t1.month_forecated_bcm, 0) / t1.monthly_target_bcm) * 100, 1)
            END AS forecast_delivery_percent
        FROM `tab{REPORT_DOCTYPE}` t1
        INNER JOIN (
            SELECT
                location,
                MAX(prod_month_end_date) AS latest_month_end
            FROM `tab{REPORT_DOCTYPE}`
            WHERE location IN ({site_sql})
              AND prod_month_end_date >= %(start_date)s
              AND prod_month_start_date <= %(end_date)s
            GROUP BY location
        ) picked
            ON picked.location = t1.location
            AND picked.latest_month_end = t1.prod_month_end_date
        WHERE t1.location IN ({site_sql})
        ORDER BY t1.location ASC
        """,
        values,
        as_dict=True,
    )

    for row in rows:
        row["planning_group"] = planning_group

    return rows