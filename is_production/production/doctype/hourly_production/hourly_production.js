// Disable Frappe Onboarding Tour to avoid unrelated errors (if applicable)
if (frappe.ui && frappe.ui.init_onboarding_tour) {
    frappe.ui.init_onboarding_tour = function() {};
}

// Stub for update_doc_name function (update as needed)
function update_doc_name(frm) {
    // Placeholder logic for updating document name
    console.log("update_doc_name stub invoked.");
}

frappe.ui.form.on('Hourly Production', {
    setup: function (frm) {
        if (frm.fields_dict['truck_loads']?.grid) {
            frm.fields_dict['truck_loads'].grid.get_field('asset_name_shoval').get_query = function () {
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

    location: function (frm) {
        fetch_monthly_production_planning(frm);
        populate_truck_loads_and_lookup(frm);
        populate_dozer_production_table(frm);
        if (frm.doc.__islocal) {
            populate_truck_loads_and_lookup(frm);
        }
    },

    prod_date: function (frm) {
        fetch_monthly_production_planning(frm);
        set_day_number(frm);
    },

    after_save: function (frm) {
        frm.reload_doc();
    },

    shift_system: function (frm) {
        update_shift_options(frm);
    },

    shift: function (frm) {
        update_shift_num_hour_options(frm);
    },

    shift_num_hour: function (frm) {
        if (frm.doc.shift_num_hour) {
            update_hour_slot(frm);
        }
    },

    refresh: function (frm) {
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
        frm.set_df_property(fieldname, 'options', options.join('\n'));
    } else {
        console.warn(`Field "${fieldname}" not found.`);
    }
}

function set_day_number(frm) {
    if (frm.doc.prod_date) {
        let prodDate = new Date(frm.doc.prod_date);
        frm.set_value('day_number', prodDate.getDate());
    }
}

function update_shift_options(frm) {
    let shift_options = [];
    if (frm.doc.shift_system === '2x12Hour') {
        shift_options = ['Day', 'Night'];
    } else if (frm.doc.shift_system === '3x8Hour') {
        shift_options = ['Morning', 'Afternoon', 'Night'];
    }
    set_field_options(frm, 'shift', shift_options);
    frm.set_value('shift', null);
}

function update_shift_num_hour_options(frm) {
    let shift_num_hour_options = [];
    if (frm.doc.shift === 'Day') {
        shift_num_hour_options = Array.from({ length: 12 }, (_, i) => `Day-${i + 1}`);
    } else if (frm.doc.shift === 'Night') {
        shift_num_hour_options = Array.from({ length: 12 }, (_, i) => `Night-${i + 1}`);
    } else if (frm.doc.shift === 'Morning') {
        shift_num_hour_options = Array.from({ length: 8 }, (_, i) => `Morning-${i + 1}`);
    } else if (frm.doc.shift === 'Afternoon') {
        shift_num_hour_options = Array.from({ length: 8 }, (_, i) => `Afternoon-${i + 1}`);
    } else if (frm.doc.shift === 'Night') {
        shift_num_hour_options = Array.from({ length: 8 }, (_, i) => `Night-${i + 1}`);
    }
    set_field_options(frm, 'shift_num_hour', shift_num_hour_options);
    frm.set_value('shift_num_hour', null);
}

function update_hour_slot(frm) {
    let shift_timings = {};

    if (frm.doc.shift === "Day") {
        // For Day shift: 12 slots starting at 6:00 AM up to 18:00
        shift_timings = Array.from({ length: 12 }, (_, i) => 
            [`Day-${i + 1}`, `${6 + i}:00-${7 + i}:00`]
        ).reduce((acc, [k, v]) => { 
            acc[k] = v; 
            return acc; 
        }, {});
    } else if (frm.doc.shift === "Morning") {
        // For Morning shift: 8 slots starting at 6:00 AM up to 14:00
        shift_timings = Array.from({ length: 8 }, (_, i) => 
            [`Morning-${i + 1}`, `${6 + i}:00-${7 + i}:00`]
        ).reduce((acc, [k, v]) => { 
            acc[k] = v; 
            return acc; 
        }, {});
    } else if (frm.doc.shift === "Afternoon") {
        // For Afternoon shift: 8 slots starting at 14:00 up to 22:00
        shift_timings = Array.from({ length: 8 }, (_, i) => 
            [`Afternoon-${i + 1}`, `${14 + i}:00-${15 + i}:00`]
        ).reduce((acc, [k, v]) => { 
            acc[k] = v; 
            return acc; 
        }, {});
    } else if (frm.doc.shift === "Night") {
        if (frm.doc.shift_system === "2x12Hour") {
            // For a 2x12Hour system, Night shift: 12 slots starting at 18:00 up to 5:00
            shift_timings = Array.from({ length: 12 }, (_, i) => 
                [`Night-${i + 1}`, `${(18 + i) % 24}:00-${(19 + i) % 24}:00`]
            ).reduce((acc, [k, v]) => { 
                acc[k] = v; 
                return acc; 
            }, {});
        } else if (frm.doc.shift_system === "3x8Hour") {
            // For a 3x8Hour system, Night shift: 8 slots starting at 22:00 up to 5:00
            shift_timings = Array.from({ length: 8 }, (_, i) => 
                [`Night-${i + 1}`, `${(22 + i) % 24}:00-${(23 + i) % 24}:00`]
            ).reduce((acc, [k, v]) => { 
                acc[k] = v; 
                return acc; 
            }, {});
        }
    }

    const timing = shift_timings[frm.doc.shift_num_hour];
    if (!timing) {
        frappe.msgprint(__('Please select a valid shift number hour.'), 'Validation Error');
        return;
    }
    frm.set_value('hour_slot', timing);
}

// -------------------------
// Data Fetching Functions
// -------------------------

// Fetch a matching Monthly Production Planning record based on location and prod_date,
// then set the month_prod_planning field and fetch mining_areas data.
function fetch_monthly_production_planning(frm) {
    if (frm.doc.location && frm.doc.prod_date) {
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Monthly Production Planning',
                fields: ['name', 'prod_month_start_date', 'prod_month_end_date', 'shift_system'],
                filters: [
                    ['location', '=', frm.doc.location],
                    ['prod_month_start_date', '<=', frm.doc.prod_date],
                    ['prod_month_end_date', '>=', frm.doc.prod_date]
                ],
                limit_page_length: 1
            },
            callback: function (r) {
                if (r.message && r.message.length > 0) {
                    const plan = r.message[0];
                    console.log("Matching Monthly Production Planning found:", plan);
                    frm.set_value('month_prod_planning', plan.name);
                    frm.set_value('shift_system', plan.shift_system || null);
                    update_doc_name(frm);
                    
                    // Fetch the complete document and then populate mining_areas_options table.
                    fetch_mining_areas_from_monthly_plan(frm, plan.name);
                } else {
                    frm.set_value('month_prod_planning', null);
                    frm.set_value('shift_system', null);
                    frappe.msgprint(__('No Monthly Production Planning document found for the selected location and production date.'));
                }
            }
        });
    }
}

// Fetch the complete Monthly Production Planning document using its name,
// log the mining_areas table values, and then populate the Hourly Production child table.
function fetch_mining_areas_from_monthly_plan(frm, monthlyPlanName) {
    console.log("Fetching complete Monthly Production Planning document for:", monthlyPlanName);
    frappe.call({
        method: 'frappe.client.get',
        args: {
            doctype: 'Monthly Production Planning',
            name: monthlyPlanName
        },
        callback: function (r) {
            if (r.message) {
                console.log("Fetched Monthly Production Planning Document:", r.message);
                if (r.message.mining_areas) {
                    if (r.message.mining_areas.length > 0) {
                        console.log("Mining Areas Table Values:", r.message.mining_areas);
                        // Clear existing rows in the child table "mining_areas_options" of the Hourly Production document.
                        frm.clear_table("mining_areas_options");
                        // Loop through each entry in the monthly plan's mining_areas child table.
                        r.message.mining_areas.forEach(function(row) {
                            let child = frm.add_child("mining_areas_options");
                            // Copy the value from the field "mining_areas" in the monthly plan
                            // into the field "mining_areas" in the Hourly Production child table.
                            frappe.model.set_value(child.doctype, child.name, "mining_areas", row.mining_areas);
                        });
                        frm.refresh_field("mining_areas_options");
                    } else {
                        console.log("The mining_areas table is present but empty in the fetched document.");
                    }
                } else {
                    console.log("The fetched document does not contain a field named mining_areas.");
                }
            } else {
                console.log("Unable to fetch the Monthly Production Planning document for:", monthlyPlanName);
            }
        }
    });
}

// -------------------------
// Other Data Functions
// -------------------------

function populate_truck_loads_and_lookup(frm) {
    if (frm.doc.location) {
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Asset',
                fields: ['asset_name', 'item_name'],
                filters: [
                    ['location', '=', frm.doc.location],
                    ['asset_category', 'in', ['ADT', 'RIGID']],
                    ['docstatus', '=', 1]
                ],
                order_by: 'asset_name asc'
            },
            callback: function (r) {
                if (r.message && r.message.length > 0) {
                    frm.clear_table('truck_loads');
                    r.message.forEach(asset => {
                        const row = frm.add_child('truck_loads');
                        frappe.model.set_value(row.doctype, row.name, 'asset_name_truck', asset.asset_name);
                        frappe.model.set_value(row.doctype, row.name, 'item_name', asset.item_name || "");
                    });
                    frm.refresh_field('truck_loads');
                } else {
                    frappe.msgprint(__('No assets found for the selected location.'));
                }
                suppress_excavator_autofill = false;
            }
        });
    }
}

