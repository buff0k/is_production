frappe.ui.form.on('Hourly Production', {
    // Setup: Ensure form initializes correctly
    setup: function (frm) {
        if (frm.fields_dict['truck_loads']?.grid) {
            frm.fields_dict['truck_loads'].grid.get_field('asset_name_shoval').get_query = function () {
                return {
                    filters: {
                        docstatus: 1,
                        asset_category: 'Excavator'
                    }
                };
            };
        }
    },

    location: function (frm) {
        fetch_monthly_production_planning(frm);
        populate_truck_loads_and_lookup(frm);
    },

    prod_date: function (frm) {
        fetch_monthly_production_planning(frm);
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

    before_save: function (frm) {
        // Fetch the unique_reference from the server before saving
        frappe.call({
            method: 'is_production.production.doctype.hourly_production.hourly_production.get_unique_reference',
            args: {
                doc: frm.doc
            },
            callback: function (r) {
                if (r.message) {
                    frm.set_value('unique_reference', r.message); // Set value in the form
                    frm.set_value('name', r.message); // Set as the document name
                } else {
                    frappe.msgprint(__('Unable to generate Unique Reference. Please try again.'), 'Validation Error');
                    frappe.validated = false;
                }
            },
            async: false
        });

        if (!frm.doc.unique_reference) {
            frappe.msgprint(__('Unique Reference field is required to save the document.'), 'Validation Error');
            frappe.validated = false; // Prevent save if unique_reference is missing
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
            method: 'is_production.production.doctype.hourly_production.hourly_production.fetch_monthly_production_plan',
            args: {
                location: frm.doc.location,
                prod_date: frm.doc.prod_date
            },
            callback: function (r) {
                frm.set_value('month_prod_planning', r.message || null);
                update_doc_name(frm);
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
                        row.asset_name_truck = asset.asset_name;
                        row.item_name = asset.item_name || "Unknown Model";
                        frappe.model.set_value(row.doctype, row.name, 'asset_name_truck', asset.asset_name);
                        frappe.model.set_value(row.doctype, row.name, 'item_name', asset.item_name || "Unknown Model");
                    });
                    frm.refresh_field('truck_loads');
                } else {
                    frappe.msgprint(__('No assets found for the selected location.'));
                }
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
    }
});

function update_tub_factor_doc_link(frm, cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn);

    if (row.item_name && row.mat_type) {
        // Remove spaces around the hyphen when generating the link
        row.tub_factor_doc_link = `${row.item_name}-${row.mat_type}`;
        frappe.model.set_value(cdt, cdn, 'tub_factor_doc_link', row.tub_factor_doc_link);

        // Fetch the tub_factor value
        frappe.call({
            method: 'frappe.client.get_value',
            args: {
                doctype: 'Tub Factor',
                filters: { tub_factor_lookup: row.tub_factor_doc_link },
                fieldname: 'tub_factor'
            },
            callback: function (r) {
                if (r.message) {
                    frappe.model.set_value(cdt, cdn, 'tub_factor', r.message.tub_factor);
                } else {
                    frappe.msgprint(__('Tub Factor not found for the selected Item Name and Material Type.'));
                    frappe.model.set_value(cdt, cdn, 'tub_factor', null);
                }
            }
        });
    } else {
        // Clear the fields if item_name or mat_type is missing
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

// Trigger on location field change
frappe.ui.form.on("Hourly Production", {
    location: function (frm) {
        fetch_monthly_production_planning(frm);
        populate_truck_loads_and_lookup(frm);
        populate_dozer_production_table(frm);
    }
});

// Update bcm_hour based on dozer_service selection
frappe.ui.form.on("Dozer Production", {
    dozer_service: function (frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        const service_bcm_map = {
            "No Dozing": 0,
            "Tip Dozing": 0,
            "Production Dozing-50m": 180,
            "Production Dozing-100m": 150,
            "Levelling": 0
        };

        row.bcm_hour = service_bcm_map[row.dozer_service] || 0; // Set based on mapping
        frappe.model.set_value(cdt, cdn, "bcm_hour", row.bcm_hour);
        frm.refresh_field("dozer_production");
    }
});