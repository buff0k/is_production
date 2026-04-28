import frappe
from frappe.model.document import Document


class RentalEquipment(Document):
    def validate(self):
        self.calculate_totals()

    def calculate_totals(self):
        calculate_hours_from_hr_meter(self)

        total_litres = 0
        first_start = 0
        last_stop = 0

        for row in self.rental_equipment_logs:
            start = flt(row.start)
            stop = flt(row.stop)
            hours = flt(row.hours)
            litres = get_row_litres(row)

            row.total = stop - start

            if hours:
                row.lhr = litres / hours
            else:
                row.lhr = 0

            total_litres += litres

            if not first_start and start:
                first_start = start

            if stop:
                last_stop = stop

        self.start_hrs = first_start
        self.closing_hrs = last_stop

        if first_start and last_stop:
            self.total_hrs = last_stop - first_start
        else:
            self.total_hrs = 0

        self.total_litres = total_litres

        if self.total_hrs:
            self.average_lhr = total_litres / self.total_hrs
        else:
            self.average_lhr = 0


@frappe.whitelist()
def populate_rental_equipment_logs(docname):
    doc = frappe.get_doc("Rental Equipment", docname)

    if not doc.site:
        frappe.throw("Please select Site first.")

    if not doc.plant_number:
        frappe.throw("Please select Plant Number first.")

    if not doc.shift:
        frappe.throw("Please select Shift first.")

    if not doc.rental_equipment_logs:
        frappe.throw("Please generate month rows first.")

    shift_filter = get_shift_filter(doc.shift)

    for row in doc.rental_equipment_logs:
        if not row.date:
            continue

        pre_use_data = get_pre_use_data(
            site=doc.site,
            asset=doc.plant_number,
            log_date=row.date,
            shift_filter=shift_filter
        )

        diesel_data = get_daily_diesel_data(
            site=doc.site,
            asset=doc.plant_number,
            log_date=row.date,
            shift_filter=shift_filter
        )

        row.start = pre_use_data.get("start") or 0
        row.stop = pre_use_data.get("stop") or 0

        # Hr Meter comes from Daily Diesel Sheet > Daily Diesel Entries > Hours/Km.
        row.hr_meter = diesel_data.get("hr_meter") or 0

        set_row_litres(row, diesel_data.get("litres") or 0)

        # Do not auto-fill comment.
        # User will enter comments manually.
        # Existing user comments are not changed.

    calculate_hours_from_hr_meter(doc)
    doc.calculate_totals()
    doc.save(ignore_permissions=True)

    return "Rental Equipment Logs populated successfully."


def get_shift_filter(selected_shift):
    """
    Rental Equipment shift values:
        Day Shift
        Night Shift
        Both Shifts

    Source document shift values:
        Day
        Night

    If Both Shifts is selected, return None so the code uses all shifts.
    """

    if selected_shift == "Day Shift":
        return ["Day"]

    if selected_shift == "Night Shift":
        return ["Night"]

    return None


def calculate_hours_from_hr_meter(doc):
    """
    Hours calculation:
    - First captured Hr Meter:
        Hours = Hr Meter - Last re-Fueling Hr Meter
    - Following captured Hr Meter:
        Hours = Current Hr Meter - Previous captured Hr Meter

    If a row has no Hr Meter, Hours becomes 0 and previous Hr Meter is not changed.
    """

    previous_hr_meter = flt(doc.last_refueling_hr_meter)

    for row in doc.rental_equipment_logs:
        current_hr_meter = flt(row.hr_meter)

        if current_hr_meter:
            row.hours = current_hr_meter - previous_hr_meter

            if row.hours < 0:
                row.hours = 0

            previous_hr_meter = current_hr_meter
        else:
            row.hours = 0

        litres = get_row_litres(row)

        if row.hours:
            row.lhr = litres / row.hours
        else:
            row.lhr = 0


