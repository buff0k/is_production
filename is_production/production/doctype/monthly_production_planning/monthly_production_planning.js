frappe.ui.form.on('Monthly Production Planning', {
    // Section 1: Introduction - Monthly Production Planning
    refresh: function(frm) {
        console.log("Form Refresh triggered");

        // Disable onboarding tour if enabled
        if (frappe.ui.init_onboarding_tour) {
            frappe.ui.init_onboarding_tour = function() {};
        }

        // Button for populating Monthly Production Days
        frm.add_custom_button(__('Populate Monthly Production Days'), function(event) {
            if (event && event.currentTarget) {
                event.currentTarget.blur();
            }
            frm.trigger('populate_monthly_prod_days');
        }, __('Actions'));

        // Button for clearing Production Days
        frm.add_custom_button(__('Clear Production Days'), function(event) {
            if (event && event.currentTarget) {
                event.currentTarget.blur();
            }
            frm.trigger('clear_production_days');
        }, __('Actions'));

        // --- Updated Modal Event Handlers ---
        $(document).on('hide.bs.modal', function (event) {
            let modal = event.target;
            if (modal.contains(document.activeElement)) {
                document.activeElement.blur();
            }
            modal.setAttribute("inert", "");
        });
        $(document).on('hidden.bs.modal', function (event) {
            let modal = event.target;
            requestAnimationFrame(() => {
                modal.removeAttribute("aria-hidden");
                modal.removeAttribute("inert");
                modal.querySelectorAll("button, input, a, textarea, select").forEach(el => el.blur());
            });
        });
        $(document).on('shown.bs.modal', function (event) {
            let modal = event.target;
            modal.removeAttribute("inert");
            modal.removeAttribute("aria-hidden");
            let focusable = modal.querySelector("button, input, a, textarea, select");
            if (focusable) {
                focusable.focus();
            }
        });
    },

    // Section 2: Populate Monthly Production Days Function
    populate_monthly_prod_days: function(frm) {
        try {
            if (document.activeElement) {
                document.activeElement.blur();
            }

            console.log("populate_monthly_prod_days triggered");
            console.log("prod_month_start_date:", frm.doc.prod_month_start_date, typeof frm.doc.prod_month_start_date);
            console.log("prod_month_end_date:", frm.doc.prod_month_end_date, typeof frm.doc.prod_month_end_date);
            if (!frm.doc.prod_month_start_date || !frm.doc.prod_month_end_date) {
                frappe.msgprint(__('Please select valid production start and end dates.'));
                console.log("Missing start or end date");
                return;
            }

            console.log("weekday_shift_hours:", frm.doc.weekday_shift_hours, typeof frm.doc.weekday_shift_hours);
            console.log("saturday_shift_hours:", frm.doc.saturday_shift_hours, typeof frm.doc.saturday_shift_hours);
            console.log("num_sat_shifts:", frm.doc.num_sat_shifts, typeof frm.doc.num_sat_shifts);
            if (
                frm.doc.weekday_shift_hours == null || frm.doc.weekday_shift_hours === "" ||
                frm.doc.saturday_shift_hours == null || frm.doc.saturday_shift_hours === "" ||
                frm.doc.num_sat_shifts == null || frm.doc.num_sat_shifts === ""
            ) {
                frappe.msgprint(__('Please populate Weekday Shift Hours, Saturday Shift Hours, and Number of Saturday Shifts.'));
                console.log("Missing shift hour fields");
                return;
            }

            let start_date = frappe.datetime.str_to_obj(frm.doc.prod_month_start_date);
            let end_date = frappe.datetime.str_to_obj(frm.doc.prod_month_end_date);

            console.log("Start Date:", start_date);
            console.log("End Date:", end_date);
            if (!start_date || !end_date) {
                frappe.msgprint(__('Invalid production start or end date format.'));
                console.log("Invalid start or end date format");
                return;
            }

            frm.clear_table('month_prod_days');
            console.log("Cleared 'month_prod_days' table");

            let total_day_hours = 0;
            let total_night_hours = 0;
            let total_morning_hours = 0;
            let total_afternoon_hours = 0;

            const weekday_shift_hours = Number(frm.doc.weekday_shift_hours);
            const saturday_shift_hours = Number(frm.doc.saturday_shift_hours);
            const num_sat_shifts = Number(frm.doc.num_sat_shifts);

            let current_date = new Date(start_date);
            while (current_date <= end_date) {
                let day_date = new Date(current_date);
                let day_of_week = day_date.toLocaleDateString('en-US', { weekday: 'long' });
                console.log('Processing Date:', day_date, 'Day of Week:', day_of_week);

                let day_shift_hours = 0, night_shift_hours = 0;
                let morning_shift_hours = 0, afternoon_shift_hours = 0;

                if (frm.doc.shift_system === '2x12Hour') {
                    if (day_of_week === 'Sunday') {
                        day_shift_hours = 0;
                        night_shift_hours = 0;
                    } else if (day_of_week === 'Saturday') {
                        if (num_sat_shifts === 1) {
                            day_shift_hours = saturday_shift_hours;
                            night_shift_hours = 0;
                        } else if (num_sat_shifts === 2) {
                            day_shift_hours = saturday_shift_hours;
                            night_shift_hours = saturday_shift_hours;
                        } else {
                            day_shift_hours = saturday_shift_hours;
                            night_shift_hours = saturday_shift_hours;
                        }
                    } else {
                        day_shift_hours = weekday_shift_hours;
                        night_shift_hours = weekday_shift_hours;
                    }
                } else if (frm.doc.shift_system === '3x8Hour') {
                    if (day_of_week === 'Sunday') {
                        morning_shift_hours = 0;
                        afternoon_shift_hours = 0;
                        night_shift_hours = 0;
                    } else if (day_of_week === 'Saturday') {
                        if (num_sat_shifts === 1) {
                            morning_shift_hours = saturday_shift_hours;
                            afternoon_shift_hours = 0;
                            night_shift_hours = 0;
                        } else if (num_sat_shifts === 2) {
                            morning_shift_hours = saturday_shift_hours;
                            afternoon_shift_hours = saturday_shift_hours;
                            night_shift_hours = 0;
                        } else if (num_sat_shifts === 3) {
                            morning_shift_hours = saturday_shift_hours;
                            afternoon_shift_hours = saturday_shift_hours;
                            night_shift_hours = saturday_shift_hours;
                        } else {
                            morning_shift_hours = saturday_shift_hours;
                            afternoon_shift_hours = saturday_shift_hours;
                            night_shift_hours = saturday_shift_hours;
                        }
                    } else {
                        morning_shift_hours = weekday_shift_hours;
                        afternoon_shift_hours = weekday_shift_hours;
                        night_shift_hours = weekday_shift_hours;
                    }
                }

                total_day_hours += day_shift_hours;
                total_night_hours += night_shift_hours;
                total_morning_hours += morning_shift_hours;
                total_afternoon_hours += afternoon_shift_hours;

                let row = frm.add_child('month_prod_days');
                row.shift_start_date = frappe.datetime.obj_to_str(day_date);
                row.day_week = day_of_week;
                row.shift_day_hours = day_shift_hours;
                row.shift_night_hours = night_shift_hours;
                row.shift_morning_hours = morning_shift_hours;
                row.shift_afternoon_hours = afternoon_shift_hours;

                current_date.setDate(current_date.getDate() + 1);
            }

            frm.set_value('tot_shift_day_hours', total_day_hours);
            frm.set_value('tot_shift_night_hours', total_night_hours);
            frm.set_value('tot_shift_morning_hours', total_morning_hours);
            frm.set_value('tot_shift_afternoon_hours', total_afternoon_hours);
            frm.set_value('total_month_prod_hours', total_day_hours + total_night_hours + total_morning_hours + total_afternoon_hours);

            frm.trigger('recalculate_totals');
            frm.refresh_field('month_prod_days');
            frappe.msgprint(__('Monthly Production Days table has been populated.'));
        } catch (error) {
            console.error('Error in populate_monthly_prod_days:', error);
            frappe.msgprint(__('An error occurred: ' + error.message));
        }
    },

    // Section 3: Location Function
    location: function(frm) {
        if (frm.doc.location) {
            frm.clear_table('prod_excavators');
            frm.clear_table('prod_trucks');
            frm.clear_table('dozer_table');
            frm.refresh_fields(['prod_excavators', 'prod_trucks', 'dozer_table']);

            // Fetch Excavators
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Asset',
                    filters: {
                        location: frm.doc.location,
                        asset_category: 'Excavator',
                        docstatus: 1
                    },
                    fields: ['asset_name', 'item_name', 'asset_category']
                },
                callback: function(r) {
                    if (r && r.message) {
                        r.message.forEach(function(asset) {
                            let row = frm.add_child('prod_excavators');
                            row.asset_name = asset.asset_name;
                            row.item_name = asset.item_name;
                        });
                        frm.refresh_field('prod_excavators');
                        frm.set_value('num_excavators', frm.doc.prod_excavators.length);
                    } else {
                        frappe.msgprint(__('No Excavators found for the selected location.'));
                        frm.set_value('num_excavators', 0);
                    }
                }
            });

            // Fetch Trucks
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Asset',
                    filters: {
                        location: frm.doc.location,
                        asset_category: ['in', ['ADT', 'RIGID']],
                        docstatus: 1
                    },
                    fields: ['asset_name', 'item_name', 'asset_category']
                },
                callback: function(r) {
                    if (r && r.message) {
                        r.message.forEach(function(asset) {
                            let row = frm.add_child('prod_trucks');
                            row.asset_name = asset.asset_name;
                            row.item_name = asset.item_name;
                            row.asset_category = asset.asset_category;
                        });
                        frm.refresh_field('prod_trucks');
                        frm.set_value('num_trucks', frm.doc.prod_trucks.length);
                    } else {
                        frappe.msgprint(__('No Trucks found for the selected location.'));
                        frm.set_value('num_trucks', 0);
                    }
                }
            });

            // Fetch Dozers
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Asset',
                    filters: {
                        location: frm.doc.location,
                        asset_category: 'Dozer',
                        docstatus: 1
                    },
                    fields: ['asset_name', 'item_name']
                },
                callback: function(r) {
                    if (r && r.message) {
                        r.message.forEach(function(asset) {
                            let row = frm.add_child('dozer_table');
                            row.asset_name = asset.asset_name;
                            row.item_name = asset.item_name;
                        });
                        frm.refresh_field('dozer_table');
                        frm.set_value('num_dozers', frm.doc.dozer_table.length);
                    } else {
                        frappe.msgprint(__('No Dozers found for the selected location.'));
                        frm.set_value('num_dozers', 0);
                    }
                }
            });
        } else {
            frappe.msgprint(__('Please select a location.'));
        }
    },

    // Section 4: Clear Production Days Function
    clear_production_days: function(frm) {
        frm.clear_table('month_prod_days');
        frm.refresh_field('month_prod_days');
        frm.set_value('tot_shift_day_hours', 0);
        frm.set_value('tot_shift_night_hours', 0);
        frm.set_value('tot_shift_morning_hours', 0);
        frm.set_value('tot_shift_afternoon_hours', 0);
        frm.set_value('total_month_prod_hours', 0);
        frm.set_value('num_prod_days', 0);
        frm.set_value('target_bcm_day', 0);
        frm.set_value('target_bcm_hour', 0);
        frm.set_value('num_excavators', 0);
        frm.set_value('num_trucks', 0);
        frm.set_value('num_dozers', 0);
        frappe.msgprint(__('Monthly Production Days table has been cleared.'));
    },

    // Section 5: Calculate Production Month End
    prod_month_end_date: function(frm) {
        let selected_date = frm.doc.prod_month_end_date;
        if (selected_date) {
            let date_obj = new Date(selected_date);
            let last_day_of_month = new Date(date_obj.getFullYear(), date_obj.getMonth() + 1, 0);

            frm.set_value('prod_month_end', frappe.datetime.obj_to_str(last_day_of_month));
            frappe.msgprint(__('Production month end has been set to the last day of the month.'));
        }
    },

    // Section 6: Monthly Target BCM & Recalculate Totals Functions
    monthly_target_bcm: function(frm) {
        frm.trigger('recalculate_totals');
    },

    recalculate_totals: function(frm) {
        let total_day_hours = 0;
        let total_night_hours = 0;
        let total_morning_hours = 0;
        let total_afternoon_hours = 0;
        let num_prod_days = 0;

        frm.doc.month_prod_days.forEach(row => {
            total_day_hours += row.shift_day_hours || 0;
            total_night_hours += row.shift_night_hours || 0;
            total_morning_hours += row.shift_morning_hours || 0;
            total_afternoon_hours += row.shift_afternoon_hours || 0;

            if ((row.shift_day_hours || 0) > 0 || 
                (row.shift_night_hours || 0) > 0 || 
                (row.shift_morning_hours || 0) > 0 || 
                (row.shift_afternoon_hours || 0) > 0) {
                num_prod_days++;
            }
        });

        let total_month_prod_hours = total_day_hours + total_night_hours + total_morning_hours + total_afternoon_hours;

        frm.set_value('tot_shift_day_hours', total_day_hours);
        frm.set_value('tot_shift_night_hours', total_night_hours);
        frm.set_value('tot_shift_morning_hours', total_morning_hours);
        frm.set_value('tot_shift_afternoon_hours', total_afternoon_hours);
        frm.set_value('total_month_prod_hours', total_month_prod_hours);
        frm.set_value('num_prod_days', num_prod_days);

        if (frm.doc.monthly_target_bcm) {
            frm.set_value('target_bcm_day', frm.doc.monthly_target_bcm / num_prod_days);
            frm.set_value('target_bcm_hour', frm.doc.monthly_target_bcm / total_month_prod_hours);
        } else {
            frm.set_value('target_bcm_day', 0);
            frm.set_value('target_bcm_hour', 0);
        }
    },

    // Section 7: Update Month-to-Date (MTD) Production Function
    update_mtd_production: function(frm) {
        if (!frm.doc.name) {
            frappe.msgprint(__('Please save the document first.'));
            return;
        }

        // First: Process Hourly Production data for shift-wise BCM totals
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Hourly Production',
                filters: {
                    month_prod_planning: frm.doc.name
                },
                fields: ['shift', 'prod_date', 'hour_total_bcm']
            },
            callback: function(r) {
                if (r && r.message) {
                    let hourly_production_data = r.message;
                    
                    // Reset the BCM fields in the child table
                    frm.doc.month_prod_days.forEach(row => {
                        row.day_shift_bcms = 0;
                        row.night_shift_bcms = 0;
                        row.morning_shift_bcms = 0;
                        row.afternoon_shift_bcms = 0;
                        row.total_daily_bcms = 0;
                    });

                    // Sum the production per shift for each day
                    hourly_production_data.forEach(entry => {
                        frm.doc.month_prod_days.forEach(row => {
                            if (row.shift_start_date === frappe.datetime.obj_to_str(entry.prod_date)) {
                                if (entry.shift === 'Day') {
                                    row.day_shift_bcms += entry.hour_total_bcm;
                                } else if (entry.shift === 'Night') {
                                    row.night_shift_bcms += entry.hour_total_bcm;
                                } else if (entry.shift === 'Morning') {
                                    row.morning_shift_bcms += entry.hour_total_bcm;
                                } else if (entry.shift === 'Afternoon') {
                                    row.afternoon_shift_bcms += entry.hour_total_bcm;
                                }
                            }
                        });
                    });

                    // Calculate total daily BCM for each child row
                    frm.doc.month_prod_days.forEach(row => {
                        row.total_daily_bcms =
                            (row.day_shift_bcms || 0) +
                            (row.night_shift_bcms || 0) +
                            (row.morning_shift_bcms || 0) +
                            (row.afternoon_shift_bcms || 0);
                    });

                    // Update parent field: month_actual_bcm
                    let month_actual_bcm = frm.doc.month_prod_days.reduce((sum, row) => {
                        return sum + (row.total_daily_bcms || 0);
                    }, 0);
                    frm.set_value('month_actual_bcm', month_actual_bcm);
                    frm.refresh_field('month_actual_bcm');

                    // Calculate production days and hours completed (up to yesterday)
                    let prod_days_completed = 0;
                    let today = new Date();
                    let yesterday = new Date();
                    yesterday.setDate(today.getDate() - 1);
                    
                    frm.doc.month_prod_days.forEach(row => {
                        let row_date = frappe.datetime.str_to_obj(row.shift_start_date);
                        if (row_date <= yesterday && (
                            (row.shift_day_hours || 0) > 0 ||
                            (row.shift_night_hours || 0) > 0 ||
                            (row.shift_morning_hours || 0) > 0 ||
                            (row.shift_afternoon_hours || 0) > 0
                        )) {
                            prod_days_completed++;
                        }
                    });
                    frm.set_value('prod_days_completed', prod_days_completed);
                    frm.refresh_field('prod_days_completed');

                    let month_prod_hours_completed = 0;
                    frm.doc.month_prod_days.forEach(row => {
                        let row_date = frappe.datetime.str_to_obj(row.shift_start_date);
                        if (row_date <= yesterday && (
                            (row.shift_day_hours || 0) > 0 ||
                            (row.shift_night_hours || 0) > 0 ||
                            (row.shift_morning_hours || 0) > 0 ||
                            (row.shift_afternoon_hours || 0) > 0
                        )) {
                            month_prod_hours_completed += 
                                (row.shift_day_hours || 0) +
                                (row.shift_night_hours || 0) +
                                (row.shift_morning_hours || 0) +
                                (row.shift_afternoon_hours || 0);
                        }
                    });
                    frm.set_value('month_prod_hours_completed', month_prod_hours_completed);
                    frm.refresh_field('month_prod_hours_completed');

                    let mtd_bcm_day = prod_days_completed ? (month_actual_bcm / prod_days_completed) : 0;
                    frm.set_value('mtd_bcm_day', mtd_bcm_day);
                    frm.refresh_field('mtd_bcm_day');

                    let mtd_bcm_hour = month_prod_hours_completed ? (month_actual_bcm / month_prod_hours_completed) : 0;
                    frm.set_value('mtd_bcm_hour', mtd_bcm_hour);
                    frm.refresh_field('mtd_bcm_hour');

                    let month_forecated_bcm = mtd_bcm_hour * (frm.doc.total_month_prod_hours || 0);
                    frm.set_value('month_forecated_bcm', month_forecated_bcm);
                    frm.refresh_field('month_forecated_bcm');

                    // Next: Retrieve Hourly Production records to sum total_ts_bcm and total_dozing_bcm
                    frappe.call({
                        method: 'frappe.client.get_list',
                        args: {
                            doctype: 'Hourly Production',
                            filters: {
                                prod_date: ['>=', frm.doc.prod_month_start_date],
                                prod_date: ['<=', frm.doc.prod_month_end_date],
                                location: frm.doc.location
                            },
                            fields: ['prod_date', 'total_ts_bcm', 'total_dozing_bcm']
                        },
                        callback: function(hr2) {
                            if (hr2 && hr2.message) {
                                let hourly_data2 = hr2.message;
                                let dateSums = {};
                                hourly_data2.forEach(entry => {
                                    let prodDateStr = frappe.datetime.obj_to_str(new Date(entry.prod_date));
                                    if (!dateSums[prodDateStr]) {
                                        dateSums[prodDateStr] = { sum_ts: 0, sum_dozing: 0 };
                                    }
                                    dateSums[prodDateStr].sum_ts += entry.total_ts_bcm;
                                    dateSums[prodDateStr].sum_dozing += entry.total_dozing_bcm;
                                });
                                // Update the child table with the summed values
                                frm.doc.month_prod_days.forEach(row => {
                                    if (dateSums[row.shift_start_date]) {
                                        row.total_dozing_bcms = dateSums[row.shift_start_date].sum_dozing;
                                        row.total_ts_bcms = dateSums[row.shift_start_date].sum_ts;
                                    }
                                });
                                frm.refresh_field('month_prod_days');

                                // Sum the child records' totals and update the parent fields
                                let sum_total_ts_bcms = 0;
                                let sum_total_dozing_bcms = 0;
                                frm.doc.month_prod_days.forEach(row => {
                                    sum_total_ts_bcms += row.total_ts_bcms || 0;
                                    sum_total_dozing_bcms += row.total_dozing_bcms || 0;
                                });
                                frm.set_value('month_act_ts_bcm_tallies', sum_total_ts_bcms);
                                frm.set_value('month_act_dozing_bcm_tallies', sum_total_dozing_bcms);
                                frm.refresh_field('month_act_ts_bcm_tallies');
                                frm.refresh_field('month_act_dozing_bcm_tallies');

                                // Finally: Retrieve Survey data to update additional fields in the child table
                                frappe.call({
                                    method: 'frappe.client.get_list',
                                    args: {
                                        doctype: 'Survey',
                                        filters: [
                                            ['location', '=', frm.doc.location],
                                            ['last_production_shift_start_date', '>=', frm.doc.prod_month_start_date],
                                            ['last_production_shift_start_date', '<=', frm.doc.prod_month_end_date],
                                            ['docstatus', '=', 1]
                                        ],
                                        fields: ['name', 'last_production_shift_start_date', 'total_ts_bcm', 'total_dozing_bcm']
                                    },
                                    callback: function(sr) {
                                        if (sr && sr.message) {
                                            let survey_data = sr.message;
                                            survey_data.forEach(survey => {
                                                frm.doc.month_prod_days.forEach(row => {
                                                    if (row.shift_start_date === frappe.datetime.obj_to_str(new Date(survey.last_production_shift_start_date))) {
                                                        // Set the survey override fields
                                                        row.tot_cum_dozing_survey = survey.total_dozing_bcm;
                                                        row.tot_cum_ts_survey = survey.total_ts_bcm;
                                                    }
                                                });
                                            });
                                            frm.refresh_field('month_prod_days');
                                        }
                                        
                                        // ---- New Cumulative Calculation with Survey Overrides ----
                                        let cumulative_dozing = 0;
                                        let cumulative_ts = 0;
                                        // Sort the child records by shift_start_date to ensure sequential processing
                                        frm.doc.month_prod_days.sort((a, b) => new Date(a.shift_start_date) - new Date(b.shift_start_date));
                                        frm.doc.month_prod_days.forEach(row => {
                                            // For Dozing: if survey override exists and is >0, use that value
                                            if (row.tot_cum_dozing_survey && row.tot_cum_dozing_survey > 0) {
                                                cumulative_dozing = row.tot_cum_dozing_survey;
                                                row.tot_cumulative_dozing_bcms = cumulative_dozing;
                                            } else {
                                                cumulative_dozing += row.total_dozing_bcms || 0;
                                                row.tot_cumulative_dozing_bcms = cumulative_dozing;
                                            }
                                            
                                            // For TS: if survey override exists and is >0, use that value
                                            if (row.tot_cum_ts_survey && row.tot_cum_ts_survey > 0) {
                                                cumulative_ts = row.tot_cum_ts_survey;
                                                row.cum_ts_bcms = cumulative_ts;
                                            } else {
                                                cumulative_ts += row.total_ts_bcms || 0;
                                                row.cum_ts_bcms = cumulative_ts;
                                            }
                                        });
                                        frm.refresh_field('month_prod_days');
                                        frappe.msgprint(__('Month-to-Date Production updated successfully.'));
                                    }
                                });
                            }
                        }
                    });
                } else {
                    frappe.msgprint(__('No Hourly Production data found for this Monthly Production Planning document.'));
                }
            }
        });
    },
});

// Section 8: Trigger Sections
frappe.ui.form.on('Monthly Production Days', {
    shift_day_hours: function(frm, cdt, cdn) {
        frm.trigger('recalculate_totals');
    },
    shift_night_hours: function(frm, cdt, cdn) {
        frm.trigger('recalculate_totals');
    },
    shift_morning_hours: function(frm, cdt, cdn) {
        frm.trigger('recalculate_totals');
    },
    shift_afternoon_hours: function(frm, cdt, cdn) {
        frm.trigger('recalculate_totals');
    }
});
