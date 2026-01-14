import frappe
import json
from frappe.desk.query_report import get_prepared_report_result


@frappe.whitelist()
def get_latest_sites_from_prepared_report():
    """
    Get Site values from the newest Completed Prepared Report
    for HO-DB-0001 (Frappe 15.96 correct usage)
    """

    # 1. Get newest prepared report name
    pr = frappe.get_all(
        "Prepared Report",
        filters={
            "report_name": "HO-DB-0001",
            "status": "Completed"
        },
        fields=["name", "filters"],
        order_by="creation desc",
        limit=1
    )

    if not pr:
        return []

    prepared_report_name = pr[0].name

    # 2. Load Prepared Report document (IMPORTANT)
    prepared_report = frappe.get_doc("Prepared Report", prepared_report_name)

    # 3. Parse stored filters
    filters = {}
    if prepared_report.filters:
        filters = json.loads(prepared_report.filters)

    # 4. Call internal engine with DOCUMENT, not string
    result = get_prepared_report_result(prepared_report, filters)

    columns = result.get("columns") or []
    rows = result.get("result") or []

    # 5. Find Site column index
    site_index = None
    for i, col in enumerate(columns):
        if col.get("fieldname") == "site" or col.get("label") == "Site":
            site_index = i
            break

    if site_index is None:
        return []

    # 6. Extract Site values
    sites = []
    for row in rows:
        if len(row) > site_index and row[site_index]:
            sites.append(row[site_index])

    return sites
