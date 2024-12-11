// Helper Function: Set Field Options
function set_field_options(frm, fieldname, options) {
    frm.set_df_property(fieldname, 'options', options.join('\n'));
}

// Fetch Monthly Production Planning
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
            },
            error: function () {
                frappe.msgprint(__('Failed to fetch monthly production planning.'));
            }
        });
    } else {
        frappe.msgprint(__('Location and Production Date are required to fetch monthly production planning.'));
    }
}

// Populate Truck Loads Table
function populate_truck_loads(frm) {
    if (frm.doc.location) {
        frappe.confirm(__('This will clear and repopulate the Truck Loads table. Do you want to continue?'), function () {
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Asset',
                    fields: ['asset_name', 'item_name'], // Fetch both asset_name and item_name
                    filters: [
                        ['location', '=', frm.doc.location],
                        ['asset_category', 'in', ['ADT', 'RIGID']], // Filter for ADT and RIGID categories
                        ['docstatus', '=', 1] // Only submitted assets
                    ],
                    order_by: 'asset_name asc'
                },
                callback: function (r) {
                    if (r.message && r.message.length > 0) {
                        frm.clear_table('truck_loads');
                        r.message.forEach(asset => {
                            const row = frm.add_child('truck_loads');
                            row.asset_name_truck = asset.asset_name; // Populate asset_name_truck
                            row.item_name = asset.item_name; // Populate item_name
                        });
                        frm.refresh_field('truck_loads');
                    } else {
                        frappe.msgprint(__('No ADT or RIGID assets found for the selected location.'));
                    }
                },
                error: function () {
                    frappe.msgprint(__('Failed to fetch assets for Truck Loads.'));
                }
            });
        });
    } else {
        frappe.msgprint(__('Please select a location to populate Truck Loads.'));
    }
}

// Recalculate BCMs
function calculate_bcms(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (row.loads && row.tub_factor) {
        frappe.model.set_value(cdt, cdn, 'bcms', row.loads * row.tub_factor);
    }
}

// Parent Doctype: Hourly Production
frappe.ui.form.on('Hourly Production', {
    location: function (frm) {
        fetch_monthly_production_planning(frm);
        populate_truck_loads(frm);
    },
    prod_date: fetch_monthly_production_planning,
    shift_system: function (frm) {
        const options = frm.doc.shift_system === '2x12Hour'
            ? ['Day', 'Night']
            : frm.doc.shift_system === '3x8Hour'
                ? ['Morning', 'Afternoon', 'Night']
                : [];
        set_field_options(frm, 'shift', options);
        frm.set_value('shift', ''); // Reset the shift
    },
    shift: function (frm) {
        if (frm.doc.shift_system) {
            const shift_hours = frm.doc.shift_system === '2x12Hour' ? 12 : 8;
            const options = Array.from({ length: shift_hours }, (_, i) => `${frm.doc.shift}-${i + 1}`);
            set_field_options(frm, 'shift_num_hour', options);
        }
        frm.set_value('shift_num_hour', ''); // Reset shift_num_hour
    },
    shift_num_hour: function (frm) {
        if (frm.doc.shift && frm.doc.shift_num_hour) {
            frappe.call({
                method: 'is_production.production.doctype.hourly_production.hourly_production.get_hour_slot',
                args: {
                    shift: frm.doc.shift,
                    shift_num_hour: frm.doc.shift_num_hour
                },
                callback: function (r) {
                    frm.set_value('hour_slot', r.message || null);
                },
                error: function () {
                    frappe.msgprint(__('Failed to fetch hour slot.'));
                }
            });
        }
    },
   setup: function (frm) {
    frm.fields_dict['truck_loads'].grid.get_field('asset_name_shoval').get_query = function () {
        return {
            query: 'is_production.production.doctype.hourly_production.hourly_production.get_assets',
            filters: JSON.stringify({
                location: frm.doc.location,
                asset_category: 'Excavator' // Single category filter
            })
        };
    };

    frm.fields_dict['truck_loads'].grid.get_field('asset_name_truck').get_query = function () {
        return {
            query: 'is_production.production.doctype.hourly_production.hourly_production.get_assets',
            filters: JSON.stringify({
                location: frm.doc.location,
                asset_category: ['ADT', 'RIGID'] // Multiple categories
            })
        };
    };
}
});

// Child Doctype: Truck Loads
frappe.ui.form.on('Truck Loads', {
    asset_name_truck: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.asset_name_truck) {
            frappe.db.get_value('Asset', row.asset_name_truck, 'item_name', (r) => {
                if (r) {
                    frappe.model.set_value(cdt, cdn, 'item_name', r.item_name);
                }
            });
        }
    },
    mat_type: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.item_name && row.mat_type) {
            frappe.call({
                method: 'is_production.production.doctype.hourly_production.hourly_production.get_tub_factor',
                args: {
                    item_name: row.item_name,
                    mat_type: row.mat_type
                },
                callback: function (r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'tub_factor', r.message.tub_factor);
                        frappe.model.set_value(cdt, cdn, 'tub_factor_doc_link', r.message.tub_factor_doc_link);
                    }
                }
            });
        }
    },
    loads: calculate_bcms,
    tub_factor: calculate_bcms
});
