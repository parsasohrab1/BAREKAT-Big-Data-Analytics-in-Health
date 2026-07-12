"""Chart theming and reusable Plotly helpers."""

import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

CHART_COLORS = [
    "#0E7490", "#0891B2", "#06B6D4", "#22D3EE",
    "#6366F1", "#8B5CF6", "#EC4899", "#F59E0B",
]

SEVERITY_COLORS = {
    "critical": "#DC2626",
    "high": "#EA580C",
    "medium": "#D97706",
    "low": "#059669",
}

pio.templates["barekat"] = go.layout.Template(
    layout=go.Layout(
        font=dict(family="Segoe UI, Tahoma, sans-serif", color="#0F172A", size=13),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=CHART_COLORS,
        margin=dict(l=24, r=24, t=56, b=24),
        title=dict(font=dict(size=18, color="#0F172A")),
        xaxis=dict(gridcolor="#E2E8F0", linecolor="#CBD5E1", zerolinecolor="#E2E8F0"),
        yaxis=dict(gridcolor="#E2E8F0", linecolor="#CBD5E1", zerolinecolor="#E2E8F0"),
        legend=dict(bgcolor="rgba(255,255,255,0.8)", bordercolor="#E2E8F0", borderwidth=1),
    )
)
pio.templates.default = "barekat"


def bar_chart(df, x, y, title, orientation="v", color=None):
    if orientation == "h":
        fig = px.bar(df, x=x, y=y, title=title, color=color, orientation="h", text_auto=True)
    else:
        fig = px.bar(df, x=x, y=y, title=title, color=color, text_auto=True)
    fig.update_traces(marker_line_width=0)
    fig.update_layout(hovermode="x unified")
    return fig


def donut_chart(df, names, values, title):
    fig = px.pie(df, names=names, values=values, title=title, hole=0.55)
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return fig


def line_chart(df, x, y, color=None, title=""):
    fig = px.line(df, x=x, y=y, color=color, title=title, markers=True)
    fig.update_traces(line=dict(width=3))
    return fig


def heatmap_chart(matrix, x_labels, y_labels, title):
    fig = go.Figure(
        data=go.Heatmap(
            z=matrix,
            x=x_labels,
            y=y_labels,
            colorscale="Teal",
            hoverongaps=False,
        )
    )
    fig.update_layout(title=title)
    return fig


def gauge_chart(value: float, title: str, max_value: float = 100):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            title={"text": title, "font": {"size": 16}},
            number={"suffix": "%", "font": {"size": 28}},
            gauge={
                "axis": {"range": [0, max_value]},
                "bar": {"color": "#0891B2"},
                "steps": [
                    {"range": [0, 33], "color": "#ECFDF5"},
                    {"range": [33, 66], "color": "#FEF3C7"},
                    {"range": [66, max_value], "color": "#FEE2E2"},
                ],
                "threshold": {
                    "line": {"color": "#DC2626", "width": 4},
                    "thickness": 0.8,
                    "value": max_value * 0.7,
                },
            },
        )
    )
    fig.update_layout(height=280, margin=dict(l=20, r=20, t=60, b=20))
    return fig
