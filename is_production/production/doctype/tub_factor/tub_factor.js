// Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Tub Factor", {
    setup(frm) {
        frm.set_query("item_name", () => ({
            filters: [
                ["Item", "item_group", "in", ["ADT", "RIGID"]]
            ]
        }));
    },

    refresh(frm) {
        if (frm.doc.docstatus === 0) {
            frm.dashboard.set_headline_alert(
                __("Submit this Tub Factor before adding it to a Monthly Production Plan."),
                "blue"
            );
        } else if (frm.doc.docstatus === 1) {
            frm.dashboard.set_headline_alert(
                __("This Tub Factor is submitted and immutable. Create a new record for a different value."),
                "green"
            );
        }
    }
});
