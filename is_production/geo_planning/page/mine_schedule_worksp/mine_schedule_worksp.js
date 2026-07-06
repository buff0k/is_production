// Copyright (c) 2026, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

frappe.pages["mine-schedule-worksp"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Mine Schedule Workspace"),
		single_column: true
	});

	const workspace = new MineScheduleWorkspace(page, wrapper);
	workspace.make();
};


class MineScheduleWorkspace {
	constructor(page, wrapper) {
		this.page = page;
		this.wrapper = $(wrapper);
		this.body = $(this.page.body);
		this.data = null;
		this.fields = {};
	}

	make() {
		this.make_layout();
		this.make_filter_fields();
		this.bind_events();
		this.inject_styles();

		this.page.set_primary_action(__("Load Workspace"), () => {
			this.load_workspace();
		});
	}

	make_layout() {
		this.body.empty();

		this.body.append(`
			<div class="mine-schedule-workspace">
				<div class="workspace-intro">
					<div class="workspace-title">${__("Mine Schedule Workspace")}</div>
					<div class="workspace-subtitle">
						${__("Spreadsheet-style mine schedule volume profile and allocation detail.")}
					</div>
				</div>

				<div class="workspace-filter-card">
					<div class="filter-title">${__("Filters")}</div>

					<div class="workspace-filter-grid">
						<div data-filter-field="schedule_scenario"></div>
						<div data-filter-field="engine_run"></div>
						<div data-filter-field="from_date"></div>
						<div data-filter-field="to_date"></div>
						<div data-filter-field="material_seam"></div>
						<div data-filter-field="mining_block_code"></div>
					</div>

					<div class="workspace-filter-actions">
						<button class="btn btn-primary" data-action="load_workspace">
							${__("Load Workspace")}
						</button>
						<button class="btn btn-default" data-action="clear_filters">
							${__("Clear Filters")}
						</button>
					</div>
				</div>

				<div class="workspace-kpis" data-section="kpis"></div>

				<div class="workspace-tabs">
					<button class="workspace-tab active" data-tab="spreadsheet_profile">
						${__("Spreadsheet Profile")}
					</button>
					<button class="workspace-tab" data-tab="charts">
						${__("Charts")}
					</button>
					<button class="workspace-tab" data-tab="schedule_detail">
						${__("Schedule Detail")}
					</button>
					<button class="workspace-tab" data-tab="material_summary">
						${__("Material Summary")}
					</button>
				</div>

				<div class="workspace-tab-content active" data-content="spreadsheet_profile">
					<div class="workspace-section">
						<div class="section-heading">
							<div>
								<h3>${__("Spreadsheet Profile")}</h3>
								<p>${__("Dates across the top, moved and remaining volumes down the side.")}</p>
							</div>
							<div>
								<button class="btn btn-sm btn-default" data-action="export_spreadsheet_profile">
									${__("Export Profile CSV")}
								</button>
							</div>
						</div>

						<div class="table-wrap profile-wrap" data-table="spreadsheet_profile"></div>
					</div>
				</div>

				<div class="workspace-tab-content" data-content="charts">
					<div class="workspace-section">
						<div class="section-heading">
							<div>
								<h3>${__("Charts")}</h3>
								<p>${__("Visual view of daily material movement, cumulative BCM and coal tonnes.")}</p>
							</div>
						</div>

						<div class="chart-grid">
							<div class="chart-card">
								<h4>${__("Daily Material BCM")}</h4>
								<div data-chart="daily_material_bcm"></div>
							</div>
							<div class="chart-card">
								<h4>${__("Cumulative BCM")}</h4>
								<div data-chart="cumulative_bcm"></div>
							</div>
							<div class="chart-card">
								<h4>${__("Coal Tonnes")}</h4>
								<div data-chart="coal_tonnes"></div>
							</div>
						</div>

						<div class="table-wrap" data-table="daily_profile"></div>
					</div>
				</div>

				<div class="workspace-tab-content" data-content="schedule_detail">
					<div class="workspace-section">
						<div class="section-heading">
							<div>
								<h3>${__("Schedule Detail")}</h3>
								<p>${__("Line-by-line allocation detail behind the profile.")}</p>
							</div>
							<div>
								<button class="btn btn-sm btn-default" data-action="export_detail">
									${__("Export Detail CSV")}
								</button>
							</div>
						</div>

						<div class="table-wrap" data-table="schedule_detail"></div>
					</div>
				</div>

				<div class="workspace-tab-content" data-content="material_summary">
					<div class="workspace-section">
						<div class="section-heading">
							<div>
								<h3>${__("Material Summary")}</h3>
								<p>${__("Total scheduled quantities grouped by material and bucket.")}</p>
							</div>
						</div>

						<div class="table-wrap" data-table="material_summary"></div>
					</div>
				</div>

				<div class="workspace-empty" data-section="empty">
					${__("Select a Schedule Scenario and click Load Workspace.")}
				</div>
			</div>
		`);
	}

