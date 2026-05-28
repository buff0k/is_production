frappe.pages["geo-planning-viewer"].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Geo Planning Viewer",
		single_column: true
	});

	new GeoPlanningViewerPage(page);
};

class GeoPlanningViewerPage {
	constructor(page) {
		this.page = page;
		this.wrapper = $(page.body);

		this.points = [];
		this.heatmapMetrics = null;
		this.pitOutlinePoints = [];
		this.previewBlocks = [];

		this.hoverPoint = null;
		this.hoverBlock = null;
		this.selectedBlock = null;

		this.showPoints = true;
		this.showPitOutline = true;
		this.showBlocks = true;
		this.rotateViewMode = false;

		this.filters = {};

		this.canvas = null;
		this.ctx = null;
		this.hoverBox = null;

		this.pixelRatio = Math.max(1, Math.min(window.devicePixelRatio || 1, 3));
		this.canvasCssWidth = 900;
		this.canvasCssHeight = 620;

		this.heatmapMetrics = null;

		this.view = {
			scale: 1,
			offsetX: 0,
			offsetY: 0,
			rotation: 0,
			isDragging: false,
			isRotating: false,
			dragMoved: false,
			lastX: 0,
			lastY: 0,
			startAngle: 0,
			startRotation: 0
		};

		this.make();
	}

	make() {
		this.make_layout();
		this.make_controls();
		this.setup_queries();
		this.bind_actions();
		this.resize_canvas();
		this.setup_resize();
		this.draw();
	}

	make_layout() {
		this.wrapper.html(`
			<style>
				.geo-viewer-shell {
					height: calc(100vh - 86px);
					display: grid;
					grid-template-columns: 315px 1fr;
					gap: 10px;
					padding: 8px;
					background: #f6f7f9;
				}

				.geo-side-panel {
					background: #fff;
					border: 1px solid #e0e0e0;
					border-radius: 10px;
					padding: 12px;
					overflow-y: auto;
					box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
				}

				.geo-side-title {
					font-size: 15px;
					font-weight: 700;
					margin-bottom: 4px;
				}

				.geo-side-subtitle {
					font-size: 11px;
					color: #777;
					line-height: 1.35;
					margin-bottom: 10px;
				}

				.geo-filter-section {
					border-top: 1px solid #eee;
					padding-top: 10px;
					margin-top: 10px;
				}

				.geo-filter-slot {
					margin-bottom: 9px;
				}

				.geo-button-row {
					display: grid;
					grid-template-columns: 1fr 1fr;
					gap: 6px;
					margin-top: 8px;
				}

				.geo-button-row .btn {
					width: 100%;
				}

				.geo-button-row .btn.geo-active-tool {
					background: #111;
					color: #fff;
					border-color: #111;
				}

				.geo-note {
					padding: 8px;
					border-radius: 8px;
					background: #fff8e1;
					border: 1px solid #ead89a;
					font-size: 11px;
					line-height: 1.4;
					color: #4d4218;
					margin-top: 8px;
				}

				.geo-selected-info {
					margin-top: 8px;
					padding: 8px;
					border: 1px dashed #bbb;
					border-radius: 7px;
					font-size: 11px;
					color: #444;
					background: #fafafa;
				}

				.geo-main-panel {
					position: relative;
					min-width: 0;
					background: #fff;
					border: 1px solid #e0e0e0;
					border-radius: 10px;
					overflow: hidden;
					box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
				}

				.geo-canvas-wrap {
					position: absolute;
					inset: 0;
					background: #fbfbfb;
					overflow: hidden;
				}

				#geo_canvas {
					width: 100%;
					height: 100%;
					display: block;
					cursor: grab;
				}

				#geo_canvas.dragging {
					cursor: grabbing;
				}

				.geo-info-box {
					position: absolute;
					top: 12px;
					left: 12px;
					background: rgba(255, 255, 255, 0.95);
					border: 1px solid #ddd;
					border-radius: 8px;
					padding: 9px 11px;
					font-size: 12px;
					line-height: 1.45;
					pointer-events: none;
					box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
					min-width: 240px;
					max-width: 420px;
				}

				.geo-hover-box {
					position: absolute;
					display: none;
					background: rgba(20, 20, 20, 0.92);
					color: #fff;
					border-radius: 7px;
					padding: 8px 10px;
					font-size: 12px;
					line-height: 1.45;
					pointer-events: none;
					z-index: 5;
					box-shadow: 0 3px 10px rgba(0, 0, 0, 0.2);
					max-width: 360px;
				}

				.geo-legend {
					position: absolute;
					right: 12px;
					bottom: 12px;
					background: rgba(255, 255, 255, 0.96);
					border: 1px solid #ddd;
					border-radius: 9px;
					padding: 10px 12px;
					font-size: 12px;
					pointer-events: none;
					min-width: 270px;
					box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
				}

				.geo-legend-title {
					font-weight: 700;
					margin-bottom: 3px;
				}

				.geo-legend-subtitle {
					color: #555;
					margin-bottom: 8px;
					max-width: 245px;
					white-space: nowrap;
					overflow: hidden;
					text-overflow: ellipsis;
				}

				.geo-legend-bar {
					width: 245px;
					height: 15px;
					background: linear-gradient(to right, blue, cyan, lime, yellow, red);
					border: 1px solid #aaa;
					margin: 4px 0;
				}

				.geo-legend-ticks {
					width: 245px;
					display: flex;
					justify-content: space-between;
					font-size: 10px;
					color: #333;
				}

				.geo-legend-stats {
					margin-top: 8px;
					display: grid;
					grid-template-columns: 1fr 1fr;
					gap: 3px 10px;
				}

				.geo-help-text {
					font-size: 11px;
					color: #777;
					line-height: 1.35;
					margin-top: 4px;
				}

				@media (max-width: 1000px) {
					.geo-viewer-shell {
						grid-template-columns: 1fr;
						height: auto;
					}

					.geo-main-panel {
						height: 700px;
					}
				}
			</style>

			<div class="geo-viewer-shell">
				<div class="geo-side-panel">
					<div class="geo-side-title">Geo Planning Viewer</div>
					<div class="geo-side-subtitle">
						Light visual viewer. Reads imported points and optional pit outline only. Nothing is saved from this page.
					</div>

					<div class="geo-filter-slot" id="geo_project_filter"></div>
					<div class="geo-filter-slot" id="geo_import_batch_filter"></div>

					<div class="geo-filter-section">
						<div class="geo-filter-slot" id="pit_outline_batch_filter"></div>
						<div class="geo-filter-slot" id="pit_outline_mode_filter"></div>
						<div class="geo-help-text">
							Use <b>Point Order</b> for a proper permit/pit boundary. Use <b>Convex Hull</b> only for unordered points.
						</div>
					</div>

					<div class="geo-filter-section">
						<div class="geo-filter-slot" id="block_size_filter"></div>
						<div class="geo-filter-slot" id="block_angle_filter"></div>
						<div class="geo-filter-slot" id="minimum_inside_filter"></div>
						<div class="geo-help-text">
							Preview blocks are drawn in the browser only. They are not saved.
						</div>
					</div>

					<div class="geo-button-row">
						<button class="btn btn-primary btn-sm" id="load_view">Load View</button>
						<button class="btn btn-default btn-sm" id="fit_view">Fit</button>
						<button class="btn btn-default btn-sm" id="preview_blocks">Preview Blocks</button>
						<button class="btn btn-default btn-sm" id="clear_blocks">Clear Blocks</button>
					</div>

					<div class="geo-button-row">
						<button class="btn btn-default btn-sm" id="toggle_points">Points On/Off</button>
						<button class="btn btn-default btn-sm" id="toggle_pit">Pit On/Off</button>
						<button class="btn btn-default btn-sm" id="toggle_blocks">Blocks On/Off</button>
						<button class="btn btn-default btn-sm" id="clear_view">Clear View</button>
					</div>

					<div class="geo-button-row">
						<button class="btn btn-default btn-sm" id="toggle_rotate_view">Rotate View</button>
						<button class="btn btn-default btn-sm" id="reset_rotation">Reset Rotation</button>
					</div>

					<div class="geo-note">
						Use this page to check imported data, permit overlays, block size and block angle visually before using the real Geo Pit Layout workflow.
					</div>

					<div class="geo-selected-info" id="selected_info">
						No preview block selected.
					</div>
				</div>

				<div class="geo-main-panel">
					<div class="geo-canvas-wrap" id="geo_canvas_wrap">
						<canvas id="geo_canvas"></canvas>

						<div class="geo-info-box" id="geo_info_box">
							No data loaded.
						</div>

						<div class="geo-hover-box" id="geo_hover_box"></div>

						<div class="geo-legend" id="geo_legend" style="display:none;">
							<div class="geo-legend-title">Z Value</div>
							<div class="geo-legend-subtitle" id="geo_legend_variable">No batch selected</div>
							<div class="geo-legend-bar"></div>
							<div class="geo-legend-ticks">
								<span id="geo_tick_0"></span>
								<span id="geo_tick_1"></span>
								<span id="geo_tick_2"></span>
								<span id="geo_tick_3"></span>
								<span id="geo_tick_4"></span>
							</div>
							<div class="geo-legend-stats">
								<div><b>Min:</b> <span id="geo_min_z"></span></div>
								<div><b>Max:</b> <span id="geo_max_z"></span></div>
								<div><b>Avg:</b> <span id="geo_avg_z"></span></div>
								<div><b>Range:</b> <span id="geo_range_z"></span></div>
							</div>
						</div>
					</div>
				</div>
			</div>
		`);

		this.canvas = document.getElementById("geo_canvas");
		this.ctx = this.canvas.getContext("2d");
		this.hoverBox = document.getElementById("geo_hover_box");
	}

