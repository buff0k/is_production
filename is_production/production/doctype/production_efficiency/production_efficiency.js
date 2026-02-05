// is_production/production/doctype/production_efficiency/production_efficiency.js

frappe.ui.form.on("Production Efficiency", {
  refresh(frm) {
    // Replace old button with a single "Run" button that triggers server-side update,
    // then reloads the doc so child tables reflect new data.
    frm.add_custom_button("Run", async () => {
      if (frm.is_new()) {
        frappe.msgprint("Please save the document first.");
        return;
      }

      if (!frm.doc.site || !frm.doc.start_date || !frm.doc.end_date) {
        frappe.msgprint("Please set Site, Start Date and End Date first.");
        return;
      }

      try {
        await frappe.call({
          method:
            "is_production.production.doctype.production_efficiency.production_efficiency.run_update",
          args: { docname: frm.doc.name },
          freeze: true,
          freeze_message: "Updating Production Efficiency…",
        });

        frappe.show_alert({ message: "Updated ✅", indicator: "green" });

        // Reload to pull updated child tables from DB, then re-render HTML report
        await frm.reload_doc();
        frm.trigger("render_hourly_report");
      } catch (e) {
        console.error(e);
        frappe.msgprint({
          title: "Run failed",
          indicator: "red",
          message: e?.message || String(e),
        });
      }
    });

    frm.trigger("render_hourly_report");
  },

  start_date(frm) {
    frm.trigger("render_hourly_report");
  },
  end_date(frm) {
    frm.trigger("render_hourly_report");
  },
  site(frm) {
    frm.trigger("render_hourly_report");
  },

  monday(frm) {
    frm.trigger("render_hourly_report");
  },
  tuesday(frm) {
    frm.trigger("render_hourly_report");
  },
  wednesday(frm) {
    frm.trigger("render_hourly_report");
  },
  thursday(frm) {
    frm.trigger("render_hourly_report");
  },
  friday(frm) {
    frm.trigger("render_hourly_report");
  },
  saturday(frm) {
    frm.trigger("render_hourly_report");
  },
  sunday(frm) {
    frm.trigger("render_hourly_report");
  },

  // When users edit comments/improvements, refresh the HTML summary too
  comment(frm) {
    frm.trigger("render_hourly_report");
  },
  improvementrecommendation(frm) {
    frm.trigger("render_hourly_report");
  },

  render_hourly_report(frm) {
    if (!frm.fields_dict.hourly_report) return;

    if (frm.is_new()) {
      frm.fields_dict.hourly_report.$wrapper.html(
        `<div class="text-muted" style="padding:10px;">Save the document to generate the hourly report.</div>`
      );
      return;
    }

    try {
      const html = build_report_html(frm);
      frm.fields_dict.hourly_report.$wrapper.html(html);
    } catch (e) {
      console.error(e);
      frm.fields_dict.hourly_report.$wrapper.html(
        `<div class="text-danger" style="padding:10px;">
          Failed to render hourly report.<br>
          <pre style="white-space:pre-wrap;">${frappe.utils.escape_html(
            e?.stack || e?.message || String(e)
          )}</pre>
        </div>`
      );
    }
  },
});

// --------------------
// Main HTML builder
// --------------------

