import frappe


# =========================================================
# REPORT EXECUTION
# =========================================================

def execute(filters=None):
    """
    HO-DB-0001
    Prepared Script Report – Monthly Production Planning KPI view
    Always resolves the latest Define Monthly Production if no filter is provided.
    """
    filters = filters or {}

    define_name = filters.get("define_monthly_production")

    # Auto-pick latest Define Monthly Production if not provided
    if not define_name:
        define_name = get_latest_define_monthly_production()

    columns = get_columns()

    if not define_name:
        # No Define Monthly Production exists yet
        return columns, []

    data = get_data(define_name)
    return columns, data


# =========================================================
# HELPERS
# =========================================================

def get_latest_define_monthly_production():
    """
    Returns the name of the most recently created
    Define Monthly Production document.
    """
    return frappe.db.get_value(
        "Define Monthly Production",
        filters={},
        fieldname="name",
        order_by="creation desc"
    )


# =========================================================
# COLUMNS
# =========================================================

def get_columns():
    columns = []

    meta = frappe.get_meta("Monthly Production Planning")

    # Base Monthly Production Planning fields
    for df in meta.fields:
        if df.fieldtype in (
            "Section Break",
            "Column Break",
            "Tab Break",
            "HTML",
            "Button",
        ):
            continue

        columns.append({
            "label": df.label or df.fieldname,
            "fieldname": df.fieldname,
            "fieldtype": df.fieldtype,
            "options": df.options,
            "width": 150,
        })

    # CEO-dashboard-aligned calculated columns
    columns.extend([
        {"label": "Daily BCM", "fieldname": "daily_bcm", "fieldtype": "Float", "width": 120},
        {"label": "Daily Left", "fieldname": "daily_left", "fieldtype": "Float", "width": 120},
        {"label": "MTD Plan", "fieldname": "mtd_plan", "fieldtype": "Float", "width": 130},
        {"label": "MTD C Plan", "fieldname": "mtd_c_plan", "fieldtype": "Float", "width": 130},
        {"label": "MTD W Plan", "fieldname": "mtd_w_plan", "fieldtype": "Float", "width": 130},
        {"label": "Remaining", "fieldname": "remaining_bcm", "fieldtype": "Float", "width": 130},
    ])

    return columns


# =========================================================
# DATA
# =========================================================

def get_data(define_name):
    rows = []

    # Load Define Monthly Production
    define_doc = frappe.get_doc("Define Monthly Production", define_name)

    plan_names = {
        row.monthly_production_plan
        for row in define_doc.define
        if row.monthly_production_plan
    }

    if not plan_names:
        return []

    plans = frappe.get_all(
        "Monthly Production Planning",
        filters={"name": ["in", list(plan_names)]},
        fields=["*"],
    )

    for p in plans:
        # Authoritative fields
        monthly = p.get("monthly_target_bcm") or 0
        coal_total = p.get("coal_tons_planned") or 0
        waste_total = p.get("waste_bcms_planned") or 0
        days = p.get("num_prod_days") or 0
        done = p.get("prod_days_completed") or 0
        mtd_actual = p.get("month_actual_bcm") or 0
        target_bcm_day = p.get("target_bcm_day") or 0

        # CEO Dashboard aligned calculations
        daily_bcm = p.get("mtd_bcm_day") or 0
        daily_left = target_bcm_day - daily_bcm

        mtd_plan = (monthly / days * done) if days else 0
        mtd_c_plan = (coal_total / days * done) if days else 0
        mtd_w_plan = (waste_total / days * done) if days else 0
        remaining = monthly - mtd_actual

        # Inject calculated fields
        p.update({
            "daily_bcm": daily_bcm,
            "daily_left": daily_left,
            "mtd_plan": mtd_plan,
            "mtd_c_plan": mtd_c_plan,
            "mtd_w_plan": mtd_w_plan,
            "remaining_bcm": remaining,
        })

        rows.append(p)

    return rows


# =========================================================
# SCHEDULER JOB (USED BY hooks.py)
# =========================================================

def rebuild_prepared_report():
    """
    Scheduler job to rebuild all Prepared Reports
    for HO-DB-0001 every 20 minutes.
    """

    report_name = "HO-DB-0001"

    prepared_reports = frappe.get_all(
        "Prepared Report",
        filters={"report_name": report_name},
        pluck="name",
    )

    for pr in prepared_reports:
        frappe.enqueue(
            "frappe.desk.query_report.run",
            report_name=report_name,
            prepared_report_name=pr,
            user="Administrator",
            now=False,
        )
