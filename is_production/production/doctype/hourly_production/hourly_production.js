// apps/is_production/public/js/hourly_production.js

// ——————————————————————
// Guard the onboarding tour stub
// ——————————————————————
if (frappe.ui && frappe.ui.init_onboarding_tour) {
    const _origOnboarding = frappe.ui.init_onboarding_tour;
    frappe.ui.init_onboarding_tour = function() {
        const container = document.querySelector('.onboarding-tour-container');
        if (container) {
            try {
                _origOnboarding.apply(this, arguments);
            } catch (e) {
                console.warn('Onboarding tour init skipped:', e);
            }
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
// Sync MTD Data from Monthly Production Planning
// ——————————————————————
function sync_mtd_data(frm) {
    const mpp = frm.doc.month_prod_planning;
    if (!mpp) return;

    frappe.call({
        method: 'is_production.production.doctype.monthly_production_planning.monthly_production_planning.update_mtd_production',
        args: { name: mpp },
        callback: () => {
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Monthly Production Planning',
                    name: mpp,
                    fields: [
                        'monthly_target_bcm',
                        'target_bcm_day',
                        'target_bcm_hour',
                        'month_act_ts_bcm_tallies',
                        'month_act_dozing_bcm_tallies',
                        'monthly_act_tally_survey_variance',
                        'month_actual_bcm',
                        'mtd_bcm_day',
                        'mtd_bcm_hour',
                        'month_forecated_bcm'
                    ]
                },
                callback: r => {
                    const m = r.message || {};
                    [
                        'monthly_target_bcm',
                        'target_bcm_day',
                        'target_bcm_hour',
                        'month_act_ts_bcm_tallies',
                        'month_act_dozing_bcm_tallies',
                        'monthly_act_tally_survey_variance',
                        'month_actual_bcm',
                        'mtd_bcm_day',
                        'mtd_bcm_hour',
                        'month_forecated_bcm'
                    ].forEach(field => frm.set_value(field, m[field]));
                    frm.refresh_field([
                        'monthly_target_bcm',
                        'target_bcm_day',
                        'target_bcm_hour',
                        'month_act_ts_bcm_tallies',
                        'month_act_dozing_bcm_tallies',
                        'monthly_act_tally_survey_variance',
                        'month_actual_bcm',
                        'mtd_bcm_day',
                        'mtd_bcm_hour',
                        'month_forecated_bcm'
                    ]);
                }
            });
        }
    });
}

// ——————————————————————
// Populate MPP Child Ref & Mining Areas
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
                ['location', '=', location],
                ['prod_month_start_date', '<=', prod_date],
                ['prod_month_end_date', '>=', prod_date]
            ],
            order_by: 'prod_month_start_date asc',
            limit_page_length: 1
        },
        callback: r => {
            if (!r.message?.length) return;
            const plan = r.message[0];
            frm.set_value('month_prod_planning', plan.name);
            frm.set_value('shift_system', plan.shift_system);
            update_shift_options(frm);

            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Monthly Production Planning',
                    name: plan.name
                },
                callback: r2 => {
                    const mpp = r2.message;
                    const match = (mpp.month_prod_days || [])
                        .find(d => d.shift_start_date === frm.doc.prod_date);
                    if (match) {
                        frm.set_value('monthly_production_child_ref', match.hourly_production_reference);
                     }
                    populate_mining_areas(frm, mpp.mining_areas || []);
                    const geoRows = mpp.geo_mat_layer || [];
                    const geoDescriptions = geoRows.map(row => row.geo_ref_description);
                    frm.truck_geo_options_str = geoDescriptions.join('\n');
                    update_truck_geo_options(frm);
                }
            });
        }
    });
}

function populate_mining_areas(frm, areas) {
    frm.clear_table('mining_areas_options');
    areas.forEach(a => {
        const row = frm.add_child('mining_areas_options');
        frappe.model.set_value(row.doctype, row.name, 'mining_areas', a.mining_areas);
    });
    frm.refresh_field('mining_areas_options');
    update_mining_area_trucks_options(frm);
    update_mining_area_dozer_options(frm);
}

// ——————————————————————
// Dynamic options for mining_areas_trucks
// ——————————————————————
function update_mining_area_trucks_options(frm) {
  const opts = (frm.doc.mining_areas_options || [])
    .map(r => r.mining_areas)
    .filter(v => v);

  // array of options, blank first
  const options_list = [''].concat(opts);

  // update the child-DocType’s DocField
  frappe.meta.get_docfield('Truck Loads', 'mining_areas_trucks')
    .options = options_list;

  // re-render the entire child table
  frm.refresh_field('truck_loads');
}



// ——————————————————————
// Dynamic options for mining_areas_dozer_child
// ——————————————————————
function update_mining_area_dozer_options(frm) {
  const opts = (frm.doc.mining_areas_options || [])
    .map(r => r.mining_areas)
    .filter(v => v);

  const options_list = [''].concat(opts);

  frappe.meta.get_docfield('Dozer Production', 'mining_areas_dozer_child')
    .options = options_list;

  frm.refresh_field('dozer_production');
}


