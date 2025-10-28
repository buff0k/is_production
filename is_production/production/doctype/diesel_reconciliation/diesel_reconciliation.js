// ===========================================================
// Diesel Reconciliation Form Script (Full Extended Version)
// -----------------------------------------------------------
// Author: Isambane Mining (Pty) Ltd
// Year: 2025
// ===========================================================
// Features:
// 1. Filters Monthly Production Plan by selected Site
// 2. Loads Start/End Dates from selected Monthly Production Plan
// 3. Filters BOTH Plant No and Tank No dropdowns by:
//    - Asset Category = Diesel Bowsers / Diesel Bulk
//    - Location = selected Site
// 4. Auto-fetches diesel_issued and diesel_receipts when machine selected
// 5. Auto-Fill button to load all diesel data from backend
// 6. Calculates Theoretical Closing Balance & Variance per row
// 7. "Recalculate All" button for recalculations
// 8. Automatically fetches totals for all Asset Categories
// ===========================================================

frappe.ui.form.on("Diesel Reconciliation", {
  onload(frm) {
    set_monthly_plan_query(frm);
    if (frm.doc.site) {
      set_bowser_query(frm);
      set_tank_query(frm);
    }
  },

  site(frm) {
    frm.set_value("monthly_production_plan", "");
    frm.refresh_field("monthly_production_plan");

    frm.clear_table("diesel_bowser_readings");
    frm.clear_table("main_tank_readings");
    frm.refresh_fields(["diesel_bowser_readings", "main_tank_readings"]);

    set_monthly_plan_query(frm);
    set_bowser_query(frm);
    set_tank_query(frm);
  },

  async monthly_production_plan(frm) {
    if (!frm.doc.monthly_production_plan) return;

    try {
      const result = await frappe.db.get_value(
        "Monthly Production Planning",
        frm.doc.monthly_production_plan,
        ["prod_month_start_date", "prod_month_end_date"]
      );

      if (result && result.message) {
        frm.set_value("start_date", result.message.prod_month_start_date);
        frm.set_value("end_date", result.message.prod_month_end_date);
        frappe.show_alert({
          message: "Dates loaded from Monthly Production Planning",
          indicator: "green",
        });
      }
    } catch (e) {
      frappe.msgprint("Could not load plan dates. Please check configuration.");
    }

    set_bowser_query(frm);
    set_tank_query(frm);
  },

  refresh(frm) {
    set_monthly_plan_query(frm);
    set_bowser_query(frm);
    set_tank_query(frm);

    // Auto-Fill Button
    if (!frm.is_new()) {
      frm.add_custom_button("Auto-Fill Diesel Data", async function () {
        if (!frm.doc.site || !frm.doc.start_date || !frm.doc.end_date) {
          frappe.msgprint("Please fill Site, Start Date, and End Date first.");
          return;
        }

        frappe.call({
          method: "is_production.production.doctype.diesel_reconciliation.diesel_reconciliation.auto_fill_all_diesel_data",
          args: {
            site: frm.doc.site,
            start_date: frm.doc.start_date,
            end_date: frm.doc.end_date,
          },
          callback: function (r) {
            if (r.message) {
              populate_child_tables(frm, r.message);
              frappe.show_alert({
                message: "Diesel Data Loaded Successfully",
                indicator: "green",
              });
              update_equipment_category_totals(frm);
            } else {
              frappe.msgprint("No data returned from backend.");
            }
          },
        });
      }).addClass("btn-primary");
    }

    // Recalculate All Button
    frm.add_custom_button("Recalculate All Rows", function () {
      recalculate_all_rows(frm);
      update_equipment_category_totals(frm);
    });
  },
});

// --------------------------------------------------------
// Helper Functions
// --------------------------------------------------------

function set_monthly_plan_query(frm) {
  frm.set_query("monthly_production_plan", () => {
    if (frm.doc.site) {
      return { filters: { location: frm.doc.site } };
    } else {
      frappe.msgprint("Please select a Site first.");
      return {};
    }
  });
}

