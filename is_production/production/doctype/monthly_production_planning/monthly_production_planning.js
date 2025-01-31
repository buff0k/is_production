// Section 1: Introduction - Monthly Production Planning
frappe.ui.form.on('Monthly Production Planning', {
    refresh: function(frm) {
        console.log("Form Refresh triggered");

        // Disable onboarding tour if enabled
        if (frappe.ui.init_onboarding_tour) {
            frappe.ui.init_onboarding_tour = function() {};
        }

        // Button for populating Monthly Production Days
        frm.add_custom_button(__('Populate Monthly Production Days'), function() {
            frm.trigger('populate_monthly_prod_days');
        }, __('Actions'));

        // Button for clearing Production Days
        frm.add_custom_button(__('Clear Production Days'), function() {
            frm.trigger('clear_production_days');
        }, __('Actions'));

        // Ensure modals handle focus properly
        $(document).on('hidden.bs.modal', function (event) {
            let modal = event.target;
            
            // Ensure `aria-hidden` is properly removed
            requestAnimationFrame(() => {
                modal.removeAttribute("aria-hidden");
                modal.removeAttribute("inert");

                // Move focus to a safe element outside the modal
                let safeElement = document.querySelector(".btn-primary") || document.body;
                safeElement.focus();

                // Force blur on elements inside the modal to prevent retained focus
                modal.querySelectorAll("button, input, a, textarea, select").forEach(el => el.blur());
            });
        });

        $(document).on('shown.bs.modal', function (event) {
            let modal = event.target;
            
            // Ensure accessibility attributes are properly set
            requestAnimationFrame(() => {
                modal.removeAttribute("inert");
                modal.removeAttribute("aria-hidden");

                // Ensure focus is properly set inside the opened modal
                let focusable = modal.querySelector("button, input, a, textarea, select");
                if (focusable) {
                    focusable.focus();
                }
            });
        });
    }
});


