"""Regulatory compliance frameworks: HIPAA, GDPR, Iran domestic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ComplianceRequirement:
    id: str
    framework: str
    title: str
    title_fa: str
    description: str
    implemented: bool
    config_key: str | None = None


FRAMEWORKS = {
    "hipaa": {
        "name": "HIPAA",
        "name_fa": "قانون قابلیت انتقال و پاسخگویی بیمه سلامت آمریکا",
        "scope": "US healthcare — PHI protection",
        "regulations": [
            "45 CFR §164.308 — Administrative safeguards",
            "45 CFR §164.312 — Technical safeguards (access control, audit controls)",
            "45 CFR §164.514 — De-identification of PHI",
        ],
    },
    "gdpr": {
        "name": "GDPR",
        "name_fa": "مقررات عمومی حفاظت از داده اتحادیه اروپا",
        "scope": "EU/EEA — personal data of data subjects",
        "regulations": [
            "Art. 5 — Principles (purpose limitation, storage limitation)",
            "Art. 7 — Conditions for consent",
            "Art. 17 — Right to erasure",
            "Art. 25 — Data protection by design",
            "Art. 30 — Records of processing activities",
            "Art. 32 — Security of processing",
        ],
    },
    "iran": {
        "name": "Iran Domestic",
        "name_fa": "قوانین و مصوبات داخلی",
        "scope": "Iran — electronic health records, national ID, SEPAS",
        "regulations": [
            "قانون جرایم رایانه‌ای — حفاظت از داده‌های شخصی",
            "مصوبات وزارت بهداشت — پرونده الکترونیک سلامت (EHR)",
            "SEPAS / IHIO — تبادل اطلاعات سلامت ملی",
            "بیمه سلامت / تأمین اجتماعی — الزامات گزارش‌دهی",
            "آیین‌نامه حفاظت از اطلاعات بیماران",
        ],
    },
}


REQUIREMENTS: list[ComplianceRequirement] = [
    ComplianceRequirement(
        "audit_trail", "all", "Access audit trail",
        "ثبت کامل دسترسی (چه کسی، چه زمانی، به چه داده‌ای)",
        "Every PHI access logged with user, timestamp, resource, patient_id",
        True, "AUDIT_ENABLED",
    ),
    ComplianceRequirement(
        "rbac", "all", "Role-based access control",
        "کنترل دسترسی مبتنی بر نقش",
        "JWT + RBAC with view_phi, export, delete permissions",
        True, None,
    ),
    ComplianceRequirement(
        "pseudonymization", "gdpr", "Pseudonymization",
        "شناسه‌سازی مجدد (pseudonymization)",
        "HMAC-based pseudonym map with reversible lookup for authorized users",
        True, "PSEUDONYMIZATION_SALT",
    ),
    ComplianceRequirement(
        "anonymization", "gdpr", "Anonymization",
        "ناشناس‌سازی (anonymization)",
        "Irreversible removal of identifiers from patient records",
        True, None,
    ),
    ComplianceRequirement(
        "retention", "all", "Data retention & auto-deletion",
        "سیاست نگهداری و حذف خودکار",
        "Configurable retention per data category with scheduled purge",
        True, "DATA_RETENTION_ENABLED",
    ),
    ComplianceRequirement(
        "erasure", "gdpr", "Right to erasure",
        "حق حذف (Right to erasure)",
        "Per-patient data deletion API with audit log",
        True, None,
    ),
    ComplianceRequirement(
        "consent", "gdpr", "Consent management",
        "مدیریت رضایت‌نامه",
        "Consent records with lawful basis and revocation",
        True, "REQUIRE_CONSENT_FOR_RESEARCH",
    ),
    ComplianceRequirement(
        "legal_hold", "hipaa", "Legal hold",
        "توقیف قانونی داده",
        "Suspend deletion for litigation or regulatory audit",
        True, None,
    ),
    ComplianceRequirement(
        "min_necessary", "hipaa", "Minimum necessary",
        "حداقل ضرورت",
        "view_phi permission gates direct patient identifier access",
        True, None,
    ),
    ComplianceRequirement(
        "national_id", "iran", "National ID (کد ملی) handling",
        "مدیریت کد ملی",
        "Not stored in analytics schema; FHIR parser strips before persist",
        True, None,
    ),
    ComplianceRequirement(
        "sepas", "iran", "SEPAS interoperability",
        "انطباق SEPAS",
        "FHIR profiles for MOH, Salamat, Tamin connectors",
        True, None,
    ),
    ComplianceRequirement(
        "encryption_transit", "hipaa", "Encryption in transit",
        "رمزنگاری در انتقال",
        "TLS required in production deployment",
        False, None,
    ),
    ComplianceRequirement(
        "encryption_rest", "hipaa", "Encryption at rest",
        "رمزنگاری در ذخیره‌سازی",
        "Fernet application-level PHI encryption + MinIO SSE",
        False, "PHI_ENCRYPTION_ENABLED",
    ),
    ComplianceRequirement(
        "mfa_admin", "hipaa", "MFA for admin",
        "احراز هویت دو مرحله‌ای برای مدیر",
        "TOTP-based MFA required for admin role",
        True, "MFA_REQUIRED_FOR_ADMIN",
    ),
    ComplianceRequirement(
        "rate_limiting", "all", "Rate limiting",
        "محدودیت نرخ درخواست",
        "Redis-backed rate limiting on API and login endpoints",
        True, "RATE_LIMIT_ENABLED",
    ),
    ComplianceRequirement(
        "waf", "all", "WAF protection",
        "فایروال اپلیکیشن وب",
        "Nginx + application WAF pattern blocking",
        True, "WAF_ENABLED",
    ),
    ComplianceRequirement(
        "secrets_management", "all", "Secrets management",
        "مدیریت امن اسرار",
        "Docker Secrets or HashiCorp Vault — not plain .env",
        True, "SECRETS_BACKEND",
    ),
]


def get_frameworks(active: str = "all") -> dict[str, Any]:
    if active == "all":
        return FRAMEWORKS
    return {active: FRAMEWORKS[active]} if active in FRAMEWORKS else FRAMEWORKS


def get_requirements(framework: str = "all") -> list[dict[str, Any]]:
    from barekat.config.settings import get_settings
    from barekat.security.phi_crypto import phi_encryption_active

    settings = get_settings()
    reqs = REQUIREMENTS
    if framework != "all":
        reqs = [r for r in reqs if r.framework in (framework, "all")]

    result = []
    for r in reqs:
        implemented = r.implemented
        if r.id == "encryption_transit":
            implemented = settings.tls_enabled or settings.is_production
        elif r.id == "encryption_rest":
            implemented = phi_encryption_active()
        elif r.id == "secrets_management":
            implemented = settings.secrets_backend in ("docker", "vault")
        elif r.id == "mfa_admin":
            implemented = settings.mfa_required_for_admin
        elif r.id == "rate_limiting":
            implemented = settings.rate_limit_enabled
        elif r.id == "waf":
            implemented = settings.waf_enabled
        result.append({
            "id": r.id,
            "framework": r.framework,
            "title": r.title,
            "title_fa": r.title_fa,
            "description": r.description,
            "implemented": implemented,
            "config_key": r.config_key,
        })
    return result


def compliance_summary(framework: str = "all") -> dict[str, Any]:
    reqs = get_requirements(framework)
    implemented = sum(1 for r in reqs if r["implemented"])
    return {
        "framework": framework,
        "frameworks": get_frameworks(framework),
        "requirements": reqs,
        "implemented_count": implemented,
        "total_count": len(reqs),
        "coverage_pct": round(implemented / len(reqs) * 100, 1) if reqs else 0,
    }
