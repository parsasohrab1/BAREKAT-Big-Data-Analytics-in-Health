"""Live WebSocket alert feed for Streamlit dashboard."""

from __future__ import annotations

import os

import streamlit.components.v1 as components


def render_live_alert_feed(api_base: str | None = None, height: int = 320) -> None:
    base = (api_base or os.getenv("BAREKAT_API_URL", "http://localhost:8000")).rstrip("/")
    ws_url = base.replace("https://", "wss://").replace("http://", "ws://") + "/api/v1/stream/alerts"

    components.html(
        f"""
        <div style="font-family: Tahoma, sans-serif; direction: rtl;">
          <div id="status" style="padding:8px; background:#f0f9ff; border-radius:8px; margin-bottom:8px;">
            در حال اتصال به WebSocket...
          </div>
          <div id="feed" style="max-height:{height - 60}px; overflow-y:auto;"></div>
        </div>
        <script>
        const feed = document.getElementById('feed');
        const status = document.getElementById('status');
        const ws = new WebSocket("{ws_url}");
        const colors = {{critical:'#fee2e2', high:'#ffedd5', medium:'#fef9c3', low:'#ecfccb'}};

        ws.onopen = () => {{
          status.textContent = 'متصل — هشدارهای بلادرنگ فعال';
          status.style.background = '#dcfce7';
        }};
        ws.onclose = () => {{
          status.textContent = 'قطع اتصال WebSocket';
          status.style.background = '#fee2e2';
        }};
        ws.onerror = () => {{
          status.textContent = 'خطا در اتصال WebSocket';
          status.style.background = '#fee2e2';
        }};
        ws.onmessage = (evt) => {{
          try {{
            const alert = JSON.parse(evt.data);
            const div = document.createElement('div');
            const sev = alert.severity || 'medium';
            div.style.cssText = `padding:10px; margin:6px 0; border-radius:8px; background:${{colors[sev] || '#f8fafc'}}; border-right:4px solid #0891b2;`;
            div.innerHTML = `<strong>[${{sev}}]</strong> ${{alert.message || ''}}<br><small>بیمار: ${{alert.patient_id || '-'}} | ریسک: ${{((alert.risk_score||0)*100).toFixed(0)}}%</small>`;
            feed.prepend(div);
            while (feed.children.length > 30) feed.removeChild(feed.lastChild);
          }} catch (e) {{}}
        }};
        </script>
        """,
        height=height,
    )