function build_report_html(frm) {
  const days = [
    { field: "monday", label: "Monday", map: get_field_map_for_day("monday") },
    { field: "tuesday", label: "Tuesday", map: get_field_map_for_day("tuesday") },
    { field: "wednesday", label: "Wednesday", map: get_field_map_for_day("wednesday") },
    { field: "thursday", label: "Thursday", map: get_field_map_for_day("thursday") },
    { field: "friday", label: "Friday", map: get_field_map_for_day("friday") },
    { field: "saturday", label: "Saturday", map: get_field_map_for_day("saturday") },
    { field: "sunday", label: "Sunday", map: get_field_map_for_day("sunday") },
  ];

  const site = escape_html(frm.doc.site || "");
  const start = escape_html(frm.doc.start_date || "");
  const end = escape_html(frm.doc.end_date || "");

  let out = `
  <style>
    .pe-wrap { padding: 10px; }
    .pe-title { display:flex; justify-content:space-between; align-items:center; margin-bottom: 10px; gap: 12px; flex-wrap: wrap; }
    .pe-title h3 { margin: 0; }
    .pe-meta { color: #6b7280; font-size: 12px; }

    .pe-day { margin: 14px 0; border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden; }
    .pe-day-head { padding: 10px 12px; background: #f9fafb; border-bottom:1px solid #e5e7eb; display:flex; justify-content:space-between; align-items:center; }
    .pe-day-head b { font-size: 14px; }
    .pe-badge { padding: 2px 8px; border-radius: 999px; font-size: 12px; background: #eef2ff; color:#3730a3; }

    /* horizontal scroll only within report area */
    .pe-scroll { overflow-x: auto; overflow-y: hidden; max-width: 100%; }

    /* wide table for 24 columns */
    .pe-table {
      border-collapse: collapse;
      table-layout: auto;
      min-width: 1800px;
      width: max-content;
    }

    .pe-table th, .pe-table td {
      border-bottom: 1px solid #f1f5f9;
      padding: 6px 8px;
      font-size: 12px;
      text-align: right;
      white-space: nowrap;
    }

    .pe-table thead th {
      background: #f8fafc;
      font-weight: 700;
    }

    .pe-table th:first-child, .pe-table td:first-child {
      text-align: left;
      position: sticky; left: 0;
      background: inherit;
      z-index: 1;
      min-width: 110px;
    }

    .pe-table th:last-child, .pe-table td:last-child { min-width: 80px; }

    .pe-table tfoot td { background: #fafafa; font-weight: 700; }

    /* Coloring rules */
    .pe-red    { background: #fee2e2; color: #991b1b; font-weight: 700; }
    .pe-yellow { background: #fef9c3; color: #92400e; font-weight: 700; }
    .pe-green  { background: #dcfce7; color: #065f46; font-weight: 700; }
    .pe-zero   { background: #ffffff; color: inherit; font-weight: 400; }

    .pe-empty { padding: 10px 12px; color: #6b7280; }

    /* summary blocks for child tables */
    .pe-block { margin-top: 18px; border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden; }
    .pe-block-head { padding: 10px 12px; background:#f9fafb; border-bottom:1px solid #e5e7eb; }
    .pe-block-head b { font-size: 14px; }
    .pe-block-body { padding: 10px 12px; }

    .pe-mini { width: 100%; border-collapse: collapse; }
    .pe-mini th, .pe-mini td { border-bottom: 1px solid #f1f5f9; padding: 6px 8px; font-size: 12px; text-align:left; vertical-align: top; }
    .pe-mini th { background:#f8fafc; font-weight:700; }
    .pe-muted { color:#6b7280; font-size: 12px; margin-top: 6px; }
  </style>

  <div class="pe-wrap">
    <div class="pe-title">
      <h3>Hourly Report</h3>
      <div class="pe-meta">${site} · ${start} → ${end}</div>
    </div>
  `;

  for (const day of days) {
    const rows = (frm.doc[day.field] || []).map((r) => ({ ...r }));

    if (!rows.length) {
      out += `
        <div class="pe-day">
          <div class="pe-day-head">
            <b>${day.label}</b>
            <span class="pe-badge">0 rows</span>
          </div>
          <div class="pe-empty">No data for ${day.label}.</div>
        </div>
      `;
      continue;
    }

    out += render_day_table(day.label, rows, day.map);
  }

  // Append neat summaries for the two child tables (read-only)
  out += render_child_table_summaries(frm);

  out += `</div>`;
  return out;
}

// --------------------
// Hourly Day table render
// --------------------

