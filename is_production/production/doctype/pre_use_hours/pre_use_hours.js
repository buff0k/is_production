frappe.ui.form.on('Pre-Use Hours', {
    location: function(frm) {
        console.log("Location changed, clearing pre_use_assets table.");
        frm.clear_table('pre_use_assets');

        if (frm.doc.location) {
            console.log("Fetching assets for location with status 'Submitted':", frm.doc.location);
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Asset',
                    filters: {
                        location: frm.doc.location,
                        asset_category: ['!=', 'LDV'],
                        status: 'Submitted'
                    },
                    fields: ['name', 'asset_name', 'item_name', 'asset_category']
                },
                callback: function(response) {
                    console.log("Assets fetched with status 'Submitted':", response.message);
                    const assets = response.message;

                    if (assets && assets.length > 0) {
                        assets.forEach(asset => {
                            const row = frm.add_child('pre_use_assets');
                            row.asset_name = asset.asset_name;
                            row.item_name = asset.item_name;
                            row.asset_category = asset.asset_category;
                            row.pre_use_avail_status = '1';
                        });
                    } else {
                        frm.clear_table('pre_use_assets');
                    }

                    frm.refresh_field('pre_use_assets');
                    disable_row_editing(frm);
                }
            });
        }

        // Trigger shift system fetch if shift_date is populated
        if (frm.doc.shift_date) {
            fetch_shift_system(frm);
        }
    },
    shift_date: function(frm) {
        // Trigger shift system fetch if location is populated
        if (frm.doc.location) {
            fetch_shift_system(frm);
        }
    },
    refresh: function(frm) {
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Pre-Use Status',
                fields: ['*'],
                order_by: 'name asc'  // Sort by 'name' field in ascending order
            },
            callback: function(response) {
                const records = response.message;
                let html = "<table style='width:100%; border-collapse: collapse;'>";

                if (records && records.length > 0) {
                    const excludedFields = ["owner", "creation", "modified", "modified_by", "docstatus", "idx"];
                    html += "<tr>";
                    Object.keys(records[0]).forEach(field => {
                        if (!excludedFields.includes(field.toLowerCase())) {
                            const fieldName = field.toLowerCase() === "name" ? "Status" : field.charAt(0).toUpperCase() + field.slice(1);
                            html += `<th style="border: 1px solid #000; padding: 5px;">${fieldName}</th>`;
                        }
                    });
                    html += "</tr>";

                    records.forEach(record => {
                        html += "<tr>";
                        Object.keys(record).forEach(field => {
                            if (!excludedFields.includes(field.toLowerCase())) {
                                html += `<td style="border: 1px solid #000; padding: 5px;">${record[field]}</td>`;
                            }
                        });
                        html += "</tr>";
                    });

                    html += "</table>";
                    html += "<br><b>For all records below with a 2 or 3 status the Engine Hours do not have to be captured.</b>";

                    console.log("Generated HTML for pre_use_status_explain:", html);
                    $(frm.fields_dict.pre_use_status_explain.wrapper).html(html);
                } else {
                    const no_records_html = "<p>No records found in 'Pre-Use Status'.</p>";
                    console.log("Generated HTML for pre_use_status_explain (no records):", no_records_html);
                    $(frm.fields_dict.pre_use_status_explain.wrapper).html(no_records_html);
                }
            }
        });
    }
});

// Function to fetch shift system based on location and shift_date within the same month
function fetch_shift_system(frm) {
    console.log("Fetching shift_system based on location and shift_date.");

    const shiftDate = frappe.datetime.str_to_obj(frm.doc.shift_date);
    const startOfMonth = frappe.datetime.get_first_day(shiftDate);
    const endOfMonth = frappe.datetime.get_last_day(shiftDate);

    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Monthly Production Planning',
            filters: [
                ['location', '=', frm.doc.location],
                ['prod_month_end', '>=', startOfMonth],
                ['prod_month_end', '<=', endOfMonth]
            ],
            fields: ['shift_system', 'prod_month_end'],
            order_by: 'prod_month_end asc',
            limit: 1
        },
        callback: function(response) {
            const planningDoc = response.message && response.message[0];
            if (planningDoc) {
                frm.set_value('shift_system', planningDoc.shift_system);
                console.log("Shift system fetched:", planningDoc.shift_system);

                // Set shift options based on the shift_system
                if (planningDoc.shift_system === "2x12Hour") {
                    frm.fields_dict.shift.df.options = ['A', 'B'].join('\n');
                } else if (planningDoc.shift_system === "3x8Hour") {
                    frm.fields_dict.shift.df.options = ['A', 'B', 'C'].join('\n');
                }
                frm.refresh_field('shift');
            } else {
                console.log("No matching Monthly Production Planning document found for the same month.");
            }
        }
    });
}
