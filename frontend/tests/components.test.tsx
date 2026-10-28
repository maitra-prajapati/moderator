import {
  describe,
  expect,
  it,
  vi
} from "vitest";

import {
  render,
  screen,
  fireEvent
} from "@testing-library/react";

import {
  MemoryRouter
} from "react-router-dom";

import App, {
  DecisionForm,
  FindingCard,
  PermissionGrid,
  RevisionHistory
} from "../src/app";

import {
  createMockApi
} from "../src/mock";

import type {
  Finding,
  Permissions
} from "../src/types";

const finding: Finding = {
  finding_id: "f1",
  category: "claim_mismatch",
  severity: "blocker",
  evidence_status: "contradicted",
  span: {
    start: 0,
    end: 17,
    quote: "30-day free trial"
  },
  rule_id: null,
  claim_id: "claim_trial",
  source_id: "src_trial",
  knowledge_version_id: "kv_001",
  explanation: "Approved trial is 14 days.",
  suggested_replacement: "14-day free trial",
  confidence_kind: "deterministic"
};

describe("M5 components and screens", () => {
  it("shows finding severity, evidence, source and suggestion", () => {
    render(
      <FindingCard
        finding={finding}
        source="Trial Policy"
      />
    );

    expect(
      screen.getByText("Blocker")
    ).toBeInTheDocument();

    expect(
      screen.getByText(/Evidence: Contradicted/)
    ).toBeInTheDocument();

    expect(
      screen.getByText(/Trial Policy/)
    ).toBeInTheDocument();

    expect(
      screen.getByText(/Suggested: 14-day free trial/)
    ).toBeInTheDocument();
  });

  it("shows checkboxes reflecting exact permissions", () => {
    const perms: Permissions = {
      can_create: true,
      can_review: false,
      can_approve: false,
      can_manage_knowledge: false,
      can_manage_users: false
    };

    render(
      <PermissionGrid
        value={perms}
        onChange={vi.fn()}
      />
    );

    expect(
      screen.getByLabelText("Create")
    ).toBeChecked();

    expect(
      screen.getByLabelText("Approve")
    ).not.toBeChecked();
  });

  it("blocks normal approve on blockers and requires override comment", async () => {
    const fn = vi.fn().mockResolvedValue(undefined);

    render(
      <DecisionForm
        canApprove
        canOverride
        blockers={2}
        onSubmit={fn}
      />
    );

    expect(
      screen.getByText("Approve revision")
    ).toBeDisabled();

    fireEvent.click(
      screen.getByText("Admin override…")
    );

    expect(
      screen.getByRole("dialog", {
        name: /Blocker override reason/
      })
    ).toBeInTheDocument();

    expect(
      screen.getByText("Confirm override")
    ).toBeDisabled();

    fireEvent.change(
      screen.getByLabelText(
        "Mandatory override reason"
      ),
      {
        target: {
          value: "Reviewed evidence"
        }
      }
    );

    fireEvent.click(
      screen.getByText("Confirm override")
    );

    expect(fn).toHaveBeenCalledWith(
      "override_approve",
      "Reviewed evidence"
    );
  });

  it("displays revision-specific event history", () => {
    render(
      <RevisionHistory
        revisionId="rev_1"
        events={[
          {
            event_id: "evt_1",
            event_type: "review.approved",
            occurred_at: "2026-10-25T00:00:00Z",
            actor_id: "user_reviewer",
            submission_id: "sub_1",
            revision_id: "rev_1",
            knowledge_version_id: "kv_1",
            metadata: {
              comment: "Approved evidence"
            }
          }
        ]}
      />
    );

    expect(
      screen.getByText("Approved evidence")
    ).toBeInTheDocument();

    expect(
      screen.getByText(/Revision: rev_1/)
    ).toBeInTheDocument();
  });

  it("starts with a role-free email/password login", () => {
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <App client={createMockApi()} />
      </MemoryRouter>
    );

    expect(
      screen.getByLabelText("Email address")
    ).toBeInTheDocument();

    expect(
      screen.getByLabelText("Password")
    ).toBeInTheDocument();

    expect(
      screen.queryByLabelText(
        "Sign in as admin"
      )
    ).not.toBeInTheDocument();
  });
});

it("runs the mocked creator create → submit → inspect journey", async () => {
  const { findByText } = render(
    <MemoryRouter initialEntries={["/login"]}>
      <App client={createMockApi()} />
    </MemoryRouter>
  );

  fireEvent.click(
    screen.getByText(
      "Fill Creator demo account"
    )
  );

  fireEvent.click(
    screen.getByRole("button", {
      name: "Sign in"
    })
  );

  expect(
    await findByText("Content Studio")
  ).toBeInTheDocument();

  fireEvent.change(
    screen.getByLabelText("Title"),
    {
      target: {
        value: "New marketing copy"
      }
    }
  );

  fireEvent.change(
    screen.getByLabelText("Content"),
    {
      target: {
        value:
          "Flow Pilot offers a 30-day free trial."
      }
    }
  );

  fireEvent.click(
    screen.getByRole("button", {
      name: "Create draft"
    })
  );

  expect(
    await findByText(/Draft created successfully/)
  ).toBeInTheDocument();

  fireEvent.click(
    screen.getByRole("button", {
      name: "Submit for analysis"
    })
  );

  expect(
    await findByText(
      /Submission status: Review Required/
    )
  ).toBeInTheDocument();

  expect(
    await findByText("Analysis findings")
  ).toBeInTheDocument();

  expect(
    screen.getAllByText("Flow Pilot").length
  ).toBeGreaterThan(0);
});