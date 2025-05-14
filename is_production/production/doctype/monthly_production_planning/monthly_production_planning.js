// Helper: Reapply default_excavator options on refresh and location
function updateDefaultExcavatorOptions(frm) {
  if (!frm.doc.location) return;
  frappe.call({
    method: 'frappe.client.get_list',
    args: {
      doctype: 'Asset',
      filters: [
        ['location', '=', frm.doc.location],
        ['asset_category', '=', 'Excavator'],
        ['docstatus', '=', 1]
      ],
      fields: ['asset_name']
    },
    callback: r => {
      const names = (r.message || []).map(a => a.asset_name);
      const opts  = names.join('\n');
      console.log('[Defaults] ↺ Resetting excavator options:', names);
      const grid = frm.get_field('prod_trucks').grid;
      grid.update_docfield_property('default_excavator', 'options', opts);
      frm.refresh_field('prod_trucks');
    },
    error: err => {
      console.error('[Defaults] Error fetching Excavators:', err);
      logError('updateDefaultExcavatorOptions', err);
    }
  });
}

/**
 * Logs a diagnostic message or exception to the console
 * and into the Error Log DocType (method field).
 */
function logError(context, data) {
  console.error(`ERROR — ${context}:`, data);
  const frmDoc = cur_frm?.doc;
  const methodName = frmDoc
    ? `${frmDoc.doctype} ${frmDoc.name} — ${context}`
    : context;
  const message = typeof data === 'object'
    ? JSON.stringify(data, null, 2)
    : String(data);
  frappe.call({
    method: 'frappe.client.insert',
    args: { doc: {
      doctype: 'Error Log',
      method: methodName,
      error: message,
      traceback: message,
      reference_doctype: frmDoc?.doctype,
      reference_name: frmDoc?.name
    }},
    error: err => console.error('Failed to write Error Log:', err)
  });
}
function calculateGeoRefDescription(frm, cdt, cdn) {
  const row  = locals[cdt][cdn];
  const desc = row.geo_mat_type_description || '';
  // Find this row’s index in the geo_mat_layer table (1-based)
  const rows = frm.doc.geo_mat_layer || [];
  const idx  = rows.findIndex(r => r.name === row.name) + 1;
  // Always "<row number> - <description>"
  const combined = `${idx} - ${desc}`;
  frappe.model.set_value(cdt, cdn, 'geo_ref_description', combined);
}

