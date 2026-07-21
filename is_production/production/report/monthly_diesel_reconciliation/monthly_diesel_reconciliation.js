// Copyright (c) 2026, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Monthly Diesel Reconciliation"] = {
	filters: [
		{
			fieldname: "site",
			label: __("Site"),
			fieldtype: "Link",
			options: "Location",
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_end(),
			reqd: 1,
		},
	],

	onload(report) {
		report.page.set_title(__("Diesel Reconciliation"));
		add_diesel_report_styles();
	},

	after_datatable_render() {
		render_diesel_html_report();
	},
};


function add_diesel_report_styles() {
	if (document.getElementById("diesel-reconciliation-styles")) {
		return;
	}

	const style = document.createElement("style");
	style.id = "diesel-reconciliation-styles";

	style.innerHTML = `
		.diesel-html-report {
			margin-top: 24px;
			border-radius: 16px;
			overflow: hidden;
			border: 1px solid var(--border-color);
			background: var(--card-bg);
			box-shadow: 0 8px 30px rgba(0, 0, 0, 0.08);
		}

		.diesel-report-header {
			display: flex;
			justify-content: space-between;
			align-items: center;
			gap: 20px;
			padding: 22px 24px;
			color: #ffffff;
			background:
				linear-gradient(
					135deg,
					rgba(24, 28, 34, 0.98),
					rgba(61, 67, 74, 0.96)
				);
			border-bottom: 4px solid #e67e22;
		}

		.diesel-report-title {
			margin: 0;
			color: #ffffff;
			font-size: 22px;
			font-weight: 800;
			letter-spacing: 0.3px;
			text-shadow: 0 1px 2px rgba(0, 0, 0, 0.35);
			}

			.diesel-report-subtitle {
				margin-top: 5px;
				color: rgba(255, 255, 255, 0.82);
				font-size: 13px;
				font-weight: 500;
			}

		.diesel-report-period {
			min-width: 230px;
			padding: 11px 15px;
			border-radius: 10px;
			background: rgba(255, 255, 255, 0.1);
			border: 1px solid rgba(255, 255, 255, 0.16);
			text-align: right;
			font-weight: 600;
		}

		.diesel-table-scroll {
			width: 100%;
			overflow-x: auto;
		}

		.diesel-report-table {
			width: 100%;
			min-width: 1180px;
			border-collapse: separate;
			border-spacing: 0;
			font-size: 13px;
		}

		.diesel-report-table thead th {
			position: sticky;
			top: 0;
			z-index: 2;
			padding: 13px 12px;
			color: #ffffff;
			background: #2f343b;
			border-right: 1px solid rgba(255, 255, 255, 0.08);
			border-bottom: 3px solid #e67e22;
			text-align: left;
			white-space: nowrap;
			font-weight: 700;
		}

		.diesel-report-table thead th.numeric {
			text-align: right;
		}

		.diesel-report-table tbody td {
			padding: 11px 12px;
			border-right: 1px solid var(--border-color);
			border-bottom: 1px solid var(--border-color);
			vertical-align: middle;
			background: var(--card-bg);
		}

		.diesel-report-table tbody tr.machine-row:hover td {
			background: var(--subtle-fg);
		}

		.diesel-report-table td.numeric {
			text-align: right;
			font-variant-numeric: tabular-nums;
			white-space: nowrap;
		}

		.diesel-report-table td.fleet-number {
			font-weight: 700;
			color: var(--text-color);
		}

		.diesel-report-table td.model-name {
			color: var(--text-muted);
		}

		.diesel-category-total td {
			font-weight: 800;
			background: #e9ecef !important;
			border-top: 3px solid #343a40 !important;
			border-bottom: 3px solid #343a40 !important;
		}

		.diesel-grand-total td {
			font-size: 14px;
			font-weight: 900;
			color: #ffffff;
			background: #252a30 !important;
			border-top: 4px solid #e67e22 !important;
			border-bottom: 4px solid #e67e22 !important;
		}

		.diesel-count-badge {
			display: inline-flex;
			align-items: center;
			justify-content: center;
			min-width: 30px;
			height: 25px;
			padding: 0 9px;
			border-radius: 999px;
			color: #ffffff;
			background: #343a40;
			font-size: 12px;
			font-weight: 800;
		}

		.diesel-grand-total .diesel-count-badge {
			color: #252a30;
			background: #f39c3d;
		}

		.diesel-value-good {
			color: #198754;
			font-weight: 700;
		}

		.diesel-value-warning {
			color: #d97706;
			font-weight: 700;
		}

		.diesel-value-bad {
			color: #c0392b;
			font-weight: 800;
		}

		.diesel-no-data {
			padding: 45px 20px;
			text-align: center;
			color: var(--text-muted);
			font-size: 14px;
		}

		@media (max-width: 768px) {
			.diesel-report-header {
				align-items: flex-start;
				flex-direction: column;
			}

			.diesel-report-period {
				width: 100%;
				text-align: left;
			}
		}
	`;

	document.head.appendChild(style);
}


function render_diesel_html_report() {
	const report = frappe.query_report;
	const data = report?.data || [];

	const report_wrapper = report?.$report;
	if (!report_wrapper || !report_wrapper.length) {
		return;
	}

	hide_standard_datatable(report_wrapper);

	report_wrapper.find(".diesel-html-report").remove();

	const site = report.get_filter_value("site") || "";
	const from_date = report.get_filter_value("from_date");
	const to_date = report.get_filter_value("to_date");

	const html = build_diesel_report_html(
		data,
		site,
		from_date,
		to_date
	);

	report_wrapper.append(html);
}


