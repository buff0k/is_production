// monthly_production_planning.js
// Combined functionality: existing Monthly Production Planning logic + drag-and-drop Excavator Teams & Trucks

// helper for logging errors without breaking your flow
function logError(section, err) {
  console.error(`Error in ${section}:`, err);
}

console.log("🛠 Monthly Production Planning JS loaded");
console.log("📦 Custom JS: monthly_production_planning.js loaded — version 2025-06-16 20:34");



function calculateGeoRefDescription(frm, cdt, cdn) {
  const row  = locals[cdt][cdn];
  const desc = row.geo_mat_type_description || '';
  const rows = frm.doc.geo_mat_layer || [];
  const idx  = rows.findIndex(r => r.name === row.name) + 1;
  const combined = `${idx} - ${desc}`;
  frappe.model.set_value(cdt, cdn, 'geo_ref_description', combined);
}


// ──────────────────────────────────────────────────────────────────────────────
//                      Now start the actual event‐handler object
// ──────────────────────────────────────────────────────────────────────────────

frappe.ui.form.on('Monthly Production Planning', {

  setup(frm) {
    // hide the native child-tables
    //frm.get_field('excavator_truck_assignments').$wrapper.hide();
    //frm.get_field('dozer_table').$wrapper.hide();

    frm.set_df_property('dozer_table', 'cannot_delete', false);
    frm.set_query('excavator', 'excavator_truck_assignments', function () {
      return {
        filters: {
          asset_category: 'Excavator',
          location: frm.doc.location
        }
      };
    });

    frm.set_query('truck', 'excavator_truck_assignments', function () {
      return {
        filters: {
          asset_category: 'ADT',
          location: frm.doc.location
        }
      };
    });
  },

  // Section 0: Before Save
  before_save(frm) {
    try {
      // ✅ Keep this: Patch hourly_production_reference for each day
      frm.doc.month_prod_days?.forEach(r => {
        r.hourly_production_reference = `${frm.doc.name}-${r.shift_start_date}`;
      });
      frm.refresh_field('month_prod_days');

    } catch (e) {
      logError('before_save', e);
    }
    
        if (!frm.doc.prod_trucks) {
            frm.doc.prod_trucks = [];
        }
    
  },

  // Section 1: Refresh

 refresh(frm) {
  try {
    console.log("🌀 Refresh triggered");
    console.log("📍 Location is:", frm.doc.location);

    // on every refresh, re-enable the delete icon in the grid
    if (frm.fields_dict.dozer_table && frm.fields_dict.dozer_table.grid) {
      // allow the grid to delete rows
      frm.fields_dict.dozer_table.grid.can_delete = true;
      // show the little “trash” icon in each row
      frm.fields_dict.dozer_table.grid.wrapper
        .find('.grid-delete-row, .grid-remove-rows, .grid-delete')
        .show();
    }

    // Custom buttons
    frm.add_custom_button(
      __('Populate Monthly Production Days'),
      () => frm.trigger('populate_monthly_prod_days'),
      __('Actions')
    );
    frm.add_custom_button(
      __('Clear Production Days'),
      () => frm.trigger('clear_production_days'),
      __('Actions')
    );
    // Add refresh machines button (will appear in form header under "Site Details and Plant")
    frm.add_custom_button(
      __('🔄 Refresh Machines'),
      () => frm.trigger('refresh_machines_from_assets'),
      __('Site Details and Plant')
    );

    // Calculate geo layer descriptions
    (frm.doc.geo_mat_layer || []).forEach(row => {
      calculateGeoRefDescription(frm, row.doctype, row.name);
    });

    // ── Update equipment counts and volume fields ──
    frm.trigger('update_equipment_counts');
    frm.trigger('update_ts_planned_volumes');
    frm.trigger('update_planned_dozer_volumes');

    // Render drag-and-drop UI if location exists
    if (frm.doc.location) {
      renderTruckAssignmentUI(frm);
      renderDozerAssignmentUI(frm);
    } else {
      frm.get_field('dnd_html_truck_ui').$wrapper.html('<p>Please select a location first.</p>');
      frm.get_field('dnd_dozer_assigned').$wrapper.html('<p>Please select a location first.</p>');
    }

    // ── Requirement 1: dynamically populate geo_description options ──
    const opts = (frm.doc.geo_mat_layer || [])
      .map(r => r.geo_ref_description)
      .join('\n');

    // tell the Blasting Plan child‐table’s grid to use these as the select options
    frm.fields_dict.blasting_plan.grid.update_docfield_property(
      'geo_description', 'options', opts
    );

  } catch (e) {
    logError('refresh', e);
  }
},

  // ────────────────────────────────────────────────────────────────────
  // Volume recalculation triggers
  // 1) TS volumes when either input changes
  total_month_prod_hours: frm => frm.trigger('update_ts_planned_volumes'),
  ts_tempo:               frm => frm.trigger('update_ts_planned_volumes'),

  // 2) Dozer volumes whenever a Blasting Plan row is added or removed
  blasting_plan_add:    frm => frm.trigger('update_planned_dozer_volumes'),
  blasting_plan_remove: frm => frm.trigger('update_planned_dozer_volumes'),

  // 3) Keep your location handler
  location(frm) {
    console.log("🧭 Location changed:", frm.doc.location);
    if (frm.doc.location) {
      frm.refresh();
    }
  },
 // Section: Refresh Machines from Assets (non-destructive)
refresh_machines_from_assets(frm) {
  if (!frm.doc.location) {
    frappe.msgprint(__('Please select a location first.'));
    return;
  }

  frappe.call({
    method: "frappe.client.get_list",
    args: {
      doctype: "Asset",
      filters: {
        location: frm.doc.location,
        docstatus: 1   // ✅ Only Submitted assets
      },
      fields: ["name", "item_name", "asset_category"],
      limit_page_length: 500
    },
    callback: function(r) {
      const assets = r.message || [];

      const excavators = assets.filter(a => a.asset_category === "Excavator");
      const trucks     = assets.filter(a => a.asset_category === "ADT");
      const dozers     = assets.filter(a => a.asset_category === "Dozer");

      // helper: sync without wiping table
      function syncTable(tableName, keyField, assetList, assignFields = {}) {
        let table = frm.doc[tableName] || [];

        // keep only valid rows
        table = table.filter(row =>
          assetList.some(asset => asset.name === row[keyField])
        );

        // add missing rows
        assetList.forEach(asset => {
          if (!table.some(row => row[keyField] === asset.name)) {
            const row = frm.add_child(tableName);
            row[keyField] = asset.name;
            Object.assign(row, assignFields(asset));
          }
        });

        frm.doc[tableName] = table;
        frm.refresh_field(tableName);
      }

      // 🔄 Sync each table
      syncTable("excavator_truck_assignments", "excavator", excavators, a => ({
        excavator_model: a.item_name
      }));

      syncTable("excavator_truck_assignments", "truck", trucks, a => ({
        truck_model: a.item_name
      }));

      syncTable("dozer_table", "asset_name", dozers, a => ({
        item_name: a.item_name
      }));

      frappe.msgprint(__("✅ Machines refreshed — only adds/removes applied, existing assignments kept."));
    }
  });
},


  // Section 2: Populate Monthly Production Days
  populate_monthly_prod_days(frm) {
    try {
      if (!frm.doc.prod_month_start_date || !frm.doc.prod_month_end_date) {
        frappe.msgprint(__('Please select production start and end dates.'));
        return;
      }
      if (
        [frm.doc.weekday_shift_hours, frm.doc.saturday_shift_hours, frm.doc.num_sat_shifts]
          .some(v => v == null)
      ) {
        frappe.msgprint(__('Please enter shift hours and number of Saturday shifts.'));
        return;
      }
      const start = frappe.datetime.str_to_obj(frm.doc.prod_month_start_date);
      const end   = frappe.datetime.str_to_obj(frm.doc.prod_month_end_date);
      frm.clear_table('month_prod_days');
      let totals = { day: 0, night: 0, morning: 0, afternoon: 0 };
      const wH  = +frm.doc.weekday_shift_hours;
      const sH  = +frm.doc.saturday_shift_hours;
      const sSh = +frm.doc.num_sat_shifts;
      for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
        const dow = d.toLocaleDateString('en-US', { weekday: 'long' });
        let hours = { day: 0, night: 0, morning: 0, afternoon: 0 };
        if (frm.doc.shift_system === '2x12Hour') {
          if (dow === 'Saturday') {
            hours.day   = sH;
            hours.night = sSh > 1 ? sH : 0;
          } else if (dow !== 'Sunday') {
            hours.day   = hours.night = wH;
          }
        } else {
          if (dow === 'Saturday') {
            hours.morning = sH;
            if (sSh > 1) hours.afternoon = sH;
            if (sSh > 2) hours.night     = sH;
          } else if (dow !== 'Sunday') {
            hours.morning = hours.afternoon = hours.night = wH;
          }
        }
        totals.day      += hours.day;
        totals.night    += hours.night;
        totals.morning  += hours.morning;
        totals.afternoon+= hours.afternoon;

        const row = frm.add_child('month_prod_days');
        row.shift_start_date      = frappe.datetime.obj_to_str(d);
        row.day_week              = dow;
        row.shift_day_hours       = hours.day;
        row.shift_night_hours     = hours.night;
        row.shift_morning_hours   = hours.morning;
        row.shift_afternoon_hours = hours.afternoon;
      }

      frm.set_value({
        tot_shift_day_hours:       totals.day,
        tot_shift_night_hours:     totals.night,
        tot_shift_morning_hours:   totals.morning,
        tot_shift_afternoon_hours: totals.afternoon,
        total_month_prod_hours:    totals.day + totals.night + totals.morning + totals.afternoon
      });
      frm.trigger('recalculate_totals');
      frm.refresh_field('month_prod_days');
      frappe.msgprint(__('Monthly Production Days populated.'));
    } catch (e) {
      logError('populate_monthly_prod_days', e);
    }
  },

  // Section 4: Clear Production Days
  clear_production_days(frm) {
    try {
      frm.clear_table('month_prod_days');
      frm.refresh_field('month_prod_days');
      [
        'tot_shift_day_hours',
        'tot_shift_night_hours',
        'tot_shift_morning_hours',
        'tot_shift_afternoon_hours',
        'total_month_prod_hours',
        'num_prod_days',
        'target_bcm_day',
        'target_bcm_hour',
        'num_excavators',
        'num_trucks',
        'num_dozers'
      ].forEach(f => frm.set_value(f, 0));
      frappe.msgprint(__('Production Days cleared.'));
    } catch (e) {
      logError('clear_production_days', e);
    }
  },

  // Section 5: prod_month_end_date
  prod_month_end_date(frm) {
    try {
      if (!frm.doc.prod_month_end_date) return;
      const d    = new Date(frm.doc.prod_month_end_date);
      const last = new Date(d.getFullYear(), d.getMonth() + 1, 0);
      frm.set_value('prod_month_end', frappe.datetime.obj_to_str(last));
      frappe.msgprint(__('Month end set to last day.'));
    } catch (e) {
      logError('prod_month_end_date', e);
    }
  },

  // Section 6: recalculate_totals
  //monthly_target_bcm: frm => frm.trigger('recalculate_totals'),
  recalculate_totals(frm) {
    try {
      console.log('🔁 recalculate_totals() called');

      let sums = { day: 0, night: 0, morning: 0, afternoon: 0, days: 0 };
      (frm.doc.month_prod_days || []).forEach(r => {
        const d = +r.shift_day_hours      || 0;
        const n = +r.shift_night_hours    || 0;
        const m = +r.shift_morning_hours  || 0;
        const a = +r.shift_afternoon_hours|| 0;
        const hrs = d + n + m + a;

        if (hrs) sums.days++;
        sums.day       += d;
        sums.night     += n;
        sums.morning   += m;
        sums.afternoon += a;
      });

      const totalHrs = sums.day + sums.night + sums.morning + sums.afternoon;

      frm.set_value({
        tot_shift_day_hours:       sums.day,
        tot_shift_night_hours:     sums.night,
        tot_shift_morning_hours:   sums.morning,
        tot_shift_afternoon_hours: sums.afternoon,
        total_month_prod_hours:    totalHrs,
        num_prod_days:             sums.days
      });

      if (frm.doc.monthly_target_bcm) {
        frm.set_value('target_bcm_day',  frm.doc.monthly_target_bcm / (sums.days || 1));
        frm.set_value('target_bcm_hour', frm.doc.monthly_target_bcm / (totalHrs   || 1));
      }
    } catch (e) {
      logError('recalculate_totals', e);
    }
  },


  // Section 7: Update MTD Production
  update_mtd_production(frm) {
    try {
      if (!frm.doc.name) {
        frappe.msgprint(__('Save first.'));
        return;
      }
      const refs = frm.doc.month_prod_days
        .map(r => r.hourly_production_reference)
        .filter(Boolean);
      if (!refs.length) {
        frappe.msgprint(__('No refs to query.'));
        return;
      }

      // Fetch ALL Hourly Production
      frappe.call({
        method: 'frappe.client.get_list',
        args: {
          doctype: 'Hourly Production',
          filters: [
            ['month_prod_planning','=', frm.doc.name],
            ['monthly_production_child_ref','in', refs]
          ],
          fields: [
            'name',
            'monthly_production_child_ref as ref',
            'shift',
            'total_ts_bcm',
            'total_dozing_bcm'
          ],
          limit_page_length: 0,
          limit_start: 0
        },
        callback: r => {
          try {
            const records = r.message || [];

            // Matching Records
            const matchEntries = records.map(e => {
              const matched = frm.doc.month_prod_days
                .some(row => row.hourly_production_reference === e.ref);
              return `${e.name}: ${e.ref}${matched ? '-x' : ''}`;
            });
            logError('Matching Records', matchEntries.join('; '));

            // Fetch Summary
            const recordCount = records.length;
            const totalTS     = records.reduce((s,e) => s + (e.total_ts_bcm    || 0), 0);
            const totalDZ     = records.reduce((s,e) => s + (e.total_dozing_bcm || 0), 0);
            const totalBCM    = totalTS + totalDZ;
            logError('Hourly Production Fetch Summary', { recordCount, totalTS, totalDZ, totalBCM });

            // Aggregate & Write-back
            const sumsMap = {};
            records.forEach(e => {
              const ts  = e.total_ts_bcm     || 0;
              const dz  = e.total_dozing_bcm  || 0;
              const bcm = ts + dz;
              sumsMap[e.ref] = sumsMap[e.ref] || { Day:0, Night:0, Morning:0, Afternoon:0, total:0, ts:0, dz:0 };
              sumsMap[e.ref][e.shift] += bcm;
              sumsMap[e.ref].total    += bcm;
              sumsMap[e.ref].ts       += ts;
              sumsMap[e.ref].dz       += dz;
            });
            frm.doc.month_prod_days.forEach(row => {
              const s = sumsMap[row.hourly_production_reference] || { Day:0, Night:0, Morning:0, Afternoon:0, total:0, ts:0, dz:0 };
              frappe.model.set_value(row.doctype, row.name, {
                day_shift_bcms:      s.Day,
                night_shift_bcms:    s.Night,
                morning_shift_bcms:  s.Morning,
                afternoon_shift_bcms:s.Afternoon,
                total_daily_bcms:    s.total,
                total_ts_bcms:       s.ts,
                total_dozing_bcms:   s.dz
              });
            });
            frm.refresh_field('month_prod_days');

            // Checksum
            const expected = Object.keys(sumsMap).length;
            const updated  = frm.doc.month_prod_days.filter(r => sumsMap[r.hourly_production_reference]).length;
            logError('HP Update Checksum', { expected, updated });

            // Post-update Totals
            const tableTotals = frm.doc.month_prod_days.reduce((acc,row) => {
              acc.day      += row.day_shift_bcms    || 0;
              acc.night    += row.night_shift_bcms  || 0;
              acc.morning  += row.morning_shift_bcms|| 0;
              acc.afternoon+= row.afternoon_shift_bcms|| 0;
              acc.total    += row.total_daily_bcms  || 0;
              return acc;
            }, { day:0, night:0, morning:0, afternoon:0, total:0 });
            logError('Monthly Prod Days BCM Totals', tableTotals);

            // Cumulative Totals (fixed field names)
            let runTs = 0, runDz = 0;
            frm.doc.month_prod_days
              .slice()
              .sort((a, b) => new Date(a.shift_start_date) - new Date(b.shift_start_date))
              .forEach(rw => {
                runTs += rw.total_ts_bcms     || 0;
                runDz += rw.total_dozing_bcms || 0;
                frappe.model.set_value(rw.doctype, rw.name, {
                  cum_ts_bcms:                 runTs,
                  tot_cumulative_dozing_bcms:  runDz
                });
              });
            frm.refresh_field('month_prod_days');

          } catch (inner) {
            logError('Processing HP Callback', inner);
          }
        },
        error: err => {
          logError('Call HP', err);
          frappe.msgprint(__('Unable to load Hourly Production data. See Error Log.'));
        }
      });

      // Section 3: Fetch ALL Survey & calculate variances (last‐only) + parent-level updates
      frappe.call({
        method: 'frappe.client.get_list',
        args: {
          doctype: 'Survey',
          filters: [
            ['hourly_prod_ref', 'in', refs],
            ['docstatus', '=', 1]
          ],
          fields: [
            'hourly_prod_ref as ref',
            'total_dozing_bcm',
            'total_ts_bcm'
          ],
          limit_page_length: 0,
          limit_start: 0
        },
        callback: function(srv) {
          try {
            // 1) Build survey map
            const surveyMap = {};
            (srv.message || []).forEach(s => {
              surveyMap[s.ref] = {
                dz: s.total_dozing_bcm || 0,
                ts: s.total_ts_bcm     || 0
              };
            });

            // 2) Determine which ref is the latest
            const surveyRows = frm.doc.month_prod_days
              .filter(r => surveyMap[r.hourly_production_reference]);
            let lastRef = null;
            if (surveyRows.length) {
              const lastRow = surveyRows.reduce((prev, curr) =>
                new Date(curr.shift_start_date) > new Date(prev.shift_start_date)
                  ? curr
                  : prev,
                surveyRows[0]
              );
              lastRef = lastRow.hourly_production_reference;
            }

            // 3) Loop every child-row: keep variance only on lastRef, zero out others
            frm.doc.month_prod_days.forEach(row => {
              const ref    = row.hourly_production_reference;
              const baseDz = row.tot_cumulative_dozing_bcms || 0;
              const baseTs = row.cum_ts_bcms             || 0;

              if (ref === lastRef) {
                const survey = surveyMap[ref];
                frappe.model.set_value(row.doctype, row.name, {
                  tot_cum_dozing_survey: survey.dz,
                  tot_cum_ts_survey:     survey.ts,
                  cum_dozing_variance:   survey.dz - baseDz,
                  cum_ts_variance:       survey.ts - baseTs
                });
              } else {
                frappe.model.set_value(row.doctype, row.name, {
                  tot_cum_dozing_survey: 0,
                  tot_cum_ts_survey:     0,
                  cum_dozing_variance:   0,
                  cum_ts_variance:       0
                });
              }
            });

            frm.refresh_field('month_prod_days');

            // --- Final parent-level updates ---

            // 4) Parent-level tallies
            let totalTs = 0, totalDz = 0;
            frm.doc.month_prod_days.forEach(r => {
              totalTs += r.total_ts_bcms    || 0;
              totalDz += r.total_dozing_bcms|| 0;
            });

            // 5) ORIGINAL survey-variance from most recent non-zero child variance
            let varRows = frm.doc.month_prod_days
              .filter(r => (r.cum_dozing_variance || 0) !== 0
                         || (r.cum_ts_variance     || 0) !== 0)
              .sort((a, b) => new Date(b.shift_start_date) - new Date(a.shift_start_date));
            let surveyVar = 0;
            if (varRows.length) {
              const latest = varRows[0];
              surveyVar = (latest.cum_dozing_variance || 0)
                        + (latest.cum_ts_variance     || 0);
            }

            // 6) Completed days & hours (up to yesterday)
            const today = new Date();
            const yest  = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1);
            let doneDays = 0, doneHrs = 0;
            frm.doc.month_prod_days.forEach(r => {
              const rd = frappe.datetime.str_to_obj(r.shift_start_date);
              if (rd <= yest) {
                const hrs =
                  (r.shift_day_hours     || 0) +
                  (r.shift_night_hours   || 0) +
                  (r.shift_morning_hours || 0) +
                  (r.shift_afternoon_hours || 0);
                if (hrs) doneDays++;
                doneHrs += hrs;
              }
            });

            // 7) Final parent-level updates
            const actual   = totalTs + totalDz + surveyVar;
            const mtdDay   = actual / doneDays;
            const mtdHr    = actual / doneHrs;
            const forecast = mtdHr * (frm.doc.total_month_prod_hours || 0);

            frm.set_value({
              month_act_ts_bcm_tallies:          totalTs,
              month_act_dozing_bcm_tallies:      totalDz,
              monthly_act_tally_survey_variance: surveyVar,
              month_actual_bcm:                  actual,
              prod_days_completed:               doneDays,
              month_prod_hours_completed:        doneHrs,
              month_remaining_production_days:   frm.doc.num_prod_days - doneDays,
              month_remaining_prod_hours:        frm.doc.total_month_prod_hours - doneHrs,
              mtd_bcm_day:                       mtdDay,
              mtd_bcm_hour:                      mtdHr,
              month_forecated_bcm:               forecast
            });
            frm.refresh_fields([
              'month_act_ts_bcm_tallies',
              'month_act_dozing_bcm_tallies',
              'monthly_act_tally_survey_variance',
              'month_actual_bcm',
              'prod_days_completed',
              'month_prod_hours_completed',
              'month_remaining_production_days',
              'month_remaining_prod_hours',
              'mtd_bcm_day',
              'mtd_bcm_hour',
              'month_forecated_bcm'
            ]);

          } catch (inner) {
            logError('Processing Survey Callback', inner);
          }
        },
        error: function(err) {
          logError('Call Survey', err);
          frappe.msgprint(__('Unable to load Survey data. See Error Log.'));
        }
      });

    } catch (e) {
      logError('update_mtd_production', e);
      frappe.msgprint(__('An unexpected error occurred. Check the Error Log.'));
    }
  },

  // Section 8: Child Table Triggers
  //'Monthly Production Days': {
    //shift_day_hours:       frm => frm.trigger('recalculate_totals'),
    //shift_night_hours:     frm => frm.trigger('recalculate_totals'),
    //shift_morning_hours:   frm => frm.trigger('recalculate_totals'),
    //shift_afternoon_hours: frm => frm.trigger('recalculate_totals')
  //},

   // Section 9: Update Equipment Counts (with logging)
  update_equipment_counts(frm) {
    try {
      // Count unique Excavator groups (as reflected in the UI)
      const assignments = frm.doc.excavator_truck_assignments || [];
      const excavatorIds = [...new Set(
        assignments
          .filter(r => !!r.excavator)
          .map(r => r.excavator)
      )];
      const numExcavators = excavatorIds.length;
      // Count only trucks assigned to excavator groups
      const numTrucks     = assignments.filter(r => r.excavator && r.truck).length;
      // Count only dozer rows with Production dozing_type
      const numDozers     = (frm.doc.dozer_table || []).filter(r => r.dozing_type === 'Production').length;

      // Log calculations
      console.log(`🧮 Equipment counts -> Excavators: ${numExcavators}, Trucks: ${numTrucks}, Dozers (Production): ${numDozers}`);

      frm.set_value({
        num_excavators: numExcavators,
        num_trucks:     numTrucks,
        num_dozers:     numDozers
      });
      frm.refresh_fields(['num_excavators', 'num_trucks', 'num_dozers']);
    } catch (e) {
      logError('update_equipment_counts', e);
    }
  },

  // Section X: Update TS Planned Volumes (with logging, using precomputed excavator count)
  update_ts_planned_volumes(frm) {
    try {
      const hours = frm.doc.total_month_prod_hours || 0;
      const tempo = frm.doc.ts_tempo            || 0;
      // Use precomputed number of excavators
      const numExcavators = frm.doc.num_excavators || 0;
      // Calculate TS volume
      const tsTotal = hours * tempo * numExcavators;
      // Retrieve current dozer volume
      const dozerTotal = frm.doc.planned_dozer_volumes || 0;
      // Calculate target BCM
      const monthlyTarget = tsTotal + dozerTotal;

      // Log calculations
      console.log(
        `📊 TS Planned Volumes -> hours: ${hours}, tempo: ${tempo}, excavators: ${numExcavators}, tsTotal: ${tsTotal}, dozerTotal: ${dozerTotal}, monthlyTarget: ${monthlyTarget}`
      );

      frm.set_value({
        total_ts_planned_volumes: tsTotal,
        monthly_target_bcm:       monthlyTarget
      });
    } catch (e) {
      logError('update_ts_planned_volumes', e);
    }
  },

  // Section Y: Update Planned Dozer Volumes (with logging)
  update_planned_dozer_volumes(frm) {
    try {
      const blasts = frm.doc.blasting_plan || [];
      const dozerTotal = blasts.reduce(
        (sum, row) => sum + (row.block_dozing_bcms || 0), 0
      );
      // Retrieve current TS volume
      const tsTotal = frm.doc.total_ts_planned_volumes || 0;
      // Calculate target BCM
      const monthlyTarget = tsTotal + dozerTotal;

      // Log calculations
      console.log(
        `📐 Planned Dozer Volumes -> blast rows: ${blasts.length}, dozerTotal: ${dozerTotal}, tsTotal: ${tsTotal}, monthlyTarget: ${monthlyTarget}`
      );

      frm.set_value({
        planned_dozer_volumes: dozerTotal,
        monthly_target_bcm:    monthlyTarget
      });
    } catch (e) {
      logError('update_planned_dozer_volumes', e);
    }
  },

 coal_tons_planned: function(frm) {
        // Calculate the derived fields when coal_tons_planned changes
        if (frm.doc.coal_tons_planned) {
            // Calculate coal_planned_bcm
            const coal_planned_bcm = frm.doc.coal_tons_planned / 1.5;
            
            // Calculate waste_bcms_planned (only if monthly_target_bcm exists)
            const waste_bcms_planned = frm.doc.monthly_target_bcm ? 
                frm.doc.monthly_target_bcm - coal_planned_bcm : 0;
            
            // Calculate planned_strip_ratio (avoid division by zero)
            const planned_strip_ratio = frm.doc.coal_tons_planned ? 
                waste_bcms_planned / frm.doc.coal_tons_planned : 0;
            
            // Set the values in the form
            frm.set_value('coal_planned_bcm', coal_planned_bcm);
            frm.set_value('waste_bcms_planned', waste_bcms_planned);
            frm.set_value('planned_strip_ratio', planned_strip_ratio);
        } else {
            // Clear the fields if coal_tons_planned is empty
            frm.set_value('coal_planned_bcm', 0);
            frm.set_value('waste_bcms_planned', 0);
            frm.set_value('planned_strip_ratio', 0);
        }
    },


    monthly_target_bcm: function(frm) {
        // Also recalculate when monthly_target_bcm changes if coal_tons_planned exists
        if (frm.doc.coal_tons_planned) {
            const coal_planned_bcm = frm.doc.coal_tons_planned / 1.5;
            const waste_bcms_planned = frm.doc.monthly_target_bcm ? 
                frm.doc.monthly_target_bcm - coal_planned_bcm : 0;
            const planned_strip_ratio = frm.doc.coal_tons_planned ? 
                waste_bcms_planned / frm.doc.coal_tons_planned : 0;
            
            frm.set_value('waste_bcms_planned', waste_bcms_planned);
            frm.set_value('planned_strip_ratio', planned_strip_ratio);
        }
        // ALSO trigger totals
        frm.trigger('recalculate_totals');
        
        console.log('📣 monthly_target_bcm changed — triggering recalc');
    }



});

