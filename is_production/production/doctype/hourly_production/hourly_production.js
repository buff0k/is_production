/*
 * Offline Sync Capabilities
 * ------------------------
 * This form supports full offline functionality:
 * - Detects online/offline status automatically
 * - Caches form changes when offline
 * - Shows offline status indicator and controls
 * - Syncs changes automatically when back online
 * - Allows manual sync of cached changes
 * - Preserves all form fields and child tables when offline
 * - Provides UI feedback for offline state and sync operations
 */

// --- Offline status tag and sync popup ---
function showOfflineStatus(frm) {
    if (!frm) return;
    let tagId = 'offline-status-tag';
    let $tag = $('#' + tagId);
    // Use form header or wrapper for robustness
    let $header = frm.$wrapper.find('.form-title, .page-title') || frm.$wrapper;
    if (!window.HourlyProductionOffline.isOnline()) {
        if ($tag.length === 0) {
            let $el = $('<span id="' + tagId + '" class="indicator orange" style="margin-left:10px;">Offline</span>');
            if ($header.length) {
                $header.append($el);
            } else {
                frm.$wrapper.prepend($el);
            }
        }
    } else {
        $tag.remove();
    }
}

// Listen for online/offline events to update tag and show sync popup
function setupOfflineStatusEvents(frm) {
    window.addEventListener('offline', () => showOfflineStatus(frm));
    window.addEventListener('online', () => {
        showOfflineStatus(frm);
        // Wait for sync, then show popup
        window.HourlyProductionOffline.syncCachedDocs().then(() => {
            if (frappe.show_alert) {
                frappe.show_alert({
                    message: __('Offline changes synced!'),
                    indicator: 'green'
                });
            } else {
                frappe.msgprint(__('Offline changes synced!'));
            }
        });
    });
}
// Import offline sync utility
frappe.require('/assets/is_production/js/offline_sync.js');
//Complete table is working and no ui
// apps/is_production/public/js/hourly_production.js
// 
// ——————————————————————
// Guard the onboarding tour stub
// ——————————————————————
//utility
frappe.provide('is_production.ui');
console.log('HourlyProduction namespace initialized');

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

// UI Initialization Helpers
// UI Initialization Helpers
// UI State Management
let uiInitialized = false;
let pendingUIInitialization = false;

// Replace your existing initializeOrRefreshUI function with this:
function initializeOrRefreshUI(frm, forceRefresh = false) {
    // Skip if we don't have all required fields
    if (!frm.doc.location || !frm.doc.prod_date || !frm.doc.shift || !frm.doc.shift_num_hour || 
        (frm.is_new() && !frm.doc.shift_num_hour)) {
        return;
    }

    // If already initialized and not forcing a refresh, just call loadUI()
    if (uiInitialized && frm.hourlyProductionUI && !forceRefresh) {
        frm.hourlyProductionUI.loadUI();
        return;
    }

    // Prevent duplicate initializations
    if (pendingUIInitialization) return;
    pendingUIInitialization = true;

    loadUIWithDependencies(frm).then(() => {
        if (frm.doc.month_prod_planning) {
            return loadMPPAssignments(frm);
        }
    }).then(() => {
        createOrRefreshUI(frm);
      
        uiInitialized = true;
        pendingUIInitialization = false;
    }).catch(() => {
        pendingUIInitialization = false;
    });
}

function cleanupUIState(frm) {
    uiInitialized = false;
    pendingUIInitialization = false;
    if (frm.hourlyProductionUI) {
        // Call any cleanup method if it exists in your UI class
        if (typeof frm.hourlyProductionUI.cleanup === 'function') {
            frm.hourlyProductionUI.cleanup();
        }
        frm.hourlyProductionUI = null;
    }
}

function loadUIWithDependencies(frm) {
    return new Promise((resolve) => {
        if (window.hourlyProductionUICssLoaded && is_production.ui.HourlyProductionUI) {
            resolve();
            return;
        }
        
        frappe.require([
            '/assets/is_production/css/hourly_production_ui.css',
            '/assets/is_production/js/hourly_production_ui.js'
        ], () => {
            window.hourlyProductionUICssLoaded = true;
            resolve();
        });
    });
}


function loadMPPAssignments(frm) {
    return new Promise((resolve) => {
        if (!frm.doc.month_prod_planning) {
            resolve();
            return;
        }

        frappe.call({
            method: 'frappe.client.get',
            args: {
                doctype: 'Monthly Production Planning',
                name: frm.doc.month_prod_planning,
                fields: ['excavator_truck_assignments']
            },
            callback: function(r) {
                const mppDoc = r.message || {};
                frm.mppAssignments = {};
                
                (mppDoc.excavator_truck_assignments || []).forEach(assignment => {
                    if (assignment.truck && assignment.excavator) {
                        frm.mppAssignments[assignment.truck] = assignment.excavator;
                    }
                });
                
                console.log('MPP assignments loaded:', frm.mppAssignments);
                resolve();
            }
        });
    });
}

function createOrRefreshUI(frm) {
    if (frm.hourlyProductionUI) {
        frm.hourlyProductionUI.loadUI();
    } else {
        frm.hourlyProductionUI = new is_production.ui.HourlyProductionUI(frm);
    }
}

function applyMPPAssignments(frm) {
    (frm.doc.truck_loads || []).forEach(row => {
        if (!row.asset_name_shoval && frm.mppAssignments[row.asset_name_truck]) {
            frappe.model.set_value(
                row.doctype,
                row.name,
                'asset_name_shoval',
                frm.mppAssignments[row.asset_name_truck]
            );
        }
    });
}

// Define this EXACTLY as shown - at the TOP LEVEL of your file
function fetch_whatsapp_from_user(frm) {
    if (!frm.doc.owner) {
        frappe.msgprint(__("Please save the document first to associate with a user"));
        return;
    }

    frappe.call({
        method: 'frappe.client.get',
        args: {
            doctype: 'User',
            name: frm.doc.owner,
            fields: ['mobile_no', 'whatsapp_number']
        },
        callback: function(r) {
            if (r.message) {
                const user = r.message;
                const number = user.whatsapp_number || user.mobile_no;
                
                if (number) {
                    frm.set_value('whatsapp_recipient', number);
                    frappe.show_alert(__("WhatsApp number set from user profile"));
                } else {
                    frappe.msgprint(__("No WhatsApp number or mobile number found for this user"));
                }
            }
        }
    });
}