function render_day_table(dayLabel, rows, map) {
  const hourKeys = map.map((x) => x.key);
  const hourLabels = map.map((x) => x.label);

  const grouped = {};
  for (const r of rows) {
    const ex = r.excavators || "(No excavator)";
    if (!grouped[ex]) grouped[ex] = [];
    grouped[ex].push(r);
  }

  const excavatorNames = Object.keys(grouped).sort((a, b) => a.localeCompare(b));

  const totalsByHour = {};
  for (const k of hourKeys) totalsByHour[k] = 0;

  const excavatorTotals = {};
  for (const ex of excavatorNames) {
    let exTotal = 0;
    for (const k of hourKeys) {
      const sum = grouped[ex].reduce((acc, r) => acc + asNumber(r[k]), 0);
      exTotal += sum;
      totalsByHour[k] += sum;
    }
    excavatorTotals[ex] = exTotal;
  }

  const dayGrandTotal = hourKeys.reduce((acc, k) => acc + totalsByHour[k], 0);

  let html = `
    <div class="pe-day">
      <div class="pe-day-head">
        <b>${escape_html(dayLabel)}</b>
        <span class="pe-badge">${rows.length} row${rows.length === 1 ? "" : "s"}</span>
      </div>
      <div class="pe-scroll">
        <table class="pe-table">
          <thead>
            <tr>
              <th>Excavator</th>
              ${hourLabels.map((l) => `<th>${escape_html(l)}</th>`).join("")}
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
  `;

  for (const ex of excavatorNames) {
    html += `<tr><td>${escape_html(ex)}</td>`;

    for (const k of hourKeys) {
      const v = grouped[ex].reduce((acc, r) => acc + asNumber(r[k]), 0);
      const cls = cellClass(v);
      html += `<td class="${cls}">${formatNumberOrBlank(v)}</td>`;
    }

    html += `<td><b>${formatNumberOrBlank(excavatorTotals[ex])}</b></td></tr>`;
  }

  html += `
          </tbody>
          <tfoot>
            <tr>
              <td><b>Totals</b></td>
              ${hourKeys
                .map((k) => {
                  const v = totalsByHour[k];
                  const cls = cellClass(v);
                  return `<td class="${cls}">${formatNumberOrBlank(v)}</td>`;
                })
                .join("")}
              <td><b>${formatNumberOrBlank(dayGrandTotal)}</b></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  `;

  return html;
}

// --------------------
// Read-only summaries for comment + improvementrecommendation
// --------------------

function render_child_table_summaries(frm) {
  const comments = frm.doc.comment || [];
  const improvements = frm.doc.improvementrecommendation || [];

  let html = `
    <div class="pe-block">
      <div class="pe-block-head">
        <b>Comments (Summary)</b>
        <div class="pe-muted">This is a read-only summary. Edit entries in the “Comments” tab.</div>
      </div>
      <div class="pe-block-body">
        ${render_generic_child_table(frm, "Production Efficiency Comments", comments)}
      </div>
    </div>

    <div class="pe-block">
      <div class="pe-block-head">
        <b>Improvements / Recommendations (Summary)</b>
        <div class="pe-muted">This is a read-only summary. Edit entries in the “Comments” tab.</div>
      </div>
      <div class="pe-block-body">
        ${render_generic_child_table(frm, "Production Efficiency Improvements", improvements)}
      </div>
    </div>
  `;

  return html;
}

/**
 * Renders a generic child table by introspecting its DocType meta,
 * showing all non-hidden, non-layout fields.
 */
