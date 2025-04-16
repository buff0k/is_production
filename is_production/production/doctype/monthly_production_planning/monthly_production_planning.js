// --- Override the onboarding tour early to avoid errors ---
if (frappe.ui && frappe.ui.init_onboarding_tour) {
    frappe.ui.init_onboarding_tour = function() {
        try {
            return;
        } catch (e) {
            console.error("Onboarding tour error suppressed:", e);
        }
    }
}

frappe.ui.form.on('Monthly Production Planning', {
    // Section 1: Introduction - Monthly Production Planning
    refresh: function(frm) {
        console.log("Refresh triggered");

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
        $(document).on('hide.bs.modal', function(event) {
            let modal = event.target;
            if (modal.contains(document.activeElement)) {
                document.activeElement.blur();
            }
            modal.setAttribute("inert", "");
        });
        $(document).on('hidden.bs.modal', function(event) {
            let modal = event.target;
            requestAnimationFrame(() => {
                modal.removeAttribute("aria-hidden");
                modal.removeAttribute("inert");
                modal.querySelectorAll("button, input, a, textarea, select").forEach(el => el.blur());
            });
        });
        $(document).on('shown.bs.modal', function(event) {
            let modal = event.target;
            modal.removeAttribute("inert");
            modal.removeAttribute("aria-hidden");
            let focusable = modal.querySelector("button, input, a, textarea, select");
            if (focusable) {
                focusable.focus();
            }
        });

        // Update hourly production references in child table if document is saved
        if (!frm.doc.__islocal && frm.doc.month_prod_days) {
            frm.doc.month_prod_days.forEach(function(row, index) {
                let referenceValue = frm.doc.name + "-" + row.shift_start_date;
                row.hourly_production_reference = referenceValue;
                console.log("Row " + index + " hourly_production_reference updated to:", referenceValue);
            });
            frm.refresh_field('month_prod_days');
            frappe.msgprint(__('Hourly Production Reference fields updated on refresh.'));
        }
    },

    // Section 2: Populate Monthly Production Days Function
    populate_monthly_prod_days: function(frm) {
        try {
            if (document.activeElement) {
                document.activeElement.blur();
            }
            console.log("populate_monthly_prod_days triggered");

            // Log the parent production start and end dates
            console.log("Production start date from doc:", frm.doc.prod_month_start_date);
            console.log("Production end date from doc:", frm.doc.prod_month_end_date);

            if (!frm.doc.prod_month_start_date || !frm.doc.prod_month_end_date) {
                frappe.msgprint(__('Please select valid production start and end dates.'));
                console.log("Missing start or end date");
                return;
            }
            if (
                frm.doc.weekday_shift_hours == null || frm.doc.weekday_shift_hours === "" ||
                frm.doc.saturday_shift_hours == null || frm.doc.saturday_shift_hours === "" ||
                frm.doc.num_sat_shifts == null || frm.doc.num_sat_shifts === ""
            ) {
                frappe.msgprint(__('Please populate Weekday Shift Hours, Saturday Shift Hours, and Number of Saturday Shifts.'));
                console.log("Missing shift hour fields");
                return;
            }

            // Convert production start and end date strings to Date objects
            let start_date = frappe.datetime.str_to_obj(frm.doc.prod_month_start_date);
            let end_date = frappe.datetime.str_to_obj(frm.doc.prod_month_end_date);
            console.log("Converted start date:", start_date);
            console.log("Converted end date:", end_date);
            if (!start_date || !end_date) {
                frappe.msgprint(__('Invalid production start or end date format.'));
                console.log("Invalid start or end date format");
                return;
            }

            // Clear existing child table entries before populating
            frm.clear_table('month_prod_days');
            let total_day_hours = 0,
                total_night_hours = 0,
                total_morning_hours = 0,
                total_afternoon_hours = 0;

            const weekday_shift_hours = Number(frm.doc.weekday_shift_hours),
                saturday_shift_hours = Number(frm.doc.saturday_shift_hours),
                num_sat_shifts = Number(frm.doc.num_sat_shifts);

            // Start with a new Date cloned from start_date
            let current_date = new Date(start_date);
            while (current_date <= end_date) {
                let day_date = new Date(current_date); // clone current_date for this iteration
                let day_of_week = day_date.toLocaleDateString('en-US', { weekday: 'long' });
                console.log("Processing date:", frappe.datetime.obj_to_str(day_date), "Day of week:", day_of_week);

                let day_shift_hours = 0,
                    night_shift_hours = 0,
                    morning_shift_hours = 0,
                    afternoon_shift_hours = 0;

                // Calculate shift hours based on shift system
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

                // Add a new row in the child table using frappe's obj_to_str for correct formatting
                let row = frm.add_child('month_prod_days');
                let formatted_date = frappe.datetime.obj_to_str(day_date);
                row.shift_start_date = formatted_date;
                row.day_week = day_of_week;
                row.shift_day_hours = day_shift_hours;
                row.shift_night_hours = night_shift_hours;
                row.shift_morning_hours = morning_shift_hours;
                row.shift_afternoon_hours = afternoon_shift_hours;

                console.log("Added row with date:", formatted_date);

                // Increment current_date by one day
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
        let total_day_hours = 0,
            total_night_hours = 0,
            total_morning_hours = 0,
            total_afternoon_hours = 0,
            num_prod_days = 0;

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

    // Section 7: Update Month-to-Date (MTD) Production Function with Debug Logging
    update_mtd_production: function(frm) {
        if (!frm.doc.name) {
            frappe.msgprint(__('Please save the document first.'));
            return;
        }
        // Retrieve Hourly Production records that match:
        // - The current Monthly Production Planning reference,
        // - Production date range, and location.
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Hourly Production',
                filters: [
                    ['month_prod_planning', '=', frm.doc.name],
                    ['prod_date', '>=', frm.doc.prod_month_start_date],
                    ['prod_date', '<=', frm.doc.prod_month_end_date],
                    ['location', '=', frm.doc.location]
                ],
                fields: ['shift', 'prod_date', 'total_ts_bcm', 'total_dozing_bcm']
            },
            callback: function(r) {
                if (r && r.message) {
                    let hourly_data = r.message;
                    let dateSums = {};
                    // Group and sum records per production date and by shift.
                    hourly_data.forEach(entry => {
                        // Convert entry.prod_date to a "YYYY-MM-DD" string.
                        let prodDateStr = frappe.datetime.obj_to_str(new Date(entry.prod_date));
                        if (!dateSums[prodDateStr]) {
                            dateSums[prodDateStr] = { Day: 0, Night: 0, Morning: 0, Afternoon: 0, total: 0 };
                        }
                        let production = (entry.total_ts_bcm || 0) + (entry.total_dozing_bcm || 0);
                        // Sum production per shift type:
                        if (entry.shift in dateSums[prodDateStr]) {
                            dateSums[prodDateStr][entry.shift] += production;
                        }
                        dateSums[prodDateStr].total += production;
                    });
                    console.log("Hourly Production Sums grouped by Date:", dateSums);

                    // For each day in the Monthly Production Planning child table,
                    // update the corresponding production sums and log results.
                    frm.doc.month_prod_days.forEach(row => {
                        let row_date = frappe.datetime.obj_to_str(new Date(row.shift_start_date));
                        if (dateSums[row_date]) {
                            console.log("For date " + row_date + ": ", dateSums[row_date]);
                            row.day_shift_bcms = dateSums[row_date].Day;
                            row.night_shift_bcms = dateSums[row_date].Night;
                            row.morning_shift_bcms = dateSums[row_date].Morning;
                            row.afternoon_shift_bcms = dateSums[row_date].Afternoon;
                            row.total_daily_bcms = dateSums[row_date].total;
                        } else {
                            console.log("No Hourly Production records found for date " + row_date);
                        }
                    });
                    frm.refresh_field('month_prod_days');

                    // Debug: Sum overall total production from the grouped data.
                    let overall_total = 0;
                    Object.keys(dateSums).forEach(dateKey => {
                        overall_total += dateSums[dateKey].total;
                    });
                    console.log("Overall Total Production from Hourly Production:", overall_total);

                    frappe.msgprint(__('Month-to-Date Production updated successfully. Check the browser console for per-day sums.'));
                }
            }
        });
    }
});

// Section 8: Trigger Sections for Child Table Updates
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
