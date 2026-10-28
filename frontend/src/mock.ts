import type {
  Api,
  AnalyticsSummary,
  AuditEvent,
  AuthToken,
  Decision,
  Finding,
  FindingsResult,
  Knowledge,
  KnowledgeDraft,
  NewUser,
  Permissions,
  ReviewResult,
  State,
  Submission,
  SubmissionCreate,
  SubmissionDetail,
  SubmitResult,
  User
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string
  ) {
    super(message);
  }
}

const error = (
  status: number,
  code: string,
  message: string
): never => {
  throw new ApiError(status, code, message);
};

const now = () => new Date().toISOString();
const clone = <T,>(x: T): T => structuredClone(x);

const defaults: Record<User["role"], Permissions> = {
  creator: {
    can_create: true,
    can_review: false,
    can_approve: false,
    can_manage_knowledge: false,
    can_manage_users: false
  },
  reviewer: {
    can_create: false,
    can_review: true,
    can_approve: true,
    can_manage_knowledge: false,
    can_manage_users: false
  },
  admin: {
    can_create: true,
    can_review: true,
    can_approve: true,
    can_manage_knowledge: true,
    can_manage_users: true
  }
};

const initialUsers: User[] = (
  ["creator", "reviewer", "admin"] as const
).map(role => ({
  user_id: `user_${role}`,
  email: `${role}@flowpilot.demo`,
  role,
  is_active: true,
  permissions: clone(defaults[role])
}));

export const demoPassword = "DemoPass!1234";

export const demoText =
  "Flow Pilot offers a 30-day free trial. " +
  "Security is 100% guaranteed!";

const demoKnowledge: Knowledge = {
  brand_id: "brand_flowpilot",
  knowledge_version_id: "kv_001",
  version_no: 1,
  activated_at: "2026-10-25T00:00:00Z",
  voice_traits: ["friendly", "professional", "precise"],
  sources: [
    {
      id: "src_trial",
      title: "Demo Trial Policy",
      excerpt: "FlowPilot offers a 14-day free trial.",
      valid_until: null
    },
    {
      id: "src_names",
      title: "Demo Brand Guide",
      excerpt: "Official product spelling: FlowPilot.",
      valid_until: null
    }
  ],
  rules: [
    {
      id: "rule_name",
      type: "terminology",
      pattern: "Flow Pilot",
      replacement: "FlowPilot",
      severity: "warning",
      source_id: "src_names"
    },
    {
      id: "rule_guarantee",
      type: "restricted_phrase",
      pattern: "100% guaranteed",
      replacement: null,
      severity: "blocker",
      source_id: null
    }
  ],
  claims: [
    {
      id: "claim_trial",
      fact_key: "free_trial_days",
      value: 14,
      unit: "days",
      approved_text: "14-day free trial",
      source_id: "src_trial"
    }
  ]
};

// Mock-only deterministic findings, not the real M4 engine.
function getFindings(
  text: string,
  version: string
): Finding[] {
  const output: Finding[] = [];

  const definitions = [
    {
      quote: "Flow Pilot",
      category: "terminology",
      severity: "warning",
      evidence_status: "not_applicable",
      rule_id: "rule_name",
      claim_id: null,
      source_id: "src_names",
      explanation: "Use the official product spelling: FlowPilot.",
      suggested_replacement: "FlowPilot"
    },
    {
      quote: "30-day free trial",
      category: "claim_mismatch",
      severity: "blocker",
      evidence_status: "contradicted",
      rule_id: null,
      claim_id: "claim_trial",
      source_id: "src_trial",
      explanation:
        "The approved free trial lasts 14 days, not 30 days.",
      suggested_replacement: "14-day free trial"
    },
    {
      quote: "100% guaranteed",
      category: "restricted_phrase",
      severity: "blocker",
      evidence_status: "not_applicable",
      rule_id: "rule_guarantee",
      claim_id: null,
      source_id: null,
      explanation:
        "Absolute guarantees are prohibited by the brand policy.",
      suggested_replacement: null
    }
  ] as const;

  definitions.forEach((def, index) => {
    let offset = 0;

    while (true) {
      const found = text
        .toLowerCase()
        .indexOf(def.quote.toLowerCase(), offset);

      if (found < 0) break;

      // Code-point offsets, matching the Python contract.
      const start = Array.from(text.slice(0, found)).length;
      const quote = text.slice(found, found + def.quote.length);

      output.push({
        finding_id: `find_${index}_${start}`,
        category: def.category,
        severity: def.severity,
        evidence_status: def.evidence_status,
        span: {
          start,
          end: start + Array.from(quote).length,
          quote
        },
        rule_id: def.rule_id,
        claim_id: def.claim_id,
        source_id: def.source_id,
        explanation: def.explanation,
        suggested_replacement: def.suggested_replacement,
        knowledge_version_id: version,
        confidence_kind: "deterministic",
        user_action: null
      });

      offset = found + def.quote.length;
    }
  });

  return output.sort((a, b) => a.span.start - b.span.start);
}

