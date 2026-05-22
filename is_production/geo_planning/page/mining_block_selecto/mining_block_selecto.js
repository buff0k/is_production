frappe.pages["mining-block-selecto"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Mining Block Selector"),
		single_column: true
	});

	new MiningBlockSelectoPage(page);
};

class MiningBlockSelectoPage {
	constructor(page) {
		this.page = page;
		this.wrapper = $(page.body);

		this.blocks = [];
		this.block_by_name = {};
		this.material_summaries = [];
		this.material_values = [];

		this.selected_blocks = new Set();
		this.selected_block_order = [];

		this.spatial_overlay = null;
		this.spatial_overlay_points = [];

		this.active_cut_no = 1;
		this.active_cut = "Cut 1";
		this.max_cut_no = 1;

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
		this.make_filter_controls();
		this.make_actions();
		this.render_empty_state();
		this.render_cut_control();
		this.update_compass();
	}

	make_actions() {
		this.page.set_primary_action(__("Load Blocks"), () => {
			this.load_blocks();
		});

		this.page.add_action_item(__("Summary of Selection"), () => {
			this.show_selection_summary();
		});

		this.page.add_action_item(__("Clear Selection"), () => {
			this.clear_selection();
		});

		this.page.add_action_item(__("Save Selection"), () => {
			this.prompt_save_selection();
		});
	}

	make_layout() {
		this.wrapper.empty();

		this.wrapper.append(`
			<div class="mining-selector">
				<div class="selector-filter-card">
					<div class="selector-filter-title">
						<strong>${__("Selection Filters")}</strong>
						<span class="text-muted">${__("Choose the project, layout and material stack before loading blocks.")}</span>
					</div>

					<div class="selector-filter-grid">
						<div data-field="geo_project"></div>
						<div data-field="geo_pit_layout"></div>
						<div data-field="material_stack"></div>
						<div data-field="material_seam"></div>
					</div>
				</div>

				<div class="selector-spatial-card">
					<div class="selector-spatial-header">
						<div>
							<strong>${__("Permit / Boundary Overlay")}</strong>
							<span class="text-muted">${__("Optional. Load an imported XYZ or pit outline over the blocks, then select blocks inside it.")}</span>
						</div>
					</div>

					<div class="selector-spatial-grid">
						<div data-field="spatial_source_type"></div>
						<div data-field="spatial_geo_import_batch"></div>
						<div data-field="spatial_pit_outline_batch"></div>
						<div data-field="spatial_outline_mode"></div>
						<div class="selector-spatial-actions">
							<button class="btn btn-sm btn-default" data-action="load_spatial_overlay">${__("Load Overlay")}</button>
							<button class="btn btn-sm btn-primary" data-action="select_from_overlay">${__("Select Blocks Inside")}</button>
							<button class="btn btn-sm btn-default" data-action="clear_spatial_overlay">${__("Clear Overlay")}</button>
						</div>
					</div>
				</div>

				<div class="selector-cut-card">
					<div class="selector-cut-header">
						<div>
							<strong>${__("Planning Cut")}</strong>
							<span class="text-muted">${__("Select blocks in mining order. Add the next cut only when needed.")}</span>
						</div>
						<div class="selector-active-cut">
							${__("Active")}: <strong data-role="active_cut_label">Cut 1</strong>
						</div>
					</div>

					<div class="selector-cut-control">
						<button class="btn btn-sm btn-default" data-action="previous_cut">${__("Previous Cut")}</button>
						<button class="btn btn-sm btn-primary" data-action="active_cut_display" disabled>${__("Cut 1")}</button>
						<button class="btn btn-sm btn-default" data-action="next_cut">${__("Next Cut")}</button>
						<button class="btn btn-sm btn-success" data-action="add_cut">${__("+ Add Cut")}</button>
						<button class="btn btn-sm btn-info" data-action="selection_summary">${__("Summary of Selection")}</button>
					</div>
				</div>

				<div class="selector-summary-row">
					<div class="selector-card">
						<div class="selector-label">${__("Selected Blocks")}</div>
						<div class="selector-value" data-total="selected_block_count">0</div>
					</div>
					<div class="selector-card">
						<div class="selector-label">${__("Effective Area")}</div>
						<div class="selector-value" data-total="total_effective_area">0.00</div>
					</div>
					<div class="selector-card">
						<div class="selector-label">${__("Volume")}</div>
						<div class="selector-value" data-total="total_volume">0.00</div>
					</div>
					<div class="selector-card">
						<div class="selector-label">${__("Tonnes")}</div>
						<div class="selector-value" data-total="total_tonnes">0.00</div>
					</div>
					<div class="selector-card">
						<div class="selector-label">${__("Average Density")}</div>
						<div class="selector-value" data-total="average_density">0.000</div>
					</div>
					<div class="selector-card">
						<div class="selector-label">${__("Average CV")}</div>
						<div class="selector-value" data-total="average_cv">0.00</div>
					</div>
				</div>

				<div class="selector-main-row">
					<div class="selector-map-card">
						<div class="selector-toolbar">
							<div>
								<strong>${__("Block Map")}</strong>
								<span class="text-muted selector-subtitle" data-role="map_status">${__("Load filters to begin.")}</span>
							</div>
							<div class="selector-map-actions">
								<button class="btn btn-xs btn-default" data-action="zoom_in">${__("Zoom +")}</button>
								<button class="btn btn-xs btn-default" data-action="zoom_out">${__("Zoom -")}</button>
								<button class="btn btn-xs btn-default" data-action="rotate_left">${__("Rotate Left")}</button>
								<button class="btn btn-xs btn-default" data-action="rotate_right">${__("Rotate Right")}</button>
								<button class="btn btn-xs btn-default" data-action="reset_view">${__("Reset View")}</button>
								<button class="btn btn-xs btn-default" data-action="clear_selection">${__("Clear")}</button>
							</div>
						</div>

						<div class="selector-map-wrap">
							<div class="selector-compass" data-role="compass">
								<div class="selector-compass-arrow" data-role="compass_arrow">▲</div>
								<div class="selector-compass-n">N</div>
								<div class="selector-compass-s">S</div>
								<div class="selector-compass-e">E</div>
								<div class="selector-compass-w">W</div>
							</div>
							<div class="selector-map" data-role="map"></div>
						</div>
					</div>

					<div class="selector-side-card">
						<div class="selector-side-header">
							<strong>${__("Mining Sequence")}</strong>
							<div class="text-muted">${__("The order below is the saved mining order.")}</div>
						</div>
						<div class="selector-selected-list" data-role="selected_list">
							<div class="text-muted">${__("No blocks selected.")}</div>
						</div>

						<hr>

						<div class="selector-side-header">
							<strong>${__("Material Split")}</strong>
						</div>
						<div class="selector-material-list" data-role="material_list">
							<div class="text-muted">${__("No material data loaded.")}</div>
						</div>
					</div>
				</div>
			</div>
		`);

		this.add_styles();
		this.bind_layout_events();
	}