function render_generic_child_table(frm, child_doctype, rows) {
  if (!rows || !rows.length) {
    return `<div class="pe-empty">No rows.</div>`;
  }

  const meta = frappe.get_meta(child_doctype);
  if (!meta) {
    return `<div class="pe-empty">Could not load meta for ${escape_html(child_doctype)}.</div>`;
  }

  const cols = (meta.fields || []).filter((df) => {
    if (!df.fieldname) return false;
    if (df.hidden) return false;
    if (["Section Break", "Column Break", "Tab Break", "HTML", "Button"].includes(df.fieldtype)) return false;
    if (["parent", "parenttype", "parentfield", "idx", "doctype", "name", "owner", "creation", "modified", "modified_by"].includes(df.fieldname))
      return false;
    return true;
  });

  if (!cols.length) {
    return `<div class="pe-empty">No displayable columns found.</div>`;
  }

  const head = cols.map((c) => `<th>${escape_html(c.label || c.fieldname)}</th>`).join("");

  const body = rows
    .map((r) => {
      const tds = cols
        .map((c) => {
          const raw = r[c.fieldname];
          const val = format_child_value(raw, c);
          return `<td>${val}</td>`;
        })
        .join("");
      return `<tr>${tds}</tr>`;
    })
    .join("");

  return `
    <div class="pe-scroll">
      <table class="pe-mini">
        <thead><tr>${head}</tr></thead>
        <tbody>${body}</tbody>
      </table>
    </div>
  `;
}

function format_child_value(raw, df) {
  if (raw == null || raw === "") return "";

  if (df.fieldtype === "Link") return escape_html(String(raw));
  if (df.fieldtype === "Date") return escape_html(frappe.datetime.str_to_user(raw));
  if (df.fieldtype === "Datetime") return escape_html(frappe.datetime.str_to_user(raw));

  if (["Int", "Float", "Currency", "Percent"].includes(df.fieldtype)) {
    const n = flt(raw);
    if (isNaN(n)) return escape_html(String(raw));
    return escape_html(frappe.format(n, df) || String(n));
  }

  return escape_html(String(raw));
}

// --------------------
// Day field mapping per day
// --------------------