//Child Table Triggers (diagnostic version)
frappe.ui.form.on('Monthly Production Days', {
  shift_day_hours: function (frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    console.log('🟨 shift_day_hours changed', {
      cdn,
      ref: row.hourly_production_reference,
      newVal: row.shift_day_hours
    });
    frm.trigger('recalculate_totals');
  },
  shift_night_hours: function (frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    console.log('🟨 shift_night_hours changed', {
      cdn,
      ref: row.hourly_production_reference,
      newVal: row.shift_night_hours
    });
    frm.trigger('recalculate_totals');
  },
  shift_morning_hours: function (frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    console.log('🟨 shift_morning_hours changed', {
      cdn,
      ref: row.hourly_production_reference,
      newVal: row.shift_morning_hours
    });
    frm.trigger('recalculate_totals');
  },
  shift_afternoon_hours: function (frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    console.log('🟨 shift_afternoon_hours changed', {
      cdn,
      ref: row.hourly_production_reference,
      newVal: row.shift_afternoon_hours
    });
    frm.trigger('recalculate_totals');
  }
});

// When either source field changes on a Geo_mat_layer row:
frappe.ui.form.on('Geo_mat_layer', {
  geo_mat_layer_ref: function(frm, cdt, cdn) {
    calculateGeoRefDescription(frm, cdt, cdn);
  },
  geo_mat_type_description: function(frm, cdt, cdn) {
    calculateGeoRefDescription(frm, cdt, cdn);
  }
});

