// ------------------------------
// Child Table Script: Surveyed Values
// ------------------------------
frappe.ui.form.on('Surveyed Values', {
    // When the 'bcm' field is updated in a child row...
    bcm: function(frm, cdt, cdn) {
        update_metric_tonnes(cdt, cdn);
        calculate_total_bcm(frm);
    },
    // When the 'rd' field is updated in a child row...
    rd: function(frm, cdt, cdn) {
        update_metric_tonnes(cdt, cdn);
    },
    // Recalculate total when a row is removed
    after_delete: function(frm, cdt, cdn) {
        calculate_total_bcm(frm);
    }
});

// Function to update metric tonnes in a child row
function update_metric_tonnes(cdt, cdn) {
    let row = locals[cdt][cdn];
    let bcm_value = flt(row.bcm);
    let rd_value = flt(row.rd);
    let result = bcm_value * rd_value;
    frappe.model.set_value(cdt, cdn, 'metric_tonnes', result);
}

// ------------------------------
// Parent Form Script: Survey
// ------------------------------
frappe.ui.form.on('Survey', {
    // Recalculate total when the parent form is refreshed
    refresh: function(frm) {
        calculate_total_bcm(frm);
    }
});

// Function to calculate the total bcm from all child rows and set it on the parent
function calculate_total_bcm(frm) {
    let total = 0;
    if (frm.doc.surveyed_values && frm.doc.surveyed_values.length) {
        frm.doc.surveyed_values.forEach(row => {
            total += flt(row.bcm);
        });
    }
    frm.set_value('total_surveyed_bcm', total);
}
