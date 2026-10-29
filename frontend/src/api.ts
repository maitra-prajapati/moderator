import type {
  Api,
  AnalyticsSummary,
  AuthToken,
  AuditEvent,
  Decision,
  FindingsResult,
  Knowledge,
  KnowledgeDraft,
  NewUser,
  Permissions,
  ReviewResult,
  Submission,
  SubmissionCreate,
  SubmissionDetail,
  SubmitResult,
  User
} from "./types";

import {
  ApiError,
  createMockApi
} from "./mock";

export const MODE = "real";

const BASE =
  "https://moderator-eight-beta.vercel.app/api/v1";


const path = (s: string) => encodeURIComponent(s);

async function request<T>(
  endpoint: string,
  token?: string,
  method = "GET",
  data?: unknown
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(BASE + endpoint, {
      method,
      headers: {
        ...(data === undefined
          ? {}
          : { "Content-Type": "application/json" }),
        ...(token
          ? { Authorization: `Bearer ${token}` }
          : {})
      },
      ...(data === undefined
        ? {}
        : { body: JSON.stringify(data) })
    });
  } catch {
    throw new ApiError(
      503,
      "OFFLINE",
      "Cannot reach FastAPI. Your unsaved text has been kept."
    );
  }

  let body: unknown;

  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    const obj =
      body && typeof body === "object"
        ? (body as Record<string, unknown>)
        : {};

    const err = (
      obj.error && typeof obj.error === "object"
        ? obj.error
        : obj.detail
    ) as Record<string, unknown> | undefined;

    throw new ApiError(
      response.status,
      typeof err?.code === "string"
        ? err.code
        : `HTTP_${response.status}`,
      typeof err?.message === "string"
        ? err.message
        : `Request failed (${response.status}).`
    );
  }

  return body as T;
}

function realApi(): Api {
  return {
    login: (email, password): Promise<AuthToken> =>
      request(
        "/auth/login",
        undefined,
        "POST",
        { email, password }
      ),

    me: token =>
      request<User>("/auth/me", token),

    users: token =>
      request<User[]>("/admin/users", token),

    createUser: (token, user: NewUser) =>
      request<User>(
        "/admin/users",
        token,
        "POST",
        user
      ),

    setPermissions: (
      token,
      id,
      permissions: Partial<Permissions>
    ) =>
      request<User>(
        `/admin/users/${path(id)}/permissions`,
        token,
        "PATCH",
        permissions
      ),

    knowledge: (token, brandId) =>
      request<Knowledge>(
        `/brands/${path(brandId)}/knowledge`,
        token
      ),

    draftKnowledge: (
      token,
      brandId,
      draft: KnowledgeDraft
    ) =>
      request(
        `/brands/${path(brandId)}/knowledge`,
        token,
        "POST",
        draft
      ),

    activateKnowledge: (
      token,
      brandId,
      version
    ) =>
      request(
        `/brands/${path(brandId)}/knowledge/${version}/activate`,
        token,
        "POST"
      ),

    submissions: token =>
      request<Submission[]>("/submissions", token),

    submission: (token, id) =>
      request<SubmissionDetail>(
        `/submissions/${path(id)}`,
        token
      ),

    create: (token, data: SubmissionCreate) =>
      request<Submission>(
        "/submissions",
        token,
        "POST",
        data
      ),

    revise: (token, id, text) =>
      request<Submission>(
        `/submissions/${path(id)}/revisions`,
        token,
        "POST",
        { text }
      ),

    submit: (token, id) =>
      request<SubmitResult>(
        `/submissions/${path(id)}/submit`,
        token,
        "POST"
      ),

    findings: (token, id, revisionId) =>
      request<FindingsResult>(
        `/submissions/${path(id)}/findings${
          revisionId
            ? `?revision_id=${path(revisionId)}`
            : ""
        }`,
        token
      ),

    findingAction: (
      token,
      id,
      findingId,
      action,
      reason
    ) =>
      request<void>(
        `/submissions/${path(id)}/findings/${path(findingId)}/actions`,
        token,
        "POST",
        {
          action,
          reason: reason || null
        }
      ),

    review: (
      token,
      id,
      decision: Decision,
      comment: string
    ): Promise<ReviewResult> =>
      request(
        `/submissions/${path(id)}/reviews`,
        token,
        "POST",
        { decision, comment }
      ),

    history: (
      token,
      id
    ): Promise<AuditEvent[]> =>
      request(
        `/submissions/${path(id)}/history`,
        token
      ),

    // This route belongs to M6 and is not yet present
    // in your current FastAPI application.
    analytics: (
      token
    ): Promise<AnalyticsSummary> =>
      request(
        "/analytics/summary",
        token
      )
  };
}

export const api: Api =
  MODE === "mock"
    ? createMockApi()
    : realApi();

export { ApiError };
