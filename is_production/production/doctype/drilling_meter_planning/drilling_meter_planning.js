frappe.ui.form.on("Drilling Meter Planning", {
  refresh(frm) {
    run_all(frm);
    fetch_actuals(frm);
  },

  start_date(frm) {
    run_all(frm);
    fetch_actuals(frm);
  },

  end_date(frm) {
    run_all(frm);
    fetch_actuals(frm);
  },

  monthly_target_meters(frm) { run_all(frm); },
  number_of_drills(frm) { run_all(frm); },

  weekday_shift_hours(frm) { run_all(frm); },
  saturday_shift_hours(frm) { run_all(frm); },
  no_of_shifts(frm) { run_all(frm); },

  worked_days(frm) { run_all(frm); },
  monthly_drilling_hours_completed(frm) { run_all(frm); },

  mtd_drills_meter(frm) { run_all(frm); }
});

// ---------------- SERVER FETCH (actuals) ----------------
function fetch_actuals(frm) {
  if (!frm.doc.name || !frm.doc.start_date || !frm.doc.end_date) return;

  frappe.call({
    method: "is_production.is_production.production.doctype.drilling_meter_planning.drilling_meter_planning.get_hourly_report_actuals",
    args: {
      planning_name: frm.doc.name
    },
    callback: function (r) {
      if (!r.message) return;

      if (r.message.worked_days !== undefined) {
        frm.set_value("worked_days", r.message.worked_days);
      }

      if (r.message.monthly_drilling_hours_completed !== undefined) {
        frm.set_value("monthly_drilling_hours_completed", r.message.monthly_drilling_hours_completed);
      }

      run_all(frm);
    }
  });
}

// ---------------- calculations ----------------
function run_all(frm) {
  set_drilling_month_label(frm);
  calc_planned_days(frm);
  calc_daily_target(frm);
  calc_remaining_days(frm);
  calc_total_monthly_hours(frm);
  calc_monthly_remaining_hours(frm);
  calc_remaining_meter(frm);
  calc_meters_per_drill(frm);
  calc_current_rate(frm);
  calc_required_hourly_rate(frm);
  calc_forecast(frm);
}

/* helper functions remain unchanged */