// Diesel Bowser Readings – filter Plant No dropdown
function set_bowser_query(frm) {
  if (frm.fields_dict.diesel_bowser_readings) {
    frm.fields_dict.diesel_bowser_readings.grid.get_field("plant_no").get_query =
      function () {
        return {
          filters: [
            ["asset_category", "in", ["Diesel Bowsers", "Diesel Bulk"]],
            ["location", "=", frm.doc.site || ""],
          ],
        };
      };
  }
}


// Main Tank Readings – filter Tank No dropdown
function set_tank_query(frm) {
  if (frm.fields_dict.main_tank_readings) {
    frm.fields_dict.main_tank_readings.grid.get_field("tank_no").get_query =
      function () {
        return {
          filters: [
            ["asset_category", "in", ["Diesel Bowsers", "Diesel Bulk"]],
            ["location", "=", frm.doc.site || ""],
          ],
        };
      };
  }
}

// Populate child tables with backend data
function populate_child_tables(frm, data) {
  frm.clear_table("diesel_bowser_readings");
  frm.clear_table("main_tank_readings");

  (data.bowsers || []).forEach((d) => {
    const row = frm.add_child("diesel_bowser_readings");
    row.plant_no = d.asset;
    row.opening_balance = d.opening_balance || 0;
    row.diesel_receipts = d.receipt_total || 0;
    row.diesel_issued = d.issue_total || 0;
    row.dipstick_value = d.dipstick_value || 0;
  });

  (data.tanks || []).forEach((d) => {
    const row = frm.add_child("main_tank_readings");
    row.tank_no = d.asset;
    row.opening_balance = d.opening_balance || 0;
    row.diesel_receipts = d.receipt_total || 0;
    row.diesel_issued = d.issue_total || 0;
    row.dipstick_value = d.dipstick_value || 0;
  });

  frm.refresh_fields(["diesel_bowser_readings", "main_tank_readings"]);
}

// --------------------------------------------------------
// CHILD TABLE CALCULATIONS (Per Row)
// --------------------------------------------------------

frappe.ui.form.on("Diesel Bowser Readings", {
  plant_no: async function (frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!frm.doc.start_date || !frm.doc.end_date) {
      frappe.msgprint("Please select Start Date and End Date first.");
      return;
    }

    frappe.call({
      method: "is_production.production.doctype.diesel_reconciliation.diesel_reconciliation.get_machine_diesel_totals",
      args: {
        site: frm.doc.site,
        start_date: frm.doc.start_date,
        end_date: frm.doc.end_date,
        asset_name: row.plant_no,
      },
      callback: function (r) {
        if (r.message) {
          row.diesel_issued = r.message.diesel_issued || 0;
          row.diesel_receipts = r.message.diesel_received || 0;
          calculate_row_values(frm, cdt, cdn);
          frm.refresh_field("diesel_bowser_readings");
          update_equipment_category_totals(frm);
        } else {
          frappe.msgprint("Could not fetch diesel totals.");
        }
      },
    });
  },

  diesel_issued: function (frm, cdt, cdn) {
    calculate_row_values(frm, cdt, cdn);
    update_equipment_category_totals(frm);
  },
  diesel_receipts: function (frm, cdt, cdn) {
    calculate_row_values(frm, cdt, cdn);
    update_equipment_category_totals(frm);
  },
  opening_balance: function (frm, cdt, cdn) {
    calculate_row_values(frm, cdt, cdn);
  },
  dipstick_value: function (frm, cdt, cdn) {
    calculate_row_values(frm, cdt, cdn);
  },
});

frappe.ui.form.on("Main Tank Readings", {
  tank_no: async function (frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!frm.doc.start_date || !frm.doc.end_date) {
      frappe.msgprint("Please select Start Date and End Date first.");
      return;
    }

    frappe.call({
      method: "is_production.production.doctype.diesel_reconciliation.diesel_reconciliation.get_machine_diesel_totals",
      args: {
        site: frm.doc.site,
        start_date: frm.doc.start_date,
        end_date: frm.doc.end_date,
        asset_name: row.tank_no,
      },
      callback: function (r) {
        if (r.message) {
          row.diesel_issued = r.message.diesel_issued || 0;
          row.diesel_receipts = r.message.diesel_received || 0;
          calculate_row_values(frm, cdt, cdn);
          frm.refresh_field("main_tank_readings");
          update_equipment_category_totals(frm);
        } else {
          frappe.msgprint("Could not fetch diesel totals.");
        }
      },
    });
  },

  diesel_issued: function (frm, cdt, cdn) {
    calculate_row_values(frm, cdt, cdn);
    update_equipment_category_totals(frm);
  },
  diesel_receipts: function (frm, cdt, cdn) {
    calculate_row_values(frm, cdt, cdn);
    update_equipment_category_totals(frm);
  },
  opening_balance: function (frm, cdt, cdn) {
    calculate_row_values(frm, cdt, cdn);
  },
  dipstick_value: function (frm, cdt, cdn) {
    calculate_row_values(frm, cdt, cdn);
  },
});