function get_previous_hour_excavator_assignments(frm) {
    // Ensure all required fields exist and are valid
    if (!frm.doc?.location || !frm.doc?.prod_date || !frm.doc?.shift || !frm.doc?.shift_num_hour) {
        console.log('Missing required fields:', {
            location: frm.doc?.location,
            prod_date: frm.doc?.prod_date,
            shift: frm.doc?.shift,
            shift_num_hour: frm.doc?.shift_num_hour
        });
        return Promise.resolve(null);
    }

    console.log('Current doc fields:', {
        location: frm.doc.location,
        prod_date: frm.doc.prod_date,
        shift: frm.doc.shift,
        shift_num_hour: frm.doc.shift_num_hour
    });

    // Parse current hour number from shift_num_hour (e.g., "Day-3" → 3)
    const shiftParts = frm.doc.shift_num_hour.split('-');
    if (shiftParts.length !== 2) {
        console.log('Invalid shift_num_hour format:', frm.doc.shift_num_hour);
        return Promise.resolve(null);
    }

    const currentHourNum = parseInt(shiftParts[1]);
    if (isNaN(currentHourNum)) {
        console.log('Invalid hour number in shift_num_hour:', shiftParts[1]);
        return Promise.resolve(null);
    }

    // Calculate previous hour number
    const prevHourNum = currentHourNum - 1;
    if (prevHourNum < 1) {
        console.log('First hour of shift - no previous hour');
        return Promise.resolve(null);
    }

    const prevShiftNum = `${frm.doc.shift}-${prevHourNum}`;
    console.log('Looking for previous hour with shift_num_hour:', prevShiftNum);

    let formattedDate;
    try {
        formattedDate = frappe.datetime.str_to_obj(frm.doc.prod_date);
        formattedDate = frappe.datetime.obj_to_str(formattedDate);
    } catch (e) {
        console.error('Error formatting date:', e);
        return Promise.resolve(null);
    }

    return new Promise((resolve) => {
        // Step 1: Get the previous Hourly Production doc name
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Hourly Production',
                filters: [
                    ['location', '=', frm.doc.location],
                    ['prod_date', '=', formattedDate],
                    ['shift', '=', frm.doc.shift],
                    ['shift_num_hour', '=', prevShiftNum]
                ],
                fields: ['name'],
                limit_page_length: 1
            },
            callback: function(r) {
                if (r.exc || !r.message || !r.message.length) {
                    console.log('No previous hour found or error:', r.exc || 'Not found');
                    return resolve(null);
                }

                const prevHourDoc = r.message[0];

                // Step 2: Get full document to access truck_loads
                frappe.call({
                    method: 'frappe.client.get',
                    args: {
                        doctype: 'Hourly Production',
                        name: prevHourDoc.name
                    },
                    callback: function(r2) {
                        const fullDoc = r2.message;
                        const assignments = {};

                        // Collect both excavator assignments AND mining areas
                        (fullDoc.truck_loads || []).forEach(row => {
                            if (row.asset_name_truck) {
                                assignments[row.asset_name_truck] = {
                                    excavator: row.asset_name_shoval || null,
                                    mining_area: row.mining_areas_trucks || null
                                };
                            }
                        });

                        console.log('Previous assignments with mining areas:', assignments);
                        resolve(Object.keys(assignments).length > 0 ? assignments : null);
                    }
                });
            }
        });
    });
}
// ——————————————————————
// Utility: set day_number
// ——————————————————————
function set_day_number(frm) {
    if (frm.doc.prod_date) {
        frm.set_value('day_number', new Date(frm.doc.prod_date).getDate());
        
    }
}

function calculate_excavators_count(frm) {
    const uniqueExcavators = new Set();
    
    // Loop through truck_loads table and collect unique excavators
    (frm.doc.truck_loads || []).forEach(row => {
        if (row.asset_name_shoval) {
            uniqueExcavators.add(row.asset_name_shoval);
        }
    });
    
    // Set the count to excavators_prod_num field
    frm.set_value('excavators_prod_num', uniqueExcavators.size);
    
    console.log('Unique excavators count:', uniqueExcavators.size);
}

// ——————————————————————
// Sync MTD Data from Monthly Production Planning
// ——————————————————————
// Silent version of sync_mtd_data that doesn't trigger form events
function sync_mtd_data_silent(frm) {
    const mpp = frm.doc.month_prod_planning;
    if (!mpp || !frm.new) return;

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
                    const fields = [
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
                    ];
                    
                    // Store original dirty state
                    const originalDirty = frm.dirty;
                    const originalUnsaved = frm.doc.__unsaved;
                    
                    // Update values directly without triggering events
                    fields.forEach(field => {
                        frm.doc[field] = m[field];
                    });
                    
                    // Restore original dirty state
                    frm.dirty = originalDirty;
                    frm.doc.__unsaved = originalUnsaved;
                    
                    // Refresh field display without triggering events
                    frm.refresh_field(fields);
                }
            });
        }
    });
}

// ——————————————————————
// Populate MPP Child Ref & Mining Areas
// ——————————————————————
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
            fields: ['name', 'shift_system', 'site_status'],
            filters: [
                ['location', '=', location],
                ['prod_month_start_date', '<=', prod_date],
                ['prod_month_end_date', '>=', prod_date],
                ['site_status', 'like', '%Producing%']
            ],
            order_by: 'prod_month_start_date asc',
            limit_page_length: 1
        },
        callback: r => {
            if (!r.message?.length) {
                // Display error message and clear prod_date field
                frappe.msgprint({
                    title: __('Production Not Available'),
                    message: __(`${location} is not producing for ${prod_date}`),
                    indicator: 'red'
                });
                frm.set_value('prod_date', '');
                return;
            }
            
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
                     if (frm.is_new()) {
                        const match = (mpp.month_prod_days || [])
                            .find(d => d.shift_start_date === frm.doc.prod_date);
                        if (match) {
                            frm.set_value('monthly_production_child_ref', match.hourly_production_reference);
                        }
                    }
                    populate_mining_areas(frm, mpp.mining_areas || []);
                    const geoRows = mpp.geo_mat_layer || [];
                    const geoDescriptions = geoRows.map(row => row.geo_ref_description);
                    frm.truck_geo_options_str = geoDescriptions.join('\n');

                    updateTruckGeoMaterialOptions(frm);
                }
            });
        }
    });
}

