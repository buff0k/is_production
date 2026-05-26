frappe.pages["mining-schedule-gant"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Mining Schedule Gantt"),
		single_column: true
	});

	new MiningScheduleGant(page);
};


class MiningScheduleGant {
	constructor(page) {
		this.page = page;
		this.wrapper = $(page.body);
		this.data = null;
		this.active_period_no = null;
		this.active_unit = "All";
		this.active_material = "All";

		this.make();

		const route_options = frappe.get_route_options() || {};

		if (route_options.scenario) {
			this.scenario_control.set_value(route_options.scenario);
			this.load();
		}
	}

	make() {
		this.wrapper.html(`
			<div class="gant-page">
				<div class="gant-topbar">
					<div class="gant-filter-card">
						<div data-field="scenario"></div>
						<div data-field="period_filter"></div>
						<div data-field="unit_filter"></div>
						<div data-field="material_filter"></div>
						<div class="gant-actions">
							<button class="btn btn-sm btn-primary" data-action="load">${__("Load")}</button>
							<button class="btn btn-sm btn-default" data-action="reset_filters">${__("Reset")}</button>
						</div>
					</div>
				</div>

				<div class="gant-summary" data-role="summary"></div>

				<div class="gant-layout">
					<div class="gant-main">
						<div class="gant-card">
							<div class="gant-card-header">
								<div>
									<h4>${__("Period Plan")}</h4>
									<div class="text-muted">${__("Concise period-by-period mining output.")}</div>
								</div>
							</div>
							<div data-role="period_cards"></div>
						</div>

						<div class="gant-card">
							<div class="gant-card-header">
								<div>
									<h4>${__("Timeline")}</h4>
									<div class="text-muted">${__("Rows are material movement tasks. Green = coal tonnes. Orange = BCM.")}</div>
								</div>
							</div>
							<div data-role="gant"></div>
						</div>
					</div>

					<div class="gant-side">
						<div class="gant-card">
							<h4>${__("Material Summary")}</h4>
							<div data-role="material_summary"></div>
						</div>

						<div class="gant-card">
							<h4>${__("Selected Output")}</h4>
							<div data-role="selected_output"></div>
						</div>
					</div>
				</div>

				<div class="gant-card">
					<div class="gant-card-header">
						<div>
							<h4>${__("Detailed Output Table")}</h4>
							<div class="text-muted">${__("Period, block, material, unit, volume and tonnes.")}</div>
						</div>
					</div>
					<div data-role="table"></div>
				</div>
			</div>
		`);

		this.add_styles();
		this.make_controls();
		this.bind_events();
		this.render_empty();
	}

	make_controls() {
		this.scenario_control = frappe.ui.form.make_control({
			parent: this.wrapper.find('[data-field="scenario"]'),
			df: {
				fieldtype: "Link",
				fieldname: "scenario",
				label: __("Mining Schedule Scenario"),
				options: "Mining Schedule Scenario",
				reqd: 1,
				change: () => this.load()
			},
			render_input: true
		});

		this.period_filter_control = frappe.ui.form.make_control({
			parent: this.wrapper.find('[data-field="period_filter"]'),
			df: {
				fieldtype: "Select",
				fieldname: "period_filter",
				label: __("Period"),
				options: "All",
				default: "All",
				change: () => {
					this.active_period_no = this.get_period_filter_value();
					this.render();
				}
			},
			render_input: true
		});

		this.unit_filter_control = frappe.ui.form.make_control({
			parent: this.wrapper.find('[data-field="unit_filter"]'),
			df: {
				fieldtype: "Select",
				fieldname: "unit_filter",
				label: __("Unit"),
				options: "All\nBCM\nTonnes",
				default: "All",
				change: () => {
					this.active_unit = this.unit_filter_control.get_value() || "All";
					this.render();
				}
			},
			render_input: true
		});

		this.material_filter_control = frappe.ui.form.make_control({
			parent: this.wrapper.find('[data-field="material_filter"]'),
			df: {
				fieldtype: "Select",
				fieldname: "material_filter",
				label: __("Material"),
				options: "All",
				default: "All",
				change: () => {
					this.active_material = this.material_filter_control.get_value() || "All";
					this.render();
				}
			},
			render_input: true
		});
	}

