frappe.ui.form.on("Geo Calculation Batch", {
    refresh(frm) {
        set_default_values(frm);
        toggle_source_fields(frm);
        add_buttons(frm);
        set_indicators(frm);
    },

    source_mode(frm) {
        toggle_source_fields(frm);
    },

    reference_variable_code(frm) {
        update_all_full_names(frm);
    },

    reference_variable_name(frm) {
        update_all_full_names(frm);
    },

    target_variable_code(frm) {
        update_all_full_names(frm);
    },

    target_variable_name(frm) {
        update_all_full_names(frm);
    },

    calculated_variable_code(frm) {
        update_all_full_names(frm);
    },

    calculated_variable_name(frm) {
        update_all_full_names(frm);
    },

    before_save(frm) {
        update_all_full_names(frm);
    }
});


function safe_set_value(frm, fieldname, value) {
    if (!frm.fields_dict[fieldname]) return;

    const current = frm.doc[fieldname];
    const currentNormalised = current === null || current === undefined ? "" : String(current);
    const nextNormalised = value === null || value === undefined ? "" : String(value);

    if (currentNormalised !== nextNormalised) {
        frm.set_value(fieldname, value);
    }
}


function set_default_values(frm) {
    if (!frm.doc.source_mode) {
        safe_set_value(frm, "source_mode", "Attached Files");
    }

    if (!frm.doc.calculation_type) {
        safe_set_value(frm, "calculation_type", "Reference Minus Target");
    }

    if (!frm.doc.processing_status) {
        safe_set_value(frm, "processing_status", "Draft");
    }

    if (!frm.doc.approval_status) {
        safe_set_value(frm, "approval_status", "Draft");
    }

    if (!frm.doc.coordinate_rounding) {
        safe_set_value(frm, "coordinate_rounding", 2);
    }

    if (frm.doc.replace_existing === undefined || frm.doc.replace_existing === null) {
        safe_set_value(frm, "replace_existing", 1);
    }
}


function set_indicators(frm) {
    if (frm.doc.processing_status) {
        const color = {
            "Draft": "gray",
            "Validated": "orange",
            "Queued": "orange",
            "Processing": "blue",
            "Processed": "green",
            "Error": "red"
        }[frm.doc.processing_status] || "gray";

        frm.dashboard.add_indicator(`Processing: ${frm.doc.processing_status}`, color);
    }

    if (frm.doc.approval_status) {
        const color = {
            "Draft": "gray",
            "Approved": "green",
            "Rejected": "red",
            "Superseded": "red"
        }[frm.doc.approval_status] || "gray";

        frm.dashboard.add_indicator(`Approval: ${frm.doc.approval_status}`, color);
    }

    if (frm.doc.success_count) {
        frm.dashboard.add_indicator(`Calculated Points: ${frm.doc.success_count}`, "green");
    }

    if (frm.doc.error_count) {
        frm.dashboard.add_indicator(`Errors: ${frm.doc.error_count}`, "red");
    }
}


function add_buttons(frm) {
    frm.clear_custom_buttons();

    frm.add_custom_button("Detect Reference Variables", () => {
        detect_variables(frm, "reference");
    }, "Variables");

    frm.add_custom_button("Detect Target Variables", () => {
        detect_variables(frm, "target");
    }, "Variables");

    frm.add_custom_button("Update Full Names", () => {
        update_all_full_names(frm);
        frappe.show_alert({
            message: "Full names updated.",
            indicator: "green"
        });
    }, "Variables");

    if (frm.is_new()) {
        return;
    }

    frm.add_custom_button("Calculate Points", () => {
        start_calculation(frm);
    }, "Calculation");

    frm.add_custom_button("Run Calculation Now", () => {
        run_calculation_now(frm);
    }, "Calculation");

    frm.add_custom_button("View Calculated Points", () => {
        frappe.set_route("List", "Geo Calculated Points", {
            calculation_batch: frm.doc.name
        });
    }, "View");

    frm.add_custom_button("Use in Geology Run", () => {
        create_geology_run_from_calculation(frm);
    }, "Next Step");

    frm.add_custom_button("Open Viewer", () => {
        frappe.set_route("geology-viewer");
    }, "View");

    frm.add_custom_button("Approve Calculation", () => {
        frm.set_value("approval_status", "Approved");
        frm.save();
    }, "Actions");
}


function toggle_source_fields(frm) {
    const mode = frm.doc.source_mode || "Attached Files";
    const attached = mode === "Attached Files";
    const batches = mode === "Existing Import Batches";

    frm.toggle_display("reference_file_attachment", attached);
    frm.toggle_display("target_file_attachment", attached);

    frm.toggle_display("reference_import_batch", batches);
    frm.toggle_display("target_import_batch", batches);
}


