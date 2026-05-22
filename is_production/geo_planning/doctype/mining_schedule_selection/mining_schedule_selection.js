frappe.ui.form.on("Mining Schedule Selection", {
	refresh(frm) {
		frm.trigger("set_indicators");
		frm.trigger("add_custom_buttons");
	},

	set_indicators(frm) {
		if (!frm.doc.selection_status) {
			return;
		}

		const color_map = {
			"Draft": "orange",
			"Reviewed": "blue",
			"Approved": "green",
			"Sent To Scheduler": "purple",
			"Cancelled": "red"
		};

		frm.dashboard.clear_headline();
		frm.dashboard.set_headline_alert(
			`Status: ${frm.doc.selection_status}`,
			color_map[frm.doc.selection_status] || "gray"
		);
	},

	add_custom_buttons(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(__("Create Schedule Scenario"), function () {
			show_create_schedule_scenario_dialog(frm);
		}, __("Scheduling"));

		frm.add_custom_button(__("Open Selector"), function () {
			frappe.set_route("mining-block-selecto");
		});

		frm.add_custom_button(__("Show Source Filters"), function () {
			frappe.call({
				method: "is_production.geo_planning.doctype.mining_schedule_selection.mining_schedule_selection.get_source_filters",
				args: {
					name: frm.doc.name
				},
				callback: function (r) {
					const filters = r.message || {};

					frappe.msgprint({
						title: __("Source Filters"),
						indicator: "blue",
						message: `<pre style="white-space: pre-wrap;">${frappe.utils.escape_html(JSON.stringify(filters, null, 2))}</pre>`
					});
				}
			});
		});

		frm.add_custom_button(__("Validate Selection"), function () {
			frappe.call({
				method: "is_production.geo_planning.doctype.mining_schedule_selection.mining_schedule_selection.validate_selection_integrity",
				args: {
					name: frm.doc.name
				},
				freeze: true,
				freeze_message: __("Validating Selection..."),
				callback: function (r) {
					const result = r.message || {};
					const critical_issues = result.critical_issues || [];
					const warnings = result.warnings || [];

					if (!critical_issues.length && !warnings.length) {
						frappe.msgprint({
							title: __("Selection Integrity"),
							indicator: "green",
							message: __("Passed. No issues found.")
						});
						return;
					}

					let message = "";

					if (critical_issues.length) {
						const critical_html = critical_issues.map((issue) => {
							return `<li>${frappe.utils.escape_html(issue)}</li>`;
						}).join("");

						message += `<p><b>${__("Critical Issues")}</b></p><ul>${critical_html}</ul>`;
					}

					if (warnings.length) {
						const warning_html = warnings.map((warning) => {
							return `<li>${frappe.utils.escape_html(warning)}</li>`;
						}).join("");

						message += `<p><b>${__("Warnings")}</b></p><ul>${warning_html}</ul>`;
					}

					frappe.msgprint({
						title: __("Selection Integrity"),
						indicator: critical_issues.length ? "red" : "orange",
						message: message
					});
				}
			});
		});

		frm.add_custom_button(__("Recalculate Totals"), function () {
			frappe.call({
				method: "is_production.geo_planning.doctype.mining_schedule_selection.mining_schedule_selection.recalculate_selection_doc",
				args: {
					name: frm.doc.name
				},
				freeze: true,
				freeze_message: __("Recalculating Totals..."),
				callback: function () {
					frappe.show_alert({
						message: __("Totals recalculated."),
						indicator: "green"
					});

					frm.reload_doc();
				}
			});
		});

		if (frm.doc.selection_status === "Draft") {
			frm.add_custom_button(__("Mark Reviewed"), function () {
				set_selection_status(frm, "Reviewed");
			}, __("Status"));
		}

		if (frm.doc.selection_status === "Reviewed") {
			frm.add_custom_button(__("Approve Selection"), function () {
				set_selection_status(frm, "Approved");
			}, __("Status"));
		}

		if (frm.doc.selection_status !== "Cancelled" && frm.doc.selection_status !== "Sent To Scheduler") {
			frm.add_custom_button(__("Cancel Selection"), function () {
				frappe.confirm(
					__("Cancel this selection?"),
					function () {
						set_selection_status(frm, "Cancelled");
					}
				);
			}, __("Status"));
		}
	}
});


