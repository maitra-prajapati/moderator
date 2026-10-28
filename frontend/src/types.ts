export type Role = "creator" | "reviewer" | "admin";

export type Channel = "linkedin" | "website" | "email";

export type State =
  | "DRAFT"
  | "ANALYZING"
  | "ANALYSIS_FAILED"
  | "REVIEW_REQUIRED"
  | "CHANGES_REQUESTED"
  | "APPROVED"
  | "REJECTED";

export type Severity = "info" | "warning" | "blocker";

export type PermissionName = keyof Permissions;

export interface Permissions {
  can_create: boolean;
  can_review: boolean;
  can_approve: boolean;
  can_manage_knowledge: boolean;
  can_manage_users: boolean;
}

export interface User {
  user_id: string;
  email: string;
  role: Role;
  is_active: boolean;
  permissions: Permissions;
}

export interface AuthToken {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface Source {
  id: string;
  title: string;
  excerpt: string;
  valid_until: string | null;
}

export interface Rule {
  id: string;
  type: "terminology" | "restricted_phrase";
  pattern: string;
  replacement: string | null;
  severity: Severity;
  source_id: string | null;
}

export interface Claim {
  id: string;
  fact_key: string;
  value: number;
  unit: string;
  approved_text: string;
  source_id: string;
}

export interface Knowledge {
  brand_id: string;
  knowledge_version_id: string;
  version_no: number;
  activated_at: string;
  voice_traits: string[];
  sources: Source[];
  rules: Rule[];
  claims: Claim[];
}

export interface KnowledgeDraft {
  voice_traits: string[];
  sources: Source[];
  rules: Rule[];
  claims: Claim[];
}

export interface SubmissionCreate {
  brand_id: string;
  title: string;
  channel: Channel;
  text: string;
}

export interface Counts {
  blocker: number;
  warning: number;
  info: number;
}

export interface Submission {
  submission_id: string;
  brand_id: string;
  author_id: string;
  title: string;
  channel: Channel;
  state: State;
  current_revision_id: string;
  revision_no: number;
  knowledge_version_id: string;
  finding_counts: Counts;
  updated_at: string;
}

export interface SubmissionDetail extends Submission {
  text: string;
}

export interface SubmitResult extends Submission {
  request_id: string;
}

export interface Finding {
  finding_id: string;
  category:
    | "terminology"
    | "restricted_phrase"
    | "claim_mismatch"
    | "unsupported_claim"
    | "tone";
  severity: Severity;
  evidence_status:
    | "supported"
    | "contradicted"
    | "needs_verification"
    | "not_applicable";
  span: {
    start: number;
    end: number;
    quote: string;
  };
  rule_id: string | null;
  claim_id: string | null;
  source_id: string | null;
  knowledge_version_id: string;
  explanation: string;
  suggested_replacement: string | null;
  confidence_kind: "deterministic" | "ai_assisted";
  user_action?:
    | "acknowledge"
    | "accept_suggestion"
    | "dismiss"
    | null;
  action_reason?: string | null;
}

export interface FindingsResult {
  revision_id: string;
  knowledge_version_id: string | null;
  analysis_status:
    | "NOT_STARTED"
    | "ANALYZING"
    | "FAILED"
    | "COMPLETED";
  findings: Finding[];
}

export type Decision =
  | "approve"
  | "request_changes"
  | "reject"
  | "override_approve";

export interface ReviewResult {
  review_id: string;
  revision_id: string;
  decision: Decision;
  state: State;
  comment: string;
}

export interface AuditEvent {
  event_id: string;
  event_type: string;
  occurred_at: string;
  actor_id: string;
  submission_id: string;
  revision_id: string;
  knowledge_version_id: string | null;
  metadata: Record<string, unknown>;
}

export interface AnalyticsSummary {
  total: number;
  approved: number;
  reviewing: number;
  blockers: number;
}

export interface NewUser {
  email: string;
  password: string;
  role: Role;
}

export interface Api {
  login(email: string, password: string): Promise<AuthToken>;
  me(token: string): Promise<User>;

  users(token: string): Promise<User[]>;
  createUser(token: string, data: NewUser): Promise<User>;
  setPermissions(
    token: string,
    userId: string,
    changes: Partial<Permissions>
  ): Promise<User>;

  knowledge(token: string, brandId: string): Promise<Knowledge>;
  draftKnowledge(
    token: string,
    brandId: string,
    data: KnowledgeDraft
  ): Promise<{ version_no: number; knowledge_version_id: string }>;
  activateKnowledge(
    token: string,
    brandId: string,
    version: number
  ): Promise<Knowledge>;

  submissions(token: string): Promise<Submission[]>;
  submission(token: string, id: string): Promise<SubmissionDetail>;
  create(token: string, data: SubmissionCreate): Promise<Submission>;
  revise(token: string, id: string, text: string): Promise<Submission>;
  submit(token: string, id: string): Promise<SubmitResult>;

  findings(
    token: string,
    id: string,
    revisionId?: string
  ): Promise<FindingsResult>;

  findingAction(
    token: string,
    id: string,
    findingId: string,
    action: "acknowledge" | "accept_suggestion" | "dismiss",
    reason?: string
  ): Promise<void>;

  review(
    token: string,
    id: string,
    decision: Decision,
    comment: string
  ): Promise<ReviewResult>;

  history(token: string, id: string): Promise<AuditEvent[]>;
  analytics(token: string): Promise<AnalyticsSummary>;
}