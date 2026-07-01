// Copyright (c) 2026, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mining Schedule Scenario", {
	refresh(frm) {
		frm.trigger("set_indicators");
		frm.trigger("add_custom_buttons");
	},

	set_indicators(frm) {
		if (!frm.doc.schedule_status) return;

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
		if (frm.is_new()) return;

		frm.add_custom_button(__("Validate Schedule Foundation"), function () {
			frappe.call({
				method: "is_production.geo_planning.services.mining_schedule_foundation_service.validate_schedule_foundation_html",
				freeze: true,
				freeze_message: __("Validating schedule foundation..."),
				callback(r) {
					if (!r.exc && r.message) {
						frappe.msgprint({
							title: __("Schedule Foundation Validation"),
							message: r.message,
							wide: true
						});
					}
				}
			});
		}, __("Scheduling"));

		frm.add_custom_button(__("Edit Schedule Inputs"), function () {
			frappe.call({
				method: "is_production.geo_planning.services.mining_schedule_scenario_service.get_schedule_scenario_inputs",
				args: { scenario: frm.doc.name },
				freeze: true,
				freeze_message: __("Loading schedule inputs..."),
				callback(r) {
					show_schedule_inputs_dialog({
						frm: frm,
						mode: "edit",
						scenario: frm.doc.name,
						source_selection: frm.doc.mining_schedule_selection,
						defaults: r.message || {}
					});
				}
			});
		}, __("Scheduling"));

		frm.add_custom_button(__("Open Gantt View"), function () {
			frappe.route_options = { scenario: frm.doc.name };
			frappe.set_route("mining-schedule-gant");
		}, __("Scheduling"));

		frm.add_custom_button(__("Open Schedule Viewer"), function () {
			frappe.route_options = { scenario: frm.doc.name };
			frappe.set_route("mining-schedule-view");
		}, __("Scheduling"));

		frm.add_custom_button(__("Show Source Settings"), function () {
			show_source_settings(frm);
		}, __("Scheduling"));

		frm.add_custom_button(__("Recalculate Totals"), function () {
			frappe.call({
				method: "is_production.geo_planning.doctype.mining_schedule_scenario.mining_schedule_scenario.recalculate_scenario_doc",
				args: { name: frm.doc.name },
				freeze: true,
				freeze_message: __("Recalculating..."),
				callback() {
					frappe.show_alert({ message: __("Scenario totals recalculated."), indicator: "green" });
					frm.reload_doc();
				}
			});
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
				frappe.confirm(__("Cancel this schedule scenario?"), function () {
					set_scenario_status(frm, "Cancelled");
				});
			}, __("Status"));
		}
	}
});


