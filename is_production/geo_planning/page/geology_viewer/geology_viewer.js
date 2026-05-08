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

        this.preview_blocks = [];
        this.saved_blocks = [];
        this.current_blocks = [];
        this.overlay_results = {};
        this.overlay_payload = null;
        this.last_saved_geology_run = null;
        this.phase3_payload = null;
        this.phase4_payload = null;
        this.import_batches = [];
        this.calculation_batches = [];
        this.saved_layouts = [];
        this.pit_batches = [];
        this.bounds = null;
        this.hover_block = null;
        this.selected_block = null;
        this.loaded_layout = null;

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
            show_partial: true
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
                    grid-template-columns: 360px minmax(0, 1fr);
                    gap: 14px;
                    height: calc(100vh - 110px);
                    min-height: 680px;
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
                    min-height: 560px;
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
                    background: rgba(255,255,255,0.94);
                    border: 1px solid #d1d5db;
                    border-radius: 10px;
                    padding: 10px 12px;
                    font-size: 12px;
                    min-width: 230px;
                    max-width: 340px;
                    box-shadow: 0 4px 14px rgba(0,0,0,0.08);
                    pointer-events: none;
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
                }
                .gv-block-info {
                    background: #fff;
                    border: 1px solid #d1d8dd;
                    border-radius: 10px;
                    padding: 10px 12px;
                    min-height: 54px;
                    font-size: 12px;
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
            </style>

            <div class="gv-shell">
                <div class="gv-panel">
                    <div class="gv-panel-body">
                        <div class="gv-section">
                            <h4>1. Create Pit Layout</h4>
                            <div class="gv-help">Generate blocks from a selected Pit Outline Batch. This creates preview geometry only until you click Save Layout.</div>
                            <div id="project_control"></div>
                            <div id="pit_batch_control"></div>
                            <div id="layout_name_control"></div>
                            <div id="layout_version_control"></div>
                            <div class="row">
                                <div class="col-xs-6" id="block_size_x_control"></div>
                                <div class="col-xs-6" id="block_size_y_control"></div>
                            </div>
                            <div class="row">
                                <div class="col-xs-6" id="angle_control"></div>
                                <div class="col-xs-6" id="inside_control"></div>
                            </div>
                            <div class="row">
                                <div class="col-xs-6" id="cut_no_control"></div>
                                <div class="col-xs-6" id="numbering_control"></div>
                            </div>
                            <div class="gv-actions">
                                <button class="btn btn-primary" id="preview_blocks_btn">Preview Blocks</button>
                                <button class="btn btn-success" id="save_layout_btn">Save Layout</button>
                            </div>
                        </div>

                        <div class="gv-section">
                            <h4>2. Load Saved Layout</h4>
                            <div class="gv-help">Use this after a layout has been saved. This is the layout we will use in Phase 2 for geology overlays.</div>
                            <div id="saved_layout_control"></div>
                            <div class="gv-actions">
                                <button class="btn btn-default" id="refresh_layouts_btn">Refresh</button>
                                <button class="btn btn-info" id="load_layout_btn">Load Layout</button>
                            </div>
                        </div>

                        <div class="gv-section">
                            <h4>3. Geology Overlay</h4>
                            <div class="gv-help">Apply a selected Geo Import Batch or Geo Calculation Batch to the loaded layout. Enter rules only when needed.</div>
                            <div id="source_type_control"></div>
                            <div id="geo_import_batch_control"></div>
                            <div id="geo_calculation_batch_control"></div>
                            <div id="variable_name_control"></div>
                            <div id="value_meaning_control"></div>
                            <div class="checkbox"><label><input type="checkbox" id="rule_enabled_toggle"> Enable rule/filter</label></div>
                            <div id="rule_operator_control"></div>
                            <div class="row">
                                <div class="col-xs-6" id="rule_value_control"></div>
                                <div class="col-xs-6" id="rule_value_to_control"></div>
                            </div>
                            <div id="run_name_control"></div>
                            <div class="gv-actions">
                                <button class="btn btn-warning" id="preview_overlay_btn">Preview Overlay</button>
                                <button class="btn btn-success" id="save_geology_run_btn">Save Run</button>
                            </div>
                        </div>

                        <div class="gv-section">
                            <h4>4. Final Mining Blocks</h4>
                            <div class="gv-help">After a layout and geology run are approved, mark the layout final and create official Mining Block records.</div>
                            <div id="final_geology_run_control"></div>
                            <div class="checkbox"><label><input type="checkbox" id="overwrite_mining_blocks_toggle"> Overwrite existing Mining Blocks / material values</label></div>
                            <div class="gv-actions">
                                <button class="btn btn-default" id="mark_final_btn">Mark Final</button>
                                <button class="btn btn-danger" id="generate_mining_blocks_btn">Generate Blocks</button>
                            </div>
                        </div>

                        <div class="gv-section">
                            <h4>5. Planning Calculations</h4>
                            <div class="gv-help">Calculate volume and tonnes from official Mining Block Material Values. First version uses density entered manually.</div>
                            <div id="calc_value_type_control"></div>
                            <div id="calc_material_seam_control"></div>
                            <div id="calc_density_control"></div>
                            <div class="checkbox"><label><input type="checkbox" id="mineable_only_toggle" checked> Calculate mineable values only</label></div>
                            <div class="gv-actions">
                                <button class="btn btn-default" id="planning_summary_btn">Check Summary</button>
                                <button class="btn btn-primary" id="calculate_tonnes_btn">Calculate Tonnes</button>
                            </div>
                        </div>

                        <div class="gv-section">
                            <h4>Display</h4>
                            <div class="checkbox"><label><input type="checkbox" id="show_labels_toggle"> Show labels</label></div>
                            <div class="checkbox"><label><input type="checkbox" id="show_grid_toggle" checked> Show grid</label></div>
                            <div class="checkbox"><label><input type="checkbox" id="show_partial_toggle" checked> Show partial blocks</label></div>
                        </div>

                        <div class="gv-section">
                            <h4>Phase Tracker</h4>
                            <div class="gv-help">
                                <span class="gv-pill">Current</span> Phases 1–4 workflow<br>
                                Next: Phase 5 — Scheduling Later
                            </div>
                            <div id="summary_box" class="gv-kpi">
                                <div><b>0</b>Blocks</div>
                                <div><b>0</b>Effective Area</div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="gv-main">
                    <div class="gv-toolbar">
                        <div class="gv-toolbar-left">
                            <button class="btn btn-xs btn-default" id="zoom_fit_btn">Zoom Fit</button>
                            <button class="btn btn-xs btn-default" id="clear_btn">Clear</button>
                            <button class="btn btn-xs btn-default" id="zoom_in_btn">+</button>
                            <button class="btn btn-xs btn-default" id="zoom_out_btn">-</button>
                        </div>
                        <div class="gv-toolbar-right text-muted">
                            Scroll to zoom · Drag to pan · Click a block to inspect
                        </div>
                    </div>

                    <div class="gv-canvas-wrap">
                        <canvas id="geology_viewer_canvas"></canvas>
                        <div class="gv-floating-summary" id="floating_summary">
                            <b>No layout loaded</b><br>
                            Select a project and pit outline, then preview blocks.
                        </div>
                        <div class="gv-scale" id="scale_box">Scale: —</div>
                    </div>

                    <div id="block_info" class="gv-block-info">
                        Click a block to inspect it.
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
            parent: this.page.main.find("#project_control"),
            df: {
                fieldtype: "Link",
                options: "Geo Project",
                label: "Geo Project",
                reqd: 1,
                onchange: () => {
                    this.load_pit_batches();
                    this.load_saved_layouts();
                    this.load_geology_batches();
                }
            },
            render_input: true
        });

        this.controls.pit_outline_batch = frappe.ui.form.make_control({
            parent: this.page.main.find("#pit_batch_control"),
            df: { fieldtype: "Select", label: "Pit Outline Batch", options: [""], reqd: 1 },
            render_input: true
        });

        this.controls.layout_name = frappe.ui.form.make_control({
            parent: this.page.main.find("#layout_name_control"),
            df: { fieldtype: "Data", label: "Layout Name", default: "Pit Layout 100x40" },
            render_input: true
        });

        this.controls.layout_version = frappe.ui.form.make_control({
            parent: this.page.main.find("#layout_version_control"),
            df: { fieldtype: "Data", label: "Layout Version", default: "V001" },
            render_input: true
        });

        this.controls.block_size_x = frappe.ui.form.make_control({
            parent: this.page.main.find("#block_size_x_control"),
            df: { fieldtype: "Float", label: "Block Size X", default: 100 },
            render_input: true
        });

        this.controls.block_size_y = frappe.ui.form.make_control({
            parent: this.page.main.find("#block_size_y_control"),
            df: { fieldtype: "Float", label: "Block Size Y", default: 40 },
            render_input: true
        });

        this.controls.block_angle_degrees = frappe.ui.form.make_control({
            parent: this.page.main.find("#angle_control"),
            df: { fieldtype: "Float", label: "Angle Degrees", default: 0 },
            render_input: true
        });

        this.controls.minimum_inside_percent = frappe.ui.form.make_control({
            parent: this.page.main.find("#inside_control"),
            df: { fieldtype: "Float", label: "Minimum Inside %", default: 50 },
            render_input: true
        });

        this.controls.default_cut_no = frappe.ui.form.make_control({
            parent: this.page.main.find("#cut_no_control"),
            df: { fieldtype: "Int", label: "Cut No", default: 1 },
            render_input: true
        });

        this.controls.numbering_style = frappe.ui.form.make_control({
            parent: this.page.main.find("#numbering_control"),
            df: { fieldtype: "Select", label: "Numbering", options: ["C1B1", "Row Column", "Custom"], default: "C1B1" },
            render_input: true
        });

        this.controls.saved_layout = frappe.ui.form.make_control({
            parent: this.page.main.find("#saved_layout_control"),
            df: { fieldtype: "Select", label: "Saved Geo Pit Layout", options: [""] },
            render_input: true
        });

        this.controls.source_type = frappe.ui.form.make_control({
            parent: this.page.main.find("#source_type_control"),
            df: {
                fieldtype: "Select",
                label: "Source Type",
                options: ["", "Geo Import Batch", "Geo Calculation Batch"],
                onchange: () => this.toggle_source_controls()
            },
            render_input: true
        });

        this.controls.geo_import_batch = frappe.ui.form.make_control({
            parent: this.page.main.find("#geo_import_batch_control"),
            df: { fieldtype: "Select", label: "Geo Import Batch", options: [""] },
            render_input: true
        });

        this.controls.geo_calculation_batch = frappe.ui.form.make_control({
            parent: this.page.main.find("#geo_calculation_batch_control"),
            df: { fieldtype: "Select", label: "Geo Calculation Batch", options: [""] },
            render_input: true
        });

        this.controls.variable_name = frappe.ui.form.make_control({
            parent: this.page.main.find("#variable_name_control"),
            df: { fieldtype: "Data", label: "Variable Name" },
            render_input: true
        });

        this.controls.value_meaning = frappe.ui.form.make_control({
            parent: this.page.main.find("#value_meaning_control"),
            df: {
                fieldtype: "Select",
                label: "Value Meaning",
                options: ["", "Elevation", "Thickness", "Depth", "Quality", "Density", "Other"]
            },
            render_input: true
        });

        this.controls.rule_operator = frappe.ui.form.make_control({
            parent: this.page.main.find("#rule_operator_control"),
            df: {
                fieldtype: "Select",
                label: "Rule Operator",
                options: ["", "Greater Than", "Greater Than Or Equal", "Less Than", "Less Than Or Equal", "Equal", "Between", "Outside"]
            },
            render_input: true
        });

        this.controls.rule_value = frappe.ui.form.make_control({
            parent: this.page.main.find("#rule_value_control"),
            df: { fieldtype: "Float", label: "Rule Value" },
            render_input: true
        });

        this.controls.rule_value_to = frappe.ui.form.make_control({
            parent: this.page.main.find("#rule_value_to_control"),
            df: { fieldtype: "Float", label: "Rule Value To" },
            render_input: true
        });

        this.controls.run_name = frappe.ui.form.make_control({
            parent: this.page.main.find("#run_name_control"),
            df: { fieldtype: "Data", label: "Run Name" },
            render_input: true
        });

        this.controls.final_geology_run = frappe.ui.form.make_control({
            parent: this.page.main.find("#final_geology_run_control"),
            df: {
                fieldtype: "Link",
                options: "Geo Pit Layout Geology Run",
                label: "Geology Run for Material Values"
            },
            render_input: true
        });

        this.controls.calc_value_type = frappe.ui.form.make_control({
            parent: this.page.main.find("#calc_value_type_control"),
            df: {
                fieldtype: "Select",
                label: "Value Type",
                options: ["", "Thickness", "Depth", "Elevation", "Quality", "Density", "Other"]
            },
            render_input: true
        });

        this.controls.calc_material_seam = frappe.ui.form.make_control({
            parent: this.page.main.find("#calc_material_seam_control"),
            df: {
                fieldtype: "Data",
                label: "Material / Seam Filter"
            },
            render_input: true
        });

        this.controls.calc_density = frappe.ui.form.make_control({
            parent: this.page.main.find("#calc_density_control"),
            df: {
                fieldtype: "Float",
                label: "Density",
                description: "Manual density for now. Later this can come from a density grid."
            },
            render_input: true
        });

        // Force defaults because custom page controls sometimes render blank default values.
        this.controls.layout_name.set_value("Pit Layout 100x40");
        this.controls.layout_version.set_value("V001");
        this.controls.block_size_x.set_value(100);
        this.controls.block_size_y.set_value(40);
        this.controls.block_angle_degrees.set_value(0);
        this.controls.minimum_inside_percent.set_value(50);
        this.controls.default_cut_no.set_value(1);
        this.controls.numbering_style.set_value("C1B1");
        this.toggle_source_controls();

        this.page.main.find("#preview_blocks_btn").on("click", () => this.generate_preview_blocks());
        this.page.main.find("#save_layout_btn").on("click", () => this.save_layout());
        this.page.main.find("#refresh_layouts_btn").on("click", () => this.load_saved_layouts());
        this.page.main.find("#load_layout_btn").on("click", () => this.load_saved_layout());
        this.page.main.find("#preview_overlay_btn").on("click", () => this.preview_geology_overlay());
        this.page.main.find("#save_geology_run_btn").on("click", () => this.save_geology_run());
        this.page.main.find("#mark_final_btn").on("click", () => this.mark_final_layout());
        this.page.main.find("#generate_mining_blocks_btn").on("click", () => this.generate_mining_blocks());
        this.page.main.find("#planning_summary_btn").on("click", () => this.check_planning_summary());
        this.page.main.find("#calculate_tonnes_btn").on("click", () => this.calculate_tonnes());
        this.page.main.find("#zoom_fit_btn").on("click", () => this.zoom_fit());
        this.page.main.find("#clear_btn").on("click", () => this.clear_view());
        this.page.main.find("#zoom_in_btn").on("click", () => this.zoom_by(1.25));
        this.page.main.find("#zoom_out_btn").on("click", () => this.zoom_by(0.8));

        this.page.main.find("#show_labels_toggle").on("change", (e) => {
            this.settings.show_labels = !!e.target.checked;
            this.draw();
        });
        this.page.main.find("#show_grid_toggle").on("change", (e) => {
            this.settings.show_grid = !!e.target.checked;
            this.draw();
        });
        this.page.main.find("#show_partial_toggle").on("change", (e) => {
            this.settings.show_partial = !!e.target.checked;
            this.draw();
        });
    }

    get_value(fieldname) {
        return this.controls[fieldname].get_value();
    }

    set_select_options(control, rows, label_field="label", value_field="value") {
        const options = [""].concat((rows || []).map(row => ({
            label: `${row[label_field] || row[value_field]}${row.point_count ? " (" + row.point_count.toLocaleString() + " pts)" : ""}`,
            value: row[value_field]
        })));

        control.df.options = options;
        control.refresh();
    }

    load_pit_batches() {
        const geo_project = this.get_value("geo_project");
        if (!geo_project) {
            this.set_select_options(this.controls.pit_outline_batch, []);
            return;
        }

        frappe.call({
            method: `${this.method_base}.get_pit_outline_batches`,
            args: { geo_project },
            callback: (r) => {
                this.pit_batches = r.message || [];
                this.set_select_options(this.controls.pit_outline_batch, this.pit_batches);
            }
        });
    }

    load_saved_layouts() {
        const geo_project = this.get_value("geo_project");

        frappe.call({
            method: `${this.method_base}.get_saved_layouts`,
            args: { geo_project },
            callback: (r) => {
                this.saved_layouts = r.message || [];
                const rows = this.saved_layouts.map(row => ({
                    value: row.name,
                    label: `${row.layout_name || row.layout_code || row.name} - ${row.block_count || 0} blocks`
                }));
                this.set_select_options(this.controls.saved_layout, rows, "label", "value");
            }
        });
    }

    load_geology_batches() {
        const geo_project = this.get_value("geo_project");
        if (!geo_project) {
            this.set_select_options(this.controls.geo_import_batch, []);
            this.set_select_options(this.controls.geo_calculation_batch, []);
            return;
        }

        frappe.call({
            method: `${this.method_base}.get_geo_import_batches`,
            args: { geo_project },
            callback: (r) => {
                this.import_batches = r.message || [];
                this.set_select_options(this.controls.geo_import_batch, this.import_batches);
            }
        });

        frappe.call({
            method: `${this.method_base}.get_geo_calculation_batches`,
            args: { geo_project },
            callback: (r) => {
                this.calculation_batches = r.message || [];
                this.set_select_options(this.controls.geo_calculation_batch, this.calculation_batches);
            }
        });
    }

    toggle_source_controls() {
        const source_type = this.get_value("source_type") || "";

        if (source_type === "Geo Calculation Batch") {
            this.page.main.find("#geo_import_batch_control").hide();
            this.page.main.find("#geo_calculation_batch_control").show();
        } else if (source_type === "Geo Import Batch") {
            this.page.main.find("#geo_import_batch_control").show();
            this.page.main.find("#geo_calculation_batch_control").hide();
        } else {
            this.page.main.find("#geo_import_batch_control").hide();
            this.page.main.find("#geo_calculation_batch_control").hide();
        }
    }

    get_overlay_settings() {
        const source_type = this.get_value("source_type") || "";
        return {
            geo_pit_layout: this.get_value("saved_layout"),
            source_type,
            geo_import_batch: source_type === "Geo Import Batch" ? this.get_value("geo_import_batch") : null,
            geo_calculation_batch: source_type === "Geo Calculation Batch" ? this.get_value("geo_calculation_batch") : null,
            variable_name: this.get_value("variable_name"),
            value_meaning: this.get_value("value_meaning"),
            rule_enabled: this.page.main.find("#rule_enabled_toggle").is(":checked") ? 1 : 0,
            rule_operator: this.get_value("rule_operator"),
            rule_value: this.get_value("rule_value"),
            rule_value_to: this.get_value("rule_value_to"),
            run_name: this.get_value("run_name")
        };
    }

    validate_overlay_inputs(settings, saving=false) {
        if (!settings.geo_pit_layout) {
            frappe.msgprint("Please select and load a saved Geo Pit Layout.");
            return false;
        }

        if (!this.current_blocks.length) {
            frappe.msgprint("Please load the saved layout blocks before applying geology.");
            return false;
        }

        if (!settings.source_type) {
            frappe.msgprint("Please select a Source Type.");
            return false;
        }

        if (settings.source_type === "Geo Import Batch" && !settings.geo_import_batch) {
            frappe.msgprint("Please select a Geo Import Batch.");
            return false;
        }

        if (settings.source_type === "Geo Calculation Batch" && !settings.geo_calculation_batch) {
            frappe.msgprint("Please select a Geo Calculation Batch.");
            return false;
        }

        if (settings.rule_enabled) {
            if (!settings.rule_operator) {
                frappe.msgprint("Please select a Rule Operator or disable the rule.");
                return false;
            }

            if (settings.rule_value === undefined || settings.rule_value === null || settings.rule_value === "") {
                frappe.msgprint("Please enter a Rule Value or disable the rule.");
                return false;
            }

            if ((settings.rule_operator === "Between" || settings.rule_operator === "Outside") &&
                (settings.rule_value_to === undefined || settings.rule_value_to === null || settings.rule_value_to === "")) {
                frappe.msgprint("Please enter Rule Value To for Between/Outside rules.");
                return false;
            }
        }

        if (saving && !settings.run_name) {
            frappe.msgprint("Please enter a Run Name.");
            return false;
        }

        return true;
    }

    apply_overlay_results(payload) {
        this.overlay_payload = payload || null;
        this.overlay_results = {};

        for (const result of (payload && payload.results) || []) {
            if (result.layout_block) {
                this.overlay_results[result.layout_block] = result;
            }
        }

        this.update_summary("Geology Overlay");
        this.draw();
    }

    preview_geology_overlay() {
        const settings = this.get_overlay_settings();
        if (!this.validate_overlay_inputs(settings)) return;

        frappe.call({
            method: `${this.method_base}.preview_geology_overlay`,
            args: settings,
            freeze: true,
            freeze_message: "Applying geology overlay...",
            callback: (r) => {
                const payload = r.message || {};
                this.apply_overlay_results(payload);
                frappe.show_alert({
                    message: `Overlay complete: ${payload.passing_blocks || 0} pass, ${payload.failing_blocks || 0} fail, ${payload.no_data_blocks || 0} no data.`,
                    indicator: "green"
                });
            }
        });
    }

    save_geology_run() {
        const settings = this.get_overlay_settings();
        if (!this.validate_overlay_inputs(settings, true)) return;

        frappe.confirm("Save this geology overlay as a Geo Pit Layout Geology Run?", () => {
            frappe.call({
                method: `${this.method_base}.save_geology_run`,
                args: {
                    run_name: settings.run_name,
                    geo_pit_layout: settings.geo_pit_layout,
                    source_type: settings.source_type,
                    geo_import_batch: settings.geo_import_batch,
                    geo_calculation_batch: settings.geo_calculation_batch,
                    variable_name: settings.variable_name,
                    value_meaning: settings.value_meaning,
                    rule_enabled: settings.rule_enabled,
                    rule_operator: settings.rule_operator,
                    rule_value: settings.rule_value,
                    rule_value_to: settings.rule_value_to,
                    remarks: "Created from Geology Viewer"
                },
                freeze: true,
                freeze_message: "Saving geology run and block results...",
                callback: (r) => {
                    const result = r.message || {};
                    this.last_saved_geology_run = result.geology_run;
                    if (result.geology_run) {
                        this.controls.final_geology_run.set_value(result.geology_run);
                    }
                    frappe.msgprint(`Saved geology run <b>${result.geology_run}</b> with ${result.results_created || 0} block results.`);
                }
            });
        });
    }

    get_selected_layout_for_final() {
        return this.get_value("saved_layout") || (this.loaded_layout && this.loaded_layout.name);
    }

    mark_final_layout() {
        const geo_pit_layout = this.get_selected_layout_for_final();

        if (!geo_pit_layout) {
            frappe.msgprint("Please select and load a saved Geo Pit Layout first.");
            return;
        }

        frappe.confirm("Mark this Geo Pit Layout as Final?", () => {
            frappe.call({
                method: `${this.method_base}.mark_final_layout`,
                args: { geo_pit_layout },
                freeze: true,
                freeze_message: "Marking layout final...",
                callback: (r) => {
                    const result = r.message || {};
                    if (this.loaded_layout && this.loaded_layout.name === result.geo_pit_layout) {
                        this.loaded_layout.layout_status = result.layout_status;
                        this.loaded_layout.is_final_layout = result.is_final_layout;
                    }
                    this.update_summary("Final Layout");
                    frappe.msgprint(`Layout <b>${result.geo_pit_layout}</b> is now Final.`);
                }
            });
        });
    }

    generate_mining_blocks() {
        const geo_pit_layout = this.get_selected_layout_for_final();
        const geology_run = this.get_value("final_geology_run");
        const overwrite_existing = this.page.main.find("#overwrite_mining_blocks_toggle").is(":checked") ? 1 : 0;

        if (!geo_pit_layout) {
            frappe.msgprint("Please select and load a saved Geo Pit Layout first.");
            return;
        }

        if (!geology_run) {
            frappe.msgprint("Please select the Geo Pit Layout Geology Run to copy into Mining Block Material Values.");
            return;
        }

        frappe.confirm("Generate official Mining Block records from this final layout?", () => {
            frappe.call({
                method: `${this.method_base}.generate_mining_blocks`,
                args: {
                    geo_pit_layout,
                    geology_run,
                    require_final: 1,
                    overwrite_existing
                },
                freeze: true,
                freeze_message: "Generating Mining Blocks...",
                callback: (r) => {
                    const result = r.message || {};
                    this.phase3_payload = result;
                    this.update_summary("Mining Blocks Generated");
                    frappe.msgprint(`
                        Mining Blocks created: <b>${result.mining_blocks_created || 0}</b><br>
                        Mining Blocks skipped: <b>${result.mining_blocks_skipped || 0}</b><br>
                        Material Values created: <b>${result.material_values_created || 0}</b><br>
                        Material Values skipped: <b>${result.material_values_skipped || 0}</b>
                    `);
                }
            });
        });
    }

    get_calc_settings() {
        return {
            source_pit_layout: this.get_selected_layout_for_final(),
            value_type: this.get_value("calc_value_type"),
            material_seam: this.get_value("calc_material_seam"),
            density: this.get_value("calc_density"),
            mineable_only: this.page.main.find("#mineable_only_toggle").is(":checked") ? 1 : 0,
            update_block_status: 1
        };
    }

    validate_calc_settings(settings, calculate=false) {
        if (!settings.source_pit_layout) {
            frappe.msgprint("Please select and load a saved Geo Pit Layout first.");
            return false;
        }

        if (!settings.value_type) {
            frappe.msgprint("Please select a Value Type, for example Thickness.");
            return false;
        }

        if (calculate && (!settings.density || Number(settings.density) <= 0)) {
            frappe.msgprint("Please enter a Density greater than zero.");
            return false;
        }

        return true;
    }

    check_planning_summary() {
        const settings = this.get_calc_settings();
        if (!this.validate_calc_settings(settings, false)) return;

        frappe.call({
            method: `${this.method_base}.get_planning_summary`,
            args: {
                source_pit_layout: settings.source_pit_layout,
                value_type: settings.value_type,
                material_seam: settings.material_seam
            },
            freeze: true,
            freeze_message: "Checking planning summary...",
            callback: (r) => {
                const result = r.message || {};
                this.phase4_payload = result;
                this.update_summary("Planning Summary");
                frappe.msgprint(`
                    Mining Blocks: <b>${result.mining_block_count || 0}</b><br>
                    Material Values: <b>${result.material_value_count || 0}</b><br>
                    Values with data: <b>${result.values_with_data || 0}</b><br>
                    Mineable/passing: <b>${result.mineable_or_passing_values || 0}</b><br>
                    No data: <b>${result.no_data_values || 0}</b>
                `);
            }
        });
    }

    calculate_tonnes() {
        const settings = this.get_calc_settings();
        if (!this.validate_calc_settings(settings, true)) return;

        frappe.confirm("Calculate volume and tonnes for this layout?", () => {
            frappe.call({
                method: `${this.method_base}.calculate_planning_values`,
                args: settings,
                freeze: true,
                freeze_message: "Calculating volume and tonnes...",
                callback: (r) => {
                    const result = r.message || {};
                    this.phase4_payload = result;
                    this.update_summary("Tonnes Calculated");
                    frappe.msgprint(`
                        Records checked: <b>${result.records_checked || 0}</b><br>
                        Records updated: <b>${result.records_updated || 0}</b><br>
                        Mineable values: <b>${result.mineable_values || 0}</b><br>
                        Total volume: <b>${Number(result.total_volume || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}</b><br>
                        Total tonnes: <b>${Number(result.total_tonnes || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}</b>
                    `);
                }
            });
        });
    }

    get_settings() {
        return {
            geo_project: this.get_value("geo_project"),
            pit_outline_batch: this.get_value("pit_outline_batch"),
            layout_name: this.get_value("layout_name"),
            layout_version: this.get_value("layout_version") || "V001",
            block_size_x: Number(this.get_value("block_size_x") || 100),
            block_size_y: Number(this.get_value("block_size_y") || 40),
            block_angle_degrees: Number(this.get_value("block_angle_degrees") || 0),
            minimum_inside_percent: Number(this.get_value("minimum_inside_percent") || 50),
            default_cut_no: Number(this.get_value("default_cut_no") || 1),
            numbering_style: this.get_value("numbering_style") || "C1B1"
        };
    }

    validate_create_inputs(settings) {
        if (!settings.geo_project) {
            frappe.msgprint("Please select a Geo Project.");
            return false;
        }
        if (!settings.pit_outline_batch) {
            frappe.msgprint("Please select a Pit Outline Batch.");
            return false;
        }
        if (!settings.block_size_x || !settings.block_size_y) {
            frappe.msgprint("Please enter valid Block Size X and Block Size Y.");
            return false;
        }
        return true;
    }

    generate_preview_blocks() {
        const settings = this.get_settings();
        if (!this.validate_create_inputs(settings)) return;

        frappe.call({
            method: `${this.method_base}.preview_blocks`,
            args: settings,
            freeze: true,
            freeze_message: "Generating preview blocks...",
            callback: (r) => {
                this.preview_blocks = this.normalise_blocks(r.message || []);
                this.saved_blocks = [];
                this.current_blocks = this.preview_blocks;
                this.selected_block = null;
                this.loaded_layout = null;
                this.overlay_results = {};
                this.overlay_payload = null;
                this.update_bounds();
                this.zoom_fit();
                this.update_summary("Preview Blocks");
                frappe.show_alert({ message: `Generated ${this.current_blocks.length.toLocaleString()} preview blocks.`, indicator: "green" });
            }
        });
    }

    save_layout() {
        const settings = this.get_settings();

        if (!this.validate_create_inputs(settings)) return;
        if (!settings.layout_name) {
            frappe.msgprint("Please enter a Layout Name.");
            return;
        }

        frappe.confirm("Save this pit layout and create Geo Pit Layout Block records?", () => {
            frappe.call({
                method: `${this.method_base}.save_layout`,
                args: { ...settings, layout_type: "Pit Layout", remarks: "Created from Geology Viewer" },
                freeze: true,
                freeze_message: "Saving layout and blocks...",
                callback: (r) => {
                    const result = r.message || {};
                    frappe.msgprint(`Saved layout <b>${result.layout_code || result.layout}</b> with ${result.blocks_created || 0} blocks.`);
                    this.load_saved_layouts();
                }
            });
        });
    }

    load_saved_layout() {
        const geo_pit_layout = this.get_value("saved_layout");
        if (!geo_pit_layout) {
            frappe.msgprint("Please select a saved Geo Pit Layout.");
            return;
        }

        frappe.call({
            method: `${this.method_base}.load_layout_blocks`,
            args: { geo_pit_layout },
            freeze: true,
            freeze_message: "Loading saved layout blocks...",
            callback: (r) => {
                const payload = r.message || {};
                this.loaded_layout = payload.layout || null;
                this.overlay_results = {};
                this.overlay_payload = null;
                this.saved_blocks = this.normalise_blocks(payload.blocks || []);
                this.preview_blocks = [];
                this.current_blocks = this.saved_blocks;
                this.selected_block = null;
                this.update_bounds();
                this.zoom_fit();
                this.update_summary("Saved Layout");
                frappe.show_alert({ message: `Loaded ${this.current_blocks.length.toLocaleString()} saved layout blocks.`, indicator: "green" });
            }
        });
    }

    clear_view() {
        this.preview_blocks = [];
        this.saved_blocks = [];
        this.current_blocks = [];
        this.overlay_results = {};
        this.overlay_payload = null;
        this.last_saved_geology_run = null;
        this.phase3_payload = null;
        this.phase4_payload = null;
        this.import_batches = [];
        this.calculation_batches = [];
        this.selected_block = null;
        this.hover_block = null;
        this.loaded_layout = null;
        this.overlay_results = {};
        this.overlay_payload = null;
        this.bounds = null;
        this.update_summary();
        this.update_block_info();
        this.draw();
    }

    normalise_blocks(blocks) {
        return (blocks || []).map((block, index) => {
            let corners = [];
            try {
                if (typeof block.corners_json === "string" && block.corners_json) {
                    corners = JSON.parse(block.corners_json);
                } else if (Array.isArray(block.corners_json)) {
                    corners = block.corners_json;
                } else if (Array.isArray(block.corners)) {
                    corners = block.corners;
                }
            } catch (e) {
                corners = [];
            }

            corners = (corners || [])
                .map(p => ({ x: Number(p.x), y: Number(p.y) }))
                .filter(p => isFinite(p.x) && isFinite(p.y));

            return {
                ...block,
                _index: index,
                block_code: block.block_code || block.label || `B${index + 1}`,
                centroid_x: Number(block.centroid_x || block.x || 0),
                centroid_y: Number(block.centroid_y || block.y || 0),
                area: Number(block.area || 0),
                effective_area: Number(block.effective_area || 0),
                inside_percent: Number(block.inside_percent || 0),
                corners
            };
        });
    }

    percentile(values, pct) {
        const clean = (values || []).filter(v => Number.isFinite(v)).sort((a, b) => a - b);
        if (!clean.length) return null;
        const idx = Math.max(0, Math.min(clean.length - 1, Math.floor((pct / 100) * (clean.length - 1))));
        return clean[idx];
    }

    update_bounds() {
        // Robust viewer bounds:
        // Use block centroids, not polygon corners, because one bad corner can zoom the whole map out.
        // Use 1st/99th percentiles to avoid rare outliers.
        const centroid_xs = [];
        const centroid_ys = [];

        for (const block of this.current_blocks || []) {
            const x = Number(block.centroid_x);
            const y = Number(block.centroid_y);
            if (Number.isFinite(x) && Number.isFinite(y)) {
                centroid_xs.push(x);
                centroid_ys.push(y);
            }
        }

        if (!centroid_xs.length || !centroid_ys.length) {
            this.bounds = null;
            return;
        }

        let min_x = this.percentile(centroid_xs, 1);
        let max_x = this.percentile(centroid_xs, 99);
        let min_y = this.percentile(centroid_ys, 1);
        let max_y = this.percentile(centroid_ys, 99);

        // Fallback for small layouts.
        if (min_x === max_x) {
            min_x = Math.min(...centroid_xs);
            max_x = Math.max(...centroid_xs);
        }
        if (min_y === max_y) {
            min_y = Math.min(...centroid_ys);
            max_y = Math.max(...centroid_ys);
        }

        const width = Math.max(max_x - min_x, 1);
        const height = Math.max(max_y - min_y, 1);

        // Add padding based on layout size.
        const pad_x = width * 0.08;
        const pad_y = height * 0.08;

        this.bounds = {
            min_x: min_x - pad_x,
            max_x: max_x + pad_x,
            min_y: min_y - pad_y,
            max_y: max_y + pad_y
        };

        // Keep full bounds for diagnostics only.
        this.full_bounds = {
            min_x: Math.min(...centroid_xs),
            max_x: Math.max(...centroid_xs),
            min_y: Math.min(...centroid_ys),
            max_y: Math.max(...centroid_ys),
            count: centroid_xs.length
        };
    }

    resize_canvas() {
        const wrap = this.page.main.find(".gv-canvas-wrap");
        this.canvas.width = wrap.width() || 900;
        this.canvas.height = wrap.height() || 620;
    }

    zoom_fit() {
        if (!this.bounds) {
            this.draw();
            return;
        }

        this.resize_canvas();

        const pad = 70;
        const w = Math.max(this.bounds.max_x - this.bounds.min_x, 1);
        const h = Math.max(this.bounds.max_y - this.bounds.min_y, 1);

        const available_w = Math.max(this.canvas.width - pad * 2, 200);
        const available_h = Math.max(this.canvas.height - pad * 2, 200);

        const sx = available_w / w;
        const sy = available_h / h;

        this.view.scale = Math.min(sx, sy);

        // Keep scale sane. Mine coordinates are metres, so normal layouts should not need microscopic scale.
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
        return { x: x * this.view.scale + this.view.offset_x, y: -y * this.view.scale + this.view.offset_y };
    }

    screen_to_world(x, y) {
        return { x: (x - this.view.offset_x) / this.view.scale, y: -(y - this.view.offset_y) / this.view.scale };
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
            this.draw();
        });

        $(this.canvas).on("click", (e) => {
            const world = this.screen_to_world(e.offsetX, e.offsetY);
            this.selected_block = this.find_block_at(world.x, world.y);
            this.update_block_info();
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
        for (let i = (this.current_blocks || []).length - 1; i >= 0; i--) {
            const block = this.current_blocks[i];
            if (this.point_in_polygon(x, y, block.corners)) return block;
        }
        return null;
    }

    point_in_polygon(x, y, polygon) {
        if (!polygon || polygon.length < 3) return false;
        let inside = false;
        for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
            const xi = polygon[i].x, yi = polygon[i].y;
            const xj = polygon[j].x, yj = polygon[j].y;
            const intersect = ((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / ((yj - yi) || 0.0000001) + xi);
            if (intersect) inside = !inside;
        }
        return inside;
    }

    draw() {
        const ctx = this.ctx;
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        ctx.fillStyle = "#f9fafb";
        ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        if (this.settings.show_grid) this.draw_grid();

        for (const block of this.current_blocks || []) {
            if (!this.settings.show_partial && Number(block.inside_percent || 0) < 99) continue;
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
            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, this.canvas.height); ctx.stroke();
        }
        for (let y = 0; y < this.canvas.height; y += spacing) {
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(this.canvas.width, y); ctx.stroke();
        }
        ctx.restore();
    }

    draw_block(block) {
        const ctx = this.ctx;
        const corners = block.corners || [];
        if (corners.length < 3) return;

        // Skip obviously off-screen blocks for performance.
        const screens = corners.map(p => this.world_to_screen(p.x, p.y));
        const min_sx = Math.min(...screens.map(p => p.x));
        const max_sx = Math.max(...screens.map(p => p.x));
        const min_sy = Math.min(...screens.map(p => p.y));
        const max_sy = Math.max(...screens.map(p => p.y));
        if (max_sx < -200 || min_sx > this.canvas.width + 200 || max_sy < -200 || min_sy > this.canvas.height + 200) {
            return;
        }

        const is_selected = this.selected_block && this.selected_block._index === block._index;
        const is_hover = this.hover_block && this.hover_block._index === block._index;
        const inside = Number(block.inside_percent || 0);

        ctx.beginPath();
        screens.forEach((s, i) => {
            if (i === 0) ctx.moveTo(s.x, s.y);
            else ctx.lineTo(s.x, s.y);
        });
        ctx.closePath();

        const overlay = this.overlay_results[block.name] || this.overlay_results[block.layout_block];

        if (is_selected) {
            ctx.fillStyle = "rgba(37, 99, 235, 0.42)";
            ctx.strokeStyle = "#1d4ed8";
            ctx.lineWidth = 3;
        } else if (is_hover) {
            ctx.fillStyle = "rgba(245, 158, 11, 0.36)";
            ctx.strokeStyle = "#d97706";
            ctx.lineWidth = 2.5;
        } else if (overlay) {
            if (overlay.result_status === "Pass") {
                ctx.fillStyle = "rgba(22, 163, 74, 0.42)";
                ctx.strokeStyle = "rgba(21, 128, 61, 0.65)";
            } else if (overlay.result_status === "Fail") {
                ctx.fillStyle = "rgba(220, 38, 38, 0.42)";
                ctx.strokeStyle = "rgba(185, 28, 28, 0.7)";
            } else if (overlay.result_status === "No Data") {
                ctx.fillStyle = "rgba(107, 114, 128, 0.20)";
                ctx.strokeStyle = "rgba(75, 85, 99, 0.35)";
            } else {
                ctx.fillStyle = "rgba(59, 130, 246, 0.24)";
                ctx.strokeStyle = "rgba(37, 99, 235, 0.45)";
            }
            ctx.lineWidth = 0.75;
        } else {
            if (inside >= 99) ctx.fillStyle = "rgba(16, 185, 129, 0.26)";
            else if (inside >= 70) ctx.fillStyle = "rgba(59, 130, 246, 0.20)";
            else ctx.fillStyle = "rgba(249, 115, 22, 0.22)";

            ctx.strokeStyle = "rgba(31, 41, 55, 0.55)";
            ctx.lineWidth = 0.75;
        }

        ctx.fill();
        ctx.stroke();

        if (this.settings.show_labels || is_selected || is_hover) {
            const c = this.world_to_screen(block.centroid_x, block.centroid_y);
            ctx.fillStyle = "#111827";
            ctx.font = is_selected || is_hover ? "12px sans-serif" : "10px sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(block.block_code || "", c.x, c.y);
        }
    }

    update_summary(mode) {
        const blocks = this.current_blocks || [];
        if (!blocks.length) {
            this.page.main.find("#summary_box").html(`<div><b>0</b>Blocks</div><div><b>0</b>Effective Area</div>`);
            this.page.main.find("#floating_summary").html(`<b>No layout loaded</b><br>Select a project and pit outline, then preview blocks.`);
            return;
        }

        const total_area = blocks.reduce((sum, b) => sum + Number(b.area || 0), 0);
        const effective_area = blocks.reduce((sum, b) => sum + Number(b.effective_area || 0), 0);
        const avg_inside = blocks.length ? blocks.reduce((sum, b) => sum + Number(b.inside_percent || 0), 0) / blocks.length : 0;

        this.page.main.find("#summary_box").html(`
            <div><b>${blocks.length.toLocaleString()}</b>Blocks</div>
            <div><b>${effective_area.toLocaleString(undefined, { maximumFractionDigits: 0 })}</b>Effective Area</div>
            <div><b>${total_area.toLocaleString(undefined, { maximumFractionDigits: 0 })}</b>Total Area</div>
            <div><b>${avg_inside.toFixed(1)}%</b>Avg Inside</div>
        `);

        const layout_text = this.loaded_layout
            ? `${this.loaded_layout.layout_name || this.loaded_layout.layout_code}`
            : "Preview layout";

        const bounds_text = this.full_bounds
            ? `<br>Extent: ${(this.full_bounds.max_x - this.full_bounds.min_x).toFixed(0)} x ${(this.full_bounds.max_y - this.full_bounds.min_y).toFixed(0)}`
            : "";

        const overlay_text = this.overlay_payload
            ? `<br><b>Overlay:</b> ${this.overlay_payload.passing_blocks || 0} pass · ${this.overlay_payload.failing_blocks || 0} fail · ${this.overlay_payload.no_data_blocks || 0} no data`
            : "";

        const phase3_text = this.phase3_payload
            ? `<br><b>Mining Blocks:</b> ${this.phase3_payload.mining_blocks_created || 0} created · ${this.phase3_payload.material_values_created || 0} values`
            : "";

        const phase4_text = this.phase4_payload && this.phase4_payload.total_tonnes !== undefined
            ? `<br><b>Tonnes:</b> ${Number(this.phase4_payload.total_tonnes || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
            : "";

        this.page.main.find("#floating_summary").html(`
            <b>${mode || "Layout"}</b><br>
            ${layout_text}<br>
            Blocks: ${blocks.length.toLocaleString()}<br>
            Effective Area: ${effective_area.toLocaleString(undefined, { maximumFractionDigits: 2 })}<br>
            Avg Inside: ${avg_inside.toFixed(2)}%${bounds_text}${overlay_text}${phase3_text}${phase4_text}
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

    update_block_info() {
        const b = this.selected_block;
        if (!b) {
            this.page.main.find("#block_info").html("Click a block to inspect it.");
            return;
        }

        const overlay = this.overlay_results[b.name] || this.overlay_results[b.layout_block];
        const overlay_html = overlay ? `
            <br><b>Overlay:</b>
            Avg: ${overlay.avg_value === null || overlay.avg_value === undefined ? "No Data" : Number(overlay.avg_value).toFixed(3)}
            &nbsp; | &nbsp; Min: ${overlay.min_value === null || overlay.min_value === undefined ? "-" : Number(overlay.min_value).toFixed(3)}
            &nbsp; | &nbsp; Max: ${overlay.max_value === null || overlay.max_value === undefined ? "-" : Number(overlay.max_value).toFixed(3)}
            &nbsp; | &nbsp; Points: ${overlay.point_count || 0}
            &nbsp; | &nbsp; Result: <b>${overlay.result_status}</b>
        ` : "";

        this.page.main.find("#block_info").html(`
            <b>${b.block_code}</b>
            &nbsp; <span class="text-muted">Row ${b.row_no || ""}, Column ${b.column_no || ""}</span><br>
            Centroid: ${Number(b.centroid_x || 0).toFixed(3)}, ${Number(b.centroid_y || 0).toFixed(3)}
            &nbsp; | &nbsp; Area: ${Number(b.area || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
            &nbsp; | &nbsp; Effective: ${Number(b.effective_area || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
            &nbsp; | &nbsp; Inside: ${Number(b.inside_percent || 0).toFixed(2)}%
            &nbsp; | &nbsp; Status: ${b.block_status || ""}
            ${overlay_html}
        `);
    }
}
