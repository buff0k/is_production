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

# -------------------------------------------------------------------
# A&U weekly engine (same query concept as engineering dashboard)
# -------------------------------------------------------------------


def _fetch_submitted_assets(site: str) -> list[dict]:
    """Return submitted (docstatus=1) Assets for a site in AU_DB_CATEGORIES."""
    site = (site or "").strip()
    if not site:
        return []

    return frappe.get_all(
        "Asset",
        filters={
            "docstatus": 1,
            "location": site,
            "asset_category": ["in", AU_DB_CATEGORIES],
        },
        fields=["name", "asset_name", "asset_category"],
        order_by="asset_category asc, asset_name asc",
        limit_page_length=5000,
    )

AU_DT = "Availability and Utilisation"
AU_DB_CATEGORIES = ["ADT", "Excavator", "Dozer"]


def _get_submitted_asset_categories() -> list[str]:
    """
    Return which of AU_DB_CATEGORIES actually exist as SUBMITTED Assets (docstatus=1).
    A&U docs can be any status, but we only include categories that have submitted Assets.
    """
    rows = frappe.get_all(
        "Asset",
        filters={"docstatus": 1, "asset_category": ["in", AU_DB_CATEGORIES]},
        pluck="asset_category",
        limit_page_length=5000,
    )
    return [c for c in AU_DB_CATEGORIES if c in set(rows)]



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


def _fetch_au_rows(site: str, start_date, end_date, asset_names: list[str] | None = None):
    """
    Fetch Availability & Utilisation rows for a site/date-range.

    Notes:
      - No docstatus filter on A&U docs (engine may leave them as Draft).
      - No shift filter (supports both 2x12 (Day/Night) and 3x8 (Morning/Afternoon/Night)).
      - If asset_names is provided, only those assets are included.
    """
    site = (site or "").strip()
    if not site:
        return []

    filters = {
        "location": site,
        "shift_date": ["between", [start_date, end_date]],
        "asset_category": ["in", AU_DB_CATEGORIES],
    }
    if asset_names:
        filters["asset_name"] = ["in", asset_names]

    return frappe.get_all(
        AU_DT,
        filters=filters,
        fields=[
            "shift_date",
            "shift",
            "asset_category",
            "asset_name",
            "plant_shift_availability",
            "plant_shift_utilisation",
            "docstatus",
        ],
        order_by="shift_date asc, asset_category asc, asset_name asc, shift asc",
        limit_page_length=50000,
    )

def _compute_au_daily_averages(rows: list[dict]) -> dict:
    """
    Returns:
      {
        "YYYY-MM-DD": {
          "ADT": {"avail": float|None, "util": float|None},
          "Excavator": {...},
          "Dozer": {...}
        },
        ...
      }
    Logic matches dashboard: average all values found for that day+category.
    (If both day+night exist, they are included in the same average naturally.)
    """
    bucket = {}
    for r in rows:
        day = str(r.get("shift_date"))
        cat = r.get("asset_category")
        if cat not in AU_DB_CATEGORIES:
            continue

        bucket.setdefault(day, {}).setdefault(cat, {"avail": [], "util": []})

        av = r.get("plant_shift_availability")
        ut = r.get("plant_shift_utilisation")
        if av is not None:
            bucket[day][cat]["avail"].append(float(av))
        if ut is not None:
            bucket[day][cat]["util"].append(float(ut))

    out = {}
    for day, cats in bucket.items():
        out[day] = {}
        for cat in AU_DB_CATEGORIES:
            avs = cats.get(cat, {}).get("avail", [])
            uts = cats.get(cat, {}).get("util", [])
            out[day][cat] = {
                "avail": (sum(avs) / len(avs)) if avs else None,
                "util": (sum(uts) / len(uts)) if uts else None,
            }
    return out


AU_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

def _norm(s: str | None) -> str:
    return (s or "").strip().lower()

