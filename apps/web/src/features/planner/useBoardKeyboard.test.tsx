import { act, renderHook } from "@testing-library/react";

import { useBoardKeyboard } from "./useBoardKeyboard";

const item = {
  activityId: "a1",
  name: "CS 201",
  start: "2026-01-12T06:00:00.000Z",
  resources: {},
  pending: false,
  pinned: false,
};

function setup(carrying = false) {
  const handlers = {
    onOpen: vi.fn(),
    onPickUp: vi.fn(),
    onTarget: vi.fn(),
    onDrop: vi.fn(),
    onCancel: vi.fn(),
  };
  const hook = renderHook(
    ({ carrying: c }: { carrying: boolean }) =>
      useBoardKeyboard({
        rowCount: 2,
        colCount: 2,
        itemAt: (r, c2) => (r === 0 && c2 === 1 ? item : undefined),
        ...handlers,
        carrying: c,
      }),
    { initialProps: { carrying } },
  );
  const press = (key: string) => {
    act(() => {
      hook.result.current.onKeyDown({
        key,
        preventDefault: vi.fn(),
      } as unknown as React.KeyboardEvent);
    });
  };
  return { hook, handlers, press };
}

describe("useBoardKeyboard", () => {
  it("moves with arrows and clamps at the edges", () => {
    const { hook, press } = setup();
    press("ArrowLeft");
    expect(hook.result.current.focus).toEqual({ r: 0, c: 0 });
    press("ArrowRight");
    press("ArrowRight");
    press("ArrowRight");
    expect(hook.result.current.focus).toEqual({ r: 0, c: 1 });
    press("Home");
    expect(hook.result.current.focus).toEqual({ r: 0, c: 0 });
    press("End");
    press("ArrowDown");
    press("ArrowDown");
    expect(hook.result.current.focus).toEqual({ r: 1, c: 1 });
  });

  it("opens only cells with an item", () => {
    const { handlers, press } = setup();
    press("Enter");
    expect(handlers.onOpen).not.toHaveBeenCalled();
    press("ArrowRight");
    press("Enter");
    expect(handlers.onOpen).toHaveBeenCalledWith(0, 1);
  });

  it("picks up, targets, drops and cancels", () => {
    const { hook, handlers, press } = setup();
    press("ArrowRight");
    press(" ");
    expect(handlers.onPickUp).toHaveBeenCalledWith(0, 1);
    hook.rerender({ carrying: true });
    press("ArrowDown");
    expect(handlers.onTarget).toHaveBeenCalledWith(1, 1);
    press(" ");
    expect(handlers.onDrop).toHaveBeenCalledWith(1, 1);
    press("Escape");
    expect(handlers.onCancel).toHaveBeenCalledOnce();
  });
});