function populate_mining_areas(frm, areas) {
    frm.clear_table('mining_areas_options');

    // Step 1: Populate mining_areas_options table
    const areaValues = [];

    areas.forEach(a => {
        const areaValue = a.mining_areas || a.name || a;
        if (areaValue) {
            const row = frm.add_child('mining_areas_options');
            frappe.model.set_value(row.doctype, row.name, 'mining_areas', areaValue);
            areaValues.push(areaValue);
        }
    });

    frm.refresh_field('mining_areas_options');

    // Step 2: Populate ts_area_bcm_total table
    frm.clear_table('ts_area_bcm_total');
    areaValues.forEach(areaValue => {
        const tsRow = frm.add_child('ts_area_bcm_total');
        frappe.model.set_value(tsRow.doctype, tsRow.name, 'ts_area_options', areaValue);
        frappe.model.set_value(tsRow.doctype, tsRow.name, 'ts_area_bcm', 0); // Initialize with 0
        frappe.model.set_value(tsRow.doctype, tsRow.name, 'dozer_area_bcm', 0); // Initialize with 0
    });
    frm.refresh_field('ts_area_bcm_total');

    
    

    // Step 4: Update dynamic dropdowns
    update_mining_area_trucks_options(frm);
    update_mining_area_dozer_options(frm);

    // Step 5: If there's only one mining area, assign it to each truck and dozer
    if (areaValues.length === 1) {
        const defaultArea = areaValues[0];

        // Populate truck_loads[].mining_areas_trucks
        (frm.doc.truck_loads || []).forEach(row => {
            frappe.model.set_value(row.doctype, row.name, 'mining_areas_trucks', defaultArea);
        });
        frm.refresh_field('truck_loads');

        // Populate dozer_production[].mining_areas_dozer_child
        (frm.doc.dozer_production || []).forEach(row => {
            frappe.model.set_value(row.doctype, row.name, 'mining_areas_dozer_child', defaultArea);
        });
        frm.refresh_field('dozer_production');
    }
    
    // Step 6: Calculate initial totals
    calculate_ts_area_bcm_totals_silent(frm);
    
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
// ——————————————————————
// Geo layer dropdown helper - Modified to exclude Coal
// ——————————————————————
function update_dozer_geo_options(frm) {
    if (!frm.doc.month_prod_planning) return;

    frappe.call({
        method: 'frappe.client.get',
        args: {
            doctype: 'Monthly Production Planning',
            name: frm.doc.month_prod_planning,
            fields: ['geo_mat_layer']
        },
        callback: function(r) {
            if (r.message && r.message.geo_mat_layer) {
                const options = ['']; // Start with empty option
                
                r.message.geo_mat_layer.forEach(row => {
                    // Only add if geo_ref_description exists AND custom_material_type is NOT "Coal"
                    if (row.geo_ref_description && row.custom_material_type !== 'Coal') {
                        options.push(row.geo_ref_description);
                    }
                });

                // Update the dropdown options
                frm.dozer_geo_options_str = options.join('\n');
                frappe.meta.get_docfield('Dozer Production', 'dozer_geo_mat_layer')
                    .options = frm.dozer_geo_options_str;
                
                frm.refresh_field('dozer_production');
            }
        }
    });
}


function updateTruckGeoMaterialOptions(frm) {
  if (!frm.doc.month_prod_planning) return;

  frappe.call({
    method: 'frappe.client.get',
    args: {
      doctype: 'Monthly Production Planning',
      name: frm.doc.month_prod_planning,
      fields: ['geo_mat_layer']
    },
    callback: function(r) {
      if (r.message && r.message.geo_mat_layer) {
        // Create a map of geo_ref_description to custom_material_type
        frm.geoMaterialMap = {};
        const options = ['']; // Start with empty option
        const geoDescriptions = []; // Track descriptions for table population
        
        r.message.geo_mat_layer.forEach(row => {
          if (row.geo_ref_description) {
            options.push(row.geo_ref_description);
            geoDescriptions.push(row.geo_ref_description);
            frm.geoMaterialMap[row.geo_ref_description] = row.custom_material_type;
          }
        });

        // Update the dropdown options
        frm.truck_geo_options_str = options.join('\n');
        frappe.meta.get_docfield('Truck Loads', 'geo_mat_layer_truck')
          .options = frm.truck_geo_options_str;
        
        frm.refresh_field('truck_loads');

        // ===== MODIFIED CODE: Only populate table if empty or if it's a new document =====
        // Check if table is empty OR if we're in a new document
        const shouldPopulateTable = !frm.doc.geo_mat_total_bcm || 
                                   frm.doc.geo_mat_total_bcm.length === 0 || 
                                   frm.is_new();
        
        if (shouldPopulateTable) {
          // Clear existing geo_mat_total_bcm table
          frm.clear_table('geo_mat_total_bcm');
          
          // Add new rows for each geo description
          geoDescriptions.forEach(geoDescription => {
            const row = frm.add_child('geo_mat_total_bcm');
            frappe.model.set_value(row.doctype, row.name, 'geo_layer_options', geoDescription);
            // Initialize with 0 or any default value you prefer
            frappe.model.set_value(row.doctype, row.name, 'geo_bcm_total', 0);
          });
          
          frm.refresh_field('geo_mat_total_bcm');
        }
        // ===== END MODIFIED CODE =====
      }
    }
  });
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
            // 🕐 Enable full 24-hour time picker including midnight
        const timeFields = [
            'day_shift_start',
            'day_shift_end',
            'night_shift_start',
            'night_shift_end'
        ];

        timeFields.forEach(field => {
            if (frm.fields_dict[field] && frm.fields_dict[field].$input) {
                frm.fields_dict[field].$input.flatpickr({
                    enableTime: true,
                    noCalendar: true,
                    time_24hr: true,
                    enableSeconds: false,
                    allowInput: true,
                    minuteIncrement: 1
                });
            }
        });

        // Load offline sync utility (keep this line after picker setup)
        frappe.require('/assets/is_production/js/offline_sync.js');
 
        
        cleanupUIState(frm);
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
        updateTruckGeoMaterialOptions(frm);
        
    },
    
    onload_post_render(frm) {
    // This will trigger for both new and existing docs
    if (frm.is_new()) {
        cleanupUIState(frm);
    }

    // ✅ Restore locked hour_slot if it exists (prevents recalculation)
    if (frm.doc.locked_hour_slot && frm.doc.hour_slot !== frm.doc.locked_hour_slot) {
        frm.set_value('hour_slot', frm.doc.locked_hour_slot);
        frm.refresh_field('hour_slot');
        console.log('Restored locked hour slot:', frm.doc.locked_hour_slot);
    }

    frappe.require(['/assets/is_production/js/offline_sync.js'], function() {
        // Ensure offline sync is ready
        if (!window.HourlyProductionOffline) {
            console.error('Offline sync utility not loaded');
            return;
        }

        // Restore cached doc if offline and cached
        if (!window.HourlyProductionOffline.isOnline()) {
            const cached = window.HourlyProductionOffline.getCachedDocs().find(d => d.name === frm.doc.name);
            if (cached) {
                frappe.confirm(
                    __('You have unsynced offline changes for this record. Restore them?'),
                    () => {
                        frm.doc.truck_loads = cached.truck_loads || [];
                        frm.doc.dozer_production = cached.dozer_production || [];
                        frm.doc.mining_areas_options = cached.mining_areas_options || [];
                        frm.doc.ts_area_bcm_total = cached.ts_area_bcm_total || [];
                        frm.doc.geo_mat_total_bcm = cached.geo_mat_total_bcm || [];
                        
                        Object.keys(cached).forEach(key => {
                            if (!Array.isArray(cached[key]) && typeof cached[key] !== 'object') {
                                frm.doc[key] = cached[key];
                            }
                        });
                        
                        frm.refresh();
                        ['truck_loads', 'dozer_production', 'mining_areas_options', 
                         'ts_area_bcm_total', 'geo_mat_total_bcm'].forEach(table => {
                            frm.refresh_field(table);
                        });
                        
                        frappe.show_alert({
                            message: __('Offline changes restored'),
                            indicator: 'green'
                        });
                    }
                );
            }
        }

        setTimeout(() => {
            showOfflineStatus(frm);
            setupOfflineStatusEvents(frm);
        }, 300);

        if (!window.HourlyProductionOffline.isOnline()) {
            frm.page.set_indicator('Offline Mode', 'orange');
            
            if (!frm.custom_buttons['View Cached Changes']) {
                frm.add_custom_button(__('View Cached Changes'), function() {
                    const docs = window.HourlyProductionOffline.getCachedDocs();
                    const formattedDocs = docs.map(doc => `${doc.name} (${doc.doctype})`).join('\n');
                    frappe.msgprint(formattedDocs || 'No cached changes');
                }, __('Offline'));
            }
        }
    });
},


     total_coal_bcm(frm) {
        if (frm.doc.total_coal_bcm) {
            frm.set_value('coal_tons_total', frm.doc.total_coal_bcm * 1.5);
        } else {
            frm.set_value('coal_tons_total', 0);
        }},

    refresh(frm) {
        if (frm.is_saving) return;

        if (frm.is_new() && uiInitialized) {
            cleanupUIState(frm);
        }
        
        frm.set_df_property('whats_send', 'label', 'Send WhatsApp');
        
        // Ensure offline sync utility is loaded and check status
        frappe.require('/assets/is_production/js/offline_sync.js').then(() => {
            // Show offline status and handle cached changes
            const cachedDocs = window.HourlyProductionOffline.getCachedDocs();
            const hasCachedChanges = cachedDocs.some(doc => doc.name === frm.doc.name);
            
            if (!window.HourlyProductionOffline.isOnline()) {
                frm.page.set_indicator('Offline Mode', 'orange');
                
                // Show view cached changes button
                frm.add_custom_button(__('View Cached Changes'), function() {
                    const formattedDocs = cachedDocs.map(doc => {
                        return `${doc.name} (${doc.doctype})`;
                    }).join('\n');
                    frappe.msgprint(formattedDocs || 'No cached changes');
                }, __('Offline'));
                
            } else if (hasCachedChanges) {
                frm.page.set_indicator('Has offline changes', 'orange');
                
                // Show sync button
                frm.add_custom_button(__('Sync Changes'), function() {
                    window.HourlyProductionOffline.syncCachedDocs().then((results) => {
                        if (results.success > 0) {
                            frappe.show_alert({
                                message: __('Changes synced successfully!'),
                                indicator: 'green'
                            });
                            frm.reload_doc();
                        }
                    });
                }, __('Offline'));
            } else {
                // Clear indicator if online and no cached changes
                frm.page.clear_indicator();
            }
        });

        if (frm.doc.total_coal_bcm) {
            frm.set_value('coal_tons_total', frm.doc.total_coal_bcm * 1.5);
        } else if (frm.doc.total_coal_bcm === 0) {
            frm.set_value('coal_tons_total', 0);
        }

        // ✅ Auto-fill WhatsApp recipient if empty
        if (!frm.doc.whatsapp_recipient) {
            frappe.call({
                method: 'is_production.production.doctype.hourly_production.hourly_production.get_user_whatsapp_number',
                args: { user: frappe.session.user },
                callback: function (r) {
                    const number = r.message;
                    if (number) {
                        frm.set_value('whatsapp_recipient', number);
                    }
                }
            });
        }
        // ⬇ Keep the rest of your UI loading as-is
        
        update_mining_area_trucks_options(frm);
        update_mining_area_dozer_options(frm);
        update_dozer_geo_options(frm);
        updateTruckGeoMaterialOptions(frm);

        if (!frm.is_new()) {
            calculate_day_total(frm);
        }

        if (frm.doc.location && frm.doc.prod_date && frm.doc.shift && frm.doc.shift_num_hour) {
        // For existing docs, just initialize UI without data population
        if (!frm.is_new()) {
            if (!uiInitialized) {
                initializeOrRefreshUI(frm);
            } else if (frm.hourlyProductionUI) {
                frm.hourlyProductionUI.loadUI();
            }
        } 
        // For new docs, proceed with normal initialization
        else {
            initializeOrRefreshUI(frm);
        }
        }
        if (frm.doc.geo_mat_total_bcm && frm.doc.geo_mat_total_bcm.length > 0) {
            calculate_geo_mat_bcm_totals(frm);
        }

        if (!frm.is_new()) {
            calculate_excavators_count(frm);
        }

    // Update offline status tag (robust)
    setTimeout(() => showOfflineStatus(frm), 300);

        // Add manual sync button if offline changes exist
        if (window.HourlyProductionOffline.getCachedDocs().length > 0) {
            frm.add_custom_button(__('Sync Offline Changes'), function() {
                window.HourlyProductionOffline.syncCachedDocs().then(() => {
                    frappe.show_alert('Offline changes synced!');
                });
            });
        }
        
    },

    whats_send: function(frm) {
        if (frm.is_new()) {
            frappe.msgprint("Please save the document before sending WhatsApp.");
            return;
        }

        frappe.call({
            method: 'send_whatsapp_notification',
            doc: frm.doc,
            callback: function(response) {
                frm.reload_doc();
            },
            error: function(error) {
                frappe.msgprint(__('Failed to send WhatsApp notification'), 'red');
            }
        });
    },
    
      dozer_service(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        if (row.dozer_service === 'No Dozing') {
            frappe.model.set_value(cdt, cdn, 'bcm_hour', 0);
        }
    },
    mining_areas_dozer_child(frm) {
        update_mining_area_dozer_options(frm);
    },

    
    truck_loads_add(frm) {
        update_mining_area_trucks_options(frm);
        updateTruckGeoMaterialOptions(frm);
        
    },

    location(frm) {
    fetch_monthly_production_plan(frm);
    if (frm.is_new() || !frm.doc.truck_loads || frm.doc.truck_loads.length === 0) {
        populate_truck_loads_and_lookup(frm);
    }
    
    if (frm.is_new() || !frm.doc.dozer_production || frm.doc.dozer_production.length === 0) {
        populate_dozer_production_table(frm);
    }
        // If offline, cache doc on location change
        if (!window.HourlyProductionOffline.isOnline()) {
            window.HourlyProductionOffline.cacheDoc(frm.doc);
            frappe.show_alert({
                message: __('Offline: changes cached and will sync when online.'),
                indicator: 'orange'
            });
        }
    setTimeout(() => showOfflineStatus(frm), 300);
    },

    prod_date(frm) {
    // --- Keep existing logic first ---
    set_day_number(frm);
    fetch_monthly_production_plan(frm);

    // --- New Weekend Defaults for Shifts ---
    if (!frm.doc.prod_date) return;

    try {
        // Support both DD-MM-YYYY and YYYY-MM-DD formats
        const parts = frm.doc.prod_date.split('-');
        let dateObj;
        if (parts[0].length === 4) {
            dateObj = new Date(frm.doc.prod_date); // YYYY-MM-DD
        } else {
            const [d, m, y] = parts;
            dateObj = new Date(`${y}-${m}-${d}`); // DD-MM-YYYY
        }

        if (isNaN(dateObj)) return;
        const day = dateObj.getDay(); // Sunday=0, Saturday=6

        // ✅ If Saturday or Sunday → default shift times
        if (day === 0 || day === 6) {
            frm.set_value('day_shift_start', '06:00:00');
            frm.set_value('day_shift_end', '18:00:00');
            frm.set_value('night_shift_start', '18:00:00');
            frm.set_value('night_shift_end', '06:00:00');

            // Calculate working hours automatically
            calculate_shift_hours(frm, 'day_shift_start', 'day_shift_end', 'total_working_hours');
            calculate_shift_hours(frm, 'night_shift_start', 'night_shift_end', 'total_working_hour');
        }
    } catch (e) {
        console.warn('Weekend default logic failed:', e);
    }
},
    // --- Auto-calculate totals when start/end times change ---
    day_shift_start(frm) {
        if (frm.doc.day_shift_start && frm.doc.day_shift_end) {
            calculate_shift_hours(frm, 'day_shift_start', 'day_shift_end', 'total_working_hours');
        }
    },

    day_shift_end(frm) {
        if (frm.doc.day_shift_start && frm.doc.day_shift_end) {
            calculate_shift_hours(frm, 'day_shift_start', 'day_shift_end', 'total_working_hours');
        }
    },

    night_shift_start(frm) {
        if (frm.doc.night_shift_start && frm.doc.night_shift_end) {
            calculate_shift_hours(frm, 'night_shift_start', 'night_shift_end', 'total_working_hour');
        }
    },

    night_shift_end(frm) {
        if (frm.doc.night_shift_start && frm.doc.night_shift_end) {
            calculate_shift_hours(frm, 'night_shift_start', 'night_shift_end', 'total_working_hour');
        }
    },


    shift_system(frm) {
        update_shift_options(frm);
    },

    shift(frm) {
        update_shift_num_hour_options(frm);
    },

    shift_num_hour(frm) {
        update_hour_slot(frm);

        if (frm.doc.location && frm.doc.prod_date && frm.doc.shift && frm.doc.shift_num_hour) {
        // Only populate if new doc or no data exists
        if (frm.is_new() || !frm.doc.truck_loads || frm.doc.truck_loads.length === 0) {
            populate_truck_loads_and_lookup(frm).then(() => {
                if (!uiInitialized) {
                    initializeOrRefreshUI(frm);
                }
            });
        } 
        // Just initialize UI for existing docs with data
        else if (!uiInitialized) {
            initializeOrRefreshUI(frm);
        }
    }
    },
// ====================================================
// PRE-SAVE HOOK — ensure hour_slot is locked before saving
// ====================================================
before_save(frm) {
    // ✅ Only apply on Saturday or Sunday
    if (is_weekend(frm)) {
        // Force recalculation of hour slot before the save
        update_hour_slot(frm);
        console.log('Pre-save hour slot ensured:', frm.doc.hour_slot);
    }
},


after_save(frm) {
    console.log('After save triggered');

    // ====================================================
    // POST-SAVE HOOK — reapply and lock the correct hour_slot
    // ====================================================
    if (is_weekend(frm)) {
        const oldSlot = frm.doc.hour_slot;
        update_hour_slot(frm);
        const newSlot = frm.doc.hour_slot;

        // If slot changed during save, correct and persist it again
        if (oldSlot !== newSlot) {
            frappe.model.set_value(frm.doctype, frm.doc.name, 'hour_slot', newSlot);
            frm.set_value('hour_slot', newSlot);
            frm.refresh_field('hour_slot');
            console.log('Hour slot locked to:', newSlot);
        }
    }

    // Prevent multiple rapid saves
    if (frm.is_saving) {
        console.log('Save already in progress, skipping');
        return;
    }

    
    frappe.require(['/assets/is_production/js/offline_sync.js'], function() {
        // Check if we're offline
        if (window.HourlyProductionOffline && !window.HourlyProductionOffline.isOnline()) {
            // Cache the full doc with all its fields and child tables
            const docToCache = {
                ...frm.doc,
                doctype: frm.doctype,
                truck_loads: frm.doc.truck_loads || [],
                dozer_production: frm.doc.dozer_production || [],
                mining_areas_options: frm.doc.mining_areas_options || [],
                ts_area_bcm_total: frm.doc.ts_area_bcm_total || [],
                geo_mat_total_bcm: frm.doc.geo_mat_total_bcm || []
            };
            
            window.HourlyProductionOffline.cacheDoc(docToCache);
            frm.page.set_indicator('Saved Offline', 'orange');
            
            frappe.show_alert({
                message: __('You are offline. Changes are saved locally and will sync when online.'),
                indicator: 'orange'
            });
            
            // Add sync button if not already present
            if (!frm.custom_buttons['Sync Changes']) {
                frm.add_custom_button(__('Sync Changes'), function() {
                    window.HourlyProductionOffline.syncCachedDocs().then((results) => {
                        if (results.success > 0) {
                            frappe.show_alert({
                                message: __('Changes synced successfully!'),
                                indicator: 'green'
                            });
                            frm.reload_doc();
                        }
                    });
                }, __('Offline'));
            }
            
            return false;
        }
        
        // Handle online save operations
        if (frm.doc.total_coal_bcm) {
            frm.set_value('coal_tons_total', frm.doc.total_coal_bcm * 1.5);
        } else if (frm.doc.total_coal_bcm === 0) {
            frm.set_value('coal_tons_total', 0);
        }
        
        // Mark that we're doing a save operation
        frm.is_saving = true;
        // Sync MTD data first - this is a server call that doesn't affect form state
        sync_mtd_data_silent(frm);
        // Use setTimeout to allow the save to complete fully before doing UI updates
        setTimeout(() => {
            try {
                // Update options without triggering form changes
                update_mining_area_trucks_options(frm);
                update_mining_area_dozer_options(frm);
                // Calculate totals without triggering dirty state
                if (frm.doc.geo_mat_total_bcm && frm.doc.geo_mat_total_bcm.length > 0) {
                    calculate_geo_mat_bcm_totals_silent(frm);
                }
                // Also calculate area totals
                calculate_ts_area_bcm_totals_silent(frm);
                calculate_day_total(frm);
                // Ensure form is marked as clean first
                frm.doc.__unsaved = 0;
                frm.dirty = false;
                // Refresh the form toolbar to update save button state
                if (frm.toolbar && frm.toolbar.refresh) {
                    frm.toolbar.refresh();
                }
                // Only refresh UI if it exists and document has required data
                // Use a longer timeout to ensure save is completely finished
                setTimeout(() => {
                    if (frm.hourlyProductionUI && frm.doc.location && frm.doc.docstatus !== 2) {
                        console.log('Reloading UI after save');
                        frm.hourlyProductionUI.loadUI();
                    }
                }, 100);
            } catch (error) {
                console.error('Error in after_save cleanup:', error);
            } finally {
                // Always reset the saving flag
                frm.is_saving = false;
            }
        }, 300);
        if (!frm.is_new()) {
            calculate_excavators_count(frm);
        }
    });
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

  
// Update the month_prod_planning form event (keep the rest of the function the same)
// Replace your existing month_prod_planning event with this:
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
                
                // Store MPP assignments for later use but DON'T apply them here
                // They should only be applied in populate_truck_loads_and_lookup
                // when there are no previous hour assignments
                frm.mppAssignments = {};
                const assignments = mppDoc.excavator_truck_assignments || [];
                assignments.forEach(assignment => {
                    if (assignment.truck && assignment.excavator) {
                        frm.mppAssignments[assignment.truck] = assignment.excavator;
                    }
                });

                // Update geo material options (this is safe to do here)
                const geoRows = mppDoc.geo_mat_layer || [];
                const geoDescriptions = geoRows.map(row => row.geo_ref_description);
                
                frm.dozer_geo_options_str = geoDescriptions.join('\n');
                update_dozer_geo_options(frm);
                
                frm.truck_geo_options_str = geoDescriptions.join('\n');
                updateTruckGeoMaterialOptions(frm);

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
    return new Promise((resolve) => {
        // First, try to get previous hour assignments AND mining areas
        get_previous_hour_excavator_assignments(frm).then(prevAssignments => {
            console.log('Previous hour assignments found:', prevAssignments);
            
            // Get truck assets
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
                    order_by: 'asset_name asc',
                    limit_page_length: 500   // <- add this
                },
                callback: r => {
                    frm.clear_table('truck_loads');
                    
                    // Add default mining area ONLY if we're NOT using previous hour data
                    let defaultArea = '';
                    if (!prevAssignments && frm.doc.mining_areas_options && frm.doc.mining_areas_options.length === 1) {
                        defaultArea = frm.doc.mining_areas_options[0].mining_areas;
                    }
                    
                    // Create truck load rows
                    (r.message || []).forEach(asset => {
                        const row = frm.add_child('truck_loads');
                        frappe.model.set_value(row.doctype, row.name, 'asset_name_truck', asset.asset_name);
                        frappe.model.set_value(row.doctype, row.name, 'item_name', asset.item_name || '');
                        
                        // Set default mining area ONLY if we're NOT using previous hour data
                        if (defaultArea) {
                            frappe.model.set_value(row.doctype, row.name, 'mining_areas_trucks', defaultArea);
                        }
                    });
                    
                    // Now apply excavator assignments and mining areas - priority order:
                    // 1. Previous hour assignments (if found) - includes mining areas
                    // 2. MPP assignments (if no previous hour found) - no mining areas
                    
                    if (prevAssignments) {
                        console.log('Applying previous hour assignments with mining areas');
                        // Apply both excavator assignments AND mining areas from previous hour
                        (frm.doc.truck_loads || []).forEach(loadRow => {
                            const prevData = prevAssignments[loadRow.asset_name_truck];
                            if (prevData) {
                                if (prevData.excavator) {
                                    frappe.model.set_value(
                                        loadRow.doctype,
                                        loadRow.name,
                                        'asset_name_shoval',
                                        prevData.excavator
                                    );
                                }
                                if (prevData.mining_area) {
                                    frappe.model.set_value(
                                        loadRow.doctype,
                                        loadRow.name,
                                        'mining_areas_trucks',
                                        prevData.mining_area
                                    );
                                }
                            }
                        });
                    } else if (frm.mppAssignments) {
                        console.log('Applying MPP assignments (no mining areas)');
                        // Apply only excavator assignments from MPP, leave mining areas empty
                        (frm.doc.truck_loads || []).forEach(loadRow => {
                            if (frm.mppAssignments[loadRow.asset_name_truck]) {
                                frappe.model.set_value(
                                    loadRow.doctype,
                                    loadRow.name,
                                    'asset_name_shoval',
                                    frm.mppAssignments[loadRow.asset_name_truck]
                                );
                                // Explicitly leave mining_areas_trucks empty when using MPP
                            }
                        });
                    }
                    
                    frm.refresh_field('truck_loads');
                    update_mining_area_trucks_options(frm);
                    
                    resolve();
                }
            });
        }).catch(error => {
            console.error('Error in populate_truck_loads_and_lookup:', error);
            resolve();
        });
    });
}



