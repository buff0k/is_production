frappe.ui.form.on('Rental Equipment', {
    refresh(frm) {
        frm.add_custom_button(__('Generate Month Rows'), function () {
            generate_month_rows(frm);
        });

        frm.add_custom_button(__('Populate Hours & Diesel'), function () {
            populate_hours_and_diesel(frm);
        });

        if (frm.doc.plant_number) {
            fetch_asset_details(frm);
        }
    },

    plant_number(frm) {
        fetch_asset_details(frm);

        if (frm.doc.month && frm.doc.rental_equipment_logs && frm.doc.rental_equipment_logs.length) {
            frappe.show_alert({
                message: __('Plant Number changed. Click Populate Hours & Diesel to refresh logs.'),
                indicator: 'orange'
            });
        }
    },

    site(frm) {
        if (frm.doc.month && frm.doc.rental_equipment_logs && frm.doc.rental_equipment_logs.length) {
            frappe.show_alert({
                message: __('Site changed. Click Populate Hours & Diesel to refresh logs.'),
                indicator: 'orange'
            });
        }
    }
});


frappe.ui.form.on('Rental Equipment Log Row', {
    start(frm, cdt, cdn) {
        calculate_row(frm, cdt, cdn);
    },

    stop(frm, cdt, cdn) {
        calculate_row(frm, cdt, cdn);
    },

    hours(frm, cdt, cdn) {
        calculate_row(frm, cdt, cdn);
    },

    liter(frm, cdt, cdn) {
        calculate_row(frm, cdt, cdn);
    },

    litres(frm, cdt, cdn) {
        calculate_row(frm, cdt, cdn);
    }
});


function fetch_asset_details(frm) {
    if (!frm.doc.plant_number) {
        frm.set_value('make', '');
        frm.set_value('model', '');
        return;
    }

    frappe.db.get_value(
        'Asset',
        frm.doc.plant_number,
        [
            'asset_category',
            'item_code'
        ]
    ).then(function (r) {
        if (!r || !r.message) {
            return;
        }

        const asset = r.message;

        // Make = Asset Category
        frm.set_value('make', asset.asset_category || '');

        // Model = Item Code
        frm.set_value('model', asset.item_code || '');
    });
}


function generate_month_rows(frm) {
    if (!frm.doc.month) {
        frappe.msgprint(__('Please enter Month first. Example: Jan-26 or Jan-2026'));
        return;
    }

    const parsed = parse_month_year(frm.doc.month);

    if (!parsed) {
        frappe.msgprint(__('Month format must be like Jan-26 or Jan-2026'));
        return;
    }

    const year = parsed.year;
    const month = parsed.month;
    const daysInMonth = new Date(year, month + 1, 0).getDate();

    frm.clear_table('rental_equipment_logs');

    for (let day = 1; day <= daysInMonth; day++) {
        const d = new Date(year, month, day);
        const row = frm.add_child('rental_equipment_logs');

        row.date = format_date_for_frappe(d);
        row.day = d.toLocaleDateString('en-US', { weekday: 'long' });
        row.start = 0;
        row.stop = 0;
        row.total = 0;
        row.hr_meter = 0;
        row.hours = 0;

        set_row_litres_js(row, 0);

        row.lhr = 0;
        row.comment = '';
    }

    frm.refresh_field('rental_equipment_logs');
    calculate_totals(frm);
}


function parse_month_year(value) {
    value = String(value || '').trim();

    const parts = value.split('-');

    if (parts.length !== 2) {
        return null;
    }

    const monthMap = {
        Jan: 0,
        Feb: 1,
        Mar: 2,
        Apr: 3,
        May: 4,
        Jun: 5,
        Jul: 6,
        Aug: 7,
        Sep: 8,
        Oct: 9,
        Nov: 10,
        Dec: 11
    };

    const monthName = parts[0].trim();
    const yearText = parts[1].trim();
    const yearPart = parseInt(yearText, 10);

    if (!(monthName in monthMap)) {
        return null;
    }

    if (isNaN(yearPart)) {
        return null;
    }

    let year;

    if (yearText.length === 2) {
        year = 2000 + yearPart;
    } else {
        year = yearPart;
    }

    return {
        month: monthMap[monthName],
        year: year
    };
}