// after the Monthly Production Planning block, add:

// ──────────────────────────────────────────────────────────────────────────────
//                    Blasting Plan child‐table event handlers
// ──────────────────────────────────────────────────────────────────────────────
frappe.ui.form.on('Blasting Blocks Planned', {
  block_length:       (frm, cdt, cdn) => { recompute(frm,cdt,cdn); frm.trigger('update_planned_dozer_volumes'); },
  block_width:        (frm, cdt, cdn) => { recompute(frm,cdt,cdn); frm.trigger('update_planned_dozer_volumes'); },
  blasting_depth:     (frm, cdt, cdn) => { recompute(frm,cdt,cdn); frm.trigger('update_planned_dozer_volumes'); },
  dozing_percentage:  (frm, cdt, cdn) => { recompute(frm,cdt,cdn); frm.trigger('update_planned_dozer_volumes'); }
});

// Hook equipment-count update on child-table changes
frappe.ui.form.on('Excavator Truck Link', {
  excavator: frm => frm.trigger('update_equipment_counts'),
  truck:     frm => frm.trigger('update_equipment_counts')
});

frappe.ui.form.on('Dozers Planned', {
  asset_name: frm => frm.trigger('update_equipment_counts')
});

function recompute(frm, cdt, cdn) {
  const row = locals[cdt][cdn];
  console.log('Recompute called', row.block_length, row.block_width, row.blasting_depth);
  // Requirement 2: block_bcm = length × width × depth
  const bcm = (row.block_length   || 0)
            * (row.block_width    || 0)
            * (row.blasting_depth || 0);

  frappe.model.set_value(cdt, cdn, 'block_bcm', bcm);

  // once bcm is set, update dozing too
  recompute_dozing(frm, cdt, cdn);
}

