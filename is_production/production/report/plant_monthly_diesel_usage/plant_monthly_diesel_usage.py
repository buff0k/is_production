import frappe
from frappe.utils import flt, getdate  # Import getdate to convert strings to date objects

def execute(filters=None):
    # Define columns for the report
    columns = [
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 120},
        {"label": "Shift", "fieldname": "shift", "fieldtype": "Data", "width": 80},
        {"label": "Asset Name", "fieldname": "asset_name", "fieldtype": "Link", "options": "Asset", "width": 150},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 150},
        {"label": "Hours/Km", "fieldname": "hours_km", "fieldtype": "Float", "width": 100},
        {"label": "Hours/Km Since Previous", "fieldname": "hours_km_since_prev", "fieldtype": "Float", "width": 150},
        {"label": "Litres Issued", "fieldname": "litres_issued", "fieldtype": "Float", "width": 120},
        {"label": "Actual Consumption", "fieldname": "actual_consumption", "fieldtype": "Float", "width": 150},
    ]
    
    # Fetch data based on filters
    data = get_daily_diesel_data(filters.get("location"), filters.get("from_date"), filters.get("to_date"))
    
    return columns, data

def get_daily_diesel_data(location, from_date, to_date):
    # Convert from_date and to_date to date objects if they are provided
    from_date = getdate(from_date) if from_date else None
    to_date = getdate(to_date) if to_date else None
    
    # Query the Daily Diesel Sheet doctype with the location filter for all records (no date filter here)
    daily_diesel_data = frappe.db.get_all(
        'Daily Diesel Sheet',
        filters={'location': location, 'docstatus': 1},
        fields=['name', 'shift', 'daily_sheet_date'],
        order_by='daily_sheet_date ASC'
    )
    
    # Track previous hours_km for each asset to calculate hours_km_since_prev
    previous_hours_km = {}
    result = []
    
    for sheet in daily_diesel_data:
        # Convert daily_sheet_date to a date object for comparison
        sheet_date = getdate(sheet['daily_sheet_date'])
        
        # Fetch related entries from the daily_diesel_entries table
        diesel_entries = frappe.db.get_all(
            'Daily Diesel Entries',
            filters={'parent': sheet['name']},
            fields=['asset_name', 'hours_km', 'litres_issued']
        )
        
        # Combine the sheet and entries data
        for entry in diesel_entries:
            asset_name = entry['asset_name']
            current_hours_km = flt(entry['hours_km'])
            litres_issued = flt(entry['litres_issued'])
            
            # Get item_name from Asset doctype based on asset_name
            item_name = frappe.db.get_value('Asset', asset_name, 'item_name') or "Unknown"
            
            # Calculate hours_km_since_prev if there is a previous entry for the asset
            if asset_name in previous_hours_km:
                hours_km_since_prev = current_hours_km - flt(previous_hours_km[asset_name])
            else:
                hours_km_since_prev = None  # No previous entry available for calculation
            
            # Calculate actual consumption if hours_km_since_prev is available
            if hours_km_since_prev and hours_km_since_prev > 0:
                actual_consumption = litres_issued / hours_km_since_prev
            else:
                actual_consumption = None
            
            # Update previous_hours_km for the next calculation
            previous_hours_km[asset_name] = current_hours_km
            
            # Apply display filter: only add records within the from_date and to_date range
            if from_date <= sheet_date <= to_date:
                result.append({
                    'date': sheet['daily_sheet_date'],
                    'shift': sheet['shift'],
                    'asset_name': asset_name,
                    'item_name': item_name,
                    'hours_km': current_hours_km,
                    'hours_km_since_prev': hours_km_since_prev,
                    'litres_issued': litres_issued,
                    'actual_consumption': actual_consumption
                })
    
    return result