	bind_events() {
		this.page.set_primary_action(__("Load"), () => this.load());

		this.wrapper.find('[data-action="load"]').on("click", () => {
			this.load();
		});

		this.wrapper.find('[data-action="reset_filters"]').on("click", () => {
			this.active_period_no = null;
			this.active_unit = "All";
			this.active_material = "All";

			this.period_filter_control.set_value("All");
			this.unit_filter_control.set_value("All");
			this.material_filter_control.set_value("All");

			this.render();
		});
	}

	load() {
		const scenario = this.scenario_control.get_value();

		if (!scenario) {
			return;
		}

		frappe.call({
			method: "is_production.geo_planning.page.mining_schedule_gant.mining_schedule_gant.get_gant_data",
			args: {
				scenario: scenario
			},
			freeze: true,
			freeze_message: __("Loading schedule output..."),
			callback: (r) => {
				this.data = r.message || {};
				this.active_period_no = null;
				this.active_unit = "All";
				this.active_material = "All";

				this.refresh_filter_options();
				this.render();
			}
		});
	}

	refresh_filter_options() {
		const periods = this.data && this.data.periods ? this.data.periods : [];
		const tasks = this.data && this.data.tasks ? this.data.tasks : [];

		const period_options = ["All"].concat(
			periods.map((period) => `${period.period_no} - ${period.period_label}`)
		);

		const material_options = ["All"].concat(
			[...new Set(tasks.map((task) => task.material_seam).filter(Boolean))].sort()
		);

		this.period_filter_control.df.options = period_options.join("\n");
		this.period_filter_control.refresh();
		this.period_filter_control.set_value("All");

		this.unit_filter_control.set_value("All");

		this.material_filter_control.df.options = material_options.join("\n");
		this.material_filter_control.refresh();
		this.material_filter_control.set_value("All");
	}

	get_period_filter_value() {
		const value = this.period_filter_control.get_value();

		if (!value || value === "All") {
			return null;
		}

		return cint(String(value).split(" - ")[0]);
	}

	render_empty() {
		this.wrapper.find('[data-role="summary"]').html("");
		this.wrapper.find('[data-role="period_cards"]').html("");
		this.wrapper.find('[data-role="material_summary"]').html("");
		this.wrapper.find('[data-role="selected_output"]').html("");
		this.wrapper.find('[data-role="gant"]').html(`
			<div class="gant-empty">
				${__("Select a Mining Schedule Scenario and click Load.")}
			</div>
		`);
		this.wrapper.find('[data-role="table"]').html("");
	}

	render() {
		if (!this.data) {
			this.render_empty();
			return;
		}

		this.render_summary();
		this.render_period_cards();
		this.render_material_summary();
		this.render_selected_output();
		this.render_gant();
		this.render_table();
	}

	get_filtered_tasks() {
		let tasks = this.data && this.data.tasks ? this.data.tasks : [];

		if (this.active_period_no) {
			tasks = tasks.filter((task) => cint(task.period_no) === cint(this.active_period_no));
		}

		if (this.active_unit && this.active_unit !== "All") {
			tasks = tasks.filter((task) => {
				return (task.mining_unit || this.infer_unit(task)) === this.active_unit;
			});
		}

		if (this.active_material && this.active_material !== "All") {
			tasks = tasks.filter((task) => task.material_seam === this.active_material);
		}

		return tasks;
	}

	render_summary() {
		const scenario = this.data.scenario || {};
		const tasks = this.get_filtered_tasks();

		const totals = this.calculate_task_totals(tasks);

		this.wrapper.find('[data-role="summary"]').html(`
			<div class="gant-metric wide">
				<div class="gant-label">${__("Scenario")}</div>
				<div class="gant-value">${frappe.utils.escape_html(scenario.scenario_name || scenario.name || "")}</div>
			</div>
			<div class="gant-metric">${this.metric(__("Periods"), scenario.total_periods || 0, 0)}</div>
			<div class="gant-metric">${this.metric(__("Blocks"), totals.block_count || 0, 0)}</div>
			<div class="gant-metric orange">${this.metric(__("BCM"), totals.bcm || 0, 2)}</div>
			<div class="gant-metric green">${this.metric(__("Tonnes"), totals.tonnes || 0, 2)}</div>
			<div class="gant-metric">${this.metric(__("Capacity Used"), `${format_number(scenario.capacity_used_percent || 0, null, 1)}%`, null, true)}</div>
		`);
	}