	make_controls() {
		const make_control = (parent, df) => {
			return frappe.ui.form.make_control({
				parent: $(parent),
				df,
				render_input: true
			});
		};

		this.filters.geo_project = make_control("#geo_project_filter", {
			fieldtype: "Link",
			options: "Geo Project",
			label: "Project",
			fieldname: "geo_project",
			reqd: 1,
			change: () => {
				this.filters.geo_import_batch.set_value("");
				this.filters.pit_outline_batch.set_value("");
				this.clear_all_data();
				this.setup_queries();
			}
		});

		this.filters.geo_import_batch = make_control("#geo_import_batch_filter", {
			fieldtype: "Link",
			options: "Geo Import Batch",
			label: "Geo Import Batch",
			fieldname: "geo_import_batch",
			reqd: 1,
			description: "The imported model/variable batch to view."
		});

		this.filters.pit_outline_batch = make_control("#pit_outline_batch_filter", {
			fieldtype: "Link",
			options: "Geo Import Batch",
			label: "Pit Outline / Permit Batch",
			fieldname: "pit_outline_batch",
			description: "Optional. Imported boundary batch sent to Pit Outline Points."
		});

		this.filters.pit_outline_mode = make_control("#pit_outline_mode_filter", {
			fieldtype: "Select",
			label: "Pit Outline Mode",
			fieldname: "pit_outline_mode",
			options: "Point Order\nConvex Hull",
			default: "Point Order"
		});

		this.filters.block_size = make_control("#block_size_filter", {
			fieldtype: "Data",
			label: "Preview Block Size",
			fieldname: "block_size",
			default: "100 x 40",
			description: "Example: 100 x 40, 50 x 50, 20."
		});

		this.filters.block_angle = make_control("#block_angle_filter", {
			fieldtype: "Float",
			label: "Preview Block Angle",
			fieldname: "block_angle",
			default: 0,
			description: "Degrees. Visual only."
		});

		this.filters.minimum_inside = make_control("#minimum_inside_filter", {
			fieldtype: "Percent",
			label: "Minimum Inside %",
			fieldname: "minimum_inside",
			default: 50,
			description: "For visual pit-outline clipping only."
		});
	}