function recompute_dozing(frm, cdt, cdn) {
  const row = locals[cdt][cdn];
  console.log('Recompute dozing', row.block_bcm, row.dozing_percentage);
  // Requirement 3: block_dozing_bcms = block_bcm × dozing_percentage
  const dz = (row.block_bcm || 0)
           * ((row.dozing_percentage || 0) / 100);

  frappe.model.set_value(cdt, cdn, 'block_dozing_bcms', dz);
}


function renderTeam(container, excavatorId, excavatorModel, truckList) {
  const teamId = excavatorId || 'unassigned';
  const label = excavatorId
    ? `⛏️ ${excavatorId} - ${excavatorModel}`
    : '📦 Unassigned Trucks';

  const section = $(`
    <div class="team-section" style="margin-bottom:20px;">
      <h4>${label}</h4>
      <ul class="truck-bin" data-excavator="${teamId}" style="min-height: 50px; background: #f9f9f9; border: 1px solid #ccc; padding: 10px; border-radius: 4px; list-style: none;"></ul>
    </div>
  `);

  truckList.forEach(truck => {
    const item = $(`
      <li class="truck-item" data-truck="${truck.id}" style="margin: 5px 0; padding: 6px 12px; background: #e3f2fd; border-radius: 3px;">
        🚚 ${truck.id} - ${truck.model}
      </li>
    `);
    section.find('.truck-bin').append(item);
  });

  container.append(section);

  console.log(`🧱 Rendered team: ${label} with ${truckList.length} truck(s)`);

}

