frappe.ui.form.on("Geo Pit Layout Geology Run", {
    refresh(frm) {
        set_defaults(frm);
        toggle_source_fields(frm);
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
    },

    source_type(frm) {
        toggle_source_fields(frm);
    },

    rule_enabled(frm) {
        toggle_rule_fields(frm);
    }
});

function set_defaults(frm) {
    if (frm.is_new()) {
        if (!frm.doc.processing_status) frm.set_value("processing_status", "Draft");
        if (!frm.doc.run_status) frm.set_value("run_status", "Draft");
        if (!frm.doc.value_meaning) frm.set_value("value_meaning", "Other");
    }
}

function set_indicators(frm) {
    if (frm.doc.processing_status) {
        const color = {
            "Draft": "gray",
            "Queued": "orange",
            "Running": "blue",
            "Complete": "green",
            "Error": "red"
        }[frm.doc.processing_status] || "gray";

        frm.dashboard.set_headline_alert(
            `<div class="indicator ${color}">Assignment Status: ${frappe.utils.escape_html(frm.doc.processing_status)}</div>`
        );
    }

    if (frm.doc.run_status) {
        const color = {
            "Draft": "gray",
            "Approved": "green",
            "Superseded": "red"
        }[frm.doc.run_status] || "gray";

        frm.dashboard.add_indicator(`Run Status: ${frm.doc.run_status}`, color);
    }
}

function toggle_source_fields(frm) {
    const source_type = frm.doc.source_type || "";

    frm.toggle_display("geo_import_batch", source_type === "Geo Import Batch");
    frm.toggle_display("geo_calculation_batch", source_type === "Geo Calculation Batch");

    toggle_rule_fields(frm);
}

function toggle_rule_fields(frm) {
    const enabled = !!frm.doc.rule_enabled;

    frm.toggle_display("rule_operator", enabled);
    frm.toggle_display("rule_value", enabled);
    frm.toggle_display("rule_value_to", enabled);
}

function add_buttons(frm) {
    if (frm.is_new()) return;

    frm.add_custom_button("Preview Assignment", () => {
        preview_assignment(frm);
    }, "Assignment");

    frm.add_custom_button("Run Assignment", () => {
        enqueue_assignment(frm);
    }, "Assignment");

    frm.add_custom_button("Run Assignment Now", () => {
        run_assignment_now(frm);
    }, "Assignment");

    frm.add_custom_button("View Results", () => {
        frappe.set_route("List", "Geo Pit Layout Geology Result", {
            geology_run: frm.doc.name
        });
    }, "View");

    frm.add_custom_button("View Assignment Batches", () => {
        frappe.set_route("List", "Geo Layout Geology Assignment Batch", {
            geology_run: frm.doc.name
        });
    }, "View");

    frm.add_custom_button("Open Viewer", () => {
        frappe.set_route("geology-viewer");
    }, "View");

    frm.add_custom_button("Approve Run", () => {
        frm.set_value("run_status", "Approved");
        frm.save();
    }, "Actions");
}

function validate_assignment_inputs(frm) {
    if (!frm.doc.geo_pit_layout) {
        frappe.msgprint("Geo Pit Layout is required.");
        return false;
    }

    if (!frm.doc.geo_project) {
        frappe.msgprint("Geo Project is required.");
        return false;
    }

    if (!frm.doc.source_type) {
        frappe.msgprint("Source Type is required.");
        return false;
    }

    if (frm.doc.source_type === "Geo Import Batch" && !frm.doc.geo_import_batch) {
        frappe.msgprint("Geo Import Batch is required.");
        return false;
    }

    if (frm.doc.source_type === "Geo Calculation Batch" && !frm.doc.geo_calculation_batch) {
        frappe.msgprint("Geo Calculation Batch is required.");
        return false;
    }

    if (frm.doc.rule_enabled) {
        if (!frm.doc.rule_operator) {
            frappe.msgprint("Rule Operator is required.");
            return false;
        }

        if (frm.doc.rule_value === undefined || frm.doc.rule_value === null || frm.doc.rule_value === "") {
            frappe.msgprint("Rule Value is required.");
            return false;
        }

        if ((frm.doc.rule_operator === "Between" || frm.doc.rule_operator === "Outside") &&
            (frm.doc.rule_value_to === undefined || frm.doc.rule_value_to === null || frm.doc.rule_value_to === "")) {
            frappe.msgprint("Rule Value To is required for Between/Outside rules.");
            return false;
        }
    }

    return true;
}