	make_filter_controls() {
		this.geo_project_control = frappe.ui.form.make_control({
			parent: this.wrapper.find('[data-field="geo_project"]'),
			df: {
				fieldtype: "Link",
				fieldname: "geo_project",
				label: __("Geo Project"),
				options: "Geo Project",
				reqd: 1,
				change: () => {
					this.clear_data();
				}
			},
			render_input: true
		});

		this.geo_pit_layout_control = frappe.ui.form.make_control({
			parent: this.wrapper.find('[data-field="geo_pit_layout"]'),
			df: {
				fieldtype: "Link",
				fieldname: "geo_pit_layout",
				label: __("Geo Pit Layout"),
				options: "Geo Pit Layout",
				reqd: 1,
				get_query: () => {
					const geo_project = this.geo_project_control.get_value();

					if (!geo_project) {
						return {};
					}

					return {
						filters: {
							geo_project: geo_project
						}
					};
				},
				change: () => {
					this.clear_data();
				}
			},
			render_input: true
		});

		this.material_stack_control = frappe.ui.form.make_control({
			parent: this.wrapper.find('[data-field="material_stack"]'),
			df: {
				fieldtype: "Link",
				fieldname: "material_stack",
				label: __("Material Stack"),
				options: "Geo Pit Layout Material Stack",
				reqd: 1,
				get_query: () => {
					const geo_project = this.geo_project_control.get_value();
					const geo_pit_layout = this.geo_pit_layout_control.get_value();

					const filters = {};

					if (geo_project) {
						filters.geo_project = geo_project;
					}

					if (geo_pit_layout) {
						filters.geo_pit_layout = geo_pit_layout;
					}

					return {
						filters: filters
					};
				},
				change: () => {
					this.clear_data();
				}
			},
			render_input: true
		});

		this.material_seam_control = frappe.ui.form.make_control({
			parent: this.wrapper.find('[data-field="material_seam"]'),
			df: {
				fieldtype: "Data",
				fieldname: "material_seam",
				label: __("Material / Seam"),
				description: __("Optional. Example: S2U or S2L."),
				change: () => {
					this.clear_data();
				}
			},
			render_input: true
		});

		this.spatial_source_type_control = frappe.ui.form.make_control({
			parent: this.wrapper.find('[data-field="spatial_source_type"]'),
			df: {
				fieldtype: "Select",
				fieldname: "spatial_source_type",
				label: __("Spatial Source"),
				options: [
					"None",
					"Geo Import Batch",
					"Pit Outline Points",
					"Geo Model Points"
				].join("\n"),
				default: "None",
				change: () => {
					this.toggle_spatial_source_fields();
				}
			},
			render_input: true
		});

		this.spatial_geo_import_batch_control = frappe.ui.form.make_control({
			parent: this.wrapper.find('[data-field="spatial_geo_import_batch"]'),
			df: {
				fieldtype: "Link",
				fieldname: "spatial_geo_import_batch",
				label: __("Geo Import Batch"),
				options: "Geo Import Batch",
				get_query: () => {
					const geo_project = this.geo_project_control.get_value();

					return {
						query: "is_production.geo_planning.page.geo_planning_viewer.geo_planning_viewer.get_model_batch_query",
						filters: {
							geo_project: geo_project
						}
					};
				}
			},
			render_input: true
		});

		this.spatial_pit_outline_batch_control = frappe.ui.form.make_control({
			parent: this.wrapper.find('[data-field="spatial_pit_outline_batch"]'),
			df: {
				fieldtype: "Link",
				fieldname: "spatial_pit_outline_batch",
				label: __("Pit Outline"),
				options: "Geo Import Batch",
				get_query: () => {
					const geo_project = this.geo_project_control.get_value();

					return {
						query: "is_production.geo_planning.page.geo_planning_viewer.geo_planning_viewer.get_pit_outline_batch_query",
						filters: {
							geo_project: geo_project
						}
					};
				}
			},
			render_input: true
		});

		this.spatial_outline_mode_control = frappe.ui.form.make_control({
			parent: this.wrapper.find('[data-field="spatial_outline_mode"]'),
			df: {
				fieldtype: "Select",
				fieldname: "spatial_outline_mode",
				label: __("Outline Mode"),
				options: [
					"Point Order",
					"Convex Hull"
				].join("\n"),
				default: "Point Order"
			},
			render_input: true
		});

		this.toggle_spatial_source_fields();
	}