function calculate_day_total(frm) {
    if (!frm.doc.prod_date || !frm.doc.location) return;
    
    function calculate_day_total(frm) {
        if (!frm.doc.prod_date || !frm.doc.location) return;

        frappe.call({
            method: 'is_production.production.doctype.hourly_production.hourly_production.get_day_total_bcm',
            args: {
                location: frm.doc.location,
                prod_date: frm.doc.prod_date,
                exclude_name: frm.doc.name
            },
            callback: function (r) {
                const existing_total = r.message || 0;
                const current_total = frm.doc.hour_total_bcm || 0;
                frm.set_value('day_total_bcm', existing_total + current_total);
            }
        });
    }
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
            fields: ['name as asset_name', 'item_name'],
            filters: { location: frm.doc.location, asset_category: 'Dozer', docstatus: 1 }
        },
        callback: r => {
            frm.clear_table('dozer_production');
            (r.message || []).forEach(asset => {
                const row = frm.add_child('dozer_production');
                row.asset_name = asset.asset_name;
                row.item_name = asset.item_name || '';
                row.bcm_hour = 0;
                row.dozer_service = 'No Dozing'; // Default value
                // Set default mining area if only one exists
                if (frm.doc.mining_areas_options && frm.doc.mining_areas_options.length === 1) {
                    row.mining_areas_dozer_child = frm.doc.mining_areas_options[0].mining_areas;
                }
            });
            frm.refresh_field('dozer_production');
            update_mining_area_dozer_options(frm);
            update_dozer_geo_options(frm);
        }
    });
}

