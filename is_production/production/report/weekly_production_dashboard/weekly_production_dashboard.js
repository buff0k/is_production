frappe.query_reports["Weekly Production Dashboard"] = {
	filters: [
		{
			fieldname: "start_date",
			label: "Start Date",
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.month_start(),
			on_change: function () {
				auto_refresh_weekly_dashboard();
			}
		},
		{
			fieldname: "end_date",
			label: "End Date",
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.get_today(),
			on_change: function () {
				auto_refresh_weekly_dashboard();
			}
		},
		{
			fieldname: "site",
			label: "Site",
			fieldtype: "Link",
			options: "Location",
			reqd: 1,
			default: "Klipfontein",
			on_change: function () {
				auto_refresh_weekly_dashboard();
			}
		}
	],

	onload: function () {
		ensure_global_background_video();

		frappe.query_report.page.add_inner_button("Load Dashboard", function () {
			frappe.query_report.refresh();
		});

		setTimeout(function () {
			render_dashboard_from_report_data();
		}, 800);
	},

	after_datatable_render: function () {
		setTimeout(function () {
			render_dashboard_from_report_data();
		}, 300);
	}
};


let weekly_dashboard_refresh_timer = null;


function auto_refresh_weekly_dashboard() {
	clearTimeout(weekly_dashboard_refresh_timer);

	weekly_dashboard_refresh_timer = setTimeout(function () {
		if (!frappe.query_report) {
			return;
		}

		const filters = frappe.query_report.get_filter_values();

		if (!filters.start_date || !filters.end_date || !filters.site) {
			return;
		}

		frappe.query_report.refresh();
	}, 500);
}


function ensure_global_background_video() {
	if (!$("#weekly-dashboard-global-bg").length) {
		$("body").append(`
			<div id="weekly-dashboard-global-bg">
				<video autoplay muted loop playsinline>
					<source src="/files/BACKROUND.mp4" type="video/mp4">
				</video>
				<div class="weekly-dashboard-global-bg-overlay"></div>
			</div>
		`);
	}

	$("body").addClass("weekly-dashboard-body");

	$(window).off("hashchange.weekly_dashboard_bg").on("hashchange.weekly_dashboard_bg", function () {
		const route = window.location.hash || "";

		if (route.indexOf("/query-report/Weekly%20Production%20Dashboard") === -1) {
			$("#weekly-dashboard-global-bg").remove();
			$("body").removeClass("weekly-dashboard-body");
			$(window).off("hashchange.weekly_dashboard_bg");
		}
	});
}


function render_dashboard_from_report_data() {
	const wrapper = $(frappe.query_report.page.main);

	ensure_global_background_video();
	hide_report_datatable();

	const rows = frappe.query_report.data || [];

	if (!rows.length || !rows[0].dashboard_json) {
		const dashboard_root = get_or_create_dashboard_root(wrapper);

		dashboard_root.html(`
			${dashboard_styles()}
			<div class="weekly-dashboard-shell">
				<div class="weekly-dashboard-error">
					Dashboard data did not load. Change filters or click Load Dashboard.
				</div>
			</div>
		`);

		return;
	}

	let dashboard_data = {};

	try {
		dashboard_data = JSON.parse(rows[0].dashboard_json);
	} catch (error) {
		console.error("Could not parse dashboard JSON:", error, rows[0].dashboard_json);

		const dashboard_root = get_or_create_dashboard_root(wrapper);

		dashboard_root.html(`
			${dashboard_styles()}
			<div class="weekly-dashboard-shell">
				<div class="weekly-dashboard-error">
					Could not parse dashboard data. Check browser console.
				</div>
			</div>
		`);

		return;
	}

	console.log("Weekly Production Dashboard data:", dashboard_data);

	render_weekly_dashboard(
		wrapper,
		dashboard_data.filters || frappe.query_report.get_filter_values(),
		dashboard_data.bcm || {},
		dashboard_data.coal || {},
		dashboard_data.diesel || {},
		dashboard_data.equipment || []
	);
}


function get_or_create_dashboard_root(wrapper) {
	hide_report_datatable();

	let dashboard_root = wrapper.find(".weekly-dashboard-root");

	if (!dashboard_root.length) {
		dashboard_root = $(`<div class="weekly-dashboard-root"></div>`);

		const filter_area = $(".page-form, .standard-filter-section, .filter-section").first();
		const report_page = $(".query-report");

		if (filter_area.length) {
			dashboard_root.insertAfter(filter_area);
		} else if (report_page.length) {
			report_page.prepend(dashboard_root);
		} else {
			wrapper.prepend(dashboard_root);
		}
	}

	return dashboard_root;
}


