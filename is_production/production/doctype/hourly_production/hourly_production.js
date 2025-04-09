// Copyright (c) 2025, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('Hourly Production', {
    // Setup: Ensure form initializes correctly
    setup: function (frm) {
        if (frm.fields_dict['truck_loads']?.grid) {
            frm.fields_dict['truck_loads'].grid.get_field('asset_name_shoval').get_query = function () {
                return {
                    filters: {
                        docstatus: 1,
                        asset_category: 'Excavator',
                        location: frm.doc.location  // Ensures asset's location equals parent doc location
                    }
                };
            };
        }
    },

    location: function (frm) {
        fetch_monthly_production_planning(frm);
        populate_truck_loads_and_lookup(frm);
        populate_dozer_production_table(frm);
        // Only auto-populate if the document is new
        if (frm.doc.__islocal) { 
            populate_truck_loads_and_lookup(frm);
        }
    },

    prod_date: function (frm) {
        fetch_monthly_production_planning(frm);
        // Derive the day number from prod_date and set the day_number field
        set_day_number(frm);
    },

    after_save: function (frm) {
        frm.reload_doc(); // Reload document to display updated unique_reference
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
        // Ensure unique_reference is visible when the document is refreshed
        if (!frm.is_new() && frm.doc.unique_reference) {
            frm.set_value('unique_reference', frm.doc.unique_reference);
        }
    }
});

// Helper function: Set field options
function set_field_options(frm, fieldname, options) {
    if (frm.fields_dict[fieldname]) {
        frm.set_df_property(fieldname, 'options', options.join('\n'));
    } else {
        console.warn(`Field "${fieldname}" not found.`);
    }
}

// Function to derive and set the day number from the prod_date field
function set_day_number(frm) {
    if (frm.doc.prod_date) {
        // Create a Date object from the prod_date string (expected format: YYYY-MM-DD)
        let prodDate = new Date(frm.doc.prod_date);
        // Get the day of the month (1-31)
        let dayNumber = prodDate.getDate();
        // Set the derived value in the day_number field
        frm.set_value('day_number', dayNumber);
    }
}

// Update shift options based on shift_system
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

// Update shift_num_hour options based on shift
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

// Update hour_slot based on shift_num_hour
function update_hour_slot(frm) {
    const shift_timings = {
        // 2x12Hour System
        ...Array.from({ length: 12 }, (_, i) => [`Day-${i + 1}`, `${6 + i}:00-${7 + i}:00`]).reduce((a, [k, v]) => {
            a[k] = v; return a;
        }, {}),
        ...Array.from({ length: 12 }, (_, i) => [`Night-${i + 1}`, `${(18 + i) % 24}:00-${(19 + i) % 24}:00`]).reduce((a, [k, v]) => {
            a[k] = v; return a;
        }, {}),
        // 3x8Hour System
        ...Array.from({ length: 8 }, (_, i) => [`Morning-${i + 1}`, `${6 + i}:00-${7 + i}:00`]).reduce((a, [k, v]) => {
            a[k] = v; return a;
        }, {}),
        ...Array.from({ length: 8 }, (_, i) => [`Afternoon-${i + 1}`, `${14 + i}:00-${15 + i}:00`]).reduce((a, [k, v]) => {
            a[k] = v; return a;
        }, {}),
        ...Array.from({ length: 8 }, (_, i) => [`Night-${i + 1}`, `${(22 + i) % 24}:00-${(23 + i) % 24}:00`]).reduce((a, [k, v]) => {
            a[k] = v; return a;
        }, {})
    };

    const timing = shift_timings[frm.doc.shift_num_hour];

    if (!timing) {
        frappe.msgprint(__('Please select a valid shift number hour.'), 'Validation Error');
        return;
    }

    frm.set_value('hour_slot', timing);
}

// Fetch monthly production planning
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
                    frm.set_value('month_prod_planning', plan.name);
                    frm.set_value('shift_system', plan.shift_system || null);
                    update_doc_name(frm);
                } else {
                    frm.set_value('month_prod_planning', null);
                    frm.set_value('shift_system', null);
                    frappe.msgprint(__('No Monthly Production Planning document found for the selected location and production date.'));
                }
            }
        });
    }
}

// Populate truck loads table
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
                        // Only set what’s relevant here
                        frappe.model.set_value(row.doctype, row.name, 'asset_name_truck', asset.asset_name);
                        frappe.model.set_value(row.doctype, row.name, 'item_name', asset.item_name || "");
                        // Do NOT touch asset_name_shoval or item_name_excavator here
                    });
                    frm.refresh_field('truck_loads');
                } else {
                    frappe.msgprint(__('No assets found for the selected location.'));
                }

                suppress_excavator_autofill = false;  // done
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
                   // Only set if the value has changed
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

    // Check if required fields are present
    if (row.item_name && row.mat_type) {
        // Call server to find matching Tub Factor document
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Tub Factor',
                filters: {
                    item_name: row.item_name,
                    mat_type: row.mat_type
                },
                fields: ['name', 'tub_factor'],
                limit_page_length: 1
            },
            callback: function (r) {
                if (r.message && r.message.length > 0) {
                    const tubFactorDoc = r.message[0];
                    // Set the actual document name in tub_factor_doc_link
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
        // Clear fields if necessary input is missing
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
                        row.bcm_hour = 0; // Default bcm_hour value
                        row.dozer_service = "No Dozing"; // Default selection
                    });
                    frm.refresh_field("dozer_production");
                } else {
                    frappe.msgprint(__("No Dozer assets found for the selected location."));
                }
            }
        });
    }
}

// Helper function to calculate and set `bcms`
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
