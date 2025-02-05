// Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Daily Lost Hours Recon", {
    location: function(frm) {
        fetch_monthly_production_planning(frm);
		fetch_assets(frm);
    },
    shift_date: function(frm) {
        fetch_monthly_production_planning(frm);
    },
    monthly_production_planning: function(frm) {
        fetch_shift_system(frm);
    }
});

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
                    fetch_shift_system(frm);  // Fetch shift system when monthly production planning is set
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
                        row.asset_name = asset.asset_name;  // Populate asset name in child table
                        row.item_name = asset.item_name;    // Populate item name
                        row.asset_category = asset.asset_category;  // Populate asset category
                    });
                    frm.refresh_field("daily_lost_hours_assets_table");
                }
            }
        });
    }
}