	make_filter_fields() {
		this.fields.schedule_scenario = frappe.ui.form.make_control({
			parent: this.body.find('[data-filter-field="schedule_scenario"]'),
			df: {
				fieldtype: "Link",
				fieldname: "schedule_scenario",
				label: __("Schedule Scenario"),
				options: "Mining Schedule Scenario",
				reqd: 1,
				change: () => {
					this.load_engine_runs();
				}
			},
			render_input: true
		});

		this.fields.engine_run = frappe.ui.form.make_control({
			parent: this.body.find('[data-filter-field="engine_run"]'),
			df: {
				fieldtype: "Link",
				fieldname: "engine_run",
				label: __("Engine Run"),
				options: "Mining Schedule Engine Run",
				get_query: () => {
					const scenario = this.get_field_value("schedule_scenario");

					if (!scenario) {
						return {};
					}

					return {
						filters: {
							schedule_scenario: scenario
						}
					};
				}
			},
			render_input: true
		});

		this.fields.from_date = frappe.ui.form.make_control({
			parent: this.body.find('[data-filter-field="from_date"]'),
			df: {
				fieldtype: "Date",
				fieldname: "from_date",
				label: __("From Date")
			},
			render_input: true
		});

		this.fields.to_date = frappe.ui.form.make_control({
			parent: this.body.find('[data-filter-field="to_date"]'),
			df: {
				fieldtype: "Date",
				fieldname: "to_date",
				label: __("To Date")
			},
			render_input: true
		});

		this.fields.material_seam = frappe.ui.form.make_control({
			parent: this.body.find('[data-filter-field="material_seam"]'),
			df: {
				fieldtype: "Data",
				fieldname: "material_seam",
				label: __("Material / Seam")
			},
			render_input: true
		});

		this.fields.mining_block_code = frappe.ui.form.make_control({
			parent: this.body.find('[data-filter-field="mining_block_code"]'),
			df: {
				fieldtype: "Data",
				fieldname: "mining_block_code",
				label: __("Block")
			},
			render_input: true
		});
	}

	bind_events() {
		this.body.on("click", ".workspace-tab", (event) => {
			const tab = $(event.currentTarget).attr("data-tab");
			this.activate_tab(tab);
		});

		this.body.on("click", '[data-action="load_workspace"]', () => {
			this.load_workspace();
		});

		this.body.on("click", '[data-action="clear_filters"]', () => {
			this.clear_filters();
		});

		this.body.on("click", '[data-action="export_spreadsheet_profile"]', () => {
			this.export_spreadsheet_profile();
		});

		this.body.on("click", '[data-action="export_detail"]', () => {
			this.export_csv("schedule_detail");
		});
	}

	get_field_value(fieldname) {
		if (!this.fields[fieldname]) return "";
		return this.fields[fieldname].get_value();
	}

	set_field_value(fieldname, value) {
		if (!this.fields[fieldname]) return;
		this.fields[fieldname].set_value(value || "");
	}

