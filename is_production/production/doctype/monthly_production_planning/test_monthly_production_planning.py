# Copyright (c) 2025, Isambane Mining (Pty) Ltd and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestMonthlyProductionPlanning(FrappeTestCase):
    def test_validate_syncs_missing_rows_for_extended_period(self):
        doc = frappe.get_doc({
            "doctype": "Monthly Production Planning",
            "location": "Koppie",
            "shift_system": "2x12Hour",
            "prod_month_start_date": "2026-04-30",
            "prod_month_end_date": "2026-05-02",
            "weekday_shift_hours": 12,
            "saturday_shift_hours": 12,
            "num_sat_shifts": 2,
            "num_excavators": 3,
            "monthly_target_bcm": 10000,
            "month_prod_days": [
                {
                    "doctype": "Monthly Production Days",
                    "shift_start_date": "2026-04-30",
                    "hourly_production_reference": "stale-ref",
                    "total_ts_bcms": 321,
                    "production_excavators": "4",
                }
            ],
        })
        doc.name = "2026-04-30-Koppie"

        doc.validate()

        self.assertEqual(
            [str(row.shift_start_date) for row in doc.month_prod_days],
            ["2026-04-30", "2026-05-01", "2026-05-02"],
        )
        self.assertEqual(doc.month_prod_days[0].total_ts_bcms, 321)
        self.assertEqual(doc.month_prod_days[0].production_excavators, "4")
        self.assertEqual(
            doc.month_prod_days[0].hourly_production_reference,
            "2026-04-30-Koppie-2026-04-30",
        )
        self.assertEqual(
            doc.month_prod_days[2].hourly_production_reference,
            "2026-04-30-Koppie-2026-05-02",
        )
        self.assertEqual(doc.month_prod_days[2].shift_day_hours, 12)
        self.assertEqual(doc.month_prod_days[2].shift_night_hours, 12)
        self.assertEqual(doc.num_prod_days, 3)
        self.assertEqual(doc.total_month_prod_hours, 72)

    def test_validate_drops_rows_outside_current_date_range(self):
        doc = frappe.get_doc({
            "doctype": "Monthly Production Planning",
            "location": "Koppie",
            "shift_system": "2x12Hour",
            "prod_month_start_date": "2026-05-01",
            "prod_month_end_date": "2026-05-02",
            "weekday_shift_hours": 12,
            "saturday_shift_hours": 12,
            "num_sat_shifts": 2,
            "month_prod_days": [
                {
                    "doctype": "Monthly Production Days",
                    "shift_start_date": "2026-04-30",
                },
                {
                    "doctype": "Monthly Production Days",
                    "shift_start_date": "2026-05-01",
                },
            ],
        })
        doc.name = "2026-05-01-Koppie"

        doc.validate()

        self.assertEqual(
            [str(row.shift_start_date) for row in doc.month_prod_days],
            ["2026-05-01", "2026-05-02"],
        )
