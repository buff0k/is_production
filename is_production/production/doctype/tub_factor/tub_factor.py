# Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class TubFactor(Document):
    def autoname(self):
        self._validate_definition()
        self.name = build_tub_factor_name(
            self.item_name,
            self.mat_type,
            self.tub_factor,
        )

    def validate(self):
        self._validate_definition()
        self._validate_canonical_name()

    def before_submit(self):
        self._validate_definition()
        self._validate_canonical_name()

    def before_cancel(self):
        reference = frappe.db.get_value(
            "Monthly Production Tub Factor",
            {
                "tub_factor": self.name,
                "parenttype": "Monthly Production Planning",
                "parentfield": "tub_factors",
            },
            ["parent", "idx"],
            as_dict=True,
        )

        if reference:
            frappe.throw(
                _(
                    "Tub Factor {0} is used in Monthly Production Planning "
                    "{1}, row {2}, and cannot be cancelled."
                ).format(
                    frappe.bold(self.name),
                    frappe.bold(reference.parent),
                    reference.idx,
                ),
                title=_("Tub Factor Is In Use"),
            )

    def _validate_definition(self):
        if not self.item_name:
            frappe.throw(_("Truck Model is required."))
        if not self.mat_type:
            frappe.throw(_("Material Type is required."))
        if self.tub_factor in (None, ""):
            frappe.throw(_("Tub Factor is required."))
        if cint(self.tub_factor) < 0:
            frappe.throw(_("Tub Factor cannot be negative."))

    def _validate_canonical_name(self):
        if self.is_new():
            return

        expected = build_tub_factor_name(
            self.item_name,
            self.mat_type,
            self.tub_factor,
        )
        if self.name != expected:
            frappe.throw(
                _("Tub Factor name must be {0}.")
                .format(frappe.bold(expected))
            )


def build_tub_factor_name(item_name, mat_type, tub_factor):
    return (
        f"{str(item_name or '').strip()}-"
        f"{str(mat_type or '').strip()}-"
        f"{cint(tub_factor)}"
    )
