frappe.pages['esd-dashboard'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'ESD Dashboard',
		single_column: true
	});
}