frappe.pages["mining-schedule-view"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Mining Schedule Viewer"),
		single_column: true
	});

	new MiningScheduleView(page);
};


class MiningScheduleView {
	constructor(page) {
		this.page = page;
		this.wrapper = $(page.body);

		this.data = null;
		this.active_period_no = null;

		this.svg = null;
		this.viewport = null;
		this.view_box = null;

		this.zoom_level = 1;
		this.rotation_degrees = 0;
		this.pan_x = 0;
		this.pan_y = 0;
		this.is_dragging = false;
		this.drag_start = null;

		this.make();
	}

	make() {
		this.make_layout();
		this.make_filters();
		this.bind_events();

		const route_options = frappe.get_route_options() || {};

		if (route_options.scenario) {
			this.scenario_control.set_value(route_options.scenario);
			this.load_scenario();
		}
	}

	make_layout() {
		this.wrapper.empty();

		this.wrapper.append(`
			<div class="schedule-viewer">
				<div class="schedule-filter-card">
					<div class="schedule-filter-title">
						<strong>${__("Schedule Scenario")}</strong>
						<span class="text-muted">${__("Load a generated scenario to review period-by-period mining output.")}</span>
					</div>
					<div data-field="scenario"></div>
				</div>

				<div class="schedule-summary-row">
					<div class="schedule-card">
						<div class="schedule-label">${__("Periods")}</div>
						<div class="schedule-value" data-total="total_periods">0</div>
					</div>
					<div class="schedule-card">
						<div class="schedule-label">${__("Blocks")}</div>
						<div class="schedule-value" data-total="total_blocks">0</div>
					</div>
					<div class="schedule-card">
						<div class="schedule-label">${__("Volume")}</div>
						<div class="schedule-value" data-total="total_volume">0.00</div>
					</div>
					<div class="schedule-card">
						<div class="schedule-label">${__("Tonnes")}</div>
						<div class="schedule-value" data-total="total_tonnes">0.00</div>
					</div>
					<div class="schedule-card">
						<div class="schedule-label">${__("Avg Density")}</div>
						<div class="schedule-value" data-total="average_density">0.000</div>
					</div>
					<div class="schedule-card">
						<div class="schedule-label">${__("Avg CV")}</div>
						<div class="schedule-value" data-total="average_cv">0.00</div>
					</div>
				</div>

				<div class="schedule-period-strip" data-role="period_strip"></div>

				<div class="schedule-main-row">
					<div class="schedule-map-card">
						<div class="schedule-toolbar">
							<div>
								<strong>${__("Schedule Map")}</strong>
								<span class="text-muted schedule-subtitle" data-role="status">${__("Select a scenario.")}</span>
							</div>
							<div class="schedule-map-actions">
								<button class="btn btn-xs btn-default" data-action="zoom_in">${__("Zoom +")}</button>
								<button class="btn btn-xs btn-default" data-action="zoom_out">${__("Zoom -")}</button>
								<button class="btn btn-xs btn-default" data-action="rotate_left">${__("Rotate Left")}</button>
								<button class="btn btn-xs btn-default" data-action="rotate_right">${__("Rotate Right")}</button>
								<button class="btn btn-xs btn-default" data-action="reset_view">${__("Reset View")}</button>
							</div>
						</div>

						<div class="schedule-map-wrap">
							<div class="schedule-compass" data-role="compass">
								<div class="schedule-compass-arrow" data-role="compass_arrow">▲</div>
								<div class="schedule-compass-n">N</div>
								<div class="schedule-compass-s">S</div>
								<div class="schedule-compass-e">E</div>
								<div class="schedule-compass-w">W</div>
							</div>
							<div class="schedule-map" data-role="map"></div>
						</div>
					</div>

					<div class="schedule-side-card">
						<div data-role="period_summary"></div>
						<hr>
						<div data-role="block_summary"></div>
						<hr>
						<div data-role="material_summary"></div>
					</div>
				</div>
			</div>
		`);

		this.add_styles();
		this.render_empty_state();
	}

