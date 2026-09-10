// daily_lost_hours_recon.js

frappe.ui.form.on("Daily Lost Hours Recon", {

    setup(frm) {
        // 🔒 Monthly Production Planning filtered ONLY by Site (location)
        frm.set_query("monthly_production_planning", () => {

            if (!frm.doc.location) {
                return {
                    filters: {
                        name: ["=", ""]
                    }
                };
            }

            return {
                filters: {
                    location: frm.doc.location
                }
            };
        });
    },

    refresh(frm) {
        // Ensure shift options are correct when opening/editing a doc
        if (frm.doc.shift_system) {
            update_shift_options(frm, frm.doc.shift_system);
        }

        // If location + date exist and monthly plan is empty, try auto-set
        auto_set_monthly_production_planning(frm);
    },

    shift_date(frm) {
        set_day_of_week(frm);

        // Reset dependent fields when shift_date changes
        frm.set_value("monthly_production_planning", null);
        frm.set_value("shift_system", null);

        auto_set_monthly_production_planning(frm);
    },

    location(frm) {
        // Clear dependent fields when Site changes
        frm.set_value("monthly_production_planning", null);
        frm.set_value("shift_system", null);

        fetch_assets(frm);
        auto_set_monthly_production_planning(frm);
    },

    monthly_production_planning(frm) {
        fetch_shift_system(frm);
    },

    gen_training_hours(frm) {
        update_parent_total_general_lost_hours(frm);
        update_child_general_lost_hours(frm);
    },

    weather_non_work_hours(frm) {
        update_parent_total_general_lost_hours(frm);
        update_child_general_lost_hours(frm);
    },

    vfl_non_work_hours(frm) {
        update_parent_total_general_lost_hours(frm);
        update_child_general_lost_hours(frm);
    },

    other_non_work_hours(frm) {
        update_parent_total_general_lost_hours(frm);
        update_child_general_lost_hours(frm);
    },

    diesel_or_diesel_bowser_hours(frm) {
        update_parent_total_general_lost_hours(frm);
        update_child_general_lost_hours(frm);
    },

    dust_water_bowser_issues_hours(frm) {
        update_parent_total_general_lost_hours(frm);
        update_child_general_lost_hours(frm);
    },

    blasting(frm) {
        update_parent_total_general_lost_hours(frm);
        update_child_general_lost_hours(frm);
    }
});


// ------------------------------------------------------------------
// CHILD TABLE TRIGGERS
// ------------------------------------------------------------------

frappe.ui.form.on("Daily Lost Hours Assets", {

    absenteeism_no_replacement_hours(frm, cdt, cdn) {
        recalculate_total_plant_specific_lost_hours(frm, cdt, cdn);
    },

    spec_oper_train_medical_hours(frm, cdt, cdn) {
        recalculate_total_plant_specific_lost_hours(frm, cdt, cdn);
    }
});


// ------------------------------------------------------------------
// HELPER FUNCTIONS
// ------------------------------------------------------------------

function set_day_of_week(frm) {
    if (frm.doc.shift_date) {
        frm.set_value(
            "day_of_week",
            moment(frm.doc.shift_date).format("dddd")
        );
    } else {
        frm.set_value("day_of_week", null);
    }
}

function update_parent_total_general_lost_hours(frm) {
    const total =
        (frm.doc.gen_training_hours || 0) +
        (frm.doc.weather_non_work_hours || 0) +
        (frm.doc.vfl_non_work_hours || 0) +
        (frm.doc.other_non_work_hours || 0) +
        (frm.doc.diesel_or_diesel_bowser_hours || 0) +
        (frm.doc.dust_water_bowser_issues_hours || 0) +
        (frm.doc.blasting || 0);

    frm.set_value("total_general_lost_hours", total);
}