	setup_queries() {
		const get_project = () => this.filters.geo_project ? this.filters.geo_project.get_value() : "";

		if (this.filters.geo_import_batch) {
			this.filters.geo_import_batch.df.get_query = () => {
				return {
					query: "is_production.geo_planning.page.geo_planning_viewer.geo_planning_viewer.get_geo_import_batch_query",
					filters: {
						geo_project: get_project()
					}
				};
			};
		}

		if (this.filters.pit_outline_batch) {
			this.filters.pit_outline_batch.df.get_query = () => {
				return {
					query: "is_production.geo_planning.page.geo_planning_viewer.geo_planning_viewer.get_pit_outline_batch_query",
					filters: {
						geo_project: get_project()
					}
				};
			};
		}
	}

	bind_actions() {
		$("#load_view").on("click", () => this.load_view());

		$("#fit_view").on("click", () => {
			this.fit_view();
			this.draw();
		});

		$("#preview_blocks").on("click", () => {
			this.generate_preview_blocks();
			this.draw();
		});

		$("#clear_blocks").on("click", () => {
			this.previewBlocks = [];
			this.selectedBlock = null;
			this.update_selected_info();
			this.draw();
		});

		$("#toggle_points").on("click", () => {
			this.showPoints = !this.showPoints;
			this.draw();
		});

		$("#toggle_pit").on("click", () => {
			this.showPitOutline = !this.showPitOutline;
			this.draw();
		});

		$("#toggle_blocks").on("click", () => {
			this.showBlocks = !this.showBlocks;
			this.draw();
		});

		$("#clear_view").on("click", () => {
			this.clear_all_data();
			this.draw();
		});

		$("#toggle_rotate_view").on("click", (event) => {
			this.rotateViewMode = !this.rotateViewMode;
			$(event.currentTarget).toggleClass("geo-active-tool", this.rotateViewMode);
			this.canvas.style.cursor = this.rotateViewMode ? "crosshair" : "grab";
		});

		$("#reset_rotation").on("click", () => {
			this.view.rotation = 0;
			this.draw();
		});

		this.bind_canvas_events();
	}

	setup_resize() {
		window.addEventListener("resize", () => this.resize_canvas());
		setTimeout(() => this.resize_canvas(), 100);
	}

	resize_canvas() {
		const wrap = document.getElementById("geo_canvas_wrap");

		if (!wrap || !this.canvas) {
			return;
		}

		const rect = wrap.getBoundingClientRect();
		const cssWidth = Math.max(900, Math.floor(rect.width));
		const cssHeight = Math.max(620, Math.floor(rect.height));
		const nextPixelRatio = Math.max(1, Math.min(window.devicePixelRatio || 1, 3));
		const bufferWidth = Math.floor(cssWidth * nextPixelRatio);
		const bufferHeight = Math.floor(cssHeight * nextPixelRatio);

		this.pixelRatio = nextPixelRatio;
		this.canvasCssWidth = cssWidth;
		this.canvasCssHeight = cssHeight;

		this.canvas.style.width = `${cssWidth}px`;
		this.canvas.style.height = `${cssHeight}px`;

		if (this.canvas.width !== bufferWidth || this.canvas.height !== bufferHeight) {
			this.canvas.width = bufferWidth;
			this.canvas.height = bufferHeight;
		}

		if (this.points.length || this.pitOutlinePoints.length || this.previewBlocks.length) {
			this.fit_view();
		}

		this.draw();
	}

	clear_all_data() {
		this.points = [];
		this.heatmapMetrics = null;
		this.pitOutlinePoints = [];
		this.previewBlocks = [];
		this.hoverPoint = null;
		this.hoverBlock = null;
		this.selectedBlock = null;
		this.hide_hover_box();
		this.update_selected_info();
	}

	load_view() {
		const geo_project = this.filters.geo_project.get_value();
		const geo_import_batch = this.filters.geo_import_batch.get_value();
		const pit_outline_batch = this.filters.pit_outline_batch.get_value();

		if (!geo_project) {
			frappe.msgprint("Please select a Project.");
			return;
		}

		if (!geo_import_batch && !pit_outline_batch) {
			frappe.msgprint("Please select a Geo Import Batch, a Pit Outline batch, or both.");
			return;
		}

		this.clear_all_data();

		const calls = [];

		frappe.dom.freeze("Loading viewer data...");

		if (geo_import_batch) {
			calls.push(this.load_import_batch_points());
		}

		if (pit_outline_batch) {
			calls.push(this.load_pit_outline_points());
		}

		Promise.allSettled(calls).then((results) => {
			frappe.dom.unfreeze();

			const failed = results.filter(r => r.status === "rejected");

			if (failed.length) {
				console.error("Geo Planning Viewer load errors:", failed);

				frappe.msgprint({
					title: "Partial Load Warning",
					indicator: "orange",
					message: "Some layers could not load, but successful layers will still be shown."
				});
			}

			this.fit_view();
			this.draw();
		});
	}

	load_import_batch_points() {
		return new Promise((resolve, reject) => {
			frappe.call({
				method: "is_production.geo_planning.page.geo_planning_viewer.geo_planning_viewer.get_import_batch_points",
				args: {
					geo_project: this.filters.geo_project.get_value(),
					geo_import_batch: this.filters.geo_import_batch.get_value()
				},
				callback: (r) => {
					this.points = (r.message || []).map(p => ({
						name: p.name || "",
						x: Number(p.x),
						y: Number(p.y),
						z: Number(p.z || 0),
						variable_name: p.variable_name || p.full_name || p.variable_code || "",
						variable_code: p.variable_code || "",
						full_name: p.full_name || "",
						version_tag: p.version_tag || "",
						batch: p.geo_import_batch || p.import_batch || "",
						geo_model_output: p.geo_model_output || "",
						row_no: p.row_no
					})).filter(p => isFinite(p.x) && isFinite(p.y) && isFinite(p.z));

					this.heatmapMetrics = this.calculate_heatmap_metrics(this.points);

					resolve();
				},
				error: (err) => reject(err)
			});
		});
	}

