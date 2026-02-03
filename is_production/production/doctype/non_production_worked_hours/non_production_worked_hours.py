# Copyright (c) 2026, Isambane Mining (Pty) Ltd
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


def _parse_duration_to_seconds(val) -> float:
	"""
	Frappe Duration is commonly stored as seconds (int/float) but may appear as strings like:
	- "HH:MM:SS"
	- "H:MM" (common)
	- "MM:SS" (less common; we treat 2 parts as H:MM to align with typical entry)
	- "SS"
	"""
	if val is None or val == "":
		return 0.0

	# numeric seconds
	if isinstance(val, (int, float)):
		return float(val)

	# string numeric seconds
	try:
		return float(val)
	except Exception:
		pass

	if not isinstance(val, str):
		return 0.0

	s = val.strip()
	if not s:
		return 0.0

	parts = [p.strip() for p in s.split(":")]
	try:
		nums = [float(p) for p in parts]
	except Exception:
		return 0.0

	seconds = 0.0
	if len(nums) == 3:
		hh, mm, ss = nums
		seconds = (hh * 3600.0) + (mm * 60.0) + ss
	elif len(nums) == 2:
		# Treat as H:MM (typical for Duration input like 1:30)
		hh, mm = nums
		seconds = (hh * 3600.0) + (mm * 60.0)
	elif len(nums) == 1:
		seconds = nums[0]

	return seconds or 0.0


class NonProductionWorkedHours(Document):
	def validate(self):
		self._recalculate_hours()
		self._validate_machine_constraints()

	def _recalculate_hours(self):
		for row in (self.get("equipment_non_production_hours") or []):
			seconds = _parse_duration_to_seconds(row.total_time)
			row.hours = flt(seconds / 3600.0, 4)

	def _validate_machine_constraints(self):
		"""
		Enforce:
		- machine Asset must be in same location as parent site (if site set)
		- machine Asset must have Asset Category = "Excavator"
		"""
		for row in (self.get("equipment_non_production_hours") or []):
			if not row.machine:
				continue

			asset_category, location = frappe.db.get_value(
				"Asset",
				row.machine,
				["asset_category", "location"],
			) or (None, None)

			# Category check
			if asset_category != "Excavator":
				frappe.throw(
					f"Row for machine <b>{frappe.bold(row.machine)}</b> is not an Excavator "
					f"(Asset Category is <b>{frappe.bold(asset_category or 'Not Set')}</b>)."
				)

			# Site/location check (only if site selected)
			if self.site and location != self.site:
				frappe.throw(
					f"Row for machine <b>{frappe.bold(row.machine)}</b> does not belong to site "
					f"<b>{frappe.bold(self.site)}</b> (Asset location is <b>{frappe.bold(location or 'Not Set')}</b>)."
				)