// Silent version of calculate_ts_area_bcm_totals that doesn't trigger dirty state
function calculate_ts_area_bcm_totals_silent(frm) {
    // Get all truck loads and group by mining area
    const tsAreaTotals = {};
    
    (frm.doc.truck_loads || []).forEach(row => {
        const area = row.mining_areas_trucks;
        const bcms = parseFloat(row.bcms) || 0;
        
        if (area) {
            if (!tsAreaTotals[area]) {
                tsAreaTotals[area] = 0;
            }
            tsAreaTotals[area] += bcms;
        }
    });
    
    // Get all dozer production and group by mining area
    const dozerAreaTotals = {};
    
    (frm.doc.dozer_production || []).forEach(row => {
        const area = row.mining_areas_dozer_child;
        const bcmHour = parseFloat(row.bcm_hour) || 0;
        
        if (area) {
            if (!dozerAreaTotals[area]) {
                dozerAreaTotals[area] = 0;
            }
            dozerAreaTotals[area] += bcmHour;
        }
    });
    
    // Store the original dirty state
    const originalDirty = frm.dirty;
    const originalUnsaved = frm.doc.__unsaved;
    
    // Update the ts_area_bcm_total table with direct assignment
    (frm.doc.ts_area_bcm_total || []).forEach(row => {
        const area = row.ts_area_options;
        const tsTotal = tsAreaTotals[area] || 0;
        const dozerTotal = dozerAreaTotals[area] || 0;
        const bcmTotalArea = tsTotal + dozerTotal;
        
        // Direct assignment to avoid triggering dirty state
        row.ts_area_bcm = tsTotal;
        row.dozer_area_bcm = dozerTotal;
        row.bcm_total_area = bcmTotalArea;
    });
    
    // Restore the original dirty state
    frm.dirty = originalDirty;
    frm.doc.__unsaved = originalUnsaved;
    
    // Refresh the field display without triggering events
    frm.refresh_field('ts_area_bcm_total');
}

