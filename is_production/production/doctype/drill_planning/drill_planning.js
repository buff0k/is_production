frappe.ui.form.on("Drill Planning", {
  refresh(frm) {
    compute_rates(frm);
  },

  monthly_drill_planning(frm) {
    // fetch_from should populate number_of_drills automatically
    // but we recompute for instant update
    compute_rates(frm);
  },

  start_date(frm) {
    compute_rates(frm);
  },

  end_date(frm) {
    compute_rates(frm);
  },

  monthly_target(frm) {
    compute_rates(frm);
  }
});

function compute_rates(frm) {
  const start = frm.doc.start_date;
  const end = frm.doc.end_date;
  const target = frm.doc.monthly_target;

  if (!start || !end || target === null || target === undefined) {
    frm.set_value("daily_required_rate", 0);
    frm.set_value("hourly_required_rate", 0);
    return;
  }

  const start_date = frappe.datetime.str_to_obj(start);
  const end_date = frappe.datetime.str_to_obj(end);

  if (!start_date || !end_date) return;

  if (end_date < start_date) {
    frm.set_value("daily_required_rate", 0);
    frm.set_value("hourly_required_rate", 0);
    return;
  }

  const diffMs = end_date - start_date;
  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24)) + 1; // inclusive

  if (days <= 0) {
    frm.set_value("daily_required_rate", 0);
    frm.set_value("hourly_required_rate", 0);
    return;
  }

  const shift_hours = 8.0; // keep same as python DEFAULT_SHIFT_HOURS
  const monthly_target = parseFloat(target) || 0;

  let daily = monthly_target / days;
  let hourly = daily / shift_hours;

  // OPTIONAL: If you want PER DRILL rates, uncomment:
  // const drills = parseFloat(frm.doc.number_of_drills) || 0;
  // if (drills > 0) {
  //   daily = daily / drills;
  //   hourly = hourly / drills;
  // }

  frm.set_value("daily_required_rate", frappe.utils.round_precision(daily, 1));
  frm.set_value("hourly_required_rate", frappe.utils.round_precision(hourly, 1));
}
