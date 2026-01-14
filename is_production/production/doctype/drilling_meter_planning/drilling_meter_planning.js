frappe.ui.form.on('Drilling Meter Planning', {
    refresh(frm) {
        set_drilling_month_label(frm);
        set_planned_days_from_dates(frm);

        calc_remaining_days(frm);
        calc_remaining_meter(frm);
        calc_remaining_hours(frm);
        calc_required_hourly_rate(frm);
        calc_drilling_forecast(frm);
    },

    start_date(frm) {
        set_drilling_month_label(frm);
        set_planned_days_from_dates(frm);
        calc_remaining_days(frm);
    },

    end_date(frm) {
        set_drilling_month_label(frm);
        set_planned_days_from_dates(frm);
        calc_remaining_days(frm);
    },

    planned_drilling_days(frm) {
        calc_remaining_days(frm);
    },

    worked_days(frm) {
        calc_remaining_days(frm);
    },

    monthly_target_meters(frm) {
        calc_remaining_meter(frm);
        calc_required_hourly_rate(frm);
    },

    mtd_drills_meter(frm) {
        calc_remaining_meter(frm);
        calc_required_hourly_rate(frm);
        calc_drilling_forecast(frm);
    },

    total_monthly_drilling_hours(frm) {
        calc_remaining_hours(frm);
        calc_required_hourly_rate(frm);
        calc_drilling_forecast(frm);
    },

    monthly_drilling_hours_completed(frm) {
        calc_remaining_hours(frm);
        calc_required_hourly_rate(frm);
        calc_drilling_forecast(frm);
    },

    current_rate(frm) {
        calc_drilling_forecast(frm);
    }
});

// ---------------- helpers ----------------

function set_drilling_month_label(frm) {
    // drilling_month is Data field: "January 2026" or "Jan 2026 - Feb 2026"
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

function set_planned_days_from_dates(frm) {
    // Optional: auto-fill planned_drilling_days if empty/0
    if (frm.doc.start_date && frm.doc.end_date) {
        const start = moment(frm.doc.start_date);
        const end = moment(frm.doc.end_date);

        if (end.isBefore(start, 'day')) return;

        if (!flt(frm.doc.planned_drilling_days)) {
            const days_inclusive = end.diff(start, 'days') + 1;
            frm.set_value('planned_drilling_days', days_inclusive);
        }
    }
}

function calc_remaining_days(frm) {
    const planned = flt(frm.doc.planned_drilling_days);
    const worked = flt(frm.doc.worked_days);
    frm.set_value('remaining_days', Math.max(planned - worked, 0));
}

function calc_remaining_meter(frm) {
    const target = flt(frm.doc.monthly_target_meters);
    const mtd = flt(frm.doc.mtd_drills_meter);
    frm.set_value('remaining_meter', Math.max(target - mtd, 0));
}

function calc_remaining_hours(frm) {
    const total = flt(frm.doc.total_monthly_drilling_hours);
    const completed = flt(frm.doc.monthly_drilling_hours_completed);
    frm.set_value('monthly_remaining_drilling_hours', Math.max(total - completed, 0));
}

function calc_required_hourly_rate(frm) {
    const remaining_meter = flt(frm.doc.remaining_meter);
    const remaining_hours = flt(frm.doc.monthly_remaining_drilling_hours);

    if (remaining_hours > 0) {
        frm.set_value('required_hourly_rate', remaining_meter / remaining_hours);
    } else {
        frm.set_value('required_hourly_rate', 0);
    }
}

function calc_drilling_forecast(frm) {
    // forecast = MTD meters + (current_rate * remaining_hours)
    const mtd = flt(frm.doc.mtd_drills_meter);
    const rate = flt(frm.doc.current_rate);
    const remaining_hours = flt(frm.doc.monthly_remaining_drilling_hours);

    frm.set_value('drilling_meters_forecast', mtd + (rate * remaining_hours));
}
