import { pendingReducer } from "./pending";

const move = (id: string, start: string) => ({
  activity_id: id,
  start_at: start,
  resources: {},
});

describe("pendingReducer", () => {
  it("adds, replaces an earlier move of the same activity, undoes and discards", () => {
    let s = pendingReducer([], { type: "add", change: move("x", "t1") });
    s = pendingReducer(s, { type: "add", change: move("y", "t2") });
    s = pendingReducer(s, { type: "add", change: move("x", "t3") });
    expect(s).toEqual([move("y", "t2"), move("x", "t3")]);
    s = pendingReducer(s, { type: "undo" });
    expect(s).toEqual([move("y", "t2")]);
    expect(pendingReducer(s, { type: "discard" })).toEqual([]);
  });
});
