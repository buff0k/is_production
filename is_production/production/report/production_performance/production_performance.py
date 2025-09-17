import frappe

def execute(filters=None):
    filters = filters or {}
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    site = filters.get("site")   # ✅ changed from location → site

    # ✅ enforce filters
    if not start_date or not end_date or not site:
        frappe.throw("Start Date, End Date and Site are required filters.")

    columns, data = get_columns(), []

    # Fetch docs that overlap with the selected range
    docs = frappe.get_all(
        "Monthly Production Planning",
        filters={
            "location": site,  # ✅ map site filter to location field in DocType
            "prod_month_start_date": ["<=", end_date],
            "prod_month_end_date": [">=", start_date]
        },
        fields=[
            "name", "location",
            "monthly_target_bcm", "coal_tons_planned", "coal_planned_bcm", "waste_bcms_planned",
            "month_act_ts_bcm_tallies", "month_act_dozing_bcm_tallies",
            "month_actual_bcm", "monthly_act_tally_survey_variance",
            "month_forecated_bcm",
            "num_prod_days", "prod_days_completed", "month_remaining_production_days",
            "total_month_prod_hours", "month_prod_hours_completed", "month_remaining_prod_hours"
        ],
        order_by="creation desc"
    )

    for d in docs:
        # Derived values
        mtd_tallies_total = (d.month_act_ts_bcm_tallies or 0) + (d.month_act_dozing_bcm_tallies or 0)
        mtd_target = ((d.monthly_target_bcm or 0) / (d.num_prod_days or 1)) * (d.prod_days_completed or 0)
        remaining_bcm = (d.monthly_target_bcm or 0) - (d.month_actual_bcm or 0)

        row = {
            "name": d.name,
            "location": d.location,
            "monthly_target_bcm": d.monthly_target_bcm or 0,
            "coal_tons_planned": d.coal_tons_planned or 0,
            "coal_planned_bcm": d.coal_planned_bcm or 0,
            "waste_bcms_planned": d.waste_bcms_planned or 0,
            "mtd_tallies_total": mtd_tallies_total,
            "mtd_tallies_ts": d.month_act_ts_bcm_tallies or 0,
            "mtd_tallies_dozing": d.month_act_dozing_bcm_tallies or 0,
            "mtd_actual_bcm": d.month_actual_bcm or 0,
            "mtd_target_bcm": mtd_target,
            "remaining_bcm": remaining_bcm,
            "mtd_variance": d.monthly_act_tally_survey_variance or 0,
            "forecast_bcm": d.month_forecated_bcm or 0,
            "available_days": d.num_prod_days or 0,
            "worked_days": d.prod_days_completed or 0,
            "remaining_days": d.month_remaining_production_days or 0,
            "available_hours": d.total_month_prod_hours or 0,
            "worked_hours": d.month_prod_hours_completed or 0,
            "remaining_hours": d.month_remaining_prod_hours or 0,
        }

        data.append(row)

    return columns, data


def get_columns():
    return [
        {"label": "Planning Ref", "fieldname": "name", "fieldtype": "Link", "options": "Monthly Production Planning", "width": 160},
        {"label": "Location", "fieldname": "location", "fieldtype": "Link", "options": "Location", "width": 120},
        {"label": "Target BCM", "fieldname": "monthly_target_bcm", "fieldtype": "Float", "width": 120},
        {"label": "Coal Tons Planned", "fieldname": "coal_tons_planned", "fieldtype": "Float", "width": 140},
        {"label": "Coal Planned BCM", "fieldname": "coal_planned_bcm", "fieldtype": "Float", "width": 140},
        {"label": "Waste Planned BCM", "fieldname": "waste_bcms_planned", "fieldtype": "Float", "width": 140},
        {"label": "MTD Tallies Total BCM", "fieldname": "mtd_tallies_total", "fieldtype": "Float", "width": 160},
        {"label": "MTD Tallies TS BCM", "fieldname": "mtd_tallies_ts", "fieldtype": "Float", "width": 160},
        {"label": "MTD Tallies Dozing BCM", "fieldname": "mtd_tallies_dozing", "fieldtype": "Float", "width": 160},
        {"label": "MTD Actual BCM (Survey)", "fieldname": "mtd_actual_bcm", "fieldtype": "Float", "width": 180},
        {"label": "MTD Target BCM", "fieldname": "mtd_target_bcm", "fieldtype": "Float", "width": 150},
        {"label": "Remaining BCM", "fieldname": "remaining_bcm", "fieldtype": "Float", "width": 150},
        {"label": "MTD Variance (Tallies vs Survey)", "fieldname": "mtd_variance", "fieldtype": "Float", "width": 200},
        {"label": "Forecast BCM", "fieldname": "forecast_bcm", "fieldtype": "Float", "width": 160},
        {"label": "Available Days", "fieldname": "available_days", "fieldtype": "Int", "width": 120},
        {"label": "Worked Days", "fieldname": "worked_days", "fieldtype": "Int", "width": 120},
        {"label": "Remaining Days", "fieldname": "remaining_days", "fieldtype": "Int", "width": 140},
        {"label": "Available Hours", "fieldname": "available_hours", "fieldtype": "Float", "width": 140},
        {"label": "Worked Hours", "fieldname": "worked_hours", "fieldtype": "Float", "width": 140},
        {"label": "Remaining Hours", "fieldname": "remaining_hours", "fieldtype": "Float", "width": 150},
    ]



