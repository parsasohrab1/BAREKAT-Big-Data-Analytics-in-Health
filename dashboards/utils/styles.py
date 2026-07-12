"""Dashboard styling."""

import streamlit as st

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Vazirmatn', 'Segoe UI', Tahoma, sans-serif;
}

.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 1400px;
}

.hero-banner {
    background: linear-gradient(135deg, #0C4A6E 0%, #0891B2 55%, #06B6D4 100%);
    border-radius: 18px;
    padding: 1.6rem 2rem;
    color: white;
    margin-bottom: 1.2rem;
    box-shadow: 0 10px 30px rgba(8, 145, 178, 0.25);
}

.hero-banner h1 {
    color: white !important;
    font-size: 1.8rem !important;
    margin-bottom: 0.3rem !important;
}

.hero-banner p {
    color: rgba(255,255,255,0.92) !important;
    margin: 0;
    font-size: 0.98rem;
}

.metric-card {
    background: white;
    border: 1px solid #E2E8F0;
    border-radius: 16px;
    padding: 1rem 1.1rem;
    box-shadow: 0 4px 16px rgba(15, 23, 42, 0.05);
    min-height: 110px;
}

.metric-label {
    color: #64748B;
    font-size: 0.82rem;
    font-weight: 600;
    margin-bottom: 0.35rem;
}

.metric-value {
    color: #0F172A;
    font-size: 1.65rem;
    font-weight: 700;
    line-height: 1.1;
}

.metric-sub {
    color: #0891B2;
    font-size: 0.78rem;
    margin-top: 0.35rem;
}

.section-card {
    background: white;
    border: 1px solid #E2E8F0;
    border-radius: 16px;
    padding: 1rem 1.2rem;
    margin-bottom: 1rem;
    box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
}

.section-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #0F172A;
    margin-bottom: 0.8rem;
}

.badge {
    display: inline-block;
    padding: 0.18rem 0.55rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 700;
}

.badge-critical { background: #FEE2E2; color: #B91C1C; }
.badge-high { background: #FFEDD5; color: #C2410C; }
.badge-medium { background: #FEF3C7; color: #B45309; }
.badge-low { background: #DCFCE7; color: #15803D; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #F8FAFC 0%, #EFF6FF 100%);
    border-right: 1px solid #E2E8F0;
}

[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: #0C4A6E !important;
}

div[data-testid="stMetric"] {
    background: white;
    border: 1px solid #E2E8F0;
    border-radius: 14px;
    padding: 0.75rem 1rem;
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
}

.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}

.stTabs [data-baseweb="tab"] {
    background: #F8FAFC;
    border-radius: 10px;
    padding: 0.5rem 1rem;
    border: 1px solid #E2E8F0;
}

.stTabs [aria-selected="true"] {
    background: #ECFEFF !important;
    border-color: #0891B2 !important;
}
</style>
"""


def apply_styles() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_hero(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="hero-banner">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(label: str, value: str, sub: str = "") -> str:
    sub_html = f'<div class="metric-sub">{sub}</div>' if sub else ""
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {sub_html}
    </div>
    """