	make_filters() {
		this.scenario_control = frappe.ui.form.make_control({
			parent: this.wrapper.find('[data-field="scenario"]'),
			df: {
				fieldtype: "Link",
				fieldname: "scenario",
				label: __("Mining Schedule Scenario"),
				options: "Mining Schedule Scenario",
				reqd: 1,
				change: () => {
					this.load_scenario();
				}
			},
			render_input: true
		});
	}

	bind_events() {
		this.page.set_primary_action(__("Load Scenario"), () => {
			this.load_scenario();
		});

		this.wrapper.find('[data-action="zoom_in"]').on("click", () => {
			this.zoom(1.2);
		});

		this.wrapper.find('[data-action="zoom_out"]').on("click", () => {
			this.zoom(1 / 1.2);
		});

		this.wrapper.find('[data-action="rotate_left"]').on("click", () => {
			this.rotate(-10);
		});

		this.wrapper.find('[data-action="rotate_right"]').on("click", () => {
			this.rotate(10);
		});

		this.wrapper.find('[data-action="reset_view"]').on("click", () => {
			this.reset_view_transform();
		});
	}

	add_styles() {
		if ($("#mining-schedule-view-style").length) {
			$("#mining-schedule-view-style").remove();
		}

		$("head").append(`
			<style id="mining-schedule-view-style">
				.schedule-viewer {
					padding: 12px;
				}

				.schedule-filter-card,
				.schedule-card,
				.schedule-map-card,
				.schedule-side-card {
					background: var(--card-bg);
					border: 1px solid var(--border-color);
					border-radius: 12px;
					box-shadow: var(--shadow-sm);
				}

				.schedule-filter-card {
					padding: 14px;
					margin-bottom: 12px;
				}

				.schedule-filter-title {
					display: flex;
					gap: 10px;
					align-items: baseline;
					margin-bottom: 12px;
				}

				.schedule-summary-row {
					display: grid;
					grid-template-columns: repeat(6, minmax(120px, 1fr));
					gap: 12px;
					margin-bottom: 12px;
				}

				.schedule-card {
					padding: 12px;
				}

				.schedule-label {
					font-size: 11px;
					text-transform: uppercase;
					color: var(--text-muted);
					margin-bottom: 4px;
				}

				.schedule-value {
					font-size: 20px;
					font-weight: 700;
				}

				.schedule-period-strip {
					display: flex;
					gap: 8px;
					flex-wrap: wrap;
					margin-bottom: 12px;
				}

				.schedule-period-button.active {
					background: var(--primary);
					border-color: var(--primary);
					color: #fff;
				}

				.schedule-main-row {
					display: grid;
					grid-template-columns: minmax(0, 1fr) 430px;
					gap: 12px;
				}

				.schedule-toolbar {
					display: flex;
					align-items: center;
					justify-content: space-between;
					gap: 12px;
					padding: 12px;
					border-bottom: 1px solid var(--border-color);
				}

				.schedule-map-actions {
					display: flex;
					flex-wrap: wrap;
					gap: 6px;
					justify-content: flex-end;
				}

				.schedule-subtitle {
					margin-left: 8px;
					font-size: 12px;
				}

				.schedule-map-wrap {
					position: relative;
				}

				.schedule-map {
					min-height: 620px;
					overflow: hidden;
					cursor: grab;
					background:
						linear-gradient(90deg, rgba(128, 128, 128, 0.08) 1px, transparent 1px),
						linear-gradient(rgba(128, 128, 128, 0.08) 1px, transparent 1px);
					background-size: 28px 28px;
				}

				.schedule-map.is-dragging {
					cursor: grabbing;
				}

				.schedule-map svg {
					display: block;
					width: 100%;
					height: 620px;
				}

				.schedule-block {
					fill: rgba(160, 160, 160, 0.18);
					stroke: rgba(120, 120, 120, 0.9);
					stroke-width: 1;
					cursor: pointer;
				}

				.schedule-block:hover {
					stroke-width: 2;
				}

				.schedule-block.is-active-period {
					fill: rgba(46, 204, 113, 0.55);
					stroke: rgba(39, 174, 96, 1);
					stroke-width: 2;
				}

				.schedule-block.is-before-period {
					fill: rgba(90, 90, 90, 0.24);
					stroke: rgba(90, 90, 90, 0.75);
				}

				.schedule-block.is-after-period {
					fill: rgba(80, 140, 220, 0.14);
					stroke: rgba(80, 140, 220, 0.65);
				}

				.schedule-label-text {
					font-size: 10px;
					fill: var(--text-color);
					pointer-events: none;
					text-anchor: middle;
					dominant-baseline: central;
				}

				.schedule-sequence-badge {
					fill: rgba(39, 174, 96, 0.95);
					stroke: #fff;
					stroke-width: 1;
					pointer-events: none;
				}

				.schedule-sequence-text {
					fill: #fff;
					font-size: 11px;
					font-weight: 700;
					pointer-events: none;
					text-anchor: middle;
					dominant-baseline: central;
				}

				.schedule-side-card {
					padding: 12px;
					max-height: 700px;
					overflow: auto;
				}

				.schedule-section-title {
					font-weight: 700;
					margin-bottom: 8px;
				}

				.schedule-metric-grid {
					display: grid;
					grid-template-columns: repeat(2, minmax(120px, 1fr));
					gap: 8px;
				}

				.schedule-metric {
					border: 1px solid var(--border-color);
					border-radius: 8px;
					padding: 8px;
					background: var(--fg-color);
				}

				.schedule-metric-label {
					font-size: 10px;
					text-transform: uppercase;
					color: var(--text-muted);
				}

				.schedule-metric-value {
					font-weight: 700;
				}

				.schedule-table {
					width: 100%;
					border-collapse: collapse;
					font-size: 12px;
				}

				.schedule-table th,
				.schedule-table td {
					border-bottom: 1px solid var(--border-color);
					padding: 5px;
					text-align: left;
				}

				.schedule-table th {
					color: var(--text-muted);
					font-weight: 600;
				}

				.schedule-empty {
					padding: 80px 20px;
					text-align: center;
					color: var(--text-muted);
				}

				.schedule-compass {
					position: absolute;
					top: 14px;
					right: 14px;
					z-index: 5;
					width: 82px;
					height: 82px;
					border-radius: 50%;
					background: rgba(255, 255, 255, 0.9);
					border: 1px solid var(--border-color);
					box-shadow: var(--shadow-sm);
					color: #111;
					font-size: 11px;
					font-weight: 700;
					user-select: none;
				}

				.schedule-compass-arrow {
					position: absolute;
					left: 50%;
					top: 8px;
					transform-origin: 50% 33px;
					transform: translateX(-50%);
					font-size: 24px;
					color: #d35400;
				}

				.schedule-compass-n,
				.schedule-compass-s,
				.schedule-compass-e,
				.schedule-compass-w {
					position: absolute;
				}

				.schedule-compass-n {
					top: 3px;
					left: 50%;
					transform: translateX(-50%);
				}

				.schedule-compass-s {
					bottom: 3px;
					left: 50%;
					transform: translateX(-50%);
				}

				.schedule-compass-e {
					right: 6px;
					top: 50%;
					transform: translateY(-50%);
				}

				.schedule-compass-w {
					left: 6px;
					top: 50%;
					transform: translateY(-50%);
				}

				@media (max-width: 1200px) {
					.schedule-summary-row {
						grid-template-columns: repeat(3, minmax(120px, 1fr));
					}

					.schedule-main-row {
						grid-template-columns: 1fr;
					}
				}

				@media (max-width: 700px) {
					.schedule-summary-row {
						grid-template-columns: 1fr;
					}
				}
			</style>
		`);
	}

