// is_production/production/doctype/production_efficiency/production_efficiency.js

frappe.ui.form.on("Production Efficiency", {
  refresh(frm) {
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

        await frm.reload_doc();
        frm.trigger("render_graph");
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

    frm.trigger("render_graph");
    frm.trigger("render_hourly_report");
  },

  start_date(frm) {
    frm.trigger("render_graph");
    frm.trigger("render_hourly_report");
  },
  end_date(frm) {
    frm.trigger("render_graph");
    frm.trigger("render_hourly_report");
  },
  site(frm) {
    frm.trigger("render_graph");
    frm.trigger("render_hourly_report");
  },

  monday(frm) {
    frm.trigger("render_graph");
    frm.trigger("render_hourly_report");
  },
  tuesday(frm) {
    frm.trigger("render_graph");
    frm.trigger("render_hourly_report");
  },
  wednesday(frm) {
    frm.trigger("render_graph");
    frm.trigger("render_hourly_report");
  },
  thursday(frm) {
    frm.trigger("render_graph");
    frm.trigger("render_hourly_report");
  },
  friday(frm) {
    frm.trigger("render_graph");
    frm.trigger("render_hourly_report");
  },
  saturday(frm) {
    frm.trigger("render_graph");
    frm.trigger("render_hourly_report");
  },
  sunday(frm) {
    frm.trigger("render_graph");
    frm.trigger("render_hourly_report");
  },

  comment(frm) {
    frm.trigger("render_hourly_report");
  },
  improvementrecommendation(frm) {
    frm.trigger("render_hourly_report");
  },

  render_graph(frm) {
    const targetField =
      frm.fields_dict.graph
        ? frm.fields_dict.graph
        : frm.fields_dict.hourly_report
          ? frm.fields_dict.hourly_report
          : null;

    if (!targetField) return;

    if (frm.is_new()) {
      targetField.$wrapper.html(
        `<div class="text-muted" style="padding:10px;">Save the document to generate the dashboard.</div>`
      );
      return;
    }

    try {
      const html = build_graph_html(frm);
      targetField.$wrapper.html(html);
      render_graph_charts(frm);
    } catch (e) {
      console.error(e);
      targetField.$wrapper.html(
        `<div class="text-danger" style="padding:10px;">
          Failed to render dashboard.<br>
          <pre style="white-space:pre-wrap;">${frappe.utils.escape_html(
            e?.stack || e?.message || String(e)
          )}</pre>
        </div>`
      );
    }
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

const PE_THRESHOLD = 220;
const PE_WARN = 200;

const DAILY_THRESHOLD_COLOR = "#9E9E9E";
const DAILY_THRESHOLD_DASH = "4 4";

const WTD_THRESHOLD_COLOR = "#ef4444";
const WTD_THRESHOLD_DASH = "4 0";

// Graph/KPI tab uses 18 divisor (requested). Hourly report remains 24.
const GRAPH_HOURS_PER_DAY = 18;
const REPORT_HOURS_PER_DAY = 24;

function build_graph_html(frm) {
  const site = escape_html(frm.doc.site || "");
  const start = escape_html(frm.doc.start_date || "");
  const end = escape_html(frm.doc.end_date || "");

  const computed = compute_metrics_from_doc(frm);

  // KPI boxes: removed "Week avg / Excavator" and "Latest day avg / Excavator" (requested)
  const kpis = [
    { label: "Threshold", value: PE_THRESHOLD, tone: "neutral", sub: "BCM/hr target" },
    {
      label: "Week site avg / hr",
      value: computed.week_site_avg ?? 0,
      tone: kpiTone(computed.week_site_avg),
      sub: computed.days_with_data ? `Across ${computed.days_with_data} day(s)` : "No week data",
    },
    {
      label: "Latest day site avg / hr",
      value: computed.focus_day?.daily_site_avg ?? 0,
      tone: kpiTone(computed.focus_day?.daily_site_avg),
      sub: computed.focus_day ? `${computed.focus_day.excavator_count} excavators` : "No daily data",
    },
  ];

  return `
  <style>
    .pe-dash { padding: 10px; }
    .pe-dash-head { display:flex; justify-content:space-between; align-items:flex-end; gap:12px; flex-wrap:wrap; margin-bottom:10px; }
    .pe-dash-head h3 { margin:0; }
    .pe-dash-meta { color:#6b7280; font-size:12px; }

    .pe-kpis { display:grid; grid-template-columns: repeat(3, minmax(160px, 1fr)); gap:10px; margin: 10px 0 14px; }
    @media (max-width: 1200px) { .pe-kpis { grid-template-columns: repeat(2, minmax(160px, 1fr)); } }

    .pe-kpi { border: 1px solid #e5e7eb; border-radius: 12px; padding: 10px 12px; background: #fff; box-shadow: 0 1px 1px rgba(0,0,0,.03); }
    .pe-kpi .lbl { font-size: 12px; color:#6b7280; margin-bottom: 6px; }
    .pe-kpi .val { font-size: 22px; font-weight: 800; line-height: 1.1; }
    .pe-kpi .sub { font-size: 12px; color:#6b7280; margin-top: 6px; }

    .pe-tone-red { border-left: 6px solid #ef4444; }
    .pe-tone-orange { border-left: 6px solid #f59e0b; }
    .pe-tone-green { border-left: 6px solid #22c55e; }
    .pe-tone-neutral { border-left: 6px solid #94a3b8; }

    .pe-panels { display:grid; grid-template-columns: 1fr; gap: 12px; }
    .pe-panel { border: 1px solid #e5e7eb; border-radius: 12px; background:#fff; overflow:hidden; }
    .pe-panel-h { padding: 10px 12px; background:#f9fafb; border-bottom:1px solid #e5e7eb; display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap; }
    .pe-panel-h b { font-size: 14px; }
    .pe-panel-b { padding: 10px 12px; }
    .pe-note { color:#6b7280; font-size:12px; margin-top:8px; }
    .pe-chart { width: 100%; min-height: 300px; }
    .pe-chart-sm { width: 100%; min-height: 280px; }
  </style>

  <div class="pe-dash">
    <div class="pe-dash-head">
      <h3>Production Efficiency Dashboard</h3>
      <div class="pe-dash-meta">${site} · ${start} → ${end}</div>
    </div>

    <div class="pe-kpis">
      ${kpis.map(k => `
        <div class="pe-kpi pe-tone-${escape_html(k.tone)}">
          <div class="lbl">${escape_html(k.label)}</div>
          <div class="val">${escape_html(formatKpiNumber(k.value))}</div>
          <div class="sub">${escape_html(k.sub || "")}</div>
        </div>
      `).join("")}
    </div>

    <div class="pe-panels">

      <div class="pe-panel">
        <div class="pe-panel-h">
          <b>Average rate per hour: All Excavators (Week to Date)</b>
          <span class="pe-dash-meta">${computed.days_with_data ? `${computed.days_with_data} day(s) with data` : "No data"}</span>
        </div>
        <div class="pe-panel-b">
          <div id="pe_week_hourly_chart" class="pe-chart-sm"></div>
          <div class="pe-note">
            Line shows average BCM/hr per excavator at the site for each hour (averaged across days).
          </div>
        </div>
      </div>

      <div class="pe-panel">
        <div class="pe-panel-h">
          <b>Week: Excavator daily averages (per day)</b>
          <span class="pe-dash-meta">${computed.days_with_data ? `${computed.days_with_data} day(s) with data` : "No data"}</span>
        </div>
        <div class="pe-panel-b">
          <div id="pe_week_excavator_daily_chart" class="pe-chart"></div>
          <div class="pe-note">
            Bars show each excavator’s daily average BCM/hr (sum of 24 hours ÷ ${GRAPH_HOURS_PER_DAY}) for each day.
            Threshold is the dotted line at ${PE_THRESHOLD}.
          </div>
        </div>
      </div>

      <div class="pe-panel">
        <div class="pe-panel-h">
          <b>Week To Date Rate Per Hour (Per Excavator)</b>
          <span class="pe-dash-meta">${computed.days_with_data ? `Week-to-date` : "No data"}</span>
        </div>
        <div class="pe-panel-b">
          <div id="pe_wtd_excavator_chart" class="pe-chart"></div>
          <div class="pe-note">
            One bar per excavator = total BCM captured week-to-date ÷ hours completed (${GRAPH_HOURS_PER_DAY} × days present for that excavator).
            Threshold line = ${PE_THRESHOLD}.
          </div>
        </div>
      </div>

    </div>
  </div>
  `;
}

function render_graph_charts(frm) {
  const computed = compute_metrics_from_doc(frm);

  const elA = document.getElementById("pe_week_hourly_chart");
  if (elA) {
    if (!computed.days_with_data) {
      elA.innerHTML = `<div class="text-muted" style="padding:8px;">No week-to-date data to chart.</div>`;
    } else {
      const labels = hourShortLabels();
      const values = computed.week_site_hourly_avg || new Array(24).fill(0);

      new frappe.Chart("#pe_week_hourly_chart", {
        title: "",
        data: { labels, datasets: [{ name: "Site avg / hr (per excavator)", values, chartType: "line" }] },
        type: "axis-mixed",
        height: 280,
        lineOptions: { dotSize: 2, regionFill: 0 },
      });
    }
  }

  const elB = document.getElementById("pe_week_excavator_daily_chart");
  if (elB) {
    if (!computed.excavator_labels.length || !computed.days_with_data) {
      elB.innerHTML = `<div class="text-muted" style="padding:8px;">No week data to chart.</div>`;
    } else {
      const dayDatasets = computed.week_excavator_daily_matrix.map((dayObj) => ({
        name: dayObj.day_label,
        values: dayObj.values,
        chartType: "bar",
      }));

      const thresholdLine = {
        name: "Threshold",
        values: new Array(computed.excavator_labels.length).fill(PE_THRESHOLD),
        chartType: "line",
      };

      new frappe.Chart("#pe_week_excavator_daily_chart", {
        title: "",
        data: {
          labels: computed.excavator_labels,
          datasets: [...dayDatasets, thresholdLine],
        },
        type: "axis-mixed",
        height: 300,
        barOptions: { stacked: false, spaceRatio: 0.7 },
        lineOptions: { dotSize: 0, regionFill: 0 },
      });

      style_threshold_line("#pe_week_excavator_daily_chart", DAILY_THRESHOLD_COLOR, DAILY_THRESHOLD_DASH);
    }
  }

  const elC = document.getElementById("pe_wtd_excavator_chart");
  if (elC) {
    if (!computed.excavator_labels.length || !computed.days_with_data) {
      elC.innerHTML = `<div class="text-muted" style="padding:8px;">No week-to-date data to chart.</div>`;
    } else {
      const bars = computed.wtd_excavator_rate_per_hour || new Array(computed.excavator_labels.length).fill(0);

      const thresholdLine = {
        name: "Threshold",
        values: new Array(computed.excavator_labels.length).fill(PE_THRESHOLD),
        chartType: "line",
      };

      new frappe.Chart("#pe_wtd_excavator_chart", {
        title: "",
        data: {
          labels: computed.excavator_labels,
          datasets: [
            { name: "WTD rate / hr", values: bars, chartType: "bar" },
            thresholdLine,
          ],
        },
        type: "axis-mixed",
        height: 300,
        barOptions: { stacked: false, spaceRatio: 0.7 },
        lineOptions: { dotSize: 0, regionFill: 0 },
      });

      style_threshold_line("#pe_wtd_excavator_chart", WTD_THRESHOLD_COLOR, WTD_THRESHOLD_DASH);
    }
  }
}

function style_threshold_line(containerSelector, strokeHex, dashArray) {
  setTimeout(() => {
    try {
      const root = document.querySelector(containerSelector);
      if (!root) return;

      const svgs = root.querySelectorAll("svg");
      if (!svgs.length) return;

      svgs.forEach((svg) => {
        const paths = Array.from(svg.querySelectorAll("path"));
        if (!paths.length) return;

        const lineish = paths.filter((p) => {
          const sw = parseFloat(p.getAttribute("stroke-width") || "0");
          const fill = p.getAttribute("fill");
          return sw >= 2 && (!fill || fill === "none");
        });

        if (lineish.length) {
          const p = lineish[lineish.length - 1];
          p.setAttribute("stroke", strokeHex);
          if (dashArray) p.setAttribute("stroke-dasharray", dashArray);
        }
      });
    } catch (e) {
      console.warn("Threshold styling failed:", e);
    }
  }, 0);
}

function compute_metrics_from_doc(frm) {
  const days = [
    { field: "monday", label: "Monday", map: get_field_map_for_day("monday") },
    { field: "tuesday", label: "Tuesday", map: get_field_map_for_day("tuesday") },
    { field: "wednesday", label: "Wednesday", map: get_field_map_for_day("wednesday") },
    { field: "thursday", label: "Thursday", map: get_field_map_for_day("thursday") },
    { field: "friday", label: "Friday", map: get_field_map_for_day("friday") },
    { field: "saturday", label: "Saturday", map: get_field_map_for_day("saturday") },
    { field: "sunday", label: "Sunday", map: get_field_map_for_day("sunday") },
  ];

  const daySummaries = [];
  const allExcavatorsSet = new Set();

  const wtd_total_bcm = {};
  const wtd_days_present = {};

  for (const d of days) {
    const rows = (frm.doc[d.field] || []).map((r) => ({ ...r }));
    if (!rows.length) continue;

    const hourKeys = d.map.map((x) => x.key);

    const grouped = {};
    for (const r of rows) {
      let ex = r.excavators;
      ex = (ex == null ? "" : String(ex)).trim();
      if (!ex) ex = "(No excavator)";
      if (!grouped[ex]) grouped[ex] = [];
      grouped[ex].push(r);
      allExcavatorsSet.add(ex);
    }

    const excavatorNames = Object.keys(grouped).sort((a, b) => a.localeCompare(b));
    const excavatorCount = excavatorNames.length || 1;

    const totalsByHour = new Array(24).fill(0);
    const excavatorDailyAvgs = [];
    const excavatorDailyTotals = [];

    for (const ex of excavatorNames) {
      let total = 0;
      for (let i = 0; i < 24; i++) {
        const k = hourKeys[i];
        const v = grouped[ex].reduce((acc, r) => acc + asNumber(r[k]), 0);
        total += v;
        totalsByHour[i] += v;
      }

      excavatorDailyTotals.push(total);

      // Graph divisor requested: 18
      excavatorDailyAvgs.push(total / GRAPH_HOURS_PER_DAY);

      wtd_total_bcm[ex] = (wtd_total_bcm[ex] || 0) + total;
      wtd_days_present[ex] = (wtd_days_present[ex] || 0) + 1;
    }

    const siteTotal = totalsByHour.reduce((a, b) => a + b, 0);
    const siteHourlyAvg = totalsByHour.map((v) => v / excavatorCount);

    // Graph divisor requested: 18
    const siteDailyAvg = siteTotal / (excavatorCount * GRAPH_HOURS_PER_DAY);

    daySummaries.push({
      label: d.label,
      field: d.field,
      excavator_count: excavatorCount,
      excavator_names: excavatorNames,
      excavator_daily_avgs: excavatorDailyAvgs,
      excavator_daily_totals: excavatorDailyTotals,
      daily_site_total: siteTotal,
      daily_site_hourly_avg: siteHourlyAvg,
      daily_site_avg: siteDailyAvg,
    });
  }

  const focus_day = daySummaries.length ? daySummaries[daySummaries.length - 1] : null;
  const days_with_data = daySummaries.length;

  let week_site_hourly_avg = new Array(24).fill(0);
  let week_site_avg = 0;

  if (days_with_data) {
    for (let i = 0; i < 24; i++) {
      week_site_hourly_avg[i] = avg(daySummaries.map((d) => d.daily_site_hourly_avg[i] || 0));
    }
    week_site_avg = avg(daySummaries.map((d) => d.daily_site_avg || 0));
  }

  const excavator_labels_all = Array.from(allExcavatorsSet)
    .map((x) => (x == null ? "" : String(x)).trim())
    .filter((x) => !!x)
    .sort((a, b) => a.localeCompare(b));

  // Key fix: only show excavators that have real WTD BCM (>0) to prevent label suppression in prod
  const excavator_labels = excavator_labels_all.filter((ex) => asNumber(wtd_total_bcm[ex] || 0) > 0);

  const week_excavator_daily_matrix = daySummaries.map((d) => {
    const map = {};
    for (let i = 0; i < d.excavator_names.length; i++) {
      map[d.excavator_names[i]] = d.excavator_daily_avgs[i];
    }
    return {
      day_label: d.label,
      values: excavator_labels.map((ex) => asNumber(map[ex] || 0)),
    };
  });

  const wtd_excavator_rate_per_hour = excavator_labels.map((ex) => {
    const total = asNumber(wtd_total_bcm[ex] || 0);
    const daysPresent = asNumber(wtd_days_present[ex] || 0);
    const hours = daysPresent > 0 ? daysPresent * GRAPH_HOURS_PER_DAY : 0;
    return hours > 0 ? total / hours : 0;
  });

  return {
    focus_day,
    days_with_data,
    week_site_hourly_avg,
    week_site_avg,
    excavator_labels,
    week_excavator_daily_matrix,
    wtd_excavator_rate_per_hour,
  };
}

function hourShortLabels() {
  const startHours = [];
  for (let h = 6; h <= 23; h++) startHours.push(h);
  for (let h = 0; h <= 5; h++) startHours.push(h);
  return startHours.map((h) => to12hNumber(h));
}

function to12hNumber(h) {
  const n = (h % 12) === 0 ? 12 : (h % 12);
  return String(n);
}

function get_field_map_for_day(day) {
  const short = hourShortLabels();
  const display = [
    { label: short[0], norm: "06_07" },
    { label: short[1], norm: "07_08" },
    { label: short[2], norm: "08_09" },
    { label: short[3], norm: "09_10" },
    { label: short[4], norm: "10_11" },
    { label: short[5], norm: "11_12" },
    { label: short[6], norm: "12_13" },
    { label: short[7], norm: "13_14" },
    { label: short[8], norm: "14_15" },
    { label: short[9], norm: "15_16" },
    { label: short[10], norm: "16_17" },
    { label: short[11], norm: "17_18" },
    { label: short[12], norm: "18_19" },
    { label: short[13], norm: "19_20" },
    { label: short[14], norm: "20_21" },
    { label: short[15], norm: "21_22" },
    { label: short[16], norm: "22_23" },
    { label: short[17], norm: "23_00" },
    { label: short[18], norm: "00_01" },
    { label: short[19], norm: "01_02" },
    { label: short[20], norm: "02_03" },
    { label: short[21], norm: "03_04" },
    { label: short[22], norm: "04_05" },
    { label: short[23], norm: "05_06" },
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

/* -------------------- HOURLY REPORT (UNCHANGED) -------------------- */

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
    .pe-day-head { padding: 8px 10px; background: #f9fafb; border-bottom:1px solid #e5e7eb; display:flex; justify-content:space-between; align-items:center; gap: 10px; flex-wrap: wrap; }
    .pe-day-head b { font-size: 13px; }
    .pe-badge { padding: 2px 8px; border-radius: 999px; font-size: 11px; background: #eef2ff; color:#3730a3; }

    .pe-scroll { overflow-x: auto; overflow-y: hidden; max-width: 100%; }
    .pe-scroll::-webkit-scrollbar { height: 0px; }
    .pe-scroll { scrollbar-width: none; }

    .pe-table { border-collapse: collapse; table-layout: fixed; width: max(100%, 1200px); }

    .pe-table th, .pe-table td {
      border-bottom: 1px solid #f1f5f9;
      padding: 4px 4px;
      font-size: 11px;
      font-weight: 500;
      text-align: right;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .pe-table thead th { background: #f8fafc; font-weight: 700; font-size: 11px; }

    .pe-table th:first-child, .pe-table td:first-child {
      text-align: left;
      position: sticky; left: 0;
      background: inherit;
      z-index: 1;
      min-width: 120px;
      max-width: 160px;
      font-weight: 700;
    }

    .pe-table th:not(:first-child):not(:last-child),
    .pe-table td:not(:first-child):not(:last-child) {
      width: 34px;
      max-width: 34px;
    }

    .pe-table th:last-child, .pe-table td:last-child { min-width: 70px; font-weight: 700; }
    .pe-table .pe-avgcol { min-width: 70px; font-weight: 700; }
    .pe-table tfoot td { background: #fafafa; font-weight: 800; }

    .pe-red    { background: #fee2e2; color: #991b1b; font-weight: 800; }
    .pe-yellow { background: #fef9c3; color: #92400e; font-weight: 800; }
    .pe-green  { background: #dcfce7; color: #065f46; font-weight: 800; }
    .pe-zero   { background: #ffffff; color: inherit; font-weight: 500; }

    .pe-empty { padding: 10px 12px; color: #6b7280; }

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

  out += render_child_table_summaries(frm);
  out += `</div>`;
  return out;
}

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
  const excavatorAvgs = {};

  for (const ex of excavatorNames) {
    let exTotal = 0;
    for (const k of hourKeys) {
      const sum = grouped[ex].reduce((acc, r) => acc + asNumber(r[k]), 0);
      exTotal += sum;
      totalsByHour[k] += sum;
    }
    excavatorTotals[ex] = exTotal;
    excavatorAvgs[ex] = exTotal / REPORT_HOURS_PER_DAY;
  }

  const dayGrandTotal = hourKeys.reduce((acc, k) => acc + totalsByHour[k], 0);
  const exCount = excavatorNames.length || 1;
  const siteAvg = dayGrandTotal / (exCount * REPORT_HOURS_PER_DAY);

  let html = `
    <div class="pe-day">
      <div class="pe-day-head">
        <b>${escape_html(dayLabel)}</b>
        <span class="pe-badge">${rows.length} row${rows.length === 1 ? "" : "s"} · Site avg/hr: <b>${formatNumber(siteAvg)}</b></span>
      </div>
      <div class="pe-scroll">
        <table class="pe-table">
          <thead>
            <tr>
              <th>Excavator</th>
              ${hourLabels.map((l) => `<th title="${escape_html(l)}">${escape_html(l)}</th>`).join("")}
              <th class="pe-avgcol">Avg/hr</th>
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

    const avgHr = excavatorAvgs[ex];
    html += `<td class="${cellClass(avgHr)} pe-avgcol"><b>${formatNumber(avgHr)}</b></td>`;
    html += `<td><b>${formatNumberOrBlank(excavatorTotals[ex])}</b></td></tr>`;
  }

  html += `
          </tbody>
          <tfoot>
            <tr>
              <td><b>Site avg/hr</b></td>
              ${hourKeys
                .map((k) => {
                  const v = totalsByHour[k] / exCount;
                  const cls = cellClass(v);
                  return `<td class="${cls}">${formatNumber(v)}</td>`;
                })
                .join("")}
              <td class="${cellClass(siteAvg)} pe-avgcol"><b>${formatNumber(siteAvg)}</b></td>
              <td><b>${formatNumberOrBlank(dayGrandTotal)}</b></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  `;

  return html;
}

function render_child_table_summaries(frm) {
  const comments = frm.doc.comment || [];
  const improvements = frm.doc.improvementrecommendation || [];

  return `
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
}

function render_generic_child_table(frm, child_doctype, rows) {
  if (!rows || !rows.length) return `<div class="pe-empty">No rows.</div>`;

  const meta = frappe.get_meta(child_doctype);
  if (!meta) return `<div class="pe-empty">Could not load meta for ${escape_html(child_doctype)}.</div>`;

  const cols = (meta.fields || []).filter((df) => {
    if (!df.fieldname) return false;
    if (df.hidden) return false;
    if (["Section Break", "Column Break", "Tab Break", "HTML", "Button"].includes(df.fieldtype)) return false;
    if (
      ["parent", "parenttype", "parentfield", "idx", "doctype", "name", "owner", "creation", "modified", "modified_by"].includes(
        df.fieldname
      )
    )
      return false;
    return true;
  });

  if (!cols.length) return `<div class="pe-empty">No displayable columns found.</div>`;

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

function cellClass(value) {
  const v = asNumber(value);
  if (v <= 0) return "pe-zero";
  if (v >= PE_THRESHOLD) return "pe-green";
  if (v >= PE_WARN) return "pe-yellow";
  return "pe-red";
}

function kpiTone(v) {
  const n = asNumber(v);
  if (n >= PE_THRESHOLD) return "green";
  if (n >= PE_WARN) return "orange";
  if (n > 0) return "red";
  return "neutral";
}

function asNumber(v) {
  const n = flt(v);
  return isNaN(n) ? 0 : n;
}

function formatNumberOrBlank(v) {
  const n = asNumber(v);
  if (n <= 0) return "";
  return formatNumber(n);
}

function formatNumber(v) {
  const n = asNumber(v);
  if (!n) return "0";
  return String(Math.round(n));
}

function formatKpiNumber(v) {
  const n = asNumber(v);
  if (!n) return "0";
  return (Math.round(n * 10) / 10).toString();
}

function avg(arr) {
  if (!arr || !arr.length) return 0;
  const s = arr.reduce((a, b) => a + (isFinite(b) ? b : 0), 0);
  return s / arr.length;
}

function escape_html(s) {
  return frappe.utils.escape_html(s == null ? "" : String(s));
}
