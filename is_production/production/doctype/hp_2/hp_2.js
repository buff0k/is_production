// Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("HP 2", {
    // 0) On form refresh, log the full parent document for inspection
    refresh: function(frm) {
        console.log("Refresh event: Full Parent Document:", frm.doc);
    },

    // 1) When the MPP 2 link changes, fetch the linked document and populate mpp2_link2
    mpp2_link: function(frm) {
        console.log("mpp2_link event triggered: Full Parent Document:", frm.doc);

        if (!frm.doc.mpp2_link) {
            console.warn("No value found in mpp2_link field. Aborting process.");
            return;
        }

        console.log("Fetching MPP 2 document with id:", frm.doc.mpp2_link);
        frappe.db.get_doc("MPP 2", frm.doc.mpp2_link)
            .then(function(mpp2_doc) {
                console.log("Successfully fetched MPP 2 document:", mpp2_doc);

                if (!mpp2_doc.month_prod_days || mpp2_doc.month_prod_days.length === 0) {
                    console.warn("No month_prod_days child rows found.");
                    return;
                }

                // Log parent's prod_date for comparison
                console.log("Parent prod_date raw:", frm.doc.prod_date,
                            "formatted:", moment(frm.doc.prod_date).format('YYYY-MM-DD'));

                let matchFound = false;
                mpp2_doc.month_prod_days.forEach(function(childRow, idx) {
                    console.log(`Row ${idx+1} shift_start_date raw:`, childRow.shift_start_date,
                                "formatted:", moment(childRow.shift_start_date).format('YYYY-MM-DD'));

                    // Compare day‐level equality
                    if (moment(frm.doc.prod_date).isSame(moment(childRow.shift_start_date), 'day')) {
                        console.log("Match found! Setting mpp2_link2 to:", childRow.hourly_production_reference);
                        frm.set_value("mpp2_link2", childRow.hourly_production_reference);
                        frm.refresh_field("mpp2_link2");
                        matchFound = true;
                    }
                });

                if (!matchFound) {
                    console.warn("No matching child row found for parent's prod_date:",
                                 moment(frm.doc.prod_date).format('YYYY-MM-DD'));
                }
            })
            .catch(function(error) {
                console.error("Error fetching MPP 2 document:", error);
            });
    },

    // 2) When mpp2_link2 is set, dynamically update the dozer_production child‐table options
    mpp2_link2: function(frm) {
        console.log("mpp2_link2 changed. New value:", frm.doc.mpp2_link2);

        // Assume mpp2_link2 is a comma‐separated list of mining areas
        let raw = frm.doc.mpp2_link2 || "";
        let opts = raw.split(",").map(o => o.trim()).filter(o => o);
        let options_str = opts.join("\n");

        // Update the select options on the child‐table field
        frm.fields_dict['dozer_production']
           .grid
           .update_docfield_property(
             'mining_areas_dozer_child',  // child fieldname
             'options',                   // property to update
             options_str                  // newline‐separated options
           );

        // Set each existing row’s value to the first option (or blank if none)
        frm.doc.dozer_production.forEach(row => {
            frappe.ui.form.set_value({
                fieldname: 'mining_areas_dozer_child',
                value: opts[0] || "",
                row: row
            });
        });

        // Refresh the grid to show new options & values
        frm.refresh_field('dozer_production');
    }
});