	clear_filters() {
		this.set_field_value("schedule_scenario", "");
		this.set_field_value("engine_run", "");
		this.set_field_value("from_date", "");
		this.set_field_value("to_date", "");
		this.set_field_value("material_seam", "");
		this.set_field_value("mining_block_code", "");
		this.data = null;
		this.render_empty();
	}

	get_filter_values() {
		return {
			schedule_scenario: this.get_field_value("schedule_scenario"),
			engine_run: this.get_field_value("engine_run"),
			from_date: this.get_field_value("from_date"),
			to_date: this.get_field_value("to_date"),
			material_seam: this.get_field_value("material_seam"),
			mining_block_code: this.get_field_value("mining_block_code")
		};
	}

	load_engine_runs() {
		const scenario = this.get_field_value("schedule_scenario");

		if (!scenario) {
			this.set_field_value("engine_run", "");
			return;
		}

		frappe.call({
			method: "is_production.geo_planning.services.mine_schedule_workspace_service.get_engine_run_options",
			args: {
				schedule_scenario: scenario
			},
			callback: (r) => {
				const rows = r.message || [];

				if (rows.length) {
					this.set_field_value("engine_run", rows[0].name);
				}
			}
		});
	}

	load_workspace() {
		const filters = this.get_filter_values();

		if (!filters.schedule_scenario) {
			frappe.msgprint(__("Please select a Schedule Scenario first."));
			return;
		}

		frappe.call({
			method: "is_production.geo_planning.services.mine_schedule_workspace_service.get_workspace_data",
			args: filters,
			freeze: true,
			freeze_message: __("Loading mine schedule workspace..."),
			callback: (r) => {
				if (!r.exc && r.message) {
					this.data = r.message;
					this.render();
				}
			}
		});
	}

	render() {
		if (!this.data) {
			this.render_empty();
			return;
		}

		this.body.find('[data-section="empty"]').hide();

		this.render_kpis();
		this.render_spreadsheet_profile();
		this.render_daily_profile();
		this.render_schedule_detail();
		this.render_material_summary();
		this.render_charts();
	}

	render_empty() {
		this.body.find('[data-section="kpis"]').empty();
		this.body.find('[data-table="spreadsheet_profile"]').empty();
		this.body.find('[data-table="daily_profile"]').empty();
		this.body.find('[data-table="schedule_detail"]').empty();
		this.body.find('[data-table="material_summary"]').empty();
		this.body.find('[data-chart]').empty();
		this.body.find('[data-section="empty"]').show();
	}

	render_kpis() {
		const kpis = this.data.kpis || {};

		const cards = [
			{ label: __("Scheduled BCM"), value: this.fmt(kpis.total_scheduled_bcm), indicator: "blue" },
			{ label: __("Coal Tonnes"), value: this.fmt(kpis.total_coal_tonnes), indicator: "green" },
			{ label: __("Finish Date"), value: kpis.finish_date || "-", indicator: "purple" },
			{ label: __("Allocations"), value: this.fmt(kpis.allocation_rows), indicator: "blue" },
			{ label: __("Partial"), value: this.fmt(kpis.partial_allocations), indicator: kpis.partial_allocations ? "orange" : "green" },
			{ label: __("Warnings"), value: this.fmt(kpis.warnings), indicator: kpis.warnings ? "orange" : "green" },
			{ label: __("Errors"), value: this.fmt(kpis.errors), indicator: kpis.errors ? "red" : "green" }
		];

		const html = cards.map((card) => `
			<div class="workspace-kpi-card ${card.indicator}">
				<div class="kpi-label">${frappe.utils.escape_html(card.label)}</div>
				<div class="kpi-value">${frappe.utils.escape_html(String(card.value))}</div>
			</div>
		`).join("");

		this.body.find('[data-section="kpis"]').html(html);
	}

