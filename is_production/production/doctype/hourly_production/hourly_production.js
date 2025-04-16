// Disable Frappe Onboarding Tour to avoid unrelated errors (if applicable)
if (frappe.ui && frappe.ui.init_onboarding_tour) {
    console.log("Disabling onboarding tour.");
    frappe.ui.init_onboarding_tour = function() {
        console.log("Onboarding tour was called but is now disabled.");
    };
}

// Stub for update_doc_name function (update as needed)
function update_doc_name(frm) {
    console.log("update_doc_name stub invoked.");
}

frappe.ui.form.on('Hourly Production', {
    setup: function(frm) {
        if (frm.fields_dict['truck_loads']?.grid) {
            frm.fields_dict['truck_loads'].grid.get_field('asset_name_shoval').get_query = function() {
                return {
                    filters: {
                        docstatus: 1,
                        asset_category: 'Excavator',
                        location: frm.doc.location
                    }
                };
            };
        }
    },

    location: function(frm) {
        // First, fetch Monthly Production Planning (and its child table)
        fetch_monthly_production_planning(frm);
        // Then, populate truck loads and dozer production table.
        populate_truck_loads_and_lookup(frm);
        populate_dozer_production_table(frm);
        if (frm.doc.__islocal) {
            populate_truck_loads_and_lookup(frm);
        }
    },

    prod_date: function(frm) {
        // When prod_date is updated, fetch the monthly planning document.
        fetch_monthly_production_planning(frm);
    },

    after_save: function(frm) {
        frm.reload_doc();
    },

    shift_system: function(frm) {
        update_shift_options(frm);
    },

    shift: function(frm) {
        update_shift_num_hour_options(frm);
    },

    shift_num_hour: function(frm) {
        if (frm.doc.shift_num_hour) {
            update_hour_slot(frm);
        }
    },

    refresh: function(frm) {
        if (!frm.is_new() && frm.doc.unique_reference) {
            frm.set_value('unique_reference', frm.doc.unique_reference);
        }
    }
});

// -------------------------
// Helper Functions
// -------------------------
function set_field_options(frm, fieldname, options) {
    if (frm.fields_dict[fieldname]) {
        frm.set_df_property(fieldname, "options", options.join("\n"));
    } else {
        console.warn(`Field "${fieldname}" not found.`);
    }
}

function update_shift_options(frm) {
    let shift_options = [];
    if (frm.doc.shift_system === "2x12Hour") {
        shift_options = ["Day", "Night"];
    } else if (frm.doc.shift_system === "3x8Hour") {
        shift_options = ["Morning", "Afternoon", "Night"];
    }
    set_field_options(frm, "shift", shift_options);
    frm.set_value("shift", null);
}

function update_shift_num_hour_options(frm) {
    let shift_num_hour_options = [];
    if (frm.doc.shift === "Day") {
        shift_num_hour_options = Array.from({ length: 12 }, (_, i) => `Day-${i + 1}`);
    } else if (frm.doc.shift === "Night") {
        shift_num_hour_options = Array.from({ length: 12 }, (_, i) => `Night-${i + 1}`);
    } else if (frm.doc.shift === "Morning") {
        shift_num_hour_options = Array.from({ length: 8 }, (_, i) => `Morning-${i + 1}`);
    } else if (frm.doc.shift === "Afternoon") {
        shift_num_hour_options = Array.from({ length: 8 }, (_, i) => `Afternoon-${i + 1}`);
    }
    set_field_options(frm, "shift_num_hour", shift_num_hour_options);
    frm.set_value("shift_num_hour", null);
}