function hide_standard_datatable(report_wrapper) {
	report_wrapper
		.find(
			[
				".datatable",
				".dt-scrollable",
				".report-result",
				".result",
			].join(",")
		)
		.hide();
}


function build_diesel_report_html(
	data,
	site,
	from_date,
	to_date
) {
	if (!data.length) {
		return `
			<div class="diesel-html-report">
				${build_report_header(site, from_date, to_date)}
				<div class="diesel-no-data">
					${__("No diesel reconciliation information was found.")}
				</div>
			</div>
		`;
	}

	const rows = data
		.map((row) => build_diesel_row(row))
		.join("");

	return `
		<div class="diesel-html-report">
			${build_report_header(site, from_date, to_date)}

			<div class="diesel-table-scroll">
				<table class="diesel-report-table">
					<thead>
						<tr>
							<th>${__("Asset Category")}</th>
							<th>${__("Fleet Number")}</th>
							<th>${__("Model / Description")}</th>
							<th class="numeric">${__("Machines")}</th>
							<th class="numeric">${__("Litres Consumed")}</th>
							<th class="numeric">${__("Average Litres/Day")}</th>
							<th class="numeric">${__("Working Hours")}</th>
							<th class="numeric">${__("Actual L/hour")}</th>
							<th class="numeric">${__("OEM L/hour")}</th>
							<th class="numeric">${__("Variance")}</th>
						</tr>
					</thead>

					<tbody>
						${rows}
					</tbody>
				</table>
			</div>
		</div>
	`;
}


function build_report_header(site, from_date, to_date) {
	return `
		<div class="diesel-report-header">
			<div>
				<h2 class="diesel-report-title">
					${escape_html(site)} Diesel Reconciliation
				</h2>

				<div class="diesel-report-subtitle">
					OEM consumption comparison and machine performance
				</div>
			</div>

			<div class="diesel-report-period">
				${format_date(from_date)}
				&nbsp;–&nbsp;
				${format_date(to_date)}
			</div>
		</div>
	`;
}


function build_diesel_row(row) {
	if (row.is_grand_total) {
		return build_total_row(row, true);
	}

	if (row.is_category_total) {
		return build_total_row(row, false);
	}

	return `
		<tr class="machine-row">
			<td>${escape_html(row.asset_category)}</td>
			<td class="fleet-number">
				${build_asset_link(row.fleet_number)}
			</td>
			<td class="model-name">
				${escape_html(row.model)}
			</td>
			<td class="numeric"></td>
			<td class="numeric">
				${format_number(row.litres_mtd)}
			</td>
			<td class="numeric">
				${format_number(row.average_litres_day)}
			</td>
			<td class="numeric">
				${format_number(row.mtd_hours)}
			</td>
			<td class="numeric">
				${format_number(row.actual_lph)}
			</td>
			<td class="numeric">
				${format_number(row.oem_burn_rate)}
			</td>
			<td class="numeric ${variance_class(row.variance)}">
				${format_number(row.variance)}
			</td>
		</tr>
	`;
}


function build_total_row(row, grand_total) {
	const row_class = grand_total
		? "diesel-grand-total"
		: "diesel-category-total";

	const label = grand_total
		? __("Grand Total")
		: escape_html(row.model);

	return `
		<tr class="${row_class}">
			<td>${grand_total ? "" : escape_html(row.asset_category)}</td>
			<td></td>
			<td>${label}</td>
			<td class="numeric">
				<span class="diesel-count-badge">
					${format_integer(row.quantity)}
				</span>
			</td>
			<td class="numeric">
				${format_number(row.litres_mtd)}
			</td>
			<td class="numeric">
				${format_number(row.average_litres_day)}
			</td>
			<td class="numeric">
				${format_number(row.mtd_hours)}
			</td>
			<td class="numeric">
				${format_number(row.actual_lph)}
			</td>
			<td class="numeric"></td>
			<td class="numeric"></td>
		</tr>
	`;
}


function build_asset_link(asset_name) {
	if (!asset_name) {
		return "";
	}

	const escaped_name = escape_html(asset_name);
	const route = frappe.utils.get_form_link(
		"Asset",
		asset_name
	);

	return `
		<a href="${route}">
			${escaped_name}
		</a>
	`;
}


function variance_class(value) {
	const number = Number(value);

	if (!Number.isFinite(number)) {
		return "";
	}

	if (number >= 0) {
		return "diesel-value-good";
	}

	if (number >= -5) {
		return "diesel-value-warning";
	}

	return "diesel-value-bad";
}


function format_number(value) {
	if (
		value === null ||
		value === undefined ||
		value === ""
	) {
		return "—";
	}

	const number = Number(value);

	if (!Number.isFinite(number)) {
		return "—";
	}

	return format_currency_number(number, 2);
}


function format_currency_number(value, decimals) {
	return new Intl.NumberFormat(
		"en-ZA",
		{
			minimumFractionDigits: decimals,
			maximumFractionDigits: decimals,
		}
	).format(value);
}


function format_integer(value) {
	const number = Number(value);

	if (!Number.isFinite(number)) {
		return "0";
	}

	return new Intl.NumberFormat("en-ZA", {
		maximumFractionDigits: 0,
	}).format(number);
}


function format_date(value) {
	if (!value) {
		return "";
	}

	return frappe.datetime.str_to_user(value);
}


function escape_html(value) {
	return frappe.utils.escape_html(
		String(value || "")
	);
}