import {
  describe,
  expect,
  it
} from "vitest";

import {
  createMockApi,
  demoPassword,
  demoText
} from "../src/mock";

async function token(
  api: ReturnType<typeof createMockApi>,
  role: "creator" | "reviewer" | "admin"
) {
  return (
    await api.login(
      `${role}@flowpilot.demo`,
      demoPassword
    )
  ).access_token;
}

describe(
  "mock transport reproduces B contracts and backend failures",
  () => {
    it("logs in by email without client role selection", async () => {
      const api = createMockApi();

      const t = await token(api, "creator");

      expect(
        (await api.me(t)).permissions.can_approve
      ).toBe(false);

      await expect(
        api.login(
          "creator@flowpilot.demo",
          "wrong"
        )
      ).rejects.toMatchObject({
        status: 401
      });
    });

    it("supports draft, analysis, revision and reviewer override", async () => {
      const api = createMockApi();

      const creator = await token(api, "creator");
      const admin = await token(api, "admin");

      const sub = await api.create(
        creator,
        {
          brand_id: "brand_flowpilot",
          title: "Demo",
          channel: "linkedin",
          text: demoText
        }
      );

      expect(sub.state).toBe("DRAFT");

      expect(
        (
          await api.submit(
            creator,
            sub.submission_id
          )
        ).state
      ).toBe("REVIEW_REQUIRED");

      expect(
        (
          await api.findings(
            creator,
            sub.submission_id
          )
        ).findings
      ).toHaveLength(3);

      await expect(
        api.review(
          creator,
          sub.submission_id,
          "approve",
          ""
        )
      ).rejects.toMatchObject({
        status: 403
      });

      await expect(
        api.review(
          admin,
          sub.submission_id,
          "approve",
          ""
        )
      ).rejects.toMatchObject({
        code: "OPEN_BLOCKERS"
      });

      expect(
        (
          await api.review(
            admin,
            sub.submission_id,
            "override_approve",
            "Demo acceptance"
          )
        ).state
      ).toBe("APPROVED");

      const revised = await api.revise(
        creator,
        sub.submission_id,
        "FlowPilot has a 14-day free trial."
      );

      expect(revised.revision_no).toBe(2);
      expect(revised.state).toBe("DRAFT");
    });

    it("simulates 401 403 409 422 500 deterministically", async () => {
      const api = createMockApi();

      const t = await token(api, "admin");

      for (
        const status of [
          401,
          403,
          409,
          422,
          500
        ] as const
      ) {
        api.failNext(status);

        await expect(
          api.submissions(t)
        ).rejects.toMatchObject({
          status
        });
      }
    });

    it("rejects unprivileged user management", async () => {
      const api = createMockApi();

      const creator = await token(
        api,
        "creator"
      );

      await expect(
        api.users(creator)
      ).rejects.toMatchObject({
        status: 403
      });
    });
  }
);