import { landingPath } from "./landing";

describe("landingPath", () => {
  it("sends admins and planners without schedules to the wizard", () => {
    expect(
      landingPath({
        roles: ["planner"],
        scheduleIds: [],
        lastScheduleId: null,
      }),
    ).toBe("/setup");
  });
  it("prefers the last used schedule when it still exists", () => {
    expect(
      landingPath({
        roles: ["viewer"],
        scheduleIds: ["a", "b"],
        lastScheduleId: "b",
      }),
    ).toBe("/schedules/b/overview");
    expect(
      landingPath({
        roles: ["viewer"],
        scheduleIds: ["a"],
        lastScheduleId: "gone",
      }),
    ).toBe("/schedules/a/overview");
  });
  it("sends viewers without schedules to resources", () => {
    expect(
      landingPath({ roles: ["viewer"], scheduleIds: [], lastScheduleId: null }),
    ).toBe("/resources");
  });
});
