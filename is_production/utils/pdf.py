# apps/is_production/is_production/utils/pdf.py

import frappe
from frappe.utils.pdf import pdf_body_html as _pdf_body_html

def pdf_body_html(jenv, template, print_format, args):
    """
    Wrap Frappe's pdf_body_html to
    1) recalculate MtD on the linked Monthly Production Planning,
    2) pull those fresh values into args['doc'],
    3) then render the PDF as normal.
    """
    doc = args.get("doc")
    if doc and getattr(doc, "month_prod_planning", None):
        # 1) trigger MtD recalculation on the Monthly Production Planning
        frappe.get_attr(
            "is_production.production.doctype.monthly_production_planning."
            "monthly_production_planning.update_mtd_production"
        )(name=doc.month_prod_planning)

        # 2) pull updated MtD values back into our doc
        mpp = frappe.get_doc("Monthly Production Planning", doc.month_prod_planning)
        for field in [
            "monthly_target_bcm",
            "target_bcm_day",
            "target_bcm_hour",
            "month_act_ts_bcm_tallies",
            "month_act_dozing_bcm_tallies",
            "monthly_act_tally_survey_variance",
            "month_actual_bcm",
            "mtd_bcm_day",
            "mtd_bcm_hour",
            "month_forecated_bcm"
        ]:
            # overwrite the doc’s attribute so Jinja will pick it up
            setattr(doc, field, getattr(mpp, field))

    # 3) render PDF as usual
    return _pdf_body_html(jenv, template, print_format, args)
