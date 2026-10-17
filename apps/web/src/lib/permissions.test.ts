import { can } from "./permissions";

describe("can", () => {
  it("lets planners and admins manage config, viewers only read", () => {
    expect(can(["planner"], "config.manage")).toBe(true);
    expect(can(["viewer"], "config.manage")).toBe(false);
    expect(can(["viewer"], "config.read")).toBe(true);
    expect(can(["member"], "config.read")).toBe(false);
  });
  it("stacks roles", () => {
    expect(can(["member", "org_admin"], "members.manage")).toBe(true);
    expect(can(["planner"], "members.manage")).toBe(false);
  });
});