def _avg(vals: list[float]) -> float | None:
    if not vals:
        return None
    return sum(vals) / len(vals)

def _compute_au_asset_weekday_averages(rows: list[dict]) -> dict:
    """
    Keyed by asset_name (plant no):
      { "<plant_no>": { "monday": {"avail":..., "util":...}, ... } }
    """
    bucket: dict[str, dict[str, dict[str, list[float]]]] = {}

    for r in rows:
        asset = (r.get("asset_name") or "").strip()
        if not asset:
            continue

        try:
            d = _to_date(r.get("shift_date"))
        except Exception:
            continue

        day_field = DAY_TABLE_FIELDS.get(d.weekday())
        if not day_field:
            continue

        rec = bucket.setdefault(asset, {}).setdefault(day_field, {"avail": [], "util": []})

        av = r.get("plant_shift_availability")
        ut = r.get("plant_shift_utilisation")
        if av is not None:
            try:
                rec["avail"].append(float(av))
            except Exception:
                pass
        if ut is not None:
            try:
                rec["util"].append(float(ut))
            except Exception:
                pass

    out: dict[str, dict[str, dict[str, float | None]]] = {}
    for asset, days in bucket.items():
        out[asset] = {}
        for day in AU_WEEKDAYS:
            avs = (days.get(day, {}) or {}).get("avail", []) or []
            uts = (days.get(day, {}) or {}).get("util", []) or []
            out[asset][day] = {"avail": _avg(avs), "util": _avg(uts)}

    return out

def _detect_weekday_fields(child_meta) -> dict[str, str]:
    mapping: dict[str, str] = {}

    # Prefer exact fieldnames first
    for day in AU_WEEKDAYS:
        if child_meta.has_field(day):
            mapping[day] = day

    # Fallback: match by label / abbreviations
    for df in (child_meta.fields or []):
        fn = _norm(df.fieldname)
        lbl = _norm(df.label)

        for day in AU_WEEKDAYS:
            if day in mapping:
                continue
            abbr = day[:3]
            if fn == day or lbl == day:
                mapping[day] = df.fieldname
            elif fn == abbr or lbl == abbr:
                mapping[day] = df.fieldname
            elif (fn.startswith(abbr) and len(fn) <= 5) or (lbl.startswith(abbr) and len(lbl) <= 5):
                mapping[day] = df.fieldname

    return mapping

def _detect_asset_fields(child_meta) -> tuple[str | None, bool, str | None, str | None]:
    """
    Returns:
      (asset_field, asset_is_link_to_asset, asset_name_field, asset_category_field)
    """
    best_asset = None
    best_score = -1

    asset_name_field = None
    asset_category_field = None

    for df in (child_meta.fields or []):
        fn = _norm(df.fieldname)
        lbl = _norm(df.label)

        if not asset_name_field:
            if fn in ("asset_name", "plant_no", "plant", "equipment_no", "equipment"):
                asset_name_field = df.fieldname
            elif "plant" in fn and df.fieldtype in ("Data", "Link"):
                asset_name_field = df.fieldname
            elif lbl in ("asset name", "plant", "plant no", "equipment", "equipment no"):
                asset_name_field = df.fieldname

        if not asset_category_field:
            if fn in ("asset_category", "category"):
                asset_category_field = df.fieldname
            elif "category" in fn and df.fieldtype in ("Data", "Select", "Link"):
                asset_category_field = df.fieldname
            elif lbl in ("asset category", "category"):
                asset_category_field = df.fieldname

        score = 0
        if df.fieldtype == "Link" and _norm(df.options) == "asset":
            score += 100
        if fn == "asset":
            score += 90
        if fn == "asset_name":
            score += 80
        if fn in ("plant_no", "plant", "equipment", "equipment_no"):
            score += 70
        if "asset" in fn:
            score += 60
        if "plant" in fn:
            score += 50
        if lbl in ("asset", "asset name", "plant", "plant no", "equipment", "equipment no"):
            score += 40

        if score > best_score and df.fieldtype in ("Link", "Data"):
            best_score = score
            best_asset = df

    if not best_asset:
        return None, False, asset_name_field, asset_category_field

    return (
        best_asset.fieldname,
        bool(best_asset.fieldtype == "Link" and _norm(best_asset.options) == "asset"),
        asset_name_field,
        asset_category_field,
    )

