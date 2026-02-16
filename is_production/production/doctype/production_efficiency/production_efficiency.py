from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, add_days, now_datetime


# -------------------------------------------------------------------
# Hour slot mapping (normalize Hourly Production hour_slot -> slot 1..24)
# Slot 1 = 06:00-07:00 ... Slot 24 = 05:00-06:00
# -------------------------------------------------------------------
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

DAY_TABLE_FIELDS = {
    0: "monday",
    1: "tuesday",
    2: "wednesday",
    3: "thursday",
    4: "friday",
    5: "saturday",
    6: "sunday",
}

# Exact fieldnames from your console output (no guessing)
SLOT_FIELDS = {
    "monday": [
        "six_to_seven", "seven_to_eight", "eight_nine", "nine_ten",
        "ten_eleven", "eleven_twelve", "twelve_thirteen", "thirteen_fourteen",
        "fourteen_fifteen", "fifteen_sixteen", "sixteen_seventeen", "seventeen_eighteen",
        "eighteen_nineteen", "nineteen_twenty", "twenty_twentyone", "twentyone_twentytwo",
        "twentytwo_twentythree", "twentythree_twentyfour", "twentyfour_one", "one_two",
        "two_three", "three_four", "four_five", "five_six",
    ],
    "tuesday": [
        "six_seven", "seven_eight", "eight_nine", "nine_ten",
        "ten_eleven", "eleven_twelve", "twelve_thirteen", "thirteen_fourteen",
        "fourteen_fifteen", "fifteen_sixteen", "sixteen_seventeen", "seventeen_eighteen",
        "eighteen_nineteen", "nineteen_twenty", "twenty_twentyone", "twentyone_twentytwo",
        "twentytwo_twentythree", "twentythree_twentyfour", "twentyfour_one", "one_two",
        "two_three", "three_four", "four_five", "five_six",
    ],
    "wednesday": "tuesday",
    "thursday": "tuesday",
    "friday": [
        "six_seven", "seven_eight", "eight_nine", "nine_ten",
        "ten_eleven", "eleven_twelve", "twelve_thirteen", "thirteen_fourteen",
        "fourteen_fifteen", "fifteen_sixteen", "sixteen_seventeen", "seventeen_eighteen",
        "eighteen_nineteen", "nineteen_twenty", "twenty_twentyone", "twentyone_twentytwo",
        "twentytwo_twentythree", "twentythree_zero_zero", "zerozero_one", "one_two",
        "two_three", "three_four", "four_five", "five_six",
    ],
    "saturday": [
        "six_seven", "seven_eight", "eight_nine", "nine_ten",
        "ten_eleven", "eleven_twelve", "twelve_thirteen", "thirteen_fourteen",
        "fourteen_fifteen", "fifteen_sixteen", "sixteen_seventeen", "seventeen_eighteen",
        "eighteen_nineteen", "nineteen_twenty", "twenty_twentyone", "twentyone_twentytwo",
        "twentytwo_twentythree", "twentythree_zerozero", "zerozero_one", "one_two",
        "two_three", "three_four", "four_fives", "five_six",
    ],
    "sunday": [
        "six_seven", "seven_eight", "eight_nine", "nine_ten",
        "ten_eleven", "eleven_twelve", "twelve_thirteen", "thirteen_fourteen",
        "fourteen_fifteen", "fifteen_sixteen", "sixteen_seventeen", "seventeen_eighteen",
        "eighteen_nineteen", "nineteen_twenty", "twenty_twentyone", "twentyone_twentytwo",
        "twentytwo_twentythree", "twentythree_zerozero", "zerozero_one", "one_two",
        "two_three", "three_four", "four_five", "five_six",
    ],
}


def _to_date(d):
    return getdate(d)


def _current_week_range_auto():
    today = _to_date(now_datetime().date())
    monday = add_days(today, -today.weekday())
    sunday = add_days(monday, 6)
    return monday, sunday


