frappe.pages["geology-viewer"].on_page_load = function(wrapper) {
    new GeologyViewer(wrapper);
};

class GeologyViewer {
    constructor(wrapper) {
        this.wrapper = $(wrapper);
        this.page = frappe.ui.make_app_page({
            parent: wrapper,
            title: "Geology Viewer",
            single_column: true
        });

        this.method_base = "is_production.geo_planning.page.geology_viewer.geology_viewer";

        this.blocks = [];
        this.filtered_blocks = [];
        this.bounds = null;
        this.hover_block = null;
        this.selected_block = null;
        this.material_stacks = [];
        this.layout_loaded = null;

        this.view = {
            scale: 1,
            offset_x: 0,
            offset_y: 0,
            dragging: false,
            last_x: 0,
            last_y: 0
        };

        this.settings = {
            show_labels: false,
            show_grid: true,
            hide_no_material: false,
            include_qualities: true,
            color_by: "Tonnes"
        };

        this.make_layout();
        this.make_controls();
        this.bind_canvas();
        this.resize_canvas();
        this.draw();
    }

    make_layout() {
        this.page.main.html(`
            <style>
                .gv-shell {
                    display: grid;
                    grid-template-columns: 380px minmax(0, 1fr);
                    gap: 14px;
                    height: calc(100vh - 104px);
                    min-height: 720px;
                }

                .gv-panel {
                    background: #fff;
                    border: 1px solid #d1d8dd;
                    border-radius: 12px;
                    overflow: hidden;
                    display: flex;
                    flex-direction: column;
                    min-height: 0;
                }

                .gv-panel-body {
                    padding: 14px;
                    overflow-y: auto;
                }

                .gv-section {
                    border-bottom: 1px solid #eef0f2;
                    padding-bottom: 14px;
                    margin-bottom: 14px;
                }

                .gv-section:last-child {
                    border-bottom: 0;
                    margin-bottom: 0;
                }

                .gv-section h4 {
                    font-size: 14px;
                    font-weight: 700;
                    margin: 0 0 10px;
                    color: #1f2937;
                }

                .gv-help {
                    color: #6b7280;
                    font-size: 11px;
                    line-height: 1.35;
                    margin-top: -4px;
                    margin-bottom: 8px;
                }

                .gv-actions {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 8px;
                    margin-top: 10px;
                }

                .gv-actions.single {
                    grid-template-columns: 1fr;
                }

                .gv-main {
                    min-width: 0;
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                }

                .gv-toolbar {
                    background: #fff;
                    border: 1px solid #d1d8dd;
                    border-radius: 10px;
                    padding: 8px 10px;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 10px;
                    flex-wrap: wrap;
                }

                .gv-toolbar-left,
                .gv-toolbar-right {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    flex-wrap: wrap;
                }

                .gv-canvas-wrap {
                    position: relative;
                    flex: 1;
                    min-height: 580px;
                    background: #f9fafb;
                    border: 1px solid #d1d8dd;
                    border-radius: 12px;
                    overflow: hidden;
                }

                #geology_viewer_canvas {
                    width: 100%;
                    height: 100%;
                    display: block;
                    cursor: grab;
                }

                #geology_viewer_canvas:active {
                    cursor: grabbing;
                }

                .gv-floating-summary {
                    position: absolute;
                    top: 12px;
                    left: 12px;
                    background: rgba(255,255,255,0.95);
                    border: 1px solid #d1d5db;
                    border-radius: 10px;
                    padding: 10px 12px;
                    font-size: 12px;
                    min-width: 260px;
                    max-width: 380px;
                    box-shadow: 0 4px 14px rgba(0,0,0,0.08);
                    pointer-events: none;
                    z-index: 2;
                }

                .gv-tooltip {
                    position: absolute;
                    display: none;
                    background: rgba(17, 24, 39, 0.94);
                    color: #fff;
                    border-radius: 10px;
                    padding: 10px 12px;
                    font-size: 12px;
                    max-width: 380px;
                    box-shadow: 0 8px 22px rgba(0,0,0,0.22);
                    pointer-events: none;
                    z-index: 4;
                }

                .gv-scale {
                    position: absolute;
                    right: 12px;
                    bottom: 12px;
                    background: rgba(255,255,255,0.94);
                    border: 1px solid #d1d5db;
                    border-radius: 8px;
                    padding: 6px 8px;
                    font-size: 11px;
                    color: #374151;
                    pointer-events: none;
                    z-index: 2;
                }

                .gv-kpi {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 6px;
                    margin-top: 8px;
                }

                .gv-kpi div {
                    background: #f8f9fa;
                    border: 1px solid #edf0f2;
                    border-radius: 8px;
                    padding: 7px;
                    font-size: 11px;
                }

                .gv-kpi b {
                    display: block;
                    font-size: 13px;
                    color: #111827;
                }

                .gv-pill {
                    display: inline-block;
                    padding: 2px 7px;
                    border-radius: 999px;
                    background: #eef2ff;
                    color: #3730a3;
                    font-size: 11px;
                    font-weight: 600;
                }

                .gv-detail-panel {
                    background: #fff;
                    border: 1px solid #d1d8dd;
                    border-radius: 10px;
                    padding: 12px;
                    min-height: 92px;
                    max-height: 260px;
                    overflow-y: auto;
                    font-size: 12px;
                }

                .gv-detail-title {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    gap: 8px;
                    margin-bottom: 8px;
                    font-weight: 700;
                }

                .gv-material-card {
                    border: 1px solid #edf0f2;
                    border-radius: 8px;
                    padding: 8px;
                    margin-top: 8px;
                    background: #fdfdfd;
                }

                .gv-material-card h5 {
                    margin: 0 0 6px;
                    font-size: 12px;
                    font-weight: 700;
                }

                .gv-mini-grid {
                    display: grid;
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                    gap: 5px 10px;
                    font-size: 11px;
                }

                .gv-quality-list {
                    margin-top: 6px;
                    padding-top: 6px;
                    border-top: 1px dashed #e5e7eb;
                }

                .gv-quality-line {
                    display: flex;
                    justify-content: space-between;
                    gap: 10px;
                    font-size: 11px;
                }
            </style>

            <div class="gv-shell">
                <div class="gv-panel">
                    <div class="gv-panel-body">
                        <div class="gv-section">
                            <h4>Viewer Filters</h4>
                            <div class="gv-help">
                                Select a project, pit layout and optional material stack. The viewer draws real Mining Block polygon GeoJSON and loads block material data.
                            </div>
                            <div id="geo_project_control"></div>
                            <div id="geo_pit_layout_control"></div>
                            <div id="material_stack_control"></div>
                            <div id="material_seam_control"></div>
                            <div class="gv-actions">
                                <button class="btn btn-primary" id="load_view_btn">Load Viewer</button>
                                <button class="btn btn-default" id="refresh_stacks_btn">Refresh Stacks</button>
                            </div>
                        </div>

                        <div class="gv-section">
                            <h4>Display</h4>
                            <div id="color_by_control"></div>
                            <div class="checkbox">
                                <label><input type="checkbox" id="show_labels_toggle"> Show block labels</label>
                            </div>
                            <div class="checkbox">
                                <label><input type="checkbox" id="show_grid_toggle" checked> Show grid</label>
                            </div>
                            <div class="checkbox">
                                <label><input type="checkbox" id="hide_no_material_toggle"> Hide blocks with no material data</label>
                            </div>
                            <div class="checkbox">
                                <label><input type="checkbox" id="include_qualities_toggle" checked> Include qualities / other values</label>
                            </div>
                        </div>

                        <div class="gv-section">
                            <h4>Totals</h4>
                            <div id="summary_box" class="gv-kpi">
                                <div><b>0</b>Blocks</div>
                                <div><b>0</b>Materials</div>
                                <div><b>0</b>Volume</div>
                                <div><b>0</b>Tonnes</div>
                            </div>
                        </div>

                        <div class="gv-section">
                            <h4>Block Details</h4>
                            <div id="block_detail_panel" class="gv-detail-panel">
                                Click a block to view material, volume, tonnes, density and qualities.
                            </div>
                        </div>
                    </div>
                </div>

                <div class="gv-main">
                    <div class="gv-toolbar">
                        <div class="gv-toolbar-left">
                            <button class="btn btn-xs btn-default" id="zoom_fit_btn">Zoom Fit</button>
                            <button class="btn btn-xs btn-default" id="zoom_in_btn">+</button>
                            <button class="btn btn-xs btn-default" id="zoom_out_btn">-</button>
                            <button class="btn btn-xs btn-default" id="clear_btn">Clear</button>
                        </div>
                        <div class="gv-toolbar-right text-muted">
                            Scroll to zoom · Drag to pan · Hover for block summary · Click for detail
                        </div>
                    </div>

                    <div class="gv-canvas-wrap">
                        <canvas id="geology_viewer_canvas"></canvas>
                        <div class="gv-floating-summary" id="floating_summary">
                            <b>No layout loaded</b><br>
                            Select a project and layout, then click Load Viewer.
                        </div>
                        <div class="gv-tooltip" id="hover_tooltip"></div>
                        <div class="gv-scale" id="scale_box">Scale: —</div>
                    </div>
                </div>
            </div>
        `);

        this.canvas = this.page.main.find("#geology_viewer_canvas")[0];
        this.ctx = this.canvas.getContext("2d");

        $(window).off("resize.geology_viewer").on("resize.geology_viewer", () => {
            this.resize_canvas();
            this.draw();
        });
    }