	render_spreadsheet_profile() {
		const profile = this.data.spreadsheet_profile || {};
		const dates = profile.date_columns || [];
		const rows = profile.rows || [];

		if (!dates.length || !rows.length) {
			this.body.find('[data-table="spreadsheet_profile"]').html(this.empty_message(__("No spreadsheet profile rows found.")));
			return;
		}

		const html = `
			<table class="table table-bordered table-sm workspace-table spreadsheet-profile-table">
				<thead>
					<tr>
						<th class="sticky-metric">${__("Material / Metric")}</th>
						${dates.map((date) => `<th class="text-right">${this.esc(date)}</th>`).join("")}
					</tr>
				</thead>
				<tbody>
					${rows.map((row) => `
						<tr class="${this.profile_row_class(row)}">
							<td class="sticky-metric"><b>${this.esc(row.label)}</b></td>
							${dates.map((date) => `
								<td class="text-right">${this.format_profile_value(row.values ? row.values[date] : 0)}</td>
							`).join("")}
						</tr>
					`).join("")}
				</tbody>
			</table>
		`;

		this.body.find('[data-table="spreadsheet_profile"]').html(html);
	}

	render_daily_profile() {
		const rows = this.data.volume_profile || [];

		if (!rows.length) {
			this.body.find('[data-table="daily_profile"]').html(this.empty_message(__("No daily profile rows found.")));
			return;
		}

		const html = `
			<table class="table table-bordered table-sm workspace-table">
				<thead>
					<tr>
						<th>${__("Date")}</th>
						<th>${__("Day")}</th>
						<th class="text-right">${__("Topsoil BCM")}</th>
						<th class="text-right">${__("Softs BCM")}</th>
						<th class="text-right">${__("Hards BCM")}</th>
						<th class="text-right">${__("Parting BCM")}</th>
						<th class="text-right">${__("Coal BCM")}</th>
						<th class="text-right">${__("Coal Tonnes")}</th>
						<th class="text-right">${__("Other BCM")}</th>
						<th class="text-right">${__("Total BCM")}</th>
						<th class="text-right">${__("Cumulative BCM")}</th>
						<th class="text-right">${__("Cumulative Coal Tonnes")}</th>
					</tr>
				</thead>
				<tbody>
					${rows.map((row) => `
						<tr>
							<td>${this.esc(row.allocation_date)}</td>
							<td>${this.esc(row.day_type)}</td>
							<td class="text-right">${this.fmt(row.topsoil_bcm)}</td>
							<td class="text-right">${this.fmt(row.softs_bcm)}</td>
							<td class="text-right">${this.fmt(row.hards_bcm)}</td>
							<td class="text-right">${this.fmt(row.parting_bcm)}</td>
							<td class="text-right">${this.fmt(row.coal_bcm)}</td>
							<td class="text-right">${this.fmt(row.coal_tonnes)}</td>
							<td class="text-right">${this.fmt(row.other_bcm)}</td>
							<td class="text-right"><b>${this.fmt(row.scheduled_bcm)}</b></td>
							<td class="text-right">${this.fmt(row.cumulative_bcm)}</td>
							<td class="text-right">${this.fmt(row.cumulative_coal_tonnes)}</td>
						</tr>
					`).join("")}
				</tbody>
			</table>
		`;

		this.body.find('[data-table="daily_profile"]').html(html);
	}