function update_child_general_lost_hours(frm) {

    if (!frm.doc.daily_lost_hours_assets_table) return;

    const total_child_hours =
        (frm.doc.gen_training_hours || 0) +
        (frm.doc.weather_non_work_hours || 0) +
        (frm.doc.vfl_non_work_hours || 0) +
        (frm.doc.other_non_work_hours || 0) +
        (frm.doc.diesel_or_diesel_bowser_hours || 0) +
        (frm.doc.dust_water_bowser_issues_hours || 0) +
        (frm.doc.blasting || 0);

    frm.doc.daily_lost_hours_assets_table.forEach(row => {

        frappe.model.set_value(row.doctype, row.name, "gen_training_hours_child", frm.doc.gen_training_hours || 0);
        frappe.model.set_value(row.doctype, row.name, "weather_non_work_hours_child", frm.doc.weather_non_work_hours || 0);
        frappe.model.set_value(row.doctype, row.name, "vfl_non_work_hours_child", frm.doc.vfl_non_work_hours || 0);
        frappe.model.set_value(row.doctype, row.name, "other_non_work_hours_child", frm.doc.other_non_work_hours || 0);
        frappe.model.set_value(row.doctype, row.name, "diesel_or_diesel_bowser_hours_child", frm.doc.diesel_or_diesel_bowser_hours || 0);
        frappe.model.set_value(row.doctype, row.name, "dust_water_bowser_issues_hours_child", frm.doc.dust_water_bowser_issues_hours || 0);
        frappe.model.set_value(row.doctype, row.name, "blasting_child", frm.doc.blasting || 0);

        frappe.model.set_value(
            row.doctype,
            row.name,
            "total_general_lost_hours_child",
            total_child_hours
        );
    });

    frm.refresh_field("daily_lost_hours_assets_table");
}

function recalculate_total_plant_specific_lost_hours(frm, cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn);

    const total =
        (row.absenteeism_no_replacement_hours || 0) +
        (row.spec_oper_train_medical_hours || 0);

    frappe.model.set_value(
        cdt,
        cdn,
        "total_plant_specific_lost_hours",
        total
    );
}


// ------------------------------------------------------------------
// AUTO-POPULATE MONTHLY PLAN
// ------------------------------------------------------------------

function auto_set_monthly_production_planning(frm) {
    // Need both fields
    if (!frm.doc.location || !frm.doc.shift_date) return;

    // Don't overwrite if already chosen/set
    if (frm.doc.monthly_production_planning) return;

    frappe.call({
        method: "is_production.production.doctype.daily_lost_hours_recon.daily_lost_hours_recon.get_monthly_production_planning",
        args: {
            location: frm.doc.location,
            shift_date: frm.doc.shift_date
        },
        callback(response) {
            if (response.message) {
                frm.set_value("monthly_production_planning", response.message);
                // monthly_production_planning trigger fires -> fetch_shift_system
            } else {
                frm.set_value("monthly_production_planning", null);
                frm.set_value("shift_system", null);

                frappe.msgprint({
                    title: __("Monthly Plan Not Found"),
                    message: __(
                        "No Monthly Production Planning record found for Site <b>{0}</b> covering Shift Date <b>{1}</b>.",
                        [frm.doc.location, frm.doc.shift_date]
                    ),
                    indicator: "orange"
                });
            }
        }
    });
}


// ------------------------------------------------------------------
// SERVER CALLS
// ------------------------------------------------------------------

function fetch_shift_system(frm) {
    if (!frm.doc.monthly_production_planning) return;

    frappe.call({
        method: "is_production.production.doctype.daily_lost_hours_recon.daily_lost_hours_recon.get_shift_system",
        args: {
            monthly_production_planning: frm.doc.monthly_production_planning
        },
        callback(response) {
            if (response.message) {
                frm.set_value("shift_system", response.message);
                update_shift_options(frm, response.message);
            } else {
                frm.set_value("shift_system", null);
                update_shift_options(frm, null);
            }
        }
    });
}