// Silent version of calculate_geo_mat_bcm_totals that doesn't trigger dirty state
function calculate_geo_mat_bcm_totals_silent(frm) {
    // Get all truck loads and group by geo material layer
    const geoTsTotals = {};
    
    (frm.doc.truck_loads || []).forEach(row => {
        const geoLayer = row.geo_mat_layer_truck;
        const bcms = parseFloat(row.bcms) || 0;
        
        if (geoLayer) {
            if (!geoTsTotals[geoLayer]) {
                geoTsTotals[geoLayer] = 0;
            }
            geoTsTotals[geoLayer] += bcms;
        }
    });
    
    // Get all dozer production and group by geo material layer
    const geoDozerTotals = {};
    
    (frm.doc.dozer_production || []).forEach(row => {
        const geoLayer = row.dozer_geo_mat_layer;
        const bcmHour = parseFloat(row.bcm_hour) || 0;
        
        if (geoLayer) {
            if (!geoDozerTotals[geoLayer]) {
                geoDozerTotals[geoLayer] = 0;
            }
            geoDozerTotals[geoLayer] += bcmHour;
        }
    });
    
    // Store the original dirty state
    const originalDirty = frm.dirty;
    const originalUnsaved = frm.doc.__unsaved;
    
    // Update the geo_mat_total_bcm table with direct assignment
    (frm.doc.geo_mat_total_bcm || []).forEach(row => {
        const geoLayer = row.geo_layer_options;
        const tsTotal = geoTsTotals[geoLayer] || 0;
        const dozerTotal = geoDozerTotals[geoLayer] || 0;
        const geoBcmTotal = tsTotal + dozerTotal;
        
        // Direct assignment to avoid triggering dirty state
        row.geo_ts_bcm_total = tsTotal;
        row.geo_dozer_bcm_total = dozerTotal;
        row.geo_bcm_total = geoBcmTotal;
    });
    
    // Restore the original dirty state
    frm.dirty = originalDirty;
    frm.doc.__unsaved = originalUnsaved;
    
    // Refresh the field display without triggering events
    frm.refresh_field('geo_mat_total_bcm');
}


