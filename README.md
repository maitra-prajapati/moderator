# MODERATOR

**Explainable brand-governance checks with human approval**

MODERATOR helps a team review marketing copy **before publication**. A creator drafts content; MODERATOR checks it against an approved, versioned brand knowledge base; a reviewer approves it, asks for changes, or rejects it. Each finding explains what is wrong, identifies the relevant rule or source when available, and may suggest a correction. Revisions, decisions, and administrator overrides are recorded for auditability.

> **Round 2 MVP:** English **text** submissions for LinkedIn, website, and email. The bundled FlowPilot brand is **fictional**. Image/PDF analysis, automatic publication, and third-party fact verification are **not** part of the current MVP.

## Demo credentials and judge access

The following **fictional development accounts** match the frontend's bundled mock-mode accounts and password. They are proposed credentials for the live judge demo; **they will not work against the real backend until these same accounts and passwords are explicitly created there**.

| Access | Email | Demo password |
| --- | --- | --- |
| **Creator** | `creator@flowpilot.demo` | `DemoPass!1234` |
| **Reviewer** | `reviewer@flowpilot.demo` | `DemoPass!1234` |
| **Administrator (setup only)** | `admin@flowpilot.demo` | `DemoPass!1234` |

**Before judging:** Deploy the app and provide its working address through the submission platform. Create or reset these **demo-only** accounts in the real backend, enable their intended permissions, and grant `brand_flowpilot` access. Verify both creator and reviewer login in real API mode. Do not reuse this public demo password for production accounts, and do not give judges unrestricted administration access.

### Try the product without a walkthrough

1. Open the **deployed application** supplied with the submission. Sign in as **Creator** using the demo credentials above. There is no role-selection screen: permissions are assigned to each email account by the server.
2. Select **Submit / Edit**. Click **+ New draft**, choose **LinkedIn**, set the title to `Trial announcement`, and paste this deliberately incorrect sample:

   > Flow Pilot offers a 30-day free trial. Our results are 100% guaranteed!

3. Click **Create draft**, then **Submit for analysis**. Open the resulting findings in the panel on the **right**. Look for the brand-name mismatch (`Flow Pilot`), the unsupported trial duration (`30-day` instead of `14-day`), and the restricted guarantee (`100% guaranteed`). Check each explanation, severity, and evidence reference.
4. Replace the text with the compliant version below, click **Save new revision**, then **Submit for analysis** again. A suggested correction changes only the editable text until the creator explicitly saves it.

   > FlowPilot offers a 14-day free trial to help teams plan their work.

5. Sign out; sign in as **Reviewer**. Select **Findings / Review**, open the submission, inspect the latest revision, and choose **Approve revision** if no blockers remain. Alternatively, use **Request changes** with a written reason. A creator cannot review their own submission.
6. Open **History / Insights** to inspect revision-linked audit events and submission/findings/review totals. An administrator can also visit **Brand Knowledge** to inspect active rules and manage account permissions.

**Expected result:** The example progresses from **DRAFT → REVIEW_REQUIRED → revised DRAFT → REVIEW_REQUIRED → APPROVED**. A submission with unresolved blockers cannot receive ordinary approval; only an authorized administrator can approve an exception with a recorded reason.

**If no findings appear:** Confirm the active fictional brand knowledge has been seeded and the backend is running in **real mode**, not the frontend mock. The test example is specific to the bundled FlowPilot knowledge.

## Essential capabilities in this build

| Capability | What it does |
| --- | --- |
| Email-based authentication | JWT login with creator/reviewer/admin roles and editable per-user permissions; roles are not self-selected at sign-in. |
| Approved brand knowledge | Versioned FlowPilot voice traits, terminology rules, restricted phrases, approved facts, and cited sources. |
| Deterministic content analysis | Detects terminology, restricted-phrase, claim-mismatch, unsupported-claim, and tone-related findings without requiring a paid AI API. |
| Explanations and suggestions | Attaches severity, affected text span, explanation, evidence status and source identifiers where relevant, plus optional suggested replacement. |
| Revision-based review | Preserves earlier revisions, freezes content and knowledge versions during analysis, and separates creation from approval. |
| Human oversight | Reviewer comments/decisions, blocker checks, administrator overrides with required reasons, and audit history. |
| Insights | Read-only counts of submissions, findings, decisions, and overrides from authorized records. |
| Access boundaries | Server-side permissions and explicit brand grants; creators do not automatically see other users' drafts. |

