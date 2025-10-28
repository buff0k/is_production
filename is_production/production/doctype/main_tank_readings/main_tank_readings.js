// ===========================================================
// Main Tank Readings - Simple Live Formula Version
// ===========================================================
// Formula logic:
// Theoretical Closing Balance = Opening Balance + Diesel Received - Diesel Issued
// Variance = Theoretical Closing Balance - Dipstick Value
// Updates live while typing, defaults to 0 when blank
// ===========================================================

frappe.ui.form.on('Main Tank Readings', {
  opening_balance(frm, cdt, cdn) { recalc(cdt, cdn); },
  diesel_received(frm, cdt, cdn) { recalc(cdt, cdn); },
  diesel_issued(frm, cdt, cdn) { recalc(cdt, cdn); },
  dipstick_value(frm, cdt, cdn) { recalc(cdt, cdn); }
});

function recalc(cdt, cdn) {
  const row = locals[cdt][cdn];

  const open = toNum(row.opening_balance);
  const received = toNum(row.diesel_received);
  const issued = toNum(row.diesel_issued);
  const dip = toNum(row.dipstick_value);

  const theoretical = open + received - issued;
  const variance = theoretical - dip;

  frappe.model.set_value(cdt, cdn, 'theoretical_closing_balance', theoretical);
  frappe.model.set_value(cdt, cdn, 'variance', variance);
}

function toNum(v) {
  return isNaN(parseFloat(v)) ? 0 : parseFloat(v);
}
