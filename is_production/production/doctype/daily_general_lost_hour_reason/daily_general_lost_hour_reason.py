import frappe
from frappe.model.document import Document


class DailyGeneralLostHourReason(Document):
    pass


REASONS = {

    "Training Non Work Hours": [
        "Training scheduled learning activities that stop normal production.",
        "Induction or scheduled learning activities that stop normal production.",
    ],

    "Weather Conditions Non Work Hours": [
        "Weather- stoppages rain sliperery conditions.",
        "Weather- stoppages rain and lightning slippery conditions.",
        "Weather- stoppages fog/mist poor visibility.",
        "Weather- stoppages excessive wind/dust poor visibility.",
    ],

    "VFL Non Work Hours": [
        "Non-work time related to VFL activities.",
        "Non-work time related to VFL inspections.",
        "Non-work time related to VFL engagements.",
    ],

    "Other Non Work Hours": [
        "Any approved non-work time that does not fit another listed category.",
    ],

    "Dust and/or Water Bowser Lost Hours": [
        "Production time lost due to dust suppression requirements.",
        "Production time lost due to dust suppression water bowser availability / delays.",
    ],

    "Diesel and/or Diesel Bowser Lost Hours": [
        "Production time lost due to refuelling.",
        "Production time lost due to diesel availability delays.",
        "Production time lost due to diesel bowser delays.",
    ],

    "Blasting": [
        "Production time lost due to blasting clearance.",
        "Production time lost due to waiting for blasting to finish.",
        "Production time lost due to blasting evacuation.",
    ],

    "Safety Stoppage Lost Hours": [
        "Safety stand-downs.",
        "unsafe conditions.",
        "safety instructions.",
    ],

    "Pre-Shift / Toolbox Talk Lost Hours": [
        "Toolbox talks or extended pre-shift meetings.",
    ],

    "Shift Change Lost Hours": [
        "Delayed handover between Day shifts.",
        "Delayed handover between Night shifts.",
    ],

    "No Operator / Labour Lost Hours": [
        "Operator shortages.",
        "Absenteeism.",
        "Operator doing medical",
        "labour availability.",
    ],

    "Industrial Action Lost Hours": [
        "Strike.",
        "Work stoppage .",
        "labour-related interruption.",
    ],

    "Pit Access / Road Lost Hours": [
        "Haul road blocked.",
        "Long Hauling distance",
        "Short Hauling distance",
        "unsafe road.",
        "no access to loading area.",
    ],

    "Road Maintenance Lost Hours": [
        "Grading in pit.",
        "Grading haul road.",
        "maintenance preventing production.",
    ],

    "Dewatering / Water in Pit Lost Hours": [
        "Flooding.",
        "pumping .",
        "excessive water preventing mining.",
    ],

    "Survey Lost Hours": [
        "Waiting for survey clearance.",
        "Waiting for survey finish measurements.",
        "Waiting for survey markings.",
    ],

    "Geology Lost Hours": [
        "Waiting for geological identification .",
        "Waiting for geological instructions.",
    ],

    "Mining Permit / Clearance Lost Hours": [
        "Waiting for Permit.",
        "Witing for authorisation .",
        "Waiting for area-release.",
    ],

    "Bench / Face Preparation Lost Hours": [
        "Preparing loading face",
        "Preparing Catchment beam",
        "Preparing safety beam",
        "Preparing loading bench",
        "Cleanup or preparation required.",
    ],

    "Crusher / Tip / Dump Lost Hours": [
        "Tipping area unavailable.",
        "Loading material unavailable.",
        "Dumping area unavailable.",
    ],

    "Traffic / Congestion Lost Hours": [
        "Queuing at Loading area.",
        "congestion affecting hauling.",
    ],

    "Power Failure Lost Hours": [
        "Electrical supply failure affecting operations.",
    ],

    "Communication / System Lost Hours": [
        "two way radio system failure.",
        "Network",
        "ERP or dispatch system failure.",
    ],

    "Community / External Stoppage Lost Hours": [
        "Community protest.",
        "Road closure.",
        "other external disruption.",
    ],

    "Environmental Stoppage Lost Hours": [
        "Environmental restriction .",
        "inspection stopping work.",
    ],

    "Planned Production Delay Lost Hours": [
        "Service on machine",
        "Maintanace on machine",
    ],

    "Waiting for Instructions Lost Hours": [
        "Production stopped while awaiting management direction.",
        "Production stopped while awaiting supervisor direction.",
    ],
}


