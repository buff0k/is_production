frappe.ui.form.on('Pre-Use Hours', {
    location: function(frm) {
        if (frm.doc.location) {
            // Clear the pre_use_assets table
            frm.clear_table('pre_use_assets');

            // Fetch assets for the selected location
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Asset',
                    filters: {
                        location: frm.doc.location,
                        asset_category: ["in", ["Excavator", "ADT", "Dozer"]],
                        status: 'Submitted'
                    },
                    fields: ['name', 'asset_name', 'item_name', 'asset_category']
                },
                callback: function(response) {
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

            // Fetch the last created Pre-Use Hours document for the location before the current document's creation
            if (frm.doc.creation) {
                frappe.call({
                    method: 'is_production.production.doctype.pre_use_hours.pre_use_hours.get_previous_document',
                    args: {
                        location: frm.doc.location,
                        current_creation: frm.doc.creation
                    },
                    callback: function(response) {
                        if (response.message) {
                            const previous_doc = response.message;

                            frm.doc.pre_use_assets.forEach(asset => {
                                const matching_asset = previous_doc.pre_use_assets.find(
                                    prev_asset => prev_asset.asset_name === asset.asset_name
                                );
                                if (matching_asset) {
                                    asset.eng_hrs_start = matching_asset.eng_hrs_end;
                                }
                            });

                            frm.refresh_field('pre_use_assets');
                            disable_row_editing(frm);
                        }
                    }
                });
            }
        }
    
        // Trigger shift system fetch if shift_date is populated
        if (frm.doc.shift_date) {
            fetch_shift_system(frm);
        }

        // Set avail_util_lookup if all fields are filled
        set_avail_util_lookup(frm);
    },

    onsave: function(frm) {
        // Update the previous document's closing hours (eng_hrs_end) on save
        frappe.call({
            method: 'is_production.production.doctype.pre_use_hours.pre_use_hours.update_previous_document_eng_hrs',
            args: {
                        location: frm.doc.location,
                        current_creation: frm.doc.creation
                    },
            callback: function(response) {
                        if (response.message) {
                            const previous_doc = response.message;

                            frm.doc.pre_use_assets.forEach(asset => {
                                const matching_asset = previous_doc.pre_use_assets.find(
                                    prev_asset => prev_asset.asset_name === asset.asset_name
                                );
                                if (matching_asset) {
                                    asset.eng_hrs_start = matching_asset.eng_hrs_end;
                                }
                            });
                        }
                    }
        });
    },

    shift_date: function(frm) {
        if (frm.doc.location) {
            fetch_shift_system(frm);
        }
        set_avail_util_lookup(frm);
    },
    shift: function(frm) {
        set_avail_util_lookup(frm);
    },
    refresh: function(frm) {
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Pre-Use Status',
                fields: ['*'],
                order_by: 'name asc'
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
                    html += "<br><b>For all records below with a 2 or 3 status, the Engine Hours do not have to be captured.</b>";
                    $(frm.fields_dict.pre_use_status_explain.wrapper).html(html);
                } else {
                    const no_records_html = "<p>No records found in 'Pre-Use Status'.</p>";
                    $(frm.fields_dict.pre_use_status_explain.wrapper).html(no_records_html);
                }
            }
        });
    }
});

frappe.ui.form.on('Pre-Use Assets', {
    eng_hrs_start: function(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        row.eng_hrs_end = null; // Clear eng_hrs_end when eng_hrs_start is edited
        frm.refresh_field('pre_use_assets');
    }
});

function fetch_shift_system(frm) {
    const shiftDate = frappe.datetime.str_to_obj(frm.doc.shift_date);

    const startOfMonth = new Date(shiftDate.getFullYear(), shiftDate.getMonth(), 1);
    const endOfMonth = new Date(shiftDate.getFullYear(), shiftDate.getMonth() + 1, 0);

    const startOfMonthStr = frappe.datetime.obj_to_str(startOfMonth);
    const endOfMonthStr = frappe.datetime.obj_to_str(endOfMonth);

    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Monthly Production Planning',
            filters: [
                ['location', '=', frm.doc.location],
                ['prod_month_end', '>=', startOfMonthStr],
                ['prod_month_end', '<=', endOfMonthStr]
            ],
            fields: ['shift_system'],
            order_by: 'prod_month_end asc',
            limit: 1
        },
        callback: function(response) {
            const planningDoc = response.message && response.message[0];
            if (planningDoc) {
                frm.set_value('shift_system', planningDoc.shift_system);

                if (planningDoc.shift_system === "2x12Hour") {
                    frm.fields_dict.shift.df.options = ['A', 'B'].join('\n');
                } else if (planningDoc.shift_system === "3x8Hour") {
                    frm.fields_dict.shift.df.options = ['A', 'B', 'C'].join('\n');
                }
                frm.refresh_field('shift');
            }
        }
    });
}

function disable_row_editing(frm) {
    frm.fields_dict['pre_use_assets'].grid.wrapper.find('.grid-remove-row').hide();
    frm.fields_dict['pre_use_assets'].grid.wrapper.find('.grid-duplicate-row').hide();
    frm.fields_dict['pre_use_assets'].grid.wrapper.find('[data-fieldname="eng_hrs_end"]').prop('readonly', true);
}

function set_avail_util_lookup(frm) {
    if (frm.doc.location && frm.doc.shift_date && frm.doc.shift) {
        const shift_date_formatted = frappe.datetime.str_to_user(frm.doc.shift_date);
        const avail_util_lookup_value = `${frm.doc.location}-${shift_date_formatted}-${frm.doc.shift}`;
        frm.set_value('avail_util_lookup', avail_util_lookup_value);
    } else {
        frm.set_value('avail_util_lookup', '');
    }
}