	load_pit_outline_points() {
		return new Promise((resolve, reject) => {
			frappe.call({
				method: "is_production.geo_planning.page.geo_planning_viewer.geo_planning_viewer.get_pit_outline_points",
				args: {
					geo_project: this.filters.geo_project.get_value(),
					geo_import_batch: this.filters.pit_outline_batch.get_value(),
					outline_mode: this.filters.pit_outline_mode.get_value() || "Point Order"
				},
				callback: (r) => {
					this.pitOutlinePoints = (r.message || []).map(p => ({
						name: p.name || "",
						x: Number(p.x),
						y: Number(p.y),
						z: Number(p.z || 0),
						row_no: p.row_no,
						source_point_no: p.source_point_no,
						source_line_no: p.source_line_no,
						source_x: p.source_x,
						source_y: p.source_y,
						latitude: p.latitude,
						longitude: p.longitude,
						variable_name: p.variable_name || p.full_name || p.variable_code || "",
						version_tag: p.version_tag || "",
						batch: p.geo_import_batch || p.import_batch || "",
						coordinate_transform: p.coordinate_transform || ""
					})).filter(p => isFinite(p.x) && isFinite(p.y));

					resolve();
				},
				error: (err) => reject(err)
			});
		});
	}

	parse_size(value) {
		if (!value) {
			return null;
		}

		let clean = String(value).trim().toLowerCase();

		if (!clean) {
			return null;
		}

		clean = clean
			.replace(/×/g, "x")
			.replace(/\*/g, "x")
			.replace(/,/g, ".")
			.replace(/\s+/g, " ");

		let x_size = 0;
		let y_size = 0;

		if (clean.includes("x")) {
			const parts = clean.split("x").map(p => p.trim()).filter(Boolean);

			if (parts.length >= 2) {
				x_size = Number(parts[0]);
				y_size = Number(parts[1]);
			}
		} else {
			x_size = Number(clean);
			y_size = x_size;
		}

		if (!isFinite(x_size) || !isFinite(y_size) || x_size <= 0 || y_size <= 0) {
			return null;
		}

		return {
			x: x_size,
			y: y_size,
			label: `${x_size} x ${y_size}`
		};
	}

	get_block_size() {
		return this.parse_size(this.filters.block_size.get_value()) || {
			x: 100,
			y: 40,
			label: "100 x 40"
		};
	}

	get_angle_radians() {
		return Number(this.filters.block_angle.get_value() || 0) * Math.PI / 180;
	}

	rotate_to_local(point, anchor, angle) {
		const dx = point.x - anchor.x;
		const dy = point.y - anchor.y;
		const cos = Math.cos(-angle);
		const sin = Math.sin(-angle);

		return {
			x: dx * cos - dy * sin,
			y: dx * sin + dy * cos
		};
	}

	local_to_world(local, anchor, angle) {
		const cos = Math.cos(angle);
		const sin = Math.sin(angle);

		return {
			x: anchor.x + local.x * cos - local.y * sin,
			y: anchor.y + local.x * sin + local.y * cos
		};
	}

	get_generation_source_points() {
		if (this.pitOutlinePoints.length >= 3) {
			return this.pitOutlinePoints;
		}

		return this.points;
	}

	get_generation_bounds_local(anchor, angle) {
		const source = this.get_generation_source_points();

		if (!source.length) {
			return null;
		}

		const locals = source.map(p => this.rotate_to_local(p, anchor, angle));

		return {
			minX: Math.min(...locals.map(p => p.x)),
			maxX: Math.max(...locals.map(p => p.x)),
			minY: Math.min(...locals.map(p => p.y)),
			maxY: Math.max(...locals.map(p => p.y))
		};
	}

	get_anchor() {
		const source = this.get_generation_source_points();

		if (!source.length) {
			return { x: 0, y: 0 };
		}

		return {
			x: Math.min(...source.map(p => p.x)),
			y: Math.min(...source.map(p => p.y))
		};
	}

	generate_preview_blocks() {
		const block_size = this.get_block_size();
		const angle = this.get_angle_radians();
		const anchor = this.get_anchor();
		const bounds = this.get_generation_bounds_local(anchor, angle);
		const min_inside = Number(this.filters.minimum_inside.get_value() || 0);

		if (!bounds) {
			frappe.msgprint("Please load a Geo Import Batch or Pit Outline first.");
			return;
		}

		this.previewBlocks = [];

		const start_col = Math.floor(bounds.minX / block_size.x) - 1;
		const end_col = Math.ceil(bounds.maxX / block_size.x) + 1;
		const start_row = Math.floor(bounds.minY / block_size.y) - 1;
		const end_row = Math.ceil(bounds.maxY / block_size.y) + 1;

		let block_no = 1;

		if (this.pitOutlinePoints.length >= 3) {
			for (let row = start_row; row <= end_row; row++) {
				for (let col = start_col; col <= end_col; col++) {
					const block = this.make_block_from_row_col(row, col, block_size, anchor, angle, block_no);
					const inside_percent = this.estimate_block_inside_percent(block, this.pitOutlinePoints);

					if (inside_percent >= min_inside) {
						block.inside_percent = inside_percent;
						block.block_no = block_no;
						block.label = `B${block_no}`;
						this.previewBlocks.push(block);
						block_no += 1;
					}
				}
			}
		} else {
			const bucket = {};

			for (const point of this.points) {
				const local = this.rotate_to_local(point, anchor, angle);
				const col = Math.floor(local.x / block_size.x);
				const row = Math.floor(local.y / block_size.y);
				const key = `${row}|${col}`;

				if (!bucket[key]) {
					bucket[key] = {
						row,
						col,
						points: []
					};
				}

				bucket[key].points.push(point);
			}

			const keys = Object.keys(bucket).sort();

			for (const key of keys) {
				const item = bucket[key];
				const block = this.make_block_from_row_col(item.row, item.col, block_size, anchor, angle, block_no);

				block.point_count = item.points.length;
				block.inside_percent = 100;
				block.block_no = block_no;
				block.label = `B${block_no}`;

				this.previewBlocks.push(block);
				block_no += 1;
			}
		}

		this.selectedBlock = null;
		this.update_selected_info();

		frappe.show_alert({
			message: `Previewed ${this.previewBlocks.length.toLocaleString()} visual block(s). Nothing was saved.`,
			indicator: "green"
		});
	}

