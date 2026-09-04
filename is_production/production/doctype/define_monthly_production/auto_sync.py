from __future__ import annotations

import frappe
from frappe.utils import getdate


# ============================================================
# DEFINE MONTHLY PRODUCTION AUTO SYNC
# ============================================================
#
# Site grouping confirmed from August 2026 LAB configuration.
#
# Ermelo / Data:
#   - Uitgevallen
#   - Koppie
#   - Bankfontein
#
# Middelburg / Data:
#   - Klipfontein
#   - Gwab
#   - Kriel Rehabilitation
#
# Hourly / Hourly:
#   - all six sites
#
# Graphs / Graphs:
#   - all six sites
#
# The Define month/year is determined from the
# Monthly Production Planning PROD MONTH END DATE.
# ============================================================


ERMELO_SITES = {
    "Uitgevallen",
    "Koppie",
    "Bankfontein",
}

MIDDELBURG_SITES = {
    "Klipfontein",
    "Gwab",
    "Kriel Rehabilitation",
}

SUPPORTED_SITES = ERMELO_SITES | MIDDELBURG_SITES


ALL_MONTH_PARENT_TYPES = (
    ("Ermelo", "Data"),
    ("Middelburg", "Data"),
    ("Hourly", "Hourly"),
    ("Graphs", "Graphs"),
)


def _clean(value):
    return str(value or "").strip()


def _get_month_year(doc):
    """
    Define Monthly Production belongs to the month in which
    the production period ENDS.

    Example:
        Start = 2026-07-20
        End   = 2026-08-23

    Result:
        August 2026
    """

    end_date = (
        doc.get("prod_month_end_date")
        or doc.get("prod_month_end")
    )

    if not end_date:
        return None, None

    end_date = getdate(end_date)

    return end_date.strftime("%B"), str(end_date.year)


def _get_target_pairs(site):
    """
    Return the Define Monthly Production parents that
    this site must belong to.
    """

    targets = [
        ("Hourly", "Hourly"),
        ("Graphs", "Graphs"),
    ]

    if site in ERMELO_SITES:
        targets.append(("Ermelo", "Data"))

    elif site in MIDDELBURG_SITES:
        targets.append(("Middelburg", "Data"))

    return targets


def _get_define_doc(month, year, complex_name, type_name):
    """
    Find the monthly Define Monthly Production document
    by its field values.

    If it does not exist, create it.
    """

    filters = {
        "month": month,
        "year": str(year),
        "complex": complex_name,
        "type": type_name,
    }

    existing = frappe.db.get_value(
        "Define Monthly Production",
        filters,
        "name",
    )

    if existing:
        return frappe.get_doc(
            "Define Monthly Production",
            existing,
        )

    doc = frappe.new_doc("Define Monthly Production")

    doc.month = month
    doc.year = str(year)
    doc.complex = complex_name
    doc.type = type_name

    doc.insert(ignore_permissions=True)

    frappe.logger("is_production").info(
        "Created Define Monthly Production %s",
        doc.name,
    )

    return doc


def _ensure_month_parents(month, year):
    """
    Create all four parent documents for the month.

    This means the first Monthly Production Planning saved
    for a new month will create:

        Month-Year-Ermelo-Data
        Month-Year-Middelburg-Data
        Month-Year-Hourly-Hourly
        Month-Year-Graphs-Graphs
    """

    docs = {}

    for complex_name, type_name in ALL_MONTH_PARENT_TYPES:

        parent = _get_define_doc(
            month,
            year,
            complex_name,
            type_name,
        )

        docs[(complex_name, type_name)] = parent

    return docs


def _remove_plan_from_other_managed_documents(
    plan_name,
    desired_parent_names,
):
    """
    If the MPP dates or site changed, remove its old child
    rows from managed Define Monthly Production documents.

    This prevents a plan remaining in both August and
    September after its end date changes.
    """

    child_rows = frappe.get_all(
        "MPP Child",
        filters={
            "monthly_production_plan": plan_name,
            "parenttype": "Define Monthly Production",
        },
        fields=[
            "name",
            "parent",
        ],
        limit_page_length=0,
    )

    parents = set()

    for row in child_rows:
        parent = _clean(row.get("parent"))

        if parent:
            parents.add(parent)

    for parent_name in parents:

        if parent_name in desired_parent_names:
            continue

        if not frappe.db.exists(
            "Define Monthly Production",
            parent_name,
        ):
            continue

        parent = frappe.get_doc(
            "Define Monthly Production",
            parent_name,
        )

        # Only automatically manage our four standard
        # Define document types.
        key = (
            _clean(parent.get("complex")),
            _clean(parent.get("type")),
        )

        if key not in ALL_MONTH_PARENT_TYPES:
            continue

        changed = False

        for row in list(parent.get("define") or []):

            if (
                _clean(row.get("monthly_production_plan"))
                == plan_name
            ):
                parent.remove(row)
                changed = True

        if changed:
            parent.save(ignore_permissions=True)


def _upsert_site_row(
    parent,
    plan_name,
    site,
    start_date,
    end_date,
):
    """
    Keep one row per site in each Define Monthly Production.

    If:
      - same plan already exists -> update it
      - same site has old plan -> replace it
      - duplicates exist -> retain one and remove extras
    """

    keeper = None
    changed = False

    for row in list(parent.get("define") or []):

        row_site = _clean(row.get("site"))
        row_plan = _clean(
            row.get("monthly_production_plan")
        )

        matches = (
            row_site == site
            or row_plan == plan_name
        )

        if not matches:
            continue

        if keeper is None:
            keeper = row
        else:
            parent.remove(row)
            changed = True

    if keeper is None:
        keeper = parent.append(
            "define",
            {},
        )
        changed = True

    values = {
        "site": site,
        "monthly_production_plan": plan_name,
        "start_date": start_date,
        "end_date": end_date,
    }

    for fieldname, value in values.items():

        if keeper.get(fieldname) != value:
            keeper.set(fieldname, value)
            changed = True

    if changed:
        parent.save(ignore_permissions=True)

    return changed