	render_empty_state() {
		this.wrapper.find('[data-role="map"]').html(`
			<div class="schedule-empty">
				<div style="font-size: 18px; font-weight: 600;">${__("Mining Schedule Viewer")}</div>
				<div>${__("Select a Mining Schedule Scenario and load it.")}</div>
			</div>
		`);

		this.wrapper.find('[data-role="period_summary"]').html(`<div class="text-muted">${__("No period selected.")}</div>`);
		this.wrapper.find('[data-role="block_summary"]').html(`<div class="text-muted">${__("No blocks loaded.")}</div>`);
		this.wrapper.find('[data-role="material_summary"]').html(`<div class="text-muted">${__("No material rows loaded.")}</div>`);
	}

	load_scenario() {
		const scenario = this.scenario_control.get_value();

		if (!scenario) {
			return;
		}

		frappe.call({
			method: "is_production.geo_planning.page.mining_schedule_view.mining_schedule_view.get_schedule_viewer_data",
			args: {
				scenario: scenario
			},
			freeze: true,
			freeze_message: __("Loading Schedule Scenario..."),
			callback: (r) => {
				this.data = r.message || {};
				this.active_period_no = this.get_first_period_no();

				this.zoom_level = 1;
				this.rotation_degrees = 0;
				this.pan_x = 0;
				this.pan_y = 0;

				this.render_all();
			}
		});
	}

