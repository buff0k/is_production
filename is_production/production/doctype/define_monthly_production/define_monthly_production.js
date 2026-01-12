frappe.ui.form.on('Define Monthly Production', {
    setup(frm) {
        // Filter Monthly Production Planning by Location (Site)
        frm.set_query('monthly_production_plan', 'define_site_production', function (frm, cdt, cdn) {
            let row = locals[cdt][cdn];

            if (!row.site) {
                return {};
            }

            return {
                filters: {
                    location: row.site   // ✅ CORRECT FIELDNAME
                }
            };
        });
    }
});

frappe.ui.form.on('MPP Child', {

    site(frm, cdt, cdn) {
        // Reset dependent fields when site changes
        frappe.model.set_value(cdt, cdn, 'monthly_production_plan', null);
        frappe.model.set_value(cdt, cdn, 'start_date', null);
        frappe.model.set_value(cdt, cdn, 'end_date', null);
    },

    monthly_production_plan(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (!row.monthly_production_plan) return;

        frappe.call({
            method: 'is_production.production.doctype.define_monthly_production.define_monthly_production.get_plan_dates',
            args: {
                plan_name: row.monthly_production_plan
            },
            callback: function (r) {
                if (r.message) {
                    frappe.model.set_value(cdt, cdn, 'start_date', r.message.start_date);
                    frappe.model.set_value(cdt, cdn, 'end_date', r.message.end_date);
                }
            }
        });
    }
});