    make_controls() {
        this.controls = {};

        this.controls.geo_project = frappe.ui.form.make_control({
            parent: this.page.main.find("#geo_project_control"),
            df: {
                fieldtype: "Link",
                options: "Geo Project",
                label: "Geo Project",
                reqd: 1,
                onchange: () => {
                    this.refresh_material_stacks();
                }
            },
            render_input: true
        });

        this.controls.geo_pit_layout = frappe.ui.form.make_control({
            parent: this.page.main.find("#geo_pit_layout_control"),
            df: {
                fieldtype: "Link",
                options: "Geo Pit Layout",
                label: "Geo Pit Layout",
                reqd: 1,
                get_query: () => {
                    const geo_project = this.get_value("geo_project");
                    return geo_project ? { filters: { geo_project: geo_project } } : {};
                },
                onchange: () => {
                    this.refresh_material_stacks();
                }
            },
            render_input: true
        });

        this.controls.material_stack = frappe.ui.form.make_control({
            parent: this.page.main.find("#material_stack_control"),
            df: {
                fieldtype: "Select",
                label: "Material Stack",
                options: [""]
            },
            render_input: true
        });

        this.controls.material_seam = frappe.ui.form.make_control({
            parent: this.page.main.find("#material_seam_control"),
            df: {
                fieldtype: "Data",
                label: "Material / Seam Filter"
            },
            render_input: true
        });

        this.controls.color_by = frappe.ui.form.make_control({
            parent: this.page.main.find("#color_by_control"),
            df: {
                fieldtype: "Select",
                label: "Colour Blocks By",
                options: [
                    "Tonnes",
                    "Volume",
                    "Material Status",
                    "Planning Status",
                    "Block Status",
                    "Has Data"
                ],
                default: "Tonnes",
                onchange: () => {
                    this.settings.color_by = this.get_value("color_by") || "Tonnes";
                    this.draw();
                }
            },
            render_input: true
        });

        this.controls.color_by.set_value("Tonnes");

        this.page.main.find("#load_view_btn").on("click", () => this.load_viewer_data());
        this.page.main.find("#refresh_stacks_btn").on("click", () => this.refresh_material_stacks());

        this.page.main.find("#zoom_fit_btn").on("click", () => this.zoom_fit());
        this.page.main.find("#zoom_in_btn").on("click", () => this.zoom_by(1.25));
        this.page.main.find("#zoom_out_btn").on("click", () => this.zoom_by(0.8));
        this.page.main.find("#clear_btn").on("click", () => this.clear_view());

        this.page.main.find("#show_labels_toggle").on("change", (e) => {
            this.settings.show_labels = !!e.target.checked;
            this.draw();
        });

        this.page.main.find("#show_grid_toggle").on("change", (e) => {
            this.settings.show_grid = !!e.target.checked;
            this.draw();
        });

        this.page.main.find("#hide_no_material_toggle").on("change", (e) => {
            this.settings.hide_no_material = !!e.target.checked;
            this.apply_filters();
            this.draw();
        });

        this.page.main.find("#include_qualities_toggle").on("change", (e) => {
            this.settings.include_qualities = !!e.target.checked;
            this.load_viewer_data();
        });

        this.page.add_inner_button("Open Material Report", () => {
            frappe.set_route("query-report", "Mining Block Material Report");
        });

        this.page.add_inner_button("Open Mining Blocks", () => {
            frappe.set_route("List", "Mining Block");
        });

        this.page.add_inner_button("Open Material Summaries", () => {
            frappe.set_route("List", "Mining Block Material Summary");
        });
    }