	make_block_from_row_col(row, col, block_size, anchor, angle, block_no) {
		const x0 = col * block_size.x;
		const y0 = row * block_size.y;

		const local_corners = [
			{ x: x0, y: y0 },
			{ x: x0 + block_size.x, y: y0 },
			{ x: x0 + block_size.x, y: y0 + block_size.y },
			{ x: x0, y: y0 + block_size.y }
		];

		const corners = local_corners.map(p => this.local_to_world(p, anchor, angle));

		const centroid = this.local_to_world(
			{
				x: x0 + block_size.x / 2,
				y: y0 + block_size.y / 2
			},
			anchor,
			angle
		);

		return {
			row,
			col,
			block_no,
			label: `B${block_no}`,
			x: centroid.x,
			y: centroid.y,
			width: block_size.x,
			height: block_size.y,
			angle_degrees: Number(this.filters.block_angle.get_value() || 0),
			corners,
			point_count: 0,
			inside_percent: 0,
			area: block_size.x * block_size.y
		};
	}

	estimate_block_inside_percent(block, polygon) {
		if (!polygon || polygon.length < 3) {
			return 100;
		}

		const samples = [];

		const c = this.get_block_centroid(block);
		samples.push(c);

		for (const corner of block.corners) {
			samples.push(corner);
		}

		for (let i = 0; i < block.corners.length; i++) {
			const a = block.corners[i];
			const b = block.corners[(i + 1) % block.corners.length];

			samples.push({
				x: (a.x + b.x) / 2,
				y: (a.y + b.y) / 2
			});
		}

		const inside = samples.filter(p => this.point_in_polygon(p, polygon)).length;

		return inside / samples.length * 100;
	}

	get_all_visible_points() {
		const all = [];

		for (const p of this.points) {
			all.push(p);
		}

		if (this.showPitOutline) {
			for (const p of this.pitOutlinePoints) {
				all.push(p);
			}
		}

		for (const block of this.previewBlocks) {
			for (const corner of block.corners || []) {
				all.push(corner);
			}
		}

		return all;
	}

	get_bounds() {
		const all = this.get_all_visible_points();

		if (!all.length) {
			return null;
		}

		return {
			minX: Math.min(...all.map(p => p.x)),
			maxX: Math.max(...all.map(p => p.x)),
			minY: Math.min(...all.map(p => p.y)),
			maxY: Math.max(...all.map(p => p.y))
		};
	}

	get_stats() {
		if (!this.points.length) {
			return null;
		}

		const zs = this.points.map(p => p.z);
		const minZ = Math.min(...zs);
		const maxZ = Math.max(...zs);
		const sumZ = zs.reduce((a, b) => a + b, 0);

		return {
			minZ,
			maxZ,
			avgZ: sumZ / zs.length,
			rangeZ: maxZ - minZ
		};
	}

	get_canvas_width() {
		return this.canvasCssWidth || Math.max(1, Math.floor((this.canvas ? this.canvas.width : 900) / (this.pixelRatio || 1)));
	}

	get_canvas_height() {
		return this.canvasCssHeight || Math.max(1, Math.floor((this.canvas ? this.canvas.height : 620) / (this.pixelRatio || 1)));
	}

	calculate_heatmap_metrics(points) {
		if (!points || points.length < 2) {
			return null;
		}

		const xValues = points.map(p => p.x).filter(isFinite).sort((a, b) => a - b);
		const yValues = points.map(p => p.y).filter(isFinite).sort((a, b) => a - b);
		const xStep = this.get_representative_spacing(xValues);
		const yStep = this.get_representative_spacing(yValues);
		const fallback = xStep || yStep || 1;

		return {
			xStep: xStep || fallback,
			yStep: yStep || fallback
		};
	}

	get_representative_spacing(sortedValues) {
		if (!sortedValues || sortedValues.length < 2) {
			return 0;
		}

		const deltas = [];
		let previous = sortedValues[0];

		for (let i = 1; i < sortedValues.length; i++) {
			const value = sortedValues[i];
			const delta = value - previous;

			if (delta > 0.000001 && isFinite(delta)) {
				deltas.push(delta);
			}

			previous = value;
		}

		if (!deltas.length) {
			return 0;
		}

		deltas.sort((a, b) => a - b);
		const index = Math.min(deltas.length - 1, Math.max(0, Math.floor(deltas.length * 0.10)));
		return deltas[index];
	}

	get_heatmap_cell_size() {
		if (!this.heatmapMetrics) {
			this.heatmapMetrics = this.calculate_heatmap_metrics(this.points);
		}

		const metrics = this.heatmapMetrics || { xStep: 1, yStep: 1 };

		return {
			x: metrics.xStep * 1.04,
			y: metrics.yStep * 1.04
		};
	}

