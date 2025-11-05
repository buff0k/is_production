frappe.ui.form.on('Drill Planning', {
    refresh(frm) {
        // Apply initial filter if Site already selected
        if (frm.doc.site) {
            frm.set_query('monthly_production_plan', function() {
                return {
                    filters: {
                        location: frm.doc.site
                    }
                };
            });
        }
    },

    site(frm) {
        // Dynamically reapply filter when Site changes
        frm.set_query('monthly_production_plan', function() {
            return {
                filters: {
                    location: frm.doc.site
                }
            };
        });

        // Clear the Monthly Plan when Site changes
        frm.set_value('monthly_production_plan', null);
    },

    monthly_production_plan(frm) {
        if (frm.doc.monthly_production_plan) {
            frappe.db.get_value(
                'Monthly Production Planning',
                frm.doc.monthly_production_plan,
                ['prod_month_start_date', 'prod_month_end_date', 'total_month_prod_hours', 'num_prod_days'],
                function(value) {
                    if (value) {
                        // Auto populate Start/End Date from Monthly Production Plan
                        frm.set_value('start_date', value.prod_month_start_date);
                        frm.set_value('end_date', value.prod_month_end_date);

                        // Calculate rates if target already entered
                        if (frm.doc.monthly_target) {
                            if (value.total_month_prod_hours) {
                                frm.set_value('hourly_required_rate',
                                    flt(frm.doc.monthly_target / value.total_month_prod_hours, 1)
                                );
                            }
                            if (value.num_prod_days) {
                                frm.set_value('daily_required_rate',
                                    flt(frm.doc.monthly_target / value.num_prod_days, 1)
                                );
                            }
                        }
                    }
                }
            );
        }
    },

    monthly_target(frm) {
        if (frm.doc.monthly_production_plan && frm.doc.monthly_target) {
            frappe.db.get_value(
                'Monthly Production Planning',
                frm.doc.monthly_production_plan,
                ['total_month_prod_hours', 'num_prod_days'],
                function(value) {
                    if (value) {
                        if (value.total_month_prod_hours) {
                            frm.set_value('hourly_required_rate',
                                flt(frm.doc.monthly_target / value.total_month_prod_hours, 1)
                            );
                        }
                        if (value.num_prod_days) {
                            frm.set_value('daily_required_rate',
                                flt(frm.doc.monthly_target / value.num_prod_days, 1)
                            );
                        }
                    }
                }
            );
        }
    }
});