    get_value(fieldname) {
        return this.controls[fieldname] ? this.controls[fieldname].get_value() : null;
    }

    set_select_options(control, rows, label_field = "label", value_field = "value") {
        const options = [""].concat((rows || []).map(row => ({
            label: row[label_field] || row[value_field],
            value: row[value_field]
        })));

        control.df.options = options;
        control.refresh();
    }

    refresh_material_stacks() {
        const geo_project = this.get_value("geo_project");
        const geo_pit_layout = this.get_value("geo_pit_layout");

        if (!geo_project && !geo_pit_layout) {
            this.set_select_options(this.controls.material_stack, []);
            return;
        }

        frappe.call({
            method: `${this.method_base}.get_material_stacks`,
            args: {
                geo_project: geo_project,
                geo_pit_layout: geo_pit_layout
            },
            callback: (r) => {
                this.material_stacks = r.message || [];
                this.set_select_options(this.controls.material_stack, this.material_stacks);
            }
        });
    }

    validate_load_inputs() {
        if (!this.get_value("geo_project")) {
            frappe.msgprint("Please select a Geo Project.");
            return false;
        }

        if (!this.get_value("geo_pit_layout")) {
            frappe.msgprint("Please select a Geo Pit Layout.");
            return false;
        }

        return true;
    }

