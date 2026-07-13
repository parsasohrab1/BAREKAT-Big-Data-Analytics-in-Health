"""Dashboard authentication with JWT and RBAC."""

from __future__ import annotations

import streamlit as st

from barekat.security.auth import authenticate_user, create_access_token, decode_token
from barekat.security.rbac import ROLE_PERMISSIONS, Role

PAGE_ACCESS: dict[str, list[str]] = {
    "نمای کلی": ["read"],
    "جمعیت بیماران": ["view_phi"],
    "بستری و بخش‌ها": ["read"],
    "تشخیص‌ها": ["read"],
    "داروها": ["read"],
    "آزمایشگاه": ["read"],
    "هوش تحلیلی ML": ["read", "run_analytics"],
    "هشدارها": ["read"],
    "تصاویر پزشکی": ["view_phi"],
    "انطباق و حریم خصوصی": ["manage_users"],
    "مدیریت مراکز": ["manage_tenants"],
    "گزارش‌های مدیریتی": ["read", "export"],
    "زیرساخت": ["manage_users"],
}

ROLE_LABELS = {
    "admin": "مدیر",
    "clinician": "پزشک",
    "researcher": "محقق",
    "viewer": "بیننده",
}


def _user_permissions(role: str) -> set[str]:
    try:
        return ROLE_PERMISSIONS.get(Role(role), set())
    except ValueError:
        return ROLE_PERMISSIONS.get(Role.VIEWER, set())


def can_access_page(page_name: str, role: str) -> bool:
    required = PAGE_ACCESS.get(page_name, ["read"])
    perms = _user_permissions(role)
    return any(perm in perms for perm in required)


def has_permission(role: str, permission: str) -> bool:
    return permission in _user_permissions(role)


def get_current_user() -> dict | None:
    return st.session_state.get("user")


def is_authenticated() -> bool:
    user = get_current_user()
    token = st.session_state.get("token")
    if not user or not token:
        return False
    try:
        payload = decode_token(token)
        if payload.get("sub") != user.get("username"):
            return False
        return True
    except ValueError:
        return False


def login(username: str, password: str, tenant_id: str | None = None) -> bool:
    user = authenticate_user(username, password, tenant_id)
    if not user:
        return False
    token = create_access_token({
        "sub": user["username"],
        "role": user["role"],
        "email": user["email"],
        "tenant_id": user.get("tenant_id", "default"),
        "tenant_slug": user.get("tenant_slug", "default"),
        "is_platform_admin": user.get("is_platform_admin", False),
    })
    st.session_state["token"] = token
    st.session_state["user"] = {**user, "token": token}
    st.session_state["tenant_id"] = user.get("tenant_id", "default")
    return True


def logout() -> None:
    for key in ("token", "user", "tenant_id"):
        st.session_state.pop(key, None)


def render_login_form() -> None:
    st.markdown(
        """
        <div class="hero-banner">
            <h1>BAREKAT Health Analytics</h1>
            <p>برای دسترسی به داشبورد وارد شوید</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _col1, col2, _col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("نام کاربری")
            password = st.text_input("رمز عبور", type="password")
            submitted = st.form_submit_button("ورود", use_container_width=True)

        if submitted:
            if login(username, password):
                st.rerun()
            else:
                st.error("نام کاربری یا رمز عبور نادرست است.")

        st.markdown(
            """
            **کاربران نمونه (توسعه)**
            - `admin` / `admin123`
            - `clinician` / `clinician123`
            - `researcher` / `researcher123`
            """
        )


def render_user_sidebar() -> None:
    user = get_current_user()
    if not user:
        return
    role = user.get("role", "viewer")
    tenant = user.get("tenant_id", "default")
    st.sidebar.markdown(
        f"**{user.get('username', '')}**  \n"
        f"<span style='color:#0891B2'>{ROLE_LABELS.get(role, role)}</span>  \n"
        f"<small>مرکز: {tenant}</small>",
        unsafe_allow_html=True,
    )
    if st.sidebar.button("خروج", use_container_width=True):
        logout()
        st.rerun()


def filter_pages(pages: dict, role: str) -> dict:
    return {name: module for name, module in pages.items() if can_access_page(name, role)}