### Current scope and limitations

- **Text only** and **English promotional copy**; LinkedIn, website, and email are channel labels, not publishing integrations.
- The knowledge and trial policy are **synthetic demonstration data**, not external fact checking. The seeded FlowPilot trial is **14 days**.
- No image/PDF ingestion, OCR, visual/logo checks, auto-publication, multi-organisation SSO, or automatic policy-change rescan yet.
- The React frontend has a **mock mode** for UI development. **A real judge demonstration must use the integrated FastAPI backend** with working database records and permissions. Mock-mode behavior is not evidence of live integration.
- A local server running on `localhost` is **not** a judge-accessible deployed link. The team must deploy and verify the live site before submission.

## Architecture

```text
React + Vite frontend (M5)
           |
      /api/v1 HTTPS
           |
FastAPI API and composition layer (M7)
  |          |           |          |          |
  M1         M2          M3         M4         M6
  Brand      JWT +       Workflow   Analysis   Analytics
  knowledge  permissions + audit    rules      summaries
  |          |           |
  +---- knowledge.sqlite  +--- workflow.sqlite
```

M7 coordinates the independent modules through JSON contracts. Analysis runs against a **frozen text revision** and **frozen knowledge version**; validated findings are stored before a revision becomes reviewable. An analysis failure is recorded and can be retried. The current deployment uses SQLite for the MVP.

### Technology and data

- **Frontend:** React 18, TypeScript, Vite, React Router.
- **Backend:** Python 3, FastAPI, Pydantic, SQLAlchemy, SQLite, JWT (`PyJWT`), Argon2 password hashing.
- **Checking:** deterministic rules and structured brand claims; no paid AI provider is required. Optional local AI work is not required for the core workflow.
- **Testing:** pytest with module and real-SQLite integration tests; Vitest/React Testing Library frontend tests.
- **Brand data:** fictional FlowPilot sample guidelines and trial policy, seeded locally by this project. No real customer data is required.

## Run locally (Windows PowerShell)

This setup assumes the **M7 integration additions** have been applied; in particular, `backend/app.py`, `backend/integration/m2_bridge.py` and `backend/integration/m3_bridge.py` must exist. Run the commands from the `moderator` repository root.

**1 — Install backend dependencies**

```powershell
python -m pip install -r backend\requirements.txt
```

**2 — Configure a private JWT signing secret for the backend terminal**