	add_styles() {
		if ($("#mining-block-selecto-style").length) {
			$("#mining-block-selecto-style").remove();
		}

		$("head").append(`
			<style id="mining-block-selecto-style">
				.mining-selector {
					padding: 12px;
				}

				.selector-filter-card,
				.selector-spatial-card,
				.selector-cut-card,
				.selector-card,
				.selector-map-card,
				.selector-side-card {
					background: var(--card-bg);
					border: 1px solid var(--border-color);
					border-radius: 12px;
					box-shadow: var(--shadow-sm);
				}

				.selector-filter-card,
				.selector-spatial-card,
				.selector-cut-card {
					padding: 14px;
					margin-bottom: 12px;
				}

				.selector-filter-title,
				.selector-spatial-header,
				.selector-cut-header {
					display: flex;
					gap: 10px;
					align-items: baseline;
					justify-content: space-between;
					margin-bottom: 12px;
				}

				.selector-filter-grid {
					display: grid;
					grid-template-columns: repeat(4, minmax(180px, 1fr));
					gap: 12px;
				}

				.selector-spatial-grid {
					display: grid;
					grid-template-columns: repeat(4, minmax(180px, 1fr)) auto;
					gap: 12px;
					align-items: end;
				}

				.selector-spatial-actions {
					display: flex;
					flex-wrap: wrap;
					gap: 8px;
					padding-bottom: 4px;
				}

				.selector-cut-control {
					display: flex;
					flex-wrap: wrap;
					gap: 8px;
					align-items: center;
				}

				.selector-active-cut {
					white-space: nowrap;
				}

				.selector-summary-row {
					display: grid;
					grid-template-columns: repeat(6, minmax(120px, 1fr));
					gap: 12px;
					margin-bottom: 12px;
				}

				.selector-card {
					padding: 12px;
				}

				.selector-label {
					font-size: 11px;
					text-transform: uppercase;
					color: var(--text-muted);
					margin-bottom: 4px;
				}

				.selector-value {
					font-size: 20px;
					font-weight: 700;
				}

				.selector-main-row {
					display: grid;
					grid-template-columns: minmax(0, 1fr) 380px;
					gap: 12px;
					min-height: 660px;
				}

				.selector-toolbar {
					display: flex;
					align-items: center;
					justify-content: space-between;
					gap: 12px;
					padding: 12px;
					border-bottom: 1px solid var(--border-color);
				}

				.selector-map-actions {
					display: flex;
					flex-wrap: wrap;
					gap: 6px;
					justify-content: flex-end;
				}

				.selector-subtitle {
					margin-left: 8px;
					font-size: 12px;
				}

				.selector-map-wrap {
					position: relative;
				}

				.selector-map {
					min-height: 600px;
					overflow: hidden;
					cursor: grab;
					background:
						linear-gradient(90deg, rgba(128, 128, 128, 0.08) 1px, transparent 1px),
						linear-gradient(rgba(128, 128, 128, 0.08) 1px, transparent 1px);
					background-size: 28px 28px;
				}

				.selector-map.is-dragging {
					cursor: grabbing;
				}

				.selector-map svg {
					display: block;
					width: 100%;
					height: 600px;
				}

				.selector-block {
					fill: rgba(80, 140, 220, 0.18);
					stroke: rgba(80, 140, 220, 0.85);
					stroke-width: 1;
					cursor: pointer;
					transition: fill 0.12s ease, stroke-width 0.12s ease;
				}

				.selector-block:hover {
					fill: rgba(80, 140, 220, 0.34);
					stroke-width: 2;
				}

				.selector-block.is-selected {
					fill: rgba(46, 204, 113, 0.45);
					stroke: rgba(39, 174, 96, 1);
					stroke-width: 2;
				}

				.selector-overlay-polygon {
					fill: rgba(243, 156, 18, 0.16);
					stroke: rgba(230, 126, 34, 1);
					stroke-width: 2;
					stroke-dasharray: 8 5;
					pointer-events: none;
				}

				.selector-overlay-point {
					fill: rgba(230, 126, 34, 1);
					stroke: #fff;
					stroke-width: 1;
					pointer-events: none;
				}

				.selector-label-text {
					font-size: 10px;
					fill: var(--text-color);
					pointer-events: none;
					text-anchor: middle;
					dominant-baseline: central;
				}

				.selector-sequence-badge {
					fill: rgba(39, 174, 96, 0.95);
					stroke: #fff;
					stroke-width: 1;
					pointer-events: none;
				}

				.selector-sequence-text {
					fill: #fff;
					font-size: 11px;
					font-weight: 700;
					pointer-events: none;
					text-anchor: middle;
					dominant-baseline: central;
				}

				.selector-side-card {
					padding: 12px;
					overflow: auto;
					max-height: 660px;
				}

				.selector-side-header {
					margin-bottom: 8px;
				}

				.selector-selected-cut-group {
					margin-bottom: 14px;
				}

				.selector-selected-cut-title {
					font-weight: 700;
					margin-bottom: 8px;
					padding: 6px 8px;
					border-radius: 8px;
					background: var(--control-bg);
				}

				.selector-selected-item,
				.selector-material-item {
					padding: 8px;
					border: 1px solid var(--border-color);
					border-radius: 8px;
					margin-bottom: 8px;
					background: var(--fg-color);
				}

				.selector-selected-item-title {
					font-weight: 600;
				}

				.selector-selected-item-meta,
				.selector-material-item-meta {
					color: var(--text-muted);
					font-size: 12px;
					margin-top: 3px;
				}

				.selector-seq-pill {
					display: inline-flex;
					align-items: center;
					justify-content: center;
					min-width: 26px;
					height: 22px;
					border-radius: 999px;
					background: var(--primary);
					color: #fff;
					font-size: 12px;
					font-weight: 700;
					margin-right: 6px;
				}

				.selector-empty {
					padding: 80px 20px;
					text-align: center;
					color: var(--text-muted);
				}

				.selector-compass {
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

				.selector-compass-arrow {
					position: absolute;
					left: 50%;
					top: 8px;
					transform-origin: 50% 33px;
					transform: translateX(-50%);
					font-size: 24px;
					color: #d35400;
				}

				.selector-compass-n,
				.selector-compass-s,
				.selector-compass-e,
				.selector-compass-w {
					position: absolute;
				}

				.selector-compass-n {
					top: 3px;
					left: 50%;
					transform: translateX(-50%);
				}

				.selector-compass-s {
					bottom: 3px;
					left: 50%;
					transform: translateX(-50%);
				}

				.selector-compass-e {
					right: 6px;
					top: 50%;
					transform: translateY(-50%);
				}

				.selector-compass-w {
					left: 6px;
					top: 50%;
					transform: translateY(-50%);
				}

				.selection-summary-grid {
					display: grid;
					grid-template-columns: repeat(auto-fit, minmax(330px, 1fr));
					gap: 14px;
				}

				.selection-summary-card {
					border: 1px solid var(--border-color);
					border-radius: 12px;
					padding: 12px;
					background: var(--card-bg);
				}

				.selection-summary-title {
					display: flex;
					justify-content: space-between;
					gap: 10px;
					align-items: center;
					margin-bottom: 10px;
				}

				.selection-summary-title h4 {
					margin: 0;
				}

				.selection-summary-metrics {
					display: grid;
					grid-template-columns: repeat(2, minmax(120px, 1fr));
					gap: 8px;
					margin-bottom: 12px;
				}

				.selection-summary-metric {
					border: 1px solid var(--border-color);
					border-radius: 8px;
					padding: 8px;
					background: var(--fg-color);
				}

				.selection-summary-metric-label {
					font-size: 10px;
					text-transform: uppercase;
					color: var(--text-muted);
				}

				.selection-summary-metric-value {
					font-weight: 700;
					font-size: 15px;
				}

				.selection-summary-section-title {
					font-weight: 700;
					margin: 10px 0 6px;
				}

				.selection-summary-block-list {
					max-height: 160px;
					overflow: auto;
					border: 1px solid var(--border-color);
					border-radius: 8px;
					padding: 8px;
					background: var(--fg-color);
				}

				.selection-summary-block-row {
					display: flex;
					gap: 8px;
					align-items: center;
					margin-bottom: 5px;
				}

				.selection-summary-table {
					width: 100%;
					border-collapse: collapse;
					font-size: 12px;
				}

				.selection-summary-table th,
				.selection-summary-table td {
					border-bottom: 1px solid var(--border-color);
					padding: 5px;
					text-align: left;
				}

				.selection-summary-table th {
					color: var(--text-muted);
					font-weight: 600;
				}

				.selection-summary-overall {
					margin-bottom: 14px;
					padding: 12px;
					border: 1px solid var(--border-color);
					border-radius: 12px;
					background: var(--fg-color);
				}

				@media (max-width: 1200px) {
					.selector-filter-grid,
					.selector-spatial-grid {
						grid-template-columns: repeat(2, minmax(180px, 1fr));
					}

					.selector-summary-row {
						grid-template-columns: repeat(3, minmax(120px, 1fr));
					}

					.selector-main-row {
						grid-template-columns: 1fr;
					}
				}

				@media (max-width: 700px) {
					.selector-filter-grid,
					.selector-spatial-grid {
						grid-template-columns: 1fr;
					}

					.selector-summary-row {
						grid-template-columns: 1fr;
					}
				}
			</style>
		`);
	}

