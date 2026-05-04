import json
import re
import frappe


def execute(filters=None):
    filters = frappe._dict(filters or {})

    dashboard = build_dashboard_data(filters)

    columns = [
        {
            "label": "Dashboard JSON",
            "fieldname": "dashboard_json",
            "fieldtype": "Long Text",
            "width": 300,
        }
    ]

    data = [
        {
            "dashboard_json": json.dumps(dashboard, default=str)
        }
    ]

    return columns, data


def build_dashboard_data(filters):
    weekly_report = run_script_report_direct(
        "weekly_report",
        {
            "start_date": filters.get("start_date"),
            "end_date": filters.get("end_date"),
            "site": filters.get("site"),
        },
    )

    diesel_report = run_script_report_direct(
        "diesel_cap_report",
        {
            "start_date": filters.get("start_date"),
            "end_date": filters.get("end_date"),
            "site": filters.get("site"),
        },
    )

    availability_report = run_script_report_direct(
        "avail_and_util_summary",
        {
            "start_date": filters.get("start_date"),
            "end_date": filters.get("end_date"),
            "location": filters.get("site"),
        },
    )

    weekly_rows = extract_rows_from_report_result(weekly_report)
    diesel_rows = extract_rows_from_report_result(diesel_report)
    availability_rows = extract_rows_from_report_result(availability_report)

    bcm = extract_bcm_data(weekly_rows)
    coal = extract_coal_data(weekly_rows)
    diesel = extract_diesel_data(diesel_rows)
    equipment = extract_equipment_data(availability_rows)

    return {
        "filters": {
            "start_date": filters.get("start_date"),
            "end_date": filters.get("end_date"),
            "site": filters.get("site"),
        },
        "bcm": bcm,
        "coal": coal,
        "diesel": diesel,
        "equipment": equipment,
        "debug": {
            "weekly_report_error": weekly_report.get("error"),
            "diesel_report_error": diesel_report.get("error"),
            "availability_report_error": availability_report.get("error"),
            "weekly_rows": weekly_rows,
            "diesel_rows": diesel_rows,
            "availability_rows": availability_rows,
            "weekly_html_found": bool(weekly_report.get("html")),
            "diesel_html_found": bool(diesel_report.get("html")),
            "availability_html_found": bool(availability_report.get("html")),
        },
    }


def run_script_report_direct(report_folder, filters):
    try:
        method_path = (
            "is_production.production.report."
            f"{report_folder}.{report_folder}.execute"
        )

        execute_method = frappe.get_attr(method_path)
        result = execute_method(frappe._dict(filters or {}))

        columns = []
        data = []
        html = ""

        if isinstance(result, tuple):
            if len(result) >= 1:
                columns = result[0] or []
            if len(result) >= 2:
                data = result[1] or []
            if len(result) >= 3 and isinstance(result[2], str):
                html = result[2] or ""
        elif isinstance(result, dict):
            columns = result.get("columns") or []
            data = result.get("data") or result.get("result") or []
            html = result.get("html") or result.get("message") or ""

        return {
            "columns": columns,
            "data": data,
            "html": html,
            "error": None,
        }

    except Exception:
        frappe.log_error(
            title=f"Weekly Production Dashboard failed on {report_folder}",
            message=frappe.get_traceback(),
        )

        return {
            "columns": [],
            "data": [],
            "html": "",
            "error": frappe.get_traceback(),
        }


def extract_rows_from_report_result(report):
    html = report.get("html") or ""

    if html:
        html_rows = extract_rows_from_html(html)
        if html_rows:
            return html_rows

    return normalise_rows(
        report.get("columns", []),
        report.get("data", []),
    )


