frappe.ui.form.on("Geo Pit Layout", {
    refresh(frm) {
        set_defaults(frm);
        add_buttons(frm);
        set_indicators(frm);
    },

    geo_project(frm) {
        if (!frm.doc.layout_code && frm.doc.geo_project && frm.doc.layout_name) {
            make_layout_code(frm);
        }
    },

    layout_name(frm) {
        if (!frm.doc.layout_code && frm.doc.geo_project && frm.doc.layout_name) {
            make_layout_code(frm);
        }
    }
});

function set_defaults(frm) {
    if (frm.is_new()) {
        if (!frm.doc.layout_version) frm.set_value("layout_version", "V001");
        if (!frm.doc.layout_type) frm.set_value("layout_type", "Pit Layout");
        if (!frm.doc.block_size_x) frm.set_value("block_size_x", 100);
        if (!frm.doc.block_size_y) frm.set_value("block_size_y", 40);
        if (frm.doc.block_angle_degrees === undefined || frm.doc.block_angle_degrees === null) {
            frm.set_value("block_angle_degrees", 0);
        }
        if (!frm.doc.minimum_inside_percent) frm.set_value("minimum_inside_percent", 50);
        if (!frm.doc.default_cut_no) frm.set_value("default_cut_no", 1);
        if (!frm.doc.numbering_style) frm.set_value("numbering_style", "C1B1");
        if (!frm.doc.layout_status) frm.set_value("layout_status", "Draft");
        if (!frm.doc.generation_status) frm.set_value("generation_status", "Draft");
    }
}

function make_layout_code(frm) {
    const project = frm.doc.geo_project || "";
    const name = (frm.doc.layout_name || "PIT-LAYOUT").trim().replace(/\s+/g, "-").toUpperCase();

    if (project && name) {
        frm.set_value("layout_code", `${project}-${name}`);
    }
}

function set_indicators(frm) {
    if (frm.doc.generation_status) {
        const color = {
            "Draft": "gray",
            "Queued": "orange",
            "Running": "blue",
            "Complete": "green",
            "Error": "red"
        }[frm.doc.generation_status] || "gray";

        frm.dashboard.set_headline_alert(
            `<div class="indicator ${color}">Generation Status: ${frappe.utils.escape_html(frm.doc.generation_status)}</div>`
        );
    }

    if (frm.doc.is_final_layout) {
        frm.dashboard.add_indicator("Final Layout", "green");
    } else {
        frm.dashboard.add_indicator("Not Final", "orange");
    }
}

function add_buttons(frm) {
    if (frm.is_new()) return;

    frm.add_custom_button("Preview Layout Blocks", () => {
        preview_layout_blocks(frm);
    }, "Layout");

    frm.add_custom_button("Generate Layout Blocks", () => {
        enqueue_generate_layout_blocks(frm);
    }, "Layout");

    frm.add_custom_button("Run Generation Now", () => {
        run_generation_now(frm);
    }, "Layout");

    frm.add_custom_button("Open Viewer", () => {
        frappe.set_route("geology-viewer");
    }, "View");

    frm.add_custom_button("View Layout Blocks", () => {
        frappe.set_route("List", "Geo Pit Layout Block", {
            geo_pit_layout: frm.doc.name
        });
    }, "View");

    frm.add_custom_button("View Generation Batches", () => {
        frappe.set_route("List", "Geo Layout Generation Batch", {
            geo_pit_layout: frm.doc.name
        });
    }, "View");

    frm.add_custom_button("Mark Final", () => {
        mark_final(frm);
    }, "Actions");

    frm.add_custom_button("Generate Mining Blocks", () => {
        enqueue_generate_mining_blocks(frm);
    }, "Actions");

    frm.add_custom_button("Create Material Stack", () => {
        create_material_stack(frm);
    }, "Actions");
}

function preview_layout_blocks(frm) {
    if (!validate_layout_inputs(frm)) return;

    frappe.call({
        method: "is_production.geo_planning.services.pit_layout_service.preview_layout_blocks",
        args: {
            geo_project: frm.doc.geo_project,
            pit_outline_batch: frm.doc.pit_outline_batch,
            block_size_x: frm.doc.block_size_x,
            block_size_y: frm.doc.block_size_y,
            block_angle_degrees: frm.doc.block_angle_degrees,
            minimum_inside_percent: frm.doc.minimum_inside_percent,
            default_cut_no: frm.doc.default_cut_no,
            numbering_style: frm.doc.numbering_style
        },
        freeze: true,
        freeze_message: "Previewing layout blocks...",
        callback(r) {
            const rows = r.message || [];
            let total_area = 0;
            let effective_area = 0;

            rows.forEach(row => {
                total_area += Number(row.area || 0);
                effective_area += Number(row.effective_area || 0);
            });

            frappe.msgprint(`
                <b>Preview Complete</b><br>
                Blocks: <b>${rows.length.toLocaleString()}</b><br>
                Total Area: <b>${format_number(total_area, null, 2)}</b><br>
                Effective Area: <b>${format_number(effective_area, null, 2)}</b>
            `);
        }
    });
}

