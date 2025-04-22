frappe.ui.form.on('Monthly Production Planning', {
    // Section 0: Before Save - Set hourly_production_reference
    before_save: function(frm) {
        if (frm.doc.month_prod_days) {
            frm.doc.month_prod_days.forEach(row => {
                row.hourly_production_reference = frm.doc.name + '-' + row.shift_start_date;
            });
            frm.refresh_field('month_prod_days');
        }
    },

    // Section 1: Refresh - Add buttons, update refs, recalc metrics
    refresh: function(frm) {
        frm.add_custom_button(__('Populate Monthly Production Days'), function() {
            frm.trigger('populate_monthly_prod_days');
        }, __('Actions'));
        frm.add_custom_button(__('Clear Production Days'), function() {
            frm.trigger('clear_production_days');
        }, __('Actions'));

        if (!frm.doc.__islocal && frm.doc.month_prod_days) {
            // Update hourly_production_reference for each row
            frm.doc.month_prod_days.forEach(row => {
                row.hourly_production_reference = frm.doc.name + '-' + row.shift_start_date;
            });
            frm.refresh_field('month_prod_days');
            frappe.msgprint(__('References updated.'));

            // Recalculate metrics and equipment counts
            frm.trigger('update_mtd_production');
            frm.trigger('update_equipment_counts');
        }
    },

    // Section 2: Populate Monthly Production Days
    populate_monthly_prod_days: function(frm) {
        if (!frm.doc.prod_month_start_date || !frm.doc.prod_month_end_date) {
            frappe.msgprint(__('Please select production start and end dates.'));
            return;
        }
        if ([frm.doc.weekday_shift_hours, frm.doc.saturday_shift_hours, frm.doc.num_sat_shifts].some(v => v == null)) {
            frappe.msgprint(__('Please enter shift hours and number of Saturday shifts.'));
            return;
        }
        let start = frappe.datetime.str_to_obj(frm.doc.prod_month_start_date);
        let end   = frappe.datetime.str_to_obj(frm.doc.prod_month_end_date);
        frm.clear_table('month_prod_days');
        let totals = { day:0, night:0, morning:0, afternoon:0 };
        const wH  = +frm.doc.weekday_shift_hours;
        const sH  = +frm.doc.saturday_shift_hours;
        const sSh = +frm.doc.num_sat_shifts;

        for (let d = new Date(start); d <= end; d.setDate(d.getDate()+1)) {
            let dow   = d.toLocaleDateString('en-US',{ weekday:'long' });
            let hours = { day:0, night:0, morning:0, afternoon:0 };

            if (frm.doc.shift_system==='2x12Hour') {
                if (dow==='Saturday') {
                    hours.day   = sH;
                    hours.night = (sSh > 1 ? sH : 0);
                } else if (dow!=='Sunday') {
                    hours.day = hours.night = wH;
                }
            } else {
                if (dow==='Saturday') {
                    hours.morning = sH;
                    if (sSh > 1) hours.afternoon = sH;
                    if (sSh > 2) hours.night     = sH;
                } else if (dow!=='Sunday') {
                    hours.morning = hours.afternoon = hours.night = wH;
                }
            }

            totals.day      += hours.day;
            totals.night    += hours.night;
            totals.morning  += hours.morning;
            totals.afternoon+= hours.afternoon;

            let row = frm.add_child('month_prod_days');
            row.shift_start_date       = frappe.datetime.obj_to_str(d);
            row.day_week               = dow;
            row.shift_day_hours        = hours.day;
            row.shift_night_hours      = hours.night;
            row.shift_morning_hours    = hours.morning;
            row.shift_afternoon_hours  = hours.afternoon;
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
    },

    // Section 3: Location Change - clear equipment tables
    location: function(frm) {
        if (frm.doc.location) {
            ['prod_excavators','prod_trucks','dozer_table'].forEach(tbl =>
                frm.clear_table(tbl)
            );
            frm.refresh_fields(['prod_excavators','prod_trucks','dozer_table']);
            frm.trigger('update_equipment_counts');
        } else {
            frappe.msgprint(__('Please select a location.'));
        }
    },

    // Section 4: Clear Production Days table and totals
    clear_production_days: function(frm) {
        frm.clear_table('month_prod_days');
        frm.refresh_field('month_prod_days');
        [
            'tot_shift_day_hours','tot_shift_night_hours','tot_shift_morning_hours','tot_shift_afternoon_hours',
            'total_month_prod_hours','num_prod_days','target_bcm_day','target_bcm_hour',
            'num_excavators','num_trucks','num_dozers'
        ].forEach(f => frm.set_value(f, 0));
        frappe.msgprint(__('Production Days cleared.'));
    },

    // Section 5: Set last day of month as prod_month_end
    prod_month_end_date: function(frm) {
        if (frm.doc.prod_month_end_date) {
            let d    = new Date(frm.doc.prod_month_end_date);
            let last = new Date(d.getFullYear(), d.getMonth()+1, 0);
            frm.set_value('prod_month_end', frappe.datetime.obj_to_str(last));
            frappe.msgprint(__('Month end set to last day.'));
        }
    },

    // Section 6: Recalculate totals and targets
    monthly_target_bcm: function(frm) {
        frm.trigger('recalculate_totals');
    },
    recalculate_totals: function(frm) {
        let sums = { day:0, night:0, morning:0, afternoon:0, days:0 };
        frm.doc.month_prod_days.forEach(r => {
            let hrs = (r.shift_day_hours||0) + (r.shift_night_hours||0) +
                      (r.shift_morning_hours||0) + (r.shift_afternoon_hours||0);
            if (hrs > 0) sums.days++;
            sums.day      += r.shift_day_hours || 0;
            sums.night    += r.shift_night_hours || 0;
            sums.morning  += r.shift_morning_hours || 0;
            sums.afternoon+= r.shift_afternoon_hours || 0;
        });
        let totalHrs = sums.day + sums.night + sums.morning + sums.afternoon;
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
    },

    // Section 7: Update MTD Production & all downstream metrics in one go
    update_mtd_production: function(frm) {
        if (!frm.doc.name) return frappe.msgprint(__('Save first.'));
        let refs = frm.doc.month_prod_days
                      .map(r => r.hourly_production_reference)
                      .filter(Boolean);
        if (!refs.length) return frappe.msgprint(__('No refs to query.'));

        // 1) Fetch Hourly Production
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Hourly Production',
                filters: [
                    ['month_prod_planning','=', frm.doc.name],
                    ['monthly_production_child_ref','in', refs]
                ],
                fields: ['monthly_production_child_ref as ref','shift','total_ts_bcm','total_dozing_bcm']
            },
            callback: function(r) {
                let sumsMap = {};
                (r.message||[]).forEach(e => {
                    let ts  = e.total_ts_bcm    || 0,
                        dz  = e.total_dozing_bcm|| 0,
                        bcm = ts + dz;
                    sumsMap[e.ref] = sumsMap[e.ref] || { Day:0, Night:0, Morning:0, Afternoon:0, total:0, ts:0, dz:0 };
                    sumsMap[e.ref][e.shift] += bcm;
                    sumsMap[e.ref].total    += bcm;
                    sumsMap[e.ref].ts       += ts;
                    sumsMap[e.ref].dz       += dz;
                });
                // write daily totals back
                frm.doc.month_prod_days.forEach(row => {
                    let s = sumsMap[row.hourly_production_reference] || { Day:0, Night:0, Morning:0, Afternoon:0, total:0, ts:0, dz:0 };
                    frappe.model.set_value(row.doctype, row.name, {
                        day_shift_bcms:     s.Day,
                        night_shift_bcms:   s.Night,
                        morning_shift_bcms: s.Morning,
                        afternoon_shift_bcms:s.Afternoon,
                        total_daily_bcms:   s.total,
                        total_ts_bcms:      s.ts,
                        total_dozing_bcms:  s.dz
                    });
                });
                frm.refresh_field('month_prod_days');

                // 2) Child cumulatives (cum_ts_bcms & tot_cumulative_dozing_bcms)
                let runTs = 0, runDz = 0;
                frm.doc.month_prod_days
                    .slice()
                    .sort((a,b) => new Date(a.shift_start_date) - new Date(b.shift_start_date))
                    .forEach(row => {
                        runTs += row.total_ts_bcms    || 0;
                        runDz += row.total_dozing_bcms|| 0;
                        frappe.model.set_value(row.doctype, row.name, {
                            cum_ts_bcms:                runTs,
                            tot_cumulative_dozing_bcms: runDz
                        });
                    });
                frm.refresh_field('month_prod_days');

                // 3) Fetch Survey & calculate variances + parent metrics
                frappe.call({
                    method: 'frappe.client.get_list',
                    args: {
                        doctype: 'Survey',
                        filters: [
                            ['hourly_prod_ref','in', refs],
                            ['docstatus','=', 1]
                        ],
                        fields: ['hourly_prod_ref as ref','total_dozing_bcm','total_ts_bcm']
                    },
                    callback: function(srv) {
                        const map = {};
                        (srv.message||[]).forEach(s => {
                            map[s.ref] = { dz: s.total_dozing_bcm||0, ts: s.total_ts_bcm||0 };
                        });
                        // survey totals & variances on child rows
                        frm.doc.month_prod_days.forEach(row => {
                            let v = map[row.hourly_production_reference] || { dz:0, ts:0 };
                            let upd = {
                                tot_cum_dozing_survey: v.dz,
                                tot_cum_ts_survey:     v.ts
                            };
                            if (v.dz>0 || v.ts>0) {
                                upd.cum_dozing_variance = v.dz - (row.tot_cumulative_dozing_bcms||0);
                                upd.cum_ts_variance     = v.ts - (row.cum_ts_bcms||0);
                            }
                            frappe.model.set_value(row.doctype, row.name, upd);
                        });
                        frm.refresh_field('month_prod_days');

                        // parent tallies
                        let totalTs = 0, totalDz = 0;
                        frm.doc.month_prod_days.forEach(r => {
                            totalTs += r.total_ts_bcms    || 0;
                            totalDz += r.total_dozing_bcms|| 0;
                        });

                        // survey variance from the most recent non-zero row
                        let varRows = frm.doc.month_prod_days
                            .filter(r => (r.cum_dozing_variance||0)!==0 || (r.cum_ts_variance||0)!==0)
                            .sort((a,b) => new Date(b.shift_start_date) - new Date(a.shift_start_date));
                        let surveyVar = 0;
                        if (varRows.length) {
                            let latest = varRows[0];
                            surveyVar = (latest.cum_dozing_variance||0) + (latest.cum_ts_variance||0);
                        }

                        // progress metrics
                        let today = new Date(),
                            yest  = new Date(today.getFullYear(), today.getMonth(), today.getDate()-1),
                            doneDays=0, doneHrs=0;
                        frm.doc.month_prod_days.forEach(r => {
                            let rd = frappe.datetime.str_to_obj(r.shift_start_date);
                            if (rd <= yest) {
                                let hrs = (r.shift_day_hours||0) + (r.shift_night_hours||0) +
                                          (r.shift_morning_hours||0) + (r.shift_afternoon_hours||0);
                                if (hrs) doneDays++;
                                doneHrs += hrs;
                            }
                        });

                        // final parent updates
                        let actual   = totalTs + totalDz + surveyVar,
                            mtdDay   = actual / (frm.doc.prod_days_completed = doneDays),
                            mtdHr    = actual / (frm.doc.month_prod_hours_completed = doneHrs),
                            forecast = mtdHr * (frm.doc.total_month_prod_hours || 0);

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
                        frappe.msgprint(__('Full MTD & forecast recalculated.'));
                    }
                });
            }
        });
    },

    // Section 8: Child Table Triggers
    'Monthly Production Days': {
        shift_day_hours:       frm => frm.trigger('recalculate_totals'),
        shift_night_hours:     frm => frm.trigger('recalculate_totals'),
        shift_morning_hours:   frm => frm.trigger('recalculate_totals'),
        shift_afternoon_hours: frm => frm.trigger('recalculate_totals')
    },

    // Section 9: Update Equipment Counts
    update_equipment_counts: function(frm) {
        frm.set_value({
            num_excavators: frm.doc.prod_excavators?.length || 0,
            num_trucks:     frm.doc.prod_trucks?.length    || 0,
            num_dozers:     frm.doc.dozer_table?.length    || 0
        });
        frm.refresh_fields(['num_excavators','num_trucks','num_dozers']);
    }
});
