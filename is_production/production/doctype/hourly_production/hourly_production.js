// Copyright (c) 2024, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Hourly Production", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on('Hourly Production', {
    location: function(frm) {
        fetch_monthly_production_planning(frm);
    },
    prod_date: function(frm) {
        fetch_monthly_production_planning(frm);
    },
    onload: function(frm) {
        if (!frm.is_new()) {
            frm.set_df_property('shift', 'read_only', true);
            frm.set_df_property('shift_num_hour', 'read_only', true);
        }
    },
    shift: function(frm) {
        if (frm.is_new()) {
            frm.set_df_property('shift_num_hour', 'options', '');
            if (frm.doc.shift === 'A') {
                frm.set_df_property('shift_num_hour', 'options', [
                    'A-1', 'A-2', 'A-3', 'A-4', 'A-5', 'A-6',
                    'A-7', 'A-8', 'A-9', 'A-10', 'A-11', 'A-12'
                ].join('\n'));
            } else if (frm.doc.shift === 'B') {
                frm.set_df_property('shift_num_hour', 'options', [
                    'B-1', 'B-2', 'B-3', 'B-4', 'B-5', 'B-6',
                    'B-7', 'B-8', 'B-9', 'B-10', 'B-11', 'B-12'
                ].join('\n'));
            }
            frm.set_value('shift_num_hour', '');
        }
    },
    shift_num_hour: function(frm) {
        frappe.call({
            method: 'erpnext.hourly_production.utils.get_hour_slot',
            args: {
                shift: frm.doc.shift,
                shift_num_hour: frm.doc.shift_num_hour
            },
            callback: function(r) {
                if (r.message) {
                    frm.set_value('hour_slot', r.message);
                }
            }
        });
    },
    before_save: function(frm) {
        frappe.confirm(
            'Are you sure the shift_num_hour has been selected correctly?',
            function() {
                frappe.validated = true;
            },
            function() {
                frappe.msgprint('Please review and ensure shift_num_hour is correct.');
                frappe.validated = false;
            }
        );
    },
    after_save: function(frm) {
        frm.set_df_property('shift', 'read_only', true);
        frm.set_df_property('shift_num_hour', 'read_only', true);
    }
});

function fetch_monthly_production_planning(frm) {
    if (frm.doc.location && frm.doc.prod_date) {
        frappe.call({
            method: 'erpnext.hourly_production.utils.fetch_monthly_production_plan',
            args: {
                location: frm.doc.location,
                prod_date: frm.doc.prod_date
            },
            callback: function(r) {
                if (r.message) {
                    frm.set_value('month_prod_planning', r.message);
                } else {
                    frappe.msgprint(__('No matching Monthly Production Planning document found'));
                    frm.set_value('month_prod_planning', null);
                }
            }
        });
    } else {
        frappe.msgprint(__('Please set both Location and Production Date.'));
    }
}