function enableDragAndDrop(frm) {
  $('.truck-bin').each(function () {
    Sortable.create(this, {
      group: 'trucks',
      animation: 150,
      onAdd(evt) {
        const truckId = evt.item.dataset.truck;
        const newExcavator = evt.to.dataset.excavator === 'unassigned' ? null : evt.to.dataset.excavator;

        console.log(`📦 Truck '${truckId}' moved to → ${newExcavator || 'Unassigned'}`);

        // Find matching row and update its excavator field
        const row = frm.doc.excavator_truck_assignments.find(r => r.truck === truckId);
        if (row) {
          row.excavator = newExcavator;
          frm.dirty();
          frm.save()
            .then(() => console.log(`✅ Saved: ${truckId} → ${newExcavator || 'Unassigned'}`))
            .catch(err => console.error(`❌ Save failed for ${truckId}:`, err));
        } else {
          console.warn("⚠️ Could not find truck row:", truckId);
        }
      }
    });
  });
}

function addExcavatorsOnce(frm) {
  console.log("🔄 Attempting to add unassigned Excavators...");

  frappe.db.get_list('Asset', {
    filters: { asset_category: 'Excavator', location: frm.doc.location, docstatus: 1 },
    fields: ['name', 'item_name'],
    limit: 100
  }).then(excavators => {
    let added = 0;
    excavators.forEach(asset => {
      const alreadyExists = frm.doc.excavator_truck_assignments.some(
        r => r.excavator === asset.name
      );
      if (!alreadyExists) {
        const row = frm.add_child("excavator_truck_assignments");
        row.excavator = asset.name;
        row.excavator_model = asset.item_name;
        row.truck = null;
        added++;
      }
    });
    if (added) {
      frm.save().then(() => {
        console.log(`✅ Added ${added} excavator(s).`);
        renderTruckAssignmentUI(frm);
      });
    } else {
      frappe.msgprint("No new excavators to add.");
    }
  });
}

