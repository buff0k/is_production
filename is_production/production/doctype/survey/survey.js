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
  onload: function(frm) {
    set_mpp_ref_query(frm);
  },

  refresh: function(frm) {
    calculate_totals(frm);
    set_mpp_ref_query(frm);
  },

  location: function(frm) {
    set_mpp_ref_query(frm);
    frm.set_value('monthly_production_plan_ref', '');
    frm.set_value('hourly_prod_ref', '');
  },

  monthly_production_plan_ref: function(frm) {
    fetch_hourly_prod_ref(frm);
  },

  last_production_shift_start_date: function(frm) {
    fetch_hourly_prod_ref(frm);
  }
});

function set_mpp_ref_query(frm) {
  frm.set_query('monthly_production_plan_ref', function() {
    return {
      query: 'is_production.production.doctype.survey.survey.get_latest_mpp_for_site',
      filters: {
        location: frm.doc.location
      }
    };
  });
}

function fetch_hourly_prod_ref(frm) {
  const planName = frm.doc.monthly_production_plan_ref;
  const shiftDate = frm.doc.last_production_shift_start_date;

  if (!planName || !shiftDate) {
    frm.set_value('hourly_prod_ref', '');
    return;
  }

  frappe.call({
    method: 'frappe.client.get',
    args: {
      doctype: 'Monthly Production Planning',
      name: planName
    },
    callback: function(r) {
      let mpp = r.message;

      if (!mpp) {
        frappe.msgprint(__('Failed to load plan {0}', [planName]), 'Error');
        return;
      }

      let match = (mpp.month_prod_days || []).find(row =>
        row.shift_start_date === shiftDate
      );

      if (match) {
        frm.set_value('hourly_prod_ref', match.hourly_production_reference || '');
      } else {
        frm.set_value('hourly_prod_ref', '');
        frappe.msgprint(
          __('No entry for shift_start_date {0} in month_prod_days of {1}', [
            shiftDate,
            planName
          ]),
          'Validation'
        );
      }
    }
  });
}