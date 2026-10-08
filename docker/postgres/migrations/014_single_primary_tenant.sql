-- Each user must have exactly one primary tenant. Migrations 009 and 013 both seeded the
-- 'clinician' user as primary in different tenants, making login tenant resolution ambiguous.
-- 013 is the intended assignment (tehran-general); demote the superseded 009 seed rows.
UPDATE tenant.tenant_users
SET is_primary = FALSE
WHERE username = 'clinician'
  AND tenant_id IN ('default', 'isfahan-medical');
