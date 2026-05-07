frappe.pages["geo-batch-contour-vi"].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Geo Batch Contour Viewer",
		single_column: true
	});

	let points = [];
	let pitOutlinePoints = [];
	let generatedBlocks = [];
	let contourLines = [];
	let contourCacheKey = "";
	let showHeatmap = true;
	let showContours = true;
	let showContourLabels = true;
	let hoverPoint = null;
	let hoverBlock = null;
	let selectedBlock = null;
	let autoNumberBlocks = false;
	let rotateViewMode = false;

	let outlineEdgesCache = null;
	let pitCellSizeCache = null;
	let blockCacheKey = "";

	let view = {
		scale: 1,
		offsetX: 0,
		offsetY: 0,
		isDragging: false,
		isRotating: false,
		rotation: 0,
		startRotation: 0,
		startAngle: 0,
		dragMoved: false,
		lastX: 0,
		lastY: 0
	};

	$(page.body).html(`
		<style>
			.geo-viewer-shell {
				height: calc(100vh - 86px);
				display: grid;
				grid-template-columns: 330px 1fr;
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
				margin-top: 10px;
			}

			.geo-button-row .btn {
				width: 100%;
			}

			.geo-button-row .btn.geo-active-tool {
				background: #111;
				color: #fff;
				border-color: #111;
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
				background: rgba(255, 255, 255, 0.94);
				border: 1px solid #ddd;
				border-radius: 8px;
				padding: 9px 11px;
				font-size: 12px;
				line-height: 1.45;
				pointer-events: none;
				box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
				min-width: 205px;
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
				max-width: 340px;
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


			.geo-contour-swatch {
				display: inline-block;
				width: 34px;
				height: 0;
				border-top: 2px solid rgba(20, 20, 20, 0.85);
				vertical-align: middle;
				margin-right: 6px;
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
		</style>

		<div class="geo-viewer-shell">
			<div class="geo-side-panel">
				<div class="geo-side-title">Geo Batch Contour Viewer</div>

				<div class="geo-filter-slot" id="data_source_filter"></div>
				<div class="geo-filter-slot" id="geo_project_filter"></div>
				<div class="geo-filter-slot" id="geo_model_output_filter"></div>
				<div class="geo-filter-slot" id="version_filter"></div>
				<div class="geo-filter-slot" id="variable_filter"></div>

				<div class="geo-filter-section">
					<div class="geo-filter-slot" id="batch_filter"></div>
					<div class="geo-filter-slot" id="geo_depth_filter"></div>
					<div class="geo-filter-slot" id="pit_outline_filter"></div>
				</div>

				<div class="geo-filter-section">
					<div class="geo-filter-slot" id="z_filter_enabled"></div>
					<div class="geo-filter-slot" id="z_filter_mode"></div>
					<div class="geo-filter-slot" id="z_filter_value"></div>
					<div class="geo-filter-slot" id="z_filter_value_to"></div>
					<div class="geo-button-row">
						<button class="btn btn-default btn-sm" id="apply_z_filter">Apply Z Filter</button>
						<button class="btn btn-default btn-sm" id="clear_z_filter">Clear Z Filter</button>
					</div>
					<div class="geo-help-text">
						Use this to show only certain Z values. Example: enable filter, choose <b>Less Than</b>, value <b>60</b> to show only Z &lt; 60.
						This works for depth, thickness, elevation, or any loaded Z value.
					</div>
				</div>

				<div class="geo-filter-section">
					<div class="geo-filter-slot" id="show_heatmap_filter"></div>
					<div class="geo-filter-slot" id="show_contours_filter"></div>
					<div class="geo-filter-slot" id="contour_interval_filter"></div>
					<div class="geo-filter-slot" id="show_contour_labels_filter"></div>
					<div class="geo-button-row">
						<button class="btn btn-default btn-sm" id="rebuild_contours">Rebuild Contours</button>
						<button class="btn btn-default btn-sm" id="clear_contours">Clear Contours</button>
					</div>
					<div class="geo-help-text">
						Contours are built from the loaded batch X/Y/Z values. Use the interval to control spacing, for example <b>1</b>, <b>2</b>, <b>5</b>, or <b>10</b> metres.
					</div>
				</div>

				<div class="geo-filter-section">
					<div class="geo-filter-slot" id="mesh_size_filter"></div>
					<div class="geo-filter-slot" id="block_size_filter"></div>
					<div class="geo-filter-slot" id="block_angle_filter"></div>
					<div class="geo-filter-slot" id="minimum_inside_filter"></div>
					<div class="geo-help-text">
						Mesh and block size are flexible. Leave mesh on <b>Auto</b> to detect it from loaded points.
						For <b>Geo Depth</b>, Z is the calculated depth from Geo Calculated Points.
					</div>
				</div>

				<div class="geo-button-row">
					<button class="btn btn-primary btn-sm" id="load_geo_points">Load View</button>
					<button class="btn btn-default btn-sm" id="fit_geo_view">Fit</button>
					<button class="btn btn-default btn-sm" id="toggle_blocks">Blocks On/Off</button>
					<button class="btn btn-default btn-sm" id="toggle_pit_outline">Pit On/Off</button>
					<button class="btn btn-default btn-sm" id="toggle_rotate_view">Rotate View</button>
					<button class="btn btn-default btn-sm" id="reset_view_rotation">Reset Rotation</button>
				</div>

				<div class="geo-filter-section">
					<div class="geo-filter-slot" id="layout_name_filter"></div>
					<div class="geo-button-row">
						<button class="btn btn-default btn-sm" id="generate_blocks">Generate Blocks</button>
						<button class="btn btn-default btn-sm" id="clear_blocks">Clear Blocks</button>
						<button class="btn btn-default btn-sm" id="toggle_auto_numbering">Auto Number: Off</button>
						<button class="btn btn-default btn-sm" id="number_from_selected">Number From Selected</button>
						<button class="btn btn-default btn-sm" id="clear_block_numbers">Clear Numbers</button>
						<button class="btn btn-primary btn-sm" id="save_layout">Save Layout</button>
					</div>
					<div class="geo-selected-info" id="geo_selected_block_info">No block selected. Click a generated block, then click <b>Number From Selected</b>.</div>
					<div class="geo-help-text">
						Generate Blocks fills the loaded model/depth/pit area with mining blocks.
					</div>
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
						<div class="geo-legend-title" id="geo_legend_title">Z Value</div>
						<div class="geo-legend-subtitle" id="geo_legend_variable">No variable selected</div>
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

	const filters = {};
	let showBlocks = true;
	let showPitOutline = true;

	function make_control(parent, df) {
		return frappe.ui.form.make_control({
			parent: $(parent),
			df,
			render_input: true
		});
	}

	function get_data_source() {
		return filters.data_source ? filters.data_source.get_value() || "Geo Model" : "Geo Model";
	}

	function is_geo_depth() {
		return get_data_source() === "Geo Depth";
	}

	function is_batch_elevation() {
		return get_data_source() === "Batch Elevation";
	}

	function get_z_label() {
		if (is_geo_depth()) return "Depth";
		if (is_batch_elevation()) return "Elevation";
		return "Z";
	}

	function is_z_filter_enabled() {
		return !!(filters.z_filter_enabled && Number(filters.z_filter_enabled.get_value() || 0));
	}

	function get_z_filter_description() {
		if (!is_z_filter_enabled()) {
			return "Off";
		}

		const mode = filters.z_filter_mode.get_value() || "Less Than";
		const value = filters.z_filter_value.get_value();
		const valueTo = filters.z_filter_value_to.get_value();

		if (mode === "Between" || mode === "Outside") {
			return `${mode} ${value} and ${valueTo}`;
		}

		return `${mode} ${value}`;
	}

	filters.data_source = make_control("#data_source_filter", {
		fieldtype: "Select",
		label: "Data Source",
		fieldname: "data_source",
		options: "Batch Elevation\nGeo Model\nGeo Depth",
		default: "Batch Elevation",
		change: function() {
			reset_data_source_filters();
			toggle_data_source_fields();
			setup_project_filtered_queries();
			draw();
		}
	});

	filters.geo_project = make_control("#geo_project_filter", {
		fieldtype: "Link",
		options: "Geo Project",
		label: "Project",
		fieldname: "geo_project",
		change: function() {
			reset_project_dependent_filters();
			setup_project_filtered_queries();
		}
	});

	filters.geo_model_output = make_control("#geo_model_output_filter", {
		fieldtype: "Link",
		options: "Geo Model Output",
		label: "Model Output",
		fieldname: "geo_model_output"
	});

	filters.version_tag = make_control("#version_filter", {
		fieldtype: "Data",
		label: "Version",
		fieldname: "version_tag"
	});

	filters.variable_name = make_control("#variable_filter", {
		fieldtype: "Data",
		label: "Variable",
		fieldname: "variable_name"
	});

	filters.import_batch = make_control("#batch_filter", {
		fieldtype: "Link",
		options: "Geo Import Batch",
		label: "Model Batch",
		fieldname: "import_batch"
	});

	filters.geo_depth_batch = make_control("#geo_depth_filter", {
		fieldtype: "Link",
		options: "Geo Calculation Batch",
		label: "Geo Depth",
		fieldname: "geo_depth_batch"
	});

	filters.pit_outline_batch = make_control("#pit_outline_filter", {
		fieldtype: "Link",
		options: "Geo Import Batch",
		label: "Pit Outline",
		fieldname: "pit_outline_batch"
	});

	filters.z_filter_enabled = make_control("#z_filter_enabled", {
		fieldtype: "Check",
		label: "Use Z Filter",
		fieldname: "z_filter_enabled",
		default: 0,
		change: function() {
			clear_generated_blocks();
			draw();
		}
	});

	filters.z_filter_mode = make_control("#z_filter_mode", {
		fieldtype: "Select",
		label: "Z Filter Rule",
		fieldname: "z_filter_mode",
		options: "Less Than\nLess Than Or Equal\nGreater Than\nGreater Than Or Equal\nEqual\nBetween\nOutside",
		default: "Less Than",
		change: function() {
			clear_generated_blocks();
			draw();
		}
	});

	filters.z_filter_value = make_control("#z_filter_value", {
		fieldtype: "Float",
		label: "Z Filter Value",
		fieldname: "z_filter_value",
		default: 60,
		change: function() {
			clear_generated_blocks();
			draw();
		}
	});

	filters.z_filter_value_to = make_control("#z_filter_value_to", {
		fieldtype: "Float",
		label: "Z Filter To",
		fieldname: "z_filter_value_to",
		default: 0,
		description: "Only used for Between / Outside.",
		change: function() {
			clear_generated_blocks();
			draw();
		}
	});

	filters.show_heatmap = make_control("#show_heatmap_filter", {
		fieldtype: "Check",
		label: "Show Heatmap",
		fieldname: "show_heatmap",
		default: 1,
		change: function() {
			showHeatmap = !!Number(filters.show_heatmap.get_value() || 0);
			draw();
		}
	});

	filters.show_contours = make_control("#show_contours_filter", {
		fieldtype: "Check",
		label: "Show Contours",
		fieldname: "show_contours",
		default: 1,
		change: function() {
			showContours = !!Number(filters.show_contours.get_value() || 0);
			draw();
		}
	});

	filters.contour_interval = make_control("#contour_interval_filter", {
		fieldtype: "Float",
		label: "Contour Interval",
		fieldname: "contour_interval",
		default: 5,
		description: "Elevation/Z spacing between contour lines.",
		change: function() {
			clear_contours_only();
			draw();
		}
	});

	filters.show_contour_labels = make_control("#show_contour_labels_filter", {
		fieldtype: "Check",
		label: "Show Contour Labels",
		fieldname: "show_contour_labels",
		default: 1,
		change: function() {
			showContourLabels = !!Number(filters.show_contour_labels.get_value() || 0);
			draw();
		}
	});


	filters.mesh_size = make_control("#mesh_size_filter", {
		fieldtype: "Data",
		label: "Model Mesh Size",
		fieldname: "mesh_size",
		default: "Auto",
		description: "Use Auto or enter 20 x 20, 10 x 10, etc.",
		change: function() {
			clear_generated_blocks();
			draw();
		}
	});

	filters.block_size = make_control("#block_size_filter", {
		fieldtype: "Data",
		label: "Mining Block Size",
		fieldname: "block_size",
		default: "100 x 40",
		description: "Examples: 20, 20 x 20, 100 x 40.",
		change: function() {
			clear_generated_blocks();
			draw();
		}
	});

	filters.block_angle = make_control("#block_angle_filter", {
		fieldtype: "Float",
		label: "Block Angle Degrees",
		fieldname: "block_angle",
		default: 0,
		description: "0 means normal X/Y grid. Change this if blocks must follow the mining direction.",
		change: function() {
			clear_generated_blocks();
			draw();
		}
	});

	filters.minimum_inside = make_control("#minimum_inside_filter", {
		fieldtype: "Percent",
		label: "Minimum Inside %",
		fieldname: "minimum_inside",
		default: 50,
		description: "Edge filter. 50% keeps blocks with at least half the expected model cells.",
		change: function() {
			clear_generated_blocks();
			draw();
		}
	});

	filters.layout_name = make_control("#layout_name_filter", {
		fieldtype: "Data",
		label: "Layout Name",
		fieldname: "layout_name",
		default: "Draft Mining Blocks"
	});

	setup_project_filtered_queries();
	toggle_data_source_fields();

	const canvas = document.getElementById("geo_canvas");
	const ctx = canvas.getContext("2d");
	const hoverBox = document.getElementById("geo_hover_box");

	function toggle_data_source_fields() {
		const depth = is_geo_depth();

		$("#batch_filter").toggle(!depth);
		$("#geo_depth_filter").toggle(depth);

		if (depth) {
			filters.variable_name.df.label = "Depth Variable";
		} else {
			filters.variable_name.df.label = "Variable";
		}

		filters.variable_name.refresh();
	}

	function reset_data_source_filters() {
		filters.import_batch.set_value("");
		filters.geo_depth_batch.set_value("");
		filters.variable_name.set_value("");

		points = [];
		hoverPoint = null;
		hoverBlock = null;
		selectedBlock = null;

		clear_generated_blocks();
		clear_contours_only();
		invalidate_geometry_cache();
		hide_hover_box();
	}

	function reset_project_dependent_filters() {
		filters.geo_model_output.set_value("");
		filters.import_batch.set_value("");
		filters.geo_depth_batch.set_value("");
		filters.pit_outline_batch.set_value("");
		filters.variable_name.set_value("");
		filters.version_tag.set_value("");

		points = [];
		pitOutlinePoints = [];
		hoverPoint = null;
		hoverBlock = null;
		selectedBlock = null;

		clear_generated_blocks();
		clear_contours_only();
		invalidate_geometry_cache();
		hide_hover_box();
		draw();
	}

	function setup_project_filtered_queries() {
		const getProject = () => filters.geo_project.get_value();

		filters.import_batch.df.get_query = function() {
			return {
				query: "is_production.geo_planning.page.geo_batch_contour_vi.geo_batch_contour_vi.get_model_batch_query",
				filters: {
					geo_project: getProject()
				}
			};
		};

		filters.geo_depth_batch.df.get_query = function() {
			return {
				query: "is_production.geo_planning.page.geo_batch_contour_vi.geo_batch_contour_vi.get_geo_depth_batch_query",
				filters: {
					geo_project: getProject()
				}
			};
		};

		filters.pit_outline_batch.df.get_query = function() {
			return {
				query: "is_production.geo_planning.page.geo_batch_contour_vi.geo_batch_contour_vi.get_pit_outline_batch_query",
				filters: {
					geo_project: getProject()
				}
			};
		};

		filters.geo_model_output.df.get_query = function() {
			const project = getProject();

			if (!project) return {};

			return {
				filters: {
					geo_project: project
				}
			};
		};
	}

	function invalidate_geometry_cache() {
		outlineEdgesCache = null;
		pitCellSizeCache = null;
		blockCacheKey = "";
	}

	function clear_generated_blocks() {
		generatedBlocks = [];
		hoverBlock = null;
		selectedBlock = null;
		blockCacheKey = "";
		update_selected_block_info();
	}

	function clear_contours_only() {
		contourLines = [];
		contourCacheKey = "";
	}

	function invalidate_contour_cache() {
		contourCacheKey = "";
	}


	function resize_canvas() {
		const wrap = document.getElementById("geo_canvas_wrap");
		const rect = wrap.getBoundingClientRect();

		canvas.width = Math.max(900, Math.floor(rect.width));
		canvas.height = Math.max(620, Math.floor(rect.height));

		if (points.length || pitOutlinePoints.length) {
			fit_view();
			draw();
		}
	}

	window.addEventListener("resize", resize_canvas);
	setTimeout(resize_canvas, 100);

	$("#load_geo_points").on("click", function() {
		load_all_data();
	});

	$("#apply_z_filter").on("click", function() {
		if (!points.length) {
			load_all_data();
			return;
		}

		load_all_data();
	});

	$("#clear_z_filter").on("click", function() {
		filters.z_filter_enabled.set_value(0);
		filters.z_filter_mode.set_value("Less Than");
		filters.z_filter_value.set_value(60);
		filters.z_filter_value_to.set_value(0);
		clear_generated_blocks();
		load_all_data();
	});

	$("#rebuild_contours").on("click", function() {
		if (!points.length) {
			frappe.msgprint("Please load a batch before rebuilding contours.");
			return;
		}

		clear_contours_only();
		showContours = true;
		filters.show_contours.set_value(1);
		draw();

		frappe.show_alert({
			message: `Built ${contourLines.length.toLocaleString()} contour segments.`,
			indicator: "green"
		});
	});

	$("#clear_contours").on("click", function() {
		clear_contours_only();
		showContours = false;
		filters.show_contours.set_value(0);
		draw();
	});


	$("#fit_geo_view").on("click", function() {
		fit_view();
		draw();
	});

	$("#toggle_blocks").on("click", function() {
		showBlocks = !showBlocks;
		draw();
	});

	$("#toggle_pit_outline").on("click", function() {
		showPitOutline = !showPitOutline;
		draw();
	});

	$("#toggle_rotate_view").on("click", function() {
		rotateViewMode = !rotateViewMode;
		$(this).toggleClass("geo-active-tool", rotateViewMode);
		canvas.style.cursor = rotateViewMode ? "crosshair" : "grab";
		draw();
	});

	$("#reset_view_rotation").on("click", function() {
		view.rotation = 0;
		draw();
	});

	$("#generate_blocks").on("click", function() {
		generate_blocks();
		draw();
	});

	$("#clear_blocks").on("click", function() {
		clear_generated_blocks();
		draw();
	});

	$("#toggle_auto_numbering").on("click", function() {
		autoNumberBlocks = !autoNumberBlocks;
		update_auto_numbering_button();
	});

	$("#number_from_selected").on("click", function() {
		number_blocks_from_selected();
		draw();
	});

	$("#clear_block_numbers").on("click", function() {
		clear_block_numbers();
		draw();
	});

	$("#save_layout").on("click", function() {
		save_current_layout();
	});

	function load_all_data() {
		points = [];
		pitOutlinePoints = [];
		hoverPoint = null;
		hoverBlock = null;

		clear_generated_blocks();
		clear_contours_only();
		invalidate_geometry_cache();
		hide_hover_box();

		const hasMainData =
			is_geo_depth()
				? (
					!!filters.geo_depth_batch.get_value() ||
					!!filters.geo_project.get_value() ||
					!!filters.geo_model_output.get_value() ||
					!!filters.version_tag.get_value() ||
					!!filters.variable_name.get_value()
				)
				: (
					!!filters.import_batch.get_value() ||
					!!filters.geo_project.get_value() ||
					!!filters.geo_model_output.get_value() ||
					!!filters.version_tag.get_value() ||
					!!filters.variable_name.get_value()
				);

		const hasPitOutline = !!filters.pit_outline_batch.get_value();

		if (!hasMainData && !hasPitOutline) {
			$("#geo_info_box").html("Please select a project, model batch, Geo Depth batch, model filters, or a pit outline.");
			$("#geo_legend").hide();
			draw();
			return;
		}

		frappe.dom.freeze("Loading view...");

		const calls = [];

		if (hasMainData) {
			calls.push(load_geo_model_points_promise());
		}

		if (hasPitOutline) {
			calls.push(load_pit_outline_points_promise());
		}

		Promise.allSettled(calls).then((results) => {
			frappe.dom.unfreeze();

			const rejected = results.filter(r => r.status === "rejected");

			if (rejected.length) {
				console.error("Geo Planning Viewer load errors:", rejected);

				frappe.msgprint({
					title: "Partial Load Warning",
					indicator: "orange",
					message: "Some viewer data could not load, but successful data will still be shown."
				});
			}

			fit_view();
			draw();

			if (!points.length && pitOutlinePoints.length) {
				frappe.show_alert({
					message: "Pit outline loaded. No model/depth points matched the selected filters.",
					indicator: "orange"
				});
			}
		});
	}

	function load_geo_model_points_promise() {
		return new Promise((resolve, reject) => {
			frappe.call({
				method: "is_production.geo_planning.page.geo_batch_contour_vi.geo_batch_contour_vi.get_geo_points",
				args: {
					data_source: get_data_source(),
					geo_project: filters.geo_project.get_value(),
					geo_model_output: filters.geo_model_output.get_value(),
					version_tag: filters.version_tag.get_value(),
					variable_name: filters.variable_name.get_value(),
					import_batch: filters.import_batch.get_value(),
					calculation_batch: filters.geo_depth_batch.get_value(),
					z_filter_enabled: is_z_filter_enabled() ? 1 : 0,
					z_filter_mode: filters.z_filter_mode.get_value(),
					z_filter_value: filters.z_filter_value.get_value(),
					z_filter_value_to: filters.z_filter_value_to.get_value()
				},
				callback(r) {
					points = (r.message || []).map(p => ({
						x: Number(p.x),
						y: Number(p.y),
						z: Number(p.z),
						calculated_z: p.calculated_z !== undefined ? Number(p.calculated_z) : null,
						reference_z: p.reference_z !== undefined ? Number(p.reference_z) : null,
						target_z: p.target_z !== undefined ? Number(p.target_z) : null,
						reference_variable_code: p.reference_variable_code || "",
						target_variable_code: p.target_variable_code || "",
						variable_name: p.variable_name || p.full_name || p.variable_code || "",
						variable_code: p.variable_code || "",
						full_name: p.full_name || "",
						version_tag: p.version_tag || "",
						import_batch: p.import_batch || p.geo_import_batch || p.calculation_batch || "",
						calculation_batch: p.calculation_batch || "",
						geo_model_output: p.geo_model_output || "",
						data_source: p.data_source || get_data_source()
					})).filter(p => isFinite(p.x) && isFinite(p.y) && isFinite(p.z));

					resolve();
				},
				error(err) {
					reject(err);
				}
			});
		});
	}

	function load_pit_outline_points_promise() {
		return new Promise((resolve, reject) => {
			const pitBatch = filters.pit_outline_batch.get_value();

			if (!pitBatch) {
				pitOutlinePoints = [];
				resolve();
				return;
			}

			frappe.call({
				method: "is_production.geo_planning.page.geo_batch_contour_vi.geo_batch_contour_vi.get_pit_outline_points",
				args: {
					geo_import_batch: pitBatch
				},
				callback(r) {
					pitOutlinePoints = (r.message || []).map(p => ({
						x: Number(p.x),
						y: Number(p.y),
						z: Number(p.z || 0),
						variable_name: p.variable_name || p.full_name || p.variable_code || "",
						version_tag: p.version_tag || "",
						geo_import_batch: p.geo_import_batch || p.import_batch || "",
						geo_model_output: p.geo_model_output || ""
					})).filter(p => isFinite(p.x) && isFinite(p.y));

					resolve();
				},
				error(err) {
					reject(err);
				}
			});
		});
	}

	function parse_size(value) {
		if (!value) return null;

		let clean = String(value).trim().toLowerCase();

		if (!clean || clean === "auto") return null;

		clean = clean
			.replace(/×/g, "x")
			.replace(/\*/g, "x")
			.replace(/,/g, ".")
			.replace(/\s+/g, " ");

		let xSize = 0;
		let ySize = 0;

		if (clean.includes("x")) {
			const parts = clean.split("x").map(p => p.trim()).filter(Boolean);

			if (parts.length >= 2) {
				xSize = Number(parts[0]);
				ySize = Number(parts[1]);
			}
		} else {
			const parts = clean.split(" ").map(p => p.trim()).filter(Boolean);

			if (parts.length >= 2) {
				xSize = Number(parts[0]);
				ySize = Number(parts[1]);
			} else {
				xSize = Number(clean);
				ySize = xSize;
			}
		}

		if (!isFinite(xSize) || !isFinite(ySize) || xSize <= 0 || ySize <= 0) {
			return null;
		}

		return {
			x: xSize,
			y: ySize,
			label: `${xSize} x ${ySize}`
		};
	}

	function get_selected_block_size() {
		return parse_size(filters.block_size.get_value()) || {
			x: 0,
			y: 0,
			label: "Off"
		};
	}

	function get_manual_or_auto_mesh_size() {
		const manual = parse_size(filters.mesh_size.get_value());

		if (manual) {
			return {
				...manual,
				source: "Manual"
			};
		}

		const auto = estimate_model_cell_size_world();

		return {
			x: auto.x,
			y: auto.y,
			label: `${auto.x} x ${auto.y}`,
			source: "Auto"
		};
	}

	function median_gap(values, fallback) {
		const cleanValues = values.filter(v => isFinite(v)).sort((a, b) => a - b);
		const gaps = [];

		for (let i = 1; i < cleanValues.length; i++) {
			const gap = cleanValues[i] - cleanValues[i - 1];

			if (gap > 0.0001) {
				gaps.push(gap);
			}
		}

		if (!gaps.length) return fallback;

		gaps.sort((a, b) => a - b);

		return Number(gaps[Math.floor(gaps.length / 2)].toFixed(4));
	}

	function estimate_model_cell_size_world() {
		if (points.length < 2) {
			return {
				x: 20,
				y: 20
			};
		}

		const sample = points.slice(0, Math.min(points.length, 10000));
		const uniqueX = [...new Set(sample.map(p => p.x))];
		const uniqueY = [...new Set(sample.map(p => p.y))];

		return {
			x: median_gap(uniqueX, 20),
			y: median_gap(uniqueY, 20)
		};
	}

	function estimate_model_cell_size_screen() {
		const worldCell = estimate_model_cell_size_world();

		return {
			x: Math.max(1, worldCell.x * view.scale),
			y: Math.max(1, worldCell.y * view.scale)
		};
	}

	function get_all_visible_points() {
		const all = [];

		for (const p of points) {
			all.push(p);
		}

		if (showPitOutline) {
			for (const p of pitOutlinePoints) {
				all.push(p);
			}
		}

		return all;
	}

	function get_bounds() {
		const all = get_all_visible_points();

		if (!all.length) {
			return null;
		}

		const xs = all.map(p => p.x);
		const ys = all.map(p => p.y);
		const zs = points.length ? points.map(p => p.z) : [0];

		return {
			minX: Math.min(...xs),
			maxX: Math.max(...xs),
			minY: Math.min(...ys),
			maxY: Math.max(...ys),
			minZ: Math.min(...zs),
			maxZ: Math.max(...zs)
		};
	}

	function get_model_bounds_only() {
		if (!points.length) return null;

		const xs = points.map(p => p.x);
		const ys = points.map(p => p.y);
		const zs = points.map(p => p.z);

		return {
			minX: Math.min(...xs),
			maxX: Math.max(...xs),
			minY: Math.min(...ys),
			maxY: Math.max(...ys),
			minZ: Math.min(...zs),
			maxZ: Math.max(...zs)
		};
	}

	function get_model_stats() {
		if (!points.length) return null;

		const zs = points.map(p => p.z);
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

	function fit_view() {
		const b = get_bounds();

		if (!b) return;

		const pad = 70;
		const width = b.maxX - b.minX || 1;
		const height = b.maxY - b.minY || 1;
		const scaleX = (canvas.width - pad * 2) / width;
		const scaleY = (canvas.height - pad * 2) / height;

		view.scale = Math.min(scaleX, scaleY);

		const drawnWidth = width * view.scale;
		const drawnHeight = height * view.scale;

		view.offsetX = (canvas.width - drawnWidth) / 2 - b.minX * view.scale;
		view.offsetY = (canvas.height - drawnHeight) / 2 + b.maxY * view.scale;
	}

	function rotate_screen_point(x, y) {
		if (!view.rotation) {
			return { x, y };
		}

		const cx = canvas.width / 2;
		const cy = canvas.height / 2;
		const dx = x - cx;
		const dy = y - cy;
		const cos = Math.cos(view.rotation);
		const sin = Math.sin(view.rotation);

		return {
			x: cx + dx * cos - dy * sin,
			y: cy + dx * sin + dy * cos
		};
	}

	function unrotate_screen_point(x, y) {
		if (!view.rotation) {
			return { x, y };
		}

		const cx = canvas.width / 2;
		const cy = canvas.height / 2;
		const dx = x - cx;
		const dy = y - cy;
		const cos = Math.cos(-view.rotation);
		const sin = Math.sin(-view.rotation);

		return {
			x: cx + dx * cos - dy * sin,
			y: cy + dx * sin + dy * cos
		};
	}

	function world_to_screen_point(x, y) {
		return rotate_screen_point(
			x * view.scale + view.offsetX,
			-y * view.scale + view.offsetY
		);
	}

	function screen_to_world_point(x, y) {
		const p = unrotate_screen_point(x, y);

		return {
			x: (p.x - view.offsetX) / view.scale,
			y: -(p.y - view.offsetY) / view.scale
		};
	}

	function value_colour(z, minZ, maxZ) {
		const t = (z - minZ) / (maxZ - minZ || 1);

		let r, g, b;

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

	function rotate_to_local(x, y, anchor, angle) {
		const dx = x - anchor.x;
		const dy = y - anchor.y;
		const cos = Math.cos(-angle);
		const sin = Math.sin(-angle);

		return {
			x: dx * cos - dy * sin,
			y: dx * sin + dy * cos
		};
	}

	function local_to_world(localX, localY, anchor, angle) {
		const cos = Math.cos(angle);
		const sin = Math.sin(angle);

		return {
			x: anchor.x + localX * cos - localY * sin,
			y: anchor.y + localX * sin + localY * cos
		};
	}

	function get_generation_anchor() {
		const source = pitOutlinePoints.length ? pitOutlinePoints : points;

		if (!source.length) {
			return {
				x: 0,
				y: 0
			};
		}

		const xs = source.map(p => p.x);
		const ys = source.map(p => p.y);

		return {
			x: Math.min(...xs),
			y: Math.min(...ys)
		};
	}

	function get_block_key_for_point(p, blockSize, anchor, angle) {
		const local = rotate_to_local(p.x, p.y, anchor, angle);
		const col = Math.floor(local.x / blockSize.x);
		const row = Math.floor(local.y / blockSize.y);

		return {
			key: `${col}|${row}`,
			col,
			row
		};
	}

	function get_block_corners(col, row, blockSize, anchor, angle) {
		const x0 = col * blockSize.x;
		const y0 = row * blockSize.y;

		return [
			local_to_world(x0, y0, anchor, angle),
			local_to_world(x0 + blockSize.x, y0, anchor, angle),
			local_to_world(x0 + blockSize.x, y0 + blockSize.y, anchor, angle),
			local_to_world(x0, y0 + blockSize.y, anchor, angle)
		];
	}

	function point_in_block(point, block) {
		const local = rotate_to_local(point.x, point.y, block.anchor, block.angle);
		const x0 = block.col * block.width;
		const y0 = block.row * block.height;

		return (
			local.x >= x0 &&
			local.x < x0 + block.width &&
			local.y >= y0 &&
			local.y < y0 + block.height
		);
	}

	function generate_blocks() {
		const blockSize = get_selected_block_size();
		const meshSize = get_manual_or_auto_mesh_size();
		const minInside = Number(filters.minimum_inside.get_value() || 0);
		const angleDegrees = Number(filters.block_angle.get_value() || 0);
		const angle = angleDegrees * Math.PI / 180;

		if (!points.length) {
			frappe.msgprint("Please load points before generating mining blocks.");
			return;
		}

		if (!blockSize.x || !blockSize.y) {
			frappe.msgprint("Please enter a valid Mining Block Size, for example 100 x 40.");
			return;
		}

		if (!meshSize.x || !meshSize.y) {
			frappe.msgprint("Please enter a valid Model Mesh Size, for example 20 x 20, or use Auto.");
			return;
		}

		const expectedPointCount = Math.max(
			1,
			Math.round((blockSize.x / meshSize.x) * (blockSize.y / meshSize.y))
		);

		const minPointCount = Math.max(
			1,
			Math.ceil(expectedPointCount * Math.max(0, minInside) / 100)
		);

		const anchor = get_generation_anchor();
		const sourcePoints = pitOutlinePoints.length ? pitOutlinePoints : points;
		const blockMap = {};

		for (const p of sourcePoints) {
			const keyInfo = get_block_key_for_point(p, blockSize, anchor, angle);

			if (!blockMap[keyInfo.key]) {
				blockMap[keyInfo.key] = {
					key: keyInfo.key,
					col: keyInfo.col,
					row: keyInfo.row,
					source_count: 0,
					sum: 0,
					count: 0,
					min_z: null,
					max_z: null
				};
			}

			blockMap[keyInfo.key].source_count += 1;
		}

		for (const p of points) {
			const keyInfo = get_block_key_for_point(p, blockSize, anchor, angle);

			if (!blockMap[keyInfo.key]) {
				if (pitOutlinePoints.length) {
					continue;
				}

				blockMap[keyInfo.key] = {
					key: keyInfo.key,
					col: keyInfo.col,
					row: keyInfo.row,
					source_count: 0,
					sum: 0,
					count: 0,
					min_z: null,
					max_z: null
				};
			}

			const b = blockMap[keyInfo.key];

			b.sum += p.z;
			b.count += 1;
			b.min_z = b.min_z === null ? p.z : Math.min(b.min_z, p.z);
			b.max_z = b.max_z === null ? p.z : Math.max(b.max_z, p.z);
		}

		let blockNo = 0;

		selectedBlock = null;

		generatedBlocks = Object.values(blockMap)
			.filter(b => b.count >= minPointCount)
			.sort((a, b) => a.row - b.row || a.col - b.col)
			.map(b => {
				blockNo += 1;
				const assignedBlockNo = autoNumberBlocks ? blockNo : 0;

				const corners = get_block_corners(b.col, b.row, blockSize, anchor, angle);
				const cx = corners.reduce((s, p) => s + p.x, 0) / 4;
				const cy = corners.reduce((s, p) => s + p.y, 0) / 4;
				const insidePercent = Math.min(100, (b.count / expectedPointCount) * 100);

				let status = "Full Block";

				if (insidePercent < 100) {
					status = "Partial Block";
				}

				if (insidePercent < minInside) {
					status = "Review";
				}

				return {
					cut_no: 0,
					block_no: assignedBlockNo,
					label: assignedBlockNo ? `B${String(assignedBlockNo).padStart(4, "0")}` : "",
					key: b.key,
					col: b.col,
					row: b.row,
					x: cx,
					y: cy,
					width: blockSize.x,
					height: blockSize.y,
					angle,
					angle_degrees: angleDegrees,
					anchor,
					corners,
					avg_z: b.count ? b.sum / b.count : 0,
					min_z: b.min_z || 0,
					max_z: b.max_z || 0,
					point_count: b.count,
					expected_point_count: expectedPointCount,
					inside_percent: insidePercent,
					status
				};
			});

		blockCacheKey = `${points.length}|${pitOutlinePoints.length}|${blockSize.label}|${meshSize.label}|${angleDegrees}|${minInside}`;

		update_selected_block_info();

		frappe.show_alert({
			message: `Generated ${generatedBlocks.length} mining blocks. Expected points per full block: ${expectedPointCount}. ${autoNumberBlocks ? "Blocks were numbered automatically." : "Blocks are unnumbered until you select a start block."}`,
			indicator: "green"
		});
	}

	function update_auto_numbering_button() {
		const label = autoNumberBlocks ? "Auto Number: On" : "Auto Number: Off";
		$("#toggle_auto_numbering")
			.text(label)
			.toggleClass("geo-active-tool", autoNumberBlocks);
	}

	function update_selected_block_info() {
		const el = $("#geo_selected_block_info");

		if (!el.length) return;

		if (!selectedBlock) {
			el.html("No block selected. Click a generated block, then click <b>Number From Selected</b>.");
			return;
		}

		const currentLabel = selectedBlock.label || "Unnumbered";

		el.html(
			`<b>Selected:</b> ${frappe.utils.escape_html(currentLabel)} ` +
			`(row ${selectedBlock.row}, col ${selectedBlock.col})<br>` +
			`Centre X/Y: ${selectedBlock.x.toFixed(2)}, ${selectedBlock.y.toFixed(2)}`
		);
	}

	function get_sorted_blocks_for_numbering() {
		return [...generatedBlocks].sort((a, b) => a.row - b.row || a.col - b.col);
	}

	function number_blocks_from_selected() {
		if (!generatedBlocks.length) {
			frappe.msgprint("Please generate mining blocks first.");
			return;
		}

		if (!selectedBlock) {
			frappe.msgprint("Please click the block where numbering must start, then click Number From Selected.");
			return;
		}

		const sorted = get_sorted_blocks_for_numbering();
		const startIndex = sorted.findIndex(b => b.key === selectedBlock.key);

		if (startIndex < 0) {
			frappe.msgprint("The selected block could not be found in the current layout. Please select it again.");
			return;
		}

		const numberingOrder = sorted.slice(startIndex).concat(sorted.slice(0, startIndex));

		numberingOrder.forEach((block, index) => {
			const blockNo = index + 1;
			block.block_no = blockNo;
			block.label = `B${String(blockNo).padStart(4, "0")}`;
		});

		selectedBlock = numberingOrder[0];
		update_selected_block_info();

		frappe.show_alert({
			message: `Numbered ${numberingOrder.length} blocks from ${selectedBlock.label}.`,
			indicator: "green"
		});
	}

	function clear_block_numbers() {
		if (!generatedBlocks.length) {
			return;
		}

		for (const block of generatedBlocks) {
			block.block_no = 0;
			block.label = "";
		}

		update_selected_block_info();

		frappe.show_alert({
			message: "Block numbers cleared. Select a start block and number again when ready.",
			indicator: "blue"
		});
	}

	function save_current_layout() {
		if (!generatedBlocks.length) {
			frappe.msgprint("Please click Generate Blocks before saving the layout.");
			return;
		}

		if (!filters.geo_project.get_value()) {
			frappe.msgprint("Please select a project before saving the layout.");
			return;
		}

		const blockSize = get_selected_block_size();
		const meshSize = get_manual_or_auto_mesh_size();

		const blocksForSave = generatedBlocks.map(b => ({
			cut_no: b.cut_no,
			block_no: b.block_no,
			label: b.label,
			col: b.col,
			row: b.row,
			x: b.x,
			y: b.y,
			width: b.width,
			height: b.height,
			angle_degrees: b.angle_degrees,
			avg_z: b.avg_z,
			min_z: b.min_z,
			max_z: b.max_z,
			point_count: b.point_count,
			expected_point_count: b.expected_point_count,
			inside_percent: b.inside_percent,
			status: b.status,
			corners: b.corners
		}));

		frappe.call({
			method: "is_production.geo_planning.page.geo_batch_contour_vi.geo_batch_contour_vi.save_mining_block_layout",
			args: {
				layout_name: filters.layout_name.get_value() || "Draft Mining Blocks",
				geo_project: filters.geo_project.get_value(),
				geo_model_output: filters.geo_model_output.get_value(),
				model_batch: is_geo_depth() ? "" : filters.import_batch.get_value(),
				geo_depth_batch: is_geo_depth() ? filters.geo_depth_batch.get_value() : "",
				pit_outline_batch: filters.pit_outline_batch.get_value(),
				data_source: get_data_source(),
				block_size_x: blockSize.x,
				block_size_y: blockSize.y,
				mesh_size_x: meshSize.x,
				mesh_size_y: meshSize.y,
				block_angle_degrees: Number(filters.block_angle.get_value() || 0),
				minimum_inside_percent: Number(filters.minimum_inside.get_value() || 0),
				blocks_json: JSON.stringify(blocksForSave)
			},
			freeze: true,
			freeze_message: "Saving block layout...",
			callback(r) {
				if (r.message) {
					frappe.msgprint({
						title: "Layout Saved",
						indicator: "green",
						message:
							"Layout: " + r.message.layout +
							"<br>Blocks saved: " + r.message.blocks_created
					});
				}
			}
		});
	}

	function get_contour_interval() {
		const interval = Number(filters.contour_interval ? filters.contour_interval.get_value() : 5);
		return isFinite(interval) && interval > 0 ? interval : 5;
	}

	function contour_key(modelBounds) {
		if (!modelBounds || !points.length) return "";

		return [
			points.length,
			modelBounds.minX.toFixed(3),
			modelBounds.maxX.toFixed(3),
			modelBounds.minY.toFixed(3),
			modelBounds.maxY.toFixed(3),
			modelBounds.minZ.toFixed(3),
			modelBounds.maxZ.toFixed(3),
			get_contour_interval()
		].join("|");
	}

	function build_point_grid() {
		const xSet = new Set();
		const ySet = new Set();
		const pointMap = new Map();

		function coord_key(x, y) {
			return `${Number(x).toFixed(6)}|${Number(y).toFixed(6)}`;
		}

		for (const p of points) {
			if (!isFinite(p.x) || !isFinite(p.y) || !isFinite(p.z)) continue;

			xSet.add(Number(p.x.toFixed(6)));
			ySet.add(Number(p.y.toFixed(6)));
			pointMap.set(coord_key(p.x, p.y), p);
		}

		const xs = Array.from(xSet).sort((a, b) => a - b);
		const ys = Array.from(ySet).sort((a, b) => a - b);

		return {
			xs,
			ys,
			get: function(x, y) {
				return pointMap.get(coord_key(x, y));
			}
		};
	}

	function get_contour_levels(modelBounds) {
		const interval = get_contour_interval();
		const levels = [];

		if (!modelBounds || !isFinite(modelBounds.minZ) || !isFinite(modelBounds.maxZ)) {
			return levels;
		}

		if (modelBounds.maxZ === modelBounds.minZ) {
			levels.push(modelBounds.minZ);
			return levels;
		}

		const start = Math.ceil(modelBounds.minZ / interval) * interval;
		const end = Math.floor(modelBounds.maxZ / interval) * interval;

		for (let z = start; z <= end + interval * 0.0001; z += interval) {
			levels.push(Number(z.toFixed(6)));
		}

		return levels;
	}

	function contour_crosses(z1, z2, level) {
		if (!isFinite(z1) || !isFinite(z2)) return false;
		if (z1 === z2) return false;

		return (z1 < level && z2 >= level) || (z2 < level && z1 >= level);
	}

	function interpolate_contour_point(a, b, level) {
		const t = (level - a.z) / (b.z - a.z || 1);

		return {
			x: a.x + (b.x - a.x) * t,
			y: a.y + (b.y - a.y) * t,
			z: level
		};
	}

	function generate_contours(modelBounds) {
		if (!points.length || !modelBounds) {
			contourLines = [];
			return contourLines;
		}

		const key = contour_key(modelBounds);

		if (contourCacheKey === key && contourLines.length) {
			return contourLines;
		}

		const grid = build_point_grid();
		const levels = get_contour_levels(modelBounds);
		const lines = [];

		if (grid.xs.length < 2 || grid.ys.length < 2 || !levels.length) {
			contourLines = [];
			contourCacheKey = key;
			return contourLines;
		}

		for (const level of levels) {
			for (let ix = 0; ix < grid.xs.length - 1; ix++) {
				for (let iy = 0; iy < grid.ys.length - 1; iy++) {
					const x0 = grid.xs[ix];
					const x1 = grid.xs[ix + 1];
					const y0 = grid.ys[iy];
					const y1 = grid.ys[iy + 1];

					const p00 = grid.get(x0, y0);
					const p10 = grid.get(x1, y0);
					const p11 = grid.get(x1, y1);
					const p01 = grid.get(x0, y1);

					if (!p00 || !p10 || !p11 || !p01) continue;

					const crossings = [];

					if (contour_crosses(p00.z, p10.z, level)) {
						crossings.push(interpolate_contour_point(p00, p10, level));
					}

					if (contour_crosses(p10.z, p11.z, level)) {
						crossings.push(interpolate_contour_point(p10, p11, level));
					}

					if (contour_crosses(p11.z, p01.z, level)) {
						crossings.push(interpolate_contour_point(p11, p01, level));
					}

					if (contour_crosses(p01.z, p00.z, level)) {
						crossings.push(interpolate_contour_point(p01, p00, level));
					}

					if (crossings.length === 2) {
						lines.push({ level, p1: crossings[0], p2: crossings[1] });
					} else if (crossings.length === 4) {
						lines.push({ level, p1: crossings[0], p2: crossings[1] });
						lines.push({ level, p1: crossings[2], p2: crossings[3] });
					}
				}
			}
		}

		contourLines = lines;
		contourCacheKey = key;

		return contourLines;
	}

	function draw_contours(modelBounds) {
		if (!showContours || !points.length || !modelBounds) return;

		const lines = generate_contours(modelBounds);

		if (!lines.length) return;

		const interval = get_contour_interval();
		const majorInterval = interval * 5;
		const labelEvery = Math.max(1, Math.floor(lines.length / 80));

		ctx.save();
		ctx.lineCap = "round";
		ctx.lineJoin = "round";

		for (let i = 0; i < lines.length; i++) {
			const line = lines[i];
			const p1 = world_to_screen_point(line.p1.x, line.p1.y);
			const p2 = world_to_screen_point(line.p2.x, line.p2.y);
			const isMajor = majorInterval > 0 && Math.abs(line.level / majorInterval - Math.round(line.level / majorInterval)) < 0.0001;

			ctx.strokeStyle = isMajor ? "rgba(15, 15, 15, 0.9)" : "rgba(45, 45, 45, 0.58)";
			ctx.lineWidth = isMajor ? 1.35 : 0.8;

			ctx.beginPath();
			ctx.moveTo(p1.x, p1.y);
			ctx.lineTo(p2.x, p2.y);
			ctx.stroke();

			if (showContourLabels && isMajor && i % labelEvery === 0) {
				const mx = (p1.x + p2.x) / 2;
				const my = (p1.y + p2.y) / 2;
				const angle = Math.atan2(p2.y - p1.y, p2.x - p1.x);

				ctx.save();
				ctx.translate(mx, my);
				ctx.rotate(angle);
				ctx.font = "10px Arial";
				ctx.textAlign = "center";
				ctx.textBaseline = "middle";
				ctx.fillStyle = "rgba(255, 255, 255, 0.82)";
				const label = line.level.toFixed(Math.abs(interval) < 1 ? 2 : 0);
				const labelWidth = ctx.measureText(label).width + 8;
				ctx.fillRect(-labelWidth / 2, -7, labelWidth, 14);
				ctx.fillStyle = "rgba(0, 0, 0, 0.86)";
				ctx.fillText(label, 0, 0);
				ctx.restore();
			}
		}

		ctx.restore();
	}


	function draw_heatmap(modelBounds) {
		if (!points.length || !modelBounds) return;

		const cell = estimate_model_cell_size_screen();

		for (const p of points) {
			const sp = world_to_screen_point(p.x, p.y);
			const x = sp.x;
			const y = sp.y;

			ctx.fillStyle = value_colour(p.z, modelBounds.minZ, modelBounds.maxZ);
			ctx.fillRect(
				x - cell.x / 2,
				y - cell.y / 2,
				cell.x + 0.5,
				cell.y + 0.5
			);
		}
	}

	function estimate_outline_cell_size(pointsForOutline) {
		if (pitCellSizeCache) {
			return pitCellSizeCache;
		}

		if (pointsForOutline.length < 2) {
			pitCellSizeCache = {
				x: 20,
				y: 20
			};

			return pitCellSizeCache;
		}

		const sample = pointsForOutline.slice(0, Math.min(pointsForOutline.length, 5000));
		const uniqueX = [...new Set(sample.map(p => p.x))];
		const uniqueY = [...new Set(sample.map(p => p.y))];

		pitCellSizeCache = {
			x: median_gap(uniqueX, 20),
			y: median_gap(uniqueY, 20)
		};

		return pitCellSizeCache;
	}

	function get_outline_boundary_edges(pointsForOutline) {
		if (outlineEdgesCache) {
			return outlineEdgesCache;
		}

		if (!pointsForOutline.length) {
			outlineEdgesCache = [];
			return outlineEdgesCache;
		}

		const cellSize = estimate_outline_cell_size(pointsForOutline);
		const halfX = cellSize.x / 2;
		const halfY = cellSize.y / 2;
		const edgeMap = {};

		function key_for_edge(x1, y1, x2, y2) {
			return `${x1.toFixed(3)},${y1.toFixed(3)}|${x2.toFixed(3)},${y2.toFixed(3)}`;
		}

		function add_or_remove_edge(x1, y1, x2, y2) {
			const keyA = key_for_edge(x1, y1, x2, y2);
			const keyB = key_for_edge(x2, y2, x1, y1);

			if (edgeMap[keyB]) {
				delete edgeMap[keyB];
			} else {
				edgeMap[keyA] = {
					x1,
					y1,
					x2,
					y2
				};
			}
		}

		for (const p of pointsForOutline) {
			const x1 = p.x - halfX;
			const x2 = p.x + halfX;
			const y1 = p.y - halfY;
			const y2 = p.y + halfY;

			add_or_remove_edge(x1, y1, x2, y1);
			add_or_remove_edge(x2, y1, x2, y2);
			add_or_remove_edge(x2, y2, x1, y2);
			add_or_remove_edge(x1, y2, x1, y1);
		}

		outlineEdgesCache = Object.values(edgeMap);

		return outlineEdgesCache;
	}

	function draw_pit_outline() {
		if (!showPitOutline || !pitOutlinePoints.length) return;

		const edges = get_outline_boundary_edges(pitOutlinePoints);

		ctx.save();
		ctx.strokeStyle = "#000";
		ctx.lineWidth = 3;

		for (const e of edges) {
			const p1 = world_to_screen_point(e.x1, e.y1);
			const p2 = world_to_screen_point(e.x2, e.y2);

			ctx.beginPath();
			ctx.moveTo(p1.x, p1.y);
			ctx.lineTo(p2.x, p2.y);
			ctx.stroke();
		}

		ctx.restore();
	}

	function draw_generated_blocks(modelBounds) {
		if (!showBlocks || !generatedBlocks.length) return;

		ctx.save();

		for (const b of generatedBlocks) {
			if (modelBounds && b.point_count) {
				ctx.fillStyle = value_colour(b.avg_z, modelBounds.minZ, modelBounds.maxZ);
				ctx.globalAlpha = 0.22;

				const first = world_to_screen_point(b.corners[0].x, b.corners[0].y);

				ctx.beginPath();
				ctx.moveTo(first.x, first.y);

				for (let i = 1; i < b.corners.length; i++) {
					const p = world_to_screen_point(b.corners[i].x, b.corners[i].y);
					ctx.lineTo(p.x, p.y);
				}

				ctx.closePath();
				ctx.fill();
			}

			ctx.globalAlpha = 1;
			const isSelected = selectedBlock && selectedBlock.key === b.key;
			ctx.strokeStyle = isSelected ? "rgba(0,70,180,0.95)" : (b.status === "Full Block" ? "rgba(0,0,0,0.72)" : "rgba(160,80,0,0.95)");
			ctx.lineWidth = isSelected ? 3 : (b.status === "Full Block" ? 1 : 1.5);

			const first = world_to_screen_point(b.corners[0].x, b.corners[0].y);

			ctx.beginPath();
			ctx.moveTo(first.x, first.y);

			for (let i = 1; i < b.corners.length; i++) {
				const p = world_to_screen_point(b.corners[i].x, b.corners[i].y);
				ctx.lineTo(p.x, p.y);
			}

			ctx.closePath();
			ctx.stroke();

			if (b.label && b.width * view.scale >= 45 && b.height * view.scale >= 20) {
				ctx.save();
				const blockScreen = world_to_screen_point(b.x, b.y);
				ctx.translate(blockScreen.x, blockScreen.y);
				ctx.rotate(view.rotation - b.angle);
				ctx.fillStyle = "rgba(0,0,0,0.72)";
				ctx.font = "10px Arial";
				ctx.textAlign = "center";
				ctx.fillText(b.label, 0, 3);
				ctx.restore();
			}
		}

		ctx.restore();
	}

	function update_legend(modelBounds) {
		if (!modelBounds || !points.length) {
			$("#geo_legend").hide();
			return;
		}

		const stats = get_model_stats();
		const variable = filters.variable_name.get_value() || points[0]?.variable_name || "Selected variable";
		const minZ = stats.minZ;
		const maxZ = stats.maxZ;
		const range = stats.rangeZ;

		$("#geo_legend_title").text(`${get_z_label()} Value`);
		$("#geo_legend_variable").text(variable);
		$("#geo_min_z").text(minZ.toFixed(2));
		$("#geo_max_z").text(maxZ.toFixed(2));
		$("#geo_avg_z").text(stats.avgZ.toFixed(2));
		$("#geo_range_z").text(range.toFixed(2));

		$("#geo_tick_0").text(minZ.toFixed(1));
		$("#geo_tick_1").text((minZ + range * 0.25).toFixed(1));
		$("#geo_tick_2").text((minZ + range * 0.50).toFixed(1));
		$("#geo_tick_3").text((minZ + range * 0.75).toFixed(1));
		$("#geo_tick_4").text(maxZ.toFixed(1));

		$("#geo_legend").show();
	}

	function draw_hover_marker(modelBounds) {
		if (!hoverPoint || !modelBounds) return;

		const hp = world_to_screen_point(hoverPoint.x, hoverPoint.y);
		const x = hp.x;
		const y = hp.y;

		ctx.save();
		ctx.strokeStyle = "#000";
		ctx.lineWidth = 1.5;
		ctx.beginPath();
		ctx.arc(x, y, 5, 0, Math.PI * 2);
		ctx.stroke();

		ctx.fillStyle = "rgba(255, 255, 255, 0.75)";
		ctx.beginPath();
		ctx.arc(x, y, 3, 0, Math.PI * 2);
		ctx.fill();

		ctx.restore();
	}

	function draw_hover_block() {
		if (!hoverBlock) return;

		ctx.save();
		ctx.strokeStyle = "#111";
		ctx.lineWidth = 2.5;
		ctx.setLineDash([6, 3]);

		const first = world_to_screen_point(hoverBlock.corners[0].x, hoverBlock.corners[0].y);

		ctx.beginPath();
		ctx.moveTo(first.x, first.y);

		for (let i = 1; i < hoverBlock.corners.length; i++) {
			const p = world_to_screen_point(hoverBlock.corners[i].x, hoverBlock.corners[i].y);
			ctx.lineTo(p.x, p.y);
		}

		ctx.closePath();
		ctx.stroke();

		ctx.setLineDash([]);
		ctx.restore();
	}

	function draw() {
		ctx.clearRect(0, 0, canvas.width, canvas.height);

		const modelBounds = get_model_bounds_only();

		if (!points.length && !pitOutlinePoints.length) {
			$("#geo_info_box").html("No data loaded.");
			$("#geo_legend").hide();
			return;
		}

		if (points.length && modelBounds && showHeatmap) {
			draw_heatmap(modelBounds);
		}

		draw_contours(modelBounds);
		draw_generated_blocks(modelBounds);
		draw_pit_outline();
		draw_hover_block();
		draw_hover_marker(modelBounds);

		const blockSize = get_selected_block_size();
		const meshSize = get_manual_or_auto_mesh_size();

		const infoParts = [];

		infoParts.push(`<b>Data Source:</b> ${frappe.utils.escape_html(get_data_source())}`);

		if (is_geo_depth()) {
			infoParts.push(`<b>Geo Depth:</b> ${filters.geo_depth_batch.get_value() || "None"}`);
		} else {
			infoParts.push(`<b>Model Batch:</b> ${filters.import_batch.get_value() || "None"}`);
		}

		infoParts.push(`<b>Z Filter:</b> ${frappe.utils.escape_html(get_z_filter_description())}`);
		infoParts.push(`<b>Heatmap:</b> ${showHeatmap ? "On" : "Off"}`);
		infoParts.push(`<b>Contours:</b> ${showContours ? `${get_contour_interval()} interval (${contourLines.length.toLocaleString()} segments)` : "Off"}`);

		if (modelBounds) {
			infoParts.push(`<b>Points:</b> ${points.length.toLocaleString()}`);
			infoParts.push(`<b>X:</b> ${modelBounds.minX.toFixed(2)} - ${modelBounds.maxX.toFixed(2)}`);
			infoParts.push(`<b>Y:</b> ${modelBounds.minY.toFixed(2)} - ${modelBounds.maxY.toFixed(2)}`);
			infoParts.push(`<b>${get_z_label()}:</b> ${modelBounds.minZ.toFixed(2)} - ${modelBounds.maxZ.toFixed(2)}`);
		} else {
			infoParts.push(`<b>Points:</b> 0`);
		}

		infoParts.push(`<b>Pit Outline Points:</b> ${pitOutlinePoints.length.toLocaleString()}`);
		infoParts.push(`<b>Mesh Size:</b> ${meshSize.label} (${meshSize.source})`);
		infoParts.push(`<b>Block Size:</b> ${blockSize.x && blockSize.y ? blockSize.label : "Off"}`);
		infoParts.push(`<b>Blocks:</b> ${generatedBlocks.length.toLocaleString()}`);
		infoParts.push(`<b>Numbering:</b> ${autoNumberBlocks ? "Auto" : "Manual"}`);
		infoParts.push(`<b>Selected Block:</b> ${selectedBlock ? (selectedBlock.label || "Unnumbered") : "None"}`);
		infoParts.push(`<b>View Rotation:</b> ${(view.rotation * 180 / Math.PI).toFixed(1)}°`);
		infoParts.push(`<b>Pit Outline:</b> ${showPitOutline && pitOutlinePoints.length ? "On" : "Off"}`);

		$("#geo_info_box").html(infoParts.join("<br>"));

		update_legend(modelBounds);
	}

	function find_nearest_point(screenX, screenY) {
		if (!points.length) return null;

		const worldPoint = screen_to_world_point(screenX, screenY);
		const worldX = worldPoint.x;
		const worldY = worldPoint.y;
		const cellWorld = estimate_model_cell_size_world();
		const maxDistanceWorld = Math.max(cellWorld.x, cellWorld.y) * 1.2;

		let best = null;
		let bestDist = Infinity;

		for (const p of points) {
			const dx = p.x - worldX;
			const dy = p.y - worldY;
			const dist = Math.sqrt(dx * dx + dy * dy);

			if (dist < bestDist) {
				bestDist = dist;
				best = p;
			}
		}

		if (best && bestDist <= maxDistanceWorld) {
			return best;
		}

		return null;
	}

	function find_block_for_point(point) {
		if (!point || !generatedBlocks.length) return null;

		for (const block of generatedBlocks) {
			if (point_in_block(point, block)) {
				return block;
			}
		}

		return null;
	}

	function find_block_at_screen(screenX, screenY) {
		if (!generatedBlocks.length) return null;

		const worldPoint = screen_to_world_point(screenX, screenY);

		for (let i = generatedBlocks.length - 1; i >= 0; i--) {
			const block = generatedBlocks[i];

			if (point_in_block(worldPoint, block)) {
				return block;
			}
		}

		return null;
	}

	function select_block_at_screen(screenX, screenY) {
		const block = find_block_at_screen(screenX, screenY);

		if (!block) {
			selectedBlock = null;
			update_selected_block_info();
			draw();
			return;
		}

		selectedBlock = block;
		update_selected_block_info();
		draw();
	}

	function get_mouse_angle_from_canvas_centre(clientX, clientY) {
		const rect = canvas.getBoundingClientRect();
		const x = clientX - rect.left - canvas.width / 2;
		const y = clientY - rect.top - canvas.height / 2;

		return Math.atan2(y, x);
	}

	function show_hover_box(mouseX, mouseY, point) {
		if (!point) {
			hide_hover_box();
			return;
		}

		const variable = point.variable_name || filters.variable_name.get_value() || "";
		const batch = point.import_batch || "";

		hoverBlock = find_block_for_point(point);

		let depthHtml = "";

		if (is_geo_depth()) {
			depthHtml = `
				<div><b>Depth:</b> ${point.z.toFixed(3)}</div>
				${isFinite(point.reference_z) ? `<div><b>Reference Z:</b> ${point.reference_z.toFixed(3)}</div>` : ""}
				${isFinite(point.target_z) ? `<div><b>Target Z:</b> ${point.target_z.toFixed(3)}</div>` : ""}
				${point.reference_variable_code ? `<div><b>Reference:</b> ${frappe.utils.escape_html(point.reference_variable_code)}</div>` : ""}
				${point.target_variable_code ? `<div><b>Target:</b> ${frappe.utils.escape_html(point.target_variable_code)}</div>` : ""}
			`;
		} else {
			depthHtml = `<div><b>Point Z:</b> ${point.z.toFixed(3)}</div>`;
		}

		let blockHtml = "";

		if (hoverBlock) {
			blockHtml = `
				<div><b>Block:</b> ${hoverBlock.label || "Unnumbered"}</div>
				<div><b>Block Size:</b> ${hoverBlock.width} x ${hoverBlock.height} m</div>
				<div><b>Block Avg ${get_z_label()}:</b> ${hoverBlock.avg_z.toFixed(3)}</div>
				<div><b>Block Points:</b> ${hoverBlock.point_count} / ${hoverBlock.expected_point_count}</div>
				<div><b>Inside %:</b> ${hoverBlock.inside_percent.toFixed(1)}%</div>
				<div><b>Status:</b> ${frappe.utils.escape_html(hoverBlock.status)}</div>
			`;
		}

		hoverBox.innerHTML = `
			${depthHtml}
			<div><b>X:</b> ${point.x.toFixed(2)}</div>
			<div><b>Y:</b> ${point.y.toFixed(2)}</div>
			${variable ? `<div><b>Variable:</b> ${frappe.utils.escape_html(variable)}</div>` : ""}
			${batch ? `<div><b>Batch:</b> ${frappe.utils.escape_html(batch)}</div>` : ""}
			${blockHtml}
		`;

		const wrapRect = document.getElementById("geo_canvas_wrap").getBoundingClientRect();
		const left = Math.min(mouseX + 14, wrapRect.width - 355);
		const top = Math.max(8, mouseY + 14);

		hoverBox.style.left = `${left}px`;
		hoverBox.style.top = `${top}px`;
		hoverBox.style.display = "block";
	}

	function hide_hover_box() {
		hoverBox.style.display = "none";
		hoverBlock = null;
	}

	canvas.addEventListener("mousedown", function(e) {
		view.dragMoved = false;
		view.lastX = e.clientX;
		view.lastY = e.clientY;

		if (rotateViewMode) {
			view.isRotating = true;
			view.startRotation = view.rotation;
			view.startAngle = get_mouse_angle_from_canvas_centre(e.clientX, e.clientY);
			canvas.classList.add("dragging");
			hide_hover_box();
			return;
		}

		view.isDragging = true;
		canvas.classList.add("dragging");
		hide_hover_box();
	});

	window.addEventListener("mouseup", function() {
		view.isDragging = false;
		view.isRotating = false;
		canvas.classList.remove("dragging");
	});

	window.addEventListener("mousemove", function(e) {
		const rect = canvas.getBoundingClientRect();

		if (view.isRotating) {
			const currentAngle = get_mouse_angle_from_canvas_centre(e.clientX, e.clientY);
			view.rotation = view.startRotation + currentAngle - view.startAngle;

			if (Math.abs(e.clientX - view.lastX) + Math.abs(e.clientY - view.lastY) > 3) {
				view.dragMoved = true;
			}

			draw();
			return;
		}

		if (view.isDragging) {
			const dx = e.clientX - view.lastX;
			const dy = e.clientY - view.lastY;

			if (Math.abs(dx) + Math.abs(dy) > 3) {
				view.dragMoved = true;
			}

			view.offsetX += dx;
			view.offsetY += dy;

			view.lastX = e.clientX;
			view.lastY = e.clientY;

			draw();
			return;
		}

		const mouseX = e.clientX - rect.left;
		const mouseY = e.clientY - rect.top;

		hoverPoint = find_nearest_point(mouseX, mouseY);

		if (hoverPoint) {
			show_hover_box(mouseX, mouseY, hoverPoint);
		} else {
			hide_hover_box();
		}

		draw();
	});

	canvas.addEventListener("click", function(e) {
		if (view.dragMoved || rotateViewMode) {
			return;
		}

		const rect = canvas.getBoundingClientRect();
		select_block_at_screen(e.clientX - rect.left, e.clientY - rect.top);
	});

	canvas.addEventListener("mouseleave", function() {
		hoverPoint = null;
		hide_hover_box();
		draw();
	});

	canvas.addEventListener("wheel", function(e) {
		e.preventDefault();

		if (!points.length && !pitOutlinePoints.length) return;

		const rect = canvas.getBoundingClientRect();
		const mouseX = e.clientX - rect.left;
		const mouseY = e.clientY - rect.top;
		const rawMouse = unrotate_screen_point(mouseX, mouseY);
		const zoom = e.deltaY < 0 ? 1.15 : 0.87;

		view.offsetX = rawMouse.x - (rawMouse.x - view.offsetX) * zoom;
		view.offsetY = rawMouse.y - (rawMouse.y - view.offsetY) * zoom;
		view.scale *= zoom;

		draw();
	}, {
		passive: false
	});
};