	render_schedule_detail() {
		const rows = this.data.schedule_detail || [];

		if (!rows.length) {
			this.body.find('[data-table="schedule_detail"]').html(this.empty_message(__("No schedule detail rows found.")));
			return;
		}

		const html = `
			<table class="table table-bordered table-sm workspace-table">
				<thead>
					<tr>
						<th>${__("Date")}</th>
						<th>${__("Block")}</th>
						<th>${__("Material")}</th>
						<th>${__("Bucket")}</th>
						<th class="text-right">${__("Opening")}</th>
						<th class="text-right">${__("Scheduled")}</th>
						<th class="text-right">${__("Closing")}</th>
						<th>${__("Unit")}</th>
						<th>${__("Partial")}</th>
						<th class="text-right">${__("Hours")}</th>
						<th class="text-right">${__("Capacity %")}</th>
						<th>${__("Task Status")}</th>
						<th>${__("Allocation Status")}</th>
					</tr>
				</thead>
				<tbody>
					${rows.map((row) => `
						<tr>
							<td>${this.esc(row.allocation_date)}</td>
							<td>${this.esc(row.mining_block_code)}</td>
							<td>${this.esc(row.material_seam)}</td>
							<td>${this.esc(row.material_bucket)}</td>
							<td class="text-right">${this.fmt(row.opening_quantity)}</td>
							<td class="text-right"><b>${this.fmt(row.scheduled_quantity)}</b></td>
							<td class="text-right">${this.fmt(row.closing_quantity)}</td>
							<td>${this.esc(row.unit)}</td>
							<td>${row.is_partial ? __("Yes") : __("No")}</td>
							<td class="text-right">${this.fmt(row.required_hours)}</td>
							<td class="text-right">${this.fmt(row.capacity_used_percent)}</td>
							<td>${this.status_badge(row.task_status)}</td>
							<td>${this.esc(row.allocation_status)}</td>
						</tr>
					`).join("")}
				</tbody>
			</table>
		`;

		this.body.find('[data-table="schedule_detail"]').html(html);
	}

	render_material_summary() {
		const rows = this.data.material_summary || [];

		if (!rows.length) {
			this.body.find('[data-table="material_summary"]').html(this.empty_message(__("No material summary rows found.")));
			return;
		}

		const html = `
			<table class="table table-bordered table-sm workspace-table">
				<thead>
					<tr>
						<th>${__("Material / Seam")}</th>
						<th>${__("Bucket")}</th>
						<th class="text-right">${__("Scheduled BCM")}</th>
						<th class="text-right">${__("Scheduled Tonnes")}</th>
						<th class="text-right">${__("Allocations")}</th>
					</tr>
				</thead>
				<tbody>
					${rows.map((row) => `
						<tr>
							<td>${this.esc(row.material_seam)}</td>
							<td>${this.esc(row.material_bucket)}</td>
							<td class="text-right">${this.fmt(row.scheduled_bcm)}</td>
							<td class="text-right">${this.fmt(row.scheduled_tonnes)}</td>
							<td class="text-right">${this.fmt(row.allocation_rows)}</td>
						</tr>
					`).join("")}
				</tbody>
			</table>
		`;

		this.body.find('[data-table="material_summary"]').html(html);
	}

	render_charts() {
		if (!this.data.chart_data) return;

		this.render_chart('[data-chart="daily_material_bcm"]', this.data.chart_data.daily_material_bcm, "bar");
		this.render_chart('[data-chart="cumulative_bcm"]', this.data.chart_data.cumulative_bcm, "line");
		this.render_chart('[data-chart="coal_tonnes"]', this.data.chart_data.coal_tonnes, "bar");
	}

	render_chart(selector, chart_data, type) {
		const target = this.body.find(selector);
		target.empty();

		if (!chart_data || !chart_data.labels || !chart_data.labels.length) {
			target.html(this.empty_message(__("No chart data.")));
			return;
		}

		new frappe.Chart(target[0], {
			data: chart_data,
			type: type,
			height: 240,
			axisOptions: {
				xIsSeries: true
			},
			barOptions: {
				stacked: type === "bar"
			}
		});
	}

	activate_tab(tab) {
		this.body.find(".workspace-tab").removeClass("active");
		this.body.find(`.workspace-tab[data-tab="${tab}"]`).addClass("active");

		this.body.find(".workspace-tab-content").removeClass("active");
		this.body.find(`.workspace-tab-content[data-content="${tab}"]`).addClass("active");
	}

