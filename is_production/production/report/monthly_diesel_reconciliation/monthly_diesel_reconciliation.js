// Copyright (c) 2026, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

function remove_invalid_submit_button(frm) {
	const primary_button = frm.page?.btn_primary;

	if (
		Number(frm.meta.is_submittable || 0) === 0 &&
		primary_button?.length &&
		primary_button.text().trim() === __("Submit")
	) {
		frm.page.clear_primary_action();
	}
}

frappe.ui.form.on("OEM Diesel Burn Rate", {
	refresh(frm) {
		frm.set_intro("", "blue");
		frm.set_intro(
			__(
				"When a rate changes, add a new record with a new Effective From date. This keeps historical monthly reports accurate."
			),
			"blue"
		);

		setTimeout(() => remove_invalid_submit_button(frm), 300);
	},
});