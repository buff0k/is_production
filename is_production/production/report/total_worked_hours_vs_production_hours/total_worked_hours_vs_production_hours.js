frappe.query_reports["Total Worked Hours vs Production Hours"] = {
	filters: [
		{
			fieldname: "start_date",
			label: __("Start Date"),
			fieldtype: "Date",
			reqd: 1
		},
		{
			fieldname: "end_date",
			label: __("End Date"),
			fieldtype: "Date",
			reqd: 1
		},
		{
			fieldname: "site",
			label: __("Site"),
			fieldtype: "Link",
			options: "Location"
		},
		{
			fieldname: "shift",
			label: __("Shift"),
			fieldtype: "Select",
			options: "\nDay\nNight\nMorning\nAfternoon"
		}
	],

	onload(report) {
		const today = frappe.datetime.get_today();
		const week_ago = frappe.datetime.add_days(today, -7);

		const v = report.get_values() || {};
		if (!v.start_date) report.set_filter_value("start_date", week_ago);
		if (!v.end_date) report.set_filter_value("end_date", today);
	}
};
