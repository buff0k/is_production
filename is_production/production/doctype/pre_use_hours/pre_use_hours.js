frappe.ui.form.on('Pre-Use Hours', {
    shift_system: function (frm) {
        update_shift_options(frm, frm.doc.shift_system);
    },
    location: function (frm) {
        if (frm.doc.location) {
            // Clear any existing assets in the child table
            frm.clear_table('pre_use_assets');
            fetch_assets(frm);

            // Trigger shift system fetch if shift_date is populated
            if (frm.doc.shift_date) {
                fetch_shift_system(frm);
            }

            set_avail_util_lookup(frm);
        }
    },
    shift_date: function (frm) {
        if (frm.doc.location) {
            fetch_shift_system(frm);
        }
        set_avail_util_lookup(frm);
    },
    shift: function (frm) {
        set_avail_util_lookup(frm);
    },
    refresh: function (frm) {
        fetch_pre_use_status(frm);
    }
});

/**
 * Dynamically set Shift options based on the shift system
 */
function update_shift_options(frm, shift_system) {
    const shift_options = {
        '3x8Hour': ['Morning', 'Afternoon', 'Night'],
        '2x12Hour': ['Day', 'Night']
    };
    frm.set_df_property('shift', 'options', shift_options[shift_system] || []);
}

/**
 * Fetch relevant assets (Excavator, ADT, Dozer) for the selected location
 */
function fetch_assets(frm) {
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Asset',
            filters: {
                location: frm.doc.location,
                asset_category: ['in', ['Excavator', 'ADT', 'Dozer']],
                status: 'Submitted'
            },
            fields: ['name', 'asset_name', 'item_name', 'asset_category'],
            limit_page_length: 1000
        },
        callback: function (response) {
            if (response.message) {
                response.message.forEach(asset => {
                    const row = frm.add_child('pre_use_assets');
                    row.asset_name = asset.asset_name;
                    row.item_name = asset.item_name;
                    row.asset_category = asset.asset_category;
                });
                frm.refresh_field('pre_use_assets');
            }
        }
    });
}

/**
 * Fetch the shift system from Monthly Production Planning, ensuring
 * shift_date is within prod_month_start_date and prod_month_end_date
 */
function fetch_shift_system(frm) {
    if (!frm.doc.location || !frm.doc.shift_date) return;

    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Monthly Production Planning',
            filters: {
                location: frm.doc.location,
                // New logic: shift_date must be between (inclusive) prod_month_start_date & prod_month_end_date
                prod_month_start_date: ["<=", frm.doc.shift_date],
                prod_month_end_date: [">=", frm.doc.shift_date],
                site_status: "Producing"
            },
            fields: ['name', 'prod_month_start_date', 'prod_month_end_date', 'shift_system'],
            limit_page_length: 1
        },
        callback: function (response) {
            if (response.message && response.message.length) {
                const record = response.message[0];
                
                // Optional extra check on client side:
                const shift_date_obj = frappe.datetime.str_to_obj(frm.doc.shift_date);
                const month_start_obj = frappe.datetime.str_to_obj(record.prod_month_start_date);
                const month_end_obj = frappe.datetime.str_to_obj(record.prod_month_end_date);

                if (shift_date_obj < month_start_obj || shift_date_obj > month_end_obj) {
                    frappe.throw(
                        __("Shift Date must be between {0} and {1} (inclusive).", [
                            frappe.datetime.obj_to_user(month_start_obj),
                            frappe.datetime.obj_to_user(month_end_obj)
                        ])
                    );
                }

                // Set the shift_system field and update the shift options
                frm.set_value('shift_system', record.shift_system);
                update_shift_options(frm, record.shift_system);
            } else {
                // If no record is found, you can optionally show a message
                // e.g. frappe.msgprint("No valid Monthly Production Planning found for this date.");
            }
        }
    });
}

/**
 * Build a combined field for "Availability and Utilisation Lookup"
 */
function set_avail_util_lookup(frm) {
    if (frm.doc.location && frm.doc.shift_date && frm.doc.shift) {
        const shift_date_formatted = frappe.datetime.str_to_user(frm.doc.shift_date);
        const avail_util_lookup_value = `${frm.doc.location}-${shift_date_formatted}-${frm.doc.shift}`;
        frm.set_value('avail_util_lookup', avail_util_lookup_value);
    }
}

/**
 * Fetch and display a table of Pre-Use Status records in the 'pre_use_status_explain' HTML field
 */
function fetch_pre_use_status(frm) {
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Pre-Use Status',
            fields: ['name', 'pre_use_avail_status'],
            order_by: 'name asc'
        },
        callback: function (response) {
            const records = response.message;
            let html = records && records.length
                ? generate_status_table(records)
                : "<p>No records found in 'Pre-Use Status'.</p>";

            // Add extra instruction text at the bottom
            html += "<br><b>Please ensure correct status is indicated for each Plant. "
                 + "For example, if Plant is not working at shift start due to Breakdown, "
                 + "status of 2 must be selected. Or if machine is spare, select status 3.</b>";

            $(frm.fields_dict.pre_use_status_explain.wrapper).html(html);
        }
    });
}

/**
 * Generate an HTML table with status records
 */
function generate_status_table(records) {
    let html = "<table style='width:100%; border-collapse: collapse;'>";
    html += "<tr><th>Status</th><th>Pre-Use Availability Status</th></tr>";
    records.forEach(record => {
        html += `<tr><td>${record.name}</td><td>${record.pre_use_avail_status}</td></tr>`;
    });
    html += "</table>";
    return html;
}