    load_viewer_data() {
        if (!this.validate_load_inputs()) return;

        frappe.call({
            method: `${this.method_base}.load_viewer_data`,
            args: {
                geo_project: this.get_value("geo_project"),
                geo_pit_layout: this.get_value("geo_pit_layout"),
                material_stack: this.get_value("material_stack"),
                material_seam: this.get_value("material_seam"),
                include_qualities: this.settings.include_qualities ? 1 : 0
            },
            freeze: true,
            freeze_message: "Loading mining block polygons and material data...",
            callback: (r) => {
                const payload = r.message || {};
                this.layout_loaded = payload.layout || null;
                this.blocks = this.normalise_blocks(payload.blocks || []);
                this.filtered_blocks = this.blocks.slice();
                this.selected_block = null;
                this.hover_block = null;

                this.apply_filters();
                this.update_bounds();
                this.zoom_fit();
                this.update_summary(payload.summary || {});
                this.update_detail_panel(null);

                frappe.show_alert({
                    message: `Loaded ${this.blocks.length.toLocaleString()} mining blocks.`,
                    indicator: "green"
                });
            }
        });
    }

    normalise_blocks(blocks) {
        return (blocks || []).map((block, index) => {
            const polygon = this.parse_geojson_polygon(block.polygon_geojson);

            return {
                ...block,
                _index: index,
                block_code: block.mining_block_code || block.block_code || block.name,
                centroid_x: Number(block.centroid_x || 0),
                centroid_y: Number(block.centroid_y || 0),
                area: Number(block.area || 0),
                effective_area: Number(block.effective_area || 0),
                total_volume: Number(block.total_volume || 0),
                total_tonnes: Number(block.total_tonnes || 0),
                polygon: polygon
            };
        });
    }

    parse_geojson_polygon(value) {
        if (!value) return [];

        let geojson = value;

        try {
            if (typeof geojson === "string") {
                geojson = JSON.parse(geojson);
            }
        } catch (e) {
            return [];
        }

        if (!geojson || geojson.type !== "Polygon" || !Array.isArray(geojson.coordinates)) {
            return [];
        }

        const ring = geojson.coordinates[0] || [];

        return ring
            .map(pair => ({ x: Number(pair[0]), y: Number(pair[1]) }))
            .filter(point => Number.isFinite(point.x) && Number.isFinite(point.y));
    }

    apply_filters() {
        let rows = this.blocks.slice();

        if (this.settings.hide_no_material) {
            rows = rows.filter(block => (block.materials || []).length > 0);
        }

        this.filtered_blocks = rows;
        this.update_bounds();
    }

    clear_view() {
        this.blocks = [];
        this.filtered_blocks = [];
        this.bounds = null;
        this.hover_block = null;
        this.selected_block = null;
        this.layout_loaded = null;
        this.update_summary({});
        this.update_detail_panel(null);
        this.draw();
    }

    resize_canvas() {
        const wrap = this.page.main.find(".gv-canvas-wrap");
        this.canvas.width = wrap.width() || 900;
        this.canvas.height = wrap.height() || 620;
    }