function update_hour_slot(frm) {
    let shift_timings = {};
    if (frm.doc.shift === "Day") {
        shift_timings = Array.from({ length: 12 }, (_, i) =>
            [`Day-${i + 1}`, `${6 + i}:00-${7 + i}:00`]
        ).reduce((acc, [k, v]) => { acc[k] = v; return acc; }, {});
    } else if (frm.doc.shift === "Morning") {
        shift_timings = Array.from({ length: 8 }, (_, i) =>
            [`Morning-${i + 1}`, `${6 + i}:00-${7 + i}:00`]
        ).reduce((acc, [k, v]) => { acc[k] = v; return acc; }, {});
    } else if (frm.doc.shift === "Afternoon") {
        shift_timings = Array.from({ length: 8 }, (_, i) =>
            [`Afternoon-${i + 1}`, `${14 + i}:00-${15 + i}:00`]
        ).reduce((acc, [k, v]) => { acc[k] = v; return acc; }, {});
    } else if (frm.doc.shift === "Night") {
        if (frm.doc.shift_system === "2x12Hour") {
            shift_timings = Array.from({ length: 12 }, (_, i) =>
                [`Night-${i + 1}`, `${(18 + i) % 24}:00-${(19 + i) % 24}:00`]
            ).reduce((acc, [k, v]) => { acc[k] = v; return acc; }, {});
        } else if (frm.doc.shift_system === "3x8Hour") {
            shift_timings = Array.from({ length: 8 }, (_, i) =>
                [`Night-${i + 1}`, `${(22 + i) % 24}:00-${(23 + i) % 24}:00`]
            ).reduce((acc, [k, v]) => { acc[k] = v; return acc; }, {});
        }
    }
    const timing = shift_timings[frm.doc.shift_num_hour];
    if (!timing) {
        frappe.msgprint(__('Please select a valid shift number hour.'), "Validation Error");
        return;
    }
    frm.set_value("hour_slot", timing);
}

// -------------------------
// Data Fetching Functions
// -------------------------
function fetch_monthly_production_planning(frm) {
    if (frm.doc.location && frm.doc.prod_date) {
        console.log("Attempting to fetch Monthly Production Planning for Location:", frm.doc.location, "and prod_date:", frm.doc.prod_date);
        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Monthly Production Planning",
                fields: ["name", "prod_month_start_date", "prod_month_end_date", "shift_system"],
                filters: [
                    ["location", "=", frm.doc.location],
                    ["prod_month_start_date", "<=", frm.doc.prod_date],
                    ["prod_month_end_date", ">=", frm.doc.prod_date]
                ],
                limit_page_length: 1
            },
            callback: function(r) {
                console.log("Response from get_list:", r);
                if (r.message && r.message.length > 0) {
                    const plan = r.message[0];
                    console.log("Matching Monthly Production Planning found:", plan);
                    // Set the field "month_prod_planning" on the Hourly Production form
                    frm.set_value("month_prod_planning", plan.name);
                    frm.set_value("shift_system", plan.shift_system || null);
                    update_doc_name(frm);
                    // Fetch detailed data including child table data
                    fetch_mining_areas_from_monthly_plan(frm, plan.name);
                } else {
                    console.warn("No Monthly Production Planning record found for the filters.");
                    frm.set_value("month_prod_planning", null);
                    frm.set_value("shift_system", null);
                    frappe.msgprint(__("No Monthly Production Planning document found for the selected location and production date."));
                }
            }
        });
    }
}


function fetch_mining_areas_from_monthly_plan(frm, monthlyPlanName) {
    console.log("Fetching complete Monthly Production Planning document for:", monthlyPlanName);
    frappe.call({
        method: "frappe.client.get",
        args: {
            doctype: "Monthly Production Planning",
            name: monthlyPlanName,
            // Explicitly retrieve all fields, including child table rows in month_prod_days and mining_areas
            fields: ["*", "month_prod_days:*", "mining_areas:*"]
        },
        callback: function(r) {
            if (r.message) {
                console.log("Fetched Monthly Production Planning Document:", r.message);
                
                // Added snippet to log child records from the month_prod_days table
                if (r.message.month_prod_days && r.message.month_prod_days.length > 0) {
                    console.log("Child records in month_prod_days:", JSON.stringify(r.message.month_prod_days));
                } else {
                    console.warn("No child records found in month_prod_days.");
                }
                
                if (r.message.mining_areas && r.message.mining_areas.length > 0) {
                    console.log("Mining Areas Table Values:", r.message.mining_areas);
                    // Clear existing rows in the child table "mining_areas_options"
                    frm.clear_table("mining_areas_options");
                    r.message.mining_areas.forEach(function(row) {
                        let child = frm.add_child("mining_areas_options");
                        frappe.model.set_value(child.doctype, child.name, "mining_areas", row.mining_areas);
                    });
                    frm.refresh_field("mining_areas_options");
                    console.log("After refreshing, mining_areas_options:", frm.doc.mining_areas_options);
                    // Now update the dozer production select field options.
                    update_dozer_production_mining_area_options(frm);
                } else {
                    console.log("The mining_areas table is present but empty in the fetched document.");
                }
                // Fetch the hourly production reference using the form's prod_date.
                fetch_hourly_production_reference_from_monthly_days(frm, r.message);
            } else {
                console.log("Unable to fetch the Monthly Production Planning document for:", monthlyPlanName);
            }
        }
    });
}

