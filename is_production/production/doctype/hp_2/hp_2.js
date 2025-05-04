// Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("HP 2", {
    // 0) On form load/refresh, make sure Dozer options reflect any pre‐existing PWA rows
    refresh(frm) {
      console.log("Refresh:", frm.doc);
      update_dozer_options(frm);
    },
  
    // 1) When the MPP 2 link changes, fetch its mining_areas and fill your PWA table
    mpp2_link(frm) {
      console.log("mpp2_link:", frm.doc.mpp2_link);
      if (!frm.doc.mpp2_link) {
        console.warn("No MPP 2 selected—skipping.");
        return;
      }
  
      frappe.db.get_doc("MPP 2", frm.doc.mpp2_link)
        .then(mpp2 => {
          console.log("Fetched MPP 2:", mpp2);
  
          // Clear out old PWA rows
          frm.clear_table("pwa");
  
          // Copy each mining_areas row into your PWA table
          (mpp2.mining_areas || []).forEach(areaRow => {
            // detect actual field key
            const val = areaRow.mining_area !== undefined
              ? areaRow.mining_area
              : areaRow.mining_areas;
  
            frm.add_child("pwa", {
              mining_areas: val
            });
          });
  
          frm.refresh_field("pwa");
  
          // Immediately rebuild Dozer options off the new PWA rows
          update_dozer_options(frm);
        })
        .catch(err => {
          console.error("Error fetching MPP 2:", err);
        });
    },
  
    // 2) Whenever the user adds or removes a row in PWA, rebuild Dozer options
    pwa_add(frm, cdt, cdn) {
      console.log("PWA row added");
      update_dozer_options(frm);
    },
    pwa_remove(frm, cdt, cdn) {
      console.log("PWA row removed");
      update_dozer_options(frm);
    }
  });
  
  // ── helper to rebuild the Dozer dropdown ──
  function update_dozer_options(frm) {
    // Gather non-empty mining_areas values
    const opts = (frm.doc.pwa || [])
      .map(r => r.mining_areas)
      .filter(v => v);
  
    const options_str = opts.join("\n");
    console.log("Updating Dozer options to:", opts);
  
    frm.fields_dict['dozer_production']
      .grid
      .update_docfield_property(
        'mining_areas_dozer_child',
        'options',
        options_str
      );
  
    // If you want to default existing rows to the first option, uncomment:
    // frm.doc.dozer_production.forEach(row =>
    //   frappe.ui.form.set_value({
    //     fieldname: 'mining_areas_dozer_child',
    //     value: opts[0] || "",
    //     row: row
    //   })
    // );
  
    frm.refresh_field('dozer_production');
  }
  