	bind_layout_events() {
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

		this.wrapper.find('[data-action="clear_selection"]').on("click", () => {
			this.clear_selection();
		});

		this.wrapper.find('[data-action="previous_cut"]').on("click", () => {
			this.previous_cut();
		});

		this.wrapper.find('[data-action="next_cut"]').on("click", () => {
			this.next_cut();
		});

		this.wrapper.find('[data-action="add_cut"]').on("click", () => {
			this.add_cut();
		});

		this.wrapper.find('[data-action="selection_summary"]').on("click", () => {
			this.show_selection_summary();
		});

		this.wrapper.find('[data-action="load_spatial_overlay"]').on("click", () => {
			this.load_spatial_overlay();
		});

		this.wrapper.find('[data-action="select_from_overlay"]').on("click", () => {
			this.select_blocks_from_overlay();
		});

		this.wrapper.find('[data-action="clear_spatial_overlay"]').on("click", () => {
			this.clear_spatial_overlay();
		});
	}

	toggle_spatial_source_fields() {
		const source_type = this.spatial_source_type_control
			? this.spatial_source_type_control.get_value()
			: "None";

		const show_geo_import_batch = source_type === "Geo Import Batch" || source_type === "Geo Model Points";
		const show_pit_outline_batch = source_type === "Pit Outline Points";

		this.wrapper.find('[data-field="spatial_geo_import_batch"]').toggle(show_geo_import_batch);
		this.wrapper.find('[data-field="spatial_pit_outline_batch"]').toggle(show_pit_outline_batch);

		if (!show_geo_import_batch && this.spatial_geo_import_batch_control) {
			this.spatial_geo_import_batch_control.set_value("");
		}

		if (!show_pit_outline_batch && this.spatial_pit_outline_batch_control) {
			this.spatial_pit_outline_batch_control.set_value("");
		}
	}

	render_cut_control() {
		this.active_cut = `Cut ${this.active_cut_no}`;

		this.wrapper.find('[data-role="active_cut_label"]').text(this.active_cut);
		this.wrapper.find('[data-action="active_cut_display"]').text(this.active_cut);

		this.wrapper.find('[data-action="previous_cut"]').prop("disabled", this.active_cut_no <= 1);
		this.wrapper.find('[data-action="next_cut"]').prop("disabled", this.active_cut_no >= this.max_cut_no);
	}

	add_cut() {
		this.max_cut_no += 1;
		this.active_cut_no = this.max_cut_no;
		this.active_cut = `Cut ${this.active_cut_no}`;
		this.render_cut_control();

		frappe.show_alert({
			message: __("Added {0}.", [this.active_cut]),
			indicator: "green"
		});
	}

	next_cut() {
		if (this.active_cut_no >= this.max_cut_no) {
			return;
		}

		this.active_cut_no += 1;
		this.active_cut = `Cut ${this.active_cut_no}`;
		this.render_cut_control();
	}

	previous_cut() {
		if (this.active_cut_no <= 1) {
			return;
		}

		this.active_cut_no -= 1;
		this.active_cut = `Cut ${this.active_cut_no}`;
		this.render_cut_control();
	}

	render_empty_state() {
		this.wrapper.find('[data-role="map"]').html(`
			<div class="selector-empty">
				<div style="font-size: 18px; font-weight: 600;">${__("Mining Block Selector")}</div>
				<div>${__("Choose filters and click Load Blocks.")}</div>
			</div>
		`);
	}

	clear_data() {
		this.blocks = [];
		this.block_by_name = {};
		this.material_summaries = [];
		this.material_values = [];
		this.selected_blocks = new Set();
		this.selected_block_order = [];
		this.spatial_overlay = null;
		this.spatial_overlay_points = [];

		this.update_status(__("Filters changed. Load blocks again."));
		this.render_empty_state();
		this.update_totals();
		this.render_selected_list();
		this.render_material_list();
	}

	load_blocks() {
		const geo_project = this.geo_project_control.get_value();
		const geo_pit_layout = this.geo_pit_layout_control.get_value();
		const material_stack = this.material_stack_control.get_value();
		const material_seam = this.material_seam_control.get_value();

		if (!geo_project || !geo_pit_layout || !material_stack) {
			frappe.msgprint(__("Please select Geo Project, Geo Pit Layout and Material Stack."));
			return;
		}

		frappe.call({
			method: "is_production.geo_planning.page.mining_block_selecto.mining_block_selecto.get_selector_data",
			args: {
				geo_project: geo_project,
				geo_pit_layout: geo_pit_layout,
				material_stack: material_stack,
				material_seam: material_seam
			},
			freeze: true,
			freeze_message: __("Loading Mining Blocks..."),
			callback: (r) => {
				const data = r.message || {};

				this.blocks = data.blocks || [];
				this.block_by_name = {};
				this.blocks.forEach((block) => {
					this.block_by_name[block.name] = block;
				});

				this.material_summaries = data.material_summaries || [];
				this.material_values = data.material_values || [];

				this.selected_blocks = new Set();
				this.selected_block_order = [];

				this.zoom_level = 1;
				this.rotation_degrees = 0;
				this.pan_x = 0;
				this.pan_y = 0;

				this.render_map();
				this.update_totals();
				this.render_selected_list();
				this.render_material_list();

				this.update_status(__("Loaded {0} blocks.", [this.blocks.length]));
			}
		});
	}

