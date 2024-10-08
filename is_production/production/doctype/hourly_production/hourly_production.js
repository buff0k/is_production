// Copyright (c) 2024, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on('Hourly Production', {
    location: function(frm) {
        if (frm.doc.location) {
            // Fetch the latest submitted Monthly Target Info
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Monthly Target Info',
                    filters: {
                        location: frm.doc.location,
                        docstatus: 1 // Submitted
                    },
                    fields: ['name', 'creation'],
                    order_by: 'creation desc',
                    limit: 1
                },
                callback: function(r) {
                    if (r.message && r.message.length > 0) {
                        frm.set_value('linked_monthly_target', r.message[0].name);
                    } else {
                        frm.set_value('linked_monthly_target', null);
                        frappe.msgprint(__('No submitted Monthly Target Info found for the selected location.'));
                    }
                }
            });

            // Fetch asset names when location is selected
            fetch_asset_names(frm);
        }
    },
    
    refresh: function(frm) {
        // Fetch asset names and set options for asset_name field on form refresh
        if (frm.doc.location) {
            fetch_asset_names(frm, true); // Pass true to retain asset_name after refresh
        }

        // Make endtime read-only and set properties for other fields
        frm.set_df_property('endtime', 'read_only', 1);  // Ensure endtime is read-only
        if (!frm.is_new()) {
            frm.set_df_property('starttime', 'read_only', 1);  // Make starttime read-only
            frm.set_df_property('asset_name', 'read_only', 1);  // Make asset_name read-only
            frm.set_df_property('location', 'read_only', 1);    // Make location read-only
        }
        frm.set_df_property('starttime', 'description', 'Time will be set to the top of the hour');
        frm.refresh_field('endtime');
        frm.refresh_field('starttime');
        frm.refresh_field('asset_name');
        frm.refresh_field('location');
    },

    starttime: function(frm) {
        // Adjust starttime to the top of the hour and set endtime to +1 hour
        if (frm.doc.starttime) {
            let start_time = new Date(frm.doc.starttime);
            if (start_time.getMinutes() !== 0 || start_time.getSeconds() !== 0) {
                start_time.setMinutes(0, 0, 0); // Round to the nearest hour
                frm.set_value('starttime', frappe.datetime.get_datetime_as_string(start_time));
                frappe.msgprint('Start Time has been adjusted to the top of the hour.');
            }
            start_time.setHours(start_time.getHours() + 1); // Set endtime to +1 hour
            frm.set_value('endtime', frappe.datetime.get_datetime_as_string(start_time));
        }
    },

    before_save: function(frm) {
        // Ask for confirmation before saving new records
        if (frm.is_new() && frm.doc.starttime && frm.doc.asset_name && frm.doc.location && !frm.confirmation_given) {
            frappe.validated = false;  // Stop save temporarily
            let confirmation_message = `Is the Start Time ${frappe.datetime.str_to_user(frm.doc.starttime)}, Plant No ${frm.doc.asset_name}, and Site ${frm.doc.location} correct?`;
            frappe.confirm(
                confirmation_message,
                function() {
                    // Allow save if confirmed
                    frm.confirmation_given = true;
                    frappe.validated = true;
                    frm.save_or_update();
                },
                function() {
                    // Cancel save if not confirmed
                    frappe.msgprint('Please correct the Start Time, Plant No, or Site before saving.');
                    frappe.validated = false;
                }
            );
        }
    }
});

function fetch_asset_names(frm, retain_asset_name = false) {
    if (frm.doc.location) {
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Asset',
                filters: {
                    location: frm.doc.location,  // Matching location field
                    asset_category: 'Excavator'  // Filter by asset_category
                },
                fields: ['name', 'asset_name']  // Fetch asset_name and name
            },
            callback: function(r) {
                if (r.message) {
                    let asset_names = r.message.map(asset => asset.asset_name);
                    console.log('Fetched Asset Names (Excavator): ', asset_names);
                    let options = asset_names.join('\n');
                    frm.set_df_property('asset_name', 'options', options);
                    if (retain_asset_name && frm.doc.asset_name) {
                        frm.set_value('asset_name', frm.doc.asset_name);
                    }
                    frm.refresh_field('asset_name');
                } else {
                    console.log('No assets found for the selected location and category.');
                    frm.set_df_property('asset_name', 'options', []);
                    frm.refresh_field('asset_name');
                }
            }
        });
    }
}