	draw_heatmap_cell(point, cellSize, fillStyle) {
		const ctx = this.ctx;
		const halfX = cellSize.x / 2;
		const halfY = cellSize.y / 2;
		const cw = this.get_canvas_width();
		const ch = this.get_canvas_height();

		if (!this.view.rotation) {
			const s = this.world_to_screen(point);
			const w = Math.max(1.15, cellSize.x * this.view.scale);
			const h = Math.max(1.15, cellSize.y * this.view.scale);

			if (s.x + w / 2 < -30 || s.x - w / 2 > cw + 30 || s.y + h / 2 < -30 || s.y - h / 2 > ch + 30) {
				return;
			}

			ctx.fillStyle = fillStyle;
			ctx.fillRect(s.x - w / 2, s.y - h / 2, w, h);
			return;
		}

		const corners = [
			{ x: point.x - halfX, y: point.y - halfY },
			{ x: point.x + halfX, y: point.y - halfY },
			{ x: point.x + halfX, y: point.y + halfY },
			{ x: point.x - halfX, y: point.y + halfY }
		].map(p => this.world_to_screen(p));

		if (corners.every(s => s.x < -30 || s.x > cw + 30 || s.y < -30 || s.y > ch + 30)) {
			return;
		}

		ctx.beginPath();
		corners.forEach((s, index) => {
			if (index === 0) {
				ctx.moveTo(s.x, s.y);
			} else {
				ctx.lineTo(s.x, s.y);
			}
		});
		ctx.closePath();
		ctx.fillStyle = fillStyle;
		ctx.fill();
	}

	fit_view() {
		const b = this.get_bounds();

		if (!b) {
			return;
		}

		const pad = 70;
		const width = b.maxX - b.minX || 1;
		const height = b.maxY - b.minY || 1;
		const scaleX = (this.get_canvas_width() - pad * 2) / width;
		const scaleY = (this.get_canvas_height() - pad * 2) / height;

		this.view.scale = Math.min(scaleX, scaleY);

		const drawnWidth = width * this.view.scale;
		const drawnHeight = height * this.view.scale;

		this.view.offsetX = (this.get_canvas_width() - drawnWidth) / 2 - b.minX * this.view.scale;
		this.view.offsetY = (this.get_canvas_height() - drawnHeight) / 2 + b.maxY * this.view.scale;
	}

	rotate_screen_point(x, y) {
		if (!this.view.rotation) {
			return { x, y };
		}

		const cx = this.get_canvas_width() / 2;
		const cy = this.get_canvas_height() / 2;
		const dx = x - cx;
		const dy = y - cy;
		const cos = Math.cos(this.view.rotation);
		const sin = Math.sin(this.view.rotation);

		return {
			x: cx + dx * cos - dy * sin,
			y: cy + dx * sin + dy * cos
		};
	}

	unrotate_screen_point(x, y) {
		if (!this.view.rotation) {
			return { x, y };
		}

		const cx = this.get_canvas_width() / 2;
		const cy = this.get_canvas_height() / 2;
		const dx = x - cx;
		const dy = y - cy;
		const cos = Math.cos(-this.view.rotation);
		const sin = Math.sin(-this.view.rotation);

		return {
			x: cx + dx * cos - dy * sin,
			y: cy + dx * sin + dy * cos
		};
	}

	world_to_screen(point) {
		return this.rotate_screen_point(
			point.x * this.view.scale + this.view.offsetX,
			-point.y * this.view.scale + this.view.offsetY
		);
	}

	screen_to_world(x, y) {
		const p = this.unrotate_screen_point(x, y);

		return {
			x: (p.x - this.view.offsetX) / this.view.scale,
			y: -(p.y - this.view.offsetY) / this.view.scale
		};
	}

	value_colour(z, minZ, maxZ) {
		const t = (z - minZ) / (maxZ - minZ || 1);

		let r;
		let g;
		let b;

		if (t < 0.25) {
			r = 0;
			g = Math.round(255 * (t / 0.25));
			b = 255;
		} else if (t < 0.5) {
			r = 0;
			g = 255;
			b = Math.round(255 * (1 - ((t - 0.25) / 0.25)));
		} else if (t < 0.75) {
			r = Math.round(255 * ((t - 0.5) / 0.25));
			g = 255;
			b = 0;
		} else {
			r = 255;
			g = Math.round(255 * (1 - ((t - 0.75) / 0.25)));
			b = 0;
		}

		return `rgb(${r},${g},${b})`;
	}

	draw() {
		if (!this.ctx || !this.canvas) {
			return;
		}

		const ctx = this.ctx;
		const ratio = this.pixelRatio || 1;

		ctx.setTransform(1, 0, 0, 1, 0, 0);
		ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
		ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
		ctx.imageSmoothingEnabled = false;

		this.draw_background_grid();

		if (this.showPoints) {
			this.draw_points();
		}

		if (this.showPitOutline) {
			this.draw_pit_outline();
		}

		if (this.showBlocks) {
			this.draw_preview_blocks();
		}

		this.update_info_box();
		this.update_legend();
	}

	draw_background_grid() {
		const ctx = this.ctx;
		const step = 28;
		const cw = this.get_canvas_width();
		const ch = this.get_canvas_height();

		ctx.save();
		ctx.strokeStyle = "rgba(0, 0, 0, 0.05)";
		ctx.lineWidth = 1;

		for (let x = 0; x <= cw; x += step) {
			ctx.beginPath();
			ctx.moveTo(x, 0);
			ctx.lineTo(x, ch);
			ctx.stroke();
		}

		for (let y = 0; y <= ch; y += step) {
			ctx.beginPath();
			ctx.moveTo(0, y);
			ctx.lineTo(cw, y);
			ctx.stroke();
		}

		ctx.restore();
	}

	draw_points() {
		if (!this.points.length) {
			return;
		}

		const ctx = this.ctx;
		const stats = this.get_stats();
		const cellSize = this.get_heatmap_cell_size();

		ctx.save();
		ctx.globalAlpha = 1;

		for (const p of this.points) {
			const fillStyle = stats
				? this.value_colour(p.z, stats.minZ, stats.maxZ)
				: "rgba(80, 140, 220, 0.95)";

			this.draw_heatmap_cell(p, cellSize, fillStyle);
		}

		ctx.restore();
	}