	render_map() {
		const map = this.wrapper.find('[data-role="map"]');

		if (!this.blocks.length) {
			map.html(`
				<div class="selector-empty">
					<div>${__("No Mining Blocks found for these filters.")}</div>
				</div>
			`);
			return;
		}

		const shapes = [];

		for (const block of this.blocks) {
			const points = this.get_polygon_points(block);

			if (!points.length) {
				continue;
			}

			shapes.push({
				block: block,
				points: points
			});
		}

		if (!shapes.length) {
			map.html(`
				<div class="selector-empty">
					<div>${__("Blocks were found, but no polygon_geojson could be drawn.")}</div>
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
					<g data-role="overlay_layer"></g>
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

		for (const shape of shapes) {
			const path_data = this.points_to_path(shape.points);
			const centroid = this.get_centroid(shape.points);
			const title = this.get_block_title(shape.block);

			const path = $(document.createElementNS("http://www.w3.org/2000/svg", "path"));
			path.attr("d", path_data);
			path.attr("class", "selector-block");
			path.attr("data-block", shape.block.name);
			path.append(`<title>${frappe.utils.escape_html(title)}</title>`);

			path.on("click", (event) => {
				event.stopPropagation();
				this.toggle_block(shape.block.name);
			});

			block_layer.append(path);

			const label = $(document.createElementNS("http://www.w3.org/2000/svg", "text"));
			label.attr("x", centroid.x);
			label.attr("y", -centroid.y);
			label.attr("class", "selector-label-text");
			label.text(shape.block.block_no || shape.block.mining_block_code || "");
			label_layer.append(label);
		}

		this.apply_view_transform();
		this.render_spatial_overlay();
		this.render_sequence_badges();
	}

	bind_map_navigation_events() {
		const map = this.wrapper.find('[data-role="map"]');

		map.off("wheel.selector");
		map.off("mousedown.selector");

		$(document).off("mousemove.selector");
		$(document).off("mouseup.selector");

		map.on("wheel.selector", (event) => {
			event.preventDefault();

			const original = event.originalEvent;
			const factor = original.deltaY < 0 ? 1.12 : 1 / 1.12;

			this.zoom(factor);
		});

		map.on("mousedown.selector", (event) => {
			if ($(event.target).hasClass("selector-block")) {
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

		$(document).on("mousemove.selector", (event) => {
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

		$(document).on("mouseup.selector", () => {
			this.is_dragging = false;
			this.drag_start = null;
			map.removeClass("is-dragging");
		});
	}

	load_spatial_overlay() {
		const source_type = this.spatial_source_type_control.get_value();
		const geo_import_batch = this.spatial_geo_import_batch_control.get_value();
		const pit_outline_batch = this.spatial_pit_outline_batch_control.get_value();
		const outline_mode = this.spatial_outline_mode_control.get_value() || "Point Order";

		const geo_project = this.geo_project_control.get_value();
		const geo_pit_layout = this.geo_pit_layout_control.get_value();

		if (!source_type || source_type === "None") {
			frappe.msgprint(__("Please choose a Spatial Source."));
			return;
		}

		if ((source_type === "Geo Import Batch" || source_type === "Geo Model Points") && !geo_import_batch) {
			frappe.msgprint(__("Please choose a Geo Import Batch."));
			return;
		}

		if (source_type === "Pit Outline Points" && !pit_outline_batch) {
			frappe.msgprint(__("Please choose a Pit Outline batch."));
			return;
		}

		frappe.call({
			method: "is_production.geo_planning.page.mining_block_selecto.mining_block_selecto.get_spatial_overlay",
			args: {
				source_type: source_type,
				geo_project: geo_project,
				geo_import_batch: geo_import_batch,
				pit_outline_batch: pit_outline_batch,
				geo_pit_layout: geo_pit_layout,
				outline_mode: outline_mode
			},
			freeze: true,
			freeze_message: __("Loading spatial overlay..."),
			callback: (r) => {
				const data = r.message || {};

				this.spatial_overlay = data;
				this.spatial_overlay_points = data.points || [];

				this.render_spatial_overlay();

				frappe.show_alert({
					message: __("Overlay loaded with {0} points.", [this.spatial_overlay_points.length]),
					indicator: "green"
				});
			}
		});
	}

	render_spatial_overlay() {
		const map = this.wrapper.find('[data-role="map"]');
		const layer = map.find('[data-role="overlay_layer"]');

		if (!layer.length) {
			return;
		}

		layer.empty();

		if (!this.spatial_overlay_points || !this.spatial_overlay_points.length) {
			return;
		}

		const path_data = this.overlay_points_to_path(this.spatial_overlay_points);

		const path = $(document.createElementNS("http://www.w3.org/2000/svg", "path"));
		path.attr("d", path_data);
		path.attr("class", "selector-overlay-polygon");
		layer.append(path);

		for (const point of this.spatial_overlay_points) {
			const circle = $(document.createElementNS("http://www.w3.org/2000/svg", "circle"));
			circle.attr("cx", flt(point.x));
			circle.attr("cy", -flt(point.y));
			circle.attr("r", 4);
			circle.attr("class", "selector-overlay-point");

			layer.append(circle);
		}
	}

	overlay_points_to_path(points) {
		if (!points || !points.length) {
			return "";
		}

		const commands = [];

		points.forEach((point, index) => {
			const command = index === 0 ? "M" : "L";
			commands.push(`${command} ${flt(point.x)} ${-flt(point.y)}`);
		});

		commands.push("Z");

		return commands.join(" ");
	}

	clear_spatial_overlay() {
		this.spatial_overlay = null;
		this.spatial_overlay_points = [];

		const map = this.wrapper.find('[data-role="map"]');
		map.find('[data-role="overlay_layer"]').empty();

		frappe.show_alert({
			message: __("Spatial overlay cleared."),
			indicator: "blue"
		});
	}

	select_blocks_from_overlay() {
		if (!this.spatial_overlay_points || this.spatial_overlay_points.length < 3) {
			frappe.msgprint(__("Please load a spatial overlay first."));
			return;
		}

		if (!this.blocks || !this.blocks.length) {
			frappe.msgprint(__("Please load Mining Blocks first."));
			return;
		}

		const polygon = this.spatial_overlay_points.map((point) => {
			return {
				x: flt(point.x),
				y: flt(point.y)
			};
		});

		const candidates = [];

		for (const block of this.blocks) {
			if (this.selected_blocks.has(block.name)) {
				continue;
			}

			const centroid = this.get_block_centroid_for_selection(block);

			if (!centroid) {
				continue;
			}

			if (this.point_in_polygon(centroid, polygon)) {
				candidates.push(block);
			}
		}

		candidates.sort((a, b) => {
			return (
				(flt(a.cut_no) - flt(b.cut_no)) ||
				(flt(a.row_no) - flt(b.row_no)) ||
				(flt(a.column_no) - flt(b.column_no)) ||
				(flt(a.block_no) - flt(b.block_no)) ||
				(this.get_block_title(a) || "").localeCompare(this.get_block_title(b) || "")
			);
		});

		for (const block of candidates) {
			this.add_block_to_selection(block.name);
		}

		this.resequence_selected_blocks();
		this.refresh_selected_styles();
		this.update_totals();
		this.render_selected_list();
		this.render_material_list();
		this.render_sequence_badges();

		frappe.show_alert({
			message: __("Selected {0} block(s) into {1}.", [candidates.length, this.active_cut]),
			indicator: "green"
		});
	}

	get_block_centroid_for_selection(block) {
		if (
			block.centroid_x !== null &&
			block.centroid_x !== undefined &&
			block.centroid_y !== null &&
			block.centroid_y !== undefined
		) {
			return {
				x: flt(block.centroid_x),
				y: flt(block.centroid_y)
			};
		}

		const points = this.get_polygon_points(block);

		if (!points.length) {
			return null;
		}

		return this.get_centroid(points);
	}

	point_in_polygon(point, polygon) {
		let inside = false;

		for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
			const xi = polygon[i].x;
			const yi = polygon[i].y;
			const xj = polygon[j].x;
			const yj = polygon[j].y;

			const intersect = ((yi > point.y) !== (yj > point.y)) &&
				(point.x < (xj - xi) * (point.y - yi) / ((yj - yi) || 0.0000001) + xi);

			if (intersect) {
				inside = !inside;
			}
		}

		return inside;
	}

	get_polygon_points(block) {
		const geojson = block.polygon_geojson;

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

	toggle_block(block_name) {
		if (this.selected_blocks.has(block_name)) {
			this.remove_block_from_selection(block_name);
		} else {
			this.add_block_to_selection(block_name);
		}

		this.resequence_selected_blocks();
		this.refresh_selected_styles();
		this.update_totals();
		this.render_selected_list();
		this.render_material_list();
		this.render_sequence_badges();
	}

	add_block_to_selection(block_name) {
		if (this.selected_blocks.has(block_name)) {
			return;
		}

		this.selected_blocks.add(block_name);

		this.selected_block_order.push({
			name: block_name,
			dependency_group: this.active_cut
		});
	}

	remove_block_from_selection(block_name) {
		this.selected_blocks.delete(block_name);
		this.selected_block_order = this.selected_block_order.filter((entry) => {
			return entry.name !== block_name;
		});
	}

	resequence_selected_blocks() {
		this.selected_block_order = this.selected_block_order.map((entry, index) => {
			return {
				name: entry.name,
				dependency_group: entry.dependency_group || this.active_cut,
				sequence_no: index + 1
			};
		});
	}

	refresh_selected_styles() {
		this.wrapper.find(".selector-block").each((_, element) => {
			const block_name = $(element).attr("data-block");

			if (this.selected_blocks.has(block_name)) {
				$(element).addClass("is-selected");
			} else {
				$(element).removeClass("is-selected");
			}
		});
	}

	render_sequence_badges() {
		const map = this.wrapper.find('[data-role="map"]');
		const layer = map.find('[data-role="sequence_layer"]');

		if (!layer.length) {
			return;
		}

		layer.empty();

		for (const entry of this.selected_block_order) {
			const block = this.block_by_name[entry.name];

			if (!block) {
				continue;
			}

			const points = this.get_polygon_points(block);
			const centroid = this.get_centroid(points);

			if (!points.length) {
				continue;
			}

			const circle = $(document.createElementNS("http://www.w3.org/2000/svg", "circle"));
			circle.attr("cx", centroid.x);
			circle.attr("cy", -centroid.y);
			circle.attr("r", 11);
			circle.attr("class", "selector-sequence-badge");

			const text = $(document.createElementNS("http://www.w3.org/2000/svg", "text"));
			text.attr("x", centroid.x);
			text.attr("y", -centroid.y);
			text.attr("class", "selector-sequence-text");
			text.text(entry.sequence_no || "");

			layer.append(circle);
			layer.append(text);
		}
	}

	update_totals() {
		const totals = this.calculate_selected_totals();

		this.wrapper.find('[data-total="selected_block_count"]').text(format_number(totals.selected_block_count || 0, null, 0));
		this.wrapper.find('[data-total="total_effective_area"]').text(format_number(totals.total_effective_area || 0, null, 2));
		this.wrapper.find('[data-total="total_volume"]').text(format_number(totals.total_volume || 0, null, 2));
		this.wrapper.find('[data-total="total_tonnes"]').text(format_number(totals.total_tonnes || 0, null, 2));
		this.wrapper.find('[data-total="average_density"]').text(format_number(totals.average_density || 0, null, 3));
		this.wrapper.find('[data-total="average_cv"]').text(format_number(totals.average_cv || 0, null, 2));
	}

	calculate_selected_totals() {
		const selected = this.get_selected_blocks();
		const selected_names = new Set(selected.map((block) => block.name));

		const selected_summaries = this.material_summaries.filter((summary) => selected_names.has(summary.mining_block));
		const selected_values = this.material_values.filter((value) => selected_names.has(value.mining_block));

		let total_effective_area = 0;
		let total_volume = 0;
		let total_tonnes = 0;

		for (const block of selected) {
			total_effective_area += flt(block.effective_area);
		}

		for (const summary of selected_summaries) {
			total_volume += flt(summary.volume);
			total_tonnes += flt(summary.tonnes);
		}

		if (!total_volume) {
			for (const block of selected) {
				total_volume += flt(block.total_volume);
			}
		}

		if (!total_tonnes) {
			for (const block of selected) {
				total_tonnes += flt(block.total_tonnes);
			}
		}

		let average_density = 0;

		if (total_volume) {
			average_density = total_tonnes / total_volume;
		}

		const cv_values = selected_values
			.filter((value) => {
				const variable_code = (value.variable_code || "").toUpperCase();
				return value.value_type === "Quality" && variable_code.includes("CV") && value.avg_value !== null && value.avg_value !== undefined;
			})
			.map((value) => flt(value.avg_value));

		let average_cv = 0;

		if (cv_values.length) {
			average_cv = cv_values.reduce((total, value) => total + value, 0) / cv_values.length;
		}

		return {
			selected_block_count: selected.length,
			total_effective_area: total_effective_area,
			total_volume: total_volume,
			total_tonnes: total_tonnes,
			average_density: average_density,
			average_cv: average_cv
		};
	}

	render_selected_list() {
		const list = this.wrapper.find('[data-role="selected_list"]');

		if (!this.selected_block_order.length) {
			list.html(`<div class="text-muted">${__("No blocks selected.")}</div>`);
			return;
		}

		const grouped = this.group_selection_by_cut();

		const html = Object.keys(grouped).map((cut) => {
			const rows = grouped[cut].map((entry) => {
				const block = this.block_by_name[entry.name] || {};
				return `
					<div class="selector-selected-item">
						<div class="selector-selected-item-title">
							<span class="selector-seq-pill">${entry.sequence_no}</span>
							${frappe.utils.escape_html(this.get_block_title(block))}
						</div>
						<div class="selector-selected-item-meta">
							${__("Planning Cut")}: ${frappe.utils.escape_html(entry.dependency_group || "")}
							<br>
							${__("Area")}: ${format_number(block.effective_area || 0, null, 2)}
							&nbsp;|&nbsp;
							${__("Tonnes")}: ${format_number(block.total_tonnes || 0, null, 2)}
						</div>
						<div style="margin-top: 6px;">
							<button class="btn btn-xs btn-default" data-remove-block="${frappe.utils.escape_html(entry.name)}">
								${__("Remove")}
							</button>
						</div>
					</div>
				`;
			}).join("");

			return `
				<div class="selector-selected-cut-group">
					<div class="selector-selected-cut-title">${frappe.utils.escape_html(cut)}</div>
					${rows}
				</div>
			`;
		}).join("");

		list.html(html);

		list.find("[data-remove-block]").on("click", (event) => {
			const block_name = $(event.currentTarget).attr("data-remove-block");
			this.remove_block_from_selection(block_name);
			this.resequence_selected_blocks();
			this.refresh_selected_styles();
			this.update_totals();
			this.render_selected_list();
			this.render_material_list();
			this.render_sequence_badges();
		});
	}

	render_material_list() {
		const list = this.wrapper.find('[data-role="material_list"]');
		const selected = this.get_selected_blocks();
		const selected_names = new Set(selected.map((block) => block.name));

		if (!selected_names.size) {
			list.html(`<div class="text-muted">${__("No blocks selected.")}</div>`);
			return;
		}

		const grouped = {};

		for (const summary of this.material_summaries) {
			if (!selected_names.has(summary.mining_block)) {
				continue;
			}

			const key = summary.material_seam || __("No Seam");

			if (!grouped[key]) {
				grouped[key] = {
					material_seam: key,
					effective_area: 0,
					volume: 0,
					tonnes: 0
				};
			}

			grouped[key].effective_area += flt(summary.effective_area);
			grouped[key].volume += flt(summary.volume);
			grouped[key].tonnes += flt(summary.tonnes);
		}

		const rows = Object.values(grouped);

		if (!rows.length) {
			list.html(`<div class="text-muted">${__("No material summary rows for selected blocks.")}</div>`);
			return;
		}

		const html = rows.map((row) => {
			return `
				<div class="selector-material-item">
					<div><strong>${frappe.utils.escape_html(row.material_seam)}</strong></div>
					<div class="selector-material-item-meta">
						${__("Area")}: ${format_number(row.effective_area || 0, null, 2)}
						<br>
						${__("Volume")}: ${format_number(row.volume || 0, null, 2)}
						<br>
						${__("Tonnes")}: ${format_number(row.tonnes || 0, null, 2)}
					</div>
				</div>
			`;
		}).join("");

		list.html(html);
	}

	show_selection_summary() {
		if (!this.selected_block_order.length) {
			frappe.msgprint(__("Please select at least one Mining Block first."));
			return;
		}

		const summary = this.build_selection_summary();
		const html = this.render_selection_summary_html(summary);

		const dialog = new frappe.ui.Dialog({
			title: __("Summary of Selection"),
			size: "extra-large",
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "summary_html",
					options: html
				}
			],
			primary_action_label: __("Close"),
			primary_action: () => {
				dialog.hide();
			}
		});

		dialog.show();
	}

	build_selection_summary() {
		const grouped = this.group_selection_by_cut();
		const cuts = [];
		const overall = {
			block_count: 0,
			effective_area: 0,
			volume: 0,
			tonnes: 0,
			average_density: 0,
			qualities: {}
		};

		for (const cut of Object.keys(grouped)) {
			const entries = grouped[cut];
			const block_names = entries.map((entry) => entry.name);
			const block_name_set = new Set(block_names);

			const blocks = entries.map((entry) => {
				const block = this.block_by_name[entry.name] || {};
				return {
					sequence_no: entry.sequence_no,
					name: entry.name,
					title: this.get_block_title(block),
					effective_area: flt(block.effective_area),
					total_tonnes: flt(block.total_tonnes)
				};
			});

			const cut_summary = {
				cut: cut,
				block_count: blocks.length,
				blocks: blocks,
				effective_area: 0,
				volume: 0,
				tonnes: 0,
				average_density: 0,
				materials: {},
				qualities: {}
			};

			for (const block of blocks) {
				cut_summary.effective_area += flt(block.effective_area);
			}

			for (const summary of this.material_summaries) {
				if (!block_name_set.has(summary.mining_block)) {
					continue;
				}

				const material_key = summary.material_seam || __("No Seam");

				if (!cut_summary.materials[material_key]) {
					cut_summary.materials[material_key] = {
						material_seam: material_key,
						effective_area: 0,
						volume: 0,
						tonnes: 0,
						thickness_values: [],
						density_values: []
					};
				}

				cut_summary.materials[material_key].effective_area += flt(summary.effective_area);
				cut_summary.materials[material_key].volume += flt(summary.volume);
				cut_summary.materials[material_key].tonnes += flt(summary.tonnes);

				if (summary.thickness_value !== null && summary.thickness_value !== undefined) {
					cut_summary.materials[material_key].thickness_values.push(flt(summary.thickness_value));
				}

				if (summary.density_value !== null && summary.density_value !== undefined) {
					cut_summary.materials[material_key].density_values.push(flt(summary.density_value));
				}

				cut_summary.volume += flt(summary.volume);
				cut_summary.tonnes += flt(summary.tonnes);
			}

			for (const value of this.material_values) {
				if (!block_name_set.has(value.mining_block)) {
					continue;
				}

				if (value.value_type !== "Quality") {
					continue;
				}

				const quality_key = value.variable_code || value.variable_name || __("Quality");

				if (!cut_summary.qualities[quality_key]) {
					cut_summary.qualities[quality_key] = {
						variable_code: quality_key,
						variable_name: value.variable_name || "",
						values: []
					};
				}

				if (value.avg_value !== null && value.avg_value !== undefined) {
					cut_summary.qualities[quality_key].values.push(flt(value.avg_value));
				}
			}

			if (!cut_summary.volume) {
				for (const block of blocks) {
					cut_summary.volume += flt(block.total_volume);
				}
			}

			if (!cut_summary.tonnes) {
				for (const block of blocks) {
					cut_summary.tonnes += flt(block.total_tonnes);
				}
			}

			if (cut_summary.volume) {
				cut_summary.average_density = cut_summary.tonnes / cut_summary.volume;
			}

			overall.block_count += cut_summary.block_count;
			overall.effective_area += cut_summary.effective_area;
			overall.volume += cut_summary.volume;
			overall.tonnes += cut_summary.tonnes;

			for (const quality_key of Object.keys(cut_summary.qualities)) {
				if (!overall.qualities[quality_key]) {
					overall.qualities[quality_key] = [];
				}

				overall.qualities[quality_key] = overall.qualities[quality_key].concat(
					cut_summary.qualities[quality_key].values
				);
			}

			cuts.push(cut_summary);
		}

		if (overall.volume) {
			overall.average_density = overall.tonnes / overall.volume;
		}

		return {
			overall: overall,
			cuts: cuts
		};
	}

	render_selection_summary_html(summary) {
		const overall_quality_html = this.render_quality_summary_rows(summary.overall.qualities);

		const cut_cards_html = summary.cuts.map((cut) => {
			const material_rows = Object.values(cut.materials).map((material) => {
				const avg_thickness = this.average(material.thickness_values);
				const avg_density = this.average(material.density_values);

				return `
					<tr>
						<td>${frappe.utils.escape_html(material.material_seam)}</td>
						<td>${format_number(material.effective_area || 0, null, 2)}</td>
						<td>${format_number(avg_thickness || 0, null, 3)}</td>
						<td>${format_number(material.volume || 0, null, 2)}</td>
						<td>${format_number(avg_density || 0, null, 3)}</td>
						<td>${format_number(material.tonnes || 0, null, 2)}</td>
					</tr>
				`;
			}).join("");

			const quality_rows = this.render_quality_summary_rows(cut.qualities);

			const block_rows = cut.blocks.map((block) => {
				return `
					<div class="selection-summary-block-row">
						<span class="selector-seq-pill">${block.sequence_no}</span>
						<span>${frappe.utils.escape_html(block.title)}</span>
					</div>
				`;
			}).join("");

			return `
				<div class="selection-summary-card">
					<div class="selection-summary-title">
						<h4>${frappe.utils.escape_html(cut.cut)}</h4>
						<span class="text-muted">${cut.block_count} ${__("blocks")}</span>
					</div>

					<div class="selection-summary-metrics">
						${this.metric_html(__("Effective Area"), format_number(cut.effective_area || 0, null, 2))}
						${this.metric_html(__("Volume"), format_number(cut.volume || 0, null, 2))}
						${this.metric_html(__("Tonnes"), format_number(cut.tonnes || 0, null, 2))}
						${this.metric_html(__("Avg Density"), format_number(cut.average_density || 0, null, 3))}
					</div>

					<div class="selection-summary-section-title">${__("Blocks")}</div>
					<div class="selection-summary-block-list">
						${block_rows || `<span class="text-muted">${__("No blocks")}</span>`}
					</div>

					<div class="selection-summary-section-title">${__("Materials")}</div>
					<table class="selection-summary-table">
						<thead>
							<tr>
								<th>${__("Material")}</th>
								<th>${__("Area")}</th>
								<th>${__("Thick")}</th>
								<th>${__("Vol")}</th>
								<th>${__("Dens")}</th>
								<th>${__("Tonnes")}</th>
							</tr>
						</thead>
						<tbody>
							${material_rows || `<tr><td colspan="6" class="text-muted">${__("No material rows")}</td></tr>`}
						</tbody>
					</table>

					<div class="selection-summary-section-title">${__("Qualities")}</div>
					<table class="selection-summary-table">
						<thead>
							<tr>
								<th>${__("Quality")}</th>
								<th>${__("Average")}</th>
								<th>${__("Count")}</th>
							</tr>
						</thead>
						<tbody>
							${quality_rows || `<tr><td colspan="3" class="text-muted">${__("No quality rows")}</td></tr>`}
						</tbody>
					</table>
				</div>
			`;
		}).join("");

		return `
			<div>
				<div class="selection-summary-overall">
					<h4 style="margin-top: 0;">${__("Overall Selection")}</h4>
					<div class="selection-summary-metrics">
						${this.metric_html(__("Blocks"), format_number(summary.overall.block_count || 0, null, 0))}
						${this.metric_html(__("Effective Area"), format_number(summary.overall.effective_area || 0, null, 2))}
						${this.metric_html(__("Volume"), format_number(summary.overall.volume || 0, null, 2))}
						${this.metric_html(__("Tonnes"), format_number(summary.overall.tonnes || 0, null, 2))}
						${this.metric_html(__("Avg Density"), format_number(summary.overall.average_density || 0, null, 3))}
					</div>

					<div class="selection-summary-section-title">${__("Overall Qualities")}</div>
					<table class="selection-summary-table">
						<thead>
							<tr>
								<th>${__("Quality")}</th>
								<th>${__("Average")}</th>
								<th>${__("Count")}</th>
							</tr>
						</thead>
						<tbody>
							${overall_quality_html || `<tr><td colspan="3" class="text-muted">${__("No quality rows")}</td></tr>`}
						</tbody>
					</table>
				</div>

				<div class="selection-summary-grid">
					${cut_cards_html}
				</div>
			</div>
		`;
	}

	render_quality_summary_rows(qualities) {
		return Object.keys(qualities || {}).map((quality_key) => {
			let values = [];

			if (Array.isArray(qualities[quality_key])) {
				values = qualities[quality_key];
			} else {
				values = qualities[quality_key].values || [];
			}

			const avg = this.average(values);

			return `
				<tr>
					<td>${frappe.utils.escape_html(quality_key)}</td>
					<td>${format_number(avg || 0, null, 3)}</td>
					<td>${values.length}</td>
				</tr>
			`;
		}).join("");
	}

	metric_html(label, value) {
		return `
			<div class="selection-summary-metric">
				<div class="selection-summary-metric-label">${frappe.utils.escape_html(label)}</div>
				<div class="selection-summary-metric-value">${value}</div>
			</div>
		`;
	}

	group_selection_by_cut() {
		const grouped = {};

		for (const entry of this.selected_block_order) {
			const cut = entry.dependency_group || __("No Cut");

			if (!grouped[cut]) {
				grouped[cut] = [];
			}

			grouped[cut].push(entry);
		}

		return grouped;
	}

	average(values) {
		const clean = (values || [])
			.map((value) => flt(value))
			.filter((value) => !isNaN(value));

		if (!clean.length) {
			return 0;
		}

		return clean.reduce((total, value) => total + value, 0) / clean.length;
	}

	get_selected_blocks() {
		return this.selected_block_order
			.map((entry) => this.block_by_name[entry.name])
			.filter((block) => Boolean(block));
	}

	get_block_title(block) {
		return block.mining_block_code || block.name || "";
	}

	clear_selection() {
		this.selected_blocks = new Set();
		this.selected_block_order = [];
		this.refresh_selected_styles();
		this.update_totals();
		this.render_selected_list();
		this.render_material_list();
		this.render_sequence_badges();
	}

	prompt_save_selection() {
		if (!this.selected_block_order.length) {
			frappe.msgprint(__("Please select at least one Mining Block."));
			return;
		}

		const geo_project = this.geo_project_control.get_value();
		const geo_pit_layout = this.geo_pit_layout_control.get_value();
		const material_stack = this.material_stack_control.get_value();
		const material_seam = this.material_seam_control.get_value();

		if (!geo_project || !geo_pit_layout || !material_stack) {
			frappe.msgprint(__("Please select Geo Project, Geo Pit Layout and Material Stack."));
			return;
		}

		const dialog = new frappe.ui.Dialog({
			title: __("Save Mining Schedule Selection"),
			fields: [
				{
					fieldtype: "Data",
					fieldname: "selection_name",
					label: __("Selection Name"),
					reqd: 1
				},
				{
					fieldtype: "Select",
					fieldname: "selection_type",
					label: __("Selection Type"),
					options: [
						"",
						"Option 1",
						"Option 2",
						"Option 3",
						"Option 4",
						"Option 5",
						"Option 6",
						"Weekly Plan",
						"3 Monthly Plan",
						"Yearly Plan",
						"Permit Area",
						"Draft Option",
						"Short Term Plan",
						"Monthly Plan",
						"Custom"
					].join("\n"),
					default: "Draft Option",
					reqd: 1
				},
				{
					fieldtype: "Small Text",
					fieldname: "remarks",
					label: __("Remarks")
				}
			],
			primary_action_label: __("Save Selection"),
			primary_action: (values) => {
				dialog.hide();
				this.save_selection(values);
			}
		});

		dialog.show();
	}

	save_selection(values) {
		const selected_blocks = this.selected_block_order.map((entry) => {
			return {
				name: entry.name,
				dependency_group: entry.dependency_group,
				sequence_no: entry.sequence_no
			};
		});

		frappe.call({
			method: "is_production.geo_planning.page.mining_block_selecto.mining_block_selecto.save_selection",
			args: {
				selection_name: values.selection_name,
				selection_type: values.selection_type,
				geo_project: this.geo_project_control.get_value(),
				geo_pit_layout: this.geo_pit_layout_control.get_value(),
				material_stack: this.material_stack_control.get_value(),
				material_seam: this.material_seam_control.get_value(),
				remarks: values.remarks,
				selected_blocks: JSON.stringify(selected_blocks)
			},
			freeze: true,
			freeze_message: __("Saving Selection..."),
			callback: (r) => {
				const result = r.message || {};

				if (!result.name) {
					frappe.msgprint(__("Selection was saved, but no document name was returned."));
					return;
				}

				frappe.show_alert({
					message: __("Selection {0} saved.", [result.name]),
					indicator: "green"
				});

				frappe.confirm(
					__("Open saved Mining Schedule Selection?"),
					() => {
						frappe.set_route("Form", "Mining Schedule Selection", result.name);
					}
				);
			}
		});
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

	update_status(message) {
		this.wrapper.find('[data-role="map_status"]').text(message || "");
	}
}