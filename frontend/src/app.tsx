import { useEffect, useState } from "react";
import {
  NavLink,
  Navigate,
  Route,
  Routes,
  useNavigate
} from "react-router-dom";

import {
  api as defaultApi,
  ApiError,
  MODE
} from "./api";

import { demoPassword } from "./mock";

import {
  locateFinding,
  replaceFinding
} from "./highlight";

import type {
  Api,
  AuditEvent,
  Channel,
  Decision,
  Finding,
  FindingsResult,
  Knowledge,
  NewUser,
  PermissionName,
  Permissions,
  Submission,
  SubmissionDetail,
  User
} from "./types";

type Props = {
  client?: Api;
};

type Screen = {
  api: Api;
  token: string;
  user: User;
  expired: () => void;
};

const brand = "brand_flowpilot";

const emptyDraft = {
  title: "",
  channel: "linkedin" as Channel,
  text: ""
};

const n = (value: string) =>
  value.replace(/_/g, " ").toLowerCase();

const pretty = (value: string) =>
  n(value).replace(/\b\w/g, c => c.toUpperCase());

const date = (value: string) =>
  new Date(value).toLocaleString();

const failed = (
  reason: unknown,
  expired: () => void
): string => {
  if (reason instanceof ApiError) {
    if (reason.status === 401) {
      expired();
    }

    return `${reason.message} (${reason.code})`;
  }

  return reason instanceof Error
    ? reason.message
    : "Unexpected error. Your draft is preserved.";
};

function Status({ value }: { value: string }) {
  return (
    <span className={`status status-${value.toLowerCase()}`}>
      {pretty(value)}
    </span>
  );
}

function Alert({ message }: { message: string }) {
  return (
    <p role="alert" className="alert">
      {message}
    </p>
  );
}

function Busy({ children }: { children: React.ReactNode }) {
  return (
    <p className="muted" role="status">
      {children}
    </p>
  );
}

/* =====================================================
   FINDING CARD
   ===================================================== */

export function FindingCard({
  finding,
  source,
  active,
  onClick
}: {
  finding: Finding;
  source?: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      className={`finding-card ${active ? "selected" : ""}`}
      onClick={onClick}
      aria-label={`${pretty(finding.severity)}: ${finding.span.quote}`}
    >
      <div className="finding-meta">
        <span className={`severity severity-${finding.severity}`}>
          {pretty(finding.severity)}
        </span>

        <span className="muted small">
          {pretty(finding.category)}
        </span>
      </div>

      <strong>{finding.span.quote}</strong>

      <span>{finding.explanation}</span>

      <span className="muted small">
        Evidence: {pretty(finding.evidence_status)}
      </span>

      <span className="muted small">
        Source: {source || "No verified source"}
      </span>

      {finding.suggested_replacement && (
        <span className="suggestion">
          Suggested: {finding.suggested_replacement}
        </span>
      )}

      {finding.user_action && (
        <span className="muted small">
          Action: {pretty(finding.user_action)}
        </span>
      )}
    </button>
  );
}

/* =====================================================
   UNICODE-SAFE HIGHLIGHT PREVIEW
   ===================================================== */

export function HighlightPreview({
  text,
  finding
}: {
  text: string;
  finding?: Finding;
}) {
  const span = finding
    ? locateFinding(text, finding)
    : null;

  return (
    <div
      className="preview"
      aria-label="Checked text preview"
    >
      {span ? (
        <>
          {text.slice(0, span.start)}
          <mark>
            {text.slice(span.start, span.end)}
          </mark>
          {text.slice(span.end)}
        </>
      ) : (
        text
      )}

      {finding && !span && (
        <p className="muted small">
          Quote could not be verified against this revision;
          no highlight was drawn.
        </p>
      )}

      {span?.fallback && (
        <p className="muted small">
          Unique-quote fallback used; please verify the location.
        </p>
      )}
    </div>
  );
}

/* =====================================================
   LOGIN / ROLE SCREEN
   ===================================================== */

