"""
ui_components.py - reusable Streamlit pieces: theme, cards, tables, buttons.

Nothing here runs at import time, so importing this file never draws anything.
"""

import html

import pandas as pd
import streamlit as st

CSS = """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1200px;}
h1, h2, h3 {letter-spacing: -0.01em;}

/* ---------- page header ---------- */
.ll-header {
  padding: 1.1rem 1.4rem; border-radius: 14px; margin-bottom: 1.1rem;
  background: linear-gradient(120deg, #7f1d1d 0%, #b91c1c 100%);
  box-shadow: 0 2px 8px rgba(127, 29, 29, .25);
}
.ll-header h1 {color: #ffffff; margin: 0; font-size: 1.7rem; line-height: 1.2;}
.ll-header p {color: #fee2e2; margin: .3rem 0 0 0; font-size: .95rem;}

/* ---------- KPI cards ---------- */
.ll-kpi {
  background: #ffffff; border: 1px solid #fecaca; border-left: 6px solid #b91c1c;
  border-radius: 12px; padding: .8rem 1rem; margin-bottom: .6rem;
  box-shadow: 0 1px 4px rgba(0, 0, 0, .06);
}
.ll-kpi.warn {border-left-color: #f59e0b; border-color: #fde68a;}
.ll-kpi.good {border-left-color: #15803d; border-color: #bbf7d0;}
.ll-kpi-label {color: #6b7280; font-size: .8rem; font-weight: 600;
               text-transform: uppercase; letter-spacing: .04em;}
.ll-kpi-value {color: #7f1d1d; font-size: 2rem; font-weight: 700; line-height: 1.15;}
.ll-kpi-note {color: #6b7280; font-size: .8rem;}

/* ---------- misc ---------- */
.ll-note {color: #6b7280; font-size: .82rem;}
.ll-disclaimer {
  background: #fff7ed; border: 1px solid #fed7aa; color: #9a3412;
  border-radius: 10px; padding: .55rem .8rem; font-size: .85rem; margin-bottom: .8rem;
}
button[kind="primary"], [data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primaryFormSubmit"] {
  background-color: #b91c1c !important; border-color: #b91c1c !important; color: #ffffff !important;
}
button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover,
[data-testid="stBaseButton-primaryFormSubmit"]:hover {
  background-color: #7f1d1d !important; border-color: #7f1d1d !important;
}
[data-testid="stSidebar"] {border-right: 1px solid #fecaca;}

@media (max-width: 640px) {
  .ll-header h1 {font-size: 1.35rem;}
  .ll-kpi-value {font-size: 1.6rem;}
}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(title, subtitle, icon=""):
    st.markdown(
        f'<div class="ll-header"><h1>{html.escape(icon)} {html.escape(title)}</h1>'
        f'<p>{html.escape(subtitle)}</p></div>',
        unsafe_allow_html=True,
    )


def kpi_card(label, value, note="", tone=""):
    """tone: '' (red), 'warn' (amber) or 'good' (green)."""
    st.markdown(
        f'<div class="ll-kpi {tone}"><div class="ll-kpi-label">{html.escape(str(label))}</div>'
        f'<div class="ll-kpi-value">{html.escape(str(value))}</div>'
        f'<div class="ll-kpi-note">{html.escape(str(note))}</div></div>',
        unsafe_allow_html=True,
    )


def disclaimer(text):
    st.markdown(f'<div class="ll-disclaimer">{html.escape(text)}</div>',
                unsafe_allow_html=True)


def note(text):
    st.markdown(f'<div class="ll-note">{html.escape(text)}</div>',
                unsafe_allow_html=True)


# ---------- tables and buttons (work on old and new Streamlit versions) ----------
def show_table(df, empty_message="Nothing to show."):
    """Show a DataFrame full width, or an info box when it is empty."""
    if df is None or len(df) == 0:
        st.info(empty_message)
        return
    try:
        st.dataframe(df, width="stretch", hide_index=True)
    except Exception:
        st.dataframe(df, use_container_width=True, hide_index=True)


def action_button(label, key, primary=False):
    kind = "primary" if primary else "secondary"
    try:
        return st.button(label, key=key, type=kind, width="stretch")
    except Exception:
        return st.button(label, key=key, type=kind, use_container_width=True)


# ---------- one-time messages shown after a rerun ----------
def flash(kind, message):
    """Remember a message (kind: success / error / info / warning)."""
    st.session_state["_flash"] = (kind, message)


def show_flash():
    if "_flash" in st.session_state:
        kind, message = st.session_state["_flash"]
        del st.session_state["_flash"]
        getattr(st, kind)(message)


# ---------- DataFrame builders ----------
def units_frame(units, today):
    rows = []
    for u in units:
        left = u.days_left(today)
        rows.append({
            "Unit ID": u.unit_id,
            "Blood group": u.group,
            "Collected": u.collected.isoformat(),
            "Expiry": u.expiry.isoformat(),
            "Days left": left,
            "Status": "Expiring soon" if left <= 7 else "OK",
            "Donor ID": u.donor_id or "-",
        })
    return pd.DataFrame(rows)


def donors_frame(bank, donors):
    rows = []
    for d in donors:
        wait = bank.days_until_eligible(d)
        rows.append({
            "ID": d.donor_id,
            "Name": d.name,
            "Group": d.group,
            "Area": d.area,
            "Last donation": d.last_donation.isoformat() if d.last_donation else "Not recorded",
            "Eligibility (project rule)": "Eligible" if wait == 0 else f"Wait {wait} more day(s)",
        })
    return pd.DataFrame(rows)


def requests_frame(bank, requests):
    from models import URGENCY
    rows = []
    for r in requests:
        rows.append({
            "Request": r.req_id,
            "Patient": r.patient,
            "Group": r.group,
            "Units": r.units,
            "Urgency": URGENCY[r.urgency],
            "Area": r.area,
            "Status": bank.request_status(r.req_id),
        })
    return pd.DataFrame(rows)
