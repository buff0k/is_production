import base64
import re

import frappe
from frappe import _
from frappe.utils.pdf import get_pdf


@frappe.whitelist()
def download_dashboard_pdf(html, filename=None):
    """
    Generate the Production Dashboard PDF server-side.

    The browser sends the currently active dashboard tab as HTML.
    Chart canvases must already be replaced with image data URLs.
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("You must be logged in to download this PDF."))

    if not html:
        frappe.throw(_("No dashboard content was supplied."))

    # Remove executable or unsafe browser-only content.
    html = re.sub(
        r"<script\b[^>]*>.*?</script>",
        "",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    html = re.sub(
        r"\son\w+\s*=\s*(['\"]).*?\1",
        "",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    filename = frappe.scrub(filename or "production_dashboard")
    filename = filename[:120] or "production_dashboard"

    options = {
        "page-size": "A4",
        "orientation": "Landscape",
        "margin-top": "7mm",
        "margin-right": "7mm",
        "margin-bottom": "7mm",
        "margin-left": "7mm",
        "encoding": "UTF-8",
        "print-media-type": None,
        "disable-smart-shrinking": None,
        "enable-local-file-access": None,
        "javascript-delay": "100",
        "no-stop-slow-scripts": None,
    }

    try:
        pdf_content = get_pdf(html, options=options)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Production Dashboard PDF Generation",
        )
        frappe.throw(
            _(
                "The server could not generate the Production Dashboard PDF. "
                "Please check the Error Log."
            )
        )

    return {
        "filename": f"{filename}.pdf",
        "content": base64.b64encode(pdf_content).decode("utf-8"),
    }