	export_spreadsheet_profile() {
		if (!this.data || !this.data.spreadsheet_profile) {
			frappe.msgprint(__("Please load the workspace first."));
			return;
		}

		const profile = this.data.spreadsheet_profile;
		const dates = profile.date_columns || [];
		const rows = profile.rows || [];

		if (!dates.length || !rows.length) {
			frappe.msgprint(__("No profile rows to export."));
			return;
		}

		const csv_rows = [];

		csv_rows.push(["Material / Metric"].concat(dates));

		rows.forEach((row) => {
			csv_rows.push(
				[row.label].concat(
					dates.map((date) => row.values && row.values[date] ? row.values[date] : 0)
				)
			);
		});

		const csv = csv_rows.map((row) => {
			return row.map((value) => {
				const text = String(value === null || value === undefined ? "" : value).replace(/"/g, '""');
				return `"${text}"`;
			}).join(",");
		}).join("\n");

		this.download_csv(csv, `spreadsheet_profile_${frappe.datetime.now_date()}.csv`);
	}

	export_csv(dataset) {
		if (!this.data) {
			frappe.msgprint(__("Please load the workspace first."));
			return;
		}

		const rows = this.data[dataset] || [];

		if (!rows.length) {
			frappe.msgprint(__("No rows to export."));
			return;
		}

		const columns = Object.keys(rows[0] || {});
		const csv_rows = [columns].concat(rows.map((row) => columns.map((column) => row[column])));

		const csv = csv_rows.map((row) => {
			return row.map((value) => {
				const text = String(value === null || value === undefined ? "" : value).replace(/"/g, '""');
				return `"${text}"`;
			}).join(",");
		}).join("\n");

		this.download_csv(csv, `${dataset}_${frappe.datetime.now_date()}.csv`);
	}

	download_csv(csv, filename) {
		const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
		const link = document.createElement("a");

		link.href = URL.createObjectURL(blob);
		link.download = filename;
		link.style.display = "none";

		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
	}

	status_badge(status) {
		const clean_status = status || "-";
		let color = "gray";

		if (clean_status === "Complete") color = "green";
		if (clean_status === "In Progress") color = "blue";
		if (clean_status === "Blocked") color = "red";
		if (clean_status === "Pending") color = "orange";

		return `<span class="workspace-badge ${color}">${this.esc(clean_status)}</span>`;
	}

	profile_row_class(row) {
		if (!row) return "";

		if (row.row_type === "summary") return "profile-summary-row";
		if (row.row_type === "remaining") return "profile-remaining-row";
		if (row.row_type === "moved") return "profile-moved-row";

		return "";
	}

	format_profile_value(value) {
		const number = flt(value || 0);

		if (!number) {
			return "";
		}

		return format_number(number, null, 0);
	}

	empty_message(message) {
		return `<div class="workspace-empty-small">${frappe.utils.escape_html(message)}</div>`;
	}

	fmt(value) {
		const number = flt(value || 0);

		if (!number) {
			return "0";
		}

		return format_number(number, null, 2);
	}

	esc(value) {
		return frappe.utils.escape_html(String(value || ""));
	}

	inject_styles() {
		if ($("#mine-schedule-workspace-style").length) {
			return;
		}

		$("head").append(`
			<style id="mine-schedule-workspace-style">
				.mine-schedule-workspace {
					padding: 8px 0 30px 0;
				}

				.workspace-intro,
				.workspace-filter-card {
					background: var(--card-bg);
					border: 1px solid var(--border-color);
					border-radius: 12px;
					padding: 16px 18px;
					margin-bottom: 14px;
				}

				.workspace-title {
					font-size: 20px;
					font-weight: 700;
					color: var(--text-color);
				}

				.workspace-subtitle {
					margin-top: 4px;
					color: var(--text-muted);
				}

				.filter-title {
					font-size: 15px;
					font-weight: 700;
					margin-bottom: 10px;
				}

				.workspace-filter-grid {
					display: grid;
					grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
					gap: 12px;
				}

				.workspace-filter-actions {
					margin-top: 12px;
					display: flex;
					gap: 8px;
				}

				.workspace-kpis {
					display: grid;
					grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
					gap: 10px;
					margin-bottom: 14px;
				}

				.workspace-kpi-card {
					border: 1px solid var(--border-color);
					border-radius: 12px;
					padding: 12px;
					background: var(--card-bg);
					border-left-width: 5px;
				}

				.workspace-kpi-card.blue { border-left-color: #2490ef; }
				.workspace-kpi-card.green { border-left-color: #2f9e44; }
				.workspace-kpi-card.orange { border-left-color: #f08c00; }
				.workspace-kpi-card.red { border-left-color: #e03131; }
				.workspace-kpi-card.purple { border-left-color: #7048e8; }

				.kpi-label {
					font-size: 12px;
					color: var(--text-muted);
					margin-bottom: 4px;
				}

				.kpi-value {
					font-size: 20px;
					font-weight: 700;
					color: var(--text-color);
				}

				.workspace-tabs {
					display: flex;
					gap: 8px;
					margin-bottom: 12px;
					border-bottom: 1px solid var(--border-color);
				}

				.workspace-tab {
					border: 0;
					background: transparent;
					padding: 10px 12px;
					font-weight: 600;
					color: var(--text-muted);
					border-bottom: 3px solid transparent;
				}

				.workspace-tab.active {
					color: var(--text-color);
					border-bottom-color: var(--primary);
				}

				.workspace-tab-content {
					display: none;
				}

				.workspace-tab-content.active {
					display: block;
				}

				.workspace-section {
					background: var(--card-bg);
					border: 1px solid var(--border-color);
					border-radius: 12px;
					padding: 14px;
				}

				.section-heading {
					display: flex;
					align-items: flex-start;
					justify-content: space-between;
					gap: 12px;
					margin-bottom: 12px;
				}

				.section-heading h3 {
					margin: 0;
					font-size: 18px;
					font-weight: 700;
				}

				.section-heading p {
					margin: 4px 0 0 0;
					color: var(--text-muted);
				}

				.chart-grid {
					display: grid;
					grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
					gap: 12px;
					margin-bottom: 14px;
				}

				.chart-card {
					border: 1px solid var(--border-color);
					border-radius: 10px;
					padding: 12px;
					background: var(--fg-color);
				}

				.chart-card h4 {
					margin: 0 0 8px 0;
					font-size: 14px;
					font-weight: 700;
				}

				.table-wrap {
					overflow: auto;
					max-height: 640px;
					border: 1px solid var(--border-color);
					border-radius: 10px;
				}

				.profile-wrap {
					max-height: 720px;
				}

				.workspace-table {
					margin: 0;
					white-space: nowrap;
				}

				.workspace-table thead th {
					position: sticky;
					top: 0;
					background: var(--card-bg);
					z-index: 3;
					font-weight: 700;
					color: var(--text-color);
				}

				.spreadsheet-profile-table td,
				.spreadsheet-profile-table th {
					min-width: 105px;
				}

				.spreadsheet-profile-table .sticky-metric {
					position: sticky;
					left: 0;
					z-index: 4;
					background: var(--card-bg);
					min-width: 230px;
					max-width: 260px;
					white-space: normal;
				}

				.spreadsheet-profile-table tbody .sticky-metric {
					z-index: 2;
				}

				.profile-summary-row td {
					background: #e7f5ff;
					font-weight: 700;
				}

				.profile-moved-row td {
					background: #f8f9fa;
				}

				.profile-remaining-row td {
					background: #fff9db;
				}

				.workspace-empty {
					background: var(--card-bg);
					border: 1px dashed var(--border-color);
					border-radius: 12px;
					padding: 28px;
					text-align: center;
					color: var(--text-muted);
					margin-top: 14px;
				}

				.workspace-empty-small {
					padding: 18px;
					color: var(--text-muted);
					text-align: center;
				}

				.workspace-badge {
					display: inline-block;
					padding: 3px 8px;
					border-radius: 999px;
					font-size: 12px;
					font-weight: 600;
				}

				.workspace-badge.green {
					background: #d3f9d8;
					color: #2b8a3e;
				}

				.workspace-badge.blue {
					background: #d0ebff;
					color: #1c7ed6;
				}

				.workspace-badge.orange {
					background: #fff3bf;
					color: #e67700;
				}

				.workspace-badge.red {
					background: #ffe3e3;
					color: #c92a2a;
				}

				.workspace-badge.gray {
					background: #f1f3f5;
					color: #495057;
				}
			</style>
		`);
	}
}