function calculate_geo_mat_bcm_totals(frm) {
    // Get all truck loads and group by geo material layer
    const geoTsTotals = {};
    
    (frm.doc.truck_loads || []).forEach(row => {
        const geoLayer = row.geo_mat_layer_truck;
        const bcms = parseFloat(row.bcms) || 0;
        
        if (geoLayer) {
            if (!geoTsTotals[geoLayer]) {
                geoTsTotals[geoLayer] = 0;
            }
            geoTsTotals[geoLayer] += bcms;
        }
    });
    
    // Get all dozer production and group by geo material layer
    const geoDozerTotals = {};
    
    (frm.doc.dozer_production || []).forEach(row => {
        const geoLayer = row.dozer_geo_mat_layer;
        const bcmHour = parseFloat(row.bcm_hour) || 0;
        
        if (geoLayer) {
            if (!geoDozerTotals[geoLayer]) {
                geoDozerTotals[geoLayer] = 0;
            }
            geoDozerTotals[geoLayer] += bcmHour;
        }
    });
    
    // Update the geo_mat_total_bcm table with both totals AND calculate geo_bcm_total
    (frm.doc.geo_mat_total_bcm || []).forEach(row => {
        const geoLayer = row.geo_layer_options;
        const tsTotal = geoTsTotals[geoLayer] || 0;
        const dozerTotal = geoDozerTotals[geoLayer] || 0;
        const geoBcmTotal = tsTotal + dozerTotal; // Calculate the total
        
        frappe.model.set_value(row.doctype, row.name, 'geo_ts_bcm_total', tsTotal);
        frappe.model.set_value(row.doctype, row.name, 'geo_dozer_bcm_total', dozerTotal);
        frappe.model.set_value(row.doctype, row.name, 'geo_bcm_total', geoBcmTotal);
    });
    
    frm.refresh_field('geo_mat_total_bcm');
}


// ——————————————————————
// TUB FACTOR & BCMS
// ——————————————————————
frappe.ui.form.on('Truck Loads', {
     item_name(frm, cdt, cdn) {
        _update_tub_factor(frm, cdt, cdn);
    },
    mat_type(frm, cdt, cdn) {
        _update_tub_factor(frm, cdt, cdn);
    },
    bcms(frm, cdt, cdn) {
        // When BCMS changes in any row, recalculate if it's in the selected area
        const row = frappe.get_doc(cdt, cdn);
        if (row.mining_areas_trucks === frm.doc.dd_area) {
            
        }
        
        calculate_ts_area_bcm_totals_silent(frm);
        calculate_geo_mat_bcm_totals(frm);
    },
    mining_areas_trucks(frm, cdt, cdn) {
        // When area changes in a row, recalculate if affected
        const row = frappe.get_doc(cdt, cdn);
        if (row.mining_areas_trucks === frm.doc.dd_area || 
            frappe.model.get_value(cdt, cdn, 'mining_areas_trucks') === frm.doc.dd_area) {
            
        }
        calculate_ts_area_bcm_totals_silents(frm);
    },
   
    asset_name_shoval(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        if (!row.asset_name_shoval) {
            frappe.model.set_value(cdt, cdn, 'item_name_excavator', null);
        } else {
            frappe.call({
                method: 'frappe.client.get',
                args: { doctype: 'Asset', name: row.asset_name_shoval },
                callback: r => {
                    frappe.model.set_value(cdt, cdn, 'item_name_excavator', r.message?.item_code || null);
                }
            });
        }
        
        // Calculate excavators count after excavator assignment changes
        calculate_excavators_count(frm);
    },
    
    geo_mat_layer_truck: function(frm, cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn);
    if (row.geo_mat_layer_truck && frm.geoMaterialMap) {
      const matType = frm.geoMaterialMap[row.geo_mat_layer_truck];
      if (matType) {
        frappe.model.set_value(cdt, cdn, 'mat_type', matType);
      }
    }
    calculate_geo_mat_bcm_totals(frm);
    },
    bcms(frm) {
        if (frm.doc.total_coal_bcm) {
            frm.set_value('coal_tons_total', frm.doc.total_coal_bcm * 1.5);
        }
    },

    truck_loads_add(frm, cdt, cdn) {
        // Calculate totals when new row is added
        calculate_ts_area_bcm_totals_silent(frm);
        calculate_geo_mat_bcm_totals(frm);
        calculate_excavators_count(frm);
    },
    
    // New event for when rows are removed
    truck_loads_remove(frm, cdt, cdn) {
        // Calculate totals when row is removed
        calculate_ts_area_bcm_totals_silent(frm);
        calculate_geo_mat_bcm_totals(frm);
        calculate_excavators_count(frm);
    },

      tub_factor: function(frm, cdt, cdn) {
        _calculate_bcms(frm, cdt, cdn);
        // Calculate totals after bcms is recalculated
        setTimeout(() => {
            calculate_ts_area_bcm_totals_silent(frm);
            calculate_geo_mat_bcm_totals(frm);
        }, 100);
    },
    
    loads: function(frm, cdt, cdn) {
        _calculate_bcms(frm, cdt, cdn);
        // Calculate totals after bcms is recalculated
        setTimeout(() => {
            calculate_ts_area_bcm_totals_silent(frm);
            calculate_geo_mat_bcm_totals(frm);
        }, 100);
    }
});