function show_create_schedule_scenario_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Create Schedule Scenario"),
		size: "large",
		fields: [
			{
				fieldtype: "Data",
				fieldname: "scenario_name",
				label: __("Scenario Name"),
				reqd: 1,
				default: `${frm.doc.selection_name || frm.doc.name} - Weekly Scenario`
			},
			{
				fieldtype: "Select",
				fieldname: "period_type",
				label: __("Period Type"),
				options: "Weekly\nMonthly\nDaily",
				default: "Weekly",
				reqd: 1
			},
			{
				fieldtype: "Date",
				fieldname: "start_date",
				label: __("Start Date"),
				reqd: 1,
				default: frappe.datetime.get_today()
			},
			{
				fieldtype: "Select",
				fieldname: "schedule_basis",
				label: __("Schedule Basis"),
				options: "Fleet Capacity\nTarget Tonnes\nTarget Volume\nSelection Sequence",
				default: "Fleet Capacity",
				reqd: 1
			},
			{
				fieldtype: "Column Break"
			},
			{
				fieldtype: "Float",
				fieldname: "number_of_shifts",
				label: __("Number of Shifts"),
				default: 2
			},
			{
				fieldtype: "Float",
				fieldname: "hours_per_shift",
				label: __("Hours Per Shift"),
				default: 10
			},
			{
				fieldtype: "Float",
				fieldname: "fleet_capacity_bcm_per_hour",
				label: __("Fleet Capacity BCM Per Hour")
			},
			{
				fieldtype: "Float",
				fieldname: "fleet_capacity_tonnes_per_hour",
				label: __("Fleet Capacity Tonnes Per Hour")
			},
			{
				fieldtype: "Section Break",
				label: __("Manual Period Targets")
			},
			{
				fieldtype: "Float",
				fieldname: "target_tonnes_per_period",
				label: __("Target Tonnes Per Period")
			},
			{
				fieldtype: "Float",
				fieldname: "target_volume_per_period",
				label: __("Target Volume Per Period")
			},
			{
				fieldtype: "Section Break",
				label: __("Drill / Blast")
			},
			{
				fieldtype: "Check",
				fieldname: "drill_blast_required",
				label: __("Drill / Blast Required")
			},
			{
				fieldtype: "Int",
				fieldname: "drill_blast_lead_time_days",
				label: __("Drill / Blast Lead Time Days")
			},
			{
				fieldtype: "Small Text",
				fieldname: "remarks",
				label: __("Remarks")
			}
		],
		primary_action_label: __("Create Scenario"),
		primary_action: function (values) {
			dialog.hide();

			frappe.call({
				method: "is_production.geo_planning.services.mining_schedule_scenario_service.create_schedule_scenario_from_selection",
				args: {
					mining_schedule_selection: frm.doc.name,
					scenario_name: values.scenario_name,
					period_type: values.period_type,
					start_date: values.start_date,
					schedule_basis: values.schedule_basis,
					target_tonnes_per_period: values.target_tonnes_per_period,
					target_volume_per_period: values.target_volume_per_period,
					number_of_shifts: values.number_of_shifts,
					hours_per_shift: values.hours_per_shift,
					fleet_capacity_bcm_per_hour: values.fleet_capacity_bcm_per_hour,
					fleet_capacity_tonnes_per_hour: values.fleet_capacity_tonnes_per_hour,
					drill_blast_required: values.drill_blast_required,
					drill_blast_lead_time_days: values.drill_blast_lead_time_days,
					remarks: values.remarks
				},
				freeze: true,
				freeze_message: __("Creating Schedule Scenario..."),
				callback: function (r) {
					const result = r.message || {};

					if (!result.name) {
						frappe.msgprint(__("Scenario was created, but no document name was returned."));
						return;
					}

					frappe.show_alert({
						message: __("Schedule Scenario {0} created.", [result.name]),
						indicator: "green"
					});

					frappe.set_route("Form", "Mining Schedule Scenario", result.name);
				}
			});
		}
	});

	dialog.show();
}


function set_selection_status(frm, status) {
	frappe.call({
		method: "is_production.geo_planning.doctype.mining_schedule_selection.mining_schedule_selection.update_selection_status",
		args: {
			name: frm.doc.name,
			status: status
		},
		freeze: true,
		freeze_message: __("Updating Status..."),
		callback: function () {
			frappe.show_alert({
				message: __("Selection status updated to {0}.", [status]),
				indicator: "green"
			});

			frm.reload_doc();
		}
	});
}