	metric(label, value, decimals, raw) {
		const display_value = raw ? value : format_number(value || 0, null, decimals);
		return `
			<div class="gant-label">${frappe.utils.escape_html(label)}</div>
			<div class="gant-value">${frappe.utils.escape_html(String(display_value))}</div>
		`;
	}

	render_period_cards() {
		const periods = this.data.period_summaries || [];
		const tasks = this.get_filtered_tasks();
		const active_periods = new Set(tasks.map((task) => cint(task.period_no)));

		let shown_periods = periods;

		if (this.active_period_no) {
			shown_periods = periods.filter((period) => cint(period.period_no) === cint(this.active_period_no));
		} else if (this.active_unit !== "All" || this.active_material !== "All") {
			shown_periods = periods.filter((period) => active_periods.has(cint(period.period_no)));
		}

		if (!shown_periods.length) {
			this.wrapper.find('[data-role="period_cards"]').html(`<div class="gant-empty small">${__("No periods for selected filters.")}</div>`);
			return;
		}

		const html = shown_periods.map((period) => {
			const used = flt(period.capacity_used_percent || 0);
			const used_width = Math.min(100, Math.max(0, used));

			return `
				<div class="period-card" data-period-no="${period.period_no}">
					<div class="period-card-head">
						<div>
							<div class="period-title">${frappe.utils.escape_html(period.period_label || "")}</div>
							<div class="period-dates">${frappe.utils.escape_html(period.start || "")} → ${frappe.utils.escape_html(period.end || "")}</div>
						</div>
						<div class="period-used">${format_number(used, null, 1)}%</div>
					</div>
					<div class="capacity-bar">
						<div class="capacity-fill" style="width: ${used_width}%;"></div>
					</div>
					<div class="period-stats">
						<div><span>${__("BCM")}</span><b>${format_number(period.bcm || 0, null, 0)}</b></div>
						<div><span>${__("Tonnes")}</span><b>${format_number(period.tonnes || 0, null, 0)}</b></div>
						<div><span>${__("Blocks")}</span><b>${format_number(period.block_count || 0, null, 0)}</b></div>
						<div><span>${__("Materials")}</span><b>${format_number(period.material_count || 0, null, 0)}</b></div>
					</div>
				</div>
			`;
		}).join("");

		this.wrapper.find('[data-role="period_cards"]').html(`<div class="period-grid">${html}</div>`);

		this.wrapper.find(".period-card").on("click", (event) => {
			const period_no = cint($(event.currentTarget).attr("data-period-no"));
			this.active_period_no = period_no;
			this.period_filter_control.set_value(`${period_no} - ${this.get_period_label(period_no)}`);
			this.render();
		});
	}

	render_material_summary() {
		const tasks = this.get_filtered_tasks();
		const grouped = {};

		tasks.forEach((task) => {
			const material = task.material_seam || __("No Material");
			const unit = task.mining_unit || this.infer_unit(task);
			const key = `${material}||${unit}`;

			if (!grouped[key]) {
				grouped[key] = {
					material,
					unit,
					qty: 0,
					blocks: new Set(),
					periods: new Set()
				};
			}

			grouped[key].qty += this.get_task_quantity(task, unit);

			if (task.mining_block || task.mining_block_code) {
				grouped[key].blocks.add(task.mining_block || task.mining_block_code);
			}

			if (task.period_label) {
				grouped[key].periods.add(task.period_label);
			}
		});

		const rows = Object.values(grouped)
			.sort((a, b) => (a.unit || "").localeCompare(b.unit || "") || (a.material || "").localeCompare(b.material || ""))
			.map((row) => {
				return `
					<div class="material-pill ${row.unit === "Tonnes" ? "is-tonnes" : "is-bcm"}">
						<div>
							<strong>${frappe.utils.escape_html(row.material)}</strong>
							<div class="text-muted">${row.blocks.size} ${__("blocks")} · ${row.periods.size} ${__("periods")}</div>
						</div>
						<div class="material-qty">
							${format_number(row.qty || 0, null, 0)}
							<span>${frappe.utils.escape_html(row.unit)}</span>
						</div>
					</div>
				`;
			}).join("");

		this.wrapper.find('[data-role="material_summary"]').html(rows || `<div class="gant-empty small">${__("No material output.")}</div>`);
	}