// ——————————————————————
// Geo layer dropdown helper
// ——————————————————————
function update_dozer_geo_options(frm) {
  const opts = frm.dozer_geo_options_str
    ? frm.dozer_geo_options_str.split('\n').filter(v => v)
    : [];
  const options_list = [''].concat(opts);

  frappe.meta.get_docfield('Dozer Production', 'dozer_geo_mat_layer')
    .options = options_list;

  frm.refresh_field('dozer_production');
}

// Geo layer dropdown helper for trucks
function update_truck_geo_options(frm) {
  const opts = frm.truck_geo_options_str
    ? frm.truck_geo_options_str.split('\n').filter(v => v)
    : [];
  const options_list = [''].concat(opts);

  frappe.meta.get_docfield('Truck Loads', 'geo_mat_layer_truck')
    .options = options_list;

  frm.refresh_field('truck_loads');
}
// ——————————————————————
// Form Events
// ——————————————————————
frappe.ui.form.on('Mining Areas Options', {
    mining_areas(frm) {
        update_mining_area_trucks_options(frm);
        update_mining_area_dozer_options(frm);
    },
    refresh(frm) {
        update_mining_area_trucks_options(frm);
        update_mining_area_dozer_options(frm);
    }
});

frappe.ui.form.on('Hourly Production', {
    setup(frm) {
        // ——————————————————————————————
        // 1) Prime child‐table selects with a blank entry
        // ——————————————————————————————
        const truckGrid = frm.fields_dict.truck_loads?.grid;
        if (truckGrid) {
        // blank placeholder for mining_areas_trucks
        truckGrid.update_docfield_property(
            'mining_areas_trucks',
            'options',
            '\n'
        );
        // blank placeholder for geo_mat_layer_truck
        truckGrid.update_docfield_property(
            'geo_mat_layer_truck',
            'options',
            '\n'
        );
        // your existing asset_name_shoval query
        truckGrid
            .get_field('asset_name_shoval')
            .get_query = () => ({
            filters: {
                docstatus: 1,
                asset_category: 'Excavator',
                location: frm.doc.location
            }
            });
        }

        const dozerGrid = frm.fields_dict.dozer_production?.grid;
        if (dozerGrid) {
        // blank placeholder for mining_areas_dozer_child
        dozerGrid.update_docfield_property(
            'mining_areas_dozer_child',
            'options',
            '\n'
        );
        // blank placeholder for dozer_geo_mat_layer
        dozerGrid.update_docfield_property(
            'dozer_geo_mat_layer',
            'options',
            '\n'
        );
        }

        // ——————————————————————————————
        // 2) Now inject your real, dynamic options & rebuild inline editors
        // ——————————————————————————————
        update_mining_area_trucks_options(frm);
        update_mining_area_dozer_options(frm);
        update_dozer_geo_options(frm);
        update_truck_geo_options(frm);
    },

    refresh(frm) {
        if (!frm.is_new()) {
        //    sync_mtd_data(frm);
        }
        update_mining_area_trucks_options(frm);
        update_mining_area_dozer_options(frm);
        update_dozer_geo_options(frm);
        update_truck_geo_options(frm);
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
        // first, reload the doc so we pick up the new modified timestamp
        frm.reload_doc().then(() => {
            // now it’s safe to re-sync MtD and rebuild your selects
            sync_mtd_data(frm);
            update_mining_area_trucks_options(frm);
            update_mining_area_dozer_options(frm);
        });
    },


    truck_loads_add(frm) {
        update_mining_area_trucks_options(frm);
        update_truck_geo_options(frm);
    },

    update_hourly_references(frm) {
        frappe.call({
            method: 'is_production.doctype.hourly_production.hourly_production.update_hourly_references',
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
    },

    month_prod_planning(frm) {
        // only run on new docs when month_prod_planning is set
        if (!frm.is_new() || !frm.doc.month_prod_planning) return;

        frappe.call({
            method: 'frappe.client.get',
            args: {
                doctype: 'Monthly Production Planning',
                name: frm.doc.month_prod_planning
            },
            callback: function(r) {
                try {
                    const mppDoc = r.message || {};

                    // — Populate asset_name_shoval in truck_loads —
                    const prodTrucks = mppDoc.prod_trucks || [];
                    const confirmation = [];
                    (frm.doc.truck_loads || []).forEach(loadRow => {
                        const match = prodTrucks.find(pt =>
                            pt.asset_name === loadRow.asset_name_truck
                        );
                        const excav = match ? match.default_excavator : null;
                        frappe.model.set_value(
                            loadRow.doctype,
                            loadRow.name,
                            'asset_name_shoval',
                            excav
                        );
                        confirmation.push({
                            asset_name_truck: loadRow.asset_name_truck,
                            asset_name_shoval: excav
                        });
                    });
                    frm.refresh_field('truck_loads');
                    console.log('[asset_name_shoval populated]:', confirmation);

                    // — Build geo_ref_description options string —
                    const geoRows = mppDoc.geo_mat_layer || [];
                    const geoDescriptions = geoRows.map(row =>
                        row.geo_ref_description
                    );
                    console.log('[geo_ref_description array]:', geoDescriptions);

                    // Store newline-separated options for dozer
                    frm.dozer_geo_options_str = geoDescriptions.join('\n');

                    // Apply to existing and future dozer_production rows
                    update_dozer_geo_options(frm);

                    // In fetch_monthly_production_plan callback, after building geoDescriptions:
                    frm.truck_geo_options_str = geoDescriptions.join('\n');
                    update_truck_geo_options(frm);

                } catch (e) {
                    console.error('Error in month_prod_planning callback:', e);
                }
            }
        });
    },

    dozer_production_add(frm, cdt, cdn) {
        update_dozer_geo_options(frm);
    }
});

// ——————————————————————
// TRUCK LOADS: populate & lookup
// ——————————————————————
function populate_truck_loads_and_lookup(frm) {
    if (!frm.doc.location) return;
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Asset',
            fields: ['asset_name', 'item_name'],
            filters: [
                ['location', '=', frm.doc.location],
                ['asset_category', 'in', ['ADT','RIGID']],
                ['docstatus', '=', 1]
            ],
            order_by: 'asset_name asc'
        },
        callback: r => {
            frm.clear_table('truck_loads');
            (r.message || []).forEach(asset => {
                const row = frm.add_child('truck_loads');
                frappe.model.set_value(row.doctype, row.name, 'asset_name_truck', asset.asset_name);
                frappe.model.set_value(row.doctype, row.name, 'item_name', asset.item_name || '');
            });
            frm.refresh_field('truck_loads');
            update_mining_area_trucks_options(frm);

            // Only if month_prod_planning has been set
            if (frm.doc.month_prod_planning) {
                frappe.call({
                    method: 'frappe.client.get',
                    args: {
                        doctype: 'Monthly Production Planning',
                        name: frm.doc.month_prod_planning,
                        // fetch just the child‐table field
                        fields: ['prod_trucks']
                    },
                    callback: r2 => {
                        const prodTrucks = (r2.message && r2.message.prod_trucks) || [];
                        // extract asset_name from each child‐row
                        const names = prodTrucks.map(row => row.asset_name);
                        console.log('[Monthly Production → prod_trucks.asset_name]:', names);
                    }
                });
            }
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
            filters: { location: frm.doc.location, asset_category: 'Dozer', docstatus: 1 }
        },
        callback: r => {
            frm.clear_table('dozer_production');
            (r.message || []).forEach(asset => {
                const row = frm.add_child('dozer_production');
                row.asset_name = asset.asset_name;
                row.bcm_hour = 0;
                row.dozer_service = 'No Dozing';
            });
            frm.refresh_field('dozer_production');
            update_mining_area_dozer_options(frm);
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
            args: { doctype: 'Asset', name: row.asset_name_shoval },
            callback: r => {
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
            doctype: 'Tub Factor',
            filters: { item_name: row.item_name, mat_type: row.mat_type },
            fields: ['name', 'tub_factor'],
            limit_page_length: 1
        },
        callback: r => {
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
    const loads = parseFloat(row.loads);
    const tf = parseFloat(row.tub_factor);
    frappe.model.set_value(cdt, cdn, 'bcms',
        (!isNaN(loads) && !isNaN(tf)) ? loads * tf : null
    );
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
    const s   = frm.doc.shift;
    const sys = frm.doc.shift_system;
    let count;
    if (s === 'Day') {
        count = 12;
    } else if (s === 'Night') {
        count = (sys === '2x12Hour') ? 12 : 8;
    } else {
        count = 8;
    }
    const opts = Array.from({ length: count }, (_, i) => `${s}-${i + 1}`);
    _set_options(frm, 'shift_num_hour', opts);
    frm.set_value('shift_num_hour', null);
}

function update_hour_slot(frm) {
    const [s, i] = (frm.doc.shift_num_hour || '').split('-');
    const idx = parseInt(i, 10);
    if (!s || isNaN(idx)) return;
    frm.set_value('hour_sort_key', idx);

    let baseHour;
    if (s === 'Day' || s === 'Morning') {
        baseHour = 6;
    } else if (s === 'Afternoon') {
        baseHour = 14;
    } else if (s === 'Night' && frm.doc.shift_system === '2x12Hour') {
        baseHour = 18;
    } else {
        baseHour = 22;
    }

    const start = (baseHour + (idx - 1)) % 24;
    const end   = (start + 1) % 24;
    frm.set_value('hour_slot', `${start}:00-${end}:00`);
}

function _set_options(frm, field, opts) {
    if (frm.fields_dict[field]) {
        frm.set_df_property(field, 'options', opts.join('\n'));
    }
}
