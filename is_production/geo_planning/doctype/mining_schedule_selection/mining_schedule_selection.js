frappe.ui.form.on("Mining Schedule Selection", {
	refresh(frm) {
		frm.trigger("set_indicators");
		frm.trigger("add_custom_buttons");
	},

	set_indicators(frm) {
		if (!frm.doc.selection_status) return;

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
		if (frm.is_new()) return;

		frm.add_custom_button(__("Create Schedule Scenario"), function () {
			show_schedule_inputs_dialog({
				frm: frm,
				mode: "create",
				source_selection: frm.doc.name,
				defaults: {
					scenario_name: `${frm.doc.selection_name || frm.doc.name} - Schedule`
				}
			});
		}, __("Scheduling"));

		frm.add_custom_button(__("Open Selector"), function () {
			frappe.set_route("mining-block-selecto");
		});

		frm.add_custom_button(__("Recalculate Totals"), function () {
			frappe.call({
				method: "is_production.geo_planning.doctype.mining_schedule_selection.mining_schedule_selection.recalculate_selection_doc",
				args: { name: frm.doc.name },
				freeze: true,
				freeze_message: __("Recalculating Totals..."),
				callback: function () {
					frappe.show_alert({ message: __("Totals recalculated."), indicator: "green" });
					frm.reload_doc();
				}
			});
		});

		frm.add_custom_button(__("Validate Selection"), function () {
			frappe.call({
				method: "is_production.geo_planning.doctype.mining_schedule_selection.mining_schedule_selection.validate_selection_integrity",
				args: { name: frm.doc.name },
				freeze: true,
				freeze_message: __("Validating Selection..."),
				callback: function (r) {
					const result = r.message || {};
					const critical = result.critical_issues || [];
					const warnings = result.warnings || [];

					if (!critical.length && !warnings.length) {
						frappe.msgprint({
							title: __("Selection Integrity"),
							indicator: "green",
							message: __("Passed. No issues found.")
						});
						return;
					}

					let message = "";

					if (critical.length) {
						message += `<p><b>${__("Critical Issues")}</b></p><ul>`;
						message += critical.map((issue) => `<li>${frappe.utils.escape_html(issue)}</li>`).join("");
						message += `</ul>`;
					}

					if (warnings.length) {
						message += `<p><b>${__("Warnings")}</b></p><ul>`;
						message += warnings.map((warning) => `<li>${frappe.utils.escape_html(warning)}</li>`).join("");
						message += `</ul>`;
					}

					frappe.msgprint({
						title: __("Selection Integrity"),
						indicator: critical.length ? "red" : "orange",
						message: message
					});
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
				frappe.confirm(__("Cancel this selection?"), function () {
					set_selection_status(frm, "Cancelled");
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
		title: opts.mode === "edit" ? __("Edit Schedule Inputs") : __("Create Schedule Scenario"),
		size: "extra-large",
		fields: [
			{ fieldtype: "Section Break", label: __("Scenario") },
			{
				fieldtype: "Data",
				fieldname: "scenario_name",
				label: __("Scenario Name"),
				reqd: 1,
				default: defaults.scenario_name || ""
			},
			{
				fieldtype: "Select",
				fieldname: "period_type",
				label: __("Period Type"),
				options: "Daily\nWeekly\nMonthly",
				default: defaults.period_type || "Weekly",
				reqd: 1
			},
			{
				fieldtype: "Date",
				fieldname: "start_date",
				label: __("Start Date"),
				default: defaults.start_date || frappe.datetime.get_today(),
				reqd: 1
			},
			{
				fieldtype: "Small Text",
				fieldname: "coal_materials",
				label: __("Coal Materials / Seams"),
				default: defaults.coal_materials || "2U,2L,S2U,S2L,Coal",
				description: __("Comma separated. Matching materials are scheduled in tonnes. Everything else is scheduled in BCM.")
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
				default: defaults.drilling_materials || "Hards,Hard",
				description: __("Comma separated. Example: Hards,Hard,Blast")
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
				default: defaults.remarks || ""
			}
		],
		primary_action_label: opts.mode === "edit" ? __("Regenerate Scenario") : __("Generate Schedule"),
		primary_action(values) {
			if (!values.scenario_name || !values.start_date) {
				frappe.msgprint(__("Scenario Name and Start Date are required."));
				return;
			}

			dialog.hide();

			const method = opts.mode === "edit"
				? "is_production.geo_planning.services.mining_schedule_scenario_service.update_schedule_scenario_from_inputs"
				: "is_production.geo_planning.services.mining_schedule_scenario_service.create_schedule_scenario_from_selection";

			const args = Object.assign({}, values);
			args.mining_rules_json = dialog.get_value("mining_rules_json") || "[]";

			if (opts.mode === "edit") {
				args.scenario = opts.scenario;
			} else {
				args.mining_schedule_selection = opts.source_selection;
			}

			frappe.call({
				method: method,
				args: args,
				freeze: true,
				freeze_message: __("Generating mining schedule..."),
				callback(r) {
					const result = r.message || {};

					if (!result.name) {
						frappe.msgprint(__("Schedule was generated, but no scenario name was returned."));
						return;
					}

					frappe.show_alert({
						message: __("Schedule Scenario {0} generated.", [result.name]),
						indicator: "green"
					});

					frappe.set_route("Form", "Mining Schedule Scenario", result.name);
				}
			});
		}
	});

	dialog.show();

	const load_rule_context = () => {
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
	};

	dialog.$wrapper.find('[data-action="open_rule_builder"]').on("click", function () {
		open_rule_builder({
			parent_dialog: dialog,
			rules: mining_rules,
			material_options: rule_material_options,
			on_save: function (rules) {
				mining_rules = rules;
				dialog.set_value("mining_rules_json", JSON.stringify(rules || []));
				update_rule_preview(dialog, mining_rules);
			}
		});
	});

	dialog.$wrapper.find('[data-action="show_rules_help"]').on("click", show_mining_rules_help);

	load_rule_context();
	update_rule_preview(dialog, mining_rules);
}


function open_rule_builder(opts) {
	const material_options = opts.material_options || [];
	const options_text = material_options.join("\n");
	const rules = (opts.rules || []).map((rule, index) => {
		return {
			rule_no: rule.rule_no || index + 1,
			material_code: rule.material_code || rule.material_seam || "",
			rule_note: rule.rule_note || ""
		};
	});

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
						<div class="text-muted">
							${__("The dropdown is built from the selected blocks and the Material Stack. If a block does not contain that material, it is skipped.")}
						</div>
					</div>
				`
			},
			{
				fieldtype: "Table",
				fieldname: "rules",
				label: __("Rules"),
				cannot_add_rows: 0,
				in_place_edit: 1,
				data: rules,
				fields: [
					{
						fieldtype: "Int",
						fieldname: "rule_no",
						label: __("Rule No"),
						in_list_view: 1,
						reqd: 1,
						columns: 1
					},
					{
						fieldtype: "Select",
						fieldname: "material_code",
						label: __("Material Code"),
						options: options_text,
						in_list_view: 1,
						reqd: 1,
						columns: 3
					},
					{
						fieldtype: "Data",
						fieldname: "rule_note",
						label: __("Rule Note"),
						in_list_view: 1,
						columns: 4
					}
				]
			}
		],
		primary_action_label: __("Save Rules"),
		primary_action(values) {
			const clean = (values.rules || [])
				.filter((row) => row.material_code)
				.map((row, index) => {
					return {
						rule_no: cint(row.rule_no || index + 1),
						material_code: row.material_code,
						rule_note: row.rule_note || ""
					};
				})
				.sort((a, b) => cint(a.rule_no) - cint(b.rule_no));

			dialog.hide();

			if (opts.on_save) {
				opts.on_save(clean);
			}
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
		.map((rule) => {
			return `<span class="rule-chip">${frappe.utils.escape_html(rule.rule_no + ". " + rule.material_code)}</span>`;
		})
		.join("");

	preview.html(`
		<div style="margin-top: 8px;">
			<div class="text-muted" style="margin-bottom: 4px;">${__("Current rule order")}</div>
			${html}
		</div>
	`);

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
				<p>${__("The selected rule order is applied inside Block 1, then Block 2, then Block 3.")}</p>

				<hr>

				<p><b>${__("Across All Blocks Then Next Rule")}</b></p>
				<p>${__("The first material rule is mined across all selected blocks, then the second material rule across all selected blocks, and so on.")}</p>

				<hr>

				<p><b>${__("Coal Rule")}</b></p>
				<p>${__("Coal Materials / Seams controls which material codes use tonnes. Everything else uses BCM.")}</p>
			</div>
		`
	});
}


function set_selection_status(frm, status) {
	frappe.call({
		method: "is_production.geo_planning.doctype.mining_schedule_selection.mining_schedule_selection.update_selection_status",
		args: { name: frm.doc.name, status: status },
		freeze: true,
		freeze_message: __("Updating Status..."),
		callback() {
			frappe.show_alert({
				message: __("Selection status updated to {0}.", [status]),
				indicator: "green"
			});
			frm.reload_doc();
		}
	});
}