def _weekday_label_from_date(d) -> str:
    labels = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return labels[_to_date(d).weekday()]


def _compute_au_asset_date_averages(rows: list[dict]) -> dict:
    """
    Returns:
      {
        "<asset_name>": {
          "YYYY-MM-DD": {"avail": float|None, "util": float|None},
          ...
        },
        ...
      }
    Averages across all shifts found for that asset+date.
    """
    bucket: dict[str, dict[str, dict[str, list[float]]]] = {}

    for r in rows:
        asset = (r.get("asset_name") or "").strip()
        if not asset:
            continue

        day = str(_to_date(r.get("shift_date")))
        bucket.setdefault(asset, {}).setdefault(day, {"avail": [], "util": []})

        av = r.get("plant_shift_availability")
        ut = r.get("plant_shift_utilisation")

        if av is not None:
            try:
                bucket[asset][day]["avail"].append(float(av))
            except Exception:
                pass

        if ut is not None:
            try:
                bucket[asset][day]["util"].append(float(ut))
            except Exception:
                pass

    out: dict[str, dict[str, dict[str, float | None]]] = {}
    for asset, days in bucket.items():
        out[asset] = {}
        for day, vals in days.items():
            avs = vals.get("avail", []) or []
            uts = vals.get("util", []) or []
            out[asset][day] = {
                "avail": (sum(avs) / len(avs)) if avs else None,
                "util": (sum(uts) / len(uts)) if uts else None,
            }

    return out


def _populate_availability_child_rows(pe_doc: Document, assets: list[dict], asset_date: dict, start_date, end_date):
    """
    per_asset_availability (Availability Child):
      date_ (reqd), weekdays_c (reqd), assets_c (Link Asset), availability_c
    """
    if not pe_doc.meta.has_field("per_asset_availability"):
        return

    pe_doc.set("per_asset_availability", [])

    d = _to_date(start_date)
    end_date = _to_date(end_date)

    while d <= end_date:
        day_key = str(d)
        weekday_lbl = _weekday_label_from_date(d)

        for a in (assets or []):
            asset_docname = a.get("name")        # Asset docname (Link)
            plant_no = a.get("asset_name") or "" # used in A&U rows

            v = (asset_date.get(plant_no, {}) or {}).get(day_key, {}) or {}
            row = pe_doc.append("per_asset_availability", {})
            row.set("date_", d)
            row.set("weekdays_c", weekday_lbl)
            row.set("assets_c", asset_docname)
            row.set("availability_c", v.get("avail"))

        d = add_days(d, 1)


def _populate_utilisation_child_rows(pe_doc: Document, assets: list[dict], asset_date: dict, start_date, end_date):
    """
    per_asset_utilisation (Utilisation Child):
      date_d (reqd), weekdays_c (reqd), assets_c (Link Asset), utilasazation_c
    """
    if not pe_doc.meta.has_field("per_asset_utilisation"):
        return

    pe_doc.set("per_asset_utilisation", [])

    d = _to_date(start_date)
    end_date = _to_date(end_date)

    while d <= end_date:
        day_key = str(d)
        weekday_lbl = _weekday_label_from_date(d)

        for a in (assets or []):
            asset_docname = a.get("name")        # Asset docname (Link)
            plant_no = a.get("asset_name") or "" # used in A&U rows

            v = (asset_date.get(plant_no, {}) or {}).get(day_key, {}) or {}
            row = pe_doc.append("per_asset_utilisation", {})
            row.set("date_d", d)
            row.set("weekdays_c", weekday_lbl)
            row.set("assets_c", asset_docname)
            row.set("utilasazation_c", v.get("util"))

        d = add_days(d, 1)


