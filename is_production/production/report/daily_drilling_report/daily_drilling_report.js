frappe.query_reports["Daily Drilling Report"] = {
	filters: [
		{
			fieldname: "site",
			label: __("Site"),
			fieldtype: "Select",
			options: ["All"],
			default: "All"
		},
		{
			fieldname: "start_date",
			label: __("Start Date"),
			fieldtype: "Date"
		},
		{
			fieldname: "end_date",
			label: __("End Date"),
			fieldtype: "Date"
		}
	],

	onload: function (report) {
		// Load distinct Site values from Daily Drilling Report
		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Daily Drilling Report",
				fields: ["site"],
				limit_page_length: 0,
				filters: { site: ["!=", ""] },
				order_by: "site asc"
			},
			callback: function (r) {
				const rows = (r.message || []);
				const sites = Array.from(new Set(rows.map(x => (x.site || "").trim()).filter(Boolean)));

				const site_filter = report.get_filter("site");
				site_filter.df.options = ["All", ...sites];
				site_filter.refresh();
			}
		});
	}
};