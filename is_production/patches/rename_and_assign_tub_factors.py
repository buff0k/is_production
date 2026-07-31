# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.rename_doc import rename_doc
from frappe.utils import cint, now_datetime


TUB_FACTOR_DOCTYPE = "Tub Factor"
TUB_FACTOR_CHILD_DOCTYPE = "Monthly Production Tub Factor"
MPP_DOCTYPE = "Monthly Production Planning"
TRUCK_LOADS_DOCTYPE = "Truck Loads"
HOURLY_PRODUCTION_DOCTYPE = "Hourly Production"


_ITEM_LINK_CACHE = {}


def execute():
    """
    Migrate Tub Factors to immutable names and reconstruct all historic MPP
    approvals without collapsing multiple factors for the same model/material.

    Historic Truck Loads remain unchanged except for repairing the Link field.
    """
    _assert_required_schema()
    frappe.flags.in_patch = True

    rename_map = _rename_existing_tub_factors()
    frappe.db.commit()

    factor_map = _ensure_historic_factor_definitions()
    factor_map.update(_get_factor_map())
    frappe.db.commit()

    _repair_known_link_references(rename_map)
    _repair_truck_load_links()
    frappe.db.commit()

    _backfill_monthly_production_tub_factors(factor_map)
    frappe.db.commit()

    _submit_tub_factors()
    frappe.db.commit()


def _assert_required_schema():
    required_doctypes = [
        TUB_FACTOR_DOCTYPE,
        MPP_DOCTYPE,
        TUB_FACTOR_CHILD_DOCTYPE,
        TRUCK_LOADS_DOCTYPE,
        HOURLY_PRODUCTION_DOCTYPE,
    ]

    missing = [
        doctype for doctype in required_doctypes
        if not frappe.db.exists("DocType", doctype)
    ]
    if missing:
        frappe.throw(
            _("Missing required DocTypes: {0}").format(", ".join(missing))
        )

    required_fields = [
        (MPP_DOCTYPE, "tub_factors"),
        (TUB_FACTOR_CHILD_DOCTYPE, "tub_factor"),
        (TUB_FACTOR_CHILD_DOCTYPE, "item_name"),
        (TUB_FACTOR_CHILD_DOCTYPE, "mat_type"),
        (TUB_FACTOR_CHILD_DOCTYPE, "factor_value"),
        (TRUCK_LOADS_DOCTYPE, "tub_factor_doc_link"),
        (TRUCK_LOADS_DOCTYPE, "item_name"),
        (TRUCK_LOADS_DOCTYPE, "mat_type"),
        (TRUCK_LOADS_DOCTYPE, "tub_factor"),
        (HOURLY_PRODUCTION_DOCTYPE, "month_prod_planning"),
    ]

    missing_fields = [
        f"{doctype}.{fieldname}"
        for doctype, fieldname in required_fields
        if not frappe.get_meta(doctype).has_field(fieldname)
    ]
    if missing_fields:
        frappe.throw(
            _("Missing required fields: {0}").format(", ".join(missing_fields))
        )


def _resolve_item_link(value):
    """Resolve legacy Truck Loads values to the actual Item document name.

    Historic rows may contain Item.item_name (for example ``KOMATSU``) while
    Link fields must contain Item.name / item_code (for example ``HM400``).
    Exact Item names always take precedence. A descriptive Item Name is only
    accepted when it resolves to exactly one Item.
    """
    value = str(value or "").strip()
    if not value:
        return value

    if value in _ITEM_LINK_CACHE:
        return _ITEM_LINK_CACHE[value]

    if frappe.db.exists("Item", value):
        _ITEM_LINK_CACHE[value] = value
        return value

    matches = frappe.get_all(
        "Item",
        filters={"item_name": value},
        pluck="name",
        order_by="name asc",
        limit_page_length=2,
    )

    if len(matches) == 1:
        _ITEM_LINK_CACHE[value] = matches[0]
        return matches[0]

    if len(matches) > 1:
        frappe.throw(
            _(
                "Cannot resolve legacy Truck Model {0}: multiple Items use "
                "that Item Name ({1})."
            ).format(frappe.bold(value), ", ".join(matches)),
            title=_("Ambiguous Truck Model"),
        )

    frappe.throw(
        _("Cannot resolve legacy Truck Model {0} to an Item.").format(
            frappe.bold(value)
        ),
        title=_("Missing Truck Model Item"),
    )


def _canonical_name(item_name, mat_type, factor_value):
    item_name = _resolve_item_link(item_name)
    return (
        f"{item_name}-"
        f"{str(mat_type or '').strip()}-"
        f"{cint(factor_value)}"
    )


def _factor_key(item_name, mat_type, factor_value):
    return (
        _resolve_item_link(item_name),
        str(mat_type or "").strip(),
        cint(factor_value),
    )


