// production_report.js
// Updated configuration for the Production Report with extra filters

frappe.query_reports["Production Report"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "site",
			"label": __("Site"),
			"fieldtype": "Link",
			"options": "Location",
			"reqd": 0
		},
		{
			"fieldname": "time_column",
			"label": __("Time Column Parameter"),
			"fieldtype": "Select",
			"options": "\nMonth Only\nDays and Month\nWeek and Month",
			"default": "Month Only"
		}
	]
};
