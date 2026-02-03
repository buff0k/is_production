// Copyright (c) 2026, Isambane Mining (Pty) Ltd
// For license information, please see license.txt

function parse_duration_to_seconds(val) {
	if (val === null || val === undefined || val === "") return 0;

	if (typeof val === "number") return val;
	if (!isNaN(val)) return flt(val);

	if (typeof val !== "string") return 0;
	const s = val.trim();
	if (!s) return 0;

	const parts = s.split(":").map(p => p.trim());
	if (parts.some(p => p === "" || isNaN(p))) return 0;

	let seconds = 0;

	if (parts.length === 3) {
		const hh = parseFloat(parts[0]);
		const mm = parseFloat(parts[1]);
		const ss = parseFloat(parts[2]);
		seconds = (hh * 3600) + (mm * 60) + ss;
	} else if (parts.length === 2) {
		// Treat as H:MM (typical)
		const hh = parseFloat(parts[0]);
		const mm = parseFloat(parts[1]);
		seconds = (hh * 3600) + (mm * 60);
	} else if (parts.length === 1) {
		seconds = parseFloat(parts[0]);
	}

	return seconds || 0;
}

function set_hours(cdt, cdn) {
	const row = locals[cdt][cdn];
	const seconds = parse_duration_to_seconds(row.total_time);
	const hours = seconds / 3600.0;
	frappe.model.set_value(cdt, cdn, "hours", flt(hours, 4));
}

frappe.ui.form.on("Equipment Breakdown", {
	total_time(frm, cdt, cdn) {
		set_hours(cdt, cdn);
	},

	// Optional: if you want hours to always reflect total_time even when rows load
	form_render(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row && row.total_time) {
			set_hours(cdt, cdn);
		}
	}
});