function update_shift_options(frm, shift_system) {
    let options = [];

    if (shift_system === "3x8Hour") {
        options = ["Morning", "Afternoon", "Night"];
    } else if (shift_system === "2x12Hour") {
        options = ["Day", "Night"];
    } else {
        // fallback to original select options
        options = ["Day", "Morning", "Afternoon", "Night"];
    }

    frm.set_df_property("shift", "options", options.join("\n"));
}

function fetch_assets(frm) {
    if (!frm.doc.location) return;

    frappe.call({
        method: "is_production.production.doctype.daily_lost_hours_recon.daily_lost_hours_recon.get_assets",
        args: {
            location: frm.doc.location
        },
        callback(response) {
            if (response.message) {
                frm.clear_table("daily_lost_hours_assets_table");

                response.message.forEach(asset => {
                    const row = frm.add_child("daily_lost_hours_assets_table");
                    row.asset_name = asset.asset_name;
                    row.item_name = asset.item_name;
                    row.asset_category = asset.asset_category;
                });

                frm.refresh_field("daily_lost_hours_assets_table");

                // push current general hours into the table after loading assets
                update_child_general_lost_hours(frm);
            }
        }
    });
}

// GENERAL_LOST_HOURS_TABLE_V1_START

(() => {

    const TABLE =
        "general_lost_hours_table";


    const CATEGORIES = [
        "Training Non Work Hours",
        "Weather Conditions Non Work Hours",
        "VFL Non Work Hours",
        "Other Non Work Hours",
        "Dust and/or Water Bowser Lost Hours",
        "Diesel and/or Diesel Bowser Lost Hours",
        "Blasting",
        "Safety Stoppage Lost Hours",
        "Pre-Shift / Toolbox Talk Lost Hours",
        "Shift Change Lost Hours",
        "No Operator / Labour Lost Hours",
        "Industrial Action Lost Hours",
        "Pit Access / Road Lost Hours",
        "Road Maintenance Lost Hours",
        "Dewatering / Water in Pit Lost Hours",
        "Survey Lost Hours",
        "Geology Lost Hours",
        "Mining Permit / Clearance Lost Hours",
        "Bench / Face Preparation Lost Hours",
        "Crusher / Tip / Dump Lost Hours",
        "Traffic / Congestion Lost Hours",
        "Power Failure Lost Hours",
        "Communication / System Lost Hours",
        "Community / External Stoppage Lost Hours",
        "Environmental Stoppage Lost Hours",
        "Planned Production Delay Lost Hours",
        "Waiting for Instructions Lost Hours",
        "Tramming Of machine"
    ];


    const LEGACY_PARENT = {

        "Training Non Work Hours":
            "gen_training_hours",

        "Weather Conditions Non Work Hours":
            "weather_non_work_hours",

        "VFL Non Work Hours":
            "vfl_non_work_hours",

        "Other Non Work Hours":
            "other_non_work_hours",

        "Dust and/or Water Bowser Lost Hours":
            "dust_water_bowser_issues_hours",

        "Diesel and/or Diesel Bowser Lost Hours":
            "diesel_or_diesel_bowser_hours",

        "Blasting":
            "blasting"
    };


    const LEGACY_CHILD = {

        "Training Non Work Hours":
            "gen_training_hours_child",

        "Weather Conditions Non Work Hours":
            "weather_non_work_hours_child",

        "VFL Non Work Hours":
            "vfl_non_work_hours_child",

        "Other Non Work Hours":
            "other_non_work_hours_child",

        "Dust and/or Water Bowser Lost Hours":
            "dust_water_bowser_issues_hours_child",

        "Diesel and/or Diesel Bowser Lost Hours":
            "diesel_or_diesel_bowser_hours_child"
    };


    function time_seconds(value) {

        if (!value) {
            return null;
        }

        const p =
            String(value).split(":");

        return (
            parseInt(p[0] || 0, 10) * 3600
            +
            parseInt(p[1] || 0, 10) * 60
            +
            parseInt(p[2] || 0, 10)
        );
    }


    function calculate_hours(row) {

        if (
            !row.start_time
            ||
            !row.end_time
        ) {
            return 0;
        }

        const start =
            time_seconds(row.start_time);

        const end =
            time_seconds(row.end_time);

        let seconds =
            end - start;

        if (seconds < 0) {
            seconds +=
                24 * 3600;
        }

        return flt(
            seconds / 3600,
            2
        );
    }


    function sync_all(frm) {

        const totals = {};

        CATEGORIES.forEach(
            category => {
                totals[category] = 0;
            }
        );

        let grand_total = 0;
        const comments = [];


        (frm.doc[TABLE] || []).forEach(
            row => {



                if (
                    row.start_time
                    &&
                    row.end_time
                ) {
                    row.total_hours =
                        calculate_hours(row);
                }


                const hours =
                    flt(
                        row.total_hours || 0,
                        2
                    );


                if (
                    row.lost_hour_category
                    &&
                    Object.prototype
                        .hasOwnProperty
                        .call(
                            totals,
                            row.lost_hour_category
                        )
                ) {
                    totals[
                        row.lost_hour_category
                    ] += hours;
                }


                grand_total += hours;


                if (hours > 0) {

                    const pieces = [];

                    if (row.machine) {
                        pieces.push(
                            row.machine
                        );
                    }

                    if (
                        row.lost_hour_category
                    ) {
                        pieces.push(
                            row.lost_hour_category
                        );
                    }

                    if (
                        row.reason_description
                    ) {
                        pieces.push(
                            row.reason_description
                        );
                    }

                    if (
                        row.start_time
                        &&
                        row.end_time
                    ) {
                        pieces.push(
                            row.start_time
                            +
                            "-"
                            +
                            row.end_time
                        );
                    }

                    comments.push(
                        pieces.join(" - ")
                    );
                }
            }
        );


        Object.keys(
            LEGACY_PARENT
        ).forEach(category => {

            frm.doc[
                LEGACY_PARENT[category]
            ] = flt(
                totals[category] || 0,
                2
            );
        });



        frm.doc.general_lost_hours_detail_total =
            flt(
                grand_total,
                2
            );

        frm.doc.total_general_lost_hours =
            flt(
                grand_total,
                2
            );


        frm.doc.gen_lost_hours_comments =
            comments.join("\n");


        (
            frm.doc.daily_lost_hours_assets_table
            || []
        ).forEach(asset => {

            const asset_totals = {};

            CATEGORIES.forEach(
                category => {
                    asset_totals[category] = 0;
                }
            );

            let asset_total = 0;


            (frm.doc[TABLE] || []).forEach(
                row => {

                    if (
                        row.machine && row.machine !== "ALL Equipment" && row.machine !== asset.asset_name
                    ) {
                        return;
                    }


                    const hours =
                        flt(
                            row.total_hours || 0,
                            2
                        );


                    asset_total += hours;


                    if (
                        row.lost_hour_category
                    ) {
                        asset_totals[
                            row.lost_hour_category
                        ] += hours;
                    }
                }
            );


            Object.keys(
                LEGACY_CHILD
            ).forEach(category => {

                asset[
                    LEGACY_CHILD[category]
                ] = flt(
                    asset_totals[category] || 0,
                    2
                );
            });


            asset.total_general_lost_hours_child =
                flt(
                    asset_total,
                    2
                );
        });


        frm.refresh_field(TABLE);

        frm.refresh_field(
            "general_lost_hours_detail_total"
        );


        frm.refresh_field(
            "daily_lost_hours_assets_table"
        );
    }


    frappe.ui.form.on(
        "Daily Lost Hours Recon",
        {

            setup(frm) {

                // MACHINE
                frm.set_query(
                    "machine",
                    TABLE,
                    function(
                        doc,
                        cdt,
                        cdn
                    ) {

                        const row =
                            locals[cdt][cdn];

                        const location =
                            (
                                row
                                &&
                                row.location
                            )
                            ||
                            frm.doc.location;


                        if (location) {

                            return {
                                filters: {
                                    location:
                                        location
                                }
                            };
                        }

                        return {};
                    }
                );


                // ============================================
                // REASON / DESCRIPTION
                //
                // Category selected by user controls which
                // reasons appear in this dropdown.
                // ============================================

                frm.set_query(
                    "reason_description",
                    TABLE,
                    function(
                        doc,
                        cdt,
                        cdn
                    ) {

                        const row =
                            locals[cdt][cdn];


                        if (
                            !row
                            ||
                            !row.lost_hour_category
                        ) {
                            return {
                                filters: {
                                    lost_hour_category:
                                        "__NONE__",

                                    enabled:
                                        1
                                }
                            };
                        }


                        return {
                            filters: {

                                lost_hour_category:
                                    row.lost_hour_category,

                                enabled:
                                    1
                            }
                        };
                    }
                );
            },


            refresh(frm) {
                sync_all(frm);
            },



            location(frm) {
                // General Lost Hours Location is manual.
                // Do not copy parent Location into rows.
                sync_all(frm);
            }
,


            validate(frm) {

                (frm.doc[TABLE] || []).forEach(
                    row => {

                        const used =
                            row.machine
                            ||
                            row.lost_hour_category
                            ||
                            row.reason_description
                            ||
                            row.start_time
                            ||
                            row.end_time;


                        if (!used) {
                            return;
                        }


                        if (
                            !row.lost_hour_category
                        ) {
                            frappe.throw(
                                "Please select Lost Hour Category "
                                +
                                "on General Lost Hours row "
                                +
                                row.idx
                                +
                                "."
                            );
                        }


                        if (
                            !row.reason_description
                        ) {
                            frappe.throw(
                                "Please select Reason / Description for "
                                +
                                row.lost_hour_category
                                +
                                "."
                            );
                        }


                        if (!row.location) {
                            frappe.throw(
                                "Please enter Location for "
                                +
                                row.lost_hour_category
                                +
                                "."
                            );
                        }



                        if (!row.start_time) {
                            frappe.throw(
                                "Please enter Start Time for "
                                +
                                row.lost_hour_category
                                +
                                "."
                            );
                        }


                        if (!row.end_time) {
                            frappe.throw(
                                "Please enter End Time for "
                                +
                                row.lost_hour_category
                                +
                                "."
                            );
                        }


                        row.total_hours =
                            calculate_hours(row);
                    }
                );


                sync_all(frm);
            }
        }
    );


    frappe.ui.form.on(
        "Daily General Lost Hours",
        {

            general_lost_hours_table_add(
                frm,
                cdt,
                cdn
            ) {

                const row =
                    locals[cdt][cdn];

            },


            lost_hour_category(
                frm,
                cdt,
                cdn
            ) {

                // User changed category.
                // Clear old reason automatically.

                frappe.model.set_value(
                    cdt,
                    cdn,
                    "reason_description",
                    ""
                );


                sync_all(frm);
            },


            reason_description(frm) {
                sync_all(frm);
            },


            start_time(
                frm,
                cdt,
                cdn
            ) {

                const row =
                    locals[cdt][cdn];

                frappe.model.set_value(
                    cdt,
                    cdn,
                    "total_hours",
                    calculate_hours(row)
                );

                sync_all(frm);
            },


            end_time(
                frm,
                cdt,
                cdn
            ) {

                const row =
                    locals[cdt][cdn];

                frappe.model.set_value(
                    cdt,
                    cdn,
                    "total_hours",
                    calculate_hours(row)
                );

                sync_all(frm);
            },


            machine(frm) {
                sync_all(frm);
            },


            location(frm) {
                sync_all(frm);
            },


            general_lost_hours_table_remove(
                frm
            ) {
                sync_all(frm);
            }
        }
    );

})();