frappe.ui.form.on('Dozer Production', {
    
    bcm_hour(frm, cdt, cdn) {
    calculate_ts_area_bcm_totals_silent(frm);
    calculate_geo_mat_bcm_totals(frm);
    },
    dozer_geo_mat_layer(frm, cdt, cdn) {
        // Recalculate geo totals when dozer geo layer changes
        calculate_geo_mat_bcm_totals(frm);
    },
    mining_areas_dozer_child(frm, cdt, cdn) {
       calculate_ts_area_bcm_totals_silent(frm);
    },
    dozer_production_add(frm, cdt, cdn) {
        calculate_ts_area_bcm_totals_silents(frm);
        calculate_geo_mat_bcm_totals(frm);
    },
    dozer_production_remove(frm, cdt, cdn) {
        calculate_ts_area_bcm_totals_silent(frm);
        calculate_geo_mat_bcm_totals(frm);
    }
    
    
    
    
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

    // Use the total working hours for each shift to determine number of slots
    if (s === 'Day') {
        count = parseInt(frm.doc.total_working_hours || 12);
    } else if (s === 'Night') {
        count = parseInt(frm.doc.total_working_hour || (sys === '2x12Hour' ? 12 : 8));
    } else {
        count = 8;
    }

    // Determine base hour dynamically from shift start fields
    let baseHour;
    if (s === 'Day' && frm.doc.day_shift_start) {
        baseHour = parseInt(frm.doc.day_shift_start.split(':')[0]);
    } else if (s === 'Night' && frm.doc.night_shift_start) {
        baseHour = parseInt(frm.doc.night_shift_start.split(':')[0]);
    } else if (s === 'Day' || s === 'Morning') {
        baseHour = 6;
    } else if (s === 'Afternoon') {
        baseHour = 14;
    } else {
        baseHour = 18;
    }

    // ✅ Build dropdown options like “Night-1”, “Night-2”, etc. (no time shown)
    const opts = Array.from({ length: count }, (_, i) => `${s}-${i + 1}`);

    // Store the base hour temporarily for hour_slot logic
    frm.base_shift_hour = baseHour;

    _set_options(frm, 'shift_num_hour', opts);
    frm.set_value('shift_num_hour', null);
}

function update_hour_slot(frm) {
    const [shiftName, hourIndexStr] = (frm.doc.shift_num_hour || '').split('-');
    const hourIndex = parseInt(hourIndexStr, 10);
    if (!shiftName || isNaN(hourIndex)) return;

    frm.set_value('hour_sort_key', hourIndex);

    // --- Default base hour ---
    let baseHour = 6;
    let day = null;

    // --- Get production date safely (handles all formats) ---
    if (frm.doc.prod_date) {
        try {
            let prodDateObj = null;

            if (frappe.datetime && frappe.datetime.str_to_obj) {
                prodDateObj = frappe.datetime.str_to_obj(frm.doc.prod_date);
            }

            if (!prodDateObj || isNaN(prodDateObj.getTime())) {
                // Manual fallback (handles DD-MM-YYYY or YYYY-MM-DD)
                const parts = frm.doc.prod_date.split('-');
                if (parts[0].length === 4) {
                    prodDateObj = new Date(frm.doc.prod_date);
                } else {
                    const [d, m, y] = parts;
                    prodDateObj = new Date(`${y}-${m}-${d}`);
                }
            }

            if (prodDateObj && !isNaN(prodDateObj.getTime())) {
                day = prodDateObj.getDay(); // Sunday=0, Saturday=6
            }
        } catch (e) {
            console.warn('Could not parse prod_date:', frm.doc.prod_date);
        }
    }

    // --- Determine base hour based on shift ---
    if (shiftName === 'Day' && frm.doc.day_shift_start) {
        baseHour = parseInt(frm.doc.day_shift_start.split(':')[0]);
    } 
    else if (shiftName === 'Afternoon' && frm.doc.afternoon_shift_start) {
        baseHour = parseInt(frm.doc.afternoon_shift_start.split(':')[0]);
    } 
    else if (shiftName === 'Night') {
        if (day === 0 || day === 6) {
            // Weekend (Saturday or Sunday)
            if (frm.doc.night_shift_start) {
                baseHour = parseInt(frm.doc.night_shift_start.split(':')[0]);
            } else {
                baseHour = 18; // fallback
            }
        } else {
            // Weekdays — always 18:00 start
            baseHour = 18;
        }
    }

    // --- Compute slot ---
    const startHour = (baseHour + (hourIndex - 1)) % 24;
    const endHour = (startHour + 1) % 24;
    const fmt = (h) => `${String(h).padStart(2, '0')}:00`;

    const hourSlot = `${fmt(startHour)}-${fmt(endHour)}`;
    frm.set_value('hour_slot', hourSlot);
    frm.set_value('locked_hour_slot', hourSlot);

    console.log(
        `🕓 Hour slot recalculated: ${hourSlot} | Base: ${baseHour} | Shift: ${shiftName} | Day: ${day}`
    );

    // --- Refresh UI if needed ---
    if (frm.doc.location && frm.doc.prod_date && frm.doc.shift && frm.doc.shift_num_hour) {
        populate_truck_loads_and_lookup(frm).then(() => {
            if (uiInitialized && frm.hourlyProductionUI) {
                frm.hourlyProductionUI.loadUI();
            } else {
                initializeOrRefreshUI(frm);
            }
        });
    }
}


function _set_options(frm, field, opts) {
    if (frm.fields_dict[field]) {
        frm.set_df_property(field, 'options', opts.join('\n'));
    }
}
// ====================================================
// Shift working hours calculator
// ====================================================
function calculate_shift_hours(frm, startField, endField, totalField) {
    const start = frm.doc[startField];
    const end = frm.doc[endField];
    if (!start || !end) return;

    const [sh, sm = 0] = start.split(':').map(Number);
    const [eh, em = 0] = end.split(':').map(Number);
    let diff = (eh * 60 + em) - (sh * 60 + sm);
    if (diff < 0) diff += 24 * 60; // Handle past midnight
    const hours = (diff / 60).toFixed(2);
    frm.set_value(totalField, hours);
}
// ====================================================
// Helper: Check if production date is weekend (Saturday or Sunday)
// ====================================================
function is_weekend(frm) {
    if (!frm.doc.prod_date) return false;
    try {
        const parts = frm.doc.prod_date.split('-');
        let dateObj;
        if (parts[0].length === 4) {
            // Format: YYYY-MM-DD
            dateObj = new Date(frm.doc.prod_date);
        } else {
            // Format: DD-MM-YYYY
            const [d, m, y] = parts;
            dateObj = new Date(`${y}-${m}-${d}`);
        }
        const day = dateObj.getDay();
        return day === 0 || day === 6; // Sunday = 0, Saturday = 6
    } catch {
        return false;
    }
}