def extract_rows_from_html(html):
    rows = []

    tr_matches = re.findall(
        r"<tr[^>]*>(.*?)</tr>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    for tr_html in tr_matches:
        cells = re.findall(
            r"<t[dh][^>]*>(.*?)</t[dh]>",
            tr_html,
            flags=re.IGNORECASE | re.DOTALL,
        )

        if len(cells) < 3:
            continue

        description = clean_html(cells[0])
        unit = clean_html(cells[1])
        value = clean_html(cells[2])

        if not description or description.lower() == "description":
            continue

        rows.append(
            {
                "description": description,
                "unit": unit,
                "value": value,
                "col_0": description,
                "col_1": unit,
                "col_2": value,
                "_raw": {
                    "description": description,
                    "unit": unit,
                    "value": value,
                },
            }
        )

    return rows


def clean_html(value):
    value = str(value or "")

    value = re.sub(
        r"<br\s*/?>",
        " ",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"<[^>]+>",
        "",
        value,
        flags=re.IGNORECASE | re.DOTALL,
    )

    value = value.replace("&nbsp;", " ")
    value = value.replace("&amp;", "&")
    value = value.replace("&#39;", "'")
    value = value.replace("&quot;", '"')
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def normalise_rows(columns, data):
    normalised_columns = [get_column_fieldname(col) for col in columns or []]
    rows = []

    for row in data or []:
        item = {}

        if isinstance(row, dict):
            for key, value in row.items():
                item[key] = value
                item[normalise_key(key)] = value
        elif isinstance(row, (list, tuple)):
            for index, value in enumerate(row):
                if index < len(normalised_columns):
                    key = normalised_columns[index]
                    if key:
                        item[key] = value
                        item[normalise_key(key)] = value

                item[f"col_{index}"] = value
        else:
            item["value"] = row

        item["_raw"] = row
        rows.append(item)

    return rows


def get_column_fieldname(column):
    if not column:
        return ""

    if isinstance(column, str):
        return column.split(":")[0].strip()

    if isinstance(column, dict):
        return (
            column.get("fieldname")
            or column.get("field")
            or column.get("label")
            or column.get("name")
            or ""
        )

    return ""


def normalise_key(value):
    value = str(value or "").lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value


def as_float(value):
    if value is None:
        return 0

    if isinstance(value, (int, float)):
        return float(value)

    value = str(value)
    value = clean_html(value)
    value = value.replace(",", "")
    value = value.replace("%", "")
    value = value.replace("−", "-")
    value = value.strip()

    if not value:
        return 0

    try:
        return float(value)
    except Exception:
        return 0


def get_value(row, keys):
    for key in keys:
        if key in row and row.get(key) not in [None, ""]:
            return row.get(key)

        normalised = normalise_key(key)
        if normalised in row and row.get(normalised) not in [None, ""]:
            return row.get(normalised)

    return None


def get_description(row):
    value = get_value(
        row,
        [
            "description",
            "descripition",
            "particulars",
            "item",
            "label",
            "metric",
            "col_0",
        ],
    )

    return str(value or "").strip()


def get_unit(row):
    value = get_value(
        row,
        [
            "unit",
            "uom",
            "col_1",
        ],
    )

    return str(value or "").strip()


def get_report_value(row):
    value = get_value(
        row,
        [
            "value",
            "amount",
            "total",
            "qty",
            "quantity",
            "col_2",
        ],
    )

    return as_float(value)


def find_report_value(rows, description_keywords, unit_keywords=None, exclude_keywords=None):
    unit_keywords = unit_keywords or []
    exclude_keywords = exclude_keywords or []

    for row in rows:
        description = get_description(row).lower()
        unit = get_unit(row).lower()

        if not description:
            continue

        if any(keyword.lower() in description for keyword in exclude_keywords):
            continue

        description_match = all(
            keyword.lower() in description
            for keyword in description_keywords
        )

        if not description_match:
            continue

        if unit_keywords:
            unit_match = any(
                keyword.lower() in unit
                for keyword in unit_keywords
            )

            if not unit_match:
                continue

        return get_report_value(row)

    return 0


def extract_bcm_data(rows):
    target = find_report_value(
        rows,
        ["monthly", "target"],
        ["bcm"],
        exclude_keywords=["waste", "coal"],
    )

    actual = find_report_value(
        rows,
        ["mtd", "prog", "actual", "bcm"],
        ["bcm"],
        exclude_keywords=["coal"],
    )

    if not actual:
        actual = find_report_value(
            rows,
            ["mtd", "prog", "actual", "waste"],
            ["bcm"],
            exclude_keywords=["coal"],
        )

    if not actual:
        actual = find_report_value(
            rows,
            ["actual", "bcm"],
            ["bcm"],
            exclude_keywords=["coal"],
        )

    remaining_positive = find_report_value(
        rows,
        ["remaining", "volume"],
        ["bcm"],
    )

    if not remaining_positive and target:
        remaining_positive = target - actual

    remaining = actual - target
    progress = (actual / target * 100) if target else 0

    return {
        "target": target,
        "actual": actual,
        "remaining": remaining,
        "remaining_positive": remaining_positive,
        "progress": progress,
    }


def extract_coal_data(rows):
    target = find_report_value(
        rows,
        ["monthly", "coal", "target"],
        ["tons"],
    )

    actual = find_report_value(
        rows,
        ["mtd", "prog", "actual", "coal"],
        ["tons"],
    )

    if not actual:
        actual = find_report_value(
            rows,
            ["actual", "coal"],
            ["tons"],
        )

    remaining_positive = find_report_value(
        rows,
        ["remaining", "coal"],
        ["tons"],
    )

    if not remaining_positive and target:
        remaining_positive = target - actual

    remaining = actual - target
    progress = (actual / target * 100) if target else 0

    return {
        "target": target,
        "actual": actual,
        "remaining": remaining,
        "remaining_positive": remaining_positive,
        "progress": progress,
    }


def extract_diesel_data(rows):
    usage = 0
    cap = 0

    for row in rows:
        usage_candidate = get_value(
            row,
            [
                "total_diesel_litres",
                "total_diesel_liters",
                "total_diesel_ltrs",
                "total_diesel",
                "diesel_litres",
                "diesel_liters",
                "diesel_ltrs",
                "diesel_usage",
                "diesel_used",
                "mtd_diesel",
                "month_to_date_diesel",
                "fuel_used",
                "litres",
                "liters",
                "total_litres",
                "total_liters",
            ],
        )

        if usage_candidate not in [None, ""]:
            usage = as_float(usage_candidate)

        cap_candidate = get_value(
            row,
            [
                "diesel_cap",
                "cap",
                "diesel_cap_ratio",
                "litres_per_bcm",
                "liters_per_bcm",
                "l_per_bcm",
                "l_bcm",
                "ltrs_per_bcm",
                "fuel_cap",
            ],
        )

        if cap_candidate not in [None, ""]:
            cap = as_float(cap_candidate)

    if not usage:
        usage = find_report_value(
            rows,
            ["diesel"],
            [],
            exclude_keywords=["cap"],
        )

    if not cap:
        cap = find_report_value(
            rows,
            ["cap"],
            [],
        )

    return {
        "usage": usage,
        "cap": cap,
    }


def extract_equipment_data(rows):
    result = []

    equipment_map = [
        {
            "label": "ADT",
            "matches": ["adt"],
        },
        {
            "label": "Dozer's",
            "matches": ["dozer", "dozers", "dozer's"],
        },
        {
            "label": "Excavator's",
            "matches": ["excavator", "excavators", "excavator's"],
        },
    ]

    for equipment_config in equipment_map:
        matched_row = find_equipment_summary_row(
            rows,
            equipment_config["matches"],
        )

        availability = 0
        utilisation = 0

        if matched_row:
            availability = as_float(
                get_value(
                    matched_row,
                    [
                        "plant_shift_availability",
                        "avail",
                        "avail_",
                        "availability",
                        "availability_percentage",
                    ],
                )
            )

            utilisation = as_float(
                get_value(
                    matched_row,
                    [
                        "plant_shift_utilisation",
                        "plant_shift_utilization",
                        "util",
                        "util_",
                        "utilisation",
                        "utilization",
                        "utt",
                        "utilisation_percentage",
                        "utilization_percentage",
                    ],
                )
            )

        result.append(
            {
                "equipment": equipment_config["label"],
                "availability": availability,
                "utilisation": utilisation,
            }
        )

    return result


def find_equipment_summary_row(rows, matches):
    for row in rows:
        label = get_equipment_label(row)

        if not label:
            continue

        cleaned_label = clean_equipment_label(label)

        for match in matches:
            if cleaned_label == clean_equipment_label(match):
                return row

    return None


def get_equipment_label(row):
    possible_values = [
        get_value(row, ["asset"]),
        get_value(row, ["asset_name"]),
        get_value(row, ["equipment"]),
        get_value(row, ["equipment_type"]),
        get_value(row, ["machine_type"]),
        get_value(row, ["asset_category"]),
        get_value(row, ["category"]),
        get_value(row, ["plant_type"]),
        get_value(row, ["type"]),
        get_value(row, ["asset_type"]),
        get_value(row, ["fleet_type"]),
        get_value(row, ["description"]),
        get_value(row, ["col_0"]),
    ]

    for value in possible_values:
        if value not in [None, ""]:
            return str(value).strip()

    return ""


def clean_equipment_label(value):
    value = str(value or "").strip().lower()
    value = value.replace("'", "")
    value = value.replace("’", "")
    value = value.replace(">", "")
    value = value.strip()
    return value