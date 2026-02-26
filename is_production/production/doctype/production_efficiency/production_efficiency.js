// is_production/production/doctype/production_efficiency/production_efficiency.js





frappe.ui.form.on("Production Efficiency", {
  refresh(frm) {


    if (!frm.__pe_rt_hooked) {
      frm.__pe_rt_hooked = true;

      frappe.realtime.on("production_efficiency_update_done", async (data) => {
        if (!data || data.docname !== frm.doc.name) return;

        if (data.error) {
          frappe.msgprint({ title: "Run failed", indicator: "red", message: data.error });
          return;
        }

        frappe.show_alert({ message: "Updated ✅", indicator: "green" });

        await frm.reload_doc();
        frm.trigger("render_graph");
        frm.trigger("render_hourly_report");
        frm.trigger("render_au_graph");
        frm.trigger("render_au_report");
      });
    }




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
            "is_production.production.doctype.production_efficiency.production_efficiency.enqueue_run_update",
          args: { docname: frm.doc.name },
          freeze: true,
          freeze_message: "Updating Production Efficiency…",
        });

        frappe.show_alert({ message: "Update queued…", indicator: "blue" });

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
    frm.trigger("render_au_graph");
    frm.trigger("render_au_report");

  },

  start_date(frm) {
    frm.trigger("render_graph");
    frm.trigger("render_hourly_report");
    frm.trigger("render_au_graph");
    frm.trigger("render_au_report");
  },
  end_date(frm) {
    frm.trigger("render_graph");
    frm.trigger("render_hourly_report");
  },


  // A&U fields should re-render A&U report/graph when edited
  site_b(frm) {
    frm.trigger("render_au_graph");
    frm.trigger("render_au_report");
  },
  start_date_b(frm) {
    frm.trigger("render_au_graph");
    frm.trigger("render_au_report");
  },
  end_date_b(frm) {
    frm.trigger("render_au_graph");
    frm.trigger("render_au_report");
  },
  availability_b(frm) {
    frm.trigger("render_au_graph");
    frm.trigger("render_au_report");
  },
  utilisation_b(frm) {
    frm.trigger("render_au_graph");
    frm.trigger("render_au_report");
  },
  table_comments_b(frm) {
    frm.trigger("render_au_report");
  },
  table_improvements_b(frm) {
    frm.trigger("render_au_report");
  },


  site(frm) {
    frm.trigger("render_graph");
    frm.trigger("render_hourly_report");
  },

  production_excavators(frm) {
    frm.trigger("render_graph");
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

  async render_graph(frm) {
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
      const computed = compute_metrics_from_doc(frm);

      computed.production_excavators = trunc0(asNumber(frm.doc.production_excavators || 0));
      computed.hourly_target = trunc0(computed.production_excavators * PE_THRESHOLD);

      const html = build_graph_html(frm, computed);
      targetField.$wrapper.html(html);

      render_graph_charts(frm, computed);
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

  async render_au_report(frm) {
    // A&U report field (last tab)
    if (!frm.fields_dict.html_report_b) return;

    if (frm.is_new()) {
      frm.fields_dict.html_report_b.$wrapper.html(
        `<div class="text-muted" style="padding:10px;">Save the document to generate the A&amp;U report.</div>`
      );
      return;
    }

    try {
      const computed = compute_au_from_doc(frm);
      const html = build_au_report_html(frm, computed);
      frm.fields_dict.html_report_b.$wrapper.html(html);

      render_au_per_asset_tables(frm);

      // IMPORTANT: charts must be rendered AFTER the HTML is in the DOM
      render_au_graph_charts(computed);
        await render_wearcheck_latest_statuses(frm, {
        el3_id: "wc_report_status_3",
        el4_id: "wc_report_status_4",
      });
    } catch (e) {
      console.error(e);
      frm.fields_dict.html_report_b.$wrapper.html(
        `<div class="text-danger" style="padding:10px;">
          Failed to render A&amp;U report.<br>
          <pre style="white-space:pre-wrap;">${frappe.utils.escape_html(
            e?.stack || e?.message || String(e)
          )}</pre>
        </div>`
      );
    }
  },

  render_au_graph(frm) {
    // Graph B (A&U): Per-asset graphs (fleet on X-axis)
    if (!frm.fields_dict.html_graph_b) return;

    if (frm.is_new()) {
      frm.fields_dict.html_graph_b.$wrapper.html(
        `<div class="text-muted" style="padding:10px;">Save the document to generate the A&amp;U per-asset graphs.</div>`
      );
      return;
    }

    try {
      const html = build_au_graph_b_html(frm);
      frm.fields_dict.html_graph_b.$wrapper.html(html);

      // charts after HTML is inserted
      render_au_graph_b_charts(frm);
    } catch (e) {
      console.error(e);
      frm.fields_dict.html_graph_b.$wrapper.html(
        `<div class="text-danger" style="padding:10px;">
          Failed to render Graph B (A&amp;U).<br>
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

const GRAPH_HOURS_PER_DAY = 18;
const REPORT_HOURS_PER_DAY = 24;

const FORCE_Y_AXIS_ZERO = true;
const EXTRA_CHART_HEIGHT = 50;

const FLOOR_DATASET_NAME = "Floor";
const FLOOR_HEX = "rgba(0,0,0,0)";

function build_graph_html(frm, computed) {
  const site = escape_html(frm.doc.site || "");
  const start = escape_html(frm.doc.start_date || "");
  const end = escape_html(frm.doc.end_date || "");

  const hourlyTarget = trunc0(computed.hourly_target || 0);

  const achievedTone = compareTone(computed.week_site_hourly_achieved ?? 0, hourlyTarget);

  const kpis = [
    { label: "Threshold", value: PE_THRESHOLD, tone: "neutral", sub: "BCM/hr target" },
    {
      label: "Hourly Target",
      value: hourlyTarget,
      tone: "neutral",
      sub: computed.production_excavators
        ? `${computed.production_excavators} excavators (Production Efficiency)`
        : "Set Production Excavators",
    },
    {
      label: "Hourly Achieved",
      value: computed.week_site_hourly_achieved ?? 0,
      tone: achievedTone,
      sub: computed.days_with_data ? `Across ${computed.days_with_data} day(s)` : "No week data",
    },
    {
      label: "Week site avg / hr",
      value: computed.week_site_avg ?? 0,
      tone: kpiTone(computed.week_site_avg),
      sub: computed.days_with_data ? `Across ${computed.days_with_data} day(s)` : "No week data",
    },
    {
      label: "Latest day site avg / hr",
      value: computed.focus_day?.daily_site_avg_display ?? 0,
      tone: kpiTone(computed.focus_day?.daily_site_avg_display),
      sub: computed.focus_day ? `${computed.focus_day.excavator_count} excavators` : "No daily data",
    },
  ];

  return `
  <style>
    .pe-dash { padding: 10px; }
    .pe-dash-head { display:flex; justify-content:space-between; align-items:flex-end; gap:12px; flex-wrap:wrap; margin-bottom:10px; }
    .pe-dash-head h3 { margin:0; }
    .pe-dash-meta { color:#6b7280; font-size:12px; }

    .pe-kpis { display:grid; grid-template-columns: repeat(5, minmax(160px, 1fr)); gap:10px; margin: 10px 0 14px; }
    @media (max-width: 1400px) { .pe-kpis { grid-template-columns: repeat(3, minmax(160px, 1fr)); } }
    @media (max-width: 900px) { .pe-kpis { grid-template-columns: repeat(2, minmax(160px, 1fr)); } }

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

    .pe-panel-b .chart-container { padding-bottom: 14px; }
  </style>

  <div class="pe-dash">
    <div class="pe-dash-head">
      <h3>Production Efficiency Dashboard</h3>
      <div class="pe-dash-meta">${site} · ${start} → ${end}</div>
    </div>

    <div class="pe-kpis">
      ${kpis
        .map(
          (k) => `
        <div class="pe-kpi pe-tone-${escape_html(k.tone)}">
          <div class="lbl">${escape_html(k.label)}</div>
          <div class="val">${escape_html(formatNumber0(k.value))}</div>
          <div class="sub">${escape_html(k.sub || "")}</div>
        </div>
      `
        )
        .join("")}
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
            Line shows the <b>average of the site total BCM/hr</b> for each hour (sum of all excavators per day, averaged across days).
            The threshold line is the <b>Hourly Target</b>.
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

function render_graph_charts(frm, computed) {
  // A) Week hourly chart
  const elA = document.getElementById("pe_week_hourly_chart");
  if (elA) {
    if (!computed.days_with_data) {
      elA.innerHTML = `<div class="text-muted" style="padding:8px;">No week-to-date data to chart.</div>`;
    } else {
      const labels = hourRangeLabels();
      const values = computed.week_site_hourly_total_avg || new Array(24).fill(0);

      const hourlyTarget = trunc0(computed.hourly_target || 0);
      const targetLine = {
        name: "Hourly Target",
        values: new Array(labels.length).fill(hourlyTarget),
        chartType: "line",
      };

      let datasets = [{ name: "Site total avg / hr", values, chartType: "line" }, targetLine];
      if (FORCE_Y_AXIS_ZERO) datasets = add_floor_dataset(labels, datasets);

      new frappe.Chart("#pe_week_hourly_chart", {
        title: "",
        data: { labels, datasets },
        type: "axis-mixed",
        height: 280 + EXTRA_CHART_HEIGHT,
        axisOptions: { xAxisMode: "tick", yAxisMode: "span" },
        lineOptions: { dotSize: 2, regionFill: 0 },
        colors: [FLOOR_HEX, "#3b82f6", "#22c55e"],
      });

      if (FORCE_Y_AXIS_ZERO) {
        style_floor_line("#pe_week_hourly_chart");
        strip_floor_legend("#pe_week_hourly_chart");
        strip_floor_tooltip("#pe_week_hourly_chart");
      }
      style_last_line("#pe_week_hourly_chart", "#22c55e", "4 0");
    }
  }

  // B) Week excavator daily chart
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

      let datasets = [...dayDatasets, thresholdLine];
      if (FORCE_Y_AXIS_ZERO) datasets = add_floor_dataset(computed.excavator_labels, datasets);

      new frappe.Chart("#pe_week_excavator_daily_chart", {
        title: "",
        data: { labels: computed.excavator_labels, datasets },
        type: "axis-mixed",
        height: 300 + EXTRA_CHART_HEIGHT,
        axisOptions: { xAxisMode: "tick", yAxisMode: "span" },
        barOptions: { stacked: false, spaceRatio: 0.6 },
        lineOptions: { dotSize: 0, regionFill: 0 },
      });

      style_threshold_line("#pe_week_excavator_daily_chart", DAILY_THRESHOLD_COLOR, DAILY_THRESHOLD_DASH);

      if (FORCE_Y_AXIS_ZERO) {
        style_floor_line("#pe_week_excavator_daily_chart");
        strip_floor_legend("#pe_week_excavator_daily_chart");
        strip_floor_tooltip("#pe_week_excavator_daily_chart");
      }
    }
  }

  // C) WTD excavator chart
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

      let datasets = [{ name: "WTD rate / hr", values: bars, chartType: "bar" }, thresholdLine];
      if (FORCE_Y_AXIS_ZERO) datasets = add_floor_dataset(computed.excavator_labels, datasets);

      new frappe.Chart("#pe_wtd_excavator_chart", {
        title: "",
        data: { labels: computed.excavator_labels, datasets },
        type: "axis-mixed",
        height: 300 + EXTRA_CHART_HEIGHT,
        axisOptions: { xAxisMode: "tick", yAxisMode: "span" },
        barOptions: { stacked: false, spaceRatio: 0.55 },
        lineOptions: { dotSize: 0, regionFill: 0 },
      });

      style_threshold_line("#pe_wtd_excavator_chart", WTD_THRESHOLD_COLOR, WTD_THRESHOLD_DASH);

      if (FORCE_Y_AXIS_ZERO) {
        style_floor_line("#pe_wtd_excavator_chart");
        strip_floor_legend("#pe_wtd_excavator_chart");
        strip_floor_tooltip("#pe_wtd_excavator_chart");
      }
    }
  }
}

/* ---------- Floor dataset ---------- */

function add_floor_dataset(labels, datasets) {
  const floor = {
    name: FLOOR_DATASET_NAME,
    values: new Array(labels.length).fill(0),
    chartType: "line",
  };
  return [floor, ...datasets];
}

function strip_floor_legend(containerSelector) {
  setTimeout(() => {
    try {
      const root = document.querySelector(containerSelector);
      if (!root) return;
      const legend = root.querySelector(".chart-legend");
      if (!legend) return;

      const items = Array.from(legend.querySelectorAll("*"));
      for (const el of items) {
        const t = (el.textContent || "").trim();
        if (t === FLOOR_DATASET_NAME) {
          const li = el.closest("li") || el.closest(".legend-item") || el;
          li.remove();
        }
      }
    } catch (e) {}
  }, 0);
}

function strip_floor_tooltip(containerSelector) {
  // removes the floor line row inside tooltip if it renders (best-effort, safe no-op)
  setTimeout(() => {
    try {
      const root = document.querySelector(containerSelector);
      if (!root) return;

      // observe tooltip re-renders
      const obs = new MutationObserver(() => {
        try {
          const tips = document.querySelectorAll(".graph-svg-tip");
          tips.forEach((tip) => {
            const rows = Array.from(tip.querySelectorAll("li, .dot, span, div"));
            rows.forEach((r) => {
              const txt = (r.textContent || "").trim();
              if (txt === FLOOR_DATASET_NAME) {
                const li = r.closest("li") || r.parentElement;
                if (li) li.remove();
              }
            });
          });
        } catch (e) {}
      });

      obs.observe(root, { subtree: true, childList: true });
      setTimeout(() => obs.disconnect(), 1500);
    } catch (e) {}
  }, 0);
}

function style_floor_line(containerSelector) {
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
          // first line-ish corresponds to floor because we insert it first
          const p = lineish[0];
          p.setAttribute("stroke", "transparent");
          p.setAttribute("stroke-opacity", "0");
          p.setAttribute("stroke-width", "0");
        }
      });
    } catch (e) {}
  }, 0);
}