def _populate_per_asset_tables(pe_doc: Document, assets: list[dict], au_rows: list[dict], start_date, end_date):
    asset_date = _compute_au_asset_date_averages(au_rows)
    _populate_availability_child_rows(pe_doc, assets, asset_date, start_date, end_date)
    _populate_utilisation_child_rows(pe_doc, assets, asset_date, start_date, end_date)


def _weekday_label(d) -> str:
    labels = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return labels[_to_date(d).weekday()]


def _populate_au_tables(pe_doc: Document, au_daily: dict, start_date, end_date):
    """
    Parent tables:
      - availability_b (Availability Day Entry)
      - utilisation_b (Utilisation Day Entry)

    Child fieldnames (exact from your JSON):
      Availability Day Entry:
        date_b, weekday_b, adt_b, excavator_b, dozer_b
      Utilisation Day Entry:
        date_b_b, weekday_b_b, adt_b_b, excavator_b_b, dozer_b_b
    """
    start_date = _to_date(start_date)
    end_date = _to_date(end_date)

    if pe_doc.meta.has_field("availability_b"):
        pe_doc.set("availability_b", [])
    if pe_doc.meta.has_field("utilisation_b"):
        pe_doc.set("utilisation_b", [])

    d = start_date
    while d <= end_date:
        day_key = str(d)
        day_payload = au_daily.get(day_key, {}) or {}

        # Availability row
        if pe_doc.meta.has_field("availability_b"):
            r1 = pe_doc.append("availability_b", {})
            r1.set("date_b", d)
            r1.set("weekday_b", _weekday_label(d))
            r1.set("adt_b", (day_payload.get("ADT", {}) or {}).get("avail"))
            r1.set("excavator_b", (day_payload.get("Excavator", {}) or {}).get("avail"))
            r1.set("dozer_b", (day_payload.get("Dozer", {}) or {}).get("avail"))

        # Utilisation row
        if pe_doc.meta.has_field("utilisation_b"):
            r2 = pe_doc.append("utilisation_b", {})
            r2.set("date_b_b", d)
            r2.set("weekday_b_b", _weekday_label(d))
            r2.set("adt_b_b", (day_payload.get("ADT", {}) or {}).get("util"))
            r2.set("excavator_b_b", (day_payload.get("Excavator", {}) or {}).get("util"))
            r2.set("dozer_b_b", (day_payload.get("Dozer", {}) or {}).get("util"))

        d = add_days(d, 1)




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
    for _, day_field in DAY_TABLE_FIELDS.items():
        if pe_doc.meta.has_field(day_field):
            pe_doc.set(day_field, [])

    for prod_date, excavators_map in day_data.items():
        weekday = prod_date.weekday()
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


def _get_hsc_production_excavators(site: str) -> int:
    site = (site or "").strip()
    if not site:
        return 0

    name = frappe.db.get_value(
        "Hourly Site Control",
        filters={},
        fieldname="name",
        order_by="creation desc",
    )
    if not name:
        return 0

    doc = frappe.get_doc("Hourly Site Control", name)
    for row in (doc.get("sites") or []):
        if (row.get("site") or "").strip() == site:
            try:
                return int(row.get("production_excavators") or 0)
            except Exception:
                return 0

    return 0


