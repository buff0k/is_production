// apps/is_production/public/js/hourly_production.js

// ——————————————————————
// Guard the onboarding tour stub
// ——————————————————————
if (frappe.ui && frappe.ui.init_onboarding_tour) {
    const _origOnboarding = frappe.ui.init_onboarding_tour;
    frappe.ui.init_onboarding_tour = function() {
        if (document.querySelector('.onboarding-tour-container')) {
            _origOnboarding.apply(this, arguments);
        }
    };
}

// ——————————————————————
// Utility: set day_number
// ——————————————————————
function set_day_number(frm) {
    if (frm.doc.prod_date) {
        frm.set_value('day_number', new Date(frm.doc.prod_date).getDate());
    }
}

// ——————————————————————
// Form Events
// ——————————————————————
frappe.ui.form.on('Hourly Production', {
    setup(frm) {
        if (frm.fields_dict.truck_loads?.grid) {
            frm.fields_dict.truck_loads.grid
                .get_field('asset_name_shoval').get_query = () => ({
                    filters: {
                        docstatus: 1,
                        asset_category: 'Excavator',
                        location: frm.doc.location
                    }
                });
        }
    },
    location(frm) {
        fetch_monthly_production_plan(frm);
        populate_truck_loads_and_lookup(frm);
        populate_dozer_production_table(frm);
    },
    prod_date(frm) {
        set_day_number(frm);
        fetch_monthly_production_plan(frm);
    },
    shift_system(frm) {
        update_shift_options(frm);
    },
    shift(frm) {
        update_shift_num_hour_options(frm);
    },
    shift_num_hour(frm) {
        update_hour_slot(frm);
    },
    after_save(frm) {
        frm.reload_doc();
    },
    // New: button handler to update hourly references for last 30 days
    update_hourly_references(frm) {
        frappe.call({
            method: 'is_production.production.doctype.hourly_production.hourly_production.update_hourly_references',
            args: {},
            callback: r => {
                if (r.exc) {
                    frappe.msgprint(__('Error: {0}', [r.exc]));
                } else {
                    frappe.msgprint(__('Updated {0} records', [r.message.updated]));
                    frm.reload_doc();
                }
            }
        });
    }
});

// ——————————————————————
// CORE: fetch MPP by date range & populate child ref
// ——————————————————————
function fetch_monthly_production_plan(frm) {
    const { location, prod_date } = frm.doc;
    if (!location || !prod_date) return;

    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Monthly Production Planning',
            fields: ['name', 'shift_system'],
            filters: [
                ['location',              '=', location],
                ['prod_month_start_date', '<=', prod_date],
                ['prod_month_end_date',   '>=', prod_date]
            ],
            order_by: 'prod_month_start_date asc',
            limit_page_length: 1
        },
        callback(r) {
            if (!r.message?.length) {
                frappe.msgprint(__('No plan found for {0} at {1}', [prod_date, location]), 'Validation');
                return;
            }
            const planSummary = r.message[0];

            frm.set_value('month_prod_planning', planSummary.name);
            frm.set_value('shift_system',        planSummary.shift_system);
            update_shift_options(frm);

            // fetch full plan doc to find the matching child row
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Monthly Production Planning',
                    name: planSummary.name
                },
                callback(r2) {
                    const mpp = r2.message;
                    if (!mpp) {
                        frappe.msgprint(__('Failed to load plan {0}', [planSummary.name]), 'Error');
                        return;
                    }

                    console.log('Monthly Production Planning:', mpp);
                    console.table(mpp.month_prod_days || []);

                    // match on shift_start_date
                    const match = (mpp.month_prod_days || []).find(row =>
                        row.shift_start_date === prod_date
                    );

                    if (match) {
                        frm.set_value('monthly_production_child_ref', match.hourly_production_reference);

                        // persist only if document already exists
                        if (!frm.is_new()) {
                            frappe.db.set_value(
                                frm.doc.doctype,
                                frm.doc.name,
                                'monthly_production_child_ref',
                                match.hourly_production_reference
                            ).then(() => {
                                console.log('Persisted monthly_production_child_ref:', match.hourly_production_reference);
                            });
                        }
                    } else {
                        frappe.msgprint(
                            __('No entry for shift_start_date {0} in month_prod_days of {1}', [prod_date, planSummary.name]),
                            'Validation'
                        );
                    }

                    populate_mining_areas(frm, mpp.mining_areas || []);
                }
            });
        }
    });
}

// ——————————————————————
// MINING AREAS
// ——————————————————————
function populate_mining_areas(frm, areas) {
    frm.clear_table('mining_areas_options');
    areas.forEach(a => {
        const row = frm.add_child('mining_areas_options');
        frappe.model.set_value(row.doctype, row.name, 'mining_areas', a.mining_areas);
    });
    frm.refresh_field('mining_areas_options');
}

// ——————————————————————
// TRUCK LOADS
// ——————————————————————
function populate_truck_loads_and_lookup(frm) {
    if (!frm.doc.location) return;
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Asset',
            fields: ['asset_name','item_name'],
            filters: [
                ['location','=', frm.doc.location],
                ['asset_category','in',['ADT','RIGID']],
                ['docstatus','=',1]
            ],
            order_by: 'asset_name asc'
        },
        callback(r) {
            frm.clear_table('truck_loads');
            (r.message||[]).forEach(asset => {
                const row = frm.add_child('truck_loads');
                frappe.model.set_value(row.doctype, row.name, 'asset_name_truck', asset.asset_name);
                frappe.model.set_value(row.doctype, row.name, 'item_name', asset.item_name || '');
            });
            frm.refresh_field('truck_loads');
        }
    });
}