function preview_assignment(frm) {
    if (!validate_assignment_inputs(frm)) return;

    frappe.call({
        method: "is_production.geo_planning.services.layout_geology_service.preview_layout_geology",
        args: {
            geo_pit_layout: frm.doc.geo_pit_layout,
            source_type: frm.doc.source_type,
            geo_import_batch: frm.doc.geo_import_batch,
            geo_calculation_batch: frm.doc.geo_calculation_batch,
            variable_name: frm.doc.variable_name,
            variable_code: frm.doc.variable_code,
            rule_enabled: frm.doc.rule_enabled,
            rule_operator: frm.doc.rule_operator,
            rule_value: frm.doc.rule_value,
            rule_value_to: frm.doc.rule_value_to
        },
        freeze: true,
        freeze_message: "Previewing geology assignment...",
        callback(r) {
            const msg = r.message || {};
            frappe.msgprint(`
                <b>Assignment Preview Complete</b><br>
                Blocks: <b>${msg.block_count || 0}</b><br>
                Source Points: <b>${msg.total_points || 0}</b><br>
                Assigned Points: <b>${msg.assigned_points || 0}</b><br>
                Results: <b>${msg.result_count || 0}</b><br>
                Passing Blocks: <b>${msg.passing_blocks || 0}</b><br>
                Failing Blocks: <b>${msg.failing_blocks || 0}</b><br>
                No Data Blocks: <b>${msg.no_data_blocks || 0}</b>
            `);
        }
    });
}

function enqueue_assignment(frm) {
    if (!validate_assignment_inputs(frm)) return;

    frappe.confirm(
        "Queue geology assignment for this run? Existing matching results will be updated in place.",
        () => {
            frappe.call({
                method: "is_production.geo_planning.services.layout_geology_jobs.enqueue_run_geology_assignment",
                args: {
                    geology_run: frm.doc.name,
                    clear_existing_results: 0,
                    overwrite_existing: 1
                },
                freeze: true,
                freeze_message: "Queuing geology assignment...",
                callback(r) {
                    const msg = r.message || {};
                    frappe.msgprint(`
                        Geology assignment queued.<br>
                        Batch: <b>${msg.batch || ""}</b><br>
                        Job ID: <b>${msg.job_id || ""}</b>
                    `);
                    frm.reload_doc();
                }
            });
        }
    );
}

function run_assignment_now(frm) {
    if (!validate_assignment_inputs(frm)) return;

    frappe.confirm(
        "Run assignment now in the current request? Use this only for testing or smaller runs.",
        () => {
            frappe.call({
                method: "is_production.geo_planning.services.layout_geology_jobs.run_geology_assignment_now",
                args: {
                    geology_run: frm.doc.name,
                    clear_existing_results: 0,
                    overwrite_existing: 1
                },
                freeze: true,
                freeze_message: "Running geology assignment...",
                callback(r) {
                    const msg = r.message || {};
                    const updateMode = Number(msg.update_in_place || 0) ? "Yes" : "No";

                    frappe.msgprint(`
                        Assignment complete.<br>
                        Results Created: <b>${msg.results_created || 0}</b><br>
                        Results Updated: <b>${msg.results_updated || 0}</b><br>
                        Results Skipped: <b>${msg.results_skipped || 0}</b><br>
                        Passing Blocks: <b>${msg.passing_blocks || 0}</b><br>
                        Failing Blocks: <b>${msg.failing_blocks || 0}</b><br>
                        No Data Blocks: <b>${msg.no_data_blocks || 0}</b><br>
                        Assigned Points: <b>${msg.assigned_points || 0}</b><br>
                        Update In Place: <b>${updateMode}</b>
                    `);

                    frm.reload_doc();
                }
            });
        }
    );
}