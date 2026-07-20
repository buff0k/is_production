# Copyright (c) 2026, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class OEMDieselBurnRate(Document):
	"""Effective-dated OEM diesel target for an Asset model."""

	def validate(self):
		if flt(self.burn_rate_lph) <= 0:
			frappe.throw(_("OEM Burn Rate must be greater than zero."))

		if not frappe.db.exists(
			"Asset",
			{
				"docstatus": 1,
				"asset_category": self.asset_category,
				"item_code": self.model,
			},
		):
			frappe.throw(
				_("Model {0} is not used by a submitted Asset in category {1}.").format(
					frappe.bold(self.model),
					frappe.bold(self.asset_category),
				)
			)

		duplicate = frappe.db.exists(
			"OEM Diesel Burn Rate",
			{
				"model": self.model,
				"effective_from": self.effective_from,
				"name": ["!=", self.name],
			},
		)

		if duplicate:
			frappe.throw(
				_("An OEM diesel burn rate already exists for model {0} from {1}.").format(
					self.model,
					self.effective_from,
				)
			)


@frappe.whitelist()
def get_models(asset_category: str | None = None) -> list[str]:
	"""Return models used by submitted Assets in the selected category."""

	if not asset_category:
		return []

	models = frappe.get_all(
		"Asset",
		filters={
			"docstatus": 1,
			"asset_category": asset_category,
			"item_code": ["is", "set"],
		},
		pluck="item_code",
		order_by="item_code asc",
	)

	return sorted(set(filter(None, models)), key=str.casefold)