	get_first_period_no() {
		const periods = this.data && this.data.periods ? this.data.periods : [];
		return periods.length ? periods[0].period_no : null;
	}

	render_all() {
		this.render_totals();
		this.render_period_strip();
		this.render_map();
		this.render_period_summary();
		this.render_block_summary();
		this.render_material_summary();
		this.update_status();
	}

	render_totals() {
		const scenario = this.data && this.data.scenario ? this.data.scenario : {};

		this.wrapper.find('[data-total="total_periods"]').text(format_number(scenario.total_periods || 0, null, 0));
		this.wrapper.find('[data-total="total_blocks"]').text(format_number(scenario.total_blocks || 0, null, 0));
		this.wrapper.find('[data-total="total_volume"]').text(format_number(scenario.total_volume || 0, null, 2));
		this.wrapper.find('[data-total="total_tonnes"]').text(format_number(scenario.total_tonnes || 0, null, 2));
		this.wrapper.find('[data-total="average_density"]').text(format_number(scenario.average_density || 0, null, 3));
		this.wrapper.find('[data-total="average_cv"]').text(format_number(scenario.average_cv || 0, null, 2));
	}

	render_period_strip() {
		const container = this.wrapper.find('[data-role="period_strip"]');
		const periods = this.data && this.data.periods ? this.data.periods : [];

		if (!periods.length) {
			container.html("");
			return;
		}

		const html = periods.map((period) => {
			const active = cint(period.period_no) === cint(this.active_period_no) ? "active" : "";

			return `
				<button class="btn btn-sm btn-default schedule-period-button ${active}" data-period="${period.period_no}">
					${frappe.utils.escape_html(period.period_label || ("Period " + period.period_no))}
				</button>
			`;
		}).join("");

		container.html(html);

		container.find("[data-period]").on("click", (event) => {
			this.active_period_no = cint($(event.currentTarget).attr("data-period"));
			this.render_all();
		});
	}