function Login({
  api,
  onLogin
}: {
  api: Api;
  onLogin: (token: string, user: User) => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      const auth = await api.login(email, password);
      const user = await api.me(auth.access_token);

      onLogin(auth.access_token, user);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Login failed."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-layout">
      <section className="welcome">
        <div className="wordmark">
          <span className="logo">M</span>
          MODERATOR
        </div>

        <p className="eyebrow">
          BRAND GOVERNANCE WORKSPACE
        </p>

        <h1>
          Review with clarity.
          <br />
          Publish with confidence.
        </h1>

        <p>
          Draft brand content, inspect evidence-linked
          findings, and keep approval decisions traceable.
        </p>

        <div className="welcome-points">
          <span>01 &nbsp; Create</span>
          <span>02 &nbsp; Verify</span>
          <span>03 &nbsp; Approve</span>
        </div>
      </section>

      <section className="login-panel" aria-label="Sign in">
        <h2>Welcome back</h2>

        <p className="muted">
          Sign in using your assigned email.
          Permissions come from the server.
        </p>

        <form onSubmit={submit}>
          <label>
            Email address
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              autoComplete="username"
              placeholder="you@company.com"
            />
          </label>

          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </label>

          {error && <Alert message={error} />}

          <button
            className="primary full"
            type="submit"
            disabled={loading}
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        {MODE === "mock" && (
          <div className="demo-accounts">
            <p className="muted small">
              Mock mode only · Password:{" "}
              <code>{demoPassword}</code>
            </p>

            {(
              ["creator", "reviewer", "admin"] as const
            ).map(role => (
              <button
                key={role}
                type="button"
                className="pill"
                onClick={() => {
                  setEmail(`${role}@flowpilot.demo`);
                  setPassword(demoPassword);
                }}
              >
                Fill {pretty(role)} demo account
              </button>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

/* =====================================================
   MAIN NAVIGATION
   ===================================================== */

function Shell({
  user,
  onLogout,
  children
}: {
  user: User;
  onLogout: () => void;
  children: React.ReactNode;
}) {
  const links = [
    { to: "/editor", title: "Submit / Edit" },
    { to: "/review", title: "Findings / Review" },
    { to: "/knowledge", title: "Brand Knowledge" },
    { to: "/history", title: "History / Insights" }
  ];

  return (
    <div className="shell">
      <aside className="sidebar" aria-label="Main navigation">
        <div className="wordmark">
          <span className="logo">M</span>
          MODERATOR
        </div>

        <p className="sidebar-caption">WORKSPACE</p>

        <nav>
          {links.map(link => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                isActive
                  ? "nav-link active"
                  : "nav-link"
              }
            >
              {link.title}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <span className="muted small">
            {MODE === "mock"
              ? "Demo transport • offline-ready"
              : "FastAPI transport"}
          </span>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <span className="breadcrumb">
            FlowPilot Demo
            <span className="muted">
              {" "}/ Workspace
            </span>
          </span>

          <div className="account">
            <span className="account-text">
              <strong>{user.email}</strong>
              <small>
                {pretty(user.role)} · Assigned permissions
              </small>
            </span>

            <button
              onClick={onLogout}
              className="ghost"
            >
              Sign out
            </button>
          </div>
        </header>

        <div className="page">
          {children}
        </div>
      </div>
    </div>
  );
}

/* =====================================================
   UNSAVED TEXT RECOVERY
   ===================================================== */

const DRAFT_KEY = "moderator_m5_unsaved_copy";

function readDraft(): typeof emptyDraft {
  try {
    const raw = sessionStorage.getItem(DRAFT_KEY);

    if (!raw) return { ...emptyDraft };

    const data = JSON.parse(raw) as typeof emptyDraft;

    if (
      typeof data.text === "string" &&
      typeof data.title === "string" &&
      ["linkedin", "website", "email"].includes(data.channel)
    ) {
      return data;
    }

    return { ...emptyDraft };
  } catch {
    return { ...emptyDraft };
  }
}

/* =====================================================
   SUBMIT / EDIT SCREEN
   ===================================================== */

function EditorPage({
  api,
  token,
  user,
  expired
}: Screen) {
  const [form, setForm] = useState(readDraft);

  const [items, setItems] = useState<Submission[]>([]);

  const [selected, setSelected] =
    useState<SubmissionDetail | null>(null);

  const [result, setResult] =
    useState<FindingsResult | null>(null);

  const [knowledge, setKnowledge] =
    useState<Knowledge | null>(null);

  const [activeId, setActiveId] =
    useState<string | null>(null);

  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    sessionStorage.setItem(
      DRAFT_KEY,
      JSON.stringify(form)
    );
  }, [form]);

  useEffect(() => {
    api.submissions(token)
      .then(setItems)
      .catch(e => setError(failed(e, expired)));

    api.knowledge(token, brand)
      .then(setKnowledge)
      .catch(() => {});
  }, [api, token, expired]);

  const update = (
    field: keyof typeof form,
    value: string
  ) => {
    setForm(prev => ({
      ...prev,
      [field]: value
    }));
  };

  async function refresh(id: string) {
    const [detail, findings] = await Promise.all([
      api.submission(token, id),
      api.findings(token, id)
    ]);

    setSelected(detail);
    setResult(findings);
    setActiveId(null);

    setItems(await api.submissions(token));

    return detail;
  }

  async function open(id: string) {
    setLoading(true);
    setError("");
    setMessage("");

    try {
      const detail = await refresh(id);

      setForm({
        title: detail.title,
        channel: detail.channel,
        text: detail.text
      });
    } catch (e) {
      setError(failed(e, expired));
    } finally {
      setLoading(false);
    }
  }

  const newDraft = () => {
    setSelected(null);
    setResult(null);
    setActiveId(null);

    setForm({
      title: "",
      channel: "linkedin",
      text: ""
    });

    setMessage("New unsaved draft.");
    setError("");
  };

  const save = async () => {
    if (!form.title.trim() || !form.text.trim()) {
      setError("Title and content are required.");
      return;
    }

    if (Array.from(form.text).length > 10000) {
      setError("Maximum 10,000 characters.");
      return;
    }

    setLoading(true);
    setError("");
    setMessage("");

    try {
      if (selected) {
        if (selected.text === form.text) {
          setMessage("No changes to save.");
          return;
        }

        await api.revise(
          token,
          selected.submission_id,
          form.text
        );

        await refresh(selected.submission_id);

        setMessage(
          "New text revision saved. " +
          "Earlier approval does not carry over."
        );
      } else {
        const created = await api.create(token, {
          brand_id: brand,
          ...form
        });

        await refresh(created.submission_id);

        setMessage("Draft created successfully.");
      }
    } catch (e) {
      setError(failed(e, expired));
    } finally {
      setLoading(false);
    }
  };

  const submit = async () => {
    if (!selected) return;

    if (selected.text !== form.text) {
      setError(
        "Save your edited text as a new revision " +
        "before submitting."
      );
      return;
    }

    setLoading(true);
    setError("");
    setMessage("");

    try {
      const result = await api.submit(
        token,
        selected.submission_id
      );

      await refresh(selected.submission_id);

      setMessage(
        result.state === "ANALYZING"
          ? "Analysis requested. Refresh to check progress; " +
            "M7 is needed to complete analysis in real mode."
          : `Submission status: ${pretty(result.state)}.`
      );
    } catch (e) {
      setError(failed(e, expired));
    } finally {
      setLoading(false);
    }
  };

  const apply = async (finding: Finding) => {
    const changed = replaceFinding(
      form.text,
      finding
    );

    if (changed === null) {
      setError(
        "Cannot safely apply this quote to the current text."
      );
      return;
    }

    setForm(prev => ({
      ...prev,
      text: changed
    }));

    setMessage(
      "Suggestion inserted into your editable copy only. " +
      "Click Save revision to persist it."
    );

    if (
      selected &&
      selected.state === "REVIEW_REQUIRED"
    ) {
      try {
        await api.findingAction(
          token,
          selected.submission_id,
          finding.finding_id,
          "accept_suggestion"
        );
      } catch (e) {
        setError(failed(e, expired));
      }
    }
  };

  const findingAction = async (
    finding: Finding,
    action: "acknowledge" | "dismiss"
  ) => {
    if (!selected) return;

    setLoading(true);
    setError("");

    try {
      await api.findingAction(
        token,
        selected.submission_id,
        finding.finding_id,
        action,
        reason
      );

      await refresh(selected.submission_id);

      setMessage(`Finding ${action} recorded.`);
      setReason("");
    } catch (e) {
      setError(failed(e, expired));
    } finally {
      setLoading(false);
    }
  };

  const findings = result?.findings || [];

  const active =
    findings.find(f => f.finding_id === activeId) ||
    findings[0];

  const canEdit =
    user.permissions.can_create &&
    (!selected || selected.author_id === user.user_id);

  const canSubmit =
    canEdit &&
    !!selected &&
    ["DRAFT", "ANALYSIS_FAILED"].includes(selected.state) &&
    selected.text === form.text;

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">CREATOR WORKSPACE</p>

          <h1>Content Studio</h1>

          <p className="muted">
            Write on the left. Inspect exact issues and
            source evidence on the right.
          </p>
        </div>

        <button
          className="secondary"
          onClick={newDraft}
        >
          + New draft
        </button>
      </div>

      {error && <Alert message={error} />}

      {message && (
        <p className="success" role="status">
          {message}
        </p>
      )}

      <div className="editor-layout">
        <section
          className="panel editor-panel"
          aria-label="Content editor"
        >
          <div className="panel-head">
            <strong>Document</strong>

            {selected ? (
              <Status value={selected.state} />
            ) : (
              <span className="status">Unsaved</span>
            )}
          </div>

          <div className="field-row">
            <label>
              Title

              <input
                value={form.title}
                onChange={e =>
                  update("title", e.target.value)
                }
                disabled={!!selected || !canEdit}
                maxLength={200}
                placeholder="Campaign title"
              />
            </label>

            <label>
              Channel

              <select
                value={form.channel}
                disabled={!!selected || !canEdit}
                onChange={e =>
                  update("channel", e.target.value)
                }
              >
                <option value="linkedin">LinkedIn</option>
                <option value="website">Website</option>
                <option value="email">Email</option>
              </select>
            </label>
          </div>

          <label>
            Content

            <textarea
              aria-label="Content"
              rows={11}
              value={form.text}
              onChange={e =>
                update("text", e.target.value)
              }
              disabled={
                !canEdit ||
                selected?.state === "ANALYZING"
              }
              placeholder="Paste or write your campaign copy here…"
            />
          </label>

          <div className="editor-footer">
            <span className="muted small">
              {Array.from(form.text).length.toLocaleString()}
              {" "}/ 10,000 characters · Unicode characters
            </span>

            {selected && (
              <span className="muted small">
                Revision {selected.revision_no} ·{" "}
                {selected.current_revision_id}
              </span>
            )}
          </div>

          <div className="button-row">
            <button
              type="button"
              className="primary"
              onClick={save}
              disabled={
                !canEdit ||
                loading ||
                selected?.state === "ANALYZING"
              }
            >
              {selected
                ? "Save new revision"
                : "Create draft"}
            </button>

            <button
              type="button"
              className="secondary"
              onClick={submit}
              disabled={!canSubmit || loading}
            >
              Submit for analysis
            </button>

            {selected && (
              <button
                type="button"
                className="ghost"
                disabled={loading}
                onClick={() =>
                  open(selected.submission_id)
                }
              >
                Refresh status
              </button>
            )}
          </div>

          {selected && (
            <>
              <h3>Checked revision preview</h3>

              <HighlightPreview
                text={selected.text}
                finding={active}
              />

              <p className="muted small">
                Highlights are drawn only against the
                saved revision, not unsaved edits.
              </p>
            </>
          )}
        </section>

        <section
          className="panel findings-panel"
          aria-label="Findings and explanations"
        >
          <div className="panel-head">
            <strong>Analysis findings</strong>

            <span className="count-badge">
              {findings.length}
            </span>
          </div>

          {selected && (
            <div className="counts">
              <span>
                {selected.finding_counts.blocker} blocker
              </span>
              <span>
                {selected.finding_counts.warning} warning
              </span>
              <span>
                {selected.finding_counts.info} info
              </span>
            </div>
          )}

          {!selected ? (
            <div className="empty">
              Create a draft, or open an existing
              submission to inspect findings.
            </div>
          ) : selected.state === "ANALYZING" ? (
            <Busy>
              Analysis in progress.
              Refresh to check for new results.
            </Busy>
          ) : selected.state === "ANALYSIS_FAILED" ? (
            <Alert
              message={
                "Analysis failed. " +
                "You can resubmit this revision."
              }
            />
          ) : findings.length === 0 ? (
            <div className="empty">
              No findings available for this revision.
            </div>
          ) : (
            <div className="findings-scroll">
              {findings.map(f => (
                <FindingCard
                  key={f.finding_id}
                  finding={f}
                  active={
                    active?.finding_id === f.finding_id
                  }
                  onClick={() =>
                    setActiveId(f.finding_id)
                  }
                  source={
                    knowledge?.knowledge_version_id ===
                    f.knowledge_version_id
                      ? knowledge.sources.find(
                          s => s.id === f.source_id
                        )?.title
                      : undefined
                  }
                />
              ))}
            </div>
          )}

          {active && selected && (
            <div className="finding-actions">
              <h3>Selected finding</h3>

              <p className="muted small">
                Knowledge: {active.knowledge_version_id}
                {" "}· {active.confidence_kind}
              </p>

              {canEdit &&
                active.suggested_replacement && (
                  <button
                    className="secondary full"
                    onClick={() => apply(active)}
                  >
                    Use suggestion in editable copy
                  </button>
                )}

              {selected.state === "REVIEW_REQUIRED" &&
                (canEdit ||
                  user.permissions.can_review) && (
                  <>
                    <label>
                      Dismissal reason

                      <input
                        value={reason}
                        onChange={e =>
                          setReason(e.target.value)
                        }
                        placeholder="Required only to dismiss"
                      />
                    </label>

                    <div className="button-row">
                      <button
                        className="ghost"
                        disabled={loading}
                        onClick={() =>
                          findingAction(
                            active,
                            "acknowledge"
                          )
                        }
                      >
                        Acknowledge
                      </button>

                      <button
                        className="ghost"
                        disabled={
                          loading || !reason.trim()
                        }
                        onClick={() =>
                          findingAction(
                            active,
                            "dismiss"
                          )
                        }
                      >
                        Dismiss with reason
                      </button>
                    </div>
                  </>
                )}
            </div>
          )}
        </section>
      </div>

      <section className="panel recent">
        <div className="panel-head">
          <strong>My submissions</strong>

          <span className="muted small">
            {items.length} visible
          </span>
        </div>

        {!items.length ? (
          <div className="empty">
            No submissions yet.
          </div>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Revision</th>
                  <th>Status</th>
                  <th>Updated</th>
                  <th></th>
                </tr>
              </thead>

              <tbody>
                {items.map(s => (
                  <tr key={s.submission_id}>
                    <td>{s.title}</td>
                    <td>v{s.revision_no}</td>

                    <td>
                      <Status value={s.state} />
                    </td>

                    <td>{date(s.updated_at)}</td>

                    <td>
                      <button
                        className="text-btn"
                        onClick={() =>
                          open(s.submission_id)
                        }
                      >
                        Open
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}

/* =====================================================
   REVIEW DECISION FORM / ADMIN OVERRIDE MODAL
   ===================================================== */

export function DecisionForm({
  canApprove,
  canOverride,
  blockers,
  onSubmit
}: {
  canApprove: boolean;
  canOverride: boolean;
  blockers: number;
  onSubmit: (
    decision: Decision,
    comment: string
  ) => Promise<void>;
}) {
  const [comment, setComment] = useState("");
  const [pending, setPending] = useState(false);
  const [override, setOverride] = useState(false);
  const [localError, setLocalError] = useState("");

  const decide = async (decision: Decision) => {
    if (
      decision !== "approve" &&
      !comment.trim()
    ) {
      setLocalError(
        "A written reason is required."
      );
      return;
    }

    setPending(true);
    setLocalError("");

    try {
      await onSubmit(decision, comment);

      setComment("");
      setOverride(false);
    } catch (err) {
      setLocalError(
        err instanceof Error
          ? err.message
          : "Decision failed."
      );
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="decision-form">
      <label>
        Reviewer comment

        <textarea
          value={comment}
          onChange={e =>
            setComment(e.target.value)
          }
          rows={3}
          placeholder={
            "Explain the decision, " +
            "especially changes or rejection"
          }
        />
      </label>

      {localError && (
        <Alert message={localError} />
      )}

      <div className="button-row">
        <button
          className="primary"
          disabled={
            !canApprove ||
            blockers > 0 ||
            pending
          }
          onClick={() =>
            decide("approve")
          }
        >
          Approve revision
        </button>

        <button
          className="secondary"
          disabled={pending}
          onClick={() =>
            decide("request_changes")
          }
        >
          Request changes
        </button>

        <button
          className="ghost"
          disabled={pending}
          onClick={() =>
            decide("reject")
          }
        >
          Reject
        </button>
      </div>

      {blockers > 0 && (
        <p className="muted small">
          {blockers} blocker(s) prevent normal approval.
          Dismissing a finding does not waive a blocker.
        </p>
      )}

      {canOverride && blockers > 0 && (
        <button
          className="danger-outline"
          disabled={pending}
          onClick={() =>
            setOverride(true)
          }
        >
          Admin override…
        </button>
      )}

      {override && (
        <div className="modal-backdrop">
          <div
            className="override-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="Blocker override reason"
            onKeyDown={e => {
              if (e.key === "Escape") {
                setOverride(false);
              }
            }}
          >
            <h2>Approve despite blockers?</h2>

            <p>
              Override approval will be recorded in the
              audit trail for this exact revision.
            </p>

            <label>
              Mandatory override reason

              <textarea
                autoFocus
                rows={4}
                value={comment}
                onChange={e =>
                  setComment(e.target.value)
                }
              />
            </label>

            <div className="button-row">
              <button
                className="secondary"
                onClick={() =>
                  setOverride(false)
                }
              >
                Cancel
              </button>

              <button
                className="primary"
                disabled={
                  !comment.trim() ||
                  pending
                }
                onClick={() =>
                  decide("override_approve")
                }
              >
                Confirm override
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* =====================================================
   REVIEW QUEUE SCREEN
   ===================================================== */

function ReviewPage({
  api,
  token,
  user,
  expired
}: Screen) {
  const [queue, setQueue] =
    useState<Submission[]>([]);

  const [selection, setSelection] =
    useState<SubmissionDetail | null>(null);

  const [findings, setFindings] =
    useState<Finding[]>([]);

  const [filter, setFilter] =
    useState("REVIEW_REQUIRED");

  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const [knowledge, setKnowledge] =
    useState<Knowledge | null>(null);

  const refresh = async () =>
    setQueue(await api.submissions(token));

  useEffect(() => {
    refresh().catch(e =>
      setError(failed(e, expired))
    );

    api.knowledge(token, brand)
      .then(setKnowledge)
      .catch(() => {});
  }, [api, token, expired]);

  async function open(id: string) {
    setLoading(true);
    setError("");

    try {
      const [s, f] = await Promise.all([
        api.submission(token, id),
        api.findings(token, id)
      ]);

      setSelection(s);
      setFindings(f.findings);
    } catch (e) {
      setError(failed(e, expired));
    } finally {
      setLoading(false);
    }
  }

  const decide = async (
    decision: Decision,
    comment: string
  ) => {
    if (!selection) return;

    try {
      await api.review(
        token,
        selection.submission_id,
        decision,
        comment
      );

      await refresh();
      await open(selection.submission_id);

      setMessage(
        `${pretty(decision)} recorded for revision ` +
        `${selection.revision_no}.`
      );
    } catch (e) {
      setError(failed(e, expired));
      throw e;
    }
  };

  if (!user.permissions.can_review) {
    return (
      <>
        <div className="page-heading">
          <h1>Review queue</h1>
        </div>

        <Alert
          message="You do not have review permission."
        />
      </>
    );
  }

  const list = queue.filter(
    s =>
      filter === "ALL" ||
      s.state === filter
  );

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">HUMAN APPROVAL</p>
          <h1>Review Queue</h1>

          <p className="muted">
            Decisions apply to the current immutable revision.
          </p>
        </div>

        <label className="filter">
          Filter

          <select
            value={filter}
            onChange={e =>
              setFilter(e.target.value)
            }
          >
            <option value="REVIEW_REQUIRED">
              Awaiting review
            </option>
            <option value="ALL">All</option>
            <option value="APPROVED">Approved</option>
            <option value="CHANGES_REQUESTED">
              Changes requested
            </option>
            <option value="REJECTED">Rejected</option>
          </select>
        </label>
      </div>

      {error && <Alert message={error} />}

      {message && (
        <p className="success" role="status">
          {message}
        </p>
      )}

      <div className="review-layout">
        <section className="panel">
          <div className="panel-head">
            <strong>Submissions</strong>
            <span>{list.length}</span>
          </div>

          {list.length === 0 ? (
            <div className="empty">
              No submissions match this filter.
            </div>
          ) : (
            <div className="queue-list">
              {list.map(s => (
                <button
                  key={s.submission_id}
                  className={
                    `queue-item ${
                      selection?.submission_id ===
                      s.submission_id
                        ? "selected"
                        : ""
                    }`
                  }
                  onClick={() =>
                    open(s.submission_id)
                  }
                >
                  <strong>{s.title}</strong>

                  <span className="muted small">
                    Revision {s.revision_no} · {s.channel}
                  </span>

                  <span className="queue-footer">
                    <Status value={s.state} />
                    <span>
                      {s.finding_counts.blocker} blockers
                    </span>
                  </span>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="panel review-detail">
          <div className="panel-head">
            <strong>Review details</strong>
            {loading && (
              <Busy>Loading…</Busy>
            )}
          </div>

          {!selection ? (
            <div className="empty">
              Select a submission to review.
            </div>
          ) : (
            <>
              <h2>{selection.title}</h2>

              <div className="metadata">
                Revision {selection.revision_no} ·{" "}
                {selection.current_revision_id} ·{" "}
                <Status value={selection.state} />
              </div>

              <HighlightPreview
                text={selection.text}
                finding={findings[0]}
              />

              <h3>
                Findings ({findings.length})
              </h3>

              <div className="review-findings">
                {findings.map(f => (
                  <FindingCard
                    key={f.finding_id}
                    finding={f}
                    source={
                      knowledge?.knowledge_version_id ===
                      f.knowledge_version_id
                        ? knowledge.sources.find(
                            s => s.id === f.source_id
                          )?.title
                        : undefined
                    }
                  />
                ))}
              </div>

              {selection.state === "REVIEW_REQUIRED" &&
                selection.author_id !== user.user_id && (
                  <DecisionForm
                    canApprove={
                      user.permissions.can_approve
                    }
                    canOverride={
                      user.role === "admin" &&
                      user.permissions.can_approve &&
                      user.permissions.can_manage_knowledge
                    }
                    blockers={
                      selection.finding_counts.blocker
                    }
                    onSubmit={decide}
                  />
                )}

              {selection.author_id === user.user_id && (
                <Alert message="Self-review is not allowed." />
              )}
            </>
          )}
        </section>
      </div>
    </>
  );
}

/* =====================================================
   PERMISSIONS DISPLAY
   ===================================================== */

const permLabels: {
  id: PermissionName;
  label: string;
}[] = [
  { id: "can_create", label: "Create" },
  { id: "can_review", label: "Review" },
  { id: "can_approve", label: "Approve" },
  { id: "can_manage_knowledge", label: "Knowledge" },
  { id: "can_manage_users", label: "Manage users" }
];

export function PermissionGrid({
  value,
  disabled,
  onChange
}: {
  value: Permissions;
  disabled?: boolean;
  onChange: (
    name: PermissionName,
    checked: boolean
  ) => void;
}) {
  return (
    <div className="permission-grid">
      {permLabels.map(p => (
        <label key={p.id}>
          <input
            type="checkbox"
            checked={value[p.id]}
            disabled={disabled}
            onChange={e =>
              onChange(p.id, e.target.checked)
            }
          />

          {p.label}
        </label>
      ))}
    </div>
  );
}

/* =====================================================
   BRAND KNOWLEDGE / USER MANAGEMENT SCREEN
   ===================================================== */

function KnowledgePage({
  api,
  token,
  user,
  expired
}: Screen) {
  const [knowledge, setKnowledge] =
    useState<Knowledge | null>(null);

  const [users, setUsers] =
    useState<User[]>([]);

  const [draftVersion, setDraftVersion] =
    useState<number | null>(null);

  const [newUser, setNewUser] = useState<NewUser>({
    email: "",
    password: "",
    role: "creator"
  });

  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setKnowledge(
      await api.knowledge(token, brand)
    );

    if (
      user.role === "admin" &&
      user.permissions.can_manage_users
    ) {
      setUsers(
        await api.users(token)
      );
    }
  };

  useEffect(() => {
    load()
      .catch(e =>
        setError(failed(e, expired))
      )
      .finally(() =>
        setLoading(false)
      );
  }, [
    api,
    token,
    expired,
    user.role,
    user.permissions.can_manage_users
  ]);

  async function action(
    job: () => Promise<unknown>,
    msg: string
  ) {
    setError("");
    setMessage("");

    try {
      await job();
      setMessage(msg);
    } catch (e) {
      setError(failed(e, expired));
    }
  }

  async function createDraftVersion() {
    if (!knowledge) return;

    await action(async () => {
      const {
        voice_traits,
        sources,
        rules,
        claims
      } = knowledge;

      const draft = await api.draftKnowledge(
        token,
        brand,
        {
          voice_traits,
          sources,
          rules,
          claims
        }
      );

      setDraftVersion(draft.version_no);
    }, "Draft version created from current knowledge. Review it before activation.");
  }

  async function activateVersion() {
    if (draftVersion === null) return;

    await action(async () => {
      const latest = await api.activateKnowledge(
        token,
        brand,
        draftVersion
      );

      setKnowledge(latest);
      setDraftVersion(null);
    }, "New knowledge version activated.");
  }

  async function change(
    userId: string,
    key: PermissionName,
    checked: boolean
  ) {
    await action(async () => {
      const updated = await api.setPermissions(
        token,
        userId,
        { [key]: checked }
      );

      setUsers(old =>
        old.map(x =>
          x.user_id === userId
            ? updated
            : x
        )
      );
    }, "Permissions saved.");
  }

  async function addUser(event: React.FormEvent) {
    event.preventDefault();

    await action(async () => {
      const account = await api.createUser(
        token,
        newUser
      );

      setUsers(old => [
        ...old,
        account
      ]);

      setNewUser({
        email: "",
        password: "",
        role: "creator"
      });
    }, "Account created.");
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">VERSIONED BRAND POLICY</p>
          <h1>Brand Knowledge</h1>

          <p className="muted">
            Read approved policy, source evidence,
            and administer access.
          </p>
        </div>

        {knowledge && (
          <span className="version">
            Version {knowledge.version_no} · Active
          </span>
        )}
      </div>

      {error && <Alert message={error} />}

      {message && (
        <p className="success" role="status">
          {message}
        </p>
      )}

      {loading && (
        <Busy>Loading brand knowledge…</Busy>
      )}

      {knowledge && (
        <div className="knowledge-grid">
          <section className="panel">
            <h2>Approved references</h2>

            <p className="muted small">
              {knowledge.knowledge_version_id} ·
              activated {date(knowledge.activated_at)}
            </p>

            <h3>Voice traits</h3>

            <div className="tag-list">
              {knowledge.voice_traits.map(x => (
                <span className="tag" key={x}>
                  {x}
                </span>
              ))}
            </div>

            <h3>Sources</h3>

            {knowledge.sources.map(s => (
              <div
                className="knowledge-item"
                key={s.id}
              >
                <strong>{s.title}</strong>

                <p>{s.excerpt}</p>

                <small className="muted">
                  {s.id} ·{" "}
                  {s.valid_until ||
                    "No expiry recorded"}
                </small>
              </div>
            ))}
          </section>

          <section className="panel">
            <h2>Rules and factual claims</h2>

            <h3>Policy rules</h3>

            {knowledge.rules.map(r => (
              <div
                className="knowledge-item"
                key={r.id}
              >
                <span
                  className={`severity severity-${r.severity}`}
                >
                  {r.severity}
                </span>{" "}

                <strong>{r.pattern}</strong>

                <p className="muted">
                  {r.type} ·{" "}
                  {r.replacement
                    ? `Use ${r.replacement}`
                    : "Restricted wording"}
                </p>
              </div>
            ))}

            <h3>Approved facts</h3>

            {knowledge.claims.map(c => (
              <div
                className="knowledge-item"
                key={c.id}
              >
                <strong>{c.approved_text}</strong>

                <p className="muted">
                  {c.fact_key} ·
                  evidence: {c.source_id}
                </p>
              </div>
            ))}

            {user.permissions.can_manage_knowledge && (
              <div className="admin-tools">
                <h3>Version management</h3>

                <p className="muted small">
                  Creates an identical draft for demonstration.
                  A full policy editor belongs in later work.
                </p>

                <div className="button-row">
                  <button
                    className="secondary"
                    onClick={createDraftVersion}
                  >
                    Create draft from active
                  </button>

                  {draftVersion !== null && (
                    <button
                      className="primary"
                      onClick={activateVersion}
                    >
                      Activate version {draftVersion}
                    </button>
                  )}
                </div>
              </div>
            )}
          </section>
        </div>
      )}

      {user.role === "admin" &&
        user.permissions.can_manage_users && (
          <section className="panel account-admin">
            <h2>Accounts and permissions</h2>

            <p className="muted">
              Permissions are assigned to login emails,
              not selected on the sign-in page.
            </p>

            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Account</th>
                    <th>Role</th>
                    <th>Effective permissions</th>
                  </tr>
                </thead>

                <tbody>
                  {users.map(account => (
                    <tr key={account.user_id}>
                      <td>{account.email}</td>
                      <td>{pretty(account.role)}</td>

                      <td>
                        <PermissionGrid
                          value={
                            account.permissions
                          }
                          disabled={
                            account.user_id ===
                            user.user_id
                          }
                          onChange={(name, checked) =>
                            change(
                              account.user_id,
                              name,
                              checked
                            )
                          }
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <h3>Add account</h3>

            <form
              className="new-user-form"
              onSubmit={addUser}
            >
              <label>
                Email

                <input
                  type="email"
                  required
                  value={newUser.email}
                  onChange={e =>
                    setNewUser(p => ({
                      ...p,
                      email: e.target.value
                    }))
                  }
                />
              </label>

              <label>
                Password

                <input
                  type="password"
                  minLength={12}
                  required
                  value={newUser.password}
                  onChange={e =>
                    setNewUser(p => ({
                      ...p,
                      password: e.target.value
                    }))
                  }
                />
              </label>

              <label>
                Initial role

                <select
                  value={newUser.role}
                  onChange={e =>
                    setNewUser(p => ({
                      ...p,
                      role: e.target.value as NewUser["role"]
                    }))
                  }
                >
                  <option value="creator">Creator</option>
                  <option value="reviewer">Reviewer</option>
                  <option value="admin">Admin</option>
                </select>
              </label>

              <button
                className="primary"
                type="submit"
              >
                Create user
              </button>
            </form>
          </section>
        )}
    </>
  );
}

/* =====================================================
   REVISION HISTORY
   ===================================================== */

export function RevisionHistory({
  events,
  revisionId
}: {
  events: AuditEvent[];
  revisionId?: string;
}) {
  if (!events.length) {
    return (
      <div className="empty">
        No recorded events for this submission.
      </div>
    );
  }

  return (
    <ol className="timeline">
      {events.map(e => (
        <li
          key={e.event_id}
          className={
            revisionId &&
            e.revision_id === revisionId
              ? "timeline-current"
              : ""
          }
        >
          <strong>
            {pretty(
              e.event_type.replaceAll(".", " ")
            )}
          </strong>

          <time dateTime={e.occurred_at}>
            {date(e.occurred_at)}
          </time>

          <p className="muted small">
            Actor: {e.actor_id} ·
            Revision: {e.revision_id}
          </p>

          {typeof e.metadata.comment === "string" && (
            <p>{e.metadata.comment}</p>
          )}

          {typeof e.metadata.reason === "string" && (
            <p>{e.metadata.reason}</p>
          )}
        </li>
      ))}
    </ol>
  );
}

/* =====================================================
   HISTORY AND INSIGHTS SCREEN
   ===================================================== */

function HistoryPage({
  api,
  token,
  user,
  expired
}: Screen) {
  const [items, setItems] =
    useState<Submission[]>([]);

  const [selected, setSelected] =
    useState<Submission | null>(null);

  const [events, setEvents] =
    useState<AuditEvent[]>([]);

  const [metrics, setMetrics] = useState<{
    total: number;
    approved: number;
    reviewing: number;
    blockers: number;
  } | null>(null);

  const [
    metricsUnavailable,
    setMetricsUnavailable
  ] = useState(false);

  const [error, setError] = useState("");

  useEffect(() => {
    api.submissions(token)
      .then(setItems)
      .catch(e =>
        setError(failed(e, expired))
      );

    api.analytics(token)
      .then(setMetrics)
      .catch(e => {
        if (
          e instanceof ApiError &&
          e.status === 404
        ) {
          setMetricsUnavailable(true);
        } else {
          setError(failed(e, expired));
        }
      });
  }, [api, token, expired]);

  async function open(s: Submission) {
    setSelected(s);
    setError("");

    try {
      setEvents(
        await api.history(
          token,
          s.submission_id
        )
      );
    } catch (e) {
      setError(failed(e, expired));
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">
            TRANSPARENCY & INSIGHTS
          </p>

          <h1>History & Insights</h1>

          <p className="muted">
            Trace review actions to an exact
            content revision.
          </p>
        </div>
      </div>

      {error && <Alert message={error} />}

      {metrics ? (
        <div className="metric-grid">
          {(
            [
              ["Visible submissions", metrics.total],
              ["Approved", metrics.approved],
              ["Awaiting review", metrics.reviewing],
              [
                "Active blocker findings",
                metrics.blockers
              ]
            ] as const
          ).map(([label, val]) => (
            <div className="metric" key={label}>
              <span>{label}</span>
              <strong>{val}</strong>
            </div>
          ))}
        </div>
      ) : metricsUnavailable ? (
        <p className="muted">
          Analytics are not available on the real
          backend until M6/M7.
          Audit history remains accessible.
        </p>
      ) : (
        <Busy>Loading analytics…</Busy>
      )}

      <div className="review-layout">
        <section className="panel">
          <h2>Submissions</h2>

          {items.length ? (
            items.map(s => (
              <button
                key={s.submission_id}
                className="queue-item"
                onClick={() => open(s)}
              >
                <strong>{s.title}</strong>

                <span className="muted small">
                  Revision {s.revision_no}
                </span>

                <Status value={s.state} />
              </button>
            ))
          ) : (
            <div className="empty">
              No submissions visible to {user.role}.
            </div>
          )}
        </section>

        <section className="panel">
          <h2>Audit timeline</h2>

          {selected ? (
            <>
              <p className="muted">
                {selected.title} ·
                Current revision {selected.revision_no}
              </p>

              <RevisionHistory
                events={events}
                revisionId={
                  selected.current_revision_id
                }
              />
            </>
          ) : (
            <div className="empty">
              Choose a submission to inspect
              its complete audit trail.
            </div>
          )}
        </section>
      </div>
    </>
  );
}

/* =====================================================
   APP ROUTING AND AUTHENTICATED SESSION
   ===================================================== */

export default function App({
  client = defaultApi
}: Props) {
  const [session, setSession] = useState<{
    token: string;
    user: User;
  } | null>(null);

  const [
    expiredMessage,
    setExpiredMessage
  ] = useState("");

  const navigate = useNavigate();

  const logout = () => {
    setSession(null);
    navigate("/login");
  };

  const expired = () => {
    setExpiredMessage(
      "Session expired or account disabled. " +
      "Sign in again. Unsaved text is preserved in this tab."
    );

    logout();
  };

  const screens: Screen | null = session
    ? {
        api: client,
        token: session.token,
        user: session.user,
        expired
      }
    : null;

  return (
    <Routes>
      <Route
        path="/login"
        element={
          session ? (
            <Navigate
              to="/editor"
              replace
            />
          ) : (
            <>
              {expiredMessage && (
                <Alert
                  message={expiredMessage}
                />
              )}

              <Login
                api={client}
                onLogin={(token, user) => {
                  setExpiredMessage("");

                  setSession({
                    token,
                    user
                  });

                  navigate("/editor");
                }}
              />
            </>
          )
        }
      />

      <Route
        path="/*"
        element={
          !screens ? (
            <Navigate
              to="/login"
              replace
            />
          ) : (
            <Shell
              user={screens.user}
              onLogout={logout}
            >
              <Routes>
                <Route
                  path="editor"
                  element={
                    <EditorPage {...screens} />
                  }
                />

                <Route
                  path="review"
                  element={
                    <ReviewPage {...screens} />
                  }
                />

                <Route
                  path="knowledge"
                  element={
                    <KnowledgePage {...screens} />
                  }
                />

                <Route
                  path="history"
                  element={
                    <HistoryPage {...screens} />
                  }
                />

                <Route
                  path="*"
                  element={
                    <Navigate
                      to="/editor"
                      replace
                    />
                  }
                />
              </Routes>
            </Shell>
          )
        }
      />
    </Routes>
  );
}