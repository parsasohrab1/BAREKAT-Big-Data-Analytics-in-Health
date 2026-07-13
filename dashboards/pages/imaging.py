"""Medical imaging page — PACS, thumbnails, DICOM viewer, CAD stub."""

from __future__ import annotations

import os

import streamlit as st

from dashboards.utils.imaging_loader import (
    bytes_to_image,
    get_local_thumbnail,
    get_local_viewer_image,
    load_imaging_studies,
)
from dashboards.utils.styles import render_hero


def render(data: dict, master, kpis: dict) -> None:
    render_hero(
        "تصاویر پزشکی (DICOM / PACS)",
        "اتصال PACS، thumbnail، viewer با Window/Level — CAD در فاز بعد",
    )

    api_url = os.getenv("BAREKAT_API_URL", "http://localhost:8000")
    st.caption(f"API: {api_url}/api/v1/imaging | ذخیره‌سازی: MinIO")

    tab_catalog, tab_viewer, tab_pacs, tab_cad = st.tabs([
        "کاتالوگ مطالعات",
        "Viewer",
        "اتصال PACS",
        "CAD (فاز بعد)",
    ])

    studies = load_imaging_studies()

    with tab_catalog:
        if studies.empty:
            st.info(
                "مطالعه DICOM یافت نشد. نمونه بسازید:\n\n"
                "`python scripts/generate_sample_dicom.py --output ./data/dicom`\n\n"
                "سپس ingest: `POST /api/v1/imaging/ingest/local?directory=./data/dicom`"
            )
        else:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("تعداد مطالعات", len(studies))
            with c2:
                mods = studies["modality"].nunique() if "modality" in studies.columns else 0
                st.metric("مدالیته‌ها", mods)
            with c3:
                pacs = studies["pacs_source"].nunique() if "pacs_source" in studies.columns else 1
                st.metric("منابع", pacs)

            modality_filter = st.multiselect(
                "فیلتر مدالیته",
                options=sorted(studies["modality"].dropna().unique()) if "modality" in studies.columns else [],
            )
            filtered = studies
            if modality_filter and "modality" in studies.columns:
                filtered = studies[studies["modality"].isin(modality_filter)]

            cols = st.columns(3)
            for idx, row in filtered.head(12).iterrows():
                col = cols[idx % 3]
                with col:
                    st.markdown(f"**{row.get('modality', '—')}** — {row.get('patient_id', '—')}")
                    st.caption(row.get("study_description") or row.get("body_part") or row.get("study_uid", "")[:20])

                    thumb = None
                    study_uid = row.get("study_uid", "")
                    file_path = row.get("file_path", "")

                    if study_uid:
                        try:
                            import httpx
                            token = st.session_state.get("token")
                            headers = {"Authorization": f"Bearer {token}"} if token else {}
                            resp = httpx.get(
                                f"{api_url}/api/v1/imaging/studies/{study_uid}/thumbnail",
                                headers=headers,
                                timeout=10,
                            )
                            if resp.status_code == 200:
                                thumb = resp.content
                        except Exception:
                            pass

                    if thumb is None and file_path:
                        thumb = get_local_thumbnail(file_path)

                    if thumb:
                        st.image(bytes_to_image(thumb), use_container_width=True)
                    else:
                        st.markdown("*(بدون thumbnail)*")

                    if st.button("مشاهده", key=f"view_{study_uid or idx}"):
                        st.session_state["selected_study_uid"] = study_uid
                        st.session_state["selected_file_path"] = file_path

    with tab_viewer:
        study_uid = st.session_state.get("selected_study_uid", "")
        file_path = st.session_state.get("selected_file_path", "")

        if not study_uid and not file_path:
            st.warning("از تب کاتالوگ یک مطالعه را انتخاب کنید.")
        else:
            st.markdown(f"**Study UID:** `{study_uid or 'local'}`")
            window = st.slider("Window", 50, 2000, 400, 50)
            level = st.slider("Level", -1000, 3000, 40, 10)

            image_bytes = None
            if study_uid:
                try:
                    import httpx
                    token = st.session_state.get("token")
                    headers = {"Authorization": f"Bearer {token}"} if token else {}
                    resp = httpx.get(
                        f"{api_url}/api/v1/imaging/studies/{study_uid}/viewer",
                        params={"window": window, "level": level},
                        headers=headers,
                        timeout=30,
                    )
                    if resp.status_code == 200:
                        image_bytes = resp.content
                except Exception as exc:
                    st.error(f"API viewer error: {exc}")

            if image_bytes is None and file_path:
                image_bytes = get_local_viewer_image(file_path, window, level)

            if image_bytes:
                st.image(bytes_to_image(image_bytes), use_container_width=True)
            else:
                st.error("نمایش تصویر ممکن نیست.")

    with tab_pacs:
        st.markdown("### اتصال PACS")
        st.markdown("""
| روش | توضیح |
|-----|--------|
| **DIMSE** | C-ECHO / C-FIND روی `PACS_HOST:PACS_PORT` |
| **Orthanc REST** | `PACS_ORTHANC_URL` برای query و retrieve |
        """)
        if st.button("تست C-ECHO (نیاز به JWT admin/clinician)"):
            try:
                import httpx
                token = st.session_state.get("token")
                if not token:
                    st.error("ابتدا وارد شوید.")
                else:
                    resp = httpx.post(
                        f"{api_url}/api/v1/imaging/pacs/echo",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=15,
                    )
                    st.json(resp.json())
            except Exception as exc:
                st.error(str(exc))

        patient_id = st.text_input("Patient ID برای C-FIND")
        if st.button("جستجوی مطالعات PACS") and patient_id:
            try:
                import httpx
                token = st.session_state.get("token")
                resp = httpx.post(
                    f"{api_url}/api/v1/imaging/pacs/query",
                    json={"patient_id": patient_id},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=30,
                )
                st.json(resp.json())
            except Exception as exc:
                st.error(str(exc))

    with tab_cad:
        st.markdown("### CAD — تشخیص کمکی (فاز بعد)")
        st.info(
            "مدل‌های CAD هنوز آموزش ندیده‌اند. در فاز بعد:\n"
            "- Chest X-ray: pneumothorax, cardiomegaly\n"
            "- CT: hemorrhage, PE, nodule\n"
            "- Mammography: mass detection"
        )
        if study_uid:
            if st.button("اجرای CAD stub"):
                try:
                    import httpx
                    token = st.session_state.get("token")
                    resp = httpx.get(
                        f"{api_url}/api/v1/imaging/studies/{study_uid}/cad",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=15,
                    )
                    st.json(resp.json())
                except Exception as exc:
                    st.error(str(exc))