```powershell
$env:MODERATOR_JWT_SECRET = python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Use a stable secret in your deployed environment, not a new value on every restart. Do not place it in frontend `.env` files or commit it to Git.

**3 — Seed the fictional brand (safe to rerun)**

```powershell
python -m backend.modules.knowledge.seed
```

For a **brand-new database with no users**, create the first admin once:

```powershell
$env:MODERATOR_ADMIN_EMAIL = "admin@flowpilot.demo"
python -m backend.modules.auth.seed
```

The admin bootstrap refuses to run once any account exists. If you already have users, use the existing administrator instead. Add creator/reviewer accounts from the **Brand Knowledge → Accounts and permissions** admin UI, assign roles and privileges, and ensure brand grants have been configured. Grant the demo brand to existing accounts using:

```powershell
python -m backend.integration.grant_brand "admin@flowpilot.demo" brand_flowpilot
python -m backend.integration.grant_brand "creator@flowpilot.demo" brand_flowpilot
python -m backend.integration.grant_brand "reviewer@flowpilot.demo" brand_flowpilot
```

These are the proposed demo account emails. The grant command does **not** create accounts. First create the creator and reviewer through the administrator interface, choosing the demo password listed above; on a fresh database, bootstrap the admin with the same demo-only password if this is a disposable demonstration deployment. Make sure the designated reviewer has `can_review`, and `can_approve` if they should approve; the creator needs `can_create`.

**4 — Start FastAPI**

```powershell
python -m uvicorn backend.app:app --reload
```

Health check: <http://127.0.0.1:8000/api/v1/health>  
API documentation: <http://127.0.0.1:8000/docs>

**5 — Start the frontend in a second terminal**

```powershell
cd frontend
npm install
```

Create `frontend/.env.local` with:

```dotenv
VITE_API_MODE=real
VITE_API_BASE=http://127.0.0.1:8000/api/v1
```

Then start:

```powershell
npm run dev
```

Open <http://localhost:5173>. Use the demo emails and passwords above **only after provisioning them in the real backend**. The frontend's built-in mock accounts are not automatically created as backend users.

### Tests

From the repository root:

```powershell
$env:PYTHONPATH = "$PWD;$PWD\backend"
python -m pytest backend\tests -q
```

For M7 real SQLite integration tests only:

```powershell
python -m pytest backend\tests\e2e\test_real_m7.py -v
```

For the frontend, from `frontend`:

```powershell
npm run build
npm test
```

Test results must be rerun against the exact deployment/repository revision submitted for judging.

## Pre-submission deployment checklist

These are required to meet the **“open the link and use the product without help”** criterion:

- [ ] Provide a **working, judge-accessible deployment address** in the hackathon submission form and confirm that it opens without localhost or VPN.
- [ ] Deploy the **frontend and backend**; point the frontend's `VITE_API_BASE` to the deployed HTTPS API and configure CORS for the deployed frontend origin.
- [ ] Store the JWT secret and SQLite databases securely and **persistently** on the server; do not expose SQLite files, passwords, or environment variables.
- [ ] Seed the active FlowPilot knowledge, provision the creator and reviewer accounts, and grant them `brand_flowpilot` access.
- [ ] Provision and verify the listed creator/reviewer demo accounts in the **real backend**; rotate or restrict the published administrator demo account before wider use.
- [ ] Test the entire **creator → analysis → revision → reviewer approval → history** journey using a private/incognito window **without localhost or developer tools**.
- [ ] Verify the demo still works after server restart, and verify authorization errors for users without permissions.
- [ ] Remove/replace stale UI text that still says M6/M7 are pending, if present, and confirm analytics loads from the real API.
- [ ] Check the organiser's deployment, repository-access, video and submission requirements.

## Round 3: three substantial additions planned

These are **new capabilities**, not existing Round 2 features or visual-only changes:

1. **Image and PDF compliance review:** upload and inspect image/PDF assets; OCR marketing text; check approved logos/visual rules and accessibility (e.g., missing alt text/contrast); show findings tied to exact pages or image regions.
2. **Multi-stage collaborative approval:** assign submissions to multiple named reviewers; support threaded, revision-linked comments and in-app notifications; enforce sequential approval rules and preserve each decision in the audit log.
3. **Policy-change impact monitoring:** when an approved claim, rule, or source changes/expires, automatically identify and recheck impacted pending content; show before/after evidence, new blocker counts, and action-required alerts.


## Responsible design and attribution

- **Human control:** findings and suggestions do not auto-publish or silently modify a creator's text; reviewer actions are logged; blockers cannot be bypassed by ordinary approval.
- **Evidence discipline:** source-backed claims are distinguished from policy rules and unverified statements; missing support must not be presented as verified fact.
- **Security:** authenticate on the backend, enforce per-user permissions and brand scoping, hash passwords with Argon2, use expiring JWTs, and keep secrets out of the browser.
- **Transparency:** FlowPilot records, brand facts, test inputs and demo users are fictional. No commercial hosted AI model or paid inference API is needed for deterministic analysis.
- **Provenance:** see `MODERATOR_MASTER_BUILD_BLUEPRINT.md` for planned module ownership and product scope. Any third-party components, templates, or significant AI-assisted development should be disclosed accurately in the official submission and version history; individual contributions should be provided by the team rather than guessed here.

**Project status:** source-level M7 integration is available and tested with synthetic SQLite fixtures. The demo credentials listed above are mock-mode defaults and proposed backend demo credentials, **not verified live accounts**. Public deployment and an independent end-user check remain submission setup tasks until verified.
