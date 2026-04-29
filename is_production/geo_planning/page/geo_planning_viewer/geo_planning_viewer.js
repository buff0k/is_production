frappe.pages["geo-planning-viewer"].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Geo Planning Viewer",
		single_column: true
	});

	let points = [];
	let view = {
		scale: 1,
		offsetX: 0,
		offsetY: 0,
		isDragging: false,
		lastX: 0,
		lastY: 0
	};

	$(page.body).html(`
		<style>
			.geo-viewer-wrap {
				height: calc(100vh - 115px);
				display: flex;
				flex-direction: column;
				gap: 10px;
			}

			.geo-filter-bar {
				background: #fff;
				border: 1px solid #e5e5e5;
				border-radius: 8px;
				padding: 12px;
			}

			.geo-canvas-wrap {
				position: relative;
				flex: 1;
				min-height: 520px;
				background: #fafafa;
				border: 1px solid #ddd;
				border-radius: 8px;
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
				background: rgba(255, 255, 255, 0.92);
				border: 1px solid #ddd;
				border-radius: 6px;
				padding: 8px 10px;
				font-size: 12px;
				line-height: 1.4;
				pointer-events: none;
			}

			.geo-legend {
				position: absolute;
				right: 12px;
				bottom: 12px;
				background: rgba(255, 255, 255, 0.92);
				border: 1px solid #ddd;
				border-radius: 6px;
				padding: 8px 10px;
				font-size: 12px;
				pointer-events: none;
			}

			.geo-legend-bar {
				width: 180px;
				height: 14px;
				background: linear-gradient(to right, blue, cyan, lime, yellow, red);
				border: 1px solid #aaa;
				margin: 4px 0;
			}
		</style>

		<div class="geo-viewer-wrap">
			<div class="geo-filter-bar">
				<div class="row">
					<div class="col-md-2" id="geo_project_filter"></div>
					<div class="col-md-2" id="geo_model_output_filter"></div>
					<div class="col-md-2" id="version_filter"></div>
					<div class="col-md-2" id="variable_filter"></div>
					<div class="col-md-2" id="batch_filter"></div>
					<div class="col-md-2" id="block_size_filter"></div>
				</div>

				<div class="row" style="margin-top: 8px;">
					<div class="col-md-12">
						<button class="btn btn-primary btn-sm" id="load_geo_points">Load View</button>
						<button class="btn btn-default btn-sm" id="fit_geo_view">Fit</button>
						<button class="btn btn-default btn-sm" id="toggle_blocks">Toggle Blocks</button>
					</div>
				</div>
			</div>

			<div class="geo-canvas-wrap" id="geo_canvas_wrap">
				<canvas id="geo_canvas"></canvas>

				<div class="geo-info-box" id="geo_info_box">
					No data loaded.
				</div>

				<div class="geo-legend" id="geo_legend" style="display:none;">
					<div><b>Z Value</b></div>
					<div class="geo-legend-bar"></div>
					<div style="display:flex; justify-content:space-between;">
						<span id="geo_min_z"></span>
						<span id="geo_max_z"></span>
					</div>
				</div>
			</div>
		</div>
	`);

	const filters = {};
	let showBlocks = true;

	function make_control(parent, df) {
		return frappe.ui.form.make_control({
			parent: $(parent),
			df,
			render_input: true
		});
	}

	filters.geo_project = make_control("#geo_project_filter", {
		fieldtype: "Link",
		options: "Geo Project",
		label: "Project",
		fieldname: "geo_project"
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
		label: "Batch",
		fieldname: "import_batch"
	});

	filters.block_size = make_control("#block_size_filter", {
		fieldtype: "Select",
		label: "Mining Block Size",
		fieldname: "block_size",
		options: [
			"",
			"10x10",
			"20x20",
			"30x30",
			"40x40",
			"50x50",
			"60x60",
			"70x70",
			"80x80",
			"90x90"
		].join("\n"),
		default: "10x10",
		change: function() {
			draw();
		}
	});

	const canvas = document.getElementById("geo_canvas");
	const ctx = canvas.getContext("2d");

	function resize_canvas() {
		const wrap = document.getElementById("geo_canvas_wrap");
		const rect = wrap.getBoundingClientRect();

		canvas.width = Math.max(900, Math.floor(rect.width));
		canvas.height = Math.max(520, Math.floor(rect.height));

		if (points.length) {
			fit_view();
			draw();
		}
	}

	window.addEventListener("resize", resize_canvas);
	setTimeout(resize_canvas, 100);

	$("#load_geo_points").on("click", function() {
		frappe.call({
			method: "is_production.geo_planning.page.geo_planning_viewer.geo_planning_viewer.get_geo_points",
			args: {
				geo_project: filters.geo_project.get_value(),
				geo_model_output: filters.geo_model_output.get_value(),
				version_tag: filters.version_tag.get_value(),
				variable_name: filters.variable_name.get_value(),
				import_batch: filters.import_batch.get_value()
			},
			freeze: true,
			freeze_message: "Loading geological grid...",
			callback(r) {
				points = (r.message || []).map(p => ({
					x: Number(p.x),
					y: Number(p.y),
					z: Number(p.z),
					variable_name: p.variable_name,
					version_tag: p.version_tag,
					import_batch: p.import_batch
				})).filter(p => isFinite(p.x) && isFinite(p.y) && isFinite(p.z));

				fit_view();
				draw();
			}
		});
	});

	$("#fit_geo_view").on("click", function() {
		fit_view();
		draw();
	});

	$("#toggle_blocks").on("click", function() {
		showBlocks = !showBlocks;
		draw();
	});

	function get_selected_block_size() {
		const value = filters.block_size.get_value();

		if (!value) return 0;

		const size = Number(String(value).split("x")[0]);
		return isFinite(size) ? size : 0;
	}

	function get_bounds() {
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

	function fit_view() {
		if (!points.length) return;

		const b = get_bounds();
		const pad = 55;

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

	function world_to_screen_x(x) {
		return x * view.scale + view.offsetX;
	}

	function world_to_screen_y(y) {
		return -y * view.scale + view.offsetY;
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

	function estimate_cell_size() {
		if (points.length < 2) return 3;

		const sample = points.slice(0, Math.min(points.length, 1000));
		const uniqueX = [...new Set(sample.map(p => p.x))].sort((a, b) => a - b);
		const uniqueY = [...new Set(sample.map(p => p.y))].sort((a, b) => a - b);

		function median_gap(values) {
			const gaps = [];

			for (let i = 1; i < values.length; i++) {
				const gap = values[i] - values[i - 1];
				if (gap > 0) gaps.push(gap);
			}

			if (!gaps.length) return 1;

			gaps.sort((a, b) => a - b);
			return gaps[Math.floor(gaps.length / 2)];
		}

		const dx = median_gap(uniqueX);
		const dy = median_gap(uniqueY);

		return Math.max(1, Math.min(dx, dy) * view.scale);
	}

	function draw_mining_blocks(bounds) {
		const blockSize = get_selected_block_size();

		if (!blockSize || !showBlocks) return;

		const startX = Math.floor(bounds.minX / blockSize) * blockSize;
		const endX = Math.ceil(bounds.maxX / blockSize) * blockSize;
		const startY = Math.floor(bounds.minY / blockSize) * blockSize;
		const endY = Math.ceil(bounds.maxY / blockSize) * blockSize;

		ctx.save();

		ctx.strokeStyle = "rgba(0, 0, 0, 0.45)";
		ctx.lineWidth = 1;

		const screenBlock = blockSize * view.scale;
		const showLabels = screenBlock >= 35;

		for (let x = startX; x <= endX; x += blockSize) {
			const sx = world_to_screen_x(x);
			ctx.beginPath();
			ctx.moveTo(sx, world_to_screen_y(startY));
			ctx.lineTo(sx, world_to_screen_y(endY));
			ctx.stroke();
		}

		for (let y = startY; y <= endY; y += blockSize) {
			const sy = world_to_screen_y(y);
			ctx.beginPath();
			ctx.moveTo(world_to_screen_x(startX), sy);
			ctx.lineTo(world_to_screen_x(endX), sy);
			ctx.stroke();
		}

		if (showLabels) {
			ctx.fillStyle = "rgba(0, 0, 0, 0.65)";
			ctx.font = "10px Arial";

			for (let x = startX; x < endX; x += blockSize) {
				for (let y = startY; y < endY; y += blockSize) {
					const sx = world_to_screen_x(x + blockSize / 2);
					const sy = world_to_screen_y(y + blockSize / 2);

					ctx.fillText(`${blockSize}x${blockSize}`, sx - 14, sy + 3);
				}
			}
		}

		ctx.restore();
	}

	function draw_block_averages(bounds) {
		const blockSize = get_selected_block_size();

		if (!blockSize || !showBlocks) return;

		const blocks = {};

		for (const p of points) {
			const bx = Math.floor(p.x / blockSize) * blockSize;
			const by = Math.floor(p.y / blockSize) * blockSize;
			const key = `${bx}|${by}`;

			if (!blocks[key]) {
				blocks[key] = {
					x: bx,
					y: by,
					sum: 0,
					count: 0
				};
			}

			blocks[key].sum += p.z;
			blocks[key].count += 1;
		}

		ctx.save();

		for (const key in blocks) {
			const b = blocks[key];
			const avgZ = b.sum / b.count;

			const sx = world_to_screen_x(b.x);
			const sy = world_to_screen_y(b.y + blockSize);
			const sw = blockSize * view.scale;
			const sh = blockSize * view.scale;

			ctx.fillStyle = value_colour(avgZ, bounds.minZ, bounds.maxZ);
			ctx.globalAlpha = 0.28;
			ctx.fillRect(sx, sy, sw, sh);
		}

		ctx.globalAlpha = 1;
		ctx.restore();
	}

	function draw() {
		ctx.clearRect(0, 0, canvas.width, canvas.height);

		if (!points.length) {
			$("#geo_info_box").html("No points found for selected filters.");
			$("#geo_legend").hide();
			return;
		}

		const b = get_bounds();
		const cell = Math.max(1, estimate_cell_size());

		for (const p of points) {
			const x = world_to_screen_x(p.x);
			const y = world_to_screen_y(p.y);

			ctx.fillStyle = value_colour(p.z, b.minZ, b.maxZ);
			ctx.fillRect(x - cell / 2, y - cell / 2, cell + 0.5, cell + 0.5);
		}

		draw_block_averages(b);
		draw_mining_blocks(b);

		ctx.strokeStyle = "#111";
		ctx.lineWidth = 1.5;
		ctx.strokeRect(
			world_to_screen_x(b.minX),
			world_to_screen_y(b.maxY),
			(b.maxX - b.minX) * view.scale,
			(b.maxY - b.minY) * view.scale
		);

		const blockSize = get_selected_block_size();

		$("#geo_info_box").html(`
			<b>Points:</b> ${points.length.toLocaleString()}<br>
			<b>X:</b> ${b.minX.toFixed(2)} - ${b.maxX.toFixed(2)}<br>
			<b>Y:</b> ${b.minY.toFixed(2)} - ${b.maxY.toFixed(2)}<br>
			<b>Z:</b> ${b.minZ.toFixed(2)} - ${b.maxZ.toFixed(2)}<br>
			<b>Mining Blocks:</b> ${blockSize ? blockSize + "x" + blockSize : "Off"}
		`);

		$("#geo_min_z").text(b.minZ.toFixed(2));
		$("#geo_max_z").text(b.maxZ.toFixed(2));
		$("#geo_legend").show();
	}

	canvas.addEventListener("mousedown", function(e) {
		view.isDragging = true;
		view.lastX = e.clientX;
		view.lastY = e.clientY;
		canvas.classList.add("dragging");
	});

	window.addEventListener("mouseup", function() {
		view.isDragging = false;
		canvas.classList.remove("dragging");
	});

	window.addEventListener("mousemove", function(e) {
		if (!view.isDragging) return;

		const dx = e.clientX - view.lastX;
		const dy = e.clientY - view.lastY;

		view.offsetX += dx;
		view.offsetY += dy;

		view.lastX = e.clientX;
		view.lastY = e.clientY;

		draw();
	});

	canvas.addEventListener("wheel", function(e) {
		e.preventDefault();

		if (!points.length) return;

		const rect = canvas.getBoundingClientRect();
		const mouseX = e.clientX - rect.left;
		const mouseY = e.clientY - rect.top;

		const zoom = e.deltaY < 0 ? 1.15 : 0.87;

		view.offsetX = mouseX - (mouseX - view.offsetX) * zoom;
		view.offsetY = mouseY - (mouseY - view.offsetY) * zoom;
		view.scale *= zoom;

		draw();
	}, { passive: false });
};