def _update_single_pe_doc(doc: Document):
    # -----------------------------
    # Hourly Production -> day child tables
    # -----------------------------
    if doc.site and doc.start_date and doc.end_date:
        hourly = _fetch_hourly_bcms(doc.site, doc.start_date, doc.end_date)
        _populate_child_tables(doc, hourly)

    # -----------------------------
    # A&U update (Information (A&U) tab drives the filters)
    # -----------------------------
    if (
        doc.meta.has_field("site_b")
        or doc.meta.has_field("availability_b")
        or doc.meta.has_field("utilisation_b")
        or doc.meta.has_field("per_asset_availability")
        or doc.meta.has_field("per_asset_utilisation")
    ):
        # Site defaults: site_b -> site
        if doc.meta.has_field("site_b") and not doc.get("site_b") and doc.get("site"):
            doc.set("site_b", doc.get("site"))

        au_site = (doc.get("site_b") or doc.get("site") or "").strip()

        # Use start_date_b/end_date_b if set, else default to current Mon..Sun
        au_start = doc.get("start_date_b")
        au_end = doc.get("end_date_b")

        if not au_start and not au_end:
            au_start, au_end = _current_week_range_auto()
        elif au_start and not au_end:
            au_start = _to_date(au_start)
            au_end = add_days(au_start, 6)
        elif au_end and not au_start:
            au_end = _to_date(au_end)
            au_start = add_days(au_end, -6)

        au_start = _to_date(au_start)
        au_end = _to_date(au_end)
        if au_start > au_end:
            au_start, au_end = au_end, au_start

        if doc.meta.has_field("start_date_b"):
            doc.set("start_date_b", au_start)
        if doc.meta.has_field("end_date_b"):
            doc.set("end_date_b", au_end)

        if au_site:
            # Y-axis: submitted assets only
            assets = _fetch_submitted_assets(au_site)
            asset_names = [a.get("asset_name") for a in (assets or []) if a.get("asset_name")]

            # Pull A&U values for those assets within the filtered range
            au_rows = _fetch_au_rows(au_site, au_start, au_end, asset_names=asset_names) if asset_names else []

            # Existing daily category tables
            au_daily = _compute_au_daily_averages(au_rows)
            _populate_au_tables(doc, au_daily, au_start, au_end)

            # New: per-asset rows (Asset x Date)
            _populate_per_asset_tables(doc, assets, au_rows, au_start, au_end)

            if doc.meta.has_field("html_report_b"):
                doc.set(
                    "html_report_b",
                    f"<div class='text-muted' style='padding:8px;'>A&amp;U updated at: {frappe.utils.now()}</div>",
                )


    # -----------------------------
    # WearCheck snapshot (last 10 days by register_date)
    # -----------------------------
    wc_site = None
    if doc.meta.has_field("site_b") and doc.get("site_b"):
        wc_site = doc.get("site_b")
    elif doc.get("site"):
        wc_site = doc.get("site")

    _populate_wearcheck_snapshot(doc, wc_site, days_back=10)


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
def enqueue_run_update(docname: str):
    """UI-safe: returns immediately, does the heavy work in background."""
    frappe.enqueue(
        method=_run_update_job,
        queue="default",      # use default so it runs even if you don't have a "long" worker
        timeout=1800,         # 30 min
        docname=docname,
        user=frappe.session.user,
        job_name=f"pe_update::{docname}",
    )
    return {"ok": True, "queued": True}


def _run_update_job(docname: str, user: str | None = None):
    try:
        doc = frappe.get_doc("Production Efficiency", docname)
        _update_single_pe_doc(doc)
        frappe.db.commit()

        if user:
            frappe.publish_realtime(
                "production_efficiency_update_done",
                {"docname": docname},
                user=user,
            )
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"PE update failed: {docname}")
        if user:
            frappe.publish_realtime(
                "production_efficiency_update_done",
                {"docname": docname, "error": "Update failed. Check Error Log."},
                user=user,
            )
        raise

