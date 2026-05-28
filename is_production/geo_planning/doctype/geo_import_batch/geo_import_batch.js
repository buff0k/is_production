frappe.ui.form.on("Geo Import Batch", {
	refresh(frm) {
		apply_import_type_ui(frm);
		add_buttons(frm);

		// Important:
		// Do NOT call update_full_name(frm) here.
		// Calling frm.set_value() on refresh can mark the document dirty
		// immediately after a successful save, causing "Saved" toast +
		// "Not Saved" header at the same time.
	},

	import_type(frm) {
		apply_import_type_ui(frm);
		frm.clear_custom_buttons();
		add_buttons(frm);
		update_full_name(frm);
	},

	boundary_type(frm) {
		if (is_boundary_polygon(frm) && !frm.doc.variable_name) {
			frm.set_value("variable_name", frm.doc.boundary_type || "");
		}

		update_full_name(frm);
	},

	raw_file_attachment(frm) {
		// Only clear dependent values when the attachment is changed.
		set_value_if_changed(frm, "variable_code", "");
		set_value_if_changed(frm, "full_name", "");
	},

	variable_code(frm) {
		update_full_name(frm);
	},

	variable_name(frm) {
		update_full_name(frm);
	},

	before_save(frm) {
		// Important:
		// Do NOT use frm.set_value() inside before_save for this.
		// Direct assignment avoids async dirty-state issues during save.
		frm.doc.full_name = build_full_name(frm);
	}
});

function is_boundary_polygon(frm) {
	return frm.doc.import_type === "Boundary Polygon";
}

function set_value_if_changed(frm, fieldname, value) {
	const current = frm.doc[fieldname] || "";
	const next = value || "";

	if (current !== next) {
		frm.set_value(fieldname, next);
	}
}

function build_full_name(frm) {
	const boundary_mode = is_boundary_polygon(frm);
	const code = frm.doc.variable_code || "";
	const name = frm.doc.variable_name || "";
	const boundary_type = frm.doc.boundary_type || "";

	if (boundary_mode) {
		return name || boundary_type || "Boundary Polygon";
	}

	if (code && name) {
		return code + " - " + name;
	}

	if (code) {
		return code;
	}

	return "";
}

function update_full_name(frm) {
	set_value_if_changed(frm, "full_name", build_full_name(frm));
}

function apply_import_type_ui(frm) {
	const boundary_mode = is_boundary_polygon(frm);

	frm.toggle_display("variable_code", !boundary_mode);
	frm.toggle_display("variable_name", true);
	frm.toggle_display("full_name", true);

	frm.toggle_display("boundary_format", boundary_mode);
	frm.toggle_display("boundary_type", boundary_mode);
	frm.toggle_display("coordinate_transform", boundary_mode);

	frm.toggle_reqd("variable_code", !boundary_mode);
	frm.toggle_reqd("boundary_format", boundary_mode);
	frm.toggle_reqd("boundary_type", boundary_mode);

	if (boundary_mode) {
		if (!frm.doc.boundary_format) {
			set_value_if_changed(frm, "boundary_format", "Auto Detect");
		}

		if (!frm.doc.boundary_type) {
			set_value_if_changed(frm, "boundary_type", "Pit Outline");
		}

		if (!frm.doc.coordinate_transform) {
			set_value_if_changed(frm, "coordinate_transform", "None");
		}

		if (!frm.doc.variable_name && frm.doc.boundary_type) {
			set_value_if_changed(frm, "variable_name", frm.doc.boundary_type);
		}
	}
}

function add_buttons(frm) {
	frm.clear_custom_buttons();

	if (is_boundary_polygon(frm)) {
		if (!frm.is_new()) {
			frm.add_custom_button("Import Boundary To Pit Outline Points", () => {
				start_boundary_pit_outline_import(frm);
			});
		}

		return;
	}

	frm.add_custom_button("Detect Variables", () => {
		if (!frm.doc.raw_file_attachment) {
			frappe.msgprint({
				title: "File Required",
				indicator: "orange",
				message: "Please attach the raw geo file first."
			});
			return;
		}

		frappe.call({
			method: "is_production.geo_planning.doctype.geo_import_batch.geo_import_batch.detect_geo_model_variables_from_file",
			args: {
				file_url: frm.doc.raw_file_attachment
			},
			freeze: true,
			freeze_message: "Reading file header...",
			callback(r) {
				const variables = r.message || [];

				if (!variables.length) {
					frappe.msgprint({
						title: "No Variables Found",
						indicator: "orange",
						message: "No variable columns were found in the file header."
					});
					return;
				}

				const d = new frappe.ui.Dialog({
					title: "Select Variable To Import",
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
							label: "Variable Name / Meaning",
							description: "Example: Pit Outline, Seam 2 Upper Ash, Seam 2 Upper CV, Seam 2 Lower RD",
							reqd: 0
						}
					],
					primary_action_label: "Use This Variable",
					primary_action(values) {
						frm.set_value("variable_code", values.variable_code);

						if (values.variable_name) {
							frm.set_value("variable_name", values.variable_name);
						}

						update_full_name(frm);

						frappe.msgprint({
							title: "Variable Selected",
							indicator: "green",
							message:
								"Selected variable code: <b>" + values.variable_code + "</b><br>" +
								"Now save the document before importing points."
						});

						d.hide();
					}
				});

				d.show();
			}
		});
	});

	if (!frm.is_new()) {
		frm.add_custom_button("Geo Model Points", () => {
			start_geo_model_points_import(frm);
		});

		frm.add_custom_button("Pit Outline", () => {
			start_pit_outline_import(frm);
		});
	}
}

