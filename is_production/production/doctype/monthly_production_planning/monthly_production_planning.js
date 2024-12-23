frappe.ui.form.on('Monthly Production Planning', {
    refresh: function(frm) {
        frm.add_custom_button(__('Populate Monthly Production Days'), function() {
            frm.trigger('populate_monthly_prod_days');
        }, __('Actions'));

        frm.add_custom_button(__('Clear Production Days'), function() {
            frm.trigger('clear_production_days');
        }, __('Actions'));
    },

    populate_monthly_prod_days: function(frm) {
        try {
            if (!frm.doc.prod_month_end) {
                frappe.msgprint(__('Please select a valid production month end date.'));
                return;
            }

            let end_date = frappe.datetime.str_to_obj(frm.doc.prod_month_end);
            if (!end_date) {
                frappe.msgprint(__('Invalid production month end date format.'));
                return;
            }

            let start_date = new Date(end_date.getFullYear(), end_date.getMonth(), 1);
            let last_day = new Date(end_date.getFullYear(), end_date.getMonth() + 1, 0).getDate();

            frm.clear_table('month_prod_days');
            console.log('Start Date:', start_date, 'Last Day:', last_day);

            let total_day_hours = 0;
            let total_night_hours = 0;
            let total_morning_hours = 0;
            let total_afternoon_hours = 0;

            for (let day = 1; day <= last_day; day++) {
                let day_date = new Date(start_date.getFullYear(), start_date.getMonth(), day);
                let day_of_week = day_date.toLocaleDateString('en-US', { weekday: 'long' });

                console.log('Processing Date:', day_date, 'Day of Week:', day_of_week);

                let day_shift_hours = 0, night_shift_hours = 0;
                let morning_shift_hours = 0, afternoon_shift_hours = 0;

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

                let row = frm.add_child('month_prod_days');
                row.shift_start_date = frappe.datetime.obj_to_str(day_date);
                row.day_week = day_of_week;
                row.shift_day_hours = day_shift_hours;
                row.shift_night_hours = night_shift_hours;
                row.shift_morning_hours = morning_shift_hours;
                row.shift_afternoon_hours = afternoon_shift_hours;
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

    location: function (frm) {
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
                callback: function (r) {
                    if (r && r.message) {
                        r.message.forEach(function (asset) {
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
                callback: function (r) {
                    if (r && r.message) {
                        r.message.forEach(function (asset) {
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
                callback: function (r) {
                    if (r && r.message) {
                        r.message.forEach(function (asset) {
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

    prod_month_end: function(frm) {
        let selected_date = frm.doc.prod_month_end;
        if (selected_date) {
            let date_obj = new Date(selected_date);
            let last_day_of_month = new Date(date_obj.getFullYear(), date_obj.getMonth() + 1, 0);

            if (date_obj.getDate() !== last_day_of_month.getDate()) {
                frm.set_value('prod_month_end', frappe.datetime.obj_to_str(last_day_of_month));
                frappe.msgprint(__('The selected date has been corrected to the last day of the month.'));
            }
        }
    },

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

                    // Additional calculations
                    let month_actual_bcm = frm.doc.month_prod_days.reduce((total, row) => total + (row.total_daily_bcms || 0), 0);
                    let prod_days_completed = 0;
                    let month_prod_hours_completed = 0;
                    let today = frappe.datetime.get_today();

                    frm.doc.month_prod_days.forEach(row => {
                        if (row.shift_start_date < today) {
                            let daily_hours = (row.shift_day_hours || 0) + (row.shift_night_hours || 0) +
                                (row.shift_morning_hours || 0) + (row.shift_afternoon_hours || 0);
                            
                            if (daily_hours > 0) {
                                prod_days_completed++;
                                month_prod_hours_completed += daily_hours;
                            }
                        }
                    });

                    let mtd_bcm_day = prod_days_completed > 0 ? month_actual_bcm / prod_days_completed : 0;
                    let mtd_bcm_hour = month_prod_hours_completed > 0 ? month_actual_bcm / month_prod_hours_completed : 0;
                    let month_remaining_prod_hours = frm.doc.total_month_prod_hours - month_prod_hours_completed;
                    let month_remaining_production_days = frm.doc.num_prod_days - prod_days_completed;
                    let month_forecated_bcm = mtd_bcm_hour * frm.doc.total_month_prod_hours;

                    frm.set_value('month_actual_bcm', month_actual_bcm);
                    frm.set_value('prod_days_completed', prod_days_completed);
                    frm.set_value('month_prod_hours_completed', month_prod_hours_completed);
                    frm.set_value('mtd_bcm_day', mtd_bcm_day);
                    frm.set_value('mtd_bcm_hour', mtd_bcm_hour);
                    frm.set_value('month_remaining_prod_hours', month_remaining_prod_hours);
                    frm.set_value('month_remaining_production_days', month_remaining_production_days);
                    frm.set_value('month_forecated_bcm', month_forecated_bcm);

                    frm.refresh_fields([
                        'month_actual_bcm', 'prod_days_completed', 'month_prod_hours_completed',
                        'mtd_bcm_day', 'mtd_bcm_hour', 'month_remaining_prod_hours',
                        'month_remaining_production_days', 'month_forecated_bcm'
                    ]);

                    frappe.msgprint(__('Month-to-Date Production updated successfully.'));
                } else {
                    frappe.msgprint(__('No Hourly Production data found for this Monthly Production Planning document.'));
                }
            }
        });
    }
});

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
