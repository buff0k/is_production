# Helper: safe float conversion
def to_float(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0

# Helper: round to 1 decimal place
def r1(v):
    return round(to_float(v), 1)

# Force 1 decimal on opening & closing (store normalized values)
doc.opening_drilling_hrs = r1(doc.get("opening_drilling_hrs"))
doc.closing_drilling_hrs = r1(doc.get("closing_drilling_hrs"))

# Calculate total drilling hours (also 1 decimal)
doc.total_drilling_hrs = r1(doc.closing_drilling_hrs - doc.opening_drilling_hrs)

# Sum child table
total_meters = 0.0
total_holes = 0.0

for row in (doc.get("holes_and_meter") or []):
    total_meters += to_float(row.get("meters"))
    total_holes += to_float(row.get("no_of_holes"))

# Force 1 decimal on total_meters
doc.total_meters = r1(total_meters)

# Holes are normally whole numbers; keep as float-safe
doc.total_holes = total_holes