def sync_monthly_production_plan(doc, method=None):
    """
    Frappe document-event handler.

    Called automatically when Monthly Production Planning
    is inserted or updated.
    """

    if isinstance(doc, str):
        doc = frappe.get_doc(
            "Monthly Production Planning",
            doc,
        )

    if not doc or not doc.get("name"):
        return

    site = _clean(doc.get("location"))

    if not site:
        return

    # Do not touch unmapped sites.
    if site not in SUPPORTED_SITES:

        frappe.logger("is_production").warning(
            "Define Monthly Production auto sync skipped "
            "unsupported site %s on plan %s",
            site,
            doc.name,
        )

        return

    start_date = doc.get("prod_month_start_date")

    end_date = (
        doc.get("prod_month_end_date")
        or doc.get("prod_month_end")
    )

    if not start_date or not end_date:
        return

    month, year = _get_month_year(doc)

    if not month or not year:
        return

    # --------------------------------------------------------
    # 1. Ensure all four monthly parent records exist.
    # --------------------------------------------------------

    month_parents = _ensure_month_parents(
        month,
        year,
    )

    # --------------------------------------------------------
    # 2. Work out which three parents THIS site belongs to.
    # --------------------------------------------------------

    target_pairs = _get_target_pairs(site)

    target_docs = [
        month_parents[pair]
        for pair in target_pairs
    ]

    desired_parent_names = {
        parent.name
        for parent in target_docs
    }

    # --------------------------------------------------------
    # 3. Remove this plan from old month/group documents.
    # --------------------------------------------------------

    _remove_plan_from_other_managed_documents(
        doc.name,
        desired_parent_names,
    )

    # --------------------------------------------------------
    # 4. Add/update this site in its correct documents.
    # --------------------------------------------------------

    changed_parents = []

    for parent in target_docs:

        changed = _upsert_site_row(
            parent=parent,
            plan_name=doc.name,
            site=site,
            start_date=start_date,
            end_date=end_date,
        )

        if changed:
            changed_parents.append(parent.name)

    frappe.logger("is_production").info(
        "Define Monthly Production auto sync: "
        "plan=%s site=%s month=%s year=%s parents=%s",
        doc.name,
        site,
        month,
        year,
        ", ".join(desired_parent_names),
    )

    return {
        "plan": doc.name,
        "site": site,
        "month": month,
        "year": year,
        "parents": sorted(desired_parent_names),
        "changed": sorted(changed_parents),
    }


def remove_monthly_production_plan(doc, method=None):
    """
    Remove a deleted/cancelled Monthly Production Planning
    from the managed Define Monthly Production documents.
    """

    plan_name = (
        doc
        if isinstance(doc, str)
        else doc.get("name")
    )

    plan_name = _clean(plan_name)

    if not plan_name:
        return

    child_rows = frappe.get_all(
        "MPP Child",
        filters={
            "monthly_production_plan": plan_name,
            "parenttype": "Define Monthly Production",
        },
        fields=[
            "parent",
        ],
        limit_page_length=0,
    )

    parents = {
        _clean(row.get("parent"))
        for row in child_rows
        if _clean(row.get("parent"))
    }

    for parent_name in parents:

        if not frappe.db.exists(
            "Define Monthly Production",
            parent_name,
        ):
            continue

        parent = frappe.get_doc(
            "Define Monthly Production",
            parent_name,
        )

        key = (
            _clean(parent.get("complex")),
            _clean(parent.get("type")),
        )

        if key not in ALL_MONTH_PARENT_TYPES:
            continue

        changed = False

        for row in list(parent.get("define") or []):

            if (
                _clean(row.get("monthly_production_plan"))
                == plan_name
            ):
                parent.remove(row)
                changed = True

        if changed:
            parent.save(ignore_permissions=True)


def sync_plan_by_name(name):
    """
    Manual test/recovery helper.

    Example:

    bench --site kosie.isambane.co.za execute \
      is_production.production.doctype.define_monthly_production.auto_sync.sync_plan_by_name \
      --kwargs '{"name":"2026-08-31-Koppie"}'
    """

    doc = frappe.get_doc(
        "Monthly Production Planning",
        name,
    )

    return sync_monthly_production_plan(doc)


def sync_all_plans_for_define_month(month, year):
    """
    Optional recovery/backfill helper.

    Month is decided from prod_month_end_date.
    """

    year = int(year)

    plans = frappe.get_all(
        "Monthly Production Planning",
        fields=[
            "name",
            "location",
            "prod_month_start_date",
            "prod_month_end_date",
        ],
        limit_page_length=0,
    )

    synced = []

    for row in plans:

        end_date = row.get("prod_month_end_date")

        if not end_date:
            continue

        end_date = getdate(end_date)

        if (
            end_date.strftime("%B") != month
            or end_date.year != year
        ):
            continue

        if _clean(row.get("location")) not in SUPPORTED_SITES:
            continue

        result = sync_plan_by_name(
            row.get("name")
        )

        synced.append(result)

    return synced