// Section 2: Populate Monthly Production Days Function
frappe.ui.form.on('Monthly Production Planning', {
    populate_monthly_prod_days: function(frm) {
        try {
            console.log("populate_monthly_prod_days triggered");

            // Check if start and end dates are selected
            if (!frm.doc.prod_month_start_date || !frm.doc.prod_month_end_date) {
                frappe.msgprint(__('Please select valid production start and end dates.'));
                console.log("Missing start or end date");
                return;
            }

            let start_date = frappe.datetime.str_to_obj(frm.doc.prod_month_start_date);
            let end_date = frappe.datetime.str_to_obj(frm.doc.prod_month_end_date);

            console.log("Start Date:", start_date);
            console.log("End Date:", end_date);

            // If invalid dates are found, show a message
            if (!start_date || !end_date) {
                frappe.msgprint(__('Invalid production start or end date format.'));
                console.log("Invalid start or end date format");
                return;
            }

            // Last day of the month
            let last_day = end_date.getDate();
            frm.clear_table('month_prod_days');
            console.log("Cleared 'month_prod_days' table");

            let total_day_hours = 0;
            let total_night_hours = 0;
            let total_morning_hours = 0;
            let total_afternoon_hours = 0;

            // Loop through each day of the month
            for (let day = start_date.getDate(); day <= last_day; day++) {
                let day_date = new Date(start_date.getFullYear(), start_date.getMonth(), day);
                let day_of_week = day_date.toLocaleDateString('en-US', { weekday: 'long' });

                console.log('Processing Date:', day_date, 'Day of Week:', day_of_week);

                let day_shift_hours = 0, night_shift_hours = 0;
                let morning_shift_hours = 0, afternoon_shift_hours = 0;

                // Check shift system and calculate hours
                if (frm.doc.shift_system === '2x12Hour') {
                    if (day_of_week === 'Saturday') {
                        day_shift_hours = 7;
                        night_shift_hours = 7;
                    } else if (day_of_week === 'Sunday') {
                        day_shift_hours = 0;
                        night_shift_hours = 0;
                    } else {
                        day_shift_hours = 9;
                        night_shift_hours = 9;
                    }
                } else if (frm.doc.shift_system === '3x8Hour') {
                    if (day_of_week === 'Saturday') {
                        morning_shift_hours = 5;
                        afternoon_shift_hours = 5;
                        night_shift_hours = 5;
                    } else if (day_of_week === 'Sunday') {
                        morning_shift_hours = 0;
                        afternoon_shift_hours = 0;
                        night_shift_hours = 0;
                    } else {
                        morning_shift_hours = 6;
                        afternoon_shift_hours = 6;
                        night_shift_hours = 6;
                    }
                }

                total_day_hours += day_shift_hours;
                total_night_hours += night_shift_hours;
                total_morning_hours += morning_shift_hours;
                total_afternoon_hours += afternoon_shift_hours;

                // Add data to the 'month_prod_days' child table
                let row = frm.add_child('month_prod_days');
                row.shift_start_date = frappe.datetime.obj_to_str(day_date);
                row.day_week = day_of_week;
                row.shift_day_hours = day_shift_hours;
                row.shift_night_hours = night_shift_hours;
                row.shift_morning_hours = morning_shift_hours;
                row.shift_afternoon_hours = afternoon_shift_hours;
            }

            // Update total hours and refresh fields
            frm.set_value('tot_shift_day_hours', total_day_hours);
            frm.set_value('tot_shift_night_hours', total_night_hours);
            frm.set_value('tot_shift_morning_hours', total_morning_hours);
            frm.set_value('tot_shift_afternoon_hours', total_afternoon_hours);
            frm.set_value('total_month_prod_hours', total_day_hours + total_night_hours + total_morning_hours + total_afternoon_hours);

            // Recalculate totals and refresh the child table
            frm.trigger('recalculate_totals');
            frm.refresh_field('month_prod_days');
            frappe.msgprint(__('Monthly Production Days table has been populated.'));
        } catch (error) {
            console.error('Error in populate_monthly_prod_days:', error);
            frappe.msgprint(__('An error occurred: ' + error.message));
        }
    }
});

// Section 3: Location Function
frappe.ui.form.on('Monthly Production Planning', {
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
    }
});

// Section 4: Clear Production Days Function
frappe.ui.form.on('Monthly Production Planning', {
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
    }
});

// Section 5: Calculate Production Month End
frappe.ui.form.on('Monthly Production Planning', {
    prod_month_end_date: function(frm) {
        let selected_date = frm.doc.prod_month_end_date;
        if (selected_date) {
            let date_obj = new Date(selected_date);
            let last_day_of_month = new Date(date_obj.getFullYear(), date_obj.getMonth() + 1, 0);

            frm.set_value('prod_month_end', frappe.datetime.obj_to_str(last_day_of_month));
            frappe.msgprint(__('Production month end has been set to the last day of the month.'));
        }
    }
});

// Section 6: Monthly Target BCM & Recalculate Totals Functions
frappe.ui.form.on('Monthly Production Planning', {
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
    }
});

// Section 7: Update Month-to-Date (MTD) Production Function
frappe.ui.form.on('Monthly Production Planning', {
    update_mtd_production: function(frm) {
        if (!frm.doc.name) {
            frappe.msgprint(__('Please save the document first.'));
            return;
        }

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

                    // Process Hourly Production data
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

                    // Calculate total_daily_bcms for each row
                    frm.doc.month_prod_days.forEach(row => {
                        row.total_daily_bcms =
                            (row.day_shift_bcms || 0) +
                            (row.night_shift_bcms || 0) +
                            (row.morning_shift_bcms || 0) +
                            (row.afternoon_shift_bcms || 0);
                    });

                    frappe.msgprint(__('Month-to-Date Production updated successfully.'));
                } else {
                    frappe.msgprint(__('No Hourly Production data found for this Monthly Production Planning document.'));
                }
            }
        });
    }
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