def _previous_week_range_auto():
    today = _to_date(now_datetime().date())
    this_monday = add_days(today, -today.weekday())
    prev_monday = add_days(this_monday, -7)
    prev_sunday = add_days(prev_monday, 6)
    return prev_monday, prev_sunday


def _normalise_hour_slot(raw: str) -> str | None:
    if not raw:
        return None
    s = str(raw).strip()
    s = s.replace(":00:00", ":00")
    if "-" not in s:
        return None
    a, b = s.split("-", 1)
    a = a.strip()[:5]
    b = b.strip()[:5]

    def _hhmm_to_hmm(x: str) -> str:
        try:
            hh, mm = x.split(":")
            return f"{int(hh)}:{mm}"
        except Exception:
            return x

    return f"{_hhmm_to_hmm(a)}-{_hhmm_to_hmm(b)}"


def _get_slot_fields_for_day(day_field: str) -> list[str]:
    v = SLOT_FIELDS.get(day_field)
    if isinstance(v, str):
        return SLOT_FIELDS[v]
    return v


def _fetch_hourly_bcms(site: str, start_date, end_date):
    rows = frappe.db.sql(
        """
        SELECT
            hp.prod_date AS prod_date,
            tl.asset_name_shoval AS excavator,
            hp.hour_slot AS hour_slot,
            SUM(tl.bcms) AS bcm
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.location = %s
          AND hp.prod_date BETWEEN %s AND %s
          AND tl.asset_name_shoval IS NOT NULL
        GROUP BY
            hp.prod_date,
            tl.asset_name_shoval,
            hp.hour_slot
        """,
        (site, start_date, end_date),
        as_dict=True,
    )

    data = {}
    for r in rows:
        d = _to_date(r.prod_date)
        ex = r.excavator
        slot_key = _normalise_hour_slot(r.hour_slot)
        slot = HOUR_SLOT_MAP.get(slot_key) if slot_key else None
        if not slot:
            continue
        data.setdefault(d, {}).setdefault(ex, {})[slot] = int(r.bcm or 0)

    return data


def _populate_child_tables(pe_doc: Document, day_data: dict):
    # clear
    for _, day_field in DAY_TABLE_FIELDS.items():
        if pe_doc.meta.has_field(day_field):
            pe_doc.set(day_field, [])

    # fill per date
    for prod_date, excavators_map in day_data.items():
        weekday = prod_date.weekday()  # 0=Mon..6=Sun
        day_field = DAY_TABLE_FIELDS.get(weekday)
        if not day_field or not pe_doc.meta.has_field(day_field):
            continue

        slot_fields = _get_slot_fields_for_day(day_field)
        if not slot_fields or len(slot_fields) != 24:
            frappe.log_error(
                f"{day_field} slot fields invalid: {slot_fields}",
                "PE populate child tables",
            )
            continue

        for excavator_name in sorted(excavators_map.keys()):
            row = pe_doc.append(day_field, {})
            row.set("excavators", excavator_name)

            ex_slot_data = excavators_map.get(excavator_name, {})
            for slot in range(1, 25):
                row.set(slot_fields[slot - 1], int(ex_slot_data.get(slot, 0) or 0))


def _update_single_pe_doc(doc: Document):
    if not doc.site or not doc.start_date or not doc.end_date:
        return

    start_date = _to_date(doc.start_date)
    end_date = _to_date(doc.end_date)

    day_data = _fetch_hourly_bcms(doc.site, start_date, end_date)
    _populate_child_tables(doc, day_data)

    if doc.meta.has_field("hourly_report"):
        doc.set(
            "hourly_report",
            f"<div class='text-muted' style='padding:8px;'>Updated by server at: {frappe.utils.now()}</div>",
        )

    doc.save(ignore_permissions=True)


@frappe.whitelist()
def run_update(docname: str):
    doc = frappe.get_doc("Production Efficiency", docname)

    if not doc.site or not doc.start_date or not doc.end_date:
        frappe.throw("Please set Site, Start Date and End Date before running.")

    _update_single_pe_doc(doc)
    frappe.db.commit()

    return {"ok": True, "message": "Updated and child tables repopulated."}


