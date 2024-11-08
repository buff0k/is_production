import frappe
from frappe.utils import flt, getdate
from collections import defaultdict

def get_daily_diesel_data(location, from_date, to_date, asset_name=None, display_type="Totals and Details"):
    from_date = getdate(from_date) if from_date else None
    to_date = getdate(to_date) if to_date else None

    filters = {'location': location, 'docstatus': 1}

    daily_diesel_data = frappe.db.get_all(
        'Daily Diesel Sheet',
        filters=filters,
        fields=['name', 'shift', 'daily_sheet_date'],
        order_by='daily_sheet_date ASC'
    )

    previous_hours_km = {}
    result = []
    asset_totals = defaultdict(lambda: {"litres_issued": 0, "hours_km_since_prev": 0})

    asset_details = []

    for sheet in daily_diesel_data:
        sheet_date = getdate(sheet['daily_sheet_date'])
        if (from_date and sheet_date < from_date) or (to_date and sheet_date > to_date):
            continue

        diesel_entry_filters = {'parent': sheet['name']}
        if asset_name:
            diesel_entry_filters['asset_name'] = asset_name

        diesel_entries = frappe.db.get_all(
            'Daily Diesel Entries',
            filters=diesel_entry_filters,
            fields=['asset_name', 'hours_km', 'litres_issued']
        )

        for entry in diesel_entries:
            asset_name_entry = entry['asset_name']
            current_hours_km = flt(entry['hours_km'])
            litres_issued = flt(entry['litres_issued'])
            item_name = frappe.db.get_value('Asset', asset_name_entry, 'item_name') or "Unknown"

            oem_consumption, fuel_tank_capacity = frappe.db.get_value(
                'Plant Technical Specification',
                {'item_name': item_name},
                ['oem_consumption', 'fuel_tank_capacity']
            ) or (None, None)

            # Calculate hours/km since previous entry, setting to 0 if no previous value exists
            if asset_name_entry in previous_hours_km:
                hours_km_since_prev = current_hours_km - previous_hours_km[asset_name_entry]
                hours_km_since_prev = hours_km_since_prev if hours_km_since_prev > 0 else 0
            else:
                # For the first entry, set hours_km_since_prev to 0
                hours_km_since_prev = 0

            actual_consumption = litres_issued / hours_km_since_prev if hours_km_since_prev > 0 else None

            # Update previous hours/km for this asset
            previous_hours_km[asset_name_entry] = current_hours_km

            if display_type == "Totals and Details":
                asset_details.append({
                    'date': sheet['daily_sheet_date'],
                    'shift': sheet['shift'],
                    'asset_name': asset_name_entry,
                    'item_name': item_name,
                    'hours_km': current_hours_km,
                    'hours_km_since_prev': hours_km_since_prev,
                    'litres_issued': litres_issued,
                    'actual_consumption': actual_consumption,
                    'oem_consumption': oem_consumption,
                    'fuel_tank_capacity': fuel_tank_capacity
                })

            asset_totals[asset_name_entry]["litres_issued"] += litres_issued
            asset_totals[asset_name_entry]["hours_km_since_prev"] += hours_km_since_prev

    # Add details and final total rows per asset
    for asset, totals in asset_totals.items():
        # Append all detail records for each asset
        result.extend([entry for entry in asset_details if entry['asset_name'] == asset])

        # Append a single total row per asset
        total_litres = totals["litres_issued"]
        total_hours_km_since_prev = totals["hours_km_since_prev"]
        total_actual_consumption = (
            total_litres / total_hours_km_since_prev if total_hours_km_since_prev > 0 else None
        )

        result.append({
            'date': f"Total for {asset}",
            'shift': "",
            'asset_name': asset,
            'item_name': "",
            'hours_km': None,
            'hours_km_since_prev': total_hours_km_since_prev,
            'litres_issued': total_litres,
            'actual_consumption': total_actual_consumption,
            'oem_consumption': None,
            'fuel_tank_capacity': None
        })

    return result

def execute(filters=None):
    # Define columns for the report
    columns = [
        {"label": "Date", "fieldname": "date", "fieldtype": "Data", "width": 120},
        {"label": "Shift", "fieldname": "shift", "fieldtype": "Data", "width": 80},
        {"label": "Asset Name", "fieldname": "asset_name", "fieldtype": "Link", "options": "Asset", "width": 150},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 150},
        {"label": "Hours/Km", "fieldname": "hours_km", "fieldtype": "Float", "width": 100},
        {"label": "Hours/Km Since Previous", "fieldname": "hours_km_since_prev", "fieldtype": "Float", "width": 150},
        {"label": "Litres Issued", "fieldname": "litres_issued", "fieldtype": "Float", "width": 120},
        {"label": "Actual Consumption", "fieldname": "actual_consumption", "fieldtype": "Float", "width": 150},
        {"label": "OEM Consumption", "fieldname": "oem_consumption", "fieldtype": "Float", "width": 120},
        {"label": "Fuel Tank Capacity", "fieldname": "fuel_tank_capacity", "fieldtype": "Float", "width": 150},
    ]

    # Fetch data based on filters for location, date range, asset name, and display type
    data = get_daily_diesel_data(
        filters.get("location"),
        filters.get("from_date"),
        filters.get("to_date"),
        filters.get("asset_name"),
        filters.get("display_type", "Totals and Details")
    )

    return columns, data
