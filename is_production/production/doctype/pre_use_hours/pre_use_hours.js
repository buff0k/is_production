frappe.ui.form.on('Pre-Use Hours', {
    shift_system: function (frm) {
        update_shift_options(frm, frm.doc.shift_system);
    },
    location: function (frm) {
        if (frm.doc.location) {
            frm.clear_table('pre_use_assets');
            fetch_assets(frm);

            // Trigger shift system fetch if shift_date is populated
            if (frm.doc.shift_date) fetch_shift_system(frm);

            set_avail_util_lookup(frm);
        }
    },
    shift_date: function (frm) {
        if (frm.doc.location) fetch_shift_system(frm);
        set_avail_util_lookup(frm);
    },
    shift: function (frm) {
        set_avail_util_lookup(frm);
    },
    refresh: function (frm) {
        fetch_pre_use_status(frm);
    }
});

function update_shift_options(frm, shift_system) {
    const shift_options = {
        '3x8Hour': ['Morning', 'Afternoon', 'Night'],
        '2x12Hour': ['Day', 'Night']
    };
    frm.set_df_property('shift', 'options', shift_options[shift_system] || []);
}

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
            limit_page_length: 1000 // Set a large enough limit or manage pagination
        },
        callback: function (response) {
            response.message.forEach(asset => {
                const row = frm.add_child('pre_use_assets');
                row.asset_name = asset.asset_name;
                row.item_name = asset.item_name;
                row.asset_category = asset.asset_category;
            });
            frm.refresh_field('pre_use_assets');
        }
    });
}

function fetch_shift_system(frm) {
    if (!frm.doc.location || !frm.doc.shift_date) return;

    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Monthly Production Planning',
            filters: {
                location: frm.doc.location,
                prod_month_end: [">=", frm.doc.shift_date],
                site_status: 'Producing'
            },
            fields: ['prod_month_end', 'shift_system'],
            limit_page_length: 1
        },
        callback: function (response) {
            if (response.message.length) {
                const record = response.message[0];
                const prod_month_end = frappe.datetime.str_to_obj(record.prod_month_end);
                const shift_date = frappe.datetime.str_to_obj(frm.doc.shift_date);

                // Ensure shift_date falls in the same month as prod_month_end
                if (shift_date.getMonth() !== prod_month_end.getMonth() || shift_date.getFullYear() !== prod_month_end.getFullYear()) {
                    frappe.throw("Shift Date must be in the same month as the month that ends on prod_month_end.");
                }

                frm.set_value('shift_system', record.shift_system);
                update_shift_options(frm, record.shift_system);
            }
        }
    });
}

function set_avail_util_lookup(frm) {
    if (frm.doc.location && frm.doc.shift_date && frm.doc.shift) {
        const shift_date_formatted = frappe.datetime.str_to_user(frm.doc.shift_date);
        const avail_util_lookup_value = `${frm.doc.location}-${shift_date_formatted}-${frm.doc.shift}`;
        frm.set_value('avail_util_lookup', avail_util_lookup_value);
    }
}

function fetch_pre_use_status(frm) {
    frappe.call({
        method: 'frappe.client.get_list',
        args: { doctype: 'Pre-Use Status', fields: ['name', 'pre_use_avail_status'], order_by: 'name asc' },
        callback: function (response) {
            const records = response.message;
            let html = records.length
                ? generate_status_table(records)
                : "<p>No records found in 'Pre-Use Status'.</p>";

            // Append the instructional text at the bottom
            html += "<br><b>Please ensure correct status is indicated for each Plant e.g. if Plant is not working @ shift start due to Breakdown status of 2 must be selected. Or if machine is spare then select status 3.</b>";

            $(frm.fields_dict.pre_use_status_explain.wrapper).html(html);
        }
    });
}

function generate_status_table(records) {
    let html = "<table style='width:100%; border-collapse: collapse;'>";
    html += "<tr><th>Status</th><th>Pre-Use Availability Status</th></tr>";
    records.forEach(record => {
        html += `<tr><td>${record.name}</td><td>${record.pre_use_avail_status}</td></tr>`;
    });
    html += "</table>";
    return html;
}