function addTrucksOnce(frm) {
  console.log("🔄 Attempting to add unassigned Trucks...");
  frappe.db.get_list('Asset', {
    filters: { asset_category: 'ADT', location: frm.doc.location, docstatus: 1 },
    fields: ['name', 'item_name'],
    limit: 100
  }).then(trucks => {
    let added = 0;
    trucks.forEach(asset => {
      if (!frm.doc.excavator_truck_assignments.some(r => r.truck === asset.name)) {
        const row = frm.add_child("excavator_truck_assignments");
        row.truck       = asset.name;
        row.truck_model = asset.item_name;
        row.excavator   = null;
        added++;
      }
    });
    if (added) {
      frm.save().then(() => {
        console.log(`✅ Added ${added} truck(s).`);
        renderTruckAssignmentUI(frm);
      });
    } else {
      frappe.msgprint("No new trucks to add.");
    }
  });
}

// Add Dozers handler
function addDozersOnce(frm) {
  console.log("🔄 Attempting to add unassigned Dozers...");
  frappe.db.get_list('Asset', {
    filters: { asset_category: 'Dozer', location: frm.doc.location, docstatus: 1 },
    fields: ['name', 'item_name'],
    limit: 100
  }).then(dozers => {
    console.log('Assets fetched for dozers:', dozers);
    let added = 0;
    dozers.forEach(asset => {
      const exists = frm.doc.dozer_table.some(r => r.asset_name === asset.name);
      if (!exists) {
        console.log('Adding dozer:', asset.name, asset.item_name);
        const row = frm.add_child('dozer_table');
        row.asset_name = asset.name;
        row.item_name = asset.item_name;
        added++;
      }
    });
    console.log(`Added ${added} new dozer(s)`);
    if (added) {
      frm.save().then(() => {
        console.log(`✅ Added ${added} dozer(s) and saved form`);
        renderDozerAssignmentUI(frm);
      });
    } else {
      frappe.msgprint("No new dozers to add.");
    }
  });
}


