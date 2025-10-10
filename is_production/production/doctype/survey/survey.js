// public/js/survey.js

// ——————————————————————
// Child Table Script: Surveyed Values
// ——————————————————————
frappe.ui.form.on('Surveyed Values', {
  bcm: function(frm, cdt, cdn) {
    update_metric_tonnes(cdt, cdn);
    calculate_totals(frm);
  },
  rd: function(frm, cdt, cdn) {
    update_metric_tonnes(cdt, cdn);
    calculate_totals(frm);
  },
  mat_type: function(frm) {   // use mat_type here
    calculate_totals(frm);
  },
  metric_tonnes: function(frm) {
    calculate_totals(frm);
  },
  handling_method: function(frm) {
    calculate_totals(frm);
  },
  after_delete: function(frm) {
    calculate_totals(frm);
  }
});

function update_metric_tonnes(cdt, cdn) {
  let row = locals[cdt][cdn];
  let bcm = flt(row.bcm);
  let rd  = flt(row.rd);
  frappe.model.set_value(cdt, cdn, 'metric_tonnes', bcm * rd);
}

function calculate_totals(frm) {
  let total_surveyed = 0,
      total_ts       = 0,
      total_dozing   = 0,
      total_coal     = 0;

  (frm.doc.surveyed_values || []).forEach(r => {
    let bcm = flt(r.bcm);
    let mt  = flt(r.metric_tonnes);

    total_surveyed += bcm;

    if (r.handling_method === 'Truck and Shovel') {
      total_ts += bcm;
    } else if (r.handling_method === 'Dozing') {
      total_dozing += bcm;
    }

    // Coal → metric tonnes (using fieldname mat_type)
    if (r.mat_type === "Coal") {
      total_coal += mt;
    }
  });

  frm.set_value('total_surveyed_bcm', total_surveyed);
  frm.set_value('total_ts_bcm',       total_ts);
  frm.set_value('total_dozing_bcm',   total_dozing);
  frm.set_value('total_surveyed_coal_tons', total_coal);
}

// ——————————————————————
// Parent Form Script: Survey
// ——————————————————————
frappe.ui.form.on('Survey', {
  refresh: function(frm) {
    calculate_totals(frm);
  },
  last_production_shift_start_date: function(frm) {
    fetch_survey_monthly_plan(frm);
  },
  location: function(frm) {
    fetch_survey_monthly_plan(frm);
  },
  after_save: function(frm) {
    fetch_survey_monthly_plan(frm);
  }
});

function fetch_survey_monthly_plan(frm) {
  const shiftDate = frm.doc.last_production_shift_start_date;
  const loc       = frm.doc.location;

  if (!shiftDate || !loc) {
    return;
  }

  // 1) find the matching plan
  frappe.call({
    method: 'frappe.client.get_list',
    args: {
      doctype: 'Monthly Production Planning',
      fields: ['name'],
      filters: [
        ['location',              '=', loc],
        ['prod_month_start_date', '<=', shiftDate],
        ['prod_month_end_date',   '>=', shiftDate]
      ],
      order_by: 'prod_month_start_date asc',
      limit_page_length: 1
    },
    callback: function(r1) {
      let plan = (r1.message || [])[0];
      if (!plan) {
        frappe.msgprint(
          __('No plan found for {0} at {1}', [shiftDate, loc]),
          'Validation'
        );
        frm.set_value('monthly_production_plan_ref', '');
        frm.set_value('hourly_prod_ref', '');
        return;
      }

      let plan_name = plan.name;
      frm.set_value('monthly_production_plan_ref', plan_name);

      // persist the link if saved
      if (!frm.is_new()) {
        frappe.db.set_value(
          frm.doc.doctype, frm.doc.name,
          'monthly_production_plan_ref', plan_name
        );
      }

      // 2) fetch the full plan doc
      frappe.call({
        method: 'frappe.client.get',
        args: {
          doctype: 'Monthly Production Planning',
          name: plan_name
        },
        callback: function(r2) {
          let mpp = r2.message;
          if (!mpp) {
            frappe.msgprint(
              __('Failed to load plan {0}', [plan_name]),
              'Error'
            );
            return;
          }

          console.log('Monthly Production Planning:', mpp);
          console.table(mpp.month_prod_days || []);

          // 3) find the child row whose shift_start_date === shiftDate
          let match = (mpp.month_prod_days || []).find(row =>
            row.shift_start_date === shiftDate
          );

          if (match) {
            let href = match.hourly_production_reference || '';
            frm.set_value('hourly_prod_ref', href);

            if (!frm.is_new()) {
              frappe.db.set_value(
                frm.doc.doctype, frm.doc.name,
                'hourly_prod_ref', href
              ).then(() => {
                console.log('Persisted hourly_prod_ref:', href);
              });
            }
          } else {
            frappe.msgprint(
              __('No entry for shift_start_date {0} in month_prod_days of {1}',
                [shiftDate, plan_name]),
              'Validation'
            );
            frm.set_value('hourly_prod_ref', '');
          }
        }
      });
    }
  });
}