	render_map() {
		const map = this.wrapper.find('[data-role="map"]');
		const blocks = this.data && this.data.scheduled_blocks ? this.data.scheduled_blocks : [];
		const block_geo = this.data && this.data.block_geo ? this.data.block_geo : {};

		const shapes = [];

		for (const row of blocks) {
			const geo = block_geo[row.mining_block];

			if (!geo) {
				continue;
			}

			const points = this.get_polygon_points(geo.polygon_geojson);

			if (!points.length) {
				continue;
			}

			shapes.push({
				row: row,
				geo: geo,
				points: points
			});
		}

		if (!shapes.length) {
			map.html(`
				<div class="schedule-empty">
					<div>${__("No polygons found for scheduled blocks.")}</div>
				</div>
			`);
			return;
		}

		const bounds = this.get_bounds(shapes);
		const padding = Math.max((bounds.max_x - bounds.min_x), (bounds.max_y - bounds.min_y)) * 0.06 || 10;

		this.view_box = {
			x: bounds.min_x - padding,
			y: -(bounds.max_y + padding),
			width: (bounds.max_x - bounds.min_x) + padding * 2,
			height: (bounds.max_y - bounds.min_y) + padding * 2
		};

		map.html(`
			<svg data-role="svg_map" viewBox="${this.view_box.x} ${this.view_box.y} ${this.view_box.width} ${this.view_box.height}" preserveAspectRatio="xMidYMid meet">
				<g data-role="viewport">
					<g data-role="block_layer"></g>
					<g data-role="label_layer"></g>
					<g data-role="sequence_layer"></g>
				</g>
			</svg>
		`);

		this.svg = map.find('[data-role="svg_map"]');
		this.viewport = map.find('[data-role="viewport"]');

		this.bind_map_navigation_events();

		const block_layer = map.find('[data-role="block_layer"]');
		const label_layer = map.find('[data-role="label_layer"]');
		const sequence_layer = map.find('[data-role="sequence_layer"]');

		for (const shape of shapes) {
			const centroid = this.get_centroid(shape.points);

			const path = $(document.createElementNS("http://www.w3.org/2000/svg", "path"));
			path.attr("d", this.points_to_path(shape.points));
			path.attr("class", this.get_block_class(shape.row));
			path.append(`<title>${frappe.utils.escape_html((shape.row.period_label || "") + " - " + (shape.row.mining_block_code || shape.row.mining_block || ""))}</title>`);

			block_layer.append(path);

			const label = $(document.createElementNS("http://www.w3.org/2000/svg", "text"));
			label.attr("x", centroid.x);
			label.attr("y", -centroid.y);
			label.attr("class", "schedule-label-text");
			label.text(shape.row.period_no || "");

			label_layer.append(label);

			if (cint(shape.row.period_no) === cint(this.active_period_no)) {
				const circle = $(document.createElementNS("http://www.w3.org/2000/svg", "circle"));
				circle.attr("cx", centroid.x);
				circle.attr("cy", -centroid.y);
				circle.attr("r", 11);
				circle.attr("class", "schedule-sequence-badge");

				const text = $(document.createElementNS("http://www.w3.org/2000/svg", "text"));
				text.attr("x", centroid.x);
				text.attr("y", -centroid.y);
				text.attr("class", "schedule-sequence-text");
				text.text(shape.row.sequence_no || "");

				sequence_layer.append(circle);
				sequence_layer.append(text);
			}
		}

		this.apply_view_transform();
	}

	bind_map_navigation_events() {
		const map = this.wrapper.find('[data-role="map"]');

		map.off("wheel.schedule_view");
		map.off("mousedown.schedule_view");

		$(document).off("mousemove.schedule_view");
		$(document).off("mouseup.schedule_view");

		map.on("wheel.schedule_view", (event) => {
			event.preventDefault();

			const original = event.originalEvent;
			const factor = original.deltaY < 0 ? 1.12 : 1 / 1.12;

			this.zoom(factor);
		});

		map.on("mousedown.schedule_view", (event) => {
			if ($(event.target).hasClass("schedule-block")) {
				return;
			}

			this.is_dragging = true;
			this.drag_start = {
				x: event.clientX,
				y: event.clientY,
				pan_x: this.pan_x,
				pan_y: this.pan_y
			};

			map.addClass("is-dragging");
		});

		$(document).on("mousemove.schedule_view", (event) => {
			if (!this.is_dragging || !this.drag_start) {
				return;
			}

			const dx = event.clientX - this.drag_start.x;
			const dy = event.clientY - this.drag_start.y;

			const scale_factor = this.view_box ? this.view_box.width / Math.max(map.width(), 1) : 1;

			this.pan_x = this.drag_start.pan_x + (dx * scale_factor);
			this.pan_y = this.drag_start.pan_y + (dy * scale_factor);

			this.apply_view_transform();
		});

		$(document).on("mouseup.schedule_view", () => {
			this.is_dragging = false;
			this.drag_start = null;
			map.removeClass("is-dragging");
		});
	}

	get_block_class(row) {
		let cls = "schedule-block";

		if (cint(row.period_no) === cint(this.active_period_no)) {
			cls += " is-active-period";
		} else if (cint(row.period_no) < cint(this.active_period_no)) {
			cls += " is-before-period";
		} else {
			cls += " is-after-period";
		}

		return cls;
	}

