frappe.pages['ceo-dashboard'].on_page_load = function(wrapper) {

	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'CEO dashboard',
		single_column: true
	});

	// Create iframe to load the report
	let iframe = `
		<iframe
			src="/app/query-report/CEO%20Dashboard%20One"
			style="width:100%; height:900px; border:none;">
		</iframe>
	`;

	$(page.body).html(iframe);
};