function detect_variables(frm, side) {
    if (frm.is_new() || frm.is_dirty()) {
        frappe.msgprint({
            title: "Save Required",
            indicator: "orange",
            message: "Please save the Geo Calculation Batch before detecting variables."
        });
        return;
    }

    const title = side === "reference" ? "Reference" : "Target";

    frappe.call({
        method: "is_production.geo_planning.doctype.geo_calculation_batch.geo_calculation_batch.detect_calculation_variables",
        args: {
            docname: frm.doc.name,
            side: side
        },
        freeze: true,
        freeze_message: `Reading ${title} variables...`,
        callback(r) {
            const variables = r.message || [];

            if (!variables.length) {
                frappe.msgprint({
                    title: "No Variables Found",
                    indicator: "orange",
                    message: `No ${title.toLowerCase()} variable columns were found.`
                });
                return;
            }

            const d = new frappe.ui.Dialog({
                title: `Select ${title} Variable`,
                fields: [
                    {
                        fieldname: "variable_code",
                        fieldtype: "Select",
                        label: "Variable Code",
                        options: variables.map(v => v.code).join("\n"),
                        reqd: 1
                    },
                    {
                        fieldname: "variable_name",
                        fieldtype: "Data",
                        label: "Variable Name / Meaning"
                    }
                ],
                primary_action_label: "Use This Variable",
                primary_action(values) {
                    safe_set_value(frm, `${side}_variable_code`, values.variable_code);

                    if (values.variable_name) {
                        safe_set_value(frm, `${side}_variable_name`, values.variable_name);
                    }

                    update_all_full_names(frm);

                    frappe.msgprint({
                        title: `${title} Variable Selected`,
                        indicator: "green",
                        message:
                            `Selected ${title.toLowerCase()} variable: <b>${values.variable_code}</b><br>` +
                            "Please save before calculating points."
                    });

                    d.hide();
                }
            });

            d.show();
        }
    });
}


function validate_calculation_ready(frm) {
    if (!frm.doc.geo_project) {
        frappe.msgprint("Geo Project is required.");
        return false;
    }

    if (!frm.doc.version_tag) {
        frappe.msgprint("Version Tag is required.");
        return false;
    }

    if (!frm.doc.calculation_name) {
        frappe.msgprint("Calculation Name is required.");
        return false;
    }

    if (!frm.doc.calculated_variable_code) {
        frappe.msgprint("Calculated Variable Code is required.");
        return false;
    }

    if (!frm.doc.reference_variable_code) {
        frappe.msgprint("Reference Variable Code is required.");
        return false;
    }

    if (!frm.doc.target_variable_code) {
        frappe.msgprint("Target Variable Code is required.");
        return false;
    }

    const mode = frm.doc.source_mode || "Attached Files";

    if (mode === "Attached Files") {
        if (!frm.doc.geo_model_output) {
            frappe.msgprint("Geo Model Output is required when using Attached Files.");
            return false;
        }

        if (!frm.doc.reference_file_attachment) {
            frappe.msgprint("Reference File Attachment is required.");
            return false;
        }

        if (!frm.doc.target_file_attachment) {
            frappe.msgprint("Target File Attachment is required.");
            return false;
        }
    }

    if (mode === "Existing Import Batches") {
        if (!frm.doc.reference_import_batch) {
            frappe.msgprint("Reference Import Batch is required.");
            return false;
        }

        if (!frm.doc.target_import_batch) {
            frappe.msgprint("Target Import Batch is required.");
            return false;
        }
    }

    if (frm.is_dirty()) {
        frappe.msgprint({
            title: "Save Required",
            indicator: "orange",
            message: "Please save the Geo Calculation Batch before calculating points."
        });
        return false;
    }

    return true;
}


function start_calculation(frm) {
    if (!validate_calculation_ready(frm)) {
        return;
    }

    frappe.confirm(
        "This will create <b>Geo Calculated Points</b> in the background.<br><br>" +
        `<b>${frm.doc.calculated_full_name || frm.doc.calculated_variable_code}</b><br><br>` +
        `Formula: <b>${frm.doc.reference_variable_code}</b> ${formula_label(frm.doc.calculation_type)} <b>${frm.doc.target_variable_code}</b><br><br>` +
        "Continue?",
        () => {
            frappe.call({
                method: "is_production.geo_planning.doctype.geo_calculation_batch.geo_calculation_batch.enqueue_create_calculated_points",
                args: {
                    docname: frm.doc.name,
                    replace_existing: frm.doc.replace_existing ? 1 : 0
                },
                freeze: true,
                freeze_message: "Starting calculated points job...",
                callback(r) {
                    if (r.message) {
                        frappe.msgprint({
                            title: "Calculation Started",
                            indicator: "blue",
                            message:
                                "Calculated points are being created in the background.<br>" +
                                "Refresh this batch later to see counts.<br>" +
                                "Job ID: " + (r.message.job_id || "")
                        });

                        frm.reload_doc();
                    }
                }
            });
        }
    );
}


