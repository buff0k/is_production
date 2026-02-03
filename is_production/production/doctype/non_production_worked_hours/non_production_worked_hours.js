// Copyright (c) 2026, Isambane Mining (Pty) Ltd
// For license information, please see license.txt

function parse_duration_to_seconds(val) {
	// Frappe Duration can come through as:
	// - number (seconds)
	// - string "HH:MM:SS" or "MM:SS" or "H:MM"
	if (val === null || val === undefined || val === "") return 0;

	if (typeof val === "number") return val;

	// Sometimes Duration is stored as stringified number
	if (!isNaN(val)) return flt(val);

	if (typeof val !== "string") return 0;

	const s = val.trim();
	if (!s) return 0;

	const parts = s.split(":").map(p => p.trim());
	if (parts.some(p => p === "" || isNaN(p))) return 0;

	let seconds = 0;

	// HH:MM:SS
	if (parts.length === 3) {
		const hh = parseFloat(parts[0]);
		const mm = parseFloat(parts[1]);
		const ss = parseFloat(parts[2]);
		seconds = (hh * 3600) + (mm * 60) + ss;
	}
	// MM:SS (or H:MM if user typed "1:30" meaning 1h30m — we treat 2 parts as H:MM by default)
	else if (parts.length === 2) {
		const a = parseFloat(parts[0]);
		const b = parseFloat(parts[1]);

		// Heuristic:
		// If second part >= 60, it's invalid as minutes; still handle gracefully
		// We'll treat as H:MM always (common in Duration entry: 1:30 = 1h30m).
		seconds = (a * 3600) + (b * 60);
	}
	// SS
	else if (parts.length === 1) {
		seconds = parseFloat(parts[0]);
	}

	return seconds || 0;
}

function set_child_hours_from_total_time(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const seconds = parse_duration_to_seconds(row.total_time);
	const hours = seconds / 3600.0;

	// Keep some sensible precision
	frappe.model.set_value(cdt, cdn, "hours", flt(hours, 4));
}

function apply_machine_query_filter(frm) {
	// Filter the child table Link field "machine" (Asset)
	// Based on parent site + asset_category = "Excavator"
	const grid_field = frm.fields_dict.equipment_non_production_hours?.grid?.get_field("machine");
	if (!grid_field) return;

	grid_field.get_query = function (doc, cdt, cdn) {
		const filters = {
			asset_category: "Excavator"
		};

		if (frm.doc.site) {
			// Standard ERPNext Asset field is usually "location" (Link to Location)
			filters.location = frm.doc.site;
		}

		return { filters };
	};
}

frappe.ui.form.on("Non-Production Worked Hours", {
	setup(frm) {
		apply_machine_query_filter(frm);
	},

	refresh(frm) {
		apply_machine_query_filter(frm);
	},

	site(frm) {
		// When site changes, the child machine dropdown should reflect it
		apply_machine_query_filter(frm);

		// Optional: clear machines that no longer match (client-side convenience only)
		// (Server-side validation in .py will enforce constraints anyway)
		(frm.doc.equipment_non_production_hours || []).forEach(row => {
			if (row.machine) {
				// leave as-is; server validate will catch mismatches
			}
		});
	},

	before_save(frm) {
		// Ensure hours are recalculated for all rows before saving (client-side)
		(frm.doc.equipment_non_production_hours || []).forEach(row => {
			const seconds = parse_duration_to_seconds(row.total_time);
			row.hours = flt(seconds / 3600.0, 4);
		});
	}
});