	draw_pit_outline() {
		if (!this.pitOutlinePoints.length) {
			return;
		}

		const ctx = this.ctx;
		const points = this.pitOutlinePoints;

		ctx.save();

		if (points.length >= 3) {
			ctx.beginPath();

			points.forEach((p, index) => {
				const s = this.world_to_screen(p);

				if (index === 0) {
					ctx.moveTo(s.x, s.y);
				} else {
					ctx.lineTo(s.x, s.y);
				}
			});

			ctx.closePath();

			ctx.fillStyle = "rgba(243, 156, 18, 0.13)";
			ctx.strokeStyle = "rgba(230, 126, 34, 1)";
			ctx.lineWidth = 3;
			ctx.setLineDash([9, 6]);
			ctx.fill();
			ctx.stroke();
			ctx.setLineDash([]);
		}

		for (let i = 0; i < points.length; i++) {
			const p = points[i];
			const s = this.world_to_screen(p);

			ctx.beginPath();
			ctx.arc(s.x, s.y, 4.5, 0, Math.PI * 2);
			ctx.fillStyle = "rgba(230, 126, 34, 1)";
			ctx.strokeStyle = "#fff";
			ctx.lineWidth = 1.5;
			ctx.fill();
			ctx.stroke();

			ctx.fillStyle = "#222";
			ctx.font = "11px sans-serif";
			ctx.fillText(String(p.source_point_no || p.row_no || i + 1), s.x + 7, s.y - 7);
		}

		ctx.restore();
	}

	draw_preview_blocks() {
		if (!this.previewBlocks.length) {
			return;
		}

		const ctx = this.ctx;

		ctx.save();

		for (const block of this.previewBlocks) {
			if (!block.corners || block.corners.length < 3) {
				continue;
			}

			const isSelected = this.selectedBlock === block;
			const isHover = this.hoverBlock === block;

			ctx.beginPath();

			block.corners.forEach((p, index) => {
				const s = this.world_to_screen(p);

				if (index === 0) {
					ctx.moveTo(s.x, s.y);
				} else {
					ctx.lineTo(s.x, s.y);
				}
			});

			ctx.closePath();

			if (isSelected) {
				ctx.fillStyle = "rgba(46, 204, 113, 0.42)";
				ctx.strokeStyle = "rgba(39, 174, 96, 1)";
				ctx.lineWidth = 3;
			} else if (isHover) {
				ctx.fillStyle = "rgba(52, 152, 219, 0.34)";
				ctx.strokeStyle = "rgba(41, 128, 185, 1)";
				ctx.lineWidth = 2.5;
			} else {
				ctx.fillStyle = "rgba(80, 140, 220, 0.14)";
				ctx.strokeStyle = "rgba(80, 140, 220, 0.85)";
				ctx.lineWidth = 1.2;
			}

			ctx.fill();
			ctx.stroke();

			const c = this.get_block_centroid(block);
			const s = this.world_to_screen(c);

			ctx.fillStyle = "#111";
			ctx.font = "10px sans-serif";
			ctx.textAlign = "center";
			ctx.textBaseline = "middle";
			ctx.fillText(block.label || "", s.x, s.y);
		}

		ctx.restore();
	}

	update_info_box() {
		const stats = this.get_stats();
		const block_size = this.get_block_size();
		const angle = Number(this.filters.block_angle ? this.filters.block_angle.get_value() || 0 : 0);
		const outline_mode = this.filters.pit_outline_mode ? this.filters.pit_outline_mode.get_value() : "Point Order";

		let html = `
			<b>Geo Planning Viewer</b><br>
			Imported points: ${this.points.length.toLocaleString()}<br>
			Pit outline points: ${this.pitOutlinePoints.length.toLocaleString()}<br>
			Outline mode: ${frappe.utils.escape_html(outline_mode || "")}<br>
			Preview blocks: ${this.previewBlocks.length.toLocaleString()}<br>
			Block size: ${frappe.utils.escape_html(block_size.label)}<br>
			Block angle: ${this.format_number(angle, 2)}°<br>
			<span style="color:#777;">Read-only visual page. Nothing saved.</span>
		`;

		if (stats) {
			html += `
				<hr style="margin:6px 0;">
				Z Min: ${this.format_number(stats.minZ, 3)}<br>
				Z Max: ${this.format_number(stats.maxZ, 3)}<br>
				Z Avg: ${this.format_number(stats.avgZ, 3)}
			`;
		}

		$("#geo_info_box").html(html);
	}

	update_legend() {
		const stats = this.get_stats();

		if (!stats) {
			$("#geo_legend").hide();
			return;
		}

		$("#geo_legend").show();

		const variable = this.points[0]
			? this.points[0].variable_name || this.points[0].variable_code || "Z Value"
			: "Z Value";

		$("#geo_legend_variable").text(variable);
		$("#geo_min_z").text(this.format_number(stats.minZ, 3));
		$("#geo_max_z").text(this.format_number(stats.maxZ, 3));
		$("#geo_avg_z").text(this.format_number(stats.avgZ, 3));
		$("#geo_range_z").text(this.format_number(stats.rangeZ, 3));

		for (let i = 0; i <= 4; i++) {
			const value = stats.minZ + (stats.rangeZ * i / 4);
			$(`#geo_tick_${i}`).text(this.format_number(value, 1));
		}
	}