	render_period_summary() {
		const container = this.wrapper.find('[data-role="period_summary"]');
		const period = this.get_active_period();

		if (!period) {
			container.html(`<div class="text-muted">${__("No period selected.")}</div>`);
			return;
		}

		container.html(`
			<div class="schedule-section-title">${frappe.utils.escape_html(period.period_label || "")}</div>
			<div class="text-muted" style="margin-bottom: 10px;">
				${frappe.utils.escape_html(period.period_start_date || "")} → ${frappe.utils.escape_html(period.period_end_date || "")}
			</div>

			<div class="schedule-metric-grid">
				${this.metric_html(__("Blocks"), format_number(period.planned_block_count || 0, null, 0))}
				${this.metric_html(__("Volume"), format_number(period.planned_volume || 0, null, 2))}
				${this.metric_html(__("Tonnes"), format_number(period.planned_tonnes || 0, null, 2))}
				${this.metric_html(__("Capacity Used"), format_number(period.capacity_used_percent || 0, null, 1) + "%")}
				${this.metric_html(__("Avg Density"), format_number(period.average_density || 0, null, 3))}
				${this.metric_html(__("Avg CV"), format_number(period.average_cv || 0, null, 2))}
			</div>
		`);
	}

	render_block_summary() {
		const container = this.wrapper.find('[data-role="block_summary"]');
		const rows = (this.data && this.data.scheduled_blocks ? this.data.scheduled_blocks : [])
			.filter((row) => cint(row.period_no) === cint(this.active_period_no))
			.sort((a, b) => cint(a.sequence_no) - cint(b.sequence_no));

		if (!rows.length) {
			container.html(`<div class="text-muted">${__("No blocks for this period.")}</div>`);
			return;
		}

		const html = rows.map((row) => {
			return `
				<tr>
					<td>${format_number(row.sequence_no || 0, null, 0)}</td>
					<td>${frappe.utils.escape_html(row.dependency_group || "")}</td>
					<td>${frappe.utils.escape_html(row.mining_block_code || row.mining_block || "")}</td>
					<td>${format_number(row.total_volume || 0, null, 2)}</td>
					<td>${format_number(row.total_tonnes || 0, null, 2)}</td>
				</tr>
			`;
		}).join("");

		container.html(`
			<div class="schedule-section-title">${__("Scheduled Blocks")}</div>
			<table class="schedule-table">
				<thead>
					<tr>
						<th>${__("Seq")}</th>
						<th>${__("Cut")}</th>
						<th>${__("Block")}</th>
						<th>${__("Vol")}</th>
						<th>${__("Tonnes")}</th>
					</tr>
				</thead>
				<tbody>${html}</tbody>
			</table>
		`);
	}

	render_material_summary() {
		const container = this.wrapper.find('[data-role="material_summary"]');
		const rows = (this.data && this.data.period_materials ? this.data.period_materials : [])
			.filter((row) => cint(row.period_no) === cint(this.active_period_no));

		if (!rows.length) {
			container.html(`<div class="text-muted">${__("No material rows for this period.")}</div>`);
			return;
		}

		const html = rows.map((row) => {
			return `
				<tr>
					<td>${frappe.utils.escape_html(row.material_seam || "")}</td>
					<td>${frappe.utils.escape_html(row.value_type || "")}</td>
					<td>${frappe.utils.escape_html(row.variable_code || "")}</td>
					<td>${format_number(row.volume || 0, null, 2)}</td>
					<td>${format_number(row.tonnes || 0, null, 2)}</td>
					<td>${format_number(row.average_value || 0, null, 3)}</td>
				</tr>
			`;
		}).join("");

		container.html(`
			<div class="schedule-section-title">${__("Period Materials")}</div>
			<table class="schedule-table">
				<thead>
					<tr>
						<th>${__("Material")}</th>
						<th>${__("Type")}</th>
						<th>${__("Variable")}</th>
						<th>${__("Volume")}</th>
						<th>${__("Tonnes")}</th>
						<th>${__("Avg")}</th>
					</tr>
				</thead>
				<tbody>${html}</tbody>
			</table>
		`);
	}

