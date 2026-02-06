# is_production/production/controllers/notifications.py
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode

import frappe
from frappe.utils import add_days, getdate, now_datetime


# -------------------------------------------------------------------
# Constants (match your DocType select options exactly)
# -------------------------------------------------------------------
NOTIF_TYPE_CEO = "CEO Dashboard 1"
NOTIF_TYPE_PE = "Production Efficiency"

GROUP_DOCTYPE = "Production Notification Group"
RECIPIENT_CHILD = "Production Notification Recipient"

REPORT_NAME_CEO = "CEO Dashboard 1"
REPORT_FILTER_FIELD = "define_monthly_production"
DEFINE_MONTHLY_PROD_DOCTYPE = "Define Monthly Production"

# Dummy / anchor site for CEO Dashboard 1 (your choice)
CEO_DUMMY_SITE = "Plot 22"


@dataclass(frozen=True)
class Recipient:
    email: str
    full_name: str


# -------------------------------------------------------------------
# Date helpers
# -------------------------------------------------------------------
def _today() -> date:
    return getdate(now_datetime().date())


def _previous_week_range(ref: date | None = None) -> tuple[date, date]:
    """
    Previous Monday -> Sunday relative to 'ref' (default: today).

    Example:
      If ref is Sunday 2026-02-08:
        this week Monday = 2026-02-02
        previous Monday  = 2026-01-26
        previous Sunday  = 2026-02-01
    """
    ref = ref or _today()
    this_monday = add_days(ref, -ref.weekday())
    prev_monday = add_days(this_monday, -7)
    prev_sunday = add_days(prev_monday, 6)
    return getdate(prev_monday), getdate(prev_sunday)


def _current_week_range(ref: date | None = None) -> tuple[date, date]:
    """
    Current Monday -> Sunday week for 'ref' (default: today).

    Example:
      If ref is Sunday 2026-02-08:
        Monday = 2026-02-02
        Sunday = 2026-02-08
    """
    ref = ref or _today()
    this_monday = add_days(ref, -ref.weekday())
    this_sunday = add_days(this_monday, 6)
    return getdate(this_monday), getdate(this_sunday)


def _fmt_week_range(monday: date, sunday: date) -> str:
    return f"({monday.strftime('%d %b %Y')} - {sunday.strftime('%d %b %Y')})"


def _fmt_date(d: date) -> str:
    return d.strftime("%d %b %Y")


# -------------------------------------------------------------------
# Recipient resolution
# -------------------------------------------------------------------
def _get_recipients(notification_type: str, site: str) -> list[Recipient]:
    """
    Rules:
    - Only include groups where group.enabled = 1
    - Include recipients for the matching (type, site)
    - PLUS any recipients anywhere (same type) where receive_all_sites = 1
    - Only send if User.enabled = 1 and User.email exists
    - Do NOT rely on child-row enabled (your child rows default to enabled=1 logic)
    """
    if not site:
        return []

    groups_for_site = frappe.get_all(
        GROUP_DOCTYPE,
        filters={"enabled": 1, "notification_type": notification_type, "site": site},
        fields=["name"],
        limit_page_length=500,
    )

    groups_all = frappe.get_all(
        GROUP_DOCTYPE,
        filters={"enabled": 1, "notification_type": notification_type},
        fields=["name"],
        limit_page_length=500,
    )

    group_names_site = {g["name"] for g in groups_for_site}
    group_names_all = {g["name"] for g in groups_all}

    recipient_rows = []

    # site-specific rows (NO child-row enabled filter)
    if group_names_site:
        recipient_rows += frappe.get_all(
            RECIPIENT_CHILD,
            filters={"parent": ["in", list(group_names_site)]},
            fields=["user", "receive_all_sites"],
            limit_page_length=2000,
        )

    # global rows (receive_all_sites=1) (NO child-row enabled filter)
    if group_names_all:
        recipient_rows += frappe.get_all(
            RECIPIENT_CHILD,
            filters={"parent": ["in", list(group_names_all)], "receive_all_sites": 1},
            fields=["user", "receive_all_sites"],
            limit_page_length=2000,
        )

    users = sorted({r.get("user") for r in recipient_rows if r.get("user")})

    out: dict[str, Recipient] = {}
    for user in users:
        enabled, email, full_name = frappe.db.get_value(
            "User", user, ["enabled", "email", "full_name"]
        ) or (0, None, None)

        if not enabled or not email:
            continue

        out[email] = Recipient(email=email, full_name=full_name or user)

    return sorted(out.values(), key=lambda x: x.email.lower())


