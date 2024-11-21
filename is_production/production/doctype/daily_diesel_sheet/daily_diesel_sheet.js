frappe.ui.form.on('Daily Diesel Sheet', {
    onload: function(frm) {
        // Filter 'asset_name' in the main form based on 'location' and 'asset_category'
        frm.set_query('asset_name', function() {
            return {
                filters: {
                    'location': frm.doc.location,
                    'asset_category': 'Diesel Bowsers'
                }
            };
        });

        // Filter 'asset_name' in the daily_diesel_entries table based on 'location'
        frm.fields_dict['daily_diesel_entries'].grid.get_field('asset_name').get_query = function(doc) {
            return {
                filters: {
                    'location': frm.doc.location
                }
            };
        };
    },

    refresh: function(frm) {
        // Re-apply the filter for 'asset_name' in the main form on refresh
        frm.set_query('asset_name', function() {
            return {
                filters: {
                    'location': frm.doc.location,
                    'asset_category': 'Diesel Bowsers'
                }
            };
        });

        frm.refresh_field('daily_diesel_entries');
    },

    validate: function(frm) {
        let is_valid = true;

        // Validate that an attachment is present in the daily_diesel_sheet_attachment field
        if (!frm.doc.daily_diesel_sheet_attachment) {
            frappe.msgprint(__('Please attach the Daily Diesel Sheet before submitting.'));
            is_valid = false;
        }

        if (!is_valid) {
            frappe.validated = false; // Prevent form submission if validation fails
        }
    }
});

// Handling changes within the Daily Diesel Entries table
frappe.ui.form.on('Daily Diesel Entries', {
    close_reading: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        // Validate that close_reading is not less than open_reading
        if (row.close_reading < row.open_reading) {
            frappe.msgprint(__('Close Reading cannot be less than Open Reading.'));
            frappe.validated = false;
        } else {
            // Calculate 'litres_issued' when 'close_reading' is updated
            if (row.open_reading && row.close_reading) {
                row.litres_issued = row.close_reading - row.open_reading;
                frm.refresh_field('daily_diesel_entries'); // Refresh the table to display updated values
            }

            // Set open_reading of all subsequent rows and make open_reading read-only from row 2 onward
            calculate_and_lock_open_reading(frm);

            // Trigger recalculation of total litres_issued_equipment
            calculate_total_litres_issued_equipment(frm);
        }
    },

    open_reading: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        // Validate that close_reading is not less than open_reading
        if (row.close_reading < row.open_reading) {
            frappe.msgprint(__('Close Reading cannot be less than Open Reading.'));
            frappe.validated = false;
        } else {
            // Calculate 'litres_issued' when 'open_reading' is updated
            if (row.open_reading && row.close_reading) {
                row.litres_issued = row.close_reading - row.open_reading;
                frm.refresh_field('daily_diesel_entries'); // Refresh the table to display updated values
            }

            // Set open_reading of all subsequent rows and make open_reading read-only from row 2 onward
            calculate_and_lock_open_reading(frm);

            // Trigger recalculation of total litres_issued_equipment
            calculate_total_litres_issued_equipment(frm);
        }
    },

    daily_diesel_entries_add: function(frm, cdt, cdn) {
        // Recalculate total litres_issued_equipment when a new row is added
        calculate_total_litres_issued_equipment(frm);

        // Calculate open_reading for the new row
        calculate_and_lock_open_reading(frm);
    },

    daily_diesel_entries_remove: function(frm, cdt, cdn) {
        // Recalculate total litres_issued_equipment when a row is removed
        calculate_total_litres_issued_equipment(frm);
    }
});

// Update open_reading for all rows after the first and make them read-only
function calculate_and_lock_open_reading(frm) {
    frm.doc.daily_diesel_entries.forEach(function(row, idx) {
        // For row 2 and onward
        if (idx > 0) {
            let previous_row = frm.doc.daily_diesel_entries[idx - 1];
            if (previous_row.close_reading) {
                row.open_reading = previous_row.close_reading;
                frm.fields_dict['daily_diesel_entries'].grid.grid_rows[idx].toggle_editable("open_reading", false);
            }
        }
    });
    frm.refresh_field('daily_diesel_entries');
}

// Helper function to calculate and update total litres_issued_equipment
function calculate_total_litres_issued_equipment(frm) {
    let total_litres_issued = 0;
    frm.doc.daily_diesel_entries.forEach(function(row) {
        total_litres_issued += row.litres_issued || 0;
    });
    frm.set_value('litres_issued_equipment', total_litres_issued);
    frm.refresh_field('litres_issued_equipment');
}