	render_selected_output() {
		const tasks = this.get_filtered_tasks();
		const totals = this.calculate_task_totals(tasks);

		const first_coal = tasks.find((task) => {
			const unit = task.mining_unit || this.infer_unit(task);
			return unit === "Tonnes";
		});

		const top_materials = this.get_top_materials(tasks).slice(0, 5).map((row) => {
			return `
				<tr>
					<td>${frappe.utils.escape_html(row.material)}</td>
					<td>${format_number(row.qty || 0, null, 0)}</td>
					<td>${frappe.utils.escape_html(row.unit)}</td>
				</tr>
			`;
		}).join("");

		this.wrapper.find('[data-role="selected_output"]').html(`
			<div class="selected-output-grid">
				<div>
					<div class="gant-label">${__("First Coal")}</div>
					<div class="gant-value small">${first_coal ? frappe.utils.escape_html(`${first_coal.period_label} · ${first_coal.mining_block_code || first_coal.mining_block || ""}`) : __("No coal in filter")}</div>
				</div>
				<div>
					<div class="gant-label">${__("Filtered Tasks")}</div>
					<div class="gant-value small">${format_number(tasks.length || 0, null, 0)}</div>
				</div>
				<div>
					<div class="gant-label">${__("Filtered Blocks")}</div>
					<div class="gant-value small">${format_number(totals.block_count || 0, null, 0)}</div>
				</div>
			</div>

			<table class="mini-table">
				<thead>
					<tr>
						<th>${__("Top Material")}</th>
						<th>${__("Qty")}</th>
						<th>${__("Unit")}</th>
					</tr>
				</thead>
				<tbody>${top_materials || `<tr><td colspan="3" class="text-muted">${__("No output")}</td></tr>`}</tbody>
			</table>
		`);
	}

	render_gant() {
		const tasks = this.get_filtered_tasks();
		const periods = this.get_shown_periods(tasks);
		const container = this.wrapper.find('[data-role="gant"]');

		if (!tasks.length) {
			container.html(`
				<div class="gant-empty">
					${__("No schedule output rows found for the selected filters.")}
				</div>
			`);
			return;
		}

		const period_map = {};
		periods.forEach((period, index) => {
			period_map[cint(period.period_no)] = index + 1;
		});

		const header = periods.map((period) => {
			return `
				<div class="gant-period">
					<div>${frappe.utils.escape_html(period.period_label || "")}</div>
					<div class="text-muted">${frappe.utils.escape_html(period.start || "")}</div>
				</div>
			`;
		}).join("");

		const limited_tasks = tasks.slice(0, 80);

		const rows = limited_tasks.map((task) => {
			const start_col = period_map[cint(task.period_no)] || 1;
			const unit = task.mining_unit || this.infer_unit(task);
			const qty = this.get_task_quantity(task, unit);

			const label = [
				task.sequence_no ? `#${task.sequence_no}` : "",
				task.dependency_group || "",
				task.mining_block_code || task.mining_block || "Grouped",
				task.material_seam || ""
			].filter(Boolean).join(" - ");

			return `
				<div class="gant-row">
					<div class="gant-row-label" title="${frappe.utils.escape_html(label)}">
						${frappe.utils.escape_html(label)}
					</div>
					<div class="gant-row-bars" style="grid-template-columns: repeat(${periods.length || 1}, minmax(115px, 1fr));">
						<div class="gant-bar ${unit === "Tonnes" ? "is-tonnes" : "is-bcm"}" style="grid-column: ${start_col};">
							<div><strong>${format_number(qty || 0, null, 0)} ${frappe.utils.escape_html(unit)}</strong></div>
							<div>${frappe.utils.escape_html(task.period_label || "")}</div>
						</div>
					</div>
				</div>
			`;
		}).join("");

		const note = tasks.length > 80
			? `<div class="text-muted gant-note">${__("Showing first 80 rows. Use filters to narrow the view.")}</div>`
			: "";

		container.html(`
			<div class="gant-scroll">
				<div class="gant-period-header" style="grid-template-columns: 290px repeat(${periods.length || 1}, minmax(115px, 1fr));">
					<div></div>
					${header}
				</div>
				${rows}
			</div>
			${note}
		`);
	}

