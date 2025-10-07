// listen for server-side “logs” and print them to the browser console
frappe.realtime.on("preuse:update_log", (data) => {
  console.log(
    "%c[PreUseHours]",
    "color:teal;font-weight:bold;",
    data.msg
  );
});

// ✅ Category order definition
const CATEGORY_ORDER = [
  "Excavator",
  "ADT",
  "Dozer",
  "Water Bowser",
  "Diesel Bowsers",
  "Service Truck",
  "Grader",
  "TLB",
  "Drills"
];

// ✅ Utility sorter
function sort_assets(assets) {
  return assets.sort((a, b) => {
    const orderA = CATEGORY_ORDER.indexOf(a.asset_category);
    const orderB = CATEGORY_ORDER.indexOf(b.asset_category);
    const safeA = orderA === -1 ? 999 : orderA;
    const safeB = orderB === -1 ? 999 : orderB;

    if (safeA !== safeB) return safeA - safeB;
    return (a.asset_name || a.name).localeCompare(b.asset_name || b.name);
  });
}

frappe.ui.form.on('Pre-Use Hours', {
  shift_system: function (frm) {
    update_shift_options(frm, frm.doc.shift_system);
  },

  location: function (frm) {
    if (frm.doc.location) {
      frm.clear_table('pre_use_assets');
      fetch_assets(frm);

      if (frm.doc.shift_date) {
        fetch_shift_system(frm);
      }
      set_avail_util_lookup(frm);
    }
  },

  shift_date: function (frm) {
    if (frm.doc.location) {
      fetch_shift_system(frm);
    }
    set_avail_util_lookup(frm);
  },

  shift: function (frm) {
    set_avail_util_lookup(frm);
  },

  refresh: function (frm) {
    fetch_pre_use_status(frm);

    decorate_integrity_band(frm);
    render_integrity_html_with_nav(frm);

    console.log("🧪 Summary from server:", frm.doc.data_integrity_summary);

    // ✅ Add refresh machines button
    frm.add_custom_button(
      __('🔄 Refresh Machines'),
      () => frm.trigger('refresh_machines_from_assets'),
      __('Actions')
    );
  },

  // ✅ Handler for the refresh machines button (syncs instead of wiping)
  refresh_machines_from_assets: function(frm) {
    if (!frm.doc.location) {
      frappe.msgprint(__('Please select a location first.'));
      return;
    }

    frappe.call({
      method: "frappe.client.get_list",
      args: {
        doctype: "Asset",
        filters: {
          location: frm.doc.location,
          asset_category: ["in", CATEGORY_ORDER],
          docstatus: 1   // ✅ only submitted Assets
        },
        fields: ["name", "item_name", "asset_category", "asset_name"],
        limit_page_length: 500
      },
      callback: function(r) {
        const assets = sort_assets(r.message || []);
        const assetMap = {};
        assets.forEach(a => {
          const key = a.asset_name || a.name;
          assetMap[key] = a;
        });

        // Track kept rows
        const keepRows = [];

        // 1️⃣ Check existing rows → keep if still valid, update info
        (frm.doc.pre_use_assets || []).forEach(row => {
          const key = row.asset_name;
          if (assetMap[key]) {
            row.item_name = assetMap[key].item_name;
            row.asset_category = assetMap[key].asset_category;
            keepRows.push(key);
          }
        });

        // 2️⃣ Add missing new assets
        assets.forEach(asset => {
          const key = asset.asset_name || asset.name;
          if (!keepRows.includes(key)) {
            const row = frm.add_child("pre_use_assets");
            row.asset_name = asset.asset_name || asset.name;
            row.item_name = asset.item_name;
            row.asset_category = asset.asset_category;
          }
        });

        // 3️⃣ Remove rows not in Asset list anymore
        frm.doc.pre_use_assets = (frm.doc.pre_use_assets || []).filter(
          row => assetMap[row.asset_name]
        );

        frm.refresh_field("pre_use_assets");
        frappe.msgprint(__("✅ Machines list synchronized with Asset list (added/removed only)."));
      }
    });
  }
});

/**
 * Dynamically set Shift options based on the shift system
 */
function update_shift_options(frm, shift_system) {
  const shift_options = {
    '3x8Hour': ['Morning', 'Afternoon', 'Night'],
    '2x12Hour': ['Day', 'Night']
  };
  frm.set_df_property('shift', 'options', shift_options[shift_system] || []);
}

/**
 * Fetch relevant assets for the selected location
 */
function fetch_assets(frm) {
  frappe.call({
    method: 'frappe.client.get_list',
    args: {
      doctype: 'Asset',
      filters: {
        location: frm.doc.location,
        asset_category: ['in', CATEGORY_ORDER],
        docstatus: 1
      },
      fields: ['name', 'asset_name', 'item_name', 'asset_category'],
      limit_page_length: 1000
    },
    callback: function (response) {
      if (response.message) {
        const assets = sort_assets(response.message);

        frm.clear_table('pre_use_assets');
        assets.forEach(asset => {
          const row = frm.add_child('pre_use_assets');
          row.asset_name = asset.asset_name || asset.name;
          row.item_name = asset.item_name;
          row.asset_category = asset.asset_category;
        });
        frm.refresh_field('pre_use_assets');
      }
    }
  });
}

/**
 * Fetch the shift system from Monthly Production Planning
 */