@frappe.whitelist()
def get_hourly_site_control_excavators(site: str) -> dict:
    """
    Returns the production excavator count for a site from the latest Hourly Site Control doc.
    Looks inside the child table rows (commonly fieldname 'sites') for matching row.site == site.
    """
    site = (site or "").strip()
    if not site:
        return {"site": site, "production_excavators": 0}

    name = frappe.db.get_value(
        "Hourly Site Control",
        filters={},
        fieldname="name",
        order_by="creation desc",
    )
    if not name:
        return {"site": site, "production_excavators": 0}

    doc = frappe.get_doc("Hourly Site Control", name)

    for row in (doc.get("sites") or []):
        if (row.get("site") or "").strip() == site:
            try:
                return {
                    "site": site,
                    "production_excavators": int(row.get("production_excavators") or 0),
                }
            except Exception:
                return {"site": site, "production_excavators": 0}

    return {"site": site, "production_excavators": 0}


def get_sites_from_hourly_site_control() -> list[str]:
    name = frappe.db.get_value(
        "Hourly Site Control",
        filters={},
        fieldname="name",
        order_by="creation desc",
    )
    if not name:
        return []

    doc = frappe.get_doc("Hourly Site Control", name)
    sites = []
    for row in (doc.get("sites") or []):
        if row.get("site"):
            sites.append(row.get("site"))

    return sorted(list(dict.fromkeys(sites)))


def upsert_production_efficiency(site: str, start_date, end_date) -> str:
    start_date = _to_date(start_date)
    end_date = _to_date(end_date)

    name = f"{site}:{start_date}-{end_date}"

    if frappe.db.exists("Production Efficiency", name):
        doc = frappe.get_doc("Production Efficiency", name)
    else:
        doc = frappe.new_doc("Production Efficiency")
        doc.name = name
        if doc.meta.has_field("site"):
            doc.site = site
        if doc.meta.has_field("start_date"):
            doc.start_date = start_date
        if doc.meta.has_field("end_date"):
            doc.end_date = end_date
        doc.insert(ignore_permissions=True)

    if doc.meta.has_field("site"):
        doc.site = site
    if doc.meta.has_field("start_date"):
        doc.start_date = start_date
    if doc.meta.has_field("end_date"):
        doc.end_date = end_date

    doc.save(ignore_permissions=True)
    return doc.name


def close_off_weekly_records():
    start_date, end_date = _previous_week_range_auto()

    names = frappe.get_all(
        "Production Efficiency",
        filters={"start_date": start_date, "end_date": end_date},
        pluck="name",
    )

    for name in names:
        try:
            doc = frappe.get_doc("Production Efficiency", name)
            if doc.meta.has_field("status"):
                doc.status = "Closed"
            if doc.meta.has_field("workflow_state"):
                doc.workflow_state = "Closed"
            if doc.meta.has_field("is_closed"):
                doc.is_closed = 1
            if doc.meta.has_field("closed"):
                doc.closed = 1
            doc.save(ignore_permissions=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"PE close failed ({name})")


def create_weekly_records():
    start_date, end_date = _current_week_range_auto()
    sites = get_sites_from_hourly_site_control()

    if not sites:
        frappe.log_error("No sites found in Hourly Site Control.", "PE create_weekly_records")
        return

    for site in sites:
        try:
            upsert_production_efficiency(site, start_date, end_date)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"PE create failed ({site})")


def update_weekly_records():
    start_date, end_date = _current_week_range_auto()

    try:
        create_weekly_records()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "PE update_weekly_records: create_weekly_records failed")

    pe_rows = frappe.get_all(
        "Production Efficiency",
        filters={"start_date": start_date, "end_date": end_date},
        fields=["name"],
        limit_page_length=500,
    )

    for r in pe_rows:
        try:
            doc = frappe.get_doc("Production Efficiency", r.name)
            _update_single_pe_doc(doc)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"PE scheduled update failed ({r.get('name')})")

    frappe.db.commit()


class ProductionEfficiency(Document):
    pass