frappe.ui.form.on('Truck Loads', {
    item_name: function (frm, cdt, cdn) {
        update_tub_factor_doc_link(frm, cdt, cdn);
    },
    mat_type: function (frm, cdt, cdn) {
        update_tub_factor_doc_link(frm, cdt, cdn);
    },
    asset_name_shoval: function (frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        if (!row.asset_name_shoval) {
            frappe.model.set_value(cdt, cdn, 'item_name_excavator', null);
            return;
        }
        frappe.call({
            method: 'frappe.client.get',
            args: {
                doctype: 'Asset',
                name: row.asset_name_shoval
            },
            callback: function (r) {
                if (r.message && r.message.item_code) {
                    if (row.item_name_excavator !== r.message.item_code) {
                        frappe.model.set_value(cdt, cdn, 'item_name_excavator', r.message.item_code);
                    }
                } else {
                    frappe.model.set_value(cdt, cdn, 'item_name_excavator', null);
                    frappe.msgprint(__('Item Code not found for selected Asset.'));
                }
            }
        });
    },
    tub_factor: function (frm, cdt, cdn) {
        calculate_bcms(cdt, cdn);
    },
    loads: function (frm, cdt, cdn) {
        calculate_bcms(cdt, cdn);
    }
});

function update_tub_factor_doc_link(frm, cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn);
    if (row.item_name && row.mat_type) {
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Tub Factor',
                filters: { item_name: row.item_name, mat_type: row.mat_type },
                fields: ['name', 'tub_factor'],
                limit_page_length: 1
            },
            callback: function (r) {
                if (r.message && r.message.length > 0) {
                    const tubFactorDoc = r.message[0];
                    frappe.model.set_value(cdt, cdn, 'tub_factor_doc_link', tubFactorDoc.name);
                    frappe.model.set_value(cdt, cdn, 'tub_factor', tubFactorDoc.tub_factor);
                } else {
                    frappe.msgprint(__('No Tub Factor found for the selected Item Name and Material Type.'));
                    frappe.model.set_value(cdt, cdn, 'tub_factor_doc_link', null);
                    frappe.model.set_value(cdt, cdn, 'tub_factor', null);
                }
            }
        });
    } else {
        frappe.model.set_value(cdt, cdn, 'tub_factor_doc_link', null);
        frappe.model.set_value(cdt, cdn, 'tub_factor', null);
    }
    frm.refresh_field('truck_loads');
}

function populate_dozer_production_table(frm) {
    if (frm.doc.location) {
        frappe.call({
            method: "is_production.production.doctype.hourly_production.hourly_production.fetch_dozer_production_assets",
            args: { location: frm.doc.location },
            callback: function (r) {
                if (r.message && r.message.length > 0) {
                    frm.clear_table("dozer_production");
                    r.message.forEach(asset => {
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
        frappe.model.set_value(cdt, cdn, 'bcms', loads * tub_factor);
    } else {
        frappe.model.set_value(cdt, cdn, 'bcms', null);
    }
}