frappe.ui.form.on('Monthly Production Planning', {
  // Section 0: Before Save
  before_save(frm) {
    try {
      frm.doc.month_prod_days?.forEach(r => {
        r.hourly_production_reference = `${frm.doc.name}-${r.shift_start_date}`;
      });
      frm.refresh_field('month_prod_days');
    } catch (e) {
      logError('before_save', e);
    }
  },

  // Section 1: Refresh
  refresh(frm) {
    try {
      frm.add_custom_button(__('Populate Monthly Production Days'),
        () => frm.trigger('populate_monthly_prod_days'), __('Actions')
      );
      frm.add_custom_button(__('Clear Production Days'),
        () => frm.trigger('clear_production_days'), __('Actions')
      );
      if (!frm.doc.__islocal && frm.doc.month_prod_days) {
        frm.doc.month_prod_days.forEach(r => {
          r.hourly_production_reference = `${frm.doc.name}-${r.shift_start_date}`;
        });
        frm.refresh_field('month_prod_days');
        frappe.msgprint(__('References updated.'));
        frm.trigger('update_mtd_production');
        frm.trigger('update_equipment_counts');
      }
      // Reapply dynamic excavator options on load
      if (!frm.doc.__islocal) {
        updateDefaultExcavatorOptions(frm);
      }
            // ← insert geo layer recalculation here
      (frm.doc.geo_mat_layer || []).forEach(row => {
        calculateGeoRefDescription(frm, row.doctype, row.name);
      });
    } catch (e) {
      logError('refresh', e);
    }
  },

  // Section 2: Populate Monthly Production Days
  populate_monthly_prod_days(frm) {
    try {
      if (!frm.doc.prod_month_start_date || !frm.doc.prod_month_end_date) {
        frappe.msgprint(__('Please select production start and end dates.'));
        return;
      }
      if ([frm.doc.weekday_shift_hours, frm.doc.saturday_shift_hours, frm.doc.num_sat_shifts]
          .some(v => v == null)) {
        frappe.msgprint(__('Please enter shift hours and number of Saturday shifts.'));
        return;
      }
      const start = frappe.datetime.str_to_obj(frm.doc.prod_month_start_date);
      const end   = frappe.datetime.str_to_obj(frm.doc.prod_month_end_date);
      frm.clear_table('month_prod_days');
      let totals = { day:0, night:0, morning:0, afternoon:0 };
      const wH = +frm.doc.weekday_shift_hours;
      const sH = +frm.doc.saturday_shift_hours;
      const sSh= +frm.doc.num_sat_shifts;
      for (let d = new Date(start); d <= end; d.setDate(d.getDate()+1)) {
        const dow = d.toLocaleDateString('en-US',{ weekday:'long' });
        let hours = { day:0, night:0, morning:0, afternoon:0 };
        if (frm.doc.shift_system === '2x12Hour') {
          if (dow === 'Saturday') {
            hours.day = sH;
            hours.night = sSh>1 ? sH : 0;
          } else if (dow !== 'Sunday') {
            hours.day = hours.night = wH;
          }
        } else {
          if (dow === 'Saturday') {
            hours.morning = sH;
            if (sSh>1) hours.afternoon = sH;
            if (sSh>2) hours.night     = sH;
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
        tot_shift_day_hours: totals.day,
        tot_shift_night_hours: totals.night,
        tot_shift_morning_hours: totals.morning,
        tot_shift_afternoon_hours: totals.afternoon,
        total_month_prod_hours: totals.day+totals.night+totals.morning+totals.afternoon
      });
      frm.trigger('recalculate_totals');
      frm.refresh_field('month_prod_days');
      frappe.msgprint(__('Monthly Production Days populated.'));
    } catch (e) {
      logError('populate_monthly_prod_days', e);
    }
  },

  // Section 3: Location
  location(frm) {
    try {
      console.log('[Location] 📍 handler start – location =', frm.doc.location);

      if (!frm.doc.location) {
        frappe.msgprint(__('Please select a location.'));
        console.log('[Location] ❌ No location selected, aborting.');
        return;
      }

      // 1. Clear out old rows
      frm.clear_table('prod_excavators');
      frm.clear_table('prod_trucks');
      frm.clear_table('dozer_table');
      frm.refresh_fields(['prod_excavators','prod_trucks','dozer_table']);
      console.log('[Location] 🧹 Cleared prod_excavators, prod_trucks, dozer_table');

      // 2. Fetch Excavators and build default_excavator options
      const excavatorFilters = [
        ['location', '=', frm.doc.location],
        ['asset_category', '=', 'Excavator'],
        ['docstatus', '=', 1]
      ];
      console.log('[Location] 🔍 Fetching Excavators with filters:', excavatorFilters);

      frappe.call({
        method: 'frappe.client.get_list',
        args: {
          doctype: 'Asset',
          filters: excavatorFilters,
          fields: ['asset_name','item_name','asset_category']
        },
        callback: r => {
          const excavators = r.message || [];
          console.log('[Location] ✅ Excavators fetched:', excavators);

          // Populate prod_excavators table
          excavators.forEach(a => {
            const row = frm.add_child('prod_excavators');
            row.asset_name     = a.asset_name;
            row.item_name      = a.item_name;
            row.asset_category = a.asset_category;
          });
          frm.refresh_field('prod_excavators');
          frm.set_value('num_excavators', excavators.length);
          console.log(`[Location] 🏗  Added ${excavators.length} rows to prod_excavators`);

          // Build newline-separated list of excavator names
          const opts = excavators.map(a => a.asset_name).join('\n');
          console.log('[Location] ✏️  Built options string for default_excavator:', opts);

          // Overwrite the Select field’s options in prod_trucks
          const grid = frm.get_field('prod_trucks').grid;
          console.log('[Location] 🔧 prod_trucks grid instance:', grid);
          grid.update_docfield_property('default_excavator', 'options', opts);
          console.log('[Location] 🔄 Called update_docfield_property for default_excavator');
          frm.refresh_field('prod_trucks');
          console.log('[Location] 🎨 Refreshed prod_trucks to apply new options');

          // 3. Fetch Trucks (nested to ensure options applied first)
          const truckFilters = [
            ['location', '=', frm.doc.location],
            ['asset_category', 'in', ['ADT','RIGID']],
            ['docstatus', '=', 1]
          ];
          console.log('[Location] 🔍 Fetching Trucks with filters:', truckFilters);

          frappe.call({
            method: 'frappe.client.get_list',
            args: {
              doctype: 'Asset',
              filters: truckFilters,
              fields: ['asset_name','item_name','asset_category']
            },
            callback: t => {
              const trucks = t.message || [];
              console.log('[Location] ✅ Trucks fetched:', trucks);

              trucks.forEach(a => {
                const row = frm.add_child('prod_trucks');
                row.asset_name     = a.asset_name;
                row.item_name      = a.item_name;
                row.asset_category = a.asset_category;
              });
              frm.refresh_field('prod_trucks');
              frm.set_value('num_trucks', trucks.length);
              console.log(`[Location] 🏗  Added ${trucks.length} rows to prod_trucks`);
            },
            error: err => {
              console.error('[Location] ⚠️ Error fetching Trucks:', err);
              logError('fetchAssets prod_trucks', err);
            }
          });
        },
        error: err => {
          console.error('[Location] ⚠️ Error fetching Excavators:', err);
          logError('fetchAssets prod_excavators', err);
        }
      });

      // 4. Fetch Dozers (independent)
      const dozerFilters = [
        ['location', '=', frm.doc.location],
        ['asset_category', '=', 'Dozer'],
        ['docstatus', '=', 1]
      ];
      console.log('[Location] 🔍 Fetching Dozers with filters:', dozerFilters);

      frappe.call({
        method: 'frappe.client.get_list',
        args: {
          doctype: 'Asset',
          filters: dozerFilters,
          fields: ['asset_name','item_name','asset_category']
        },
        callback: r => {
          const dozers = r.message || [];
          console.log('[Location] ✅ Dozers fetched:', dozers);

          dozers.forEach(a => {
            const row = frm.add_child('dozer_table');
            row.asset_name     = a.asset_name;
            row.item_name      = a.item_name;
            row.asset_category = a.asset_category;
          });
          frm.refresh_field('dozer_table');
          frm.set_value('num_dozers', dozers.length);
          console.log(`[Location] 🏗  Added ${dozers.length} rows to dozer_table`);
        },
        error: err => {
          console.error('[Location] ⚠️ Error fetching Dozers:', err);
          logError('fetchAssets dozer_table', err);
        }
      });

      // Reapply in case nested timing varies
      updateDefaultExcavatorOptions(frm);

    } catch (e) {
      console.error('[Location] 💥 Unexpected error in location handler:', e);
      logError('location', e);
    }
  },

  // Section 4: Clear Production Days
  clear_production_days(frm) {
    try {
      frm.clear_table('month_prod_days');
      frm.refresh_field('month_prod_days');
      [
        'tot_shift_day_hours','tot_shift_night_hours','tot_shift_morning_hours','tot_shift_afternoon_hours',
        'total_month_prod_hours','num_prod_days','target_bcm_day','target_bcm_hour',
        'num_excavators','num_trucks','num_dozers'
      ].forEach(f => frm.set_value(f, 0));
      frappe.msgprint(__('Production Days cleared.'));
    } catch (e) {
      logError('clear_production_days', e);
    }
  },

  // Section 5: prod_month_end_date
  prod_month_end_date(frm) {
    try {
      if (!frm.doc.prod_month_end_date) return;
      const d    = new Date(frm.doc.prod_month_end_date);
      const last = new Date(d.getFullYear(), d.getMonth()+1, 0);
      frm.set_value('prod_month_end', frappe.datetime.obj_to_str(last));
      frappe.msgprint(__('Month end set to last day.'));
    } catch (e) {
      logError('prod_month_end_date', e);
    }
  },

  // Section 6: recalculate_totals
  monthly_target_bcm: frm => frm.trigger('recalculate_totals'),
  recalculate_totals(frm) {
    try {
      let sums = { day:0, night:0, morning:0, afternoon:0, days:0 };
      frm.doc.month_prod_days.forEach(r => {
        const hrs = (r.shift_day_hours||0)
                  + (r.shift_night_hours||0)
                  + (r.shift_morning_hours||0)
                  + (r.shift_afternoon_hours||0);
        if (hrs) sums.days++;
        sums.day      += r.shift_day_hours    || 0;
        sums.night    += r.shift_night_hours  || 0;
        sums.morning  += r.shift_morning_hours|| 0;
        sums.afternoon+= r.shift_afternoon_hours|| 0;
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
        frm.set_value('target_bcm_day',  frm.doc.monthly_target_bcm / sums.days);
        frm.set_value('target_bcm_hour', frm.doc.monthly_target_bcm / totalHrs);
      }
    } catch (e) {
      logError('recalculate_totals', e);
    }
  },

  // Section 7: Update MTD Production
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

            // Aggregate & Write‑back
            const sumsMap = {};
            records.forEach(e => {
              const ts  = e.total_ts_bcm    || 0;
              const dz  = e.total_dozing_bcm|| 0;
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

            // Post‑update Totals
            const tableTotals = frm.doc.month_prod_days.reduce((acc,row) => {
              acc.day       += row.day_shift_bcms    || 0;
              acc.night     += row.night_shift_bcms  || 0;
              acc.morning   += row.morning_shift_bcms|| 0;
              acc.afternoon += row.afternoon_shift_bcms|| 0;
              acc.total     += row.total_daily_bcms  || 0;
              return acc;
            }, { day:0, night:0, morning:0, afternoon:0, total:0 });
            logError('Monthly Prod Days BCM Totals', tableTotals);

            // Cumulative Totals (fixed field names)
            let runTs = 0, runDz = 0;
            frm.doc.month_prod_days
              .slice()
              .sort((a, b) => new Date(a.shift_start_date) - new Date(b.shift_start_date))
              .forEach(rw => {
                // use the actual child‐table field names
                runTs += rw.total_ts_bcms    || 0;
                runDz += rw.total_dozing_bcms|| 0;

                frappe.model.set_value(rw.doctype, rw.name, {
                  cum_ts_bcms:                runTs,
                  tot_cumulative_dozing_bcms: runDz
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
                    ? curr : prev,
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
                  // clear out any previous values
                  frappe.model.set_value(row.doctype, row.name, {
                    tot_cum_dozing_survey: 0,
                    tot_cum_ts_survey:     0,
                    cum_dozing_variance:   0,
                    cum_ts_variance:       0
                  });
                }
              });

              frm.refresh_field('month_prod_days');

              // --- Final parent-level updates (unchanged) ---

              // 4) Parent-level tallies
              let totalTs = 0, totalDz = 0;
              frm.doc.month_prod_days.forEach(r => {
                totalTs += r.total_ts_bcms       || 0;
                totalDz += r.total_dozing_bcms   || 0;
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

  // Section 8: Child Table Triggers
  'Monthly Production Days': {
    shift_day_hours:       frm => frm.trigger('recalculate_totals'),
    shift_night_hours:     frm => frm.trigger('recalculate_totals'),
    shift_morning_hours:   frm => frm.trigger('recalculate_totals'),
    shift_afternoon_hours: frm => frm.trigger('recalculate_totals')
  },

  // Section 9: Update Equipment Counts
  update_equipment_counts(frm) {
    try {
      frm.set_value({
        num_excavators: frm.doc.prod_excavators?.length || 0,
        num_trucks:     frm.doc.prod_trucks?.length    || 0,
        num_dozers:     frm.doc.dozer_table?.length    || 0
      });
      frm.refresh_fields(['num_excavators','num_trucks','num_dozers']);
    } catch (e) {
      logError('update_equipment_counts', e);
    }
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