@frappe.whitelist()
def debug_au_graph_kpis(docname: str) -> dict:
    """
    Mirrors the Graph (A&U) KPI rules:
      - If avail==0 and util==0 for a date => exclude that date entirely.
      - If one has value, the other may be 0 => include the date.
    Returns averages + the exact dates counted per category.
    """
    doc = frappe.get_doc("Production Efficiency", docname)

    avail_by_date = {}
    for r in (doc.get("availability_b") or []):
        d = str(r.get("date_b") or "")
        if not d:
            continue
        avail_by_date[d] = {
            "ADT": float(r.get("adt_b") or 0),
            "Excavator": float(r.get("excavator_b") or 0),
            "Dozer": float(r.get("dozer_b") or 0),
        }

    util_by_date = {}
    for r in (doc.get("utilisation_b") or []):
        d = str(r.get("date_b_b") or "")
        if not d:
            continue
        util_by_date[d] = {
            "ADT": float(r.get("adt_b_b") or 0),
            "Excavator": float(r.get("excavator_b_b") or 0),
            "Dozer": float(r.get("dozer_b_b") or 0),
        }

    dates = sorted(set(list(avail_by_date.keys()) + list(util_by_date.keys())))

    out = {}
    for cat in AU_DB_CATEGORIES:
        av_vals = []
        ut_vals = []
        used_dates = []

        for d in dates:
            a = float((avail_by_date.get(d, {}) or {}).get(cat) or 0)
            u = float((util_by_date.get(d, {}) or {}).get(cat) or 0)

            if a == 0 and u == 0:
                continue

            used_dates.append(d)
            av_vals.append(a)
            ut_vals.append(u)

        out[cat] = {
            "points": len(used_dates),
            "dates_used": used_dates,
            "avail_avg": (sum(av_vals) / len(av_vals)) if av_vals else 0,
            "util_avg": (sum(ut_vals) / len(ut_vals)) if ut_vals else 0,
        }

    return out


@frappe.whitelist()
def get_hourly_site_control_excavators(site: str) -> dict:
    site = (site or "").strip()
    if not site:
        return {"site": site, "production_excavators": 0}

    return {"site": site, "production_excavators": int(_get_hsc_production_excavators(site) or 0)}


# -------------------- WearCheck Snapshot (last N days) --------------------

def _detect_wearcheck_register_field(meta) -> str | None:
    for cand in ("registerdate", "register_date", "register_dt", "register_datetime", "registration_date"):
        if meta.has_field(cand):
            return cand
    return None


