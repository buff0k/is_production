frappe.query_reports["Geo Model Points Viewer"] = {
	filters: [
		{
			fieldname: "geo_project",
			label: "Geo Project",
			fieldtype: "Link",
			options: "Geo Project",
			reqd: 0
		},
		{
			fieldname: "geo_model_output",
			label: "Geo Model Output",
			fieldtype: "Link",
			options: "Geo Model Output",
			reqd: 0
		},
		{
			fieldname: "import_batch",
			label: "Import Batch",
			fieldtype: "Link",
			options: "Geo Import Batch",
			reqd: 0
		},
		{
			fieldname: "variable_names",
			label: "Variable Names",
			fieldtype: "MultiSelectList",
			get_data: function(txt) {
				return frappe.call({
					method: "is_production.geo_planning.report.geo_model_points_viewer.geo_model_points_viewer.get_filter_options",
					args: {
						fieldname: "variable_name",
						txt: txt
					}
				}).then(r => r.message || []);
			}
		},
		{
			fieldname: "version_tags",
			label: "Version Tags",
			fieldtype: "MultiSelectList",
			get_data: function(txt) {
				return frappe.call({
					method: "is_production.geo_planning.report.geo_model_points_viewer.geo_model_points_viewer.get_filter_options",
					args: {
						fieldname: "version_tag",
						txt: txt
					}
				}).then(r => r.message || []);
			}
		},
		{
			fieldname: "status",
			label: "Status",
			fieldtype: "Select",
			options: "\nDraft\nActive\nSuperseded"
		},
		{
			fieldname: "x_from",
			label: "X From",
			fieldtype: "Float"
		},
		{
			fieldname: "x_to",
			label: "X To",
			fieldtype: "Float"
		},
		{
			fieldname: "y_from",
			label: "Y From",
			fieldtype: "Float"
		},
		{
			fieldname: "y_to",
			label: "Y To",
			fieldtype: "Float"
		},
		{
			fieldname: "z_from",
			label: "Z From",
			fieldtype: "Float"
		},
		{
			fieldname: "z_to",
			label: "Z To",
			fieldtype: "Float"
		},
		{
			fieldname: "limit",
			label: "Limit Rows",
			fieldtype: "Int",
			default: 5000
		}
	],

	formatter: function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "z" && data) {
			let z = Number(data.z);
			let min_z = Number(data.min_z);
			let max_z = Number(data.max_z);

			if (!isNaN(z) && !isNaN(min_z) && !isNaN(max_z) && max_z > min_z) {
				let ratio = (z - min_z) / (max_z - min_z);

				let bg = "#e8f1ff";
				let fg = "#0f172a";

				if (ratio >= 0.66) {
					bg = "#fee2e2";
					fg = "#991b1b";
				} else if (ratio >= 0.33) {
					bg = "#ffedd5";
					fg = "#9a3412";
				} else {
					bg = "#dbeafe";
					fg = "#1e40af";
				}

				return `<span style="
					display:block;
					padding:4px 6px;
					border-radius:6px;
					background:${bg};
					color:${fg};
					font-weight:600;
					text-align:right;
				">${value}</span>`;
			}
		}

		if (column.fieldname === "heat_band" && data) {
			let color = "#e5e7eb";

			if (data.heat_band === "High") color = "#fee2e2";
			if (data.heat_band === "Medium") color = "#ffedd5";
			if (data.heat_band === "Low") color = "#dbeafe";

			return `<span style="
				display:inline-block;
				padding:3px 8px;
				border-radius:999px;
				background:${color};
				font-weight:600;
			">${value}</span>`;
		}

		return value;
	}
};