def _get_all_sites_for_notification(notification_type: str) -> list[str]:
    rows = frappe.get_all(
        GROUP_DOCTYPE,
        filters={"enabled": 1, "notification_type": notification_type},
        fields=["site"],
        limit_page_length=500,
    )
    return sorted({r.get("site") for r in rows if r.get("site")})


# -------------------------------------------------------------------
# CEO Dashboard 1 helpers
# -------------------------------------------------------------------
def _expected_define_monthly_production_name(ref: date | None = None) -> str:
    ref = ref or _today()
    month_name = calendar.month_name[ref.month]  # "January"
    return f"{month_name}-{ref.year}--Data"


def _find_define_monthly_production_for_current_month() -> str | None:
    """
    Your filter values look like: January-2025--Data

    Strategy:
      1) Try exact expected name.
      2) Fallback: LIKE 'January-2025%' ordered by modified desc.
    """
    expected = _expected_define_monthly_production_name()

    if frappe.db.exists(DEFINE_MONTHLY_PROD_DOCTYPE, expected):
        return expected

    month_name = calendar.month_name[_today().month]
    year = _today().year

    name = frappe.db.get_value(
        DEFINE_MONTHLY_PROD_DOCTYPE,
        filters={"name": ["like", f"{month_name}-{year}%"]},
        fieldname="name",
        order_by="modified desc",
    )
    return name


def _build_query_report_link(report_name: str, filters: dict) -> str:
    """
    Build a Desk link to a Query Report / Script Report with filters.
    """
    # Desk expects filters in the URL as JSON string
    import json

    base = frappe.utils.get_url()
    path = f"/app/query-report/{frappe.utils.quote(report_name)}"
    qs = urlencode({"filters": json.dumps(filters or {})})
    return f"{base}{path}?{qs}"