function renderTruckAssignmentUI(frm) {
  console.log("🎯 Rendering Excavator/Truck UI");

  // 1) Clear previous HTML
  const wrapper = frm.get_field('dnd_html_truck_ui').$wrapper.empty();

 const controls = $(`
    <div style="margin-bottom:12px;display:flex;gap:8px;">
      <button id="add-excavators" class="btn btn-primary btn-sm">➕ Add Excavators</button>
      <button id="add-trucks"     class="btn btn-secondary btn-sm">➕ Add Trucks</button>
    </div>
  `).appendTo(wrapper);

  controls
    .find('#add-excavators')
    .off('click')
    .on('click', () => addExcavatorsOnce(frm));
  controls
    .find('#add-trucks')
    .off('click')
    .on('click', () => addTrucksOnce(frm));

  // 3) Build a map of { excavator → [ trucks ] } and list of unassigned
  const assignments = frm.doc.excavator_truck_assignments || [];
  const teamsMap    = {};
  const unassigned  = [];

  assignments.forEach(r => {
    if (r.excavator) {
      teamsMap[r.excavator] = teamsMap[r.excavator] || {
        model:  r.excavator_model || '',
        trucks: []
      };
      if (r.truck) {
        teamsMap[r.excavator].trucks.push({
          id:    r.truck,
          model: r.truck_model || ''
        });
      }
    } else if (r.truck) {
      unassigned.push({
        id:    r.truck,
        model: r.truck_model || ''
      });
    }
  });

  // 4) Two-column layout
  const container = $(`
    <div style="display:flex;gap:24px;">
      <div id="teams-col"      style="flex:1;"></div>
      <div id="unassigned-col" style="flex:1;"></div>
    </div>
  `).appendTo(wrapper);

  //
  // 5) Render each Excavator team
  //
  const teamsCol = container.find('#teams-col');
  Object.entries(teamsMap).forEach(([excId, data]) => {
    const section = $(`
      <div style="position:relative;padding:12px;margin-bottom:20px;
                  background:#fafafa;border:1px solid #ddd;border-radius:4px;">
        <h4>⛏️ ${excId} — ${data.model}</h4>
        <ul class="truck-bin" data-excavator="${excId}"
            style="min-height:50px;list-style:none;padding:0;margin:0;">
        </ul>
      </div>
    `);

    // • Unassign all trucks in team
    $('<button class="btn btn-danger btn-xs" ' +
      'style="position:absolute;background:transparent;top:8px;right:8px;">🗑️</button>')
      .appendTo(section)
      .on('click', () => {
        console.log("🗑️ Unassigning all trucks from team:", excId);
        // Find all rows with this excavator and unassign them
        (frm.doc.excavator_truck_assignments || []).forEach(row => {
          if (row.excavator === excId) {
            row.excavator = null;
            row.excavator_model = null;
          }
        });
        frm.refresh_field('excavator_truck_assignments');
        
          console.log("✅ All trucks unassigned from team");
          renderTruckAssignmentUI(frm);
        frm.save();
      });

    // • Unassign individual trucks
    data.trucks.forEach(t => {
      const li = $(`
        <li class="truck-item"
            data-truck="${t.id}"
            style="display:flex;justify-content:space-between;
                  padding:6px 12px;margin:4px 0;
                  background:#e3f2fd;border-radius:3px;">
          🚚 ${t.id} — ${t.model}
        </li>
      `);

      $('<button class="btn btn-danger btn-xs" style = "background:transparent;">🗑️</button>')
        .appendTo(li)
        .on('click', () => {
          console.log("🗑️ Unassigning truck:", t.id);
          // Find the row by truck ID and unassign it
          const row = (frm.doc.excavator_truck_assignments || []).find(r => r.truck === t.id);
          if (row) {
            frappe.model.set_value(row.doctype, row.name, {
              excavator: null,
              excavator_model: null
            }).then(() => {
              frm.refresh_field('excavator_truck_assignments');
              renderTruckAssignmentUI(frm);
            });
          }
        });
      section.find('.truck-bin').append(li);
    });

    teamsCol.append(section);
  });

  //
  // 6) Render Unassigned Trucks (keep existing delete functionality)
  //
  const uaCol = container.find('#unassigned-col');
  const uaSec = $(`
    <div style="padding:12px;margin-bottom:20px;
                background:#fff8e1;border:1px solid #f0e6a1;border-radius:4px;">
      <h4>📦 Unassigned Trucks</h4>
      <ul class="truck-bin" data-excavator="unassigned"
          style="min-height:50px;list-style:none;padding:0;margin:0;">
      </ul>
    </div>
  `).appendTo(uaCol);

  unassigned.forEach(t => {
    const li = $(`
      <li class="truck-item"
          data-truck="${t.id}"
          style="display:flex;justify-content:space-between;
                padding:6px 12px;margin:4px 0;
                background:#ffefd5;border-radius:3px;">
        🚚 ${t.id} — ${t.model}
      </li>
    `);

   
    

    uaSec.find('.truck-bin').append(li);
  });

  // 7) Wire up drag & drop
  enableDragAndDrop(frm);
}