function show_schedule_inputs_dialog(opts) {
	const frm = opts.frm;
	const defaults = opts.defaults || {};
	let mining_rules = parse_rules(defaults.mining_rules_json);
	let rule_material_options = [];

	const dialog = new frappe.ui.Dialog({
		title: __("Edit Schedule Inputs"),
		size: "extra-large",
		fields: [
			{ fieldtype: "Section Break", label: __("Scenario") },
			{
				fieldtype: "Data",
				fieldname: "scenario_name",
				label: __("Scenario Name"),
				reqd: 1,
				default: defaults.scenario_name || frm.doc.scenario_name || frm.doc.name
			},
			{
				fieldtype: "Select",
				fieldname: "period_type",
				label: __("Period Type"),
				options: "Daily\nWeekly\nMonthly",
				reqd: 1,
				default: defaults.period_type || frm.doc.period_type || "Weekly"
			},
			{
				fieldtype: "Date",
				fieldname: "start_date",
				label: __("Start Date"),
				reqd: 1,
				default: defaults.start_date || frm.doc.start_date || frappe.datetime.get_today()
			},
			{
				fieldtype: "Small Text",
				fieldname: "coal_materials",
				label: __("Coal Materials / Seams"),
				default: defaults.coal_materials || "2U,2L,S2U,S2L,Coal"
			},

			{ fieldtype: "Section Break", label: __("Mining Rules") },
			{
				fieldtype: "Select",
				fieldname: "mining_rule_application",
				label: __("Rule Application"),
				options: "Inside Each Block\nAcross All Blocks Then Next Rule",
				default: defaults.mining_rule_application || "Inside Each Block",
				reqd: 1
			},
			{
				fieldtype: "Code",
				fieldname: "mining_rules_json",
				label: __("Mining Rules JSON"),
				options: "JSON",
				hidden: 1,
				default: JSON.stringify(mining_rules || [])
			},
			{
				fieldtype: "HTML",
				fieldname: "rule_builder_html",
				options: `
					<div class="schedule-rule-panel">
						<button class="btn btn-sm btn-primary" data-action="open_rule_builder">
							${__("Open Rule Builder")}
						</button>
						<button class="btn btn-sm btn-default" data-action="show_rules_help">
							${__("What rules are there?")}
						</button>
						<div class="text-muted" style="margin-top: 8px;" data-role="rule_preview">
							${__("No custom rules loaded yet.")}
						</div>
					</div>
				`
			},

			{ fieldtype: "Section Break", label: __("Equipment Capacity") },
			{
				fieldtype: "Float",
				fieldname: "number_of_teams",
				label: __("Number of Teams"),
				default: defaults.number_of_teams || 1,
				reqd: 1
			},
			{
				fieldtype: "Float",
				fieldname: "team_capacity_per_hour",
				label: __("One Team Capacity per Hour"),
				default: defaults.team_capacity_per_hour || 0,
				reqd: 1,
				description: __("For coal tasks this is tonnes/hour. For non-coal tasks this is BCM/hour.")
			},
			{ fieldtype: "Column Break" },
			{
				fieldtype: "Percent",
				fieldname: "availability_percent",
				label: __("Availability %"),
				default: defaults.availability_percent || 85
			},
			{
				fieldtype: "Percent",
				fieldname: "utilisation_percent",
				label: __("Utilisation %"),
				default: defaults.utilisation_percent || 80
			},

			{ fieldtype: "Section Break", label: __("Working Time") },
			{
				fieldtype: "Float",
				fieldname: "weekday_shifts",
				label: __("Weekday Shifts per Day"),
				default: defaults.weekday_shifts || 2
			},
			{
				fieldtype: "Float",
				fieldname: "weekday_hours_per_shift",
				label: __("Weekday Hours per Shift"),
				default: defaults.weekday_hours_per_shift || 10
			},
			{
				fieldtype: "Float",
				fieldname: "saturday_shifts",
				label: __("Saturday Shifts"),
				default: defaults.saturday_shifts || 1
			},
			{
				fieldtype: "Float",
				fieldname: "saturday_hours_per_shift",
				label: __("Saturday Hours per Shift"),
				default: defaults.saturday_hours_per_shift || 8
			},
			{ fieldtype: "Column Break" },
			{
				fieldtype: "Float",
				fieldname: "sunday_shifts",
				label: __("Sunday Shifts"),
				default: defaults.sunday_shifts || 0
			},
			{
				fieldtype: "Float",
				fieldname: "sunday_hours_per_shift",
				label: __("Sunday Hours per Shift"),
				default: defaults.sunday_hours_per_shift || 0
			},

			{ fieldtype: "Section Break", label: __("Drilling / Blasting") },
			{
				fieldtype: "Check",
				fieldname: "drilling_required",
				label: __("Drilling Required"),
				default: defaults.drilling_required || 0
			},
			{
				fieldtype: "Small Text",
				fieldname: "drilling_materials",
				label: __("Drilling Materials"),
				default: defaults.drilling_materials || "Hards,Hard"
			},
			{
				fieldtype: "Float",
				fieldname: "drilling_hours_per_block_material",
				label: __("Drilling Hours per Block Material"),
				default: defaults.drilling_hours_per_block_material || 0
			},
			{
				fieldtype: "Small Text",
				fieldname: "remarks",
				label: __("Remarks"),
				default: defaults.remarks || frm.doc.remarks || ""
			}
		],
		primary_action_label: __("Regenerate Scenario"),
		primary_action(values) {
			if (!values.scenario_name || !values.start_date) {
				frappe.msgprint(__("Scenario Name and Start Date are required."));
				return;
			}

			dialog.hide();

			frappe.call({
				method: "is_production.geo_planning.services.mining_schedule_scenario_service.update_schedule_scenario_from_inputs",
				args: {
					scenario: opts.scenario,
					scenario_name: values.scenario_name,
					period_type: values.period_type,
					start_date: values.start_date,
					coal_materials: values.coal_materials,
					mining_rule_application: values.mining_rule_application,
					mining_rules_json: dialog.get_value("mining_rules_json") || "[]",
					number_of_teams: values.number_of_teams,
					team_capacity_per_hour: values.team_capacity_per_hour,
					weekday_shifts: values.weekday_shifts,
					weekday_hours_per_shift: values.weekday_hours_per_shift,
					saturday_shifts: values.saturday_shifts,
					saturday_hours_per_shift: values.saturday_hours_per_shift,
					sunday_shifts: values.sunday_shifts,
					sunday_hours_per_shift: values.sunday_hours_per_shift,
					availability_percent: values.availability_percent,
					utilisation_percent: values.utilisation_percent,
					drilling_required: values.drilling_required,
					drilling_materials: values.drilling_materials,
					drilling_hours_per_block_material: values.drilling_hours_per_block_material,
					remarks: values.remarks
				},
				freeze: true,
				freeze_message: __("Regenerating mining schedule..."),
				callback(r) {
					const result = r.message || {};
					frappe.show_alert({ message: __("Scenario regenerated."), indicator: "green" });
					if (result.name) frappe.set_route("Form", "Mining Schedule Scenario", result.name);
					frm.reload_doc();
				}
			});
		}
	});

	dialog.show();

	frappe.call({
		method: "is_production.geo_planning.services.mining_schedule_scenario_service.get_schedule_rule_context",
		args: {
			mining_schedule_selection: opts.source_selection,
			scenario: opts.scenario
		},
		callback(r) {
			const context = r.message || {};
			rule_material_options = context.material_options || [];
			if (!mining_rules.length && context.default_rules) {
				mining_rules = context.default_rules || [];
				dialog.set_value("mining_rules_json", JSON.stringify(mining_rules));
			}
			update_rule_preview(dialog, mining_rules);
		}
	});

	dialog.$wrapper.find('[data-action="open_rule_builder"]').on("click", function () {
		open_rule_builder({
			rules: mining_rules,
			material_options: rule_material_options,
			on_save(rules) {
				mining_rules = rules;
				dialog.set_value("mining_rules_json", JSON.stringify(rules || []));
				update_rule_preview(dialog, rules);
			}
		});
	});

	dialog.$wrapper.find('[data-action="show_rules_help"]').on("click", show_mining_rules_help);
}