function style_last_line(containerSelector, strokeHex, dashArray) {
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
    } catch (e) {}
  }, 0);
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

/* -------------------- METRICS (ALL INTS) -------------------- */

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

      excavatorDailyTotals.push(trunc0(total));
      excavatorDailyAvgs.push(trunc0(total / GRAPH_HOURS_PER_DAY));

      wtd_total_bcm[ex] = (wtd_total_bcm[ex] || 0) + total;
      wtd_days_present[ex] = (wtd_days_present[ex] || 0) + 1;
    }

    const siteTotal = totalsByHour.reduce((a, b) => a + b, 0);
    const siteHourlyTotal = totalsByHour.map((v) => trunc0(v));

    const siteDailyAvg18 = trunc0(siteTotal / (excavatorCount * GRAPH_HOURS_PER_DAY));
    const dailyHourlyAchieved = trunc0(siteTotal / GRAPH_HOURS_PER_DAY);

    // ONLY for the "Latest day site avg / hr" KPI display:
    const divisorForDisplay = d.field === "sunday" ? 14 : 18;
    const siteDailyAvgDisplay = trunc0(siteTotal / (excavatorCount * divisorForDisplay));

    daySummaries.push({
      label: d.label,
      field: d.field,
      excavator_count: excavatorCount,
      excavator_names: excavatorNames,
      excavator_daily_avgs: excavatorDailyAvgs,
      excavator_daily_totals: excavatorDailyTotals,
      daily_site_total: trunc0(siteTotal),
      daily_site_hourly_total: siteHourlyTotal,
      daily_site_avg: siteDailyAvg18,
      daily_site_avg_display: siteDailyAvgDisplay,
      daily_hourly_achieved: dailyHourlyAchieved,
    });
  }

  const focus_day = daySummaries.length ? daySummaries[daySummaries.length - 1] : null;
  const days_with_data = daySummaries.length;

  let week_site_hourly_total_avg = new Array(24).fill(0);
  let week_site_avg = 0;
  let week_site_hourly_achieved = 0;

  if (days_with_data) {
    for (let i = 0; i < 24; i++) {
      week_site_hourly_total_avg[i] = trunc0(avg(daySummaries.map((d) => d.daily_site_hourly_total[i] || 0)));
    }
    week_site_avg = trunc0(avg(daySummaries.map((d) => d.daily_site_avg || 0)));
    week_site_hourly_achieved = trunc0(avg(daySummaries.map((d) => d.daily_hourly_achieved || 0)));
  }

  const excavator_labels_all = Array.from(allExcavatorsSet)
    .map((x) => (x == null ? "" : String(x)).trim())
    .filter((x) => !!x)
    .sort((a, b) => a.localeCompare(b));

  const excavator_labels = excavator_labels_all.filter((ex) => asNumber(wtd_total_bcm[ex] || 0) > 0);

  const week_excavator_daily_matrix = daySummaries.map((d) => {
    const map = {};
    for (let i = 0; i < d.excavator_names.length; i++) {
      map[d.excavator_names[i]] = d.excavator_daily_avgs[i];
    }
    return {
      day_label: d.label,
      values: excavator_labels.map((ex) => trunc0(asNumber(map[ex] || 0))),
    };
  });

  const wtd_excavator_rate_per_hour = excavator_labels.map((ex) => {
    const total = asNumber(wtd_total_bcm[ex] || 0);
    const daysPresent = asNumber(wtd_days_present[ex] || 0);
    const hours = daysPresent > 0 ? daysPresent * GRAPH_HOURS_PER_DAY : 0;
    return trunc0(hours > 0 ? total / hours : 0);
  });

  return {
    focus_day,
    days_with_data,
    week_site_hourly_total_avg,
    week_site_avg,
    week_site_hourly_achieved,
    excavator_labels,
    week_excavator_daily_matrix,
    wtd_excavator_rate_per_hour,
  };
}

/* -------------------- Hour labels -------------------- */

function hourRangeLabels() {
  const starts = [];
  for (let h = 6; h <= 23; h++) starts.push(h);
  for (let h = 0; h <= 5; h++) starts.push(h);

  return starts.map((h) => {
    const next = (h + 1) % 24;
    const a = String(h);
    const b = next === 0 ? "00" : String(next);
    return `${a}-${b}`;
  });
}