// New helper function to fetch the hourly production reference using prod_date.
// Normalize both the Hourly Production form's prod_date and each child record's shift_start_date.
function fetch_hourly_production_reference_from_monthly_days(frm, monthlyPlanDoc) {
    console.log(">> Entering fetch_hourly_production_reference_from_monthly_days function");
    
    console.log("Form prod_date (raw):", frm.doc.prod_date);
    if (!frm.doc.prod_date) {
        console.warn("Production date not determined. Ensure prod_date is valid.");
        return;
    }
    
    // Normalize the form's prod_date to YYYY-MM-DD format.
    var formDate = new Date(frm.doc.prod_date).toISOString().split("T")[0];
    console.log("Normalized form prod_date:", formDate);
    
    var found = false;
    if (monthlyPlanDoc.month_prod_days && monthlyPlanDoc.month_prod_days.length > 0) {
        console.log("Found", monthlyPlanDoc.month_prod_days.length, "records in month_prod_days:");
        monthlyPlanDoc.month_prod_days.forEach(function(child, index) {
            // Normalize the child's shift_start_date.
            var childDate = new Date(child.shift_start_date).toISOString().split("T")[0];
            console.log("Record", index, ": child shift_start_date normalized =", childDate,
                        ", hourly_production_reference =", child.hourly_production_reference);
            
            if (childDate === formDate && child.hourly_production_reference) {
                frm.set_value("monthly_production_child_ref", child.hourly_production_reference);
                console.log("Match found in record", index, ": Setting monthly_production_child_ref to", child.hourly_production_reference);
                found = true;
            }
        });
    } else {
        console.warn("No records found in the month_prod_days child table.");
    }
    
    if (!found) {
        console.warn("No matching hourly production reference found for prod_date:", formDate);
        frappe.msgprint(__("No matching hourly production reference found in Monthly Production Planning for production date " + formDate));
        frm.set_value("monthly_production_child_ref", null);
    }
    
    console.log(">> Exiting fetch_hourly_production_reference_from_monthly_days function");
}

// Helper function to update the dozer production table's select field options.
function update_dozer_production_mining_area_options(frm) {
    setTimeout(function() {
        let mining_areas_records = frm.doc["mining_areas_options"] || [];
        console.log("Fetched mining areas records from frm.doc.mining_areas_options:", mining_areas_records);
        let options = [];
        mining_areas_records.forEach(function(child_row, index) {
            console.log(`Child row [${index}] data:`, child_row);
            if (child_row.mining_areas) {
                options.push(child_row.mining_areas);
            }
        });
        if (options.length === 0) {
            console.warn("Warning: No mining areas values found in mining_areas_options.");
        } else {
            console.log("Collected mining areas options:", options);
        }
        
        if (frm.fields_dict.dozer_production && frm.fields_dict.dozer_production.grid) {
            let grid = frm.fields_dict.dozer_production.grid;
            let child_fields = grid.df.fields;
            for (let i = 0; i < child_fields.length; i++) {
                if (child_fields[i].fieldname === "mining_areas_dozer_child") {
                    child_fields[i].options = options.join("\n");
                    console.log("Set grid df options for mining_areas_dozer_child:", options.join("\n"));
                    break;
                }
            }
            grid.refresh();
        } else {
            console.error("Error: Dozer production grid not found in frm.fields_dict.");
        }
    }, 500);
}