function open_rule_builder(opts) {
	const options_text = (opts.material_options || []).join("\n");
	const rules = (opts.rules || []).map((rule, index) => ({
		rule_no: rule.rule_no || index + 1,
		material_code: rule.material_code || "",
		rule_note: rule.rule_note || ""
	}));

	const dialog = new frappe.ui.Dialog({
		title: __("Mining Rule Builder"),
		size: "large",
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "intro",
				options: `
					<div style="margin-bottom: 12px;">
						<div style="font-weight: 700; font-size: 14px;">${__("Choose the material codes in the order they must be mined.")}</div>
						<div class="text-muted">${__("The dropdown is built from the selected blocks and Material Stack. Missing material in a block is skipped.")}</div>
					</div>
				`
			},
			{
				fieldtype: "Table",
				fieldname: "rules",
				label: __("Rules"),
				data: rules,
				in_place_edit: 1,
				fields: [
					{ fieldtype: "Int", fieldname: "rule_no", label: __("Rule No"), in_list_view: 1, reqd: 1, columns: 1 },
					{ fieldtype: "Select", fieldname: "material_code", label: __("Material Code"), options: options_text, in_list_view: 1, reqd: 1, columns: 3 },
					{ fieldtype: "Data", fieldname: "rule_note", label: __("Rule Note"), in_list_view: 1, columns: 4 }
				]
			}
		],
		primary_action_label: __("Save Rules"),
		primary_action(values) {
			const clean = (values.rules || [])
				.filter((row) => row.material_code)
				.map((row, index) => ({
					rule_no: cint(row.rule_no || index + 1),
					material_code: row.material_code,
					rule_note: row.rule_note || ""
				}))
				.sort((a, b) => cint(a.rule_no) - cint(b.rule_no));

			dialog.hide();
			if (opts.on_save) opts.on_save(clean);
		}
	});

	dialog.show();
}