    update_bounds() {
        const xs = [];
        const ys = [];

        for (const block of this.filtered_blocks || []) {
            for (const p of block.polygon || []) {
                xs.push(p.x);
                ys.push(p.y);
            }
        }

        if (!xs.length || !ys.length) {
            this.bounds = null;
            return;
        }

        const min_x = Math.min(...xs);
        const max_x = Math.max(...xs);
        const min_y = Math.min(...ys);
        const max_y = Math.max(...ys);

        const width = Math.max(max_x - min_x, 1);
        const height = Math.max(max_y - min_y, 1);
        const pad_x = width * 0.06;
        const pad_y = height * 0.06;

        this.bounds = {
            min_x: min_x - pad_x,
            max_x: max_x + pad_x,
            min_y: min_y - pad_y,
            max_y: max_y + pad_y
        };
    }

    zoom_fit() {
        this.resize_canvas();

        if (!this.bounds) {
            this.draw();
            return;
        }

        const pad = 60;
        const w = Math.max(this.bounds.max_x - this.bounds.min_x, 1);
        const h = Math.max(this.bounds.max_y - this.bounds.min_y, 1);

        const available_w = Math.max(this.canvas.width - pad * 2, 200);
        const available_h = Math.max(this.canvas.height - pad * 2, 200);

        const sx = available_w / w;
        const sy = available_h / h;

        this.view.scale = Math.min(sx, sy);

        if (!Number.isFinite(this.view.scale) || this.view.scale <= 0) {
            this.view.scale = 0.1;
        }

        this.view.offset_x = pad - this.bounds.min_x * this.view.scale;
        this.view.offset_y = this.canvas.height - pad + this.bounds.min_y * this.view.scale;

        this.draw();
    }

    zoom_by(factor) {
        const cx = this.canvas.width / 2;
        const cy = this.canvas.height / 2;
        const before = this.screen_to_world(cx, cy);

        this.view.scale *= factor;
        this.view.scale = Math.max(this.view.scale, 0.0001);

        const after = this.screen_to_world(cx, cy);

        this.view.offset_x += (after.x - before.x) * this.view.scale;
        this.view.offset_y -= (after.y - before.y) * this.view.scale;

        this.draw();
    }

    world_to_screen(x, y) {
        return {
            x: x * this.view.scale + this.view.offset_x,
            y: -y * this.view.scale + this.view.offset_y
        };
    }

    screen_to_world(x, y) {
        return {
            x: (x - this.view.offset_x) / this.view.scale,
            y: -(y - this.view.offset_y) / this.view.scale
        };
    }

    bind_canvas() {
        $(this.canvas).on("mousedown", (e) => {
            this.view.dragging = true;
            this.view.last_x = e.offsetX;
            this.view.last_y = e.offsetY;
        });

        $(this.canvas).on("mouseup mouseleave", () => {
            this.view.dragging = false;
        });

        $(this.canvas).on("mousemove", (e) => {
            if (this.view.dragging) {
                this.view.offset_x += e.offsetX - this.view.last_x;
                this.view.offset_y += e.offsetY - this.view.last_y;
                this.view.last_x = e.offsetX;
                this.view.last_y = e.offsetY;
                this.draw();
                return;
            }

            const world = this.screen_to_world(e.offsetX, e.offsetY);
            this.hover_block = this.find_block_at(world.x, world.y);
            this.update_hover_tooltip(e.offsetX, e.offsetY, this.hover_block);
            this.draw();
        });

        $(this.canvas).on("mouseleave", () => {
            this.hover_block = null;
            this.page.main.find("#hover_tooltip").hide();
            this.draw();
        });

        $(this.canvas).on("click", (e) => {
            const world = this.screen_to_world(e.offsetX, e.offsetY);
            this.selected_block = this.find_block_at(world.x, world.y);
            this.update_detail_panel(this.selected_block);
            this.draw();
        });

        $(this.canvas).on("wheel", (e) => {
            e.preventDefault();

            const rect = this.canvas.getBoundingClientRect();
            const mouse_x = e.originalEvent.clientX - rect.left;
            const mouse_y = e.originalEvent.clientY - rect.top;

            const before = this.screen_to_world(mouse_x, mouse_y);
            const factor = e.originalEvent.deltaY < 0 ? 1.12 : 0.89;

            this.view.scale *= factor;
            this.view.scale = Math.max(this.view.scale, 0.0001);

            const after = this.screen_to_world(mouse_x, mouse_y);

            this.view.offset_x += (after.x - before.x) * this.view.scale;
            this.view.offset_y -= (after.y - before.y) * this.view.scale;

            this.draw();
        });
    }

    find_block_at(x, y) {
        for (let i = (this.filtered_blocks || []).length - 1; i >= 0; i--) {
            const block = this.filtered_blocks[i];

            if (this.point_in_polygon(x, y, block.polygon)) {
                return block;
            }
        }

        return null;
    }