// -------------------------
// Other Data Functions
// -------------------------
function populate_truck_loads_and_lookup(frm) {
    if (frm.doc.location) {
        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Asset",
                fields: ["asset_name", "item_name"],
                filters: [
                    ["location", "=", frm.doc.location],
                    ["asset_category", "in", ["ADT", "RIGID"]],
                    ["docstatus", "=", 1]
                ],
                order_by: "asset_name asc"
            },
            callback: function(r) {
                if (r.message && r.message.length > 0) {
                    frm.clear_table("truck_loads");
                    r.message.forEach(function(asset) {
                        const row = frm.add_child("truck_loads");
                        frappe.model.set_value(row.doctype, row.name, "asset_name_truck", asset.asset_name);
                        frappe.model.set_value(row.doctype, row.name, "item_name", asset.item_name || "");
                    });
                    frm.refresh_field("truck_loads");
                } else {
                    frappe.msgprint(__("No assets found for the selected location."));
                }
            }
        });
    }
}

frappe.ui.form.on("Truck Loads", {
    item_name: function(frm, cdt, cdn) {
        update_tub_factor_doc_link(frm, cdt, cdn);
    },
    mat_type: function(frm, cdt, cdn) {
        update_tub_factor_doc_link(frm, cdt, cdn);
    },
    asset_name_shoval: function(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        if (!row.asset_name_shoval) {
            frappe.model.set_value(cdt, cdn, "item_name_excavator", null);
            return;
        }
        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "Asset",
                name: row.asset_name_shoval
            },
            callback: function(r) {
                if (r.message && r.message.item_code) {
                    if (row.item_name_excavator !== r.message.item_code) {
                        frappe.model.set_value(cdt, cdn, "item_name_excavator", r.message.item_code);
                    }
                } else {
                    frappe.model.set_value(cdt, cdn, "item_name_excavator", null);
                    frappe.msgprint(__("Item Code not found for selected Asset."));
                }
            }
        });
    },
    tub_factor: function(frm, cdt, cdn) {
        calculate_bcms(cdt, cdn);
    },
    loads: function(frm, cdt, cdn) {
        calculate_bcms(cdt, cdn);
    }
});

function update_tub_factor_doc_link(frm, cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn);
    if (row.item_name && row.mat_type) {
        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Tub Factor",
                filters: { item_name: row.item_name, mat_type: row.mat_type },
                fields: ["name", "tub_factor"],
                limit_page_length: 1
            },
            callback: function(r) {
                if (r.message && r.message.length > 0) {
                    const tubFactorDoc = r.message[0];
                    frappe.model.set_value(cdt, cdn, "tub_factor_doc_link", tubFactorDoc.name);
                    frappe.model.set_value(cdt, cdn, "tub_factor", tubFactorDoc.tub_factor);
                } else {
                    frappe.msgprint(__("No Tub Factor found for the selected Item Name and Material Type."));
                    frappe.model.set_value(cdt, cdn, "tub_factor_doc_link", null);
                    frappe.model.set_value(cdt, cdn, "tub_factor", null);
                }
            }
        });
    } else {
        frappe.model.set_value(cdt, cdn, "tub_factor_doc_link", null);
        frappe.model.set_value(cdt, cdn, "tub_factor", null);
    }
    frm.refresh_field("truck_loads");
}

function populate_dozer_production_table(frm) {
    if (frm.doc.location) {
        frappe.call({
            method: "is_production.production.doctype.hourly_production.hourly_production.fetch_dozer_production_assets",
            args: { location: frm.doc.location },
            callback: function(r) {
                if (r.message && r.message.length > 0) {
                    frm.clear_table("dozer_production");
                    r.message.forEach(function(asset) {
                        const row = frm.add_child("dozer_production");
                        row.asset_name = asset.asset_name;
                        row.bcm_hour = 0;
                        row.dozer_service = "No Dozing";
                    });
                    frm.refresh_field("dozer_production");
                } else {
                    frappe.msgprint(__("No Dozer assets found for the selected location."));
                }
            }
        });
    }
}

function calculate_bcms(cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn);
    const loads = parseFloat(row.loads);
    const tub_factor = parseFloat(row.tub_factor);
    if (!isNaN(loads) && !isNaN(tub_factor)) {
        frappe.model.set_value(cdt, cdn, "bcms", loads * tub_factor);
    } else {
        frappe.model.set_value(cdt, cdn, "bcms", null);
    }
}
