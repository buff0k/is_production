frappe.ui.form.on("Mining Schedule Scenario", {
	refresh(frm) {
		frm.trigger("set_indicators");
		frm.trigger("add_custom_buttons");
	},

	set_indicators(frm) {
		if (!frm.doc.schedule_status) {
			return;
		}

		const color_map = {
			"Draft": "orange",
			"Generated": "blue",
			"Reviewed": "purple",
			"Approved": "green",
			"Cancelled": "red"
		};

		frm.dashboard.clear_headline();
		frm.dashboard.set_headline_alert(
			`Status: ${frm.doc.schedule_status}`,
			color_map[frm.doc.schedule_status] || "gray"
		);
	},

	add_custom_buttons(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(__("Open Schedule Viewer"), function () {
			frappe.route_options = {
				scenario: frm.doc.name
			};
			frappe.set_route("mining-schedule-view");
		});

		frm.add_custom_button(__("Show Source Settings"), function () {
			frappe.call({
				method: "is_production.geo_planning.doctype.mining_schedule_scenario.mining_schedule_scenario.get_scenario_source_settings",
				args: {
					name: frm.doc.name
				},
				callback: function (r) {
					const settings = r.message || {};

					frappe.msgprint({
						title: __("Source Settings"),
						indicator: "blue",
						message: `<pre style="white-space: pre-wrap;">${frappe.utils.escape_html(JSON.stringify(settings, null, 2))}</pre>`
					});
				}
			});
		});

		frm.add_custom_button(__("Recalculate Totals"), function () {
			frappe.call({
				method: "is_production.geo_planning.doctype.mining_schedule_scenario.mining_schedule_scenario.recalculate_scenario_doc",
				args: {
					name: frm.doc.name
				},
				freeze: true,
				freeze_message: __("Recalculating..."),
				callback: function () {
					frappe.show_alert({
						message: __("Scenario totals recalculated."),
						indicator: "green"
					});

					frm.reload_doc();
				}
			});
		});

		frm.add_custom_button(__("Regenerate New Scenario"), function () {
			frappe.confirm(
				__("This will create a new scenario using the same settings. Continue?"),
				function () {
					frappe.call({
						method: "is_production.geo_planning.services.mining_schedule_scenario_service.regenerate_schedule_scenario",
						args: {
							name: frm.doc.name
						},
						freeze: true,
						freeze_message: __("Regenerating Scenario..."),
						callback: function (r) {
							const result = r.message || {};

							if (result.name) {
								frappe.set_route("Form", "Mining Schedule Scenario", result.name);
							}
						}
					});
				}
			);
		});

		if (frm.doc.schedule_status === "Generated" || frm.doc.schedule_status === "Draft") {
			frm.add_custom_button(__("Mark Reviewed"), function () {
				set_scenario_status(frm, "Reviewed");
			}, __("Status"));
		}

		if (frm.doc.schedule_status === "Reviewed") {
			frm.add_custom_button(__("Approve Scenario"), function () {
				set_scenario_status(frm, "Approved");
			}, __("Status"));
		}

		if (frm.doc.schedule_status !== "Cancelled") {
			frm.add_custom_button(__("Cancel Scenario"), function () {
				frappe.confirm(
					__("Cancel this schedule scenario?"),
					function () {
						set_scenario_status(frm, "Cancelled");
					}
				);
			}, __("Status"));
		}
	}
});


function set_scenario_status(frm, status) {
	frappe.call({
		method: "is_production.geo_planning.doctype.mining_schedule_scenario.mining_schedule_scenario.update_scenario_status",
		args: {
			name: frm.doc.name,
			status: status
		},
		freeze: true,
		freeze_message: __("Updating Status..."),
		callback: function () {
			frappe.show_alert({
				message: __("Scenario status updated to {0}.", [status]),
				indicator: "green"
			});

			frm.reload_doc();
		}
	});
}