	bind_canvas_events() {
		this.canvas.addEventListener("mousedown", (event) => {
			const rect = this.canvas.getBoundingClientRect();
			const x = event.clientX - rect.left;
			const y = event.clientY - rect.top;

			this.view.dragMoved = false;
			this.view.lastX = x;
			this.view.lastY = y;

			if (this.rotateViewMode) {
				this.view.isRotating = true;
				this.view.startRotation = this.view.rotation;
				this.view.startAngle = Math.atan2(y - this.get_canvas_height() / 2, x - this.get_canvas_width() / 2);
				return;
			}

			this.view.isDragging = true;
			this.canvas.classList.add("dragging");
		});

		this.canvas.addEventListener("mousemove", (event) => {
			const rect = this.canvas.getBoundingClientRect();
			const x = event.clientX - rect.left;
			const y = event.clientY - rect.top;

			if (this.view.isRotating) {
				const angle = Math.atan2(y - this.get_canvas_height() / 2, x - this.get_canvas_width() / 2);
				this.view.rotation = this.view.startRotation + angle - this.view.startAngle;
				this.view.dragMoved = true;
				this.draw();
				return;
			}

			if (this.view.isDragging) {
				const dx = x - this.view.lastX;
				const dy = y - this.view.lastY;

				this.view.offsetX += dx;
				this.view.offsetY += dy;
				this.view.lastX = x;
				this.view.lastY = y;
				this.view.dragMoved = true;

				this.draw();
				return;
			}

			this.update_hover(x, y, event.clientX, event.clientY);
		});

		this.canvas.addEventListener("mouseup", (event) => {
			this.canvas.classList.remove("dragging");

			if (!this.view.dragMoved && !this.rotateViewMode) {
				const rect = this.canvas.getBoundingClientRect();
				const x = event.clientX - rect.left;
				const y = event.clientY - rect.top;

				this.select_block_at(x, y);
			}

			this.view.isDragging = false;
			this.view.isRotating = false;
		});

		this.canvas.addEventListener("mouseleave", () => {
			this.view.isDragging = false;
			this.view.isRotating = false;
			this.canvas.classList.remove("dragging");
			this.hide_hover_box();
		});

		this.canvas.addEventListener("wheel", (event) => {
			event.preventDefault();

			const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
			const rect = this.canvas.getBoundingClientRect();
			const sx = event.clientX - rect.left;
			const sy = event.clientY - rect.top;

			const before = this.screen_to_world(sx, sy);

			this.view.scale *= factor;
			this.view.scale = Math.max(0.0001, Math.min(this.view.scale, 100000));

			const after = this.screen_to_world(sx, sy);

			this.view.offsetX += (after.x - before.x) * this.view.scale;
			this.view.offsetY -= (after.y - before.y) * this.view.scale;

			this.draw();
		});
	}

	update_hover(screenX, screenY, clientX, clientY) {
		const world = this.screen_to_world(screenX, screenY);
		let block = null;

		for (let i = this.previewBlocks.length - 1; i >= 0; i--) {
			const candidate = this.previewBlocks[i];

			if (candidate.corners && this.point_in_polygon(world, candidate.corners)) {
				block = candidate;
				break;
			}
		}

		if (block) {
			this.hoverBlock = block;
			this.show_hover_box(
				clientX,
				clientY,
				`
					<b>${frappe.utils.escape_html(block.label || "")}</b><br>
					Row: ${block.row}<br>
					Column: ${block.col}<br>
					Inside: ${this.format_number(block.inside_percent, 1)}%<br>
					Area: ${this.format_number(block.area, 2)}
				`
			);
			this.draw();
			return;
		}

		this.hoverBlock = null;
		this.hide_hover_box();
		this.draw();
	}

	show_hover_box(clientX, clientY, html) {
		this.hoverBox.innerHTML = html;
		this.hoverBox.style.display = "block";

		const wrapRect = document.getElementById("geo_canvas_wrap").getBoundingClientRect();

		this.hoverBox.style.left = `${clientX - wrapRect.left + 14}px`;
		this.hoverBox.style.top = `${clientY - wrapRect.top + 14}px`;
	}

	hide_hover_box() {
		if (this.hoverBox) {
			this.hoverBox.style.display = "none";
		}
	}

	select_block_at(screenX, screenY) {
		const world = this.screen_to_world(screenX, screenY);
		let found = null;

		for (let i = this.previewBlocks.length - 1; i >= 0; i--) {
			const block = this.previewBlocks[i];

			if (block.corners && this.point_in_polygon(world, block.corners)) {
				found = block;
				break;
			}
		}

		this.selectedBlock = found;
		this.update_selected_info();
		this.draw();
	}

	update_selected_info() {
		if (!this.selectedBlock) {
			$("#selected_info").html("No preview block selected.");
			return;
		}

		const block = this.selectedBlock;

		$("#selected_info").html(`
			<b>Selected preview block</b><br>
			Label: ${frappe.utils.escape_html(block.label || "")}<br>
			Row: ${block.row}<br>
			Column: ${block.col}<br>
			Inside: ${this.format_number(block.inside_percent, 1)}%<br>
			Area: ${this.format_number(block.area, 2)}<br>
			<span style="color:#777;">Visual only. Not saved.</span>
		`);
	}

	get_block_centroid(block) {
		if (!block.corners || !block.corners.length) {
			return {
				x: block.x || 0,
				y: block.y || 0
			};
		}

		const sum = block.corners.reduce((acc, p) => {
			acc.x += p.x;
			acc.y += p.y;
			return acc;
		}, { x: 0, y: 0 });

		return {
			x: sum.x / block.corners.length,
			y: sum.y / block.corners.length
		};
	}

	point_in_polygon(point, polygon) {
		if (!polygon || polygon.length < 3) {
			return false;
		}

		let inside = false;
		const x = point.x;
		const y = point.y;

		for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
			const xi = polygon[i].x;
			const yi = polygon[i].y;
			const xj = polygon[j].x;
			const yj = polygon[j].y;

			const intersect = ((yi > y) !== (yj > y)) &&
				(x < (xj - xi) * (y - yi) / ((yj - yi) || 0.0000001) + xi);

			if (intersect) {
				inside = !inside;
			}
		}

		return inside;
	}

	format_number(value, decimals) {
		const number = Number(value || 0);

		if (!isFinite(number)) {
			return "0";
		}

		return number.toLocaleString(undefined, {
			minimumFractionDigits: decimals,
			maximumFractionDigits: decimals
		});
	}
}