def _fetch_wearcheck_flagged_window(site: str | None, days_back: int = 10) -> list[dict]:
    """
    Returns rows for last N days (inclusive), filtered by register_date:
      - ONLY statuses 3/4 (so NOT all records for an asset)
      - include ALL flagged components for an asset
      - de-dupe to 1 row per (asset + component) in the window:
          worst status wins (4 over 3),
          then latest register_date,
          then creation desc
    """
    site = (site or "").strip() or None
    meta = frappe.get_meta("WearCheck Results")

    asset_field = "asset"
    location_field = "location"
    status_field = "status"

    register_field = _detect_wearcheck_register_field(meta)
    if not register_field:
        return []

    # optional fields
    sample_field = None
    for cand in ("sampledate", "sample_date", "sample_date_", "sample_datetime", "sample_dt"):
        if meta.has_field(cand):
            sample_field = cand
            break

    component_field = "component" if meta.has_field("component") else None

    action_field = None
    for cand in ("actiontext", "action_text", "action", "action_taken", "action_required"):
        if meta.has_field(cand):
            action_field = cand
            break

    feedback_field = None
    for cand in ("feedbacktext", "feedback_text", "feedback", "feedback_notes"):
        if meta.has_field(cand):
            feedback_field = cand
            break

    # inclusive window: today and previous N-1 days
    end_date = _to_date(now_datetime().date())
    start_date = add_days(end_date, -(int(days_back) - 1))

    where_site = ""
    params = [start_date, end_date]
    if site:
        where_site = f" AND wc.`{location_field}` = %s "
        params.append(site)

    rows = frappe.db.sql(
        f"""
        SELECT
            wc.name AS wearcheck_result,
            wc.`{asset_field}` AS asset,
            wc.`{location_field}` AS location,
            wc.`{status_field}` AS status,
            wc.`{register_field}` AS register_date,
            {f"wc.`{sample_field}` AS sample_date" if sample_field else "NULL AS sample_date"},
            {f"wc.`{component_field}` AS component" if component_field else "NULL AS component"},
            {f"wc.`{action_field}` AS action_text" if action_field else "NULL AS action_text"},
            {f"wc.`{feedback_field}` AS feedback_text" if feedback_field else "NULL AS feedback_text"},
            wc.creation AS creation
        FROM `tabWearCheck Results` wc
        WHERE wc.`{asset_field}` IS NOT NULL
          AND wc.`{asset_field}` != ''
          AND wc.`{register_field}` BETWEEN %s AND %s
          AND wc.`{status_field}` IN (3,4)
          {where_site}
        ORDER BY
          wc.`{asset_field}` ASC,
          {f"wc.`{component_field}` ASC," if component_field else ""}
          wc.`{status_field}` DESC,
          wc.`{register_field}` DESC,
          wc.creation DESC
        """,
        tuple(params),
        as_dict=True,
    ) or []

    best: dict[tuple[str, str], dict] = {}
    for r in rows:
        a = (r.get("asset") or "").strip()
        if not a:
            continue

        c = (r.get("component") or "").strip() if component_field else ""
        key = (a, c)

        if key not in best:
            best[key] = r
            continue

        cur = best[key]
        rs = int(r.get("status") or 0)
        cs = int(cur.get("status") or 0)

        if rs > cs:
            best[key] = r
            continue

        if rs == cs:
            rd = r.get("register_date") or ""
            cd = cur.get("register_date") or ""
            if rd > cd:
                best[key] = r
                continue
            if rd == cd:
                if (r.get("creation") or "") > (cur.get("creation") or ""):
                    best[key] = r

    out = list(best.values())
    out.sort(
        key=lambda x: (
            (x.get("asset") or ""),
            (x.get("component") or ""),
            -int(x.get("status") or 0),
            str(x.get("register_date") or ""),
            str(x.get("creation") or ""),
        )
    )
    return out


def _populate_wearcheck_snapshot(pe_doc: Document, site: str | None, days_back: int = 10):
    """
    Writes snapshot rows into the PE Table field that points to 'Sample Efficiency Child'.
    Child fields: asset,status,register_date,sample_date,component,wearcheck_result,action_text,feedback_text
    """

    # 1) find the PE table fieldname (don't assume it)
    table_field = None
    if pe_doc.meta.has_field("wearcheck_snapshot"):
        table_field = "wearcheck_snapshot"
    else:
        for df in (pe_doc.meta.fields or []):
            if df.fieldtype == "Table" and (df.options or "").strip() == "Sample Efficiency Child":
                table_field = df.fieldname
                break

    if not table_field:
        return

    # 2) populate
    pe_doc.set(table_field, [])

    rows = _fetch_wearcheck_flagged_window(site, days_back=days_back)

    for r in (rows or []):
        row = pe_doc.append(table_field, {})
        row.set("asset", r.get("asset"))
        row.set("status", str(int(r.get("status") or 0)))
        row.set("register_date", r.get("register_date"))
        row.set("sample_date", r.get("sample_date"))
        row.set("component", r.get("component"))
        row.set("wearcheck_result", r.get("wearcheck_result"))
        row.set("action_text", r.get("action_text"))
        row.set("feedback_text", r.get("feedback_text"))