function format_date_for_frappe(d) {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');

    return `${year}-${month}-${day}`;
}


function populate_hours_and_diesel(frm) {
    if (!frm.doc.name || frm.doc.__islocal) {
        frappe.msgprint(__('Please save the document first before populating hours and diesel.'));
        return;
    }

    if (!frm.doc.site) {
        frappe.msgprint(__('Please select Site first.'));
        return;
    }

    if (!frm.doc.plant_number) {
        frappe.msgprint(__('Please select Plant Number first.'));
        return;
    }

    if (!frm.doc.shift) {
        frappe.msgprint(__('Please select Shift first.'));
        return;
    }

    if (!frm.doc.rental_equipment_logs || !frm.doc.rental_equipment_logs.length) {
        frappe.msgprint(__('Please generate month rows first.'));
        return;
    }

    frappe.call({
        method: 'is_production.production.doctype.rental_equipment.rental_equipment.populate_rental_equipment_logs',
        args: {
            docname: frm.doc.name
        },
        freeze: true,
        freeze_message: __('Populating hours and diesel...'),
        callback: function (r) {
            if (!r.exc) {
                frappe.show_alert({
                    message: __('Hours and diesel populated successfully.'),
                    indicator: 'green'
                });

                frm.reload_doc();
            }
        }
    });
}


function calculate_row(frm, cdt, cdn) {
    const row = locals[cdt][cdn];

    const start = flt(row.start);
    const stop = flt(row.stop);
    const hours = flt(row.hours);
    const litres = get_row_litres_js(row);

    row.total = stop - start;

    if (hours) {
        row.lhr = litres / hours;
    } else {
        row.lhr = 0;
    }

    frm.refresh_field('rental_equipment_logs');
    calculate_totals(frm);
}


function calculate_totals(frm) {
    let total_litres = 0;
    let first_start = 0;
    let last_stop = 0;

    (frm.doc.rental_equipment_logs || []).forEach(function (row) {
        const start = flt(row.start);
        const stop = flt(row.stop);
        const hours = flt(row.hours);
        const litres = get_row_litres_js(row);

        row.total = stop - start;

        if (hours) {
            row.lhr = litres / hours;
        } else {
            row.lhr = 0;
        }

        total_litres += litres;

        if (!first_start && start) {
            first_start = start;
        }

        if (stop) {
            last_stop = stop;
        }
    });

    frm.set_value('start_hrs', first_start);
    frm.set_value('closing_hrs', last_stop);

    if (first_start && last_stop) {
        frm.set_value('total_hrs', last_stop - first_start);
    } else {
        frm.set_value('total_hrs', 0);
    }

    frm.set_value('total_litres', total_litres);

    const total_hrs = flt(frm.doc.total_hrs);

    if (total_hrs) {
        frm.set_value('average_lhr', total_litres / total_hrs);
    } else {
        frm.set_value('average_lhr', 0);
    }

    frm.refresh_field('rental_equipment_logs');
}


function get_row_litres_js(row) {
    if (row.litres !== undefined) {
        return flt(row.litres);
    }

    if (row.liter !== undefined) {
        return flt(row.liter);
    }

    return 0;
}


function set_row_litres_js(row, value) {
    if (row.litres !== undefined) {
        row.litres = flt(value);
        return;
    }

    if (row.liter !== undefined) {
        row.liter = flt(value);
        return;
    }
}


function flt(value) {
    if (value === null || value === undefined) {
        return 0;
    }

    value = String(value);
    value = value.replace(/ /g, '');
    value = value.replace(/,/g, '');

    value = parseFloat(value);

    if (isNaN(value)) {
        return 0;
    }

    return value;
}
