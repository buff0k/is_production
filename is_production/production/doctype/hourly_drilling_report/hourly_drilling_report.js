frappe.ui.form.on("Hourly Drilling Report", {
  validate(frm) {
    // make sure meters stays numeric
    (frm.doc.hourly_entries || []).forEach(row => {
      row.meters = flt(row.meters || 0);
    });
    frm.refresh_field("hourly_entries");
  }
});

frappe.ui.form.on("Hourly Entries", {
  meters(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    row.meters = flt(row.meters || 0);
    frm.refresh_field("hourly_entries");
  }
});