function validate_common_import_ready(frm) {
	if (!frm.doc.raw_file_attachment) {
		frappe.msgprint({
			title: "File Required",
			indicator: "orange",
			message: "Please attach the raw geo file first."
		});
		return false;
	}

	if (frm.is_dirty()) {
		frappe.msgprint({
			title: "Save Required",
			indicator: "orange",
			message: "Please save the Geo Import Batch before importing points."
		});
		return false;
	}

	return true;
}

function validate_grid_import_ready(frm) {
	if (!validate_common_import_ready(frm)) {
		return false;
	}

	if (!frm.doc.variable_code) {
		frappe.msgprint({
			title: "Variable Code Required",
			indicator: "orange",
			message: "Please click Detect Variables and select a variable before importing."
		});
		return false;
	}

	return true;
}

function validate_boundary_import_ready(frm) {
	if (!validate_common_import_ready(frm)) {
		return false;
	}

	if (!frm.doc.boundary_type) {
		frappe.msgprint({
			title: "Boundary Type Required",
			indicator: "orange",
			message: "Please select a Boundary Type before importing."
		});
		return false;
	}

	if (!frm.doc.boundary_format) {
		frappe.msgprint({
			title: "Boundary Format Required",
			indicator: "orange",
			message: "Please select a Boundary Format before importing."
		});
		return false;
	}

	return true;
}

function start_geo_model_points_import(frm) {
	if (!validate_grid_import_ready(frm)) {
		return;
	}

	frappe.confirm(
		"This will import the selected variable into <b>Geo Model Points</b>:<br><br><b>" +
		(frm.doc.full_name || frm.doc.variable_code) +
		"</b><br><br>Continue?",
		() => {
			frappe.call({
				method: "is_production.geo_planning.doctype.geo_import_batch.geo_import_batch.enqueue_create_geo_model_points",
				args: {
					docname: frm.doc.name,
					replace_existing: 1
				},
				freeze: true,
				freeze_message: "Starting Geo Model Points import...",
				callback(r) {
					if (r.message) {
						frappe.msgprint({
							title: "Geo Model Points Import Started",
							indicator: "blue",
							message:
								"Geo Model Points import is running in the background.<br>" +
								"Variable: " + (frm.doc.full_name || frm.doc.variable_code) + "<br>" +
								"Refresh this batch later to see row counts.<br>" +
								"Job ID: " + r.message.job_id
						});

						frm.reload_doc();
					}
				}
			});
		}
	);
}

function start_pit_outline_import(frm) {
	if (!validate_grid_import_ready(frm)) {
		return;
	}

	frappe.confirm(
		"This will import the selected grid variable into <b>Pit Outline Points</b>:<br><br><b>" +
		(frm.doc.full_name || frm.doc.variable_code) +
		"</b><br><br>Continue?",
		() => {
			frappe.call({
				method: "is_production.geo_planning.doctype.geo_import_batch.geo_import_batch.enqueue_create_pit_outline_points",
				args: {
					docname: frm.doc.name,
					replace_existing: 1
				},
				freeze: true,
				freeze_message: "Starting Pit Outline import...",
				callback(r) {
					if (r.message) {
						frappe.msgprint({
							title: "Pit Outline Import Started",
							indicator: "blue",
							message:
								"Pit Outline Points import is running in the background.<br>" +
								"Variable: " + (frm.doc.full_name || frm.doc.variable_code) + "<br>" +
								"Refresh this batch later to see row counts.<br>" +
								"Job ID: " + r.message.job_id
						});

						frm.reload_doc();
					}
				}
			});
		}
	);
}

function start_boundary_pit_outline_import(frm) {
	if (!validate_boundary_import_ready(frm)) {
		return;
	}

	frappe.confirm(
		"This will import the boundary polygon directly into <b>Pit Outline Points</b>:<br><br>" +
		"<b>Boundary Type:</b> " + (frm.doc.boundary_type || "") + "<br>" +
		"<b>Boundary Format:</b> " + (frm.doc.boundary_format || "") + "<br>" +
		"<b>Transform:</b> " + (frm.doc.coordinate_transform || "None") + "<br><br>" +
		"Continue?",
		() => {
			frappe.call({
				method: "is_production.geo_planning.doctype.geo_import_batch.geo_import_batch.enqueue_create_boundary_pit_outline_points",
				args: {
					docname: frm.doc.name,
					replace_existing: 1
				},
				freeze: true,
				freeze_message: "Starting Boundary Polygon import...",
				callback(r) {
					if (r.message) {
						frappe.msgprint({
							title: "Boundary Import Started",
							indicator: "blue",
							message:
								"Boundary polygon import is running in the background.<br>" +
								"Target: Pit Outline Points<br>" +
								"Boundary Type: " + (frm.doc.boundary_type || "") + "<br>" +
								"Job ID: " + r.message.job_id
						});

						frm.reload_doc();
					}
				}
			});
		}
	);
}

frappe.realtime.on("geo_model_points_import_complete", function(data) {
	show_import_complete_message(data, "Geo Model Points");
});

frappe.realtime.on("pit_outline_points_import_complete", function(data) {
	show_import_complete_message(data, "Pit Outline Points");
});

function show_import_complete_message(data, label) {
	if (!data) {
		return;
	}

	frappe.msgprint({
		title: data.status === "success" ? label + " Import Complete" : label + " Import Failed",
		indicator: data.status === "success" ? "green" : "red",
		message:
			"Batch: " + data.batch +
			"<br>Status: " + data.status +
			"<br>Variable/Boundary: " + (data.full_name || data.variable_code || "") +
			"<br>Rows found: " + (data.row_count || 0) +
			"<br>Created: " + (data.success_count || 0) +
			"<br>Errors: " + (data.error_count || 0)
	});

	if (cur_frm) {
		cur_frm.reload_doc();
	}
}