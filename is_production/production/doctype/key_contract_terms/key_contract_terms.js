// Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Key Contract Terms", {
    project: function(frm) {
        if (frm.doc.project) {
            frappe.db.get_doc('Project', frm.doc.project).then(doc => {
                frm.set_value('customer', doc.customer || '');
                frm.set_value('project_name', doc.project_name || '');
            });
        }
    }
});