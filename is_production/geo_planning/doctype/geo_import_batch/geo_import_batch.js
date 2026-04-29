frappe.ui.form.on("Geo Import Batch", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button("Geo Model Points", () => {
				frappe.confirm(
					"This will start a background job. You can continue working while it runs. Continue?",
					() => {
						frappe.call({
							method: "is_production.geo_planning.doctype.geo_import_batch.geo_import_batch.enqueue_create_geo_model_points",
							args: {
								docname: frm.doc.name,
								replace_existing: 1
							},
							freeze: true,
							freeze_message: "Starting background import...",
							callback(r) {
								if (r.message) {
									frappe.msgprint({
										title: "Import Started",
										indicator: "blue",
										message:
											"Geo Model Points import is running in the background.<br>" +
											"Refresh this batch later to see row counts.<br>" +
											"Job ID: " + r.message.job_id
									});
									frm.reload_doc();
								}
							}
						});
					}
				);
			});
		}
	}
});

frappe.realtime.on("geo_model_points_import_complete", function(data) {
	if (!data) return;

	frappe.msgprint({
		title: data.status === "success" ? "Geo Model Points Import Complete" : "Geo Model Points Import Failed",
		indicator: data.status === "success" ? "green" : "red",
		message:
			"Batch: " + data.batch +
			"<br>Status: " + data.status +
			"<br>Rows found: " + (data.row_count || 0) +
			"<br>Created: " + (data.success_count || 0) +
			"<br>Errors: " + (data.error_count || 0)
	});

	cur_frm && cur_frm.reload_doc();
});