//
// Single, canonical renderDozerAssignmentUI
//
function renderDozerAssignmentUI(frm) {
  console.log("🎯 Rendering Dozer UI");

  // Clear previous HTML
  const wrapper = frm.get_field('dnd_dozer_assigned').$wrapper.empty();

  // Add Dozers button
  $('<div style="margin-bottom:12px;">' +
    '<button type="button" id="add-dozers" class="btn btn-primary btn-sm">' +
    '➕ Add Dozers' +
    '</button>' +
    '</div>').appendTo(wrapper)
    .find('#add-dozers')
    .on('click', () => addDozersOnce(frm));

  const container = $('<div id="dozer-container">').appendTo(wrapper);

  // Return if no dozers
  if (!frm.doc.dozer_table || !frm.doc.dozer_table.length) {
    container.append('<p><em>No dozers assigned yet.</em></p>');
    return;
  }

  // Load dozing_type options
  const df = frappe.meta.get_docfield('Dozers Planned', 'dozing_type', frm.doc.name);
  const DOZING_TYPE_OPTIONS = (df.options || '').split('\n').filter(Boolean).map(o => ({ value: o, label: o }));

  // Create cards for each dozer
  frm.doc.dozer_table.forEach((row, idx) => {
    if (!row || !row.asset_name) return;

    const card = $(`
      <div class="dozer-card" data-dozer-name="${row.asset_name}" 
           style="position:relative;padding:12px;margin-bottom:16px;
           background:#f0f0f0;border-radius:4px;">
        <strong>🛠️ ${row.asset_name}</strong><br>
        <small>${row.item_name}</small><br>
        <label style="display:block;margin-top:8px;">
          Dozing Type:
          <select class="dozing-type-select"></select>
        </label>
      </div>
    `);

    // Populate select options
    DOZING_TYPE_OPTIONS.forEach(opt => {
      card.find('.dozing-type-select').append($(`<option value="${opt.value}">${opt.label}</option>`));
    });

    // Set current value
    card.find('.dozing-type-select').val(row.dozing_type || '');

    // Handle type changes
    card.find('.dozing-type-select').on('change', e => {
      const newType = e.target.value;
      frm.doc.dozer_table[idx].dozing_type = newType;
      frm.dirty();
      frm.save().catch(console.error);
    });

    // Remove button - using the same reliable pattern as teams removal
    $('<button class="btn btn-danger btn-xs" ' +
      'style="position:absolute;background:transparent;top:8px;right:8px;">🗑️</button>')
      .appendTo(card)
      .on('click', () => {
        const dozerName = card.attr('data-dozer-name');
        console.log("🗑️ Removing dozer:", dozerName);
        
        // Find and remove the row from dozer_table
        frm.doc.dozer_table = (frm.doc.dozer_table || []).filter(
          r => r.asset_name !== dozerName
        );
        
        // Refresh and save
        frm.refresh_field('dozer_table');
        
          console.log("✅ Dozer removed successfully");
          renderDozerAssignmentUI(frm); // Refresh UI
        
      });

    container.append(card);
  });
}