// ——————————————————————
// DOZER PRODUCTION
// ——————————————————————
function populate_dozer_production_table(frm) {
    if (!frm.doc.location) return;
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Asset',
            fields: ['name as asset_name'],
            filters: {
                location: frm.doc.location,
                asset_category: 'Dozer',
                docstatus: 1
            }
        },
        callback(r) {
            frm.clear_table('dozer_production');
            (r.message||[]).forEach(asset => {
                const row = frm.add_child('dozer_production');
                row.asset_name    = asset.asset_name;
                row.bcm_hour      = 0;
                row.dozer_service = 'No Dozing';
            });
            frm.refresh_field('dozer_production');
        }
    });
}

// ——————————————————————
// TUB FACTOR & BCMS
// ——————————————————————
frappe.ui.form.on('Truck Loads', {
    item_name: _update_tub_factor,
    mat_type:  _update_tub_factor,
    asset_name_shoval(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        if (!row.asset_name_shoval) {
            frappe.model.set_value(cdt, cdn, 'item_name_excavator', null);
            return;
        }
        frappe.call({
            method: 'frappe.client.get',
            args: { doctype:'Asset', name: row.asset_name_shoval },
            callback(r) {
                frappe.model.set_value(cdt, cdn, 'item_name_excavator', r.message?.item_code || null);
            }
        });
    },
    tub_factor: _calculate_bcms,
    loads:      _calculate_bcms
});

function _update_tub_factor(frm, cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn);
    if (!row.item_name || !row.mat_type) return;
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype:'Tub Factor',
            filters:{ item_name: row.item_name, mat_type: row.mat_type },
            fields:['name','tub_factor'], limit_page_length:1
        },
        callback(r) {
            const doc = r.message[0];
            if (doc) {
                frappe.model.set_value(cdt, cdn, 'tub_factor_doc_link', doc.name);
                frappe.model.set_value(cdt, cdn, 'tub_factor', doc.tub_factor);
            } else {
                frappe.msgprint(__('No Tub Factor found'), 'Validation');
                frappe.model.set_value(cdt, cdn, 'tub_factor_doc_link', null);
                frappe.model.set_value(cdt, cdn, 'tub_factor', null);
            }
            frm.refresh_field('truck_loads');
        }
    });
}

function _calculate_bcms(frm, cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn);
    const loads = parseFloat(row.loads), tf = parseFloat(row.tub_factor);
    frappe.model.set_value(cdt, cdn, 'bcms', (!isNaN(loads) && !isNaN(tf)) ? loads * tf : null);
}

// ——————————————————————
// SHIFT HELPERS
// ——————————————————————
function update_shift_options(frm) {
    let opts = [];
    if (frm.doc.shift_system === '2x12Hour') {
        opts = ['Day', 'Night'];
    } else if (frm.doc.shift_system === '3x8Hour') {
        opts = ['Morning', 'Afternoon', 'Night'];
    }
    _set_options(frm, 'shift', opts);
    frm.set_value('shift', null);
}

function update_shift_num_hour_options(frm) {
    const s = frm.doc.shift;
    const sys = frm.doc.shift_system;
    let count;
    if (s === 'Day') {
        count = 12;
    } else if (s === 'Night') {
        count = (sys === '2x12Hour') ? 12 : 8;
    } else {
        // Morning or Afternoon in a 3×8 system
        count = 8;
    }
    const opts = Array.from({ length: count }, (_, i) => `${s}-${i + 1}`);
    _set_options(frm, 'shift_num_hour', opts);
    frm.set_value('shift_num_hour', null);
}

function update_hour_slot(frm) {
    // split e.g. "Day-1" → ["Day","1"]
    const [s, i] = (frm.doc.shift_num_hour || '').split('-');
    const idx = parseInt(i, 10);
    if (!s || isNaN(idx)) {
        return;
    }

    // 1) Populate the sort-key (read-only field)
    frm.set_value('hour_sort_key', idx);

    // 2) Compute the raw start hour
    const baseHour =
        (s === 'Day' || s === 'Morning')               ?  6  :
        (s === 'Afternoon')                            ? 14  :
        (s === 'Night' && frm.doc.shift_system === '2x12Hour') ? 18  :
                                                        22;
    const rawStart = baseHour + (idx - 1);

    // 3) Wrap into 0–23 for display
    let displayStart = rawStart;
    if (displayStart >= 24) {
        displayStart -= 24;
    }

    // 4) Compute and wrap end hour
    let displayEnd = displayStart + 1;
    if (displayEnd >= 24) {
        displayEnd -= 24;
    }

    // 5) Format and set the label
    const fmt = h => `${h}:00`;
    frm.set_value('hour_slot', `${fmt(displayStart)}-${fmt(displayEnd)}`);
}

function _set_options(frm, field, opts) {
    if (frm.fields_dict[field]) {
        frm.set_df_property(field, 'options', opts.join('\n'));
    }
}
