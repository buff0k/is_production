// Copyright (c) 2024, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on('Pre-Use Hours', {
    location: function(frm) {
        // Clear the existing rows
        frm.clear_table('pre_use_assets');

        if (frm.doc.location) {
            frappe.call({
                // Update to match the exact path of your Python file
                method: 'is_production.production.doctype.pre_use_hours.pre_use_hours.get_assets_by_location',
                args: {
                    location: frm.doc.location
                },
                callback: function(response) {
                    const assets = response.message;
                    
                    if (assets && assets.length > 0) {
                        assets.forEach(asset => {
                            const row = frm.add_child('pre_use_assets');
                            row.asset_name = asset.asset_name;
                            row.item_name = asset.item_name;
                        });
                        frm.refresh_field('pre_use_assets');
                        frappe.msgprint(__('Assets have been populated based on location.'));
                    } else {
                        frappe.msgprint(__('No assets found for the selected location.'));
                    }
                    
                    // Disable add and delete functionality for the table
                    frm.fields_dict['pre_use_assets'].grid.cannot_add_rows = true;
                    frm.fields_dict['pre_use_assets'].grid.wrapper.find('.grid-remove-row').hide();

                    // Disable row selection or deletion
                    frm.fields_dict['pre_use_assets'].grid.wrapper.on('click', '.grid-row', function(e) {
                        e.stopPropagation();
                    });

                    frm.refresh_field('pre_use_assets');
                }
            });
        }
    }
});

frappe.ui.form.on('Pre-use Assets', {
    eng_hrs_stop: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        
        if (row.eng_hrs_start && row.eng_hrs_stop) {
            // Calculate Hours_run
            row.hours_run = row.eng_hrs_stop - row.eng_hrs_start;
            frm.refresh_field('pre_use_assets');

            // Validate Hours_run to ensure it is not less than 0
            if (row.hours_run < 0) {
                frappe.msgprint({
                    title: __('Invalid Entry'),
                    indicator: 'red',
                    message: __('Hours Run cannot be less than 0. Please check the Start and Stop values.')
                });
                row.hours_run = 0; // Reset Hours_run to 0 or any default value
                frm.refresh_field('pre_use_assets');
            }
        }
    }
});
