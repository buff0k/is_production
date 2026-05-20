frappe.ui.form.on("Geo Pit Layout Material Stack", {
    refresh(frm) {
        set_defaults(frm);
        add_buttons(frm);
        set_indicators(frm);
    },

    geo_pit_layout(frm) {
        if (frm.doc.geo_pit_layout && !frm.doc.geo_project) {
            frappe.db.get_value("Geo Pit Layout", frm.doc.geo_pit_layout, "geo_project")
                .then(r => {
                    if (r.message && r.message.geo_project) {
                        frm.set_value("geo_project", r.message.geo_project);
                    }
                });
        }
    }
});

frappe.ui.form.on("Geo Pit Layout Material Stack Item", {
    value_type(frm, cdt, cdn) {
        const row = locals[cdt][cdn];

        if (row.value_type === "Thickness") {
            frappe.model.set_value(cdt, cdn, "use_for_volume", 1);
            if (!row.aggregation_method) {
                frappe.model.set_value(cdt, cdn, "aggregation_method", "Average");
            }
            if (!row.density_source) {
                frappe.model.set_value(cdt, cdn, "density_source", "None");
            }
        }

        if (row.value_type === "Density") {
            frappe.model.set_value(cdt, cdn, "use_for_density", 1);
            frappe.model.set_value(cdt, cdn, "density_source", "Geology Run");
            if (!row.aggregation_method) {
                frappe.model.set_value(cdt, cdn, "aggregation_method", "Average");
            }
        }
    },

    density_source(frm, cdt, cdn) {
        const row = locals[cdt][cdn];

        if (row.density_source === "Manual") {
            frappe.model.set_value(cdt, cdn, "use_for_density", 1);
        }
    }
});

function set_defaults(frm) {
    if (frm.is_new()) {
        if (!frm.doc.stack_status) frm.set_value("stack_status", "Draft");
        if (!frm.doc.attach_status) frm.set_value("attach_status", "Not Attached");
        if (!frm.doc.calculation_status) frm.set_value("calculation_status", "Not Calculated");
    }
}

function set_indicators(frm) {
    if (frm.doc.stack_status) {
        const color = {
            "Draft": "gray",
            "Approved": "green",
            "Superseded": "red"
        }[frm.doc.stack_status] || "gray";

        frm.dashboard.add_indicator(`Stack Status: ${frm.doc.stack_status}`, color);
    }

    if (frm.doc.attach_status) {
        const color = {
            "Not Attached": "gray",
            "Queued": "orange",
            "Running": "blue",
            "Complete": "green",
            "Error": "red"
        }[frm.doc.attach_status] || "gray";

        frm.dashboard.add_indicator(`Attach: ${frm.doc.attach_status}`, color);
    }

    if (frm.doc.calculation_status) {
        const color = {
            "Not Calculated": "gray",
            "Queued": "orange",
            "Running": "blue",
            "Complete": "green",
            "Error": "red"
        }[frm.doc.calculation_status] || "gray";

        frm.dashboard.add_indicator(`Calculation: ${frm.doc.calculation_status}`, color);
    }

    if (frm.doc.total_volume || frm.doc.total_tonnes) {
        frm.dashboard.add_indicator(
            `Volume: ${format_number(frm.doc.total_volume || 0, null, 2)}`,
            "blue"
        );
        frm.dashboard.add_indicator(
            `Tonnes: ${format_number(frm.doc.total_tonnes || 0, null, 2)}`,
            "purple"
        );
    }
}

function add_buttons(frm) {
    if (frm.is_new()) return;

    frm.add_custom_button("Check Stack", () => {
        check_stack(frm);
    }, "Material Stack");

    frm.add_custom_button("Attach Stack to Mining Blocks", () => {
        enqueue_stack_job(frm, "Attach Stack");
    }, "Material Stack");

    frm.add_custom_button("Calculate Volumes and Tonnes", () => {
        enqueue_stack_job(frm, "Calculate Values");
    }, "Material Stack");

    frm.add_custom_button("Attach And Calculate", () => {
        enqueue_stack_job(frm, "Attach And Calculate");
    }, "Material Stack");

    frm.add_custom_button("Refresh Status", () => {
        frm.reload_doc();
    }, "View");

    frm.add_custom_button("Generate Missing Mining Blocks", () => {
        generate_missing_mining_blocks(frm);
    }, "Actions");

    frm.add_custom_button("Approve Stack", () => {
        frm.set_value("stack_status", "Approved");
        frm.save();
    }, "Actions");

    frm.add_custom_button("View Material Values", () => {
        frappe.set_route("List", "Mining Block Material Value", {
            material_stack: frm.doc.name
        });
    }, "View");

    frm.add_custom_button("View Material Summaries", () => {
        frappe.set_route("List", "Mining Block Material Summary", {
            material_stack: frm.doc.name
        });
    }, "View");

    frm.add_custom_button("View Calculation Batches", () => {
        frappe.set_route("List", "Mining Block Material Calculation Batch", {
            material_stack: frm.doc.name
        });
    }, "View");

    frm.add_custom_button("Open Viewer", () => {
        frappe.set_route("geology-viewer");
    }, "View");
}