function fetch_shift_system(frm) {
  if (!frm.doc.location || !frm.doc.shift_date) return;

  frappe.call({
    method: 'frappe.client.get_list',
    args: {
      doctype: 'Monthly Production Planning',
      filters: {
        location: frm.doc.location,
        prod_month_start_date: ["<=", frm.doc.shift_date],
        prod_month_end_date: [">=", frm.doc.shift_date],
        site_status: "Producing"
      },
      fields: ['name', 'prod_month_start_date', 'prod_month_end_date', 'shift_system'],
      limit_page_length: 1
    },
    callback: function (response) {
      if (response.message && response.message.length) {
        const record = response.message[0];

        const shift_date_obj = frappe.datetime.str_to_obj(frm.doc.shift_date);
        const month_start_obj = frappe.datetime.str_to_obj(record.prod_month_start_date);
        const month_end_obj = frappe.datetime.str_to_obj(record.prod_month_end_date);

        if (shift_date_obj < month_start_obj || shift_date_obj > month_end_obj) {
          frappe.throw(
            __("Shift Date must be between {0} and {1} (inclusive).", [
              frappe.datetime.obj_to_user(month_start_obj),
              frappe.datetime.obj_to_user(month_end_obj)
            ])
          );
        }

        frm.set_value('shift_system', record.shift_system);
        update_shift_options(frm, record.shift_system);
      }
    }
  });
}

/**
 * Build "Availability and Utilisation Lookup"
 */
function set_avail_util_lookup(frm) {
  if (frm.doc.location && frm.doc.shift_date && frm.doc.shift) {
    const shift_date_formatted = frappe.datetime.str_to_user(frm.doc.shift_date);
    const avail_util_lookup_value = `${frm.doc.location}-${shift_date_formatted}-${frm.doc.shift}`;
    frm.set_value('avail_util_lookup', avail_util_lookup_value);
  }
}

/**
 * Fetch and display a table of Pre-Use Status records
 */
function fetch_pre_use_status(frm) {
  frappe.call({
    method: 'frappe.client.get_list',
    args: {
      doctype: 'Pre-Use Status',
      fields: ['name', 'pre_use_avail_status'],
      order_by: 'name asc'
    },
    callback: function (response) {
      const records = response.message;
      let html = records && records.length
        ? generate_status_table(records)
        : "<p>No records found in 'Pre-Use Status'.</p>";

      html += "<br><b>Please ensure correct status is indicated for each Plant. "
           + "For example, if Plant is not working at shift start due to Breakdown, "
           + "status of 2 must be selected. Or if machine is spare, select status 3.</b>";

      $(frm.fields_dict.pre_use_status_explain.wrapper).html(html);
    }
  });
}

/**
 * Generate an HTML table with status records
 */
function generate_status_table(records) {
  let html = "<table style='width:100%; border-collapse: collapse;'>";
  html += "<tr><th>Status</th><th>Pre-Use Availability Status</th></tr>";
  records.forEach(record => {
    html += `<tr><td>${record.name}</td><td>${record.pre_use_avail_status}</td></tr>`;
  });
  html += "</table>";
  return html;
}

function decorate_integrity_band(frm) {
  const indicator = frm.doc.data_integ_indicator;
  const wrapper = frm.fields_dict.data_integrity_summary?.$wrapper;

  if (wrapper) {
    wrapper.css({
      "border": "2px solid transparent",
      "padding": "10px",
      "border-radius": "6px"
    });

    if (indicator === "Red") {
      wrapper.css("border", "2px solid red");
      wrapper.css("background-color", "#ffe6e6");
    } else if (indicator === "Yellow") {
      wrapper.css("border", "2px solid orange");
      wrapper.css("background-color", "#fff8e1");
    } else if (indicator === "Green") {
      wrapper.css("border", "2px solid green");
      wrapper.css("background-color", "#e8f5e9");
    }
  }
}

function render_integrity_html_with_nav(frm) {
  const wrapper = frm.fields_dict.data_integrity_summary.$wrapper;
  if (!wrapper) return;

  let raw = frm.doc.data_integrity_summary || '';
  raw = raw.replace(/^\s+|\s+$/g, '').replace(/\n\s+/g, '\n');
  wrapper.empty().append(raw);

  function bindNav(selector, isPrev) {
    wrapper.find(selector)
      .off('click')
      .on('click', () => {
        const op    = isPrev ? '<' : '>';
        const order = isPrev ? 'desc' : 'asc';
        const msg   = isPrev ? 'No earlier record' : 'No newer record';

        frappe.call({
          method: 'frappe.client.get_list',
          args: {
            doctype: 'Pre-Use Hours',
            filters: {
              location: frm.doc.location,
              creation: [op, frm.doc.creation]
            },
            fields: ['name'],
            order_by: `creation ${order}`,
            limit_page_length: 1
          },
          callback: r => {
            if (r.message && r.message.length) {
              frappe.set_route('Form', 'Pre-Use Hours', r.message[0].name);
            } else {
              frappe.msgprint(msg);
            }
          }
        });
      });
  }

  bindNav('#prev_record_top', true);
  bindNav('#prev_record',      true);
  bindNav('#next_record_top', false);
  bindNav('#next_record',     false);
}

// ✅ Reload previous doc in open form when server asks
frappe.realtime.on('preuse:reload_doc', function(data) {
  if (cur_frm
    && cur_frm.doc
    && data.doctype === cur_frm.doctype
    && data.name === cur_frm.doc.name) {
      cur_frm.reload_doc();
  }
});