	render_table() {
		const tasks = this.get_filtered_tasks();

		if (!tasks.length) {
			this.wrapper.find('[data-role="table"]').html("");
			return;
		}

		const rows = tasks.slice(0, 200).map((task) => {
			const unit = task.mining_unit || this.infer_unit(task);
			const qty = this.get_task_quantity(task, unit);

			return `
				<tr>
					<td>${frappe.utils.escape_html(task.period_label || "")}</td>
					<td>${frappe.utils.escape_html(String(task.sequence_no || ""))}</td>
					<td>${frappe.utils.escape_html(task.dependency_group || "")}</td>
					<td>${frappe.utils.escape_html(task.mining_block_code || task.mining_block || "")}</td>
					<td>${frappe.utils.escape_html(task.material_seam || "")}</td>
					<td>${format_number(qty || 0, null, 2)}</td>
					<td>${frappe.utils.escape_html(unit || "")}</td>
					<td>${format_number(task.volume || 0, null, 2)}</td>
					<td>${format_number(task.tonnes || 0, null, 2)}</td>
				</tr>
			`;
		}).join("");

		const note = tasks.length > 200
			? `<div class="text-muted gant-note">${__("Showing first 200 rows. Use filters to narrow the table.")}</div>`
			: "";

		this.wrapper.find('[data-role="table"]').html(`
			<div class="table-wrap">
				<table class="gant-table">
					<thead>
						<tr>
							<th>${__("Period")}</th>
							<th>${__("Seq")}</th>
							<th>${__("Cut")}</th>
							<th>${__("Block")}</th>
							<th>${__("Material")}</th>
							<th>${__("Scheduled Qty")}</th>
							<th>${__("Unit")}</th>
							<th>${__("Volume")}</th>
							<th>${__("Tonnes")}</th>
						</tr>
					</thead>
					<tbody>${rows}</tbody>
				</table>
			</div>
			${note}
		`);
	}

	get_shown_periods(tasks) {
		const all_periods = this.data.periods || [];

		if (this.active_period_no) {
			return all_periods.filter((period) => cint(period.period_no) === cint(this.active_period_no));
		}

		const used = new Set(tasks.map((task) => cint(task.period_no)));

		return all_periods.filter((period) => used.has(cint(period.period_no)));
	}

	get_period_label(period_no) {
		const period = (this.data.periods || []).find((row) => cint(row.period_no) === cint(period_no));
		return period ? period.period_label : `Period ${period_no}`;
	}

	calculate_task_totals(tasks) {
		const blocks = new Set();
		let bcm = 0;
		let tonnes = 0;

		tasks.forEach((task) => {
			const unit = task.mining_unit || this.infer_unit(task);
			const qty = this.get_task_quantity(task, unit);

			if (unit === "Tonnes") {
				tonnes += qty;
			} else {
				bcm += qty;
			}

			if (task.mining_block || task.mining_block_code) {
				blocks.add(task.mining_block || task.mining_block_code);
			}
		});

		return {
			bcm,
			tonnes,
			block_count: blocks.size
		};
	}

	get_top_materials(tasks) {
		const grouped = {};

		tasks.forEach((task) => {
			const material = task.material_seam || __("No Material");
			const unit = task.mining_unit || this.infer_unit(task);
			const key = `${material}||${unit}`;

			if (!grouped[key]) {
				grouped[key] = {
					material,
					unit,
					qty: 0
				};
			}

			grouped[key].qty += this.get_task_quantity(task, unit);
		});

		return Object.values(grouped).sort((a, b) => b.qty - a.qty);
	}