const count = (findings: Finding[]) => ({
  blocker: findings.filter(x => x.severity === "blocker").length,
  warning: findings.filter(x => x.severity === "warning").length,
  info: findings.filter(x => x.severity === "info").length
});

export interface MockApi extends Api {
  failNext(status: 401 | 403 | 409 | 422 | 500): void;
}

export function createMockApi(): MockApi {
  const users = clone(initialUsers);

  let knowledge = clone(demoKnowledge);

  let pending: {
    version: number;
    draft: KnowledgeDraft;
  } | null = null;

  const tokens = new Map<string, string>();
  const passwords = new Map(
    initialUsers.map(x => [x.email, demoPassword])
  );

  const items = new Map<string, SubmissionDetail>();
  const results = new Map<string, Finding[]>();
  const events = new Map<string, AuditEvent[]>();

  let serial = 1;

  let forced: 401 | 403 | 409 | 422 | 500 | null = null;

  const next = (prefix: string) =>
    `${prefix}_${String(serial++).padStart(4, "0")}`;

  const checkFailure = () => {
    if (forced !== null) {
      const status = forced;
      forced = null;

      const codes = {
        401: "UNAUTHENTICATED",
        403: "FORBIDDEN",
        409: "INVALID_TRANSITION",
        422: "INVALID_REQUEST",
        500: "SERVER_ERROR"
      } as const;

      error(
        status,
        codes[status],
        `Mock HTTP ${status} error`
      );
    }
  };

  const actor = (token: string): User => {
    checkFailure();

    const id = tokens.get(token);
    const u = users.find(x => x.user_id === id);

    if (!u || !u.is_active) {
      return error(
        401,
        "UNAUTHENTICATED",
        "Sign in to continue."
      );
    }

    return u;
  };

  const permission = (
    u: User,
    name: keyof Permissions
  ) => {
    if (!u.permissions[name]) {
      error(
        403,
        "FORBIDDEN",
        "You do not have permission for this action."
      );
    }
  };

  const one = (id: string): SubmissionDetail => {
    const s = items.get(id);

    if (!s) {
      return error(
        404,
        "SUBMISSION_NOT_FOUND",
        "Submission not found."
      );
    }

    return s;
  };

  const visible = (u: User, s: SubmissionDetail) => {
    if (
      u.user_id !== s.author_id &&
      !u.permissions.can_review &&
      !u.permissions.can_manage_users
    ) {
      error(
        403,
        "FORBIDDEN",
        "You cannot access this submission."
      );
    }
  };

  const owner = (u: User, s: SubmissionDetail) => {
    permission(u, "can_create");

    if (u.user_id !== s.author_id) {
      error(
        403,
        "FORBIDDEN",
        "Only the author can edit this submission."
      );
    }
  };

  const state = (
    s: SubmissionDetail,
    newState: State
  ) => {
    s.state = newState;
    s.updated_at = now();
  };

  const addEvent = (
    s: SubmissionDetail,
    type: string,
    id: string,
    metadata: Record<string, unknown> = {}
  ) => {
    const row: AuditEvent = {
      event_id: next("evt"),
      event_type: type,
      actor_id: id,
      occurred_at: now(),
      submission_id: s.submission_id,
      revision_id: s.current_revision_id,
      knowledge_version_id:
        s.knowledge_version_id || null,
      metadata
    };

    events.set(s.submission_id, [
      ...(events.get(s.submission_id) || []),
      row
    ]);
  };

  const clean = (
    s: SubmissionDetail
  ): Submission => {
    const { text: _text, ...summary } = s;
    void _text;
    return clone(summary);
  };

  const seed: SubmissionDetail = {
    submission_id: "sub_demo",
    brand_id: "brand_flowpilot",
    author_id: "user_creator",
    title: "Launch campaign",
    channel: "linkedin",
    state: "REVIEW_REQUIRED",
    current_revision_id: "rev_demo",
    revision_no: 1,
    knowledge_version_id: knowledge.knowledge_version_id,
    finding_counts: {
      blocker: 2,
      warning: 1,
      info: 0
    },
    updated_at: "2026-10-25T12:00:00Z",
    text: demoText
  };

  items.set(seed.submission_id, seed);

  results.set(
    seed.current_revision_id,
    getFindings(seed.text, seed.knowledge_version_id)
  );

  addEvent(seed, "content.created", seed.author_id);

  addEvent(
    seed,
    "content.analysis_completed",
    "system:m7",
    { finding_count: 3 }
  );

  return {
    failNext(status) {
      forced = status;
    },

    async login(email, password): Promise<AuthToken> {
      checkFailure();

      const u = users.find(
        x => x.email === email.trim().toLowerCase()
      );

      if (
        !u ||
        passwords.get(u.email) !== password ||
        !u.is_active
      ) {
        return error(
          401,
          "INVALID_CREDENTIALS",
          "Invalid email or password."
        );
      }

      const token =
        `mock-token-${u.user_id}-${next("session")}`;

      tokens.set(token, u.user_id);

      return {
        access_token: token,
        token_type: "bearer",
        expires_in: 1800
      };
    },

    async me(token) {
      return clone(actor(token));
    },

    async users(token) {
      const u = actor(token);
      permission(u, "can_manage_users");

      if (u.role !== "admin") {
        error(403, "FORBIDDEN", "Admin required.");
      }

      return clone(users);
    },

    async createUser(token, data: NewUser) {
      const u = actor(token);
      permission(u, "can_manage_users");

      if (u.role !== "admin") {
        error(403, "FORBIDDEN", "Admin required.");
      }

      if (
        !data.email.includes("@") ||
        data.password.length < 12
      ) {
        error(
          422,
          "INVALID_REQUEST",
          "Use a valid email and a password of at least 12 characters."
        );
      }

      if (
        users.some(
          x => x.email === data.email.toLowerCase()
        )
      ) {
        error(
          409,
          "EMAIL_IN_USE",
          "Email is already registered."
        );
      }

      const record: User = {
        user_id: next("user"),
        email: data.email.toLowerCase(),
        role: data.role,
        is_active: true,
        permissions: clone(defaults[data.role])
      };

      users.push(record);
      passwords.set(record.email, data.password);

      return clone(record);
    },

    async setPermissions(token, userId, changes) {
      const u = actor(token);
      permission(u, "can_manage_users");

      if (u.role !== "admin") {
        error(403, "FORBIDDEN", "Admin required.");
      }

      if (u.user_id === userId) {
        error(
          403,
          "SELF_MODIFICATION_FORBIDDEN",
          "Cannot edit own permissions."
        );
      }

      const other = users.find(
        x => x.user_id === userId
      );

      if (!other) {
        error(
          404,
          "USER_NOT_FOUND",
          "User not found."
        );
      }

      other.permissions = {
        ...other.permissions,
        ...changes
      };

      return clone(other);
    },

    async knowledge(token, brandId) {
      actor(token);

      if (brandId !== knowledge.brand_id) {
        error(
          404,
          "KNOWLEDGE_NOT_FOUND",
          "Brand not found."
        );
      }

      return clone(knowledge);
    },

    async draftKnowledge(token, brandId, draft) {
      const u = actor(token);
      permission(u, "can_manage_knowledge");

      if (brandId !== knowledge.brand_id) {
        error(
          404,
          "BRAND_NOT_FOUND",
          "Brand not found."
        );
      }

      pending = {
        version: knowledge.version_no + 1,
        draft: clone(draft)
      };

      return {
        version_no: pending.version,
        knowledge_version_id: `kv_${pending.version}`
      };
    },

    async activateKnowledge(token, brandId, version) {
      const u = actor(token);
      permission(u, "can_manage_knowledge");

      if (brandId !== knowledge.brand_id) {
        error(
          404,
          "BRAND_NOT_FOUND",
          "Brand not found."
        );
      }

      if (
        !pending ||
        pending.version !== version
      ) {
        error(
          409,
          "INVALID_TRANSITION",
          "No draft version to activate."
        );
      }

      knowledge = {
        ...clone(pending.draft),
        brand_id: brandId,
        knowledge_version_id: `kv_${version}`,
        version_no: version,
        activated_at: now()
      };

      pending = null;

      return clone(knowledge);
    },

    async submissions(token) {
      const u = actor(token);

      return Array.from(items.values())
        .filter(
          s =>
            s.author_id === u.user_id ||
            u.permissions.can_review ||
            u.permissions.can_manage_users
        )
        .map(clean);
    },

    async submission(token, id) {
      const u = actor(token);
      const s = one(id);

      visible(u, s);

      return clone(s);
    },

    async create(token, data: SubmissionCreate) {
      const u = actor(token);
      permission(u, "can_create");

      if (
        !data.text.trim() ||
        data.text.length > 10000 ||
        !data.title.trim() ||
        data.title.length > 200
      ) {
        error(
          422,
          "INVALID_REQUEST",
          "Title and text are required and must fit the allowed limits."
        );
      }

      const s: SubmissionDetail = {
        submission_id: next("sub"),
        current_revision_id: next("rev"),
        author_id: u.user_id,
        brand_id: data.brand_id,
        title: data.title,
        channel: data.channel,
        text: data.text,
        state: "DRAFT",
        revision_no: 1,
        knowledge_version_id: "",
        finding_counts: {
          blocker: 0,
          warning: 0,
          info: 0
        },
        updated_at: now()
      };

      items.set(s.submission_id, s);

      addEvent(
        s,
        "content.created",
        u.user_id
      );

      return clean(s);
    },

    async revise(token, id, text) {
      const u = actor(token);
      const s = one(id);

      owner(u, s);

      if (s.state === "ANALYZING") {
        error(
          409,
          "ANALYSIS_RUNNING",
          "Wait for analysis to finish."
        );
      }

      if (
        !text.trim() ||
        text.length > 10000
      ) {
        error(
          422,
          "INVALID_REQUEST",
          "Text must have 1–10,000 characters."
        );
      }

      if (text === s.text) {
        error(
          409,
          "UNCHANGED_TEXT",
          "Text has not changed."
        );
      }

      s.current_revision_id = next("rev");
      s.revision_no++;
      s.text = text;
      s.knowledge_version_id = "";

      s.finding_counts = {
        blocker: 0,
        warning: 0,
        info: 0
      };

      state(s, "DRAFT");

      addEvent(
        s,
        "content.revised",
        u.user_id
      );

      return clean(s);
    },

    async submit(token, id) {
      const u = actor(token);
      const s = one(id);

      owner(u, s);

      if (
        ![
          "DRAFT",
          "ANALYSIS_FAILED",
          "ANALYZING",
          "REVIEW_REQUIRED"
        ].includes(s.state)
      ) {
        error(
          409,
          "INVALID_TRANSITION",
          "Create a new revision before submitting."
        );
      }

      const req = next("req");

      if (
        s.state === "ANALYZING" ||
        s.state === "REVIEW_REQUIRED"
      ) {
        return {
          ...clean(s),
          request_id: req
        };
      }

      s.knowledge_version_id =
        knowledge.knowledge_version_id;

      state(s, "ANALYZING");

      addEvent(
        s,
        "content.submitted",
        u.user_id,
        { request_id: req }
      );

      // Fixture-only way to demonstrate failed analysis.
      if (s.text.includes("[analysis-fail]")) {
        state(s, "ANALYSIS_FAILED");

        addEvent(
          s,
          "content.analysis_failed",
          "system:mock"
        );
      } else {
        const fs = getFindings(
          s.text,
          s.knowledge_version_id
        );

        results.set(s.current_revision_id, fs);

        s.finding_counts = count(fs);

        state(s, "REVIEW_REQUIRED");

        addEvent(
          s,
          "content.analysis_completed",
          "system:mock",
          { finding_count: fs.length }
        );
      }

      return {
        ...clean(s),
        request_id: req
      };
    },

    async findings(token, id, revisionId) {
      const u = actor(token);
      const s = one(id);

      visible(u, s);

      if (
        revisionId &&
        revisionId !== s.current_revision_id
      ) {
        error(
          404,
          "REVISION_NOT_FOUND",
          "Only current revision findings available in demo."
        );
      }

      let analysisStatus:
        FindingsResult["analysis_status"] = "COMPLETED";

      if (s.state === "ANALYZING") {
        analysisStatus = "ANALYZING";
      } else if (s.state === "ANALYSIS_FAILED") {
        analysisStatus = "FAILED";
      } else if (s.state === "DRAFT") {
        analysisStatus = "NOT_STARTED";
      }

      return {
        revision_id: s.current_revision_id,
        knowledge_version_id:
          s.knowledge_version_id || null,
        analysis_status: analysisStatus,
        findings: clone(
          results.get(s.current_revision_id) || []
        )
      };
    },

    async findingAction(
      token,
      id,
      findingId,
      action,
      reason
    ) {
      const u = actor(token);
      const s = one(id);

      visible(u, s);

      if (s.state !== "REVIEW_REQUIRED") {
        error(
          409,
          "INVALID_TRANSITION",
          "Finding action requires review stage."
        );
      }

      if (
        s.author_id !== u.user_id &&
        !u.permissions.can_review
      ) {
        error(
          403,
          "FORBIDDEN",
          "Not permitted."
        );
      }

      if (
        action === "dismiss" &&
        !reason?.trim()
      ) {
        error(
          422,
          "INVALID_REQUEST",
          "Dismissal reason required."
        );
      }

      const f = (
        results.get(s.current_revision_id) || []
      ).find(
        x => x.finding_id === findingId
      );

      if (!f) {
        error(
          404,
          "FINDING_NOT_FOUND",
          "Finding not found."
        );
      }

      if (
        action === "accept_suggestion" &&
        !f.suggested_replacement
      ) {
        error(
          409,
          "NO_SUGGESTION",
          "No proposed replacement."
        );
      }

      f.user_action = action;
      f.action_reason = reason || null;

      addEvent(
        s,
        `finding.${action}`,
        u.user_id,
        { finding_id: findingId, reason }
      );
    },

    async review(
      token,
      id,
      decision: Decision,
      comment
    ): Promise<ReviewResult> {
      const u = actor(token);
      const s = one(id);

      permission(u, "can_review");

      if (s.author_id === u.user_id) {
        error(
          403,
          "SELF_REVIEW",
          "You cannot review your own submission."
        );
      }

      if (
        (decision === "approve" ||
          decision === "override_approve") &&
        !u.permissions.can_approve
      ) {
        error(
          403,
          "FORBIDDEN",
          "Approve permission required."
        );
      }

      if (s.state !== "REVIEW_REQUIRED") {
        error(
          409,
          "INVALID_TRANSITION",
          "Submission is not ready for review."
        );
      }

      const blockers = s.finding_counts.blocker;

      if (
        decision === "approve" &&
        blockers > 0
      ) {
        error(
          409,
          "OPEN_BLOCKERS",
          "Resolve blockers or use authorized override."
        );
      }

      if (
        decision === "override_approve" &&
        !(
          u.role === "admin" &&
          u.permissions.can_manage_knowledge &&
          u.permissions.can_approve
        )
      ) {
        error(
          403,
          "OVERRIDE_FORBIDDEN",
          "Authorized admin required."
        );
      }

      if (
        decision === "override_approve" &&
        blockers === 0
      ) {
        error(
          409,
          "NO_BLOCKERS",
          "Use normal approval instead."
        );
      }

      if (
        decision !== "approve" &&
        !comment.trim()
      ) {
        error(
          422,
          "INVALID_REQUEST",
          "Please explain this decision."
        );
      }

      const newState: State =
        decision === "approve" ||
        decision === "override_approve"
          ? "APPROVED"
          : decision === "reject"
          ? "REJECTED"
          : "CHANGES_REQUESTED";

      state(s, newState);

      addEvent(
        s,
        `review.${decision}`,
        u.user_id,
        {
          comment,
          override: decision === "override_approve"
        }
      );

      return {
        review_id: next("review"),
        revision_id: s.current_revision_id,
        decision,
        state: newState,
        comment
      };
    },

    async history(token, id) {
      const u = actor(token);
      const s = one(id);

      visible(u, s);

      return clone(events.get(id) || []);
    },

    async analytics(token): Promise<AnalyticsSummary> {
      const u = actor(token);

      const mine = Array.from(items.values()).filter(
        s =>
          s.author_id === u.user_id ||
          u.permissions.can_review ||
          u.permissions.can_manage_users
      );

      return {
        total: mine.length,
        approved: mine.filter(
          s => s.state === "APPROVED"
        ).length,
        reviewing: mine.filter(
          s => s.state === "REVIEW_REQUIRED"
        ).length,
        blockers: mine.reduce(
          (sum, s) =>
            sum + s.finding_counts.blocker,
          0
        )
      };
    }
  };
}