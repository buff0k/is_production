// Copyright (c) 2024, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on('Diesel Receipt', {
    location: function(frm) {
        // Apply the link filter for the asset_name field based on the selected location
        frm.set_query('asset_name', function() {
            return {
                filters: {
                    'asset_category': 'Diesel Bowsers',
                    'location': frm.doc.location
                }
            };
        });
    },
    close_reading_ltrs: function(frm) {
        // Calculate litres_dispensed when both close_reading_ltrs and open_reading_ltrs are filled
        if (frm.doc.close_reading_ltrs && frm.doc.open_reading_ltrs) {
            frm.set_value('litres_dispensed', frm.doc.close_reading_ltrs - frm.doc.open_reading_ltrs);
        }
    },
    open_reading_ltrs: function(frm) {
        // Calculate litres_dispensed when both close_reading_ltrs and open_reading_ltrs are filled
        if (frm.doc.close_reading_ltrs && frm.doc.open_reading_ltrs) {
            frm.set_value('litres_dispensed', frm.doc.close_reading_ltrs - frm.doc.open_reading_ltrs);
        }
    },
    validate: function(frm) {
        // Only show the confirmation message for new documents (draft state)
        if (frm.is_new() && !frm.confirmed) {
            frappe.confirm(
                'Are you sure this diesel receipt information is correct and that a signed-off diesel receipt slip was attached?',
                function() {
                    frm.confirmed = true; // Mark as confirmed to avoid repeat confirmations
                    frm.save(); // Proceed with saving after user confirms
                },
                function() {
                    frappe.msgprint('Please review the diesel receipt information before saving.');
                    frm.confirmed = false; // Reset confirmation flag if not confirmed
                }
            );
            return false; // Prevent save until confirmation is handled
        }
        frm.confirmed = false;  // Reset the flag after confirmation
    }
});

