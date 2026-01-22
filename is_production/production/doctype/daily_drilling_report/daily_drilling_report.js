// Client Script for DocType: Daily Drilling Report

frappe.ui.form.on("Daily Drilling Report", {
  refresh(frm) {
    recalc_totals(frm);
  },

  opening_drilling_hrs(frm) {
    recalc_totals(frm);
  },

  closing_drilling_hrs(frm) {
    recalc_totals(frm);
  },

  holes_and_meter_add(frm) {
    recalc_totals(frm);
  },

  holes_and_meter_remove(frm) {
    recalc_totals(frm);
  },

  validate(frm) {
    recalc_totals(frm);
  },
});

frappe.ui.form.on("Daily Drilling Hole", {
  no_of_holes(frm, cdt, cdn) {
    recalc_totals(frm);
  },

  meters(frm, cdt, cdn) {
    recalc_totals(frm);
  },
});

function recalc_totals(frm) {
  // ---- Total drilling hours ----
  const opening = flt(frm.doc.opening_drilling_hrs);
  const closing = flt(frm.doc.closing_drilling_hrs);

  // closing - opening
  const total_hrs = closing - opening;
  frm.set_value("total_drilling_hrs", total_hrs);

  // ---- Totals from child table ----
  const rows = frm.doc.holes_and_meter || [];

  let total_meters = 0;
  let total_holes = 0;

  rows.forEach((r) => {
    total_meters += flt(r.meters);
    total_holes += flt(r.no_of_holes);
  });

  frm.set_value("total_meters", total_meters);
  frm.set_value("total_holes", total_holes);

  frm.refresh_field("total_drilling_hrs");
  frm.refresh_field("total_meters");
  frm.refresh_field("total_holes");
}