function run_calculation_now(frm) {
    if (!validate_calculation_ready(frm)) {
        return;
    }

    frappe.confirm(
        "Run calculation now in the current request? Use this only for smaller tests. Large grids must use Calculate Points background job.",
        () => {
            frappe.call({
                method: "is_production.geo_planning.doctype.geo_calculation_batch.geo_calculation_batch.create_calculated_points",
                args: {
                    docname: frm.doc.name,
                    replace_existing: frm.doc.replace_existing ? 1 : 0
                },
                freeze: true,
                freeze_message: "Calculating points...",
                callback(r) {
                    const msg = r.message || {};
                    frappe.msgprint(`
                        <b>Calculation Complete</b><br>
                        Reference Rows: <b>${msg.reference_row_count || 0}</b><br>
                        Target Rows: <b>${msg.target_row_count || 0}</b><br>
                        Matched Rows: <b>${msg.matched_count || 0}</b><br>
                        Created Rows: <b>${msg.success_count || 0}</b><br>
                        Errors: <b>${msg.error_count || 0}</b>
                    `);
                    frm.reload_doc();
                }
            });
        }
    );
}


function create_geology_run_from_calculation(frm) {
    if (!frm.doc.geo_project) {
        frappe.msgprint("Geo Project is required.");
        return;
    }

    if (!frm.doc.name) {
        frappe.msgprint("Save this calculation batch first.");
        return;
    }

    if (!frm.doc.calculated_variable_code) {
        frappe.msgprint("Calculated Variable Code is required.");
        return;
    }

    frappe.prompt(
        [
            {
                fieldname: "geo_pit_layout",
                label: "Geo Pit Layout",
                fieldtype: "Link",
                options: "Geo Pit Layout",
                reqd: 1
            },
            {
                fieldname: "run_name",
                label: "Run Name",
                fieldtype: "Data",
                default: frm.doc.calculation_name || frm.doc.calculated_variable_code,
                reqd: 1
            },
            {
                fieldname: "value_meaning",
                label: "Value Meaning",
                fieldtype: "Select",
                options: "\nElevation\nThickness\nDepth\nQuality\nDensity\nOther",
                default: "Thickness",
                reqd: 1
            }
        ],
        (values) => {
            frappe.new_doc("Geo Pit Layout Geology Run", {
                run_name: values.run_name,
                geo_project: frm.doc.geo_project,
                geo_pit_layout: values.geo_pit_layout,
                source_type: "Geo Calculation Batch",
                geo_calculation_batch: frm.doc.name,
                variable_name: frm.doc.calculated_full_name || frm.doc.calculated_variable_code,
                variable_code: frm.doc.calculated_variable_code,
                value_meaning: values.value_meaning,
                processing_status: "Draft",
                run_status: "Draft"
            });
        },
        "Create Geology Run from Calculation",
        "Create"
    );
}


function formula_label(calculation_type) {
    if (calculation_type === "Target Minus Reference") return "subtracted from";
    if (calculation_type === "Absolute Difference") return "absolute difference with";
    return "minus";
}


function update_all_full_names(frm) {
    update_full_name(frm, "reference");
    update_full_name(frm, "target");
    update_calculated_full_name(frm);
}


function update_full_name(frm, side) {
    const code = frm.doc[`${side}_variable_code`] || "";
    const name = frm.doc[`${side}_variable_name`] || "";

    let fullName = "";

    if (code && name) {
        fullName = code + " - " + name;
    } else if (code) {
        fullName = code;
    }

    safe_set_value(frm, `${side}_full_name`, fullName);
}


function update_calculated_full_name(frm) {
    const code = frm.doc.calculated_variable_code || "";
    const name = frm.doc.calculated_variable_name || "";

    let fullName = "";

    if (code && name) {
        fullName = code + " - " + name;
    } else if (code) {
        fullName = code;
    }

    safe_set_value(frm, "calculated_full_name", fullName);
}


frappe.realtime.on("geo_calculated_points_complete", function(data) {
    if (!data) return;

    frappe.msgprint({
        title: data.status === "success" ? "Calculation Complete" : "Calculation Failed",
        indicator: data.status === "success" ? "green" : "red",
        message:
            "Batch: " + data.batch +
            "<br>Status: " + data.status +
            "<br>Variable: " + (data.full_name || data.variable_code || "") +
            "<br>Reference rows: " + (data.reference_row_count || 0) +
            "<br>Target rows: " + (data.target_row_count || 0) +
            "<br>Matched: " + (data.matched_count || 0) +
            "<br>Created: " + (data.success_count || 0) +
            "<br>Errors: " + (data.error_count || 0)
    });

    if (cur_frm && cur_frm.doctype === "Geo Calculation Batch") {
        cur_frm.reload_doc();
    }
});