function hide_report_datatable() {
	$(".dt-scrollable").hide();
	$(".datatable").hide();
	$(".report-wrapper").hide();
	$(".report-summary").hide();
	$(".report-result").hide();
	$(".report-footer").hide();
	$(".form-message").hide();
	$(".msgprint").hide();
	$(".freeze-message-container").hide();
	$(".empty-state").hide();
	$(".no-result").hide();
	$(".nothing-to-show").hide();

	$("div").filter(function () {
		const text = $(this).text().trim();
		return (
			text === "Nothing to show" ||
			text.includes("This report was generated")
		);
	}).hide();
}


function as_number(value) {
	if (value === null || value === undefined || value === "") {
		return 0;
	}

	if (typeof value === "number") {
		return value;
	}

	return Number(String(value).replace(/,/g, "").replace(/%/g, "").trim()) || 0;
}


function format_number(value, decimals = 0) {
	return as_number(value).toLocaleString(undefined, {
		minimumFractionDigits: decimals,
		maximumFractionDigits: decimals
	});
}


function format_percent(value) {
	return `${as_number(value).toFixed(1)}%`;
}


function render_weekly_dashboard(wrapper, filters, bcm, coal, diesel, equipment) {
	hide_report_datatable();

	const dashboard_root = get_or_create_dashboard_root(wrapper);
	const site_name = String(filters.site || "").toUpperCase();
	const video_url = "/files/BACKROUND.mp4";

	dashboard_root.html(`
		${dashboard_styles()}

		<div class="weekly-dashboard-shell">
			<div class="weekly-dashboard-slide">
				<div class="weekly-dashboard-background-video-wrap">
					<video class="weekly-dashboard-background-video" autoplay muted loop playsinline>
						<source src="${video_url}" type="video/mp4">
					</video>
					<div class="weekly-dashboard-background-overlay"></div>
				</div>

				<div class="weekly-dashboard-content">
					<div class="weekly-dashboard-header">
						<div class="weekly-dashboard-title-wrap">
							<h1>${escape_html(site_name)} WEEKLY PRODUCTION MEETING</h1>
						</div>

						<div class="weekly-dashboard-date">
							${escape_html(filters.start_date)} to ${escape_html(filters.end_date)}
						</div>
					</div>

					<div class="weekly-dashboard-grid">
						${render_progress_card("Monthly BCM Progress", bcm)}
						${render_progress_card("Monthly Coal Progress", coal)}
						${render_diesel_card(diesel)}
					</div>

					<div class="weekly-dashboard-bottom-grid">
						<div class="weekly-dashboard-card">
							<h2>Availability & Utilisation</h2>
							<div class="weekly-dashboard-section-title">Equipment Performance</div>
							${render_equipment_table(equipment)}
						</div>

						<div class="weekly-dashboard-card">
							<h2>Recommendations</h2>
							${render_recommendations(bcm, coal, diesel, equipment)}
						</div>
					</div>
				</div>
			</div>
		</div>
	`);
}


function render_progress_card(title, data) {
	const progress = Math.max(0, Math.min(100, as_number(data.progress)));

	return `
		<div class="weekly-dashboard-card">
			<h2>${escape_html(title)}</h2>

			<div class="weekly-dashboard-metric-row">
				<span>Target</span>
				<strong>${format_number(data.target)}</strong>
			</div>

			<div class="weekly-dashboard-metric-row">
				<span>Actual MTD</span>
				<strong>${format_number(data.actual)}</strong>
			</div>

			<div class="weekly-dashboard-metric-row">
				<span>Remaining</span>
				<strong>${format_number(data.remaining)}</strong>
			</div>

			<div class="weekly-dashboard-progress-text">
				${format_percent(data.progress)} of monthly target
			</div>

			<div class="weekly-dashboard-progress-bg">
				<div class="weekly-dashboard-progress-fill" style="width: ${progress}%"></div>
			</div>
		</div>
	`;
}


function render_diesel_card(data) {
	return `
		<div class="weekly-dashboard-card">
			<h2>Diesel Usage Update</h2>

			<div class="weekly-dashboard-metric-row">
				<span>Month-to-date diesel usage</span>
				<strong>${format_number(data.usage, 1)} L</strong>
			</div>

			<div class="weekly-dashboard-metric-row weekly-dashboard-diesel-cap">
				<span>Diesel Cap</span>
				<strong>${format_number(data.cap, 1)}</strong>
			</div>
		</div>
	`;
}