	infer_unit(task) {
		if (task.mining_unit) {
			return task.mining_unit;
		}

		const material = String(task.material_seam || "").toLowerCase();

		if (material.includes("coal") || material.includes("2u") || material.includes("2l") || material.includes("s2u") || material.includes("s2l")) {
			return "Tonnes";
		}

		if (flt(task.tonnes) && !flt(task.volume)) {
			return "Tonnes";
		}

		return "BCM";
	}

	get_task_quantity(task, unit) {
		if (task.scheduled_quantity !== null && task.scheduled_quantity !== undefined && task.scheduled_quantity !== "") {
			return flt(task.scheduled_quantity);
		}

		if (unit === "Tonnes") {
			return flt(task.tonnes);
		}

		return flt(task.volume);
	}

	add_styles() {
		if ($("#mining-schedule-gant-style").length) {
			$("#mining-schedule-gant-style").remove();
		}

		$("head").append(`
			<style id="mining-schedule-gant-style">
				.gant-page {
					padding: 12px;
				}

				.gant-filter-card,
				.gant-card,
				.gant-metric {
					background: var(--card-bg);
					border: 1px solid var(--border-color);
					border-radius: 14px;
					box-shadow: var(--shadow-sm);
				}

				.gant-filter-card {
					padding: 14px;
					display: grid;
					grid-template-columns: minmax(260px, 1.3fr) repeat(3, minmax(150px, 0.8fr)) auto;
					gap: 12px;
					align-items: end;
					margin-bottom: 12px;
				}

				.gant-actions {
					display: flex;
					gap: 8px;
					padding-bottom: 4px;
				}

				.gant-summary {
					display: grid;
					grid-template-columns: 2fr repeat(5, 1fr);
					gap: 10px;
					margin-bottom: 12px;
				}

				.gant-metric {
					padding: 12px;
					min-height: 74px;
				}

				.gant-metric.orange {
					border-color: rgba(211, 84, 0, 0.35);
				}

				.gant-metric.green {
					border-color: rgba(39, 174, 96, 0.35);
				}

				.gant-label {
					font-size: 10px;
					text-transform: uppercase;
					letter-spacing: 0.03em;
					color: var(--text-muted);
					margin-bottom: 4px;
				}

				.gant-value {
					font-size: 18px;
					font-weight: 750;
					line-height: 1.2;
				}

				.gant-value.small {
					font-size: 13px;
				}

				.gant-layout {
					display: grid;
					grid-template-columns: minmax(0, 1fr) 360px;
					gap: 12px;
					align-items: start;
				}

				.gant-card {
					padding: 14px;
					margin-bottom: 12px;
					overflow: hidden;
				}

				.gant-card-header {
					display: flex;
					justify-content: space-between;
					gap: 12px;
					align-items: flex-start;
					margin-bottom: 12px;
				}

				.gant-card h4 {
					margin: 0 0 4px 0;
				}

				.period-grid {
					display: grid;
					grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
					gap: 10px;
				}

				.period-card {
					border: 1px solid var(--border-color);
					border-radius: 12px;
					padding: 10px;
					background: var(--fg-color);
					cursor: pointer;
					transition: transform 0.12s ease, box-shadow 0.12s ease;
				}

				.period-card:hover {
					transform: translateY(-1px);
					box-shadow: var(--shadow-sm);
				}

				.period-card-head {
					display: flex;
					justify-content: space-between;
					gap: 8px;
					align-items: flex-start;
					margin-bottom: 8px;
				}

				.period-title {
					font-weight: 750;
				}

				.period-dates {
					font-size: 11px;
					color: var(--text-muted);
				}

				.period-used {
					font-size: 13px;
					font-weight: 750;
				}

				.capacity-bar {
					height: 8px;
					border-radius: 999px;
					background: var(--control-bg);
					overflow: hidden;
					margin-bottom: 8px;
				}

				.capacity-fill {
					height: 100%;
					border-radius: 999px;
					background: var(--primary);
				}

				.period-stats {
					display: grid;
					grid-template-columns: repeat(4, 1fr);
					gap: 6px;
				}

				.period-stats div {
					border: 1px solid var(--border-color);
					border-radius: 8px;
					padding: 6px;
					background: var(--card-bg);
				}

				.period-stats span {
					display: block;
					font-size: 9px;
					text-transform: uppercase;
					color: var(--text-muted);
				}

				.period-stats b {
					display: block;
					font-size: 12px;
				}

				.material-pill {
					display: flex;
					justify-content: space-between;
					gap: 8px;
					align-items: center;
					border: 1px solid var(--border-color);
					border-radius: 12px;
					padding: 10px;
					background: var(--fg-color);
					margin-bottom: 8px;
				}

				.material-pill.is-tonnes {
					border-color: rgba(39, 174, 96, 0.45);
				}

				.material-pill.is-bcm {
					border-color: rgba(211, 84, 0, 0.45);
				}

				.material-qty {
					font-weight: 750;
					text-align: right;
				}

				.material-qty span {
					display: block;
					font-size: 10px;
					color: var(--text-muted);
					font-weight: 500;
				}

				.selected-output-grid {
					display: grid;
					grid-template-columns: 1fr;
					gap: 10px;
					margin-bottom: 12px;
				}

				.mini-table,
				.gant-table {
					width: 100%;
					border-collapse: collapse;
					font-size: 12px;
				}

				.mini-table th,
				.mini-table td,
				.gant-table th,
				.gant-table td {
					border-bottom: 1px solid var(--border-color);
					padding: 6px;
					text-align: left;
				}

				.table-wrap {
					max-height: 460px;
					overflow: auto;
				}

				.gant-scroll {
					overflow: auto;
					max-height: 560px;
					padding-bottom: 4px;
				}

				.gant-period-header {
					display: grid;
					gap: 6px;
					margin-bottom: 6px;
					min-width: 900px;
					position: sticky;
					top: 0;
					z-index: 2;
					background: var(--card-bg);
					padding-bottom: 6px;
				}

				.gant-period {
					font-size: 11px;
					font-weight: 700;
					text-align: center;
					padding: 7px;
					background: var(--control-bg);
					border-radius: 8px;
					min-height: 44px;
				}

				.gant-row {
					display: grid;
					grid-template-columns: 290px 1fr;
					gap: 6px;
					margin-bottom: 6px;
					min-width: 900px;
				}

				.gant-row-label {
					font-size: 12px;
					padding: 8px;
					background: var(--fg-color);
					border: 1px solid var(--border-color);
					border-radius: 8px;
					white-space: nowrap;
					overflow: hidden;
					text-overflow: ellipsis;
				}

				.gant-row-bars {
					display: grid;
					gap: 6px;
				}

				.gant-bar {
					background: rgba(52, 152, 219, 0.25);
					border: 1px solid rgba(41, 128, 185, 0.8);
					border-radius: 10px;
					padding: 7px;
					font-size: 11px;
					min-height: 46px;
				}

				.gant-bar.is-tonnes {
					background: rgba(46, 204, 113, 0.28);
					border-color: rgba(39, 174, 96, 0.9);
				}

				.gant-bar.is-bcm {
					background: rgba(230, 126, 34, 0.25);
					border-color: rgba(211, 84, 0, 0.85);
				}

				.gant-note {
					margin-top: 8px;
					font-size: 12px;
				}

				.gant-empty {
					padding: 50px 20px;
					text-align: center;
					color: var(--text-muted);
				}

				.gant-empty.small {
					padding: 20px;
				}

				@media (max-width: 1300px) {
					.gant-summary {
						grid-template-columns: repeat(3, 1fr);
					}

					.gant-filter-card {
						grid-template-columns: repeat(2, minmax(180px, 1fr));
					}

					.gant-layout {
						grid-template-columns: 1fr;
					}
				}

				@media (max-width: 700px) {
					.gant-summary,
					.gant-filter-card {
						grid-template-columns: 1fr;
					}
				}
			</style>
		`);
	}
}