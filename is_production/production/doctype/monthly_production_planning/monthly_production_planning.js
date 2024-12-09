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
        if (frm.doc.prod_month_end) {
            let end_date = frappe.datetime.str_to_obj(frm.doc.prod_month_end);
            let start_date = new Date(end_date.getFullYear(), end_date.getMonth(), 1);
            let last_day = new Date(end_date.getFullYear(), end_date.getMonth() + 1, 0).getDate();

            frm.clear_table('month_prod_days');

            let total_day_hours = 0;
            let total_night_hours = 0;
            let total_morning_hours = 0;
            let total_afternoon_hours = 0;

            for (let day = 1; day <= last_day; day++) {
                let day_date = new Date(start_date.getFullYear(), start_date.getMonth(), day);
                let day_of_week = day_date.toLocaleDateString('en-US', { weekday: 'long' });

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
        } else {
            frappe.msgprint(__('Please select a valid production month end date.'));
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
        // Trigger recalculation when monthly_target_bcm is updated
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

        // Calculate target values
        if (frm.doc.monthly_target_bcm) {
            frm.set_value('target_bcm_day', frm.doc.monthly_target_bcm / num_prod_days);
            frm.set_value('target_bcm_hour', frm.doc.monthly_target_bcm / total_month_prod_hours);
        } else {
            frm.set_value('target_bcm_day', 0);
            frm.set_value('target_bcm_hour', 0);
        }
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