// --------------------------------------------------------
// Shared Calculation Logic
// --------------------------------------------------------

function calculate_row_values(frm, cdt, cdn) {
  const row = locals[cdt][cdn];

  const opening = flt(row.opening_balance || 0);
  const receipts = flt(row.diesel_receipts || 0);
  const issued = flt(row.diesel_issued || 0);
  const dipstick = flt(row.dipstick_value || 0);

  const theoretical = opening + receipts - issued;
  const variance = dipstick - theoretical;

  frappe.model.set_value(cdt, cdn, "theoretical_closing_balance", theoretical);
  frappe.model.set_value(cdt, cdn, "variance", variance);

  if (variance !== 0) {
    frappe.show_alert({
      message: "Variance detected for " + (row.plant_no || row.tank_no || "asset"),
      indicator: "red",
    });
  }
}

// --------------------------------------------------------
// Recalculate All Button Logic
// --------------------------------------------------------

function recalculate_all_rows(frm) {
  (frm.doc.diesel_bowser_readings || []).forEach((row) => {
    calculate_row_values(frm, "Diesel Bowser Readings", row.name);
  });

  (frm.doc.main_tank_readings || []).forEach((row) => {
    calculate_row_values(frm, "Main Tank Readings", row.name);
  });

  frappe.show_alert({
    message: "All rows recalculated",
    indicator: "green",
  });

  frm.refresh_fields(["diesel_bowser_readings", "main_tank_readings"]);
}

// --------------------------------------------------------
// Update Totals per Asset Category
// --------------------------------------------------------

function update_equipment_category_totals(frm) {
  if (!frm.doc.site || !frm.doc.start_date || !frm.doc.end_date) return;

  frappe.call({
    method:
      "is_production.production.doctype.diesel_reconciliation.diesel_reconciliation.calculate_equipment_totals_by_site",
    args: {
      site: frm.doc.site,
      start_date: frm.doc.start_date,
      end_date: frm.doc.end_date,
    },
    callback: function (r) {
      if (r.message) {
        const t = r.message;

        frm.set_value("adt", t["ADT"] || 0);
        frm.set_value("dozers", t["Dozer"] || 0);
        frm.set_value("excavators", t["Excavator"] || 0);
        frm.set_value("service_trucks", t["Service Truck"] || 0);
        frm.set_value("grader", t["Grader"] || 0);
        frm.set_value("tlb", t["TLB"] || 0);
        frm.set_value("diesel_bowser", t["Diesel Bowsers"] || 0);
        frm.set_value("water_bowser", t["Water Bowser"] || 0);
        frm.set_value("drills", t["Drills"] || 0);
        frm.set_value("lightning_plant", t["Lightning Plant"] || 0);
        frm.set_value("ldv", t["LDV"] || 0);
        frm.set_value("generator", t["Generator"] || 0);
        frm.set_value("water_pump", t["Water pump"] || 0);
        frm.set_value("total", t["Total"] || 0);
        frm.set_value("all_items_group", t["All items group"] || 0);

        frm.refresh_fields([
  "adt", "dozers", "excavators", "service_trucks", "grader",
  "tlb", "diesel_bowser", "water_bowser", "drills",
  "lightning_plant", "ldv", "generator", "water_pump",
  "all_items_group", "total",
]);

        frappe.show_alert({
          message: "Diesel Issued per Asset Category Updated",
          indicator: "green",
        });
      }
    },
  });
}