def seed_default_reasons():

    wanted = set()

    for category, descriptions in REASONS.items():

        for description in descriptions:

            wanted.add(
                (category, description)
            )

            existing = frappe.db.get_value(
                "Daily General Lost Hour Reason",
                {
                    "lost_hour_category": category,
                    "reason_description": description,
                },
                "name",
            )

            if existing:

                frappe.db.set_value(
                    "Daily General Lost Hour Reason",
                    existing,
                    "enabled",
                    1,
                    update_modified=False,
                )

            else:

                frappe.get_doc({
                    "doctype":
                        "Daily General Lost Hour Reason",

                    "lost_hour_category":
                        category,

                    "reason_description":
                        description,

                    "enabled":
                        1,
                }).insert(
                    ignore_permissions=True
                )


    # Disable reasons no longer in approved list.
    all_master = frappe.get_all(
        "Daily General Lost Hour Reason",
        fields=[
            "name",
            "lost_hour_category",
            "reason_description",
        ],
        limit_page_length=0,
    )


    for row in all_master:

        key = (
            row.lost_hour_category,
            row.reason_description,
        )

        if key not in wanted:

            frappe.db.set_value(
                "Daily General Lost Hour Reason",
                row.name,
                "enabled",
                0,
                update_modified=False,
            )


    # --------------------------------------------------------
    # Convert old child values from plain text into Link names.
    # --------------------------------------------------------

    old_rows = frappe.get_all(
        "Daily General Lost Hours",
        fields=[
            "name",
            "lost_hour_category",
            "reason_description",
        ],
        limit_page_length=0,
    )


    for row in old_rows:

        value = row.reason_description

        if not value:
            continue


        # Already a valid Link name.
        if frappe.db.exists(
            "Daily General Lost Hour Reason",
            value
        ):
            continue


        master_name = frappe.db.get_value(
            "Daily General Lost Hour Reason",
            {
                "lost_hour_category":
                    row.lost_hour_category,

                "reason_description":
                    value,
            },
            "name",
        )


        # Historical reason not currently in approved list.
        if not master_name:

            legacy = frappe.get_doc({
                "doctype":
                    "Daily General Lost Hour Reason",

                "lost_hour_category":
                    row.lost_hour_category,

                "reason_description":
                    value,

                "enabled":
                    0,
            })

            legacy.insert(
                ignore_permissions=True
            )

            master_name = legacy.name


        frappe.db.set_value(
            "Daily General Lost Hours",
            row.name,
            "reason_description",
            master_name,
            update_modified=False,
        )


    frappe.db.commit()


    print()
    print("=" * 70)
    print("ACTIVE REASONS")
    print("=" * 70)

    for category in REASONS:

        count = frappe.db.count(
            "Daily General Lost Hour Reason",
            {
                "lost_hour_category": category,
                "enabled": 1,
            }
        )

        print(
            category,
            "=",
            count
        )

# GLH_REASON_NAME_NORMALISATION_START

def normalise_reason_names():
    doctype = "Daily General Lost Hour Reason"

    rows = frappe.get_all(
        doctype,
        fields=[
            "name",
            "lost_hour_category",
            "reason_description",
        ],
        limit_page_length=0,
    )

    print()
    print("=" * 70)
    print("NORMALISING GENERAL LOST HOUR REASON NAMES")
    print("=" * 70)

    # --------------------------------------------------------
    # Safety check for duplicate descriptions.
    # --------------------------------------------------------

    descriptions = {}

    for row in rows:
        description = (
            row.reason_description
            or ""
        ).strip()

        if not description:
            continue

        descriptions.setdefault(
            description,
            []
        ).append(
            row.name
        )


    duplicates = {
        description: names
        for description, names
        in descriptions.items()
        if len(names) > 1
    }


    if duplicates:

        print()
        print("ERROR: Duplicate Reason descriptions found:")

        for description, names in duplicates.items():
            print()
            print(description)

            for name in names:
                print("  -", name)

        frappe.throw(
            "Duplicate General Lost Hour Reason "
            "descriptions exist. Names were not changed."
        )


    renamed = 0


    # --------------------------------------------------------
    # Rename hash document names to the actual Reason text.
    #
    # Frappe rename_doc also updates Link references.
    # --------------------------------------------------------

    for row in rows:

        old_name = row.name

        new_name = (
            row.reason_description
            or ""
        ).strip()


        if not new_name:
            continue


        if old_name == new_name:
            continue


        if frappe.db.exists(
            doctype,
            new_name
        ):
            frappe.throw(
                "Cannot rename "
                + old_name
                + " because "
                + new_name
                + " already exists."
            )


        print()
        print("Rename:")
        print(" FROM:", old_name)
        print(" TO  :", new_name)


        frappe.rename_doc(
            doctype,
            old_name,
            new_name,
            force=True,
            )


        renamed += 1


    frappe.db.commit()


    print()
    print("=" * 70)
    print("RENAMED:", renamed)
    print("=" * 70)

