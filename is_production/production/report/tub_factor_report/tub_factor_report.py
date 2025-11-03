import frappe

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    """Define report columns."""
    return [
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 160},
        {"label": "Material Type", "fieldname": "mat_type", "fieldtype": "Data", "width": 160},
        {"label": "TUB Factor", "fieldname": "tub_factor", "fieldtype": "Float", "precision": 2, "width": 120}
    ]


def get_data(filters):
    """Fetch filtered data from Tub Factor Doctype."""
    conditions = []
    values = {}

    if filters.get("item_name"):
        conditions.append("item_name = %(item_name)s")
        values["item_name"] = filters.get("item_name")

    if filters.get("mat_type"):
        conditions.append("mat_type = %(mat_type)s")
        values["mat_type"] = filters.get("mat_type")

    condition_str = " AND ".join(conditions)
    if condition_str:
        condition_str = "WHERE " + condition_str

    # ✅ Table name must match Doctype name exactly
    query = f"""
        SELECT
            item_name,
            mat_type,
            tub_factor
        FROM `tabTub Factor`
        {condition_str}
        ORDER BY item_name, mat_type
    """

    # Log to console for debugging
    print("Running query:", query)
    print("With filters:", values)

    data = frappe.db.sql(query, values=values, as_dict=True)
    return data
