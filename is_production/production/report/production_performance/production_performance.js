frappe.query_reports["Production Performance"] = {
    "filters": [
        {
            fieldname: "start_date",
            label: __("Start Date"),
            fieldtype: "Date",
            reqd: 1
        },
        {
            fieldname: "end_date",
            label: __("End Date"),
            fieldtype: "Date",
            reqd: 1
        },
        {
            fieldname: "site",
            label: __("Site"),
            fieldtype: "Link",
            options: "Location",
            reqd: 1
        }
    ],

    onload: function (report) {
        const today = frappe.datetime.get_today();
        const monthStart = frappe.datetime.month_start(today);
        frappe.query_report.set_filter_value("start_date", monthStart);
        frappe.query_report.set_filter_value("end_date", today);

        // Wait for report table to render, then slightly adjust styling
        setTimeout(() => {
            const htmlCells = $('div.report-wrapper').find('td[data-fieldtype="HTML"]');
            htmlCells.css({
                'overflow': 'visible',
                'white-space': 'normal',
                'vertical-align': 'top',
                'padding': '4px'
            });
        }, 800);
    }
};
