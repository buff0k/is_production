// Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Production Shift ADT"] = {
    onload: function(report) {
        const today = frappe.datetime.get_today();
        report.set_filter_value('start_date', today);
        report.set_filter_value('end_date', today);
    }
};