	metric_html(label, value) {
		return `
			<div class="schedule-metric">
				<div class="schedule-metric-label">${frappe.utils.escape_html(label)}</div>
				<div class="schedule-metric-value">${value}</div>
			</div>
		`;
	}

	get_active_period() {
		return (this.data && this.data.periods ? this.data.periods : [])
			.find((row) => cint(row.period_no) === cint(this.active_period_no));
	}

	update_status() {
		const scenario = this.data && this.data.scenario ? this.data.scenario : {};
		this.wrapper.find('[data-role="status"]').text(scenario.scenario_name || scenario.name || "");
	}

	get_polygon_points(geojson) {
		if (!geojson) {
			return [];
		}

		let coordinates = [];

		if (geojson.type === "Feature" && geojson.geometry) {
			coordinates = geojson.geometry.coordinates || [];
		} else if (geojson.type === "Polygon") {
			coordinates = geojson.coordinates || [];
		} else if (Array.isArray(geojson)) {
			coordinates = geojson;
		}

		if (!coordinates.length) {
			return [];
		}

		let ring = [];

		if (Array.isArray(coordinates[0]) && Array.isArray(coordinates[0][0])) {
			ring = coordinates[0];
		} else {
			ring = coordinates;
		}

		return ring
			.filter((point) => Array.isArray(point) && point.length >= 2)
			.map((point) => {
				return {
					x: flt(point[0]),
					y: flt(point[1])
				};
			});
	}

	points_to_path(points) {
		if (!points.length) {
			return "";
		}

		const commands = [];

		points.forEach((point, index) => {
			const command = index === 0 ? "M" : "L";
			commands.push(`${command} ${point.x} ${-point.y}`);
		});

		commands.push("Z");

		return commands.join(" ");
	}

	get_bounds(shapes) {
		let min_x = Infinity;
		let min_y = Infinity;
		let max_x = -Infinity;
		let max_y = -Infinity;

		for (const shape of shapes) {
			for (const point of shape.points) {
				min_x = Math.min(min_x, point.x);
				min_y = Math.min(min_y, point.y);
				max_x = Math.max(max_x, point.x);
				max_y = Math.max(max_y, point.y);
			}
		}

		return {
			min_x: min_x,
			min_y: min_y,
			max_x: max_x,
			max_y: max_y
		};
	}

	get_centroid(points) {
		if (!points.length) {
			return { x: 0, y: 0 };
		}

		let x = 0;
		let y = 0;

		for (const point of points) {
			x += point.x;
			y += point.y;
		}

		return {
			x: x / points.length,
			y: y / points.length
		};
	}

	zoom(factor) {
		this.zoom_level = Math.max(0.25, Math.min(8, this.zoom_level * factor));
		this.apply_view_transform();
	}

	rotate(delta) {
		this.rotation_degrees = (this.rotation_degrees + delta) % 360;
		this.apply_view_transform();
		this.update_compass();
	}

	reset_view_transform() {
		this.zoom_level = 1;
		this.rotation_degrees = 0;
		this.pan_x = 0;
		this.pan_y = 0;
		this.apply_view_transform();
		this.update_compass();
	}

	apply_view_transform() {
		if (!this.viewport || !this.view_box) {
			return;
		}

		const cx = this.view_box.x + this.view_box.width / 2;
		const cy = this.view_box.y + this.view_box.height / 2;

		const transform = [
			`translate(${this.pan_x} ${this.pan_y})`,
			`translate(${cx} ${cy})`,
			`rotate(${this.rotation_degrees})`,
			`scale(${this.zoom_level})`,
			`translate(${-cx} ${-cy})`
		].join(" ");

		this.viewport.attr("transform", transform);
	}

	update_compass() {
		const arrow = this.wrapper.find('[data-role="compass_arrow"]');

		if (!arrow.length) {
			return;
		}

		arrow.css(
			"transform",
			`translateX(-50%) rotate(${-this.rotation_degrees}deg)`
		);
	}
}