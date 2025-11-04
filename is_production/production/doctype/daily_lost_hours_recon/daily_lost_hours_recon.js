frappe.ui.form.on("Daily Lost Hours Recon", {
    // When shift_date changes, set day_of_week immediately
    shift_date(frm) {
        set_day_of_week(frm);
    },

    // Trigger when location changes (existing logic)
    location(frm) {
        fetch_monthly_production_planning(frm);
        fetch_assets(frm);
    },

    // Trigger when monthly_production_planning changes (existing logic)
    monthly_production_planning(frm) {
        fetch_shift_system(frm);
    },

    // When general lost hours fields change, update both the parent total and child rows
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
    // ✅ NEW FIELD: blasting
    blasting(frm) {
        update_parent_total_general_lost_hours(frm);
        update_child_general_lost_hours(frm);
    }
});

// Child Table Triggers
frappe.ui.form.on("Daily Lost Hours Assets", {
    absenteeism_no_replacement_hours(frm, cdt, cdn) {
        recalculate_total_plant_specific_lost_hours(frm, cdt, cdn);
    },
    spec_oper_train_medical_hours(frm, cdt, cdn) {
        recalculate_total_plant_specific_lost_hours(frm, cdt, cdn);
    }
});

/* ------------------------------------------------------------------
    HELPER FUNCTIONS
------------------------------------------------------------------ */

function set_day_of_week(frm) {
    if (frm.doc.shift_date) {
        const weekday = moment(frm.doc.shift_date).format("dddd");
        frm.set_value("day_of_week", weekday);
        frm.refresh_field("day_of_week");
    } else {
        frm.set_value("day_of_week", null);
        frm.refresh_field("day_of_week");
    }
}

function update_parent_total_general_lost_hours(frm) {
    const total = (
        (frm.doc.gen_training_hours || 0) +
        (frm.doc.weather_non_work_hours || 0) +
        (frm.doc.vfl_non_work_hours || 0) +
        (frm.doc.other_non_work_hours || 0) +
        (frm.doc.diesel_or_diesel_bowser_hours || 0) +
        (frm.doc.dust_water_bowser_issues_hours || 0) +
        (frm.doc.blasting || 0) // ✅ Added blasting
    );
    frm.set_value("total_general_lost_hours", total);
    frm.refresh_field("total_general_lost_hours");
}

function update_child_general_lost_hours(frm) {
    frm.doc.daily_lost_hours_assets_table.forEach(row => {
        frappe.model.set_value(row.doctype, row.name, "gen_training_hours_child", frm.doc.gen_training_hours || 0);
        frappe.model.set_value(row.doctype, row.name, "weather_non_work_hours_child", frm.doc.weather_non_work_hours || 0);
        frappe.model.set_value(row.doctype, row.name, "vfl_non_work_hours_child", frm.doc.vfl_non_work_hours || 0);
        frappe.model.set_value(row.doctype, row.name, "other_non_work_hours_child", frm.doc.other_non_work_hours || 0);
        frappe.model.set_value(row.doctype, row.name, "diesel_or_diesel_bowser_hours_child", frm.doc.diesel_or_diesel_bowser_hours || 0);
        frappe.model.set_value(row.doctype, row.name, "dust_water_bowser_issues_hours_child", frm.doc.dust_water_bowser_issues_hours || 0);
        frappe.model.set_value(row.doctype, row.name, "blasting_child", frm.doc.blasting || 0); // ✅ Added blasting_child

        const total_child_hours = (
            (frm.doc.gen_training_hours || 0) +
            (frm.doc.weather_non_work_hours || 0) +
            (frm.doc.vfl_non_work_hours || 0) +
            (frm.doc.other_non_work_hours || 0) +
            (frm.doc.diesel_or_diesel_bowser_hours || 0) +
            (frm.doc.dust_water_bowser_issues_hours || 0) +
            (frm.doc.blasting || 0) // ✅ Included blasting
        );

        frappe.model.set_value(row.doctype, row.name, "total_general_lost_hours_child", total_child_hours);
    });

    frm.refresh_field("daily_lost_hours_assets_table");
}

function recalculate_total_plant_specific_lost_hours(frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);
    row.total_plant_specific_lost_hours = (
        (row.absenteeism_no_replacement_hours || 0) +
        (row.spec_oper_train_medical_hours || 0)
    );
    frappe.model.set_value(cdt, cdn, "total_plant_specific_lost_hours", row.total_plant_specific_lost_hours);
}

/* ------------------------------------------------------------------
    EXISTING FUNCTIONS (UNCHANGED)
------------------------------------------------------------------ */

function fetch_monthly_production_planning(frm) {
    if (frm.doc.location && frm.doc.shift_date) {
        frappe.call({
            method: "is_production.production.doctype.daily_lost_hours_recon.daily_lost_hours_recon.get_monthly_production_planning",
            args: {
                location: frm.doc.location,
                shift_date: frm.doc.shift_date
            },
            callback: function(response) {
                if (response.message) {
                    frm.set_value("monthly_production_planning", response.message);
                    fetch_shift_system(frm);
                } else {
                    frm.set_value("monthly_production_planning", null);
                    frm.set_value("shift_system", null);
                }
            }
        });
    }
}

function fetch_shift_system(frm) {
    if (frm.doc.monthly_production_planning) {
        frappe.call({
            method: "is_production.production.doctype.daily_lost_hours_recon.daily_lost_hours_recon.get_shift_system",
            args: {
                monthly_production_planning: frm.doc.monthly_production_planning
            },
            callback: function(response) {
                if (response.message) {
                    frm.set_value("shift_system", response.message);
                    update_shift_options(frm, response.message);
                }
            }
        });
    }
}

function update_shift_options(frm, shift_system) {
    let shift_options = [];
    if (shift_system === "3x8Hour") {
        shift_options = ["Morning", "Afternoon", "Night"];
    } else if (shift_system === "2x12Hour") {
        shift_options = ["Day", "Night"];
    }
    frm.set_df_property("shift", "options", shift_options.join("\n"));
}

function fetch_assets(frm) {
    if (frm.doc.location) {
        frappe.call({
            method: "is_production.production.doctype.daily_lost_hours_recon.daily_lost_hours_recon.get_assets",
            args: {
                location: frm.doc.location
            },
            callback: function(response) {
                if (response.message) {
                    frm.clear_table("daily_lost_hours_assets_table");
                    response.message.forEach(asset => {
                        let row = frm.add_child("daily_lost_hours_assets_table");
                        row.asset_name = asset.asset_name;
                        row.item_name = asset.item_name;
                        row.asset_category = asset.asset_category;
                    });
                    frm.refresh_field("daily_lost_hours_assets_table");
                }
            }
        });
    }
}