function get_field_map_for_day(day) {
  const display = [
    { label: "06-07", norm: "06_07" },
    { label: "07-08", norm: "07_08" },
    { label: "08-09", norm: "08_09" },
    { label: "09-10", norm: "09_10" },
    { label: "10-11", norm: "10_11" },
    { label: "11-12", norm: "11_12" },
    { label: "12-13", norm: "12_13" },
    { label: "13-14", norm: "13_14" },
    { label: "14-15", norm: "14_15" },
    { label: "15-16", norm: "15_16" },
    { label: "16-17", norm: "16_17" },
    { label: "17-18", norm: "17_18" },
    { label: "18-19", norm: "18_19" },
    { label: "19-20", norm: "19_20" },
    { label: "20-21", norm: "20_21" },
    { label: "21-22", norm: "21_22" },
    { label: "22-23", norm: "22_23" },
    { label: "23-00", norm: "23_00" },
    { label: "00-01", norm: "00_01" },
    { label: "01-02", norm: "01_02" },
    { label: "02-03", norm: "02_03" },
    { label: "03-04", norm: "03_04" },
    { label: "04-05", norm: "04_05" },
    { label: "05-06", norm: "05_06" },
  ];

  const variants = {
    monday: {
      "06_07": "six_to_seven",
      "07_08": "seven_to_eight",
      "08_09": "eight_nine",
      "09_10": "nine_ten",
      "10_11": "ten_eleven",
      "11_12": "eleven_twelve",
      "12_13": "twelve_thirteen",
      "13_14": "thirteen_fourteen",
      "14_15": "fourteen_fifteen",
      "15_16": "fifteen_sixteen",
      "16_17": "sixteen_seventeen",
      "17_18": "seventeen_eighteen",
      "18_19": "eighteen_nineteen",
      "19_20": "nineteen_twenty",
      "20_21": "twenty_twentyone",
      "21_22": "twentyone_twentytwo",
      "22_23": "twentytwo_twentythree",
      "23_00": "twentythree_twentyfour",
      "00_01": "twentyfour_one",
      "01_02": "one_two",
      "02_03": "two_three",
      "03_04": "three_four",
      "04_05": "four_five",
      "05_06": "five_six",
    },

    tuesday: {
      "06_07": "six_seven",
      "07_08": "seven_eight",
      "08_09": "eight_nine",
      "09_10": "nine_ten",
      "10_11": "ten_eleven",
      "11_12": "eleven_twelve",
      "12_13": "twelve_thirteen",
      "13_14": "thirteen_fourteen",
      "14_15": "fourteen_fifteen",
      "15_16": "fifteen_sixteen",
      "16_17": "sixteen_seventeen",
      "17_18": "seventeen_eighteen",
      "18_19": "eighteen_nineteen",
      "19_20": "nineteen_twenty",
      "20_21": "twenty_twentyone",
      "21_22": "twentyone_twentytwo",
      "22_23": "twentytwo_twentythree",
      "23_00": "twentythree_twentyfour",
      "00_01": "twentyfour_one",
      "01_02": "one_two",
      "02_03": "two_three",
      "03_04": "three_four",
      "04_05": "four_five",
      "05_06": "five_six",
    },

    wednesday: "tuesday",
    thursday: "tuesday",
    sunday: "tuesday",

    friday: {
      "06_07": "six_seven",
      "07_08": "seven_eight",
      "08_09": "eight_nine",
      "09_10": "nine_ten",
      "10_11": "ten_eleven",
      "11_12": "eleven_twelve",
      "12_13": "twelve_thirteen",
      "13_14": "thirteen_fourteen",
      "14_15": "fourteen_fifteen",
      "15_16": "fifteen_sixteen",
      "16_17": "sixteen_seventeen",
      "17_18": "seventeen_eighteen",
      "18_19": "eighteen_nineteen",
      "19_20": "nineteen_twenty",
      "20_21": "twenty_twentyone",
      "21_22": "twentyone_twentytwo",
      "22_23": "twentytwo_twentythree",
      "23_00": "twentythree_zero_zero",
      "00_01": "zerozero_one",
      "01_02": "one_two",
      "02_03": "two_three",
      "03_04": "three_four",
      "04_05": "four_five",
      "05_06": "five_six",
    },

    saturday: {
      "06_07": "six_seven",
      "07_08": "seven_eight",
      "08_09": "eight_nine",
      "09_10": "nine_ten",
      "10_11": "ten_eleven",
      "11_12": "eleven_twelve",
      "12_13": "twelve_thirteen",
      "13_14": "thirteen_fourteen",
      "14_15": "fourteen_fifteen",
      "15_16": "fifteen_sixteen",
      "16_17": "sixteen_seventeen",
      "17_18": "seventeen_eighteen",
      "18_19": "eighteen_nineteen",
      "19_20": "nineteen_twenty",
      "20_21": "twenty_twentyone",
      "21_22": "twentyone_twentytwo",
      "22_23": "twentytwo_twentythree",
      "23_00": "twentythree_zerozero",
      "00_01": "zerozero_one",
      "01_02": "one_two",
      "02_03": "two_three",
      "03_04": "three_four",
      "04_05": "four_fives",
      "05_06": "five_six",
    },
  };

  let v = variants[day];
  if (typeof v === "string") v = variants[v];
  if (!v) v = variants.tuesday;

  return display.map((d) => ({ label: d.label, key: v[d.norm] }));
}

// --------------------
// Coloring + formatting
// --------------------

function cellClass(value) {
  const v = asNumber(value);
  if (v <= 0) return "pe-zero";
  if (v >= 220) return "pe-green";
  if (v >= 200) return "pe-yellow";
  return "pe-red"; // 1–199
}

function asNumber(v) {
  const n = flt(v);
  return isNaN(n) ? 0 : n;
}

function formatNumberOrBlank(v) {
  const n = asNumber(v);
  if (n <= 0) return ""; // blank for 0
  return frappe.format(n, { fieldtype: "Float" }) || String(n);
}

function escape_html(s) {
  return frappe.utils.escape_html(s == null ? "" : String(s));
}