    point_in_polygon(x, y, polygon) {
        if (!polygon || polygon.length < 3) return false;

        let inside = false;

        for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
            const xi = polygon[i].x;
            const yi = polygon[i].y;
            const xj = polygon[j].x;
            const yj = polygon[j].y;

            const intersect =
                ((yi > y) !== (yj > y)) &&
                (x < ((xj - xi) * (y - yi)) / ((yj - yi) || 0.0000001) + xi);

            if (intersect) inside = !inside;
        }

        return inside;
    }

    draw() {
        const ctx = this.ctx;

        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        ctx.fillStyle = "#f9fafb";
        ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        if (this.settings.show_grid) {
            this.draw_grid();
        }

        for (const block of this.filtered_blocks || []) {
            this.draw_block(block);
        }

        this.update_scale_box();
    }

    draw_grid() {
        const ctx = this.ctx;

        ctx.save();
        ctx.strokeStyle = "#e5e7eb";
        ctx.lineWidth = 1;

        const spacing = 140;

        for (let x = 0; x < this.canvas.width; x += spacing) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, this.canvas.height);
            ctx.stroke();
        }

        for (let y = 0; y < this.canvas.height; y += spacing) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(this.canvas.width, y);
            ctx.stroke();
        }

        ctx.restore();
    }

    draw_block(block) {
        const ctx = this.ctx;
        const polygon = block.polygon || [];

        if (polygon.length < 3) return;

        const screens = polygon.map(p => this.world_to_screen(p.x, p.y));

        const min_sx = Math.min(...screens.map(p => p.x));
        const max_sx = Math.max(...screens.map(p => p.x));
        const min_sy = Math.min(...screens.map(p => p.y));
        const max_sy = Math.max(...screens.map(p => p.y));

        if (
            max_sx < -200 ||
            min_sx > this.canvas.width + 200 ||
            max_sy < -200 ||
            min_sy > this.canvas.height + 200
        ) {
            return;
        }

        const is_selected = this.selected_block && this.selected_block.name === block.name;
        const is_hover = this.hover_block && this.hover_block.name === block.name;

        ctx.beginPath();

        screens.forEach((point, i) => {
            if (i === 0) ctx.moveTo(point.x, point.y);
            else ctx.lineTo(point.x, point.y);
        });

        ctx.closePath();

        const color = this.get_block_color(block);

        if (is_selected) {
            ctx.fillStyle = "rgba(37, 99, 235, 0.48)";
            ctx.strokeStyle = "#1d4ed8";
            ctx.lineWidth = 3;
        } else if (is_hover) {
            ctx.fillStyle = "rgba(245, 158, 11, 0.42)";
            ctx.strokeStyle = "#d97706";
            ctx.lineWidth = 2.5;
        } else {
            ctx.fillStyle = color.fill;
            ctx.strokeStyle = color.stroke;
            ctx.lineWidth = 0.85;
        }

        ctx.fill();
        ctx.stroke();

        if (this.settings.show_labels || is_selected || is_hover) {
            const c = this.world_to_screen(block.centroid_x, block.centroid_y);
            ctx.fillStyle = "#111827";
            ctx.font = is_selected || is_hover ? "12px sans-serif" : "10px sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(block.block_code || block.name, c.x, c.y);
        }
    }

    get_block_color(block) {
        const color_by = this.settings.color_by || "Tonnes";

        if (color_by === "Has Data") {
            if ((block.materials || []).length) {
                return {
                    fill: "rgba(16, 185, 129, 0.30)",
                    stroke: "rgba(5, 150, 105, 0.70)"
                };
            }

            return {
                fill: "rgba(156, 163, 175, 0.20)",
                stroke: "rgba(107, 114, 128, 0.45)"
            };
        }

        if (color_by === "Material Status") {
            const statuses = (block.materials || []).map(m => m.material_status);

            if (statuses.includes("Mineable")) {
                return {
                    fill: "rgba(22, 163, 74, 0.36)",
                    stroke: "rgba(21, 128, 61, 0.75)"
                };
            }

            if (statuses.includes("Review")) {
                return {
                    fill: "rgba(245, 158, 11, 0.34)",
                    stroke: "rgba(217, 119, 6, 0.75)"
                };
            }

            if (statuses.includes("No Data") || !(block.materials || []).length) {
                return {
                    fill: "rgba(107, 114, 128, 0.20)",
                    stroke: "rgba(75, 85, 99, 0.45)"
                };
            }

            return {
                fill: "rgba(220, 38, 38, 0.30)",
                stroke: "rgba(185, 28, 28, 0.65)"
            };
        }

        if (color_by === "Planning Status") {
            if (block.planning_status === "Mineable") {
                return {
                    fill: "rgba(22, 163, 74, 0.36)",
                    stroke: "rgba(21, 128, 61, 0.75)"
                };
            }

            if (block.planning_status === "Review") {
                return {
                    fill: "rgba(245, 158, 11, 0.34)",
                    stroke: "rgba(217, 119, 6, 0.75)"
                };
            }

            if (block.planning_status === "Not Mineable") {
                return {
                    fill: "rgba(220, 38, 38, 0.30)",
                    stroke: "rgba(185, 28, 28, 0.65)"
                };
            }

            return {
                fill: "rgba(107, 114, 128, 0.20)",
                stroke: "rgba(75, 85, 99, 0.45)"
            };
        }

        if (color_by === "Block Status") {
            if (["Available", "Planned", "Scheduled", "Mining", "Complete"].includes(block.block_status)) {
                return {
                    fill: "rgba(59, 130, 246, 0.28)",
                    stroke: "rgba(37, 99, 235, 0.60)"
                };
            }

            if (block.block_status === "Excluded") {
                return {
                    fill: "rgba(220, 38, 38, 0.28)",
                    stroke: "rgba(185, 28, 28, 0.65)"
                };
            }

            return {
                fill: "rgba(107, 114, 128, 0.18)",
                stroke: "rgba(75, 85, 99, 0.45)"
            };
        }

        const value = color_by === "Volume" ? Number(block.total_volume || 0) : Number(block.total_tonnes || 0);
        const max_value = color_by === "Volume" ? this.max_volume() : this.max_tonnes();

        if (!value || !max_value) {
            return {
                fill: "rgba(156, 163, 175, 0.20)",
                stroke: "rgba(107, 114, 128, 0.45)"
            };
        }

        const ratio = Math.max(0.08, Math.min(1, value / max_value));
        const alpha = 0.18 + ratio * 0.52;

        return {
            fill: `rgba(16, 185, 129, ${alpha})`,
            stroke: "rgba(5, 150, 105, 0.70)"
        };
    }

    max_volume() {
        return Math.max(...(this.filtered_blocks || []).map(b => Number(b.total_volume || 0)), 0);
    }

    max_tonnes() {
        return Math.max(...(this.filtered_blocks || []).map(b => Number(b.total_tonnes || 0)), 0);
    }

    update_hover_tooltip(x, y, block) {
        const tooltip = this.page.main.find("#hover_tooltip");

        if (!block) {
            tooltip.hide();
            return;
        }

        tooltip.html(this.make_block_tooltip_html(block));

        const wrap = this.page.main.find(".gv-canvas-wrap");
        const max_x = wrap.width() - 410;
        const left = Math.min(Math.max(x + 18, 10), Math.max(max_x, 10));
        const top = Math.min(Math.max(y + 18, 10), wrap.height() - 180);

        tooltip.css({
            left: `${left}px`,
            top: `${top}px`,
            display: "block"
        });
    }

    make_block_tooltip_html(block) {
        const materials = block.materials || [];
        const top_materials = materials.slice(0, 4);

        let html = `
            <b>${frappe.utils.escape_html(block.block_code || block.name)}</b><br>
            Area: ${this.format_number(block.effective_area)}<br>
            Volume: ${this.format_number(block.total_volume)}<br>
            Tonnes: ${this.format_number(block.total_tonnes)}<br>
            Materials: ${materials.length}
        `;

        if (top_materials.length) {
            html += `<hr style="margin:6px 0;border-color:rgba(255,255,255,0.18)">`;

            top_materials.forEach(material => {
                html += `
                    <div>
                        <b>${frappe.utils.escape_html(material.material_seam || "")}</b>
                        · Vol ${this.format_number(material.volume)}
                        · t ${this.format_number(material.tonnes)}
                    </div>
                `;
            });

            if (materials.length > top_materials.length) {
                html += `<div class="text-muted">+ ${materials.length - top_materials.length} more</div>`;
            }
        }

        return html;
    }

    update_detail_panel(block) {
        const panel = this.page.main.find("#block_detail_panel");

        if (!block) {
            panel.html("Click a block to view material, volume, tonnes, density and qualities.");
            return;
        }

        let html = `
            <div class="gv-detail-title">
                <span>${frappe.utils.escape_html(block.block_code || block.name)}</span>
                <button class="btn btn-xs btn-default" id="open_block_btn">Open Block</button>
            </div>

            <div class="gv-mini-grid">
                <div><b>Effective Area</b><br>${this.format_number(block.effective_area)}</div>
                <div><b>Total Volume</b><br>${this.format_number(block.total_volume)}</div>
                <div><b>Total Tonnes</b><br>${this.format_number(block.total_tonnes)}</div>
                <div><b>Materials</b><br>${(block.materials || []).length}</div>
                <div><b>Planning Status</b><br>${frappe.utils.escape_html(block.planning_status || "")}</div>
                <div><b>Block Status</b><br>${frappe.utils.escape_html(block.block_status || "")}</div>
            </div>
        `;

        if (!(block.materials || []).length) {
            html += `<p class="text-muted" style="margin-top:10px;">No material summary records found for this block with the selected filters.</p>`;
        }

        (block.materials || []).forEach(material => {
            html += this.make_material_card_html(material);
        });

        panel.html(html);

        panel.find("#open_block_btn").on("click", () => {
            frappe.set_route("Form", "Mining Block", block.name);
        });
    }

    make_material_card_html(material) {
        let html = `
            <div class="gv-material-card">
                <h5>${frappe.utils.escape_html(material.material_seam || "Material")}</h5>
                <div class="gv-mini-grid">
                    <div><b>Thickness</b><br>${this.format_number(material.thickness_value)}</div>
                    <div><b>Density / RD</b><br>${this.format_number(material.density_value)}</div>
                    <div><b>Volume</b><br>${this.format_number(material.volume)}</div>
                    <div><b>Tonnes</b><br>${this.format_number(material.tonnes)}</div>
                    <div><b>Status</b><br>${frappe.utils.escape_html(material.material_status || "")}</div>
                    <div><b>Points</b><br>${this.format_number(material.thickness_point_count || material.density_point_count || 0, 0)}</div>
                </div>
        `;

        const qualities = material.qualities || [];

        if (qualities.length) {
            html += `<div class="gv-quality-list"><b>Qualities / Other Values</b>`;

            qualities.forEach(q => {
                const label = q.variable_code || q.variable_name || q.value_type || "Value";
                html += `
                    <div class="gv-quality-line">
                        <span>${frappe.utils.escape_html(label)}</span>
                        <span>${this.format_number(q.avg_value)}</span>
                    </div>
                `;
            });

            html += `</div>`;
        }

        html += `</div>`;
        return html;
    }

    update_summary(summary) {
        const block_count = summary.block_count || this.filtered_blocks.length || 0;
        const material_count = summary.material_count || 0;
        const total_volume = summary.total_volume || 0;
        const total_tonnes = summary.total_tonnes || 0;

        this.page.main.find("#summary_box").html(`
            <div><b>${this.format_number(block_count, 0)}</b>Blocks</div>
            <div><b>${this.format_number(material_count, 0)}</b>Materials</div>
            <div><b>${this.format_number(total_volume)}</b>Volume</div>
            <div><b>${this.format_number(total_tonnes)}</b>Tonnes</div>
        `);

        const layout_text = this.layout_loaded
            ? `${this.layout_loaded.layout_name || this.layout_loaded.layout_code || this.layout_loaded.name}`
            : "No layout loaded";

        this.page.main.find("#floating_summary").html(`
            <b>${frappe.utils.escape_html(layout_text)}</b><br>
            Blocks: ${this.format_number(block_count, 0)}<br>
            Materials: ${this.format_number(material_count, 0)}<br>
            Volume: ${this.format_number(total_volume)}<br>
            Tonnes: ${this.format_number(total_tonnes)}<br>
            Colour: ${frappe.utils.escape_html(this.settings.color_by || "")}
        `);
    }

    update_scale_box() {
        const scale = this.view.scale ? this.view.scale.toFixed(5) : "—";
        let text = `Scale: ${scale} px/unit`;

        if (this.bounds) {
            const w = this.bounds.max_x - this.bounds.min_x;
            const h = this.bounds.max_y - this.bounds.min_y;
            text += ` · View: ${w.toFixed(0)} x ${h.toFixed(0)}`;
        }

        this.page.main.find("#scale_box").text(text);
    }

    format_number(value, decimals = 2) {
        const num = Number(value || 0);

        return num.toLocaleString(undefined, {
            minimumFractionDigits: 0,
            maximumFractionDigits: decimals
        });
    }
}