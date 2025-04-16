// Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

// frappe.ui.form.on("HP 2", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on("HP 2", {
    // This event runs whenever the mpp2_link field is modified
    mpp2_link: function(frm) {
        if (frm.doc.mpp2_link) {
            // Fetch the linked MPP 2 document using the value from mpp2_link
            frappe.db.get_doc("MPP 2", frm.doc.mpp2_link)
                .then(function(mpp2_doc) {
                    // Check if the month_prod_days child table exists and has rows
                    if (mpp2_doc.month_prod_days && mpp2_doc.month_prod_days.length > 0) {
                        console.log("Month Production Days Data:");
                        mpp2_doc.month_prod_days.forEach(function(childRow, index) {
                            console.log("Row " + (index + 1) + ":", childRow);
                        });
                    } else {
                        console.log("No Month Production Days data found in the selected MPP 2 document.");
                    }
                })
                .catch(function(error) {
                    console.error("Error retrieving the MPP 2 document:", error);
                });
        }
    }
});