function render_equipment_table(equipment) {
	if (!equipment.length) {
		return `
			<div class="weekly-dashboard-empty">
				No equipment data found from Avail and Util summary.
			</div>
		`;
	}

	const rows = equipment.map(function (row) {
		return `
			<tr>
				<td>${escape_html(row.equipment)}</td>
				<td>${format_percent(row.availability)}</td>
				<td>${format_percent(row.utilisation)}</td>
			</tr>
		`;
	}).join("");

	return `
		<table class="weekly-dashboard-equipment-table">
			<thead>
				<tr>
					<th>Equipment</th>
					<th>Avail</th>
					<th>Utt</th>
				</tr>
			</thead>
			<tbody>
				${rows}
			</tbody>
		</table>
	`;
}


function render_recommendations(bcm, coal, diesel, equipment) {
	const recommendations = [];

	if (as_number(bcm.progress) < 90 || as_number(coal.progress) < 90) {
		recommendations.push(
			`Production is behind: BCM at ${format_percent(bcm.progress)} and Coal at ${format_percent(coal.progress)} of monthly target. Create a catch-up plan for remaining ${format_number(Math.abs(as_number(bcm.remaining)))} BCM and ${format_number(Math.abs(as_number(coal.remaining)))} tons coal.`
		);
	}

	if (as_number(coal.progress) < as_number(bcm.progress)) {
		recommendations.push(
			"Prioritise coal exposure and coal hauling; review drill/blast, loading areas, tip availability, and shift targets daily."
		);
	}

	if (equipment.length) {
		const lowest_util = equipment.reduce(function (lowest, row) {
			return as_number(row.utilisation) < as_number(lowest.utilisation) ? row : lowest;
		}, equipment[0]);

		recommendations.push(
			`Reduce ${lowest_util.equipment} queuing and improve road conditions/dispatching; ${lowest_util.equipment} utilisation is lowest at ${format_percent(lowest_util.utilisation)}.`
		);

		equipment.forEach(function (row) {
			if (as_number(row.availability) < 85) {
				recommendations.push(
					`${row.equipment} utilisation is ${format_percent(row.utilisation)} but availability is ${format_percent(row.availability)}; plan maintenance windows and standby support to avoid breakdown losses.`
				);
			}

			if (as_number(row.availability) >= 90 && as_number(row.utilisation) < 85) {
				recommendations.push(
					`${row.equipment} availability is good at ${format_percent(row.availability)} but utilisation is ${format_percent(row.utilisation)}; align machines to critical production areas and minimise idle time.`
				);
			}
		});
	}

	if (as_number(diesel.usage) > 0) {
		recommendations.push(
			`Diesel usage is ${format_number(diesel.usage, 1)} L; keep monitoring litres/BCM, idling, fuel issue controls, and investigate any abnormal consumption.`
		);
	}

	if (!recommendations.length) {
		recommendations.push(
			"Production and equipment performance are tracking within expected limits. Continue monitoring daily targets, equipment availability, utilisation, and diesel usage."
		);
	}

	return `
		<ul class="weekly-dashboard-recommendations">
			${recommendations.map(function (item) {
				return `<li>${escape_html(item)}</li>`;
			}).join("")}
		</ul>
	`;
}


function escape_html(value) {
	return frappe.utils.escape_html(String(value || ""));
}