// GENERAL_LOST_HOURS_TABLE_V1_END

// GLH_ALL_EQUIPMENT_MACHINE_SELECT_START

(() => {

    const TABLE =
        "general_lost_hours_table";


    // ========================================================
    // MACHINE CATEGORIES ALLOWED IN GENERAL LOST HOURS
    // ========================================================

    const ALLOWED_MACHINE_CATEGORIES =
        new Set([
            "ADT",
            "ADTS",

            "EXCAVATOR",
            "EXCAVATORS",

            "DOZER",
            "DOZERS",

            "WATER BOWSER",
            "WATER BOWSERS",

            "TLB",
            "TLBS",

            "DIESEL BOWSER",
            "DIESEL BOWSERS",

            "GRADER",
            "GRADERS",

            "DRILL",
            "DRILLS"
        ]);


    function normalise_category(
        value
    ) {

        return String(
            value || ""
        )
        .trim()
        .replace(
            /\s+/g,
            " "
        )
        .toUpperCase();
    }


    function allowed_category(
        value
    ) {

        return (
            ALLOWED_MACHINE_CATEGORIES.has(
                normalise_category(
                    value
                )
            )
        );
    }


    async function load_glh_machines(
        frm
    ) {

        const options = [
            "ALL Equipment"
        ];


        try {

            const filters = {

                // Only submitted Assets.
                docstatus: 1
            };


            // Only machines belonging to
            // the Daily Lost Hours site.
            if (frm.doc.location) {

                filters.location =
                    frm.doc.location;
            }


            const result =
                await frappe.db.get_list(
                    "Asset",
                    {

                        fields: [
                            "name",
                            "asset_category",
                            "location"
                        ],

                        filters:
                            filters,

                        order_by:
                            "name asc",

                        limit:
                            5000
                    }
                );


            const machines =
                (
                    result || []
                )
                .filter(
                    asset =>
                        allowed_category(
                            asset.asset_category
                        )
                )
                .map(
                    asset =>
                        asset.name
                )
                .filter(Boolean);


            machines.sort(
                (a, b) =>
                    String(a)
                    .localeCompare(
                        String(b),
                        undefined,
                        {
                            numeric: true,
                            sensitivity: "base"
                        }
                    )
            );


            machines.forEach(
                machine => {

                    if (
                        !options.includes(
                            machine
                        )
                    ) {

                        options.push(
                            machine
                        );
                    }
                }
            );


            // Preserve a machine already captured
            // on an existing document.
            (
                frm.doc[TABLE] || []
            ).forEach(
                row => {

                    if (
                        row.machine
                        &&
                        !options.includes(
                            row.machine
                        )
                    ) {

                        options.push(
                            row.machine
                        );
                    }
                }
            );


            const table =
                frm.fields_dict[
                    TABLE
                ];


            if (
                !table
                ||
                !table.grid
            ) {
                return;
            }


            // Autocomplete values.
            table.grid
                .update_docfield_property(
                    "machine",
                    "options",
                    options.join("\n")
                );


            frm.refresh_field(
                TABLE
            );


            console.log(
                "General Lost Hours searchable machines:",
                options
            );

        }
        catch (error) {

            console.error(
                "Failed loading General Lost Hours machines:",
                error
            );
        }
    }


    frappe.ui.form.on(
        "Daily Lost Hours Recon",
        {

            onload_post_render(
                frm
            ) {

                load_glh_machines(
                    frm
                );
            },


            refresh(
                frm
            ) {

                load_glh_machines(
                    frm
                );
            },


            location(
                frm
            ) {

                load_glh_machines(
                    frm
                );
            }
        }
    );


    frappe.ui.form.on(
        "Daily General Lost Hours",
        {

            general_lost_hours_table_add(
                frm
            ) {

                load_glh_machines(
                    frm
                );
            }
        }
    );

})();

