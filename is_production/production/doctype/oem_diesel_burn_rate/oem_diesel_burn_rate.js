// Copyright (c) 2026, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

function load_models(frm) {
	if (!frm.doc.asset_category) {
		frm.set_df_property("model", "options", "");
		frm.refresh_field("model");
		return;
	}

	frappe.call({
		method: "is_production.production.doctype.oem_diesel_burn_rate.oem_diesel_burn_rate.get_models",
		args: {
			asset_category: frm.doc.asset_category,
		},
		callback(response) {
			const models = response.message || [];

			if (frm.doc.model && !models.includes(frm.doc.model)) {
				models.unshift(frm.doc.model);
			}

			frm.set_df_property(
				"model",
				"options",
				["", ...models].join("\n")
			);

			frm.refresh_field("model");
		},
	});
}


frappe.ui.form.on("OEM Diesel Burn Rate", {
	refresh(frm) {
		frm.set_intro(
			__(
				"One effective-dated OEM rate applies to every machine using the selected model."
			),
			"blue"
		);

		load_models(frm);
	},

	asset_category(frm) {
		frm.set_value("model", "");
		load_models(frm);
	},
});