frappe.ui.form.on('MPP Child', {

    site(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (!row.site) return;

        // Clear previously selected plan if site changes
        row.monthly_production_plan = null;
        frm.refresh_field("define");
    },

    monthly_production_plan(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (!row.monthly_production_plan) return;

        frappe.call({
            doc: frm.doc,
            method: "get_plan_dates",
            args: {
                plan: row.monthly_production_plan
            },
            callback(r) {
                if (r.message) {
                    row.start_date = r.message.start_date;
                    row.end_date = r.message.end_date;
                    frm.refresh_field("define");
                }
            }
        });
    }
});

// 🔑 THIS IS THE IMPORTANT PART
frappe.ui.form.on('Define Monthly Production', {
    onload(frm) {
        frm.fields_dict.define.grid.get_field(
            "monthly_production_plan"
        ).get_query = function (doc, cdt, cdn) {
            let row = locals[cdt][cdn];
            return {
                filters: {
                    location: row.site
                }
            };
        };
    }
});