@frappe.whitelist()
def get_latest_wearcheck_statuses(site: str | None = None) -> dict:
    """
    Latest WearCheck Results per Asset (machine), filtered by Location if provided.
    Only returns rows where the LATEST status for that asset is 3 or 4.

    Output:
      { "status_3": [...], "status_4": [...] }
    """
    site = (site or "").strip() or None

    meta = frappe.get_meta("WearCheck Results")

    # Always-present fields (from your console): asset, location, status
    asset_field = "asset"
    location_field = "location"
    status_field = "status"

    # Detect optional fields safely
    sample_field = None
    for cand in ("sampledate", "sample_date", "sample_date_", "sample_datetime", "sample_dt"):
        if meta.has_field(cand):
            sample_field = cand
            break

    component_field = "component" if meta.has_field("component") else None

    action_field = None
    for cand in ("actiontext", "action_text", "action", "action_taken", "action_required"):
        if meta.has_field(cand):
            action_field = cand
            break

    feedback_field = None
    for cand in ("feedbacktext", "feedback_text", "feedback", "feedback_notes"):
        if meta.has_field(cand):
            feedback_field = cand
            break

    # Inner select: real table columns -> stable aliases used by JS
    inner_cols = [
        f"`{asset_field}` AS machine",
        f"`{location_field}` AS location",
        f"`{status_field}` AS status",
        (f"`{sample_field}` AS sampledate" if sample_field else "NULL AS sampledate"),
        (f"`{component_field}` AS component" if component_field else "NULL AS component"),
        (f"`{action_field}` AS actiontext" if action_field else "NULL AS actiontext"),
        (f"`{feedback_field}` AS feedbacktext" if feedback_field else "NULL AS feedbacktext"),
    ]

    # Outer select: only the aliases from the subquery (NOT raw columns)
    outer_cols = ["machine", "location", "status", "sampledate", "component", "actiontext", "feedbacktext"]

    # "Latest" ordering within each asset
    order_expr = []
    if sample_field:
        order_expr.append(f"`{sample_field}` DESC")
    order_expr.append("creation DESC")
    order_by_latest = ", ".join(order_expr)

    where_site = ""
    params = []
    if site:
        where_site = f" AND `{location_field}` = %s "
        params.append(site)

    rows = frappe.db.sql(
        f"""
        SELECT
            {", ".join(outer_cols)}
        FROM (
            SELECT
                {", ".join(inner_cols)},
                ROW_NUMBER() OVER (
                    PARTITION BY `{asset_field}`
                    ORDER BY {order_by_latest}
                ) AS rn
            FROM `tabWearCheck Results`
            WHERE `{asset_field}` IS NOT NULL
              AND `{asset_field}` != ''
              {where_site}
        ) t
        WHERE t.rn = 1
          AND t.status IN (3, 4)
        ORDER BY t.status DESC, t.sampledate DESC, t.machine ASC
        """,
        tuple(params),
        as_dict=True,
    )

    out = {"status_3": [], "status_4": []}
    for r in (rows or []):
        try:
            st = int(r.get("status") or 0)
        except Exception:
            st = 0

        item = {
            "machine": r.get("machine"),
            "location": r.get("location"),
            "status": st,
            "sampledate": r.get("sampledate"),
            "component": r.get("component"),
            "actiontext": r.get("actiontext"),
            "feedbacktext": r.get("feedbacktext"),
        }

        if st == 3:
            out["status_3"].append(item)
        elif st == 4:
            out["status_4"].append(item)

    return out

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

        if doc.meta.has_field("production_excavators"):
            default_val = _get_hsc_production_excavators(site)
            if default_val and default_val > 0:
                doc.set("production_excavators", int(default_val))

        doc.insert(ignore_permissions=True)

    if doc.meta.has_field("site"):
        doc.site = site
    if doc.meta.has_field("start_date"):
        doc.start_date = start_date
    if doc.meta.has_field("end_date"):
        doc.end_date = end_date

    if doc.meta.has_field("production_excavators"):
        try:
            current_val = float(doc.get("production_excavators") or 0)
        except Exception:
            current_val = 0
        if current_val <= 0:
            default_val = _get_hsc_production_excavators(site)
            if default_val and default_val > 0:
                doc.set("production_excavators", int(default_val))

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