def get_pre_use_data(site, asset, log_date, shift_filter=None):
    """
    Gets Start and Stop from Pre-Use Hours.

    Parent DocType:
        Pre-Use Hours

    Parent fields:
        location
        shift_date
        shift

    Child DocType:
        Pre-use Assets

    Child fields:
        asset_name
        eng_hrs_start
        eng_hrs_end
    """

    parent_filters = {
        "location": site,
        "shift_date": log_date
    }

    if shift_filter:
        parent_filters["shift"] = ["in", shift_filter]

    pre_use_docs = frappe.get_all(
        "Pre-Use Hours",
        filters=parent_filters,
        pluck="name"
    )

    if not pre_use_docs:
        return {
            "found": False,
            "start": 0,
            "stop": 0
        }

    rows = frappe.get_all(
        "Pre-use Assets",
        filters={
            "parent": ["in", pre_use_docs],
            "parenttype": "Pre-Use Hours",
            "asset_name": asset
        },
        fields=[
            "asset_name",
            "eng_hrs_start",
            "eng_hrs_end"
        ]
    )

    if not rows:
        return {
            "found": False,
            "start": 0,
            "stop": 0
        }

    start_values = []
    stop_values = []

    for row in rows:
        start = flt(row.get("eng_hrs_start"))
        stop = flt(row.get("eng_hrs_end"))

        if start:
            start_values.append(start)

        if stop:
            stop_values.append(stop)

    min_start = min(start_values) if start_values else 0
    max_stop = max(stop_values) if stop_values else 0

    return {
        "found": True,
        "start": min_start,
        "stop": max_stop
    }


def get_daily_diesel_data(site, asset, log_date, shift_filter=None):
    """
    Gets litres and Hr Meter from Daily Diesel Sheet.

    Parent DocType:
        Daily Diesel Sheet

    Parent fields:
        location
        daily_sheet_date
        shift

    Child DocType:
        Daily Diesel Entries

    Child fields:
        asset_name
        hours_km
        litres_issued

    Shift logic:
        Day Shift   = only Day shift diesel records
        Night Shift = only Night shift diesel records
        Both Shifts = all shifts, with Hr Meter priority Night then Day
    """

    parent_filters = {
        "location": site,
        "daily_sheet_date": log_date
    }

    if shift_filter:
        parent_filters["shift"] = ["in", shift_filter]

    diesel_docs = frappe.get_all(
        "Daily Diesel Sheet",
        filters=parent_filters,
        fields=[
            "name",
            "shift"
        ]
    )

    if not diesel_docs:
        return {
            "litres": 0,
            "hr_meter": 0
        }

    parent_names = [d.name for d in diesel_docs]
    parent_shift_map = {d.name: d.shift for d in diesel_docs}

    rows = frappe.get_all(
        "Daily Diesel Entries",
        filters={
            "parent": ["in", parent_names],
            "parenttype": "Daily Diesel Sheet",
            "asset_name": asset
        },
        fields=[
            "parent",
            "asset_name",
            "hours_km",
            "litres_issued"
        ]
    )

    if not rows:
        return {
            "litres": 0,
            "hr_meter": 0
        }

    total_litres = 0
    night_hr_meter_values = []
    day_hr_meter_values = []
    other_hr_meter_values = []

    for row in rows:
        shift = parent_shift_map.get(row.get("parent"))
        hr_meter = flt(row.get("hours_km"))
        litres = flt(row.get("litres_issued"))

        total_litres += litres

        if hr_meter:
            if shift == "Night":
                night_hr_meter_values.append(hr_meter)
            elif shift == "Day":
                day_hr_meter_values.append(hr_meter)
            else:
                other_hr_meter_values.append(hr_meter)

    if night_hr_meter_values:
        hr_meter = max(night_hr_meter_values)
    elif day_hr_meter_values:
        hr_meter = max(day_hr_meter_values)
    elif other_hr_meter_values:
        hr_meter = max(other_hr_meter_values)
    else:
        hr_meter = 0

    return {
        "litres": total_litres,
        "hr_meter": hr_meter
    }


def get_row_litres(row):
    if hasattr(row, "litres"):
        return flt(row.litres)

    if hasattr(row, "liter"):
        return flt(row.liter)

    return 0


def set_row_litres(row, value):
    if hasattr(row, "litres"):
        row.litres = flt(value)
        return

    if hasattr(row, "liter"):
        row.liter = flt(value)
        return


def flt(value):
    try:
        if value is None:
            return 0

        value = str(value)
        value = value.replace(" ", "")
        value = value.replace(",", "")

        return float(value or 0)
    except Exception:
        return 0