# -------------------------------------------------------------------
# Email sender
# -------------------------------------------------------------------
def _send_email(recipients: list[Recipient], subject: str, body_html: str, attachments=None) -> None:
    """
    Sends/queues an email.
    If outgoing email is not configured, log a clear error and return.
    """
    if not recipients:
        return

    try:
        frappe.sendmail(
            recipients=[r.email for r in recipients],
            subject=subject,
            message=body_html,
            attachments=attachments or [],
        )
    except frappe.OutgoingEmailError:
        frappe.log_error(
            "Outgoing Email is not configured.\n"
            "Fix: Setup a DEFAULT outgoing Email Account in Frappe.\n"
            "Go to: Tools > Email Account, create/enable an account, and tick 'Default Outgoing'.",
            "Notifications email failed (OutgoingEmailError)",
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Notifications email failed")


# -------------------------------------------------------------------
# JOB 1: CEO Dashboard 1 DAILY (05:55) - LINK EMAIL (no PDF) - skip Sundays
# -------------------------------------------------------------------
def send_ceo_dashboard_daily_emails():
    """
    Daily 05:55 (except Sunday):
    - Builds a link to the CEO Dashboard 1 report with current month filter
    - Sends as a LINK (no PDF)
    - Sends to recipients configured for notification_type="CEO Dashboard 1"
      using Plot 22 as the dummy/anchor site group for normal recipients,
      plus any receive_all_sites recipients across all CEO groups.
    """
    today = _today()

    # Safety guard: if someone schedules it on Sunday, do nothing
    if today.weekday() == 6:  # Monday=0 ... Sunday=6
        return

    prev_mon, prev_sun = _previous_week_range(today)
    week_range = _fmt_week_range(prev_mon, prev_sun)

    define_name = _find_define_monthly_production_for_current_month()
    if not define_name:
        frappe.log_error(
            f"Could not find {DEFINE_MONTHLY_PROD_DOCTYPE} for current month. "
            f"Expected like '{_expected_define_monthly_production_name()}'.",
            "CEO Dashboard 1 daily email",
        )
        return

    try:
        # Build report link (with the same filter field you used in qr.run)
        report_url = _build_query_report_link(
            REPORT_NAME_CEO,
            {REPORT_FILTER_FIELD: define_name},
        )

        # 1) Anchor site recipients (Plot 22)
        all_recipients: dict[str, Recipient] = {}
        for r in _get_recipients(NOTIF_TYPE_CEO, CEO_DUMMY_SITE):
            all_recipients[r.email] = r

        # 2) Plus any receive_all_sites recipients from any CEO group (any site)
        sites = _get_all_sites_for_notification(NOTIF_TYPE_CEO)
        for site in sites:
            for r in _get_recipients(NOTIF_TYPE_CEO, site):
                all_recipients[r.email] = r

        recipients = sorted(all_recipients.values(), key=lambda x: x.email.lower())
        if not recipients:
            frappe.log_error(
                f"No recipients resolved for CEO Dashboard 1. "
                f"Ensure you have a Production Notification Group for site='{CEO_DUMMY_SITE}' "
                f"and/or receive_all_sites recipients configured.",
                "CEO Dashboard 1 daily email",
            )
            return

        subject = f"Production Update {_fmt_date(today)}"
        body = (
            "Dear Management,<br>"
            f"Please find below the link for the Production Dashboard Update. {week_range}.<br><br>"
            f"<a href=\"{report_url}\">Click here to view: CEO Dashboard 1</a><br><br>"
            "Kind Regards"
        )

        _send_email(
            recipients=recipients,
            subject=subject,
            body_html=body,
            attachments=[],
        )

    except Exception:
        frappe.log_error(frappe.get_traceback(), "CEO Dashboard 1 daily email failed")


# -------------------------------------------------------------------
# JOB 2: Production Efficiency WEEKLY (Sunday 14:15 after close)
# -------------------------------------------------------------------
def send_production_efficiency_weekly_emails():
    """
    Sunday 14:15 (scheduled in hooks.py):
    - Sends Production Efficiency emails as LINKS (no PDF)
    - Per site, for CURRENT week's Monday->Sunday doc (the same range shown in the UI)
      Example on Sunday: start_date = Monday (6 days back), end_date = Sunday (today).
    """
    today = _today()

    # Guard: this job is intended for Sunday. If it runs on another day, do nothing.
    if today.weekday() != 6:  # Sunday=6
        return

    this_mon, this_sun = _current_week_range(today)

    # On Sunday, this_sun will equal 'today'
    subject_week = _fmt_week_range(this_mon, this_sun)
    subject = f"Week Production Efficiency {subject_week}"

    sites = _get_all_sites_for_notification(NOTIF_TYPE_PE)

    for site in sites:
        docname = frappe.db.get_value(
            "Production Efficiency",
            filters={"site": site, "start_date": this_mon, "end_date": this_sun},
            fieldname="name",
            order_by="modified desc",
        )

        if not docname:
            frappe.log_error(
                f"No Production Efficiency doc found for site={site} range={this_mon}..{this_sun}",
                "Production Efficiency weekly link email",
            )
            continue

        recipients = _get_recipients(NOTIF_TYPE_PE, site)
        if not recipients:
            continue

        doc = frappe.get_doc("Production Efficiency", docname)
        url = frappe.utils.get_url(doc.get_url())

        body = (
            "Dear Management,<br>"
            f"Please find below the link to access the Production Efficiency Update after this week's production {subject_week}.<br><br>"
            f"<a href=\"{url}\">Please click here to view: {site}</a><br><br>"
            "Kind Regards"
        )

        _send_email(recipients=recipients, subject=subject, body_html=body, attachments=[])