# GLH_REASON_NAME_NORMALISATION_END

# GLH_SAFE_EXISTING_RENAME_START

def normalise_existing_reason_names():

    doctype = (
        "Daily General Lost Hour Reason"
    )

    child_doctype = (
        "Daily General Lost Hours"
    )


    print()
    print("=" * 80)
    print("GENERAL LOST HOUR REASON NAME NORMALISATION")
    print("=" * 80)


    # --------------------------------------------------------
    # IMPORTANT:
    # Do NOT save the DocType document here.
    #
    # Saving a standard DocType requires Developer Mode.
    # We only update its naming metadata directly in DB.
    # --------------------------------------------------------

    frappe.db.set_value(
        "DocType",
        doctype,
        {
            "autoname":
                "field:reason_description",

            "search_fields":
                "reason_description",

            "title_field":
                "",

            "show_title_field_in_link":
                0,
        },
        update_modified=False,
    )


    rows = frappe.get_all(
        doctype,
        fields=[
            "name",
            "lost_hour_category",
            "reason_description",
            "enabled",
        ],
        order_by=(
            "lost_hour_category, "
            "reason_description"
        ),
        limit_page_length=0,
    )


    print()
    print("Existing records:", len(rows))


    # --------------------------------------------------------
    # Check that descriptions are unique.
    # --------------------------------------------------------

    targets = {}


    for row in rows:

        target = (
            row.reason_description
            or ""
        ).strip()


        if not target:
            continue


        targets.setdefault(
            target,
            []
        ).append(
            row.name
        )


    duplicates = {
        target: names
        for target, names
        in targets.items()
        if len(names) > 1
    }


    if duplicates:

        print()
        print("DUPLICATE DESCRIPTIONS FOUND:")

        for target, names in (
            duplicates.items()
        ):

            print()
            print(target)

            for name in names:
                print(" -", name)


        frappe.throw(
            "Duplicate Reason / Description "
            "values exist. Rename stopped."
        )


    renamed = 0
    merged = 0
    unchanged = 0


    # --------------------------------------------------------
    # Rename hash names to readable Reason text.
    # --------------------------------------------------------

    for row in rows:

        old_name = row.name

        new_name = (
            row.reason_description
            or ""
        ).strip()


        if not new_name:
            print(
                "SKIP blank reason:",
                old_name
            )

            continue


        if old_name == new_name:

            unchanged += 1

            continue


        # ----------------------------------------------------
        # If readable target already exists:
        # point child Link values to it and remove duplicate.
        # ----------------------------------------------------

        if frappe.db.exists(
            doctype,
            new_name
        ):

            print()
            print("MERGE:")
            print(" OLD:", old_name)
            print(" NEW:", new_name)


            frappe.db.sql(
                """
                UPDATE `tabDaily General Lost Hours`
                SET reason_description = %s
                WHERE reason_description = %s
                """,
                (
                    new_name,
                    old_name,
                ),
            )


            frappe.delete_doc(
                doctype,
                old_name,
                force=True,
                ignore_permissions=True,
            )


            merged += 1

            continue


        print()
        print("RENAME:")
        print(" OLD:", old_name)
        print(" NEW:", new_name)


        frappe.rename_doc(
            doctype,
            old_name,
            new_name,
            force=True,
            )


        renamed += 1


    frappe.db.commit()


    frappe.clear_cache(
        doctype=doctype
    )

    frappe.clear_cache(
        doctype=child_doctype
    )


    print()
    print("=" * 80)
    print("RESULT")
    print("=" * 80)

    print("Renamed   :", renamed)
    print("Merged    :", merged)
    print("Unchanged :", unchanged)


    print()
    print("BLASTING:")


    blasting = frappe.get_all(
        doctype,
        filters={
            "lost_hour_category":
                "Blasting",

            "enabled":
                1,
        },
        fields=[
            "name",
            "reason_description",
        ],
        order_by="reason_description",
    )


    for row in blasting:

        print()
        print("NAME  :", row.name)
        print(
            "REASON:",
            row.reason_description
        )


    print()
    print("=" * 80)
    print("NORMALISATION COMPLETE")
    print("=" * 80)

# GLH_SAFE_EXISTING_RENAME_END

# GLH_TRAMMING_REASONS_START

REASONS["Tramming Of machine"] = [
    "Tramming from one loading area to other loading area",
    "Tramming from hardpark to loading area",
    "Tramming from loading area to hard park",
]

# GLH_TRAMMING_REASONS_END
