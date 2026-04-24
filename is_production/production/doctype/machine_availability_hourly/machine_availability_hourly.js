// Copyright (c) 2026
// For license information, please see license.txt

// apps/is_production/is_production/production/doctype/machine_availability_hourly/machine_availability_hourly.js

frappe.ui.form.on('Machine Availability Hourly', {
    setup(frm) {
        set_default_shift_options(frm);
    },

    refresh(frm) {
        set_default_shift_options(frm);

        if (frm.doc.date) {
            set_day_number(frm);
        }

        if (frm.doc.shift) {
            update_shift_num_hour_options(frm);
        }

        if (frm.doc.shift_num_hour) {
            update_hour_slot(frm);
        }
    },

    date(frm) {
        set_day_number(frm);

        if (frm.doc.shift_num_hour) {
            update_hour_slot(frm);
        }
    },

    site(frm) {
        populate_assets_from_site_and_category(frm);
    },

    asset_category(frm) {
        populate_assets_from_site_and_category(frm);
    },

    shift(frm) {
        update_shift_num_hour_options(frm);
        frm.set_value('hour_slot', null);
        frm.set_value('hour_sort_key', null);
    },

    shift_num_hour(frm) {
        update_hour_slot(frm);
    },

    before_save(frm) {
        set_day_number(frm);
        update_hour_slot(frm);
    }
});

function populate_assets_from_site_and_category(frm) {
    if (!frm.doc.site || !frm.doc.asset_category) {
        return;
    }

    frappe.call({
        method: 'is_production.production.doctype.machine_availability_hourly.machine_availability_hourly.get_assets_for_site_and_category',
        args: {
            site: frm.doc.site,
            asset_category: frm.doc.asset_category
        },
        freeze: true,
        freeze_message: __('Fetching machines...'),
        callback(r) {
            const assets = r.message || [];

            frm.clear_table('machine_availability');

            assets.forEach(asset => {
                const row = frm.add_child('machine_availability');
                row.asset = asset.name;

                if ('asset_name' in row) {
                    row.asset_name = asset.asset_name || '';
                }
            });

            frm.refresh_field('machine_availability');

            frappe.show_alert({
                message: __('{0} machine(s) loaded.', [assets.length]),
                indicator: 'green'
            });
        }
    });
}

function set_default_shift_options(frm) {
    set_options(frm, 'shift', ['', 'Day', 'Night', 'Morning', 'Afternoon']);
}

function update_shift_num_hour_options(frm) {
    const shift = frm.doc.shift;

    if (!shift) {
        set_options(frm, 'shift_num_hour', ['']);
        return;
    }

    const count = get_shift_hour_count(shift);
    const opts = [''];

    for (let i = 1; i <= count; i++) {
        opts.push(`${shift}-${i}`);
    }

    set_options(frm, 'shift_num_hour', opts);

    if (frm.doc.shift_num_hour && !frm.doc.shift_num_hour.startsWith(`${shift}-`)) {
        frm.set_value('shift_num_hour', null);
    }
}

function update_hour_slot(frm) {
    if (!frm.doc.shift_num_hour) return;

    const parts = frm.doc.shift_num_hour.split('-');

    if (parts.length !== 2) return;

    const shiftName = parts[0];
    const hourIndex = parseInt(parts[1], 10);

    if (!shiftName || isNaN(hourIndex)) return;

    const baseHour = get_base_hour(shiftName);
    const startHour = (baseHour + (hourIndex - 1)) % 24;
    const endHour = (startHour + 1) % 24;

    frm.set_value('hour_sort_key', hourIndex);
    frm.set_value('hour_slot', `${format_hour(startHour)}-${format_hour(endHour)}`);
}

function set_day_number(frm) {
    if (!frm.doc.date) {
        frm.set_value('day_number', null);
        return;
    }

    const dateObj = parse_date(frm.doc.date);

    if (!dateObj || isNaN(dateObj.getTime())) {
        frm.set_value('day_number', null);
        return;
    }

    frm.set_value('day_number', dateObj.getDate());
}

function get_shift_hour_count(shift) {
    if (shift === 'Day') return 12;
    if (shift === 'Night') return 12;
    if (shift === 'Morning') return 8;
    if (shift === 'Afternoon') return 8;

    return 8;
}

function get_base_hour(shift) {
    if (shift === 'Day') return 6;
    if (shift === 'Morning') return 6;
    if (shift === 'Afternoon') return 14;
    if (shift === 'Night') return 18;

    return 6;
}

function format_hour(hour) {
    return `${String(hour).padStart(2, '0')}:00`;
}

function parse_date(value) {
    if (!value) return null;

    try {
        if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
            return new Date(value);
        }

        if (/^\d{2}-\d{2}-\d{4}$/.test(value)) {
            const [d, m, y] = value.split('-');
            return new Date(`${y}-${m}-${d}`);
        }

        if (frappe.datetime && frappe.datetime.str_to_obj) {
            return frappe.datetime.str_to_obj(value);
        }

        return new Date(value);
    } catch (e) {
        console.warn('Could not parse date:', value, e);
        return null;
    }
}

function set_options(frm, fieldname, options) {
    if (frm.fields_dict[fieldname]) {
        frm.set_df_property(fieldname, 'options', options.join('\n'));
    }
}