function get_field_map_for_day(day) {
  const labels = hourRangeLabels();
  const display = [
    { label: labels[0], norm: "06_07" },
    { label: labels[1], norm: "07_08" },
    { label: labels[2], norm: "08_09" },
    { label: labels[3], norm: "09_10" },
    { label: labels[4], norm: "10_11" },
    { label: labels[5], norm: "11_12" },
    { label: labels[6], norm: "12_13" },
    { label: labels[7], norm: "13_14" },
    { label: labels[8], norm: "14_15" },
    { label: labels[9], norm: "15_16" },
    { label: labels[10], norm: "16_17" },
    { label: labels[11], norm: "17_18" },
    { label: labels[12], norm: "18_19" },
    { label: labels[13], norm: "19_20" },
    { label: labels[14], norm: "20_21" },
    { label: labels[15], norm: "21_22" },
    { label: labels[16], norm: "22_23" },
    { label: labels[17], norm: "23-00", norm_key: "23_00" },
    { label: labels[18], norm: "00_01" },
    { label: labels[19], norm: "01_02" },
    { label: labels[20], norm: "02_03" },
    { label: labels[21], norm: "03_04" },
    { label: labels[22], norm: "04_05" },
    { label: labels[23], norm: "05_06" },
  ].map((d) => ({ label: d.label, norm: d.norm_key || d.norm }));

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

/* -------------------- HOURLY REPORT -------------------- */

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

    .pe-scroll { overflow-x: auto; overflow-y: hidden; max-width: 100%; padding-bottom: 6px; }
    .pe-scroll::-webkit-scrollbar { height: 10px; }
    .pe-scroll::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 999px; }
    .pe-scroll::-webkit-scrollbar-track { background: #f1f5f9; border-radius: 999px; }

    .pe-table { border-collapse: collapse; table-layout: fixed; width: max(100%, 1400px); }

    .pe-table th, .pe-table td {
      border-bottom: 1px solid #f1f5f9;
      padding: 6px 6px;
      font-size: 11px;
      font-weight: 600;
      text-align: right;
      white-space: nowrap;
      overflow: visible;
      text-overflow: clip;
    }

    .pe-table thead th { background: #f8fafc; font-weight: 800; font-size: 11px; }

    .pe-table th:first-child, .pe-table td:first-child {
      text-align: left;
      position: sticky; left: 0;
      background: inherit;
      z-index: 1;
      min-width: 140px;
      max-width: 220px;
      font-weight: 800;
    }

    .pe-table th:not(:first-child):not(:last-child),
    .pe-table td:not(:first-child):not(:last-child) {
      width: 44px;
      max-width: 44px;
    }

    .pe-table th:last-child, .pe-table td:last-child { min-width: 90px; font-weight: 800; }
    .pe-table .pe-avgcol { min-width: 90px; font-weight: 800; }
    .pe-table tfoot td { background: #fafafa; font-weight: 900; }

    .pe-red    { background: #fee2e2; color: #991b1b; font-weight: 900; }
    .pe-yellow { background: #fef9c3; color: #92400e; font-weight: 900; }
    .pe-green  { background: #dcfce7; color: #065f46; font-weight: 900; }
    .pe-zero   { background: #ffffff; color: inherit; font-weight: 600; }

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
    excavatorTotals[ex] = trunc0(exTotal);
    excavatorAvgs[ex] = trunc0(exTotal / REPORT_HOURS_PER_DAY);
  }

  const dayGrandTotal = trunc0(hourKeys.reduce((acc, k) => acc + totalsByHour[k], 0));
  const exCount = excavatorNames.length || 1;
  const siteAvg = trunc0(dayGrandTotal / (exCount * REPORT_HOURS_PER_DAY));

  let html = `
    <div class="pe-day">
      <div class="pe-day-head">
        <b>${escape_html(dayLabel)}</b>
        <span class="pe-badge">${rows.length} row${rows.length === 1 ? "" : "s"} · Site avg/hr: <b>${formatNumber0(siteAvg)}</b></span>
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
      const v = trunc0(grouped[ex].reduce((acc, r) => acc + asNumber(r[k]), 0));
      const cls = cellClass(v);
      html += `<td class="${cls}">${formatNumberOrBlank0(v)}</td>`;
    }

    const avgHr = excavatorAvgs[ex];
    html += `<td class="${cellClass(avgHr)} pe-avgcol"><b>${formatNumber0(avgHr)}</b></td>`;
    html += `<td><b>${formatNumberOrBlank0(excavatorTotals[ex])}</b></td></tr>`;
  }

  html += `
          </tbody>
          <tfoot>
            <tr>
              <td><b>Site avg/hr</b></td>
              ${hourKeys
                .map((k) => {
                  const v = trunc0(totalsByHour[k] / exCount);
                  const cls = cellClass(v);
                  return `<td class="${cls}">${formatNumber0(v)}</td>`;
                })
                .join("")}
              <td class="${cellClass(siteAvg)} pe-avgcol"><b>${formatNumber0(siteAvg)}</b></td>
              <td><b>${formatNumberOrBlank0(dayGrandTotal)}</b></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  `;

  return html;
}

/* -------------------- child summaries unchanged -------------------- */

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


function render_generic_child_table_with_view_btn(frm, child_doctype, rows) {
  if (!rows || !rows.length) return `<div class="pe-empty">No rows.</div>`;

  const meta = frappe.get_meta(child_doctype);
  if (!meta) return `<div class="pe-empty">Could not load meta for ${escape_html(child_doctype)}.</div>`;

  // show normal columns, but replace long-text cells with a View button popup (same as WearCheck)
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

  const isLongText = (df) =>
    ["Text", "Small Text", "Long Text", "Text Editor", "Code"].includes(df.fieldtype);

  const head = cols.map((c) => `<th>${escape_html(c.label || c.fieldname)}</th>`).join("");

  const body = rows
    .map((r) => {
      const tds = cols
        .map((c) => {
          const raw = r[c.fieldname];

          if (isLongText(c)) {
            const v = raw == null ? "" : String(raw);
            return `<td>${pe_wc_view_btn(c.label || c.fieldname, v)}</td>`;
          }

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
    return escape_html(String(trunc0(n)));
  }

  return escape_html(String(raw));
}


function render_generic_child_table_precise(frm, child_doctype, rows) {
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
          let val = format_child_value_precise(raw, c);

          // Bold Date + Weekday columns (match screenshot)
          const lbl = (c.label || c.fieldname || "").toLowerCase();
          const fn = (c.fieldname || "").toLowerCase();
          const isDateCol = c.fieldtype === "Date" || lbl.includes("date") || fn.includes("date");
          const isWeekdayCol = lbl.includes("weekday") || fn.includes("weekday");

          if (isDateCol || isWeekdayCol) {
            val = `<b>${val}</b>`;
          }
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

function format_child_value_precise(raw, df) {
  if (raw == null || raw === "") return "";

  if (df.fieldtype === "Link") return escape_html(String(raw));
  if (df.fieldtype === "Date") return escape_html(frappe.datetime.str_to_user(raw));
  if (df.fieldtype === "Datetime") return escape_html(frappe.datetime.str_to_user(raw));

  if (df.fieldtype === "Int") {
    const n = flt(raw);
    if (isNaN(n)) return escape_html(String(raw));
    return escape_html(String(Math.trunc(n)));
  }

  if (["Float", "Currency", "Percent"].includes(df.fieldtype)) {
    const n = flt(raw);
    if (isNaN(n)) return escape_html(String(raw));

    const precRaw = parseInt(df.precision, 10);
    const prec = Number.isFinite(precRaw) ? precRaw : df.fieldtype === "Percent" ? 1 : 2;

    const f = Math.pow(10, prec);
    const r = Math.round(n * f) / f;

    return escape_html(df.fieldtype === "Percent" ? `${r}%` : String(r));
  }

  return escape_html(String(raw));
}

function render_generic_child_table_precise_threshold(frm, child_doctype, rows, threshold) {
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

  const catClassFor = (c) => {
    const lbl = (c.label || c.fieldname || "").toLowerCase();
    const fn = (c.fieldname || "").toLowerCase();

    // catch common fieldnames/labels for your A&U day tables
    if (lbl.includes("adt") || fn.includes("adt")) return "peau-th-adt";
    if (lbl.includes("excav") || fn.includes("excav")) return "peau-th-exc";
    if (lbl.includes("dozer") || fn.includes("dozer")) return "peau-th-doz";
    return "";
  };

  const head = cols
    .map((c) => {
      const cc = catClassFor(c);
      return `<th class="${cc}">${escape_html(c.label || c.fieldname)}</th>`;
    })
    .join("");

  const body = rows
    .map((r) => {
      const tds = cols
        .map((c) => {
          const raw = r[c.fieldname];
          let val = format_child_value_precise(raw, c);

          // Bold Date + Weekday columns (match screenshot)
          const lbl = (c.label || c.fieldname || "").toLowerCase();
          const fn = (c.fieldname || "").toLowerCase();
          const isDateCol = c.fieldtype === "Date" || lbl.includes("date") || fn.includes("date");
          const isWeekdayCol = lbl.includes("weekday") || fn.includes("weekday");

          if (isDateCol || isWeekdayCol) {
            val = `<b>${val}</b>`;
          }

          const catCls = catClassFor(c);

          // Highlight ONLY % columns
          let cls = catCls || "";
          if (c.fieldtype === "Percent" || c.fieldtype === "Float") {
            const n = flt(raw);
            if (!isNaN(n)) cls = `${cls} ${n >= threshold ? "peau-cell-good" : "peau-cell-bad"}`.trim();
          }

          return `<td class="${cls}">${val}</td>`;
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


/* -------------------- formatting / helpers -------------------- */

function trunc0(v) {
  const n = asNumber(v);
  return Math.floor(n);
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

function compareTone(actual, target) {
  const a = asNumber(actual);
  const t = asNumber(target);
  if (!t) return kpiTone(a);
  return a >= t ? "green" : "red";
}

function asNumber(v) {
  const n = flt(v);
  return isNaN(n) ? 0 : n;
}

function formatNumberOrBlank0(v) {
  const n = trunc0(v);
  if (n <= 0) return "";
  return String(n);
}

function formatNumber0(v) {
  const n = trunc0(v);
  return String(n);
}

function avg(arr) {
  if (!arr || !arr.length) return 0;
  const s = arr.reduce((a, b) => a + (isFinite(b) ? b : 0), 0);
  return s / arr.length;
}

function escape_html(s) {
  return frappe.utils.escape_html(s == null ? "" : String(s));
}


// -------------------- WearCheck popup (View buttons) --------------------

function pe_wc_ensure_popup_css() {
  if (document.getElementById("pe_wc_popup_css")) return;

  const css = document.createElement("style");
  css.id = "pe_wc_popup_css";
  css.textContent = `
    /* hide default dialog header, we render our own */
    .pe-wc-pop .modal-header { display: none !important; }

    .pe-wc-pop .modal-content {
      border-radius: 14px !important;
      overflow: hidden !important;
      border: 0 !important;
    }

    .pe-wc-popcard { background: #fff; }
    .pe-wc-pophead{
      background: #4f46e5; /* matches your screenshot */
      color: #fff;
      padding: 10px 14px;
      display:flex;
      align-items:center;
      justify-content:space-between;
      font-weight: 800;
    }
    .pe-wc-pophead .pe-wc-x{
      cursor:pointer;
      font-size: 18px;
      line-height: 1;
      opacity: .95;
      padding: 0 6px;
    }
    .pe-wc-popbody{ padding: 14px; }
    .pe-wc-chip{
      display:inline-block;
      padding: 6px 10px;
      border-radius: 12px;
      background: #f8fafc;
      font-weight: 800;
      margin-bottom: 10px;
    }
    .pe-wc-text{ color:#0f172a; }
    .pe-wc-popfoot{ padding: 12px 14px; display:flex; justify-content:flex-end; }

    .pe-wc-view.btn.btn-xs {
      padding: 2px 10px;
      border-radius: 999px;
      font-weight: 700;
    }
    
     /* flagged X-axis labels */
    .pe-wc-flag { fill: #b91c1c !important; font-weight: 900 !important; }
    .pe-wc-flag tspan { fill: #b91c1c !important; font-weight: 900 !important; }
  `;
  document.head.appendChild(css);
}

function pe_wc_open_popup(title, body_text) {
  pe_wc_ensure_popup_css();

  const d = new frappe.ui.Dialog({
    title: "",
    fields: [{ fieldtype: "HTML", fieldname: "body" }],
    size: "large",
  });

  d.$wrapper.addClass("pe-wc-pop");

  const esc = frappe.utils.escape_html;
  const raw = (body_text || "").trim();
  const txt = esc(raw || "No text.").replace(/\n/g, "<br>");

  d.fields_dict.body.$wrapper.html(`
    <div class="pe-wc-popcard">
      <div class="pe-wc-pophead">
        <div>${esc(title || "Details")}</div>
        <div class="pe-wc-x" role="button" tabindex="0">×</div>
      </div>
      <div class="pe-wc-popbody">
        <div class="pe-wc-chip">${esc(title || "Details")}</div>
        <div class="pe-wc-text">${txt}</div>
      </div>
      <div class="pe-wc-popfoot">
        <button class="btn btn-primary btn-sm pe-wc-close">Close</button>
      </div>
    </div>
  `);

  d.$wrapper.find(".pe-wc-close, .pe-wc-x").on("click", () => d.hide());
  d.show();
}

function pe_wc_open_popup_html(title, html_body) {
  pe_wc_ensure_popup_css();

  const d = new frappe.ui.Dialog({
    title: "",
    fields: [{ fieldtype: "HTML", fieldname: "body" }],
    size: "large",
  });

  d.$wrapper.addClass("pe-wc-pop");

  const esc = frappe.utils.escape_html;

  d.fields_dict.body.$wrapper.html(`
    <div class="pe-wc-popcard">
      <div class="pe-wc-pophead">
        <div>${esc(title || "Details")}</div>
        <div class="pe-wc-x" role="button" tabindex="0">×</div>
      </div>
      <div class="pe-wc-popbody">
        ${html_body || ""}
      </div>
      <div class="pe-wc-popfoot">
        <button class="btn btn-primary btn-sm pe-wc-close">Close</button>
      </div>
    </div>
  `);

  d.$wrapper.find(".pe-wc-close, .pe-wc-x").on("click", () => d.hide());
  d.show();
}

function pe_wc_view_btn(label, value) {
  const v = (value || "").trim();
  if (!v) return "";
  const esc = frappe.utils.escape_html;
  // put value in data-attr safely (escaped)
  return `<button class="btn btn-default btn-xs pe-wc-view" data-label="${esc(label)}" data-value="${esc(v)}">View</button>`;
}

function pe_wc_flag_assets_on_charts(flaggedSet) {
  try {
    if (!flaggedSet || !flaggedSet.size) return;

    const norm = (s) => (s == null ? "" : String(s)).replace(/\s+/g, "").trim().toUpperCase();

    const FORCE_COLOR = "#b91c1c";

    const apply_to_root = (root) => {
      if (!root) return;
      const svg = root.querySelector("svg");
      if (!svg) return;

      // Frappe charts sometimes don't tag x-axis text with helpful classes.
      // So: scan ALL text nodes, but keep it bounded.
      const nodes = Array.from(svg.querySelectorAll("text")).slice(0, 450);

      for (const node of nodes) {
        const txt = norm(node.textContent);
        if (!txt) continue;
        if (!flaggedSet.has(txt)) continue;

        // Force via inline style (wins vs re-renders better than class only)
        node.classList.add("pe-wc-flag");
        node.setAttribute("fill", FORCE_COLOR);
        node.style.fill = FORCE_COLOR;
        node.style.fontWeight = "900";

        const tspans = node.querySelectorAll ? node.querySelectorAll("tspan") : [];
        tspans.forEach((ts) => {
          ts.classList.add("pe-wc-flag");
          ts.setAttribute("fill", FORCE_COLOR);
          ts.style.fill = FORCE_COLOR;
          ts.style.fontWeight = "900";
        });
      }
    };

    const apply_all = () => {
      for (const cat of (typeof AU_CATS !== "undefined" ? AU_CATS : [])) {
        apply_to_root(document.querySelector(`#au_b_chart_${cat}`));
      }
    };

    // Apply several times because charts paint in stages
    setTimeout(apply_all, 0);
    setTimeout(apply_all, 200);
    setTimeout(apply_all, 600);
    setTimeout(apply_all, 1200);
  } catch (e) {}
}

// Bind once (event delegation) - WearCheck View buttons
if (!window.__pe_wc_view_bound) {
  window.__pe_wc_view_bound = true;
  document.addEventListener("click", (ev) => {
    const btn = ev.target && ev.target.closest ? ev.target.closest(".pe-wc-view") : null;
    if (!btn) return;
    ev.preventDefault();

    const label = btn.getAttribute("data-label") || "Details";
    const value = btn.getAttribute("data-value") || "";
    pe_wc_open_popup(label, value);
  });
}


function pe_au_pick_person_name(rows) {
  if (!rows || !rows.length) return "";
  const r = rows[0] || {};
  const keys = Object.keys(r || {});

  // never use the child row ID field "name"
  const banned = new Set([
    "name",
    "doctype",
    "parent",
    "parenttype",
    "parentfield",
    "owner",
    "creation",
    "modified",
    "modified_by",
    "idx",
  ]);

  // Prefer any key that contains "name" but is not the banned "name"
  const nameKey =
    keys
      .filter((k) => {
        if (banned.has(k)) return false;
        const kk = String(k).toLowerCase();
        if (!kk.includes("name")) return false;
        const v = r[k];
        return typeof v === "string" && String(v).trim().length > 0;
      })
      .sort((a, b) => a.length - b.length)[0] || "";

  if (nameKey) return String(r[nameKey] || "").trim();

  // fallback: first string containing a space (looks like a full name)
  for (const k of keys) {
    if (banned.has(k)) continue;
    const v = r[k];
    if (typeof v === "string" && v.trim().includes(" ")) return v.trim();
  }

  return "";
}

function pe_au_build_notes_popup_html(title, rows) {
  const esc = frappe.utils.escape_html;

  if (!rows || !rows.length) {
    return `<div class="pe-wc-text">No rows.</div>`;
  }

  const pickText = (r) => {
    if (!r) return "";
    const k = Object.keys(r || {})
      .filter((x) => typeof r[x] === "string" && String(r[x]).trim().length)
      .sort((a, b) => String(r[b] || "").length - String(r[a] || "").length)[0];
    return k ? String(r[k] || "").trim() : "";
  };

  const txt = rows.map(pickText).filter(Boolean).join("\n\n");

  // ONLY the comment text
  return `<div class="pe-wc-text" style="white-space:pre-wrap;">${esc(txt || "—")}</div>`;
}

// Bind once for A&U note popups (Comments / Improvements)
if (!window.__pe_au_notes_bound) {
  window.__pe_au_notes_bound = true;

  document.addEventListener("click", (ev) => {
    const btn = ev.target && ev.target.closest ? ev.target.closest("[data-au-popup]") : null;
    if (!btn) return;

    ev.preventDefault();
    ev.stopPropagation();

    const key = btn.getAttribute("data-au-popup");
    const frm = window.cur_frm;
    if (!frm || !frm.doc) return;

    if (key === "comments") {
      const rows = frm.doc.table_comments_b || [];
      const html = pe_au_build_notes_popup_html("Comments on Past 7 Days", rows);
      pe_wc_open_popup_html("Comments on Past 7 Days", html);
      return;
    }

    if (key === "improvements") {
      const rows = frm.doc.table_improvements_b || [];
      const html = pe_au_build_notes_popup_html("Improvement for Next 7 Days", rows);
      pe_wc_open_popup_html("Improvement for Next 7 Days", html);
      return;
    }
  });
}

/* ==================== A&U REPORT + GRAPH (ADD ONLY) ==================== */

const AU_CATS = ["ADT", "Excavator", "Dozer"];
const AU_AVAIL_COLOR = "#f59e0b"; // orange
const AU_UTIL_COLOR = "#6b7280";  // grey


const AU_FORCE_MIN = 0;
const AU_FORCE_MAX = 100;
const AU_INVIS_HEX = "rgba(0,0,0,0)"; // invisible dataset (scale only)

// targets
const AU_TARGET_AVAIL = 85;
const AU_TARGET_UTIL = 80;
const AU_TARGET_LINE_HEX = "#9ca3af"; // grey like screenshot

function build_au_graph_b_html(frm) {
  const AU_B_HEAD_BG = {
  ADT: "linear-gradient(90deg, #0f766e 0%, #14b8a6 55%, #99f6e4 100%)",          // teal
  Excavator: "linear-gradient(90deg, #1d4ed8 0%, #3b82f6 55%, #93c5fd 100%)",     // blue
  Dozer: "linear-gradient(90deg, #9a3412 0%, #fb923c 55%, #fde68a 100%)",         // amber
  DEFAULT: "linear-gradient(90deg, #0f172a 0%, #1e293b 55%, #334155 100%)",
};
  const site = escape_html(frm.doc.site_b || frm.doc.site || "");
  const start = escape_html(frm.doc.start_date_b || "");
  const end = escape_html(frm.doc.end_date_b || "");

  return `
    <style>
      .aub-wrap { padding: 12px; }
      .aub-head { display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; align-items:flex-end; margin-bottom:10px; }
      .aub-meta { color:#6b7280; font-size:12px; }

      .aub-block { border:1px solid #e2e8f0; border-radius:12px; background:#fff; overflow:hidden; margin-bottom:12px; }
      .aub-h { padding:10px 12px; background:#0f172a; color:#fff; display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap; }
      .aub-h b { font-size:14px; }
      .aub-note { color: rgba(255,255,255,0.85); font-size:12px; }
      /* WearCheck block: red header */
      .aub-h-wc { background:#b91c1c; }            /* red */
      .aub-h-wc b { color:#fff; }

      .aub-b { padding:10px 12px; }
      .aub-chart { min-height: 320px; }
      .aub-legend { margin-top:8px; font-size:12px; color:#6b7280; display:flex; gap:12px; flex-wrap:wrap; }
      .aub-pill { display:inline-flex; align-items:center; gap:8px; padding:4px 10px; border:1px solid #e2e8f0; border-radius:999px; background:#fff; }
      .aub-dot { width:10px; height:10px; border-radius:999px; display:inline-block; }
      .aub-dot-av { background:${AU_AVAIL_COLOR}; }
      .aub-dot-ut { background:${AU_UTIL_COLOR}; }
      .pe-scroll { overflow-x: auto; overflow-y: hidden; max-width: 100%; padding-bottom: 6px; }
      .pe-scroll::-webkit-scrollbar { height: 10px; }
      .pe-scroll::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 999px; }
      .pe-scroll::-webkit-scrollbar-track { background: #f1f5f9; border-radius: 999px; }
      /* WearCheck columns: red shades */
      .wc-col { border-radius: 12px; padding: 10px; }
      .wc-col-3 { background: #fee2e2; }  /* light red */
      .wc-col-4 { background: #fca5a5; color: #111827; } /* darker red (lighter than before) */
      .wc-col-4 h4 { color: #7f1d1d; }
      .wc-col-4 .text-muted { color: rgba(255,255,255,0.85) !important; }
      .wc-col table { background: transparent !important; }
      .wc-col-4 table { color: #0f172a; } /* keep table text readable if any renders */
    </style>

    <div class="aub-wrap">
      <div class="aub-head">
        <h3 style="margin:0;">Graph B (A&amp;U) — Per Asset</h3>
        <div class="aub-meta">${site} · ${start || "—"} → ${end || "—"}</div>
      </div>

      ${AU_CATS.map((cat) => `
        <div class="aub-block">
          <div class="aub-h" style="background:${AU_B_HEAD_BG[cat] || AU_B_HEAD_BG.DEFAULT};">
            <b>${escape_html(cat)}</b>
          </div>
          <div class="aub-b">
            <div id="au_b_chart_${escape_html(cat)}" class="aub-chart"></div>
            <div class="aub-legend">
              <span class="aub-pill"><span class="aub-dot aub-dot-av"></span>Availability %</span>
              <span class="aub-pill"><span class="aub-dot aub-dot-ut"></span>Utilisation %</span>
            </div>
          </div>
        </div>
      `).join("")}



    </div>
  `;
}

async function render_au_graph_b_charts(frm) {
  const aRows = (frm.doc.per_asset_availability || []).map((r) => ({ ...r }));
  const uRows = (frm.doc.per_asset_utilisation || []).map((r) => ({ ...r }));

  const start = frm.doc.start_date_b || null;
  const end = frm.doc.end_date_b || null;

  const inRange = (d) => {
    if (!d) return true;
    if (start && d < start) return false;
    if (end && d > end) return false;
    return true;
  };

  const aFilt = aRows.filter((r) => inRange(r.date_));
  const uFilt = uRows.filter((r) => inRange(r.date_d));

  const assets = Array.from(
    new Set([
      ...aFilt.map((r) => (r.assets_c == null ? "" : String(r.assets_c)).trim()).filter(Boolean),
      ...uFilt.map((r) => (r.assets_c == null ? "" : String(r.assets_c)).trim()).filter(Boolean),
    ])
  );

  if (!assets.length) {
    for (const cat of AU_CATS) {
      const el = document.getElementById(`au_b_chart_${cat}`);
      if (el) el.innerHTML = `<div class="text-muted" style="padding:8px;">No per-asset rows to chart.</div>`;
    }
    return;
  }

  const assetMeta = await frappe.call({
    method: "frappe.client.get_list",
    args: {
      doctype: "Asset",
      fields: ["name", "asset_category"],
      filters: [["name", "in", assets]],
      limit_page_length: assets.length,
    },
  });

  const rows = (assetMeta && assetMeta.message) ? assetMeta.message : [];
  const catByAsset = {};
  for (const r of rows) {
    const n = (r.name == null ? "" : String(r.name)).trim();
    const c = (r.asset_category == null ? "" : String(r.asset_category)).trim();
    if (n) catByAsset[n] = c;
  }

  const bucketCat = (assetCategory) => {
    const s = (assetCategory || "").toLowerCase();
    if (s.includes("adt")) return "ADT";
    if (s.includes("excav")) return "Excavator";
    if (s.includes("dozer")) return "Dozer";
    return null;
  };

  const avgFrom = (vals) => (vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0);

  const availByAsset = {};
  const utilByAsset = {};

  for (const a of assets) {
    const aVals = [];
    const uVals = [];

    const days = new Set([
      ...aFilt.filter((r) => String(r.assets_c || "").trim() === a).map((r) => r.date_),
      ...uFilt.filter((r) => String(r.assets_c || "").trim() === a).map((r) => r.date_d),
    ]);

    for (const d of Array.from(days).filter(Boolean).sort()) {
      const ar = aFilt.find((r) => String(r.assets_c || "").trim() === a && r.date_ === d);
      const ur = uFilt.find((r) => String(r.assets_c || "").trim() === a && r.date_d === d);

      const av = trunc2(asNumber(ar ? ar.availability_c : 0));
      const ut = trunc2(asNumber(ur ? ur.utilasazation_c : 0));

      if (av <= 0 && ut <= 0) continue;

      aVals.push(av);
      uVals.push(ut);
    }

    availByAsset[a] = trunc2(avgFrom(aVals));
    utilByAsset[a] = trunc2(avgFrom(uVals));
  }

  for (const cat of AU_CATS) {
    const el = document.getElementById(`au_b_chart_${cat}`);
    if (!el) continue;

    const items = assets
      .map((a) => ({ a, bucket: bucketCat(catByAsset[a] || "") }))
      .filter((x) => x.bucket === cat)
      .map((x) => x.a)
      .sort((a, b) => a.localeCompare(b));

    if (!items.length) {
      el.innerHTML = `<div class="text-muted" style="padding:8px;">No ${escape_html(cat)} assets found in per-asset rows.</div>`;
      continue;
    }

    const labels = items;
    const availVals = items.map((a) => availByAsset[a] || 0);
    const utilVals = items.map((a) => utilByAsset[a] || 0);

    const floorLabel = "__floor__";
    const ceilLabel = "__ceil__";
    const target85Label = "__target_85__";
    const target80Label = "__target_80__";

    // Invisible min/max datasets to force 0–100 scale
    const datasets = [
      { name: floorLabel, values: new Array(labels.length).fill(AU_FORCE_MIN), chartType: "line" },
      { name: ceilLabel, values: new Array(labels.length).fill(AU_FORCE_MAX), chartType: "line" },

      { name: "Availability %", values: availVals, chartType: "bar" },
      { name: "Utilisation %", values: utilVals, chartType: "bar" },

      // visible target lines (grey), but we will strip legend + tooltip
      { name: target85Label, values: new Array(labels.length).fill(AU_TARGET_AVAIL), chartType: "line" },
      { name: target80Label, values: new Array(labels.length).fill(AU_TARGET_UTIL), chartType: "line" },
    ];

    new frappe.Chart(`#au_b_chart_${cat}`, {
      title: "",
      data: { labels, datasets },
      type: "axis-mixed",
      height: 320,
      axisOptions: { xAxisMode: "tick", yAxisMode: "span" },
      barOptions: { stacked: false, spaceRatio: 0.55 },
      lineOptions: { dotSize: 0, regionFill: 0 },
      colors: [
        AU_INVIS_HEX,           // floor (invisible)
        AU_INVIS_HEX,           // ceil (invisible)
        AU_AVAIL_COLOR,         // Availability bars
        AU_UTIL_COLOR,          // Utilisation bars
        AU_AVAIL_COLOR,         // 85% target = orange (Availability)
        AU_TARGET_LINE_HEX,     // 80% target = grey
      ],
    });

    // Graph B: we use our own pills legend, so remove the chart legend completely
    remove_chart_legend(`#au_b_chart_${cat}`);
    setTimeout(() => remove_chart_legend(`#au_b_chart_${cat}`), 80);

    // Remove legends + tooltips for invisible scale + target lines
    strip_legend_item(`#au_b_chart_${cat}`, floorLabel);
    strip_legend_item(`#au_b_chart_${cat}`, ceilLabel);
    strip_legend_item(`#au_b_chart_${cat}`, target85Label);
    strip_legend_item(`#au_b_chart_${cat}`, target80Label);

    strip_tooltip_item(`#au_b_chart_${cat}`, floorLabel);
    strip_tooltip_item(`#au_b_chart_${cat}`, ceilLabel);
    strip_tooltip_item(`#au_b_chart_${cat}`, target85Label);
    strip_tooltip_item(`#au_b_chart_${cat}`, target80Label);

    // Add % suffix to left axis ticks
    suffix_y_axis_percent(`#au_b_chart_${cat}`);
    setTimeout(() => suffix_y_axis_percent(`#au_b_chart_${cat}`), 80);
    setTimeout(() => suffix_y_axis_percent(`#au_b_chart_${cat}`), 200);
    // Make the 2 target lines thin grey like screenshot
    style_last_n_lines(`#au_b_chart_${cat}`, 2, AU_TARGET_LINE_HEX, "3");
    setTimeout(() => style_last_n_lines(`#au_b_chart_${cat}`, 2, AU_TARGET_LINE_HEX, "3"), 120);
  }

  await render_wearcheck_latest_statuses(frm);

  // re-apply label flags after charts are fully painted
  if (window.__pe_wc_flagged_assets && window.__pe_wc_flagged_assets.size) {
    pe_wc_flag_assets_on_charts(window.__pe_wc_flagged_assets);
  }
}

async function render_au_per_asset_tables(frm) {
  const aRows = (frm.doc.per_asset_availability || []).map((r) => ({ ...r }));
  const uRows = (frm.doc.per_asset_utilisation || []).map((r) => ({ ...r }));

  const start = frm.doc.start_date_b || null;
  const end = frm.doc.end_date_b || null;

  const inRange = (d) => {
    if (!d) return true;
    if (start && d < start) return false;
    if (end && d > end) return false;
    return true;
  };

  const aFilt = aRows.filter((r) => inRange(r.date_));
  const uFilt = uRows.filter((r) => inRange(r.date_d));

  const assets = Array.from(
    new Set([
      ...aFilt.map((r) => (r.assets_c == null ? "" : String(r.assets_c)).trim()).filter(Boolean),
      ...uFilt.map((r) => (r.assets_c == null ? "" : String(r.assets_c)).trim()).filter(Boolean),
    ])
  );

  const setSlot = (id, html) => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
  };

  const emptyBox = (msg) =>
    `<div class="peau-report"><div class="pe-empty">${escape_html(msg)}</div></div>`;

  if (!assets.length) {
    for (const cat of AU_CATS) {
      setSlot(`au_per_asset_av_${cat}`, emptyBox("No per-asset rows."));
      setSlot(`au_per_asset_ut_${cat}`, emptyBox("No per-asset rows."));
    }
    return;
  }

  const assetMeta = await frappe.call({
    method: "frappe.client.get_list",
    args: {
      doctype: "Asset",
      fields: ["name", "asset_category"],
      filters: [["name", "in", assets]],
      limit_page_length: assets.length,
    },
  });

  const rows = assetMeta && assetMeta.message ? assetMeta.message : [];
  const catByAsset = {};
  for (const r of rows) {
    const n = (r.name == null ? "" : String(r.name)).trim();
    const c = (r.asset_category == null ? "" : String(r.asset_category)).trim();
    if (n) catByAsset[n] = c;
  }

  const bucketCat = (assetCategory) => {
    const s = (assetCategory || "").toLowerCase();
    if (s.includes("adt")) return "ADT";
    if (s.includes("excav")) return "Excavator";
    if (s.includes("dozer")) return "Dozer";
    return null;
  };

  const avgFrom = (vals) => (vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0);

  const availByAsset = {};
  const utilByAsset = {};

  for (const a of assets) {
    const aVals = [];
    const uVals = [];

    const days = new Set([
      ...aFilt.filter((r) => String(r.assets_c || "").trim() === a).map((r) => r.date_),
      ...uFilt.filter((r) => String(r.assets_c || "").trim() === a).map((r) => r.date_d),
    ]);

    for (const d of Array.from(days).filter(Boolean).sort()) {
      const ar = aFilt.find((r) => String(r.assets_c || "").trim() === a && r.date_ === d);
      const ur = uFilt.find((r) => String(r.assets_c || "").trim() === a && r.date_d === d);

      const av = trunc2(asNumber(ar ? ar.availability_c : 0));
      const ut = trunc2(asNumber(ur ? ur.utilasazation_c : 0));

      if (av <= 0 && ut <= 0) continue;

      aVals.push(av);
      uVals.push(ut);
    }

    availByAsset[a] = trunc2(avgFrom(aVals));
    utilByAsset[a] = trunc2(avgFrom(uVals));
  }

  const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

  const buildWeekdayMatrix = (rows, valueField) => {
    // returns: { [asset]: { [weekday]: avgValue } }
    const buckets = {}; // asset -> weekday -> {sum,count}

    for (const r of (rows || [])) {
      const asset = (r.assets_c == null ? "" : String(r.assets_c)).trim();
      const wd = (r.weekdays_c == null ? "" : String(r.weekdays_c)).trim();
      if (!asset || !wd) continue;

      const v = trunc2(asNumber(r[valueField] || 0));
      if (!buckets[asset]) buckets[asset] = {};
      if (!buckets[asset][wd]) buckets[asset][wd] = { sum: 0, count: 0 };

      // keep zeros too (so we can show 0% in red)
      buckets[asset][wd].sum += v;
      buckets[asset][wd].count += 1;
    }

    const out = {};
    for (const asset of Object.keys(buckets)) {
      out[asset] = {};
      for (const wd of Object.keys(buckets[asset])) {
        const b = buckets[asset][wd];
        out[asset][wd] = trunc2(b.count ? b.sum / b.count : 0);
      }
    }
    return out;
  };

  const renderWeekdayTable = (items, rows, valueField, threshold) => {
    if (!items.length) return `<div class="pe-empty">No assets found.</div>`;

    const matrix = buildWeekdayMatrix(rows, valueField);

    return `
      <div class="pe-scroll">
        <table class="pe-mini" style="table-layout:fixed;">
          <thead>
            <tr>
              <th style="min-width:140px;">Asset</th>
              ${WEEKDAYS.map((d) => `<th style="min-width:90px; text-align:center;">${escape_html(d.slice(0, 3))}</th>`).join("")}
            </tr>
          </thead>
          <tbody>
            ${items.map((a) => {
              const row = matrix[a] || {};
              return `
                <tr>
                  <td><b>${escape_html(a)}</b></td>
                  ${WEEKDAYS.map((wd) => {
                    const v = asNumber(row[wd] ?? 0);
                    const show = formatPercent1(v);
                    const cls = (v >= threshold) ? "peau-cell-good" : "peau-cell-bad";
                    return `<td class="${cls}" style="text-align:center;">${escape_html(show)}</td>`;
                  }).join("")}
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
    `;
  };

  for (const cat of AU_CATS) {
    const items = assets
      .map((a) => ({ a, bucket: bucketCat(catByAsset[a] || "") }))
      .filter((x) => x.bucket === cat)
      .map((x) => x.a)
      .sort((a, b) => a.localeCompare(b));

    const aCatRows = aFilt.filter((r) => bucketCat(catByAsset[String(r.assets_c || "").trim()] || "") === cat);
    const uCatRows = uFilt.filter((r) => bucketCat(catByAsset[String(r.assets_c || "").trim()] || "") === cat);

    setSlot(`au_per_asset_av_${cat}`, renderWeekdayTable(items, aCatRows, "availability_c", AU_TARGET_AVAIL));
    setSlot(`au_per_asset_ut_${cat}`, renderWeekdayTable(items, uCatRows, "utilasazation_c", AU_TARGET_UTIL));
  }
}

function strip_legend_item(containerSelector, labelToRemove) {
  // Removes legend items even when Frappe truncates text to "Availability Ta..."
  const want = (labelToRemove || "").trim();
  if (!want) return;

  const run = () => {
    try {
      const root = document.querySelector(containerSelector);
      if (!root) return;
      const legend = root.querySelector(".chart-legend");
      if (!legend) return;

      const items = Array.from(legend.querySelectorAll("*"));
      for (const el of items) {
        const t = (el.textContent || "").trim();
        if (!t) continue;

        // exact or prefix match (handles truncation)
        if (t === want || want.startsWith(t) || t.startsWith(want)) {
          const li = el.closest("li") || el.closest(".legend-item") || el;
          li.remove();
        }
      }
    } catch (e) {}
  };

  // run twice (legend often renders after a tick)
  setTimeout(run, 0);
  setTimeout(run, 80);
}


function strip_tooltip_item(containerSelector, labelToRemove) {
  const want = (labelToRemove || "").trim();
  if (!want) return;

  setTimeout(() => {
    try {
      const root = document.querySelector(containerSelector);
      if (!root) return;

      const obs = new MutationObserver(() => {
        try {
          const tips = document.querySelectorAll(".graph-svg-tip");
          tips.forEach((tip) => {
            const nodes = Array.from(tip.querySelectorAll("*"));
            nodes.forEach((n) => {
              const t = (n.textContent || "").trim();
              if (!t) return;

              if (t === want || want.startsWith(t) || t.startsWith(want)) {
                const row = n.closest("li") || n.closest(".tooltip-row") || n.parentElement;
                if (row) row.remove();
              }
            });
          });
        } catch (e) {}
      });

      obs.observe(root, { subtree: true, childList: true });
      setTimeout(() => obs.disconnect(), 1500);
    } catch (e) {}
  }, 0);
}

function suffix_y_axis_percent(containerSelector) {
  try {
    const root = document.querySelector(containerSelector);
    if (!root) return;

    const svg = root.querySelector("svg");
    if (!svg) return;

    const ticks = svg.querySelectorAll(".y.axis text");
    ticks.forEach((t) => {
      const s = (t.textContent || "").trim();
      if (!s) return;
      if (s.endsWith("%")) return;
      if (!isNaN(Number(s))) t.textContent = `${s}%`;
    });
  } catch (e) {}
}

function remove_chart_legend(containerSelector) {
  try {
    const root = document.querySelector(containerSelector);
    if (!root) return;

    const legend = root.querySelector(".chart-legend");
    if (legend) legend.remove();
  } catch (e) {}
}

function style_last_n_lines(containerSelector, n, strokeHex, strokeWidth) {
  setTimeout(() => {
    try {
      const root = document.querySelector(containerSelector);
      if (!root) return;

      const svg = root.querySelector("svg");
      if (!svg) return;

      const paths = Array.from(svg.querySelectorAll("path"));
      const lineish = paths.filter((p) => {
        const sw = parseFloat(p.getAttribute("stroke-width") || "0");
        const fill = p.getAttribute("fill");
        return sw >= 2 && (!fill || fill === "none");
      });

      if (!lineish.length) return;

      const take = lineish.slice(Math.max(0, lineish.length - n));
      take.forEach((p) => {
        p.setAttribute("stroke", strokeHex);
        p.setAttribute("stroke-width", String(strokeWidth || "3"));
        p.setAttribute("stroke-dasharray", ""); // solid
      });
    } catch (e) {}
  }, 0);
}


async function render_wearcheck_latest_statuses(frm, opts) {
  opts = opts || {};
  const el3 = document.getElementById(opts.el3_id || "wc_status_3");
  const el4 = document.getElementById(opts.el4_id || "wc_status_4");
  // NOTE: do NOT return if missing elements (Graph B removed); we still want chart flagging

  const site = (frm.doc.site_b || frm.doc.site || "").trim();

  const mkTable = (rows) => {
    if (!rows || !rows.length) return `<div class="text-muted" style="padding:6px 0;">No machines.</div>`;

    const esc = escape_html;

    const trunc = (s, n) => {
      s = (s == null ? "" : String(s)).trim();
      if (!s) return "";
      return s.length > n ? `${s.slice(0, n)}…` : s;
    };

    return `
      <table class="table table-bordered" style="width:100%; background:#fff;">
        <thead>
          <tr>
            <th style="width:120px;">Machine</th>
            <th style="width:110px;">Sample Date</th>
            <th style="width:140px;">Component</th>
            <th>Action</th>
            <th>Feedback</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((r) => {
            const a = (r.actiontext || "");
            const f = (r.feedbacktext || "");
            return `
              <tr>
                <td><b>${esc(r.machine || "")}</b></td>
                <td>${esc(r.sampledate ? frappe.datetime.str_to_user(r.sampledate) : "")}</td>
                <td>${esc(r.component || "")}</td>
                <td>${pe_wc_view_btn("Actions", a)}</td>
                <td>${pe_wc_view_btn("Comments", f)}</td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    `;
  };

  try {
    const resp = await frappe.call({
      method: "is_production.production.doctype.production_efficiency.production_efficiency.get_latest_wearcheck_statuses",
      args: { site: site || null },
    });

    const msg = resp && resp.message ? resp.message : {};

    if (el3) el3.innerHTML = mkTable(msg.status_3 || []);
    if (el4) el4.innerHTML = mkTable(msg.status_4 || []);

    // Always flag charts (even if this block is rendered in Report tab only)
    // Graph B labels come from Asset name (assets_c). Prefer r.asset / r.assets_c if present.
    const pick_label = (r) => {
      if (!r) return "";
      const v =
        r.asset != null ? r.asset :
        r.assets_c != null ? r.assets_c :
        r.machine != null ? r.machine :
        "";
      return String(v).replace(/\s+/g, "").trim().toUpperCase();
    };

    const flagged = new Set(
      []
        .concat(msg.status_3 || [], msg.status_4 || [])
        .map(pick_label)
        .filter(Boolean)
    );

    // keep globally so charts can re-apply after re-render
    window.__pe_wc_flagged_assets = flagged;

    // apply styling to chart x-axis labels
    pe_wc_flag_assets_on_charts(flagged);
  } catch (e) {
    console.error(e);
    const m = frappe.utils.escape_html(e?.message || String(e));
    if (el3) el3.innerHTML = `<div class="text-danger">Failed to load WearCheck: ${m}</div>`;
    if (el4) el4.innerHTML = `<div class="text-danger">Failed to load WearCheck: ${m}</div>`;
  }
}


function compute_au_from_doc(frm) {
  const availRows = (frm.doc.availability_b || []).map((r) => ({ ...r }));
  const utilRows = (frm.doc.utilisation_b || []).map((r) => ({ ...r }));

  // map date -> {ADT:x, Excavator:y, Dozer:z}
  const availByDate = {};
  const utilByDate = {};

  for (const r of availRows) {
    const d = String(r.date_b || "");
    if (!d) continue;
    availByDate[d] = {
      ADT: asNumber(r.adt_b),
      Excavator: asNumber(r.excavator_b),
      Dozer: asNumber(r.dozer_b),
    };
  }

  for (const r of utilRows) {
    const d = String(r.date_b_b || "");
    if (!d) continue;
    utilByDate[d] = {
      ADT: asNumber(r.adt_b_b),
      Excavator: asNumber(r.excavator_b_b),
      Dozer: asNumber(r.dozer_b_b),
    };
  }

  // dates = union (chronological)
  const dates = Array.from(new Set([...Object.keys(availByDate), ...Object.keys(utilByDate)])).sort();

  // per category datasets (ONLY keep points that appear on graph):
  // - if (avail==0 && util==0) => drop the date entirely (not plotted, not averaged)
  // - if one has value and the other is missing => keep date; missing side stays 0
  const byCat = {};
  for (const cat of AU_CATS) {
    const labels = [];
    const keptDates = [];
    const availability = [];
    const utilisation = [];

    for (const d of dates) {
      const a = trunc2((availByDate[d] || {})[cat] ?? 0);
      const u = trunc2((utilByDate[d] || {})[cat] ?? 0);

      if (a <= 0 && u <= 0) continue;

      keptDates.push(d);
      labels.push(d.slice(-2)); // day of month like dashboard
      availability.push(a);
      utilisation.push(u);
    }

    byCat[cat] = {
      labels,
      dates: keptDates,
      availability,
      utilisation,
    };
  }

  // KPIs (averages only across kept/plotted points)
  const kpis = {};
  for (const cat of AU_CATS) {
    const a = byCat[cat].availability;
    const u = byCat[cat].utilisation;
    kpis[cat] = {
      avail_avg: trunc1(avg(a)),
      util_avg: trunc1(avg(u)),
    };
  }

  return { dates, byCat, kpis };
}

function build_au_report_html(frm, computed) {
  const site = escape_html(frm.doc.site_b || frm.doc.site || "");
  const start = escape_html(frm.doc.start_date_b || "");
  const end = escape_html(frm.doc.end_date_b || "");

  const availRows = frm.doc.availability_b || [];
  const utilRows = frm.doc.utilisation_b || [];

  const commentRows = frm.doc.table_comments_b || [];
  const improveRows = frm.doc.table_improvements_b || [];

  // pick the "Name" field value from the child row (NOT the row id)
  const pick_person_name = (rows) => {
    const r = (rows && rows.length) ? rows[0] : null;
    if (!r) return "—";

    // prefer fields that look like a human name, and avoid the child-row id key "name"
    const keys = Object.keys(r || {});
    const candidates = keys
      .filter((k) => k && k.toLowerCase().includes("name") && k !== "name")
      .map((k) => ({ k, v: (r[k] == null ? "" : String(r[k])).trim() }))
      .filter((x) => x.v && x.v.length >= 3);

    // prefer values with spaces (e.g. "Sipho Simelane")
    const best =
      candidates.find((x) => x.v.includes(" ")) ||
      candidates[0];

    return best ? best.v : "—";
  };

  const commentName = pick_person_name(commentRows);
  const improveName = pick_person_name(improveRows);

  return `
    <style>
      .peau-wrap {
        padding: 16px;
        background: #f1f5f9;
      }

      .peau-report {
        border: 2px solid #cbd5e1;
        border-radius: 14px;
        background: #ffffff;
        overflow: hidden;
        box-shadow: 0 8px 22px rgba(15, 23, 42, 0.10);
      }

      .peau-head {
        padding: 14px 16px;
        background: linear-gradient(90deg, #0f172a 0%, #1e293b 55%, #334155 100%);
        color: #ffffff;
      }

      .peau-head h3 {
        margin: 0;
        font-size: 18px;
        font-weight: 900;
        letter-spacing: 0.2px;
        color: #ffffff !important;
      }

      .peau-badges {
        margin-top: 10px;
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }

      .peau-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 999px;
        border: 1px solid rgba(255, 255, 255, 0.22);
        background: rgba(255, 255, 255, 0.12);
        font-size: 12px;
        color: rgba(255, 255, 255, 0.95);
      }

      .peau-section {
        border-top: 1px solid #e2e8f0;
      }

      .peau-section-head {
        padding: 10px 16px;
        background: #f8fafc;
        border-bottom: 1px solid #e2e8f0;
      }

      .peau-section-head h4 {
        margin: 0;
        font-size: 14px;
        font-weight: 900;
        color: #0f172a;
      }

      .peau-section-body {
        padding: 12px 16px;
      }

      /* ===== Category gradients (match Graph B) ===== */
      .peau-grad-adt { background: linear-gradient(90deg, #0f766e 0%, #14b8a6 55%, #99f6e4 100%) !important; color:#fff !important; }
      .peau-grad-exc { background: linear-gradient(90deg, #1d4ed8 0%, #3b82f6 55%, #93c5fd 100%) !important; color:#fff !important; }
      .peau-grad-doz { background: linear-gradient(90deg, #9a3412 0%, #fb923c 55%, #fde68a 100%) !important; color:#fff !important; }

      /* Section heads: allow gradient */
      .peau-section-head.peau-grad-adt h4,
      .peau-section-head.peau-grad-exc h4,
      .peau-section-head.peau-grad-doz h4 { color:#fff !important; }

      /* Column header coloring (ADT/Excavator/Dozer columns) */
      .peau-report .pe-mini thead th.peau-th-adt { background: linear-gradient(90deg, #0f766e 0%, #14b8a6 55%, #99f6e4 100%) !important; color:#fff !important; }
      .peau-report .pe-mini thead th.peau-th-exc { background: linear-gradient(90deg, #1d4ed8 0%, #3b82f6 55%, #93c5fd 100%) !important; color:#fff !important; }
      .peau-report .pe-mini thead th.peau-th-doz { background: linear-gradient(90deg, #9a3412 0%, #fb923c 55%, #fde68a 100%) !important; color:#fff !important; }

      /* Per-asset subheads become gradient bars */
      .peau-subhead {
        padding: 8px 10px;
        border-radius: 10px;
        margin: 12px 0 8px;
      }

      /* Oil link button */
      .peau-oil-link{
        display:inline-flex;
        align-items:center;
        gap:6px;
        padding:4px 10px;
        border-radius:999px;
        border:1px solid rgba(255,255,255,0.35);
        background: rgba(255,255,255,0.18);
        color:#fff !important;
        font-size:12px;
        font-weight:900;
        text-decoration:none !important;
        white-space:nowrap;
      }
      .peau-oil-link:hover{ background: rgba(255,255,255,0.28); }


      .peau-kv {
        width: 100%;
        border-collapse: collapse;
      }

      .peau-kv th,
      .peau-kv td {
        border: 1px solid #e2e8f0;
        padding: 9px 10px;
        font-size: 12px;
        vertical-align: top;
      }

      /* Information (A&U): horizontal headings */
      .peau-kv-h th {
        width: auto !important;
        text-align: center;
        white-space: nowrap;
      }

      .peau-kv-h td {
        text-align: center;
        font-weight: 800;
        background: #ffffff;
      }


      .peau-kv th {
        width: 220px;
        background: #eef2ff;
        color: #0f172a;
        font-weight: 900;
      }

      .peau-grid {
        display: grid;
        grid-template-columns: 1fr;
        gap: 12px;
      }

      .peau-card {
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        overflow: hidden;
        background: #ffffff;
      }

      .peau-card-head {
        padding: 10px 12px;
        background: #f8fafc;
        border-bottom: 1px solid #e2e8f0;
      }

      .peau-card-head h4 {
        margin: 0;
        font-size: 13px;
        font-weight: 900;
        color: #0f172a;
      }

      .peau-name-pill{
        display:inline-flex;
        margin-left:8px;
        padding:2px 8px;
        border-radius:999px;
        background:#eef2ff;
        border:1px solid #e2e8f0;
        font-size:11px;
        font-weight:900;
        color:#0f172a;
        vertical-align:middle;
      }

      .peau-card-head-row{
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:10px;
      }

      /* nicer View pills */
      .peau-pillbtn{
        border:0;
        cursor:pointer;
        user-select:none;
        padding:6px 12px;
        border-radius:999px;
        font-size:12px;
        font-weight:900;
        color:#fff;
        box-shadow: 0 6px 16px rgba(15,23,42,.15);
        transform: translateY(0);
        transition: transform .08s ease, filter .12s ease;
      }
      .peau-pillbtn:hover{ filter: brightness(1.05); }
      .peau-pillbtn:active{ transform: translateY(1px); }

      .peau-pillbtn-blue,
      .peau-pillbtn-amber{
        background: linear-gradient(90deg, #0f172a 0%, #1f2937 55%, #475569 100%);
        color:#fff;
      }

      /* black pill buttons (match screenshot) */
      .peau-oil-link,
      .peau-report .pe-wc-view.btn.btn-xs {
        border: 0 !important;
        background: linear-gradient(90deg, #0f172a 0%, #1f2937 55%, #475569 100%) !important;
        color: #fff !important;
        box-shadow: 0 6px 16px rgba(15,23,42,.18);
        font-weight: 900 !important;
        border-radius: 999px !important;
        padding: 6px 12px !important;
        line-height: 1 !important;
      }

      .peau-oil-link:hover,
      .peau-report .pe-wc-view.btn.btn-xs:hover {
        filter: brightness(1.06);
      }

      .peau-oil-link:active,
      .peau-report .pe-wc-view.btn.btn-xs:active {
        transform: translateY(1px);
      }



      .peau-card-body {
        padding: 12px;
      }

      /* Scope table styling ONLY to the A&U report container */
      .peau-report .pe-scroll {
        overflow-x: auto;
        overflow-y: hidden;
        max-width: 100%;
        padding-bottom: 6px;
      }

      .peau-report .pe-scroll::-webkit-scrollbar { height: 10px; }
      .peau-report .pe-scroll::-webkit-scrollbar-thumb { background: #94a3b8; border-radius: 999px; }
      .peau-report .pe-scroll::-webkit-scrollbar-track { background: #e2e8f0; border-radius: 999px; }

      .peau-report .pe-mini {
        width: 100%;
        min-width: 720px;
        border-collapse: separate;
        border-spacing: 0;
      }

      .peau-report .pe-mini th,
      .peau-report .pe-mini td {
        border: 1px solid #e2e8f0;
        padding: 8px 10px;
        font-size: 12px;
        text-align: left;
        vertical-align: top;
      }

      .peau-report .pe-mini thead th {
        background: #e2e8f0;
        font-weight: 900;
        color: #0f172a;
        .peau-report .peau-boldcell { font-weight: 900 !important; }
      }

      /* A&U % cell highlighting (cells only, light colors) */
      .peau-report .peau-cell-good {
        background: #dcfce7 !important;
        color: #14532d !important;
        font-weight: 900;
      }

      .peau-report .peau-cell-bad {
        background: #fee2e2 !important;
        color: #7f1d1d !important;
        font-weight: 900;
      }      

      .peau-report .pe-mini tbody tr:nth-child(even) { background: #f8fafc; }
      .peau-report .pe-mini tbody tr:hover { background: #eef2ff; }


      /* WearCheck block (Report B) */
      .wc-col { border-radius: 12px; padding: 10px; }
      .wc-col-3 { background: #fee2e2; }
      .wc-col-4 { background: #fca5a5; color: #111827; }
      .wc-col-4 h4 { color: #111827 !important; }
      .wc-col-4 .text-muted { color: #111827 !important; }


      .peau-report .pe-empty {
        padding: 10px 12px;
        color: #64748b;
        font-size: 12px;
        border: 1px dashed #cbd5e1;
        border-radius: 10px;
        background: #f8fafc;
      }

      /* Notes tables: fit container, wrap text, no horizontal scrollbar */
      .peau-noscr .pe-scroll {
        overflow-x: visible !important;
        padding-bottom: 0 !important;
      }

      .peau-noscr .pe-mini {
        min-width: 0 !important;
        width: 100% !important;
        table-layout: fixed;
      }

      .peau-noscr .pe-mini th,
      .peau-noscr .pe-mini td {
        white-space: normal !important;
        overflow-wrap: anywhere;
        word-break: break-word;
      }


</style>

    <div class="peau-wrap">
      <div class="peau-report">
        <div class="peau-head">
          <h3>A&amp;U Report</h3>
        </div>

        <div class="peau-section">
          <div class="peau-section-head"><h4>Information (A&amp;U)</h4></div>
          <div class="peau-section-body">
            <table class="peau-kv peau-kv-h">
              <thead>
                <tr>
                  <th>Site</th>
                  <th>Start Date</th>
                  <th>End Date</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>${site || "—"}</td>
                  <td>${start || "—"}</td>
                  <td>${end || "—"}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="peau-section">
          <div class="peau-section-body">
            <div style="border:1px solid #e2e8f0; border-radius:12px; overflow:hidden; background:#fff;">
              <div style="background:#f87171; color:#fff; padding:10px 12px; font-weight:900; display:flex; align-items:center; justify-content:space-between; gap:10px;">
                <span>Latest Oil Sample Flagged Machines</span>
                <a
                  href="https://oilandwear.com/tribology/web/main/main.php"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="peau-oil-link"
                >Detailed Oil Report</a>
              </div>

              <div style="padding:12px;">
                <div class="pe-scroll">
                  <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; align-items:start;">
                    <div class="wc-col wc-col-3">
                      <h4 style="margin:0 0 8px 0;">Urgent</h4>
                      <div id="wc_report_status_3"></div>
                    </div>

                    <div class="wc-col wc-col-4">
                      <h4 style="margin:0 0 8px 0; color:#fff;">Critical</h4>
                      <div id="wc_report_status_4"></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="peau-section">
          <div class="peau-section-head"><h4>Availability Daily Category Average</h4></div>
          <div class="peau-section-body">
            ${render_generic_child_table_precise_threshold(frm, "Availability Day Entry 1", availRows, 85)}
          </div>
        </div>

        <div class="peau-section">
          <div class="peau-section-head"><h4>Utilisation Daily Category Average</h4></div>
          <div class="peau-section-body">
            ${render_generic_child_table_precise_threshold(frm, "Utilisation Day Entry", utilRows, 80)}
          </div>
        </div>

        <div class="peau-section">
          <div class="peau-section-body">
            <div class="peau-grid">
              <div class="peau-card">
                <div class="peau-card-head peau-card-head-row">
                <h4>
                  Comments on Past 7 Days
                  <span class="peau-name-pill">${escape_html(commentName || "—")}</span>
                </h4>
                  <button type="button" class="peau-pillbtn peau-pillbtn-blue" data-au-popup="comments">View</button>
                </div>
              </div>

              <div class="peau-card">
                <div class="peau-card-head peau-card-head-row">
                <h4>
                  Improvement for Next 7 Days
                  <span class="peau-name-pill">${escape_html(improveName || "—")}</span>
                </h4>
                  <button type="button" class="peau-pillbtn peau-pillbtn-amber" data-au-popup="improvements">View</button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="peau-section">
          <div class="peau-section-head"><h4>Category Average Graphs</h4></div>
          <div class="peau-section-body">
            <style>
              .peau-auwrap { padding: 2px 0; }
              .peau-aublock { border: 1px solid #e2e8f0; border-radius: 12px; background:#fff; overflow:hidden; margin-bottom: 12px; }
              .peau-auh { padding: 10px 12px; background:#f8fafc; border-bottom: 1px solid #e2e8f0; }
              .peau-auh b { font-size: 13px; }
              .peau-aukpis { display:flex; gap:10px; flex-wrap:wrap; margin-top:8px; }

              /* pills sit on a white background, so force dark text */
              .peau-aupill {
                display:inline-flex;
                gap:8px;
                align-items:center;
                padding:6px 10px;
                border-radius:999px;
                font-size:12px;
                background:#fff;
                border:1px solid #e2e8f0;
                color:#0f172a !important;
                font-weight: 800;
              }
              .peau-aupill b { color:#0f172a !important; }

              .peau-audot { width:10px; height:10px; border-radius:999px; display:inline-block; }
              .peau-audot-av { background:${AU_AVAIL_COLOR}; }
              .peau-audot-ut { background:${AU_UTIL_COLOR}; }

              .peau-aucharts { padding: 10px 12px; }
              .peau-auchart { min-height: 260px; }

              /* per-asset table sub headings */
              .peau-subhead {
                margin: 12px 0 8px;
                font-size: 12px;
                font-weight: 900;
                color: #0f172a;
              }
            </style>

            <div class="peau-auwrap">
              ${AU_CATS.map((cat, idx) => {
                const bgMap = {
                  ADT: "linear-gradient(90deg, #0f766e 0%, #14b8a6 55%, #99f6e4 100%)",
                  Excavator: "linear-gradient(90deg, #1d4ed8 0%, #3b82f6 55%, #93c5fd 100%)",
                  Dozer: "linear-gradient(90deg, #9a3412 0%, #fb923c 55%, #fde68a 100%)",
                };
                const bg = bgMap[cat] || "#f8fafc";
                return `
                  <div class="peau-aublock">
                    <div class="peau-auh" style="background:${bg}; color:#fff;">
                      <b>${escape_html(cat)}'s (AVG)</b>
                      <div class="peau-aukpis">
                        <span class="peau-aupill"><span class="peau-audot peau-audot-av"></span>Availability <b>${formatPercent1(computed.kpis[cat].avail_avg)}</b></span>
                        <span class="peau-aupill"><span class="peau-audot peau-audot-ut"></span>Utilisation <b>${formatPercent1(computed.kpis[cat].util_avg)}</b></span>
                      </div>
                    </div>
                    <div class="peau-aucharts">
                      <div id="au_chart_${escape_html(cat)}" class="peau-auchart"></div>
                    </div>
                  </div>
                `;
              }).join("")}
            </div>
          </div>
        </div>

        <!-- NEW: Per-asset tables at the bottom -->
        <div class="peau-section">
          <div class="peau-section-head"><h4>Asset Daily Performance (Availability)</h4></div>
          <div class="peau-section-body">
            <div class="peau-subhead peau-grad-adt">ADT</div>
            <div id="au_per_asset_av_ADT" class="peau-per-asset-slot"></div>

            <div class="peau-subhead peau-grad-doz">Dozer</div>
            <div id="au_per_asset_av_Dozer" class="peau-per-asset-slot"></div>

            <div class="peau-subhead peau-grad-exc">Excavator</div>
            <div id="au_per_asset_av_Excavator" class="peau-per-asset-slot"></div>
          </div>
        </div>

        <div class="peau-section">
          <div class="peau-section-head"><h4>Asset Daily Performance (Utilisation)</h4></div>
          <div class="peau-section-body">
            <div class="peau-subhead peau-grad-adt">ADT</div>
            <div id="au_per_asset_ut_ADT" class="peau-per-asset-slot"></div>

            <div class="peau-subhead peau-grad-doz">Dozer</div>
            <div id="au_per_asset_ut_Dozer" class="peau-per-asset-slot"></div>

            <div class="peau-subhead peau-grad-exc">Excavator</div>
            <div id="au_per_asset_ut_Excavator" class="peau-per-asset-slot"></div>
          </div>
        </div>

      </div>
    </div>
  `;
}

function build_au_graph_html(frm, computed) {
  const site = escape_html(frm.doc.site_b || frm.doc.site || "");
  const start = escape_html(frm.doc.start_date_b || "");
  const end = escape_html(frm.doc.end_date_b || "");

  const k = computed.kpis;

  return `
  <style>
    .au-wrap { padding:10px; }
    .au-head { display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; align-items:flex-end; margin-bottom:10px; }
    .au-meta { color:#6b7280; font-size:12px; }

    .au-block { border:1px solid #e5e7eb; border-radius:12px; background:#fff; overflow:hidden; margin-bottom:12px; }
    .au-block-h { padding:10px 12px; background:#eef7ff; border-bottom:1px solid #e5e7eb; }
    .au-kpis { display:flex; gap:10px; flex-wrap:wrap; margin-top:8px; }
    .au-pill { display:inline-flex; gap:8px; align-items:center; padding:6px 10px; border-radius:999px; font-size:12px; background:#fff; border:1px solid #e5e7eb; }
    .au-dot { width:10px; height:10px; border-radius:999px; display:inline-block; }
    .au-dot-av { background:${AU_AVAIL_COLOR}; }
    .au-dot-ut { background:${AU_UTIL_COLOR}; }

    .au-charts { padding:10px 12px; }
    .au-chart { min-height:260px; }
  </style>

  <div class="au-wrap">
    <div class="au-head">
      <h3 style="margin:0;">A&amp;U Dashboard</h3>
      <div class="au-meta">${site} · ${start} → ${end}</div>
    </div>

    ${AU_CATS.map((cat, idx) => {
      const bg = idx === 0 ? "#eaf4ff" : idx === 1 ? "#f3e8ff" : "#eaf4ff";
      return `
        <div class="au-block">
          <div class="au-block-h" style="background:${bg};">
            <b>${escape_html(cat)}'s (AVG)</b>
            <div class="au-kpis">
              <span class="au-pill"><span class="au-dot au-dot-av"></span>Availability <b>${formatPercent1(k[cat].avail_avg)}</b></span>
              <span class="au-pill"><span class="au-dot au-dot-ut"></span>Utilisation <b>${formatPercent1(k[cat].util_avg)}</b></span>
            </div>
          </div>
          <div class="au-charts">
            <div id="au_chart_${escape_html(cat)}" class="au-chart"></div>
          </div>
        </div>
      `;
    }).join("")}
  </div>
  `;
}

function render_au_graph_charts(computed) {
  for (const cat of AU_CATS) {
    const el = document.getElementById(`au_chart_${cat}`);
    if (!el) continue;

    const info = computed.byCat[cat];
    if (!info || !info.labels.length) {
      el.innerHTML = `<div class="text-muted" style="padding:8px;">No data to chart.</div>`;
      continue;
    }

    new frappe.Chart(`#au_chart_${cat}`, {
      title: "",
      data: {
        labels: info.labels,
        datasets: [
          { name: "Availability", values: info.availability, chartType: "bar" },
          { name: "Utilisation", values: info.utilisation, chartType: "bar" },
        ],
      },
      type: "bar",
      height: 260,
      axisOptions: { xAxisMode: "tick", yAxisMode: "span" },
      barOptions: { stacked: false, spaceRatio: 0.55 },
      colors: [AU_AVAIL_COLOR, AU_UTIL_COLOR],
    });
  }
}

function trunc1(v) {
  const n = asNumber(v);
  return Math.round(n * 10) / 10;
}

function trunc2(v) {
  const n = asNumber(v);
  return Math.round(n * 100) / 100;
}

function formatPercent1(v) {
  const n = trunc1(v);
  return `${n}%`;
}