function enqueue_generate_layout_blocks(frm) {
    if (!validate_layout_inputs(frm)) return;

    frappe.confirm(
        "Queue background generation for this layout? Existing matching blocks will be updated in place. Linked blocks will not be deleted.",
        () => {
            frappe.call({
                method: "is_production.geo_planning.services.pit_layout_jobs.enqueue_generate_layout_blocks",
                args: {
                    geo_pit_layout: frm.doc.name,
                    clear_existing_blocks: 0,
                    overwrite_existing: 1
                },
                freeze: true,
                freeze_message: "Queuing layout generation...",
                callback(r) {
                    const msg = r.message || {};
                    frappe.msgprint(`
                        Layout generation queued.<br>
                        Batch: <b>${msg.batch || ""}</b><br>
                        Job ID: <b>${msg.job_id || ""}</b>
                    `);
                    frm.reload_doc();
                }
            });
        }
    );
}

function run_generation_now(frm) {
    if (!validate_layout_inputs(frm)) return;

    frappe.confirm(
        "Run generation now in the current request? Existing matching blocks will be updated in place. Use this only for testing or smaller layouts.",
        () => {
            frappe.call({
                method: "is_production.geo_planning.services.pit_layout_jobs.run_generate_layout_blocks_now",
                args: {
                    geo_pit_layout: frm.doc.name,
                    clear_existing_blocks: 0,
                    overwrite_existing: 1
                },
                freeze: true,
                freeze_message: "Generating layout blocks...",
                callback(r) {
                    const msg = r.message || {};
                    const updateMode = Number(msg.update_in_place || 0) ? "Yes" : "No";

                    frappe.msgprint(`
                        Generation complete.<br>
                        Blocks Created: <b>${msg.blocks_created || 0}</b><br>
                        Blocks Updated: <b>${msg.blocks_updated || 0}</b><br>
                        Blocks Skipped: <b>${msg.blocks_skipped || 0}</b><br>
                        Stale Blocks Kept: <b>${msg.stale_blocks_kept || 0}</b><br>
                        Update In Place: <b>${updateMode}</b><br>
                        Total Area: <b>${format_number(msg.total_area || 0, null, 2)}</b><br>
                        Effective Area: <b>${format_number(msg.effective_area || 0, null, 2)}</b>
                    `);
                    frm.reload_doc();
                }
            });
        }
    );
}

function mark_final(frm) {
    frappe.confirm("Mark this Geo Pit Layout as Final?", () => {
        frappe.call({
            method: "is_production.geo_planning.services.pit_layout_service.mark_layout_final",
            args: {
                geo_pit_layout: frm.doc.name
            },
            freeze: true,
            freeze_message: "Marking final...",
            callback() {
                frappe.show_alert({
                    message: "Layout marked as Final.",
                    indicator: "green"
                });
                frm.reload_doc();
            }
        });
    });
}

function enqueue_generate_mining_blocks(frm) {
    if (!frm.doc.is_final_layout) {
        frappe.msgprint("Mark the layout as Final before generating Mining Blocks.");
        return;
    }

    frappe.confirm("Queue official Mining Block generation from this final layout?", () => {
        frappe.call({
            method: "is_production.geo_planning.services.mining_block_jobs.enqueue_generate_mining_blocks",
            args: {
                geo_pit_layout: frm.doc.name,
                require_final: 1,
                overwrite_existing: 0
            },
            freeze: true,
            freeze_message: "Queuing Mining Block generation...",
            callback(r) {
                const msg = r.message || {};
                frappe.msgprint(`
                    Mining Block generation queued.<br>
                    Batch: <b>${msg.batch || ""}</b>
                `);
            },
            error() {
                frappe.msgprint("Mining Block job service is not installed yet. Continue with Phase 3 code next.");
            }
        });
    });
}

function create_material_stack(frm) {
    frappe.prompt(
        [
            {
                fieldname: "stack_name",
                label: "Stack Name",
                fieldtype: "Data",
                default: `${frm.doc.layout_name || frm.doc.name} Stack`
            }
        ],
        (values) => {
            frappe.call({
                method: "is_production.geo_planning.services.pit_layout_service.create_material_stack_from_layout",
                args: {
                    geo_pit_layout: frm.doc.name,
                    stack_name: values.stack_name
                },
                freeze: true,
                freeze_message: "Creating material stack...",
                callback(r) {
                    const msg = r.message || {};
                    frappe.msgprint(`
                        Material Stack created:<br>
                        <b>${msg.material_stack || ""}</b>
                    `);

                    if (msg.material_stack) {
                        frappe.set_route("Form", "Geo Pit Layout Material Stack", msg.material_stack);
                    }
                }
            });
        },
        "Create Material Stack",
        "Create"
    );
}

function validate_layout_inputs(frm) {
    if (!frm.doc.geo_project) {
        frappe.msgprint("Geo Project is required.");
        return false;
    }

    if (!frm.doc.pit_outline_batch) {
        frappe.msgprint("Pit Outline Batch is required.");
        return false;
    }

    if (!Number(frm.doc.block_size_x || 0) || !Number(frm.doc.block_size_y || 0)) {
        frappe.msgprint("Block Size X and Block Size Y are required and must be greater than zero.");
        return false;
    }

    return true;
}