def _rename_existing_tub_factors():
    records = frappe.get_all(
        TUB_FACTOR_DOCTYPE,
        fields=["name", "item_name", "mat_type", "tub_factor"],
        order_by="creation asc",
        limit_page_length=0,
    )

    proposed = {}
    rename_map = {}

    for record in records:
        if not record.item_name or not record.mat_type:
            frappe.throw(
                _("Tub Factor {0} is missing Truck Model or Material Type.")
                .format(frappe.bold(record.name))
            )
        if record.tub_factor in (None, ""):
            frappe.throw(
                _("Tub Factor {0} has no numeric value.")
                .format(frappe.bold(record.name))
            )

        target = _canonical_name(
            record.item_name, record.mat_type, record.tub_factor
        )
        other = proposed.get(target)
        if other and other != record.name:
            frappe.throw(
                _("Tub Factors {0} and {1} both resolve to {2}.")
                .format(other, record.name, target),
                title=_("Duplicate Tub Factor Definitions"),
            )
        proposed[target] = record.name

    for record in records:
        target = _canonical_name(
            record.item_name, record.mat_type, record.tub_factor
        )
        rename_map[record.name] = target

        if record.name == target:
            continue

        if frappe.db.exists(TUB_FACTOR_DOCTYPE, target):
            existing = frappe.db.get_value(
                TUB_FACTOR_DOCTYPE,
                target,
                ["item_name", "mat_type", "tub_factor"],
                as_dict=True,
            )
            if existing and _factor_key(
                existing.item_name, existing.mat_type, existing.tub_factor
            ) == _factor_key(
                record.item_name, record.mat_type, record.tub_factor
            ):
                _replace_factor_references(record.name, target)
                frappe.delete_doc(
                    TUB_FACTOR_DOCTYPE,
                    record.name,
                    ignore_permissions=True,
                    force=True,
                )
                continue

            frappe.throw(
                _("Cannot rename {0} to existing, different record {1}.")
                .format(record.name, target)
            )

        rename_doc(
            doctype=TUB_FACTOR_DOCTYPE,
            old=record.name,
            new=target,
            force=True,
            merge=False,
            ignore_permissions=True,
        )

    return rename_map


def _replace_factor_references(old_name, new_name):
    frappe.db.sql(
        """
        UPDATE `tabTruck Loads`
        SET tub_factor_doc_link = %s
        WHERE tub_factor_doc_link = %s
        """,
        (new_name, old_name),
    )
    frappe.db.sql(
        """
        UPDATE `tabMonthly Production Tub Factor`
        SET tub_factor = %s
        WHERE tub_factor = %s
        """,
        (new_name, old_name),
    )


def _get_factor_map():
    factors = frappe.get_all(
        TUB_FACTOR_DOCTYPE,
        fields=["name", "item_name", "mat_type", "tub_factor"],
        limit_page_length=0,
    )

    result = {}
    for factor in factors:
        key = _factor_key(
            factor.item_name, factor.mat_type, factor.tub_factor
        )
        if key in result and result[key] != factor.name:
            frappe.throw(
                _("Duplicate Tub Factor masters for {0}/{1}/{2}.")
                .format(*key)
            )
        result[key] = factor.name
    return result


def _get_historic_factor_definitions():
    return frappe.db.sql(
        """
        SELECT DISTINCT
            tl.item_name,
            tl.mat_type,
            tl.tub_factor
        FROM `tabTruck Loads` tl
        WHERE COALESCE(tl.item_name, '') != ''
          AND COALESCE(tl.mat_type, '') != ''
          AND COALESCE(tl.tub_factor, 0) > 0
        ORDER BY tl.item_name, tl.mat_type, tl.tub_factor
        """,
        as_dict=True,
    )


def _ensure_historic_factor_definitions():
    factor_map = _get_factor_map()

    for row in _get_historic_factor_definitions():
        key = _factor_key(row.item_name, row.mat_type, row.tub_factor)
        if key in factor_map:
            continue

        doc = frappe.get_doc({
            "doctype": TUB_FACTOR_DOCTYPE,
            "item_name": key[0],
            "mat_type": key[1],
            "tub_factor": key[2],
        })
        doc.flags.ignore_permissions = True
        doc.insert()
        factor_map[key] = doc.name

    return factor_map


def _repair_known_link_references(rename_map):
    for old_name, new_name in (rename_map or {}).items():
        if old_name == new_name:
            continue
        frappe.db.sql(
            """
            UPDATE `tabMonthly Production Tub Factor`
            SET tub_factor = %s
            WHERE tub_factor = %s
            """,
            (new_name, old_name),
        )


