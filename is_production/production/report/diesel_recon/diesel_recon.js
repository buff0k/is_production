frappe.query_reports["Diesel Recon"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
		{
			"fieldname": "site",
			"label": __("Site"),
			"fieldtype": "Link",
			"options": "Location",
			"reqd": 1
		},
		{
			"fieldname": "asset_name",
			"label": __("Asset"),
			"fieldtype": "Link",
			"options": "Asset",
			"get_query": function() {
				var site = frappe.query_report.get_filter_value("site");
				if (!site) {
					frappe.msgprint(__("Please select a Site first to filter Assets."));
					return { filters: { "name": "" } };
				}
				return {
					filters: {
						"location": site,
						"asset_category": "Diesel Bowsers"
					}
				};
			}
		},
		{
			"fieldname": "time_bucket",
			"label": __("Time Bucket"),
			"fieldtype": "Select",
			"options": "\nMonth Only\nDays Only\nWeeks Only",
			"default": "Month Only",
			"reqd": 1
		}
	]
};