// GLH_ALL_EQUIPMENT_MACHINE_SELECT_END

// GLH_REASON_AUTOCOMPLETE_PERMANENT_START

(() => {

    const TABLE =
        "general_lost_hours_table";

    const METHOD =
        "is_production.production.doctype." +
        "daily_lost_hours_recon." +
        "daily_lost_hours_recon." +
        "get_general_lost_hour_reason_options";


    let reason_cache = null;


    // ========================================================
    // LOAD ACTIVE REASONS FROM SERVER
    // ========================================================

    async function load_reason_cache(
        force=false
    ) {

        if (
            reason_cache
            &&
            !force
        ) {
            return reason_cache;
        }


        try {

            const response =
                await frappe.call({
                    method: METHOD
                });


            reason_cache =
                response.message
                || {};


            console.log(
                "GLH Reason cache:",
                reason_cache
            );

        }
        catch (error) {

            console.error(
                "GLH Reason load failed:",
                error
            );

            reason_cache = {};
        }


        return reason_cache;
    }


    // ========================================================
    // REMOVE OLD LINK QUERY
    //
    // Very important:
    // Reason is now AUTOCOMPLETE, not LINK.
    // ========================================================

    function remove_old_reason_query(
        frm
    ) {

        const table =
            frm.fields_dict[
                TABLE
            ];


        if (
            !table
            ||
            !table.grid
        ) {
            return;
        }


        const grid =
            table.grid;


        try {

            const shared =
                grid.get_field(
                    "reason_description"
                );


            if (shared) {

                shared.get_query =
                    null;


                if (shared.df) {

                    shared.df.get_query =
                        null;
                }
            }

        }
        catch (error) {

            console.log(
                "GLH shared Reason field not ready."
            );
        }
    }


    // ========================================================
    // REASONS FOR ONE ROW
    // ========================================================

    async function get_options(
        row
    ) {

        const cache =
            await load_reason_cache();


        const category =
            String(
                row.lost_hour_category
                || ""
            ).trim();


        let options =
            category
            ?
                [
                    ...(
                        cache[
                            category
                        ]
                        || []
                    )
                ]
            :
                [];


        // --------------------------------------------
        // OLD SAVED RECORD SUPPORT
        //
        // Historical Reason remains a valid option
        // for its existing row.
        // --------------------------------------------

        const existing =
            String(
                row.reason_description
                || ""
            ).trim();


        if (
            existing
            &&
            !options.includes(
                existing
            )
        ) {

            options.unshift(
                existing
            );
        }


        return options;
    }


    // ========================================================
    // APPLY OPTIONS TO ACTUAL CHILD ROW CONTROL
    // ========================================================

    async function apply_row_options(
        frm,
        cdt,
        cdn
    ) {

        const row =
            locals[
                cdt
            ]?.[
                cdn
            ];


        if (!row) {
            return;
        }


        const table =
            frm.fields_dict[
                TABLE
            ];


        if (
            !table
            ||
            !table.grid
        ) {
            return;
        }


        const grid =
            table.grid;


        // Prevent old Link query from hijacking
        // Autocomplete input.
        remove_old_reason_query(
            frm
        );


        const options =
            await get_options(
                row
            );


        const grid_row =
            grid.grid_rows_by_docname[
                cdn
            ];


        if (!grid_row) {
            return;
        }


        // ====================================================
        // ROW-SPECIFIC DOCFIELD
        //
        // This is used when Frappe creates the inline control.
        // ====================================================

        const row_df =
            (
                grid_row.docfields
                || []
            ).find(
                df =>
                    df.fieldname
                    ===
                    "reason_description"
            );


        if (row_df) {

            row_df.options =
                options;

            row_df.get_query =
                null;
        }


        // ====================================================
        // ACTUAL INLINE CONTROL
        //
        // Frappe stores this in on_grid_fields_dict.
        // ====================================================

        const control =
            grid_row
            .on_grid_fields_dict
            ?.
            reason_description;


        if (control) {

            control.get_query =
                null;


            if (control.df) {

                control.df.get_query =
                    null;

                control.df.options =
                    options;
            }


            if (
                typeof control.set_data
                === "function"
            ) {

                control.set_data(
                    options
                );
            }
        }


        // ====================================================
        // EXPANDED CHILD ROW FORM
        // ====================================================

        const form_control =
            grid_row.grid_form
            ?.
            fields_dict
            ?.
            reason_description;


        if (form_control) {

            form_control.get_query =
                null;


            if (
                form_control.df
            ) {

                form_control.df.get_query =
                    null;

                form_control.df.options =
                    options;
            }


            if (
                typeof form_control.set_data
                === "function"
            ) {

                form_control.set_data(
                    options
                );
            }
        }


        console.log(
            "GLH Reason options applied:",
            category_label(row),
            options
        );
    }


    function category_label(
        row
    ) {

        return (
            row.lost_hour_category
            || "(no category)"
        );
    }


    // ========================================================
    // PRIME ROW DOCFIELDS BEFORE USER CLICKS REASON
    // ========================================================

    async function prime_all_rows(
        frm
    ) {

        remove_old_reason_query(
            frm
        );


        await load_reason_cache();


        const rows =
            frm.doc[
                TABLE
            ]
            || [];


        for (
            const row
            of rows
        ) {

            await apply_row_options(
                frm,
                row.doctype,
                row.name
            );
        }
    }


    // ========================================================
    // PARENT
    // ========================================================

    frappe.ui.form.on(
        "Daily Lost Hours Recon",
        {

            async refresh(
                frm
            ) {

                reason_cache =
                    null;


                remove_old_reason_query(
                    frm
                );


                await load_reason_cache(
                    true
                );


                setTimeout(
                    () => {

                        prime_all_rows(
                            frm
                        );
                    },
                    200
                );
            }
        }
    );


    // ========================================================
    // CHILD
    // ========================================================

    frappe.ui.form.on(
        "Daily General Lost Hours",
        {

            async lost_hour_category(
                frm,
                cdt,
                cdn
            ) {

                const row =
                    locals[
                        cdt
                    ][
                        cdn
                    ];


                // Category changed:
                // Reason from previous category must clear.
                if (
                    row.reason_description
                ) {

                    await frappe.model.set_value(
                        cdt,
                        cdn,
                        "reason_description",
                        ""
                    );
                }


                await apply_row_options(
                    frm,
                    cdt,
                    cdn
                );
            },


            async general_lost_hours_table_add(
                frm,
                cdt,
                cdn
            ) {

                await apply_row_options(
                    frm,
                    cdt,
                    cdn
                );
            },


            async form_render(
                frm,
                cdt,
                cdn
            ) {

                await apply_row_options(
                    frm,
                    cdt,
                    cdn
                );
            }
        }
    );


    // ========================================================
    // WHEN FRAPPE RENDERS A CHILD GRID ROW
    // ========================================================

    $(document)
        .off(
            "grid-row-render.glhReason"
        )
        .on(
            "grid-row-render.glhReason",
            function(
                event,
                grid_row
            ) {

                if (
                    !grid_row
                    ||
                    !grid_row.doc
                    ||
                    grid_row.doc.doctype
                    !==
                    "Daily General Lost Hours"
                ) {
                    return;
                }


                const frm =
                    cur_frm;


                if (
                    !frm
                    ||
                    frm.doctype
                    !==
                    "Daily Lost Hours Recon"
                ) {
                    return;
                }


                setTimeout(
                    () => {

                        apply_row_options(
                            frm,
                            grid_row.doc.doctype,
                            grid_row.doc.name
                        );
                    },
                    50
                );
            }
        );

})();

// GLH_REASON_AUTOCOMPLETE_PERMANENT_END