function update_rule_preview(dialog, rules) {
	const preview = dialog.$wrapper.find('[data-role="rule_preview"]');
	if (!preview.length) return;

	if (!rules || !rules.length) {
		preview.html(`<span class="text-muted">${__("No custom rules. Scheduler will use Material Stack Mining Sequence No.")}</span>`);
		return;
	}

	const html = rules
		.sort((a, b) => cint(a.rule_no) - cint(b.rule_no))
		.map((rule) => `<span class="rule-chip">${frappe.utils.escape_html(rule.rule_no + ". " + rule.material_code)}</span>`)
		.join("");

	preview.html(`<div>${html}</div>`);

	if (!$("#schedule-rule-chip-style").length) {
		$("head").append(`
			<style id="schedule-rule-chip-style">
				.rule-chip {
					display: inline-block;
					padding: 4px 8px;
					border: 1px solid var(--border-color);
					border-radius: 999px;
					margin: 0 4px 4px 0;
					background: var(--fg-color);
					font-size: 12px;
				}
			</style>
		`);
	}
}


function parse_rules(value) {
	if (!value) return [];
	if (Array.isArray(value)) return value;
	try {
		return JSON.parse(value) || [];
	} catch (e) {
		return [];
	}
}


function show_mining_rules_help() {
	frappe.msgprint({
		title: __("Mining Scheduling Rules"),
		indicator: "blue",
		message: `
			<div>
				<p><b>${__("Rule Builder")}</b></p>
				<p>${__("Pick material codes from the dropdown and arrange them in the order they must be mined.")}</p>
				<hr>
				<p><b>${__("Inside Each Block")}</b></p>
				<p>${__("The rule order is applied inside Block 1, then Block 2, then Block 3.")}</p>
				<hr>
				<p><b>${__("Across All Blocks Then Next Rule")}</b></p>
				<p>${__("The first material rule is mined across all selected blocks, then the second material rule across all selected blocks.")}</p>
			</div>
		`
	});
}


function show_source_settings(frm) {
	frappe.call({
		method: "is_production.geo_planning.doctype.mining_schedule_scenario.mining_schedule_scenario.get_scenario_source_settings",
		args: { name: frm.doc.name },
		callback(r) {
			const settings = r.message || {};
			frappe.msgprint({
				title: __("Source Settings"),
				indicator: "blue",
				message: `<pre style="white-space: pre-wrap;">${frappe.utils.escape_html(JSON.stringify(settings, null, 2))}</pre>`
			});
		}
	});
}


function set_scenario_status(frm, status) {
	frappe.call({
		method: "is_production.geo_planning.doctype.mining_schedule_scenario.mining_schedule_scenario.update_scenario_status",
		args: { name: frm.doc.name, status: status },
		freeze: true,
		freeze_message: __("Updating Status..."),
		callback() {
			frappe.show_alert({ message: __("Scenario status updated to {0}.", [status]), indicator: "green" });
			frm.reload_doc();
		}
	});
}