function dashboard_styles() {
	return `
		<style>
			#weekly-dashboard-global-bg {
				position: fixed;
				top: 0;
				left: 0;
				width: 100vw;
				height: 100vh;
				z-index: 0;
				overflow: hidden;
				background: #04111d;
				pointer-events: none;
			}

			#weekly-dashboard-global-bg video {
				width: 100%;
				height: 100%;
				object-fit: cover;
			}

			.weekly-dashboard-global-bg-overlay {
				position: absolute;
				inset: 0;
				background: rgba(0, 0, 0, 0.50);
			}

			body.weekly-dashboard-body,
			body.weekly-dashboard-body .page-container,
			body.weekly-dashboard-body .page-body,
			body.weekly-dashboard-body .main-section-wrapper,
			body.weekly-dashboard-body .layout-main-section,
			body.weekly-dashboard-body .layout-main,
			body.weekly-dashboard-body .page-content,
			body.weekly-dashboard-body .container,
			body.weekly-dashboard-body .container-fluid {
				background: transparent !important;
			}

			body.weekly-dashboard-body .page-container {
				max-width: none !important;
				width: 100% !important;
			}

			body.weekly-dashboard-body .layout-main-section-wrapper,
			body.weekly-dashboard-body .layout-main-section,
			body.weekly-dashboard-body .page-content {
				max-width: none !important;
				width: 100% !important;
				padding-left: 0 !important;
				padding-right: 0 !important;
			}

			body.weekly-dashboard-body .layout-main-section,
			body.weekly-dashboard-body .page-form,
			body.weekly-dashboard-body .page-head {
				position: relative;
				z-index: 1;
			}

			body.weekly-dashboard-body .page-head {
				background: rgba(0, 0, 0, 0.35) !important;
				color: #ffffff !important;
				backdrop-filter: blur(2px);
				-webkit-backdrop-filter: blur(2px);
			}

			body.weekly-dashboard-body .page-form {
				background: rgba(0, 0, 0, 0.28) !important;
				border-radius: 12px;
				padding: 10px 14px;
				backdrop-filter: blur(2px);
				-webkit-backdrop-filter: blur(2px);
				margin: 10px 14px;
			}

			.weekly-dashboard-root {
				position: relative;
				z-index: 2;
				margin-top: 8px;
				margin-bottom: 0;
				font-weight: 400;
				font-style: italic;
				width: 100%;
			}

			.weekly-dashboard-root * {
				font-weight: 400 !important;
				font-style: italic !important;
			}

			.weekly-dashboard-shell {
				background: transparent;
				padding: 0 14px 14px 14px;
				width: 100%;
				min-height: calc(100vh - 150px);
			}

			.weekly-dashboard-slide {
				position: relative;
				border-radius: 10px;
				padding: 24px;
				box-shadow: 0 8px 26px rgba(0,0,0,0.45);
				width: 100%;
				max-width: none;
				margin: 0;
				overflow: hidden;
				min-height: calc(100vh - 170px);
				background: #000000;
			}

			.weekly-dashboard-background-video-wrap {
				position: absolute;
				top: 0;
				left: 0;
				right: 0;
				bottom: 0;
				z-index: 1;
			}

			.weekly-dashboard-background-video {
				width: 100%;
				height: 100%;
				object-fit: cover;
			}

			.weekly-dashboard-background-overlay {
				position: absolute;
				top: 0;
				left: 0;
				right: 0;
				bottom: 0;
				background: rgba(0, 0, 0, 0.38);
			}

			.weekly-dashboard-content {
				position: relative;
				z-index: 2;
				width: 100%;
			}

			.weekly-dashboard-header {
				display: flex;
				justify-content: space-between;
				align-items: center;
				border-bottom: 3px solid rgba(255,255,255,0.85);
				padding: 14px;
				margin-bottom: 20px;
				background: rgba(0, 0, 0, 0.35);
				border-radius: 10px;
				backdrop-filter: blur(1px);
				-webkit-backdrop-filter: blur(1px);
				gap: 16px;
			}

			.weekly-dashboard-title-wrap {
				display: flex;
				align-items: center;
				gap: 20px;
			}

			.weekly-dashboard-header h1 {
				font-size: 28px;
				font-weight: 400 !important;
				font-style: italic !important;
				margin: 4px 0;
				color: #ffffff;
				text-transform: uppercase;
				text-shadow: 0 2px 5px rgba(0,0,0,0.95);
			}

			.weekly-dashboard-date {
				font-size: 13px;
				font-weight: 400 !important;
				font-style: italic !important;
				color: #ffffff;
				margin-top: 8px;
				text-shadow: 0 2px 5px rgba(0,0,0,0.95);
				white-space: nowrap;
			}

			.weekly-dashboard-grid {
				display: grid;
				grid-template-columns: 1fr 1fr 0.8fr;
				gap: 18px;
				margin-bottom: 18px;
			}

			.weekly-dashboard-bottom-grid {
				display: grid;
				grid-template-columns: 1fr 1fr;
				gap: 18px;
			}

			.weekly-dashboard-card {
				border: 1px solid rgba(255, 255, 255, 0.35);
				border-radius: 12px;
				padding: 18px;
				background: rgba(0, 0, 0, 0.38);
				backdrop-filter: blur(1.5px);
				-webkit-backdrop-filter: blur(1.5px);
				box-shadow: 0 5px 18px rgba(0,0,0,0.25);
			}

			.weekly-dashboard-card h2 {
				font-size: 17px;
				font-weight: 400 !important;
				font-style: italic !important;
				color: #ffffff;
				margin: 0 0 14px 0;
				text-shadow: 0 2px 5px rgba(0,0,0,0.95);
			}

			.weekly-dashboard-section-title {
				font-size: 15px;
				font-weight: 400 !important;
				font-style: italic !important;
				color: #ffffff;
				margin-bottom: 10px;
				text-shadow: 0 2px 5px rgba(0,0,0,0.95);
			}

			.weekly-dashboard-metric-row {
				display: flex;
				justify-content: space-between;
				align-items: center;
				border-bottom: 1px solid rgba(255, 255, 255, 0.28);
				padding: 8px 0;
				font-size: 14px;
			}

			.weekly-dashboard-metric-row span {
				color: #ffffff;
				font-weight: 400 !important;
				font-style: italic !important;
				text-shadow: 0 2px 5px rgba(0,0,0,0.95);
			}

			.weekly-dashboard-metric-row strong {
				font-size: 14px;
				font-weight: 400 !important;
				font-style: italic !important;
				color: #ffffff;
				text-shadow: 0 2px 5px rgba(0,0,0,0.95);
			}

			.weekly-dashboard-diesel-cap {
				margin-top: 18px;
			}

			.weekly-dashboard-progress-text {
				font-size: 13px;
				font-weight: 400 !important;
				font-style: italic !important;
				color: #ffffff;
				margin-top: 14px;
				margin-bottom: 6px;
				text-shadow: 0 2px 5px rgba(0,0,0,0.95);
			}

			.weekly-dashboard-progress-bg {
				height: 18px;
				background: rgba(255, 255, 255, 0.30);
				border-radius: 20px;
				overflow: hidden;
			}

			.weekly-dashboard-progress-fill {
				height: 100%;
				background: #ffffff;
				border-radius: 20px;
				transition: width 0.3s ease;
			}

			.weekly-dashboard-equipment-table {
				width: 100%;
				border-collapse: collapse;
				font-size: 14px;
			}

			.weekly-dashboard-equipment-table th {
				background: rgba(255, 255, 255, 0.22);
				color: #ffffff;
				text-align: left;
				padding: 10px;
				font-weight: 400 !important;
				font-style: italic !important;
				text-shadow: 0 2px 5px rgba(0,0,0,0.95);
			}

			.weekly-dashboard-equipment-table td {
				border-bottom: 1px solid rgba(255, 255, 255, 0.22);
				padding: 10px;
				font-weight: 400 !important;
				font-style: italic !important;
				color: #ffffff;
				text-shadow: 0 2px 5px rgba(0,0,0,0.95);
			}

			.weekly-dashboard-recommendations {
				margin: 0;
				padding-left: 18px;
				font-size: 14px;
				line-height: 1.5;
				font-weight: 400 !important;
				font-style: italic !important;
				color: #ffffff;
			}

			.weekly-dashboard-recommendations li {
				margin-bottom: 8px;
				font-weight: 400 !important;
				font-style: italic !important;
				color: #ffffff;
				text-shadow: 0 2px 5px rgba(0,0,0,0.95);
			}

			.weekly-dashboard-loading,
			.weekly-dashboard-empty,
			.weekly-dashboard-error {
				text-align: center;
				padding: 40px;
				font-size: 16px;
				font-weight: 400 !important;
				font-style: italic !important;
				color: #ffffff;
				background: rgba(0,0,0,0.45);
				border-radius: 10px;
				text-shadow: 0 2px 5px rgba(0,0,0,0.95);
			}

			.weekly-dashboard-error {
				color: #ffdddd;
			}

			.query-report .report-wrapper,
			.query-report .report-result,
			.query-report .datatable,
			.query-report .dt-scrollable,
			.query-report .report-summary,
			.query-report .report-footer,
			.query-report .form-message {
				display: none !important;
			}

			@media (max-width: 1200px) {
				.weekly-dashboard-grid,
				.weekly-dashboard-bottom-grid {
					grid-template-columns: 1fr;
				}

				.weekly-dashboard-header {
					flex-direction: column;
					align-items: flex-start;
				}

				.weekly-dashboard-date {
					white-space: normal;
				}
			}

			@media print {
				#weekly-dashboard-global-bg,
				.page-head,
				.navbar,
				.desk-sidebar,
				.layout-side-section,
				.filter-section,
				.form-message,
				.report-footer,
				.report-result,
				.datatable {
					display: none !important;
				}

				.layout-main-section {
					border: none !important;
				}

				.weekly-dashboard-shell {
					background: #ffffff;
					padding: 0;
				}

				.weekly-dashboard-slide {
					box-shadow: none;
					border-radius: 0;
				}

				.weekly-dashboard-background-video-wrap {
					display: none !important;
				}

				.weekly-dashboard-content {
					position: static;
				}
			}
		</style>
	`;
}