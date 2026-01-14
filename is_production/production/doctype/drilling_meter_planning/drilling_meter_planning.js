frappe.ui.form.on('Drilling Meter Planning', {
    refresh(frm) {
        run_all(frm);
    },

    start_date(frm) { run_all(frm); },
    end_date(frm) { run_all(frm); },

    weekday_shift_hours(frm) { run_all(frm); },
    saturday_shift_hours(frm) { run_all(frm); },
    no_of_shifts(frm) { run_all(frm); },

    worked_days(frm) { run_all(frm); },
    monthly_target_meters(frm) { run_all(frm); },
    number_of_drills(frm) { run_all(frm); }
});

// ---------- main ----------
function run_all(frm) {
    set_drilling_month_label(frm);

    const counts = get_weekdays_and_saturdays(frm.doc.start_date, frm.doc.end_date);
    const planned_days = (counts.weekdays + counts.saturdays);

    // planned drilling days (no Sundays)
    frm.set_value('planned_drilling_days', planned_days);

    // clamp worked days
    const worked = Math.min(flt(frm.doc.worked_days), flt(planned_days));
    frm.set_value('worked_days', worked);

    // remaining days
    frm.set_value('remaining_days', Math.max(planned_days - worked, 0));

    // shifts + hours
    const no_shifts = cint(frm.doc.no_of_shifts) || 0;
    const weekday_hours = flt(frm.doc.weekday_shift_hours);
    const saturday_hours = flt(frm.doc.saturday_shift_hours);

    const total_hours_one_shift = (counts.weekdays * weekday_hours) + (counts.saturdays * saturday_hours);
    const total_monthly_hours = Math.max(total_hours_one_shift * no_shifts, 0);
    frm.set_value('total_monthly_drilling_hours', total_monthly_hours);

    // completed hours based on planned mix
    const avg_hours_day_one_shift = planned_days > 0 ? (total_hours_one_shift / planned_days) : 0;
    const completed_hours = Math.max(worked * avg_hours_day_one_shift * no_shifts, 0);
    frm.set_value('monthly_drilling_hours_completed', completed_hours);

    // remaining hours
    const remaining_hours = Math.max(total_monthly_hours - completed_hours, 0);
    frm.set_value('monthly_remaining_drilling_hours', remaining_hours);

    // MTD meters (linear progress)
    const target = flt(frm.doc.monthly_target_meters);
    let mtd = planned_days > 0 ? (worked / planned_days) * target : 0;
    mtd = clamp(mtd, 0, target);
    frm.set_value('mtd_drills_meter', mtd);

    // remaining meters
    const remaining_meter = Math.max(target - mtd, 0);
    frm.set_value('remaining_meter', remaining_meter);

    // current rate (m/h)
    const current_rate = completed_hours > 0 ? (mtd / completed_hours) : 0;
    frm.set_value('current_rate', current_rate);

    // required hourly rate (m/h)
    const required_rate = remaining_hours > 0 ? (remaining_meter / remaining_hours) : 0;
    frm.set_value('required_hourly_rate', required_rate);

    // meters per drill
    const drills = flt(frm.doc.number_of_drills);
    const meters_per_drill = drills > 0 ? (target / drills) : 0;
    frm.set_value('meters_per_drill', meters_per_drill);

    // forecast
    let forecast = mtd + (current_rate * remaining_hours);
    forecast = clamp(forecast, 0, target);
    frm.set_value('drilling_meters_forecast', forecast);
}

// ---------- helpers ----------
function set_drilling_month_label(frm) {
    if (frm.doc.start_date && frm.doc.end_date) {
        const start = moment(frm.doc.start_date);
        const end = moment(frm.doc.end_date);

        if (end.isBefore(start, 'day')) {
            frm.set_value('drilling_month', '');
            return;
        }

        if (start.month() === end.month() && start.year() === end.year()) {
            frm.set_value('drilling_month', start.format('MMMM YYYY'));
        } else {
            frm.set_value('drilling_month', `${start.format('MMM YYYY')} - ${end.format('MMM YYYY')}`);
        }
    } else {
        frm.set_value('drilling_month', '');
    }
}

function get_weekdays_and_saturdays(start_date, end_date) {
    const result = { weekdays: 0, saturdays: 0 };

    if (!start_date || !end_date) return result;

    const start = moment(start_date);
    const end = moment(end_date);

    if (end.isBefore(start, 'day')) return result;

    let d = start.clone();
    while (d.isSameOrBefore(end, 'day')) {
        const wd = d.day(); // Sun=0 ... Sat=6
        if (wd >= 1 && wd <= 5) result.weekdays += 1;    // Mon-Fri
        else if (wd === 6) result.saturdays += 1;        // Sat
        // Sundays ignored
        d.add(1, 'day');
    }
    return result;
}

function clamp(v, min, max) {
    return Math.max(min, Math.min(max, v));
}