function validate_stack(frm) {
    if (!frm.doc.geo_project) {
        frappe.msgprint("Geo Project is required.");
        return false;
    }

    if (!frm.doc.geo_pit_layout) {
        frappe.msgprint("Geo Pit Layout is required.");
        return false;
    }

    if (!frm.doc.item || !frm.doc.item.length) {
        frappe.msgprint("Add at least one Material Stack Item.");
        return false;
    }

    for (const row of frm.doc.item) {
        if (!row.material_seam) {
            frappe.msgprint(`Material / Seam is required in row ${row.idx}.`);
            return false;
        }

        if (!row.value_type) {
            frappe.msgprint(`Value Type is required in row ${row.idx}.`);
            return false;
        }

        if (!row.geology_run) {
            frappe.msgprint(`Geology Run is required in row ${row.idx}.`);
            return false;
        }

        if (row.density_source === "Manual" && !Number(row.manual_density || 0)) {
            frappe.msgprint(`Manual Density is required in row ${row.idx}.`);
            return false;
        }
    }

    return true;
}

function check_stack(frm) {
    if (!validate_stack(frm)) return;

    frappe.call({
        method: "is_production.geo_planning.services.material_stack_service.get_material_stack_summary",
        args: {
            material_stack: frm.doc.name
        },
        freeze: true,
        freeze_message: "Checking material stack...",
        callback(r) {
            const msg = r.message || {};
            const items = msg.items || [];

            let html = `
                <b>Material Stack Check</b><br>
                Layout Blocks: <b>${msg.layout_block_count || 0}</b><br>
                Mining Blocks: <b>${msg.existing_mining_block_count || 0}</b><br>
                Stack Items: <b>${msg.stack_item_count || 0}</b><br>
                Existing Material Values: <b>${msg.existing_material_values || 0}</b><br>
                Existing Summaries: <b>${msg.existing_material_summaries || 0}</b><br><br>
                <table class="table table-bordered">
                    <thead>
                        <tr>
                            <th>Material</th>
                            <th>Value Type</th>
                            <th>Run</th>
                            <th>Results</th>
                            <th>Vol</th>
                            <th>Density</th>
                            <th>Tonnes</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            items.forEach(item => {
                html += `
                    <tr>
                        <td>${frappe.utils.escape_html(item.material_seam || "")}</td>
                        <td>${frappe.utils.escape_html(item.value_type || "")}</td>
                        <td>${frappe.utils.escape_html(item.run_name || item.geology_run || "")}</td>
                        <td>${item.result_count || 0}</td>
                        <td>${item.use_for_volume ? "Yes" : "No"}</td>
                        <td>${item.use_for_density ? "Yes" : "No"}</td>
                        <td>${item.use_for_tonnes ? "Yes" : "No"}</td>
                    </tr>
                `;
            });

            html += "</tbody></table>";

            frappe.msgprint(html);
        }
    });
}

function enqueue_stack_job(frm, operation_type) {
    if (!validate_stack(frm)) return;

    frappe.confirm(
        `Queue ${operation_type} for this Material Stack? This will run in the background.`,
        () => {
            frappe.call({
                method: "is_production.geo_planning.services.material_stack_jobs.enqueue_material_stack_job",
                args: {
                    material_stack: frm.doc.name,
                    operation_type: operation_type,
                    create_missing_mining_blocks: 1,
                    overwrite_existing: 1,
                    update_block_status: 1,
                    mineable_only: 0
                },
                freeze: true,
                freeze_message: `Queuing ${operation_type}...`,
                callback(r) {
                    const msg = r.message || {};
                    frappe.msgprint(`
                        ${operation_type} queued.<br>
                        Batch: <b>${msg.batch || ""}</b><br>
                        Job ID: <b>${msg.job_id || ""}</b><br><br>
                        Use <b>View Calculation Batches</b> or <b>Refresh Status</b> to check progress.
                    `);
                    frm.reload_doc();
                }
            });
        }
    );
}

function generate_missing_mining_blocks(frm) {
    if (!frm.doc.geo_pit_layout) {
        frappe.msgprint("Geo Pit Layout is required.");
        return;
    }

    frappe.confirm("Generate missing Mining Blocks for this stack layout?", () => {
        frappe.call({
            method: "is_production.geo_planning.services.mining_block_jobs.enqueue_generate_mining_blocks",
            args: {
                geo_pit_layout: frm.doc.geo_pit_layout,
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
            }
        });
    });
}