def _repair_truck_load_links():
    factor_map = _get_factor_map()
    rows = frappe.db.sql(
        """
        SELECT
            tl.name,
            tl.parent,
            tl.idx,
            tl.item_name,
            tl.mat_type,
            tl.tub_factor,
            tl.tub_factor_doc_link
        FROM `tabTruck Loads` tl
        WHERE COALESCE(tl.item_name, '') != ''
          AND COALESCE(tl.mat_type, '') != ''
          AND COALESCE(tl.tub_factor, 0) > 0
        ORDER BY tl.parent, tl.idx
        """,
        as_dict=True,
    )

    unresolved = []
    updates = []

    for row in rows:
        key = _factor_key(row.item_name, row.mat_type, row.tub_factor)
        factor_name = factor_map.get(key)

        if not factor_name:
            unresolved.append(row)
            if len(unresolved) >= 20:
                break
            continue

        if row.tub_factor_doc_link != factor_name:
            updates.append((factor_name, row.name))

    if unresolved:
        preview = "; ".join(
            f"{r.parent} row {r.idx}: "
            f"{r.item_name}/{r.mat_type}/{r.tub_factor}"
            for r in unresolved
        )
        frappe.throw(
            _("Historic Truck Loads could not be resolved: {0}").format(preview)
        )

    for idx, (factor_name, row_name) in enumerate(updates, start=1):
        frappe.db.set_value(
            TRUCK_LOADS_DOCTYPE,
            row_name,
            "tub_factor_doc_link",
            factor_name,
            update_modified=False,
        )

        if idx % 500 == 0:
            frappe.db.commit()


def _get_mpp_distinct_historic_factors(plan_name):
    """
    Preserve every distinct factor actually used under the MPP.

    The new MPP child table is an approved-options list, not a unique
    model/material mapping, so multiple values are valid.
    """
    return frappe.db.sql(
        """
        SELECT DISTINCT
            tl.item_name,
            tl.mat_type,
            tl.tub_factor
        FROM `tabHourly Production` hp
        INNER JOIN `tabTruck Loads` tl
            ON tl.parent = hp.name
           AND tl.parenttype = 'Hourly Production'
        WHERE hp.month_prod_planning = %s
          AND COALESCE(tl.item_name, '') != ''
          AND COALESCE(tl.mat_type, '') != ''
          AND COALESCE(tl.tub_factor, 0) > 0
        ORDER BY tl.item_name, tl.mat_type, tl.tub_factor
        """,
        (plan_name,),
        as_dict=True,
    )


def _backfill_monthly_production_tub_factors(factor_map):
    plans = frappe.get_all(
        MPP_DOCTYPE,
        pluck="name",
        order_by="creation asc",
        limit_page_length=0,
    )

    for plan_name in plans:
        historic_rows = _get_mpp_distinct_historic_factors(plan_name)
        if not historic_rows:
            continue

        values = []
        now = now_datetime()
        user = frappe.session.user or "Administrator"

        for idx, row in enumerate(historic_rows, start=1):
            key = _factor_key(
                row.item_name, row.mat_type, row.tub_factor
            )
            factor_name = factor_map.get(key)
            if not factor_name:
                frappe.throw(
                    _("No Tub Factor master for {0}/{1}/{2}.")
                    .format(*key)
                )

            values.append((
                frappe.generate_hash(length=10),
                now,
                now,
                user,
                user,
                0,
                idx,
                plan_name,
                "tub_factors",
                MPP_DOCTYPE,
                factor_name,
                key[0],
                key[1],
                key[2],
            ))

        frappe.db.sql(
            """
            DELETE FROM `tabMonthly Production Tub Factor`
            WHERE parent = %s
              AND parenttype = %s
              AND parentfield = 'tub_factors'
            """,
            (plan_name, MPP_DOCTYPE),
        )

        frappe.db.bulk_insert(
            TUB_FACTOR_CHILD_DOCTYPE,
            fields=[
                "name",
                "creation",
                "modified",
                "modified_by",
                "owner",
                "docstatus",
                "idx",
                "parent",
                "parentfield",
                "parenttype",
                "tub_factor",
                "item_name",
                "mat_type",
                "factor_value",
            ],
            values=values,
            chunk_size=500,
        )

        # Keep each MPP migration bounded and make reruns safe.
        frappe.db.commit()


def _submit_tub_factors():
    factors = frappe.get_all(
        TUB_FACTOR_DOCTYPE,
        filters={"docstatus": 0},
        pluck="name",
        order_by="creation asc",
        limit_page_length=0,
    )

    for idx, name in enumerate(factors, start=1):
        doc = frappe.get_doc(TUB_FACTOR_DOCTYPE, name)
        doc.flags.ignore_permissions = True
        doc.submit()

        if idx % 100 == 0:
            frappe.db.commit()

