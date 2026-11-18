import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { Alert, Badge, Button, Field, Segmented, Stepper, ToastProvider } from "../src/components/ui";
import { clamp, pct, riskFromScore, taskName } from "../src/lib/format";

const wrap = (ui: React.ReactNode) => render(<MemoryRouter><ToastProvider>{ui}</ToastProvider></MemoryRouter>);

describe("format helpers", () => {
  it("formats percentages", () => { expect(pct(0.9123)).toBe("91%"); expect(pct(0.9123, 1)).toBe("91.2%"); });
  it("maps scores to risk bands", () => {
    expect(riskFromScore(0.1)).toBe("low"); expect(riskFromScore(0.5)).toBe("moderate"); expect(riskFromScore(0.9)).toBe("high");
  });
  it("clamps", () => { expect(clamp(5, 0, 1)).toBe(1); expect(clamp(-1, 0, 1)).toBe(0); });
  it("names tasks", () => { expect(taskName("heart")).toBe("Heart disease"); expect(taskName("t1d")).toBe("Type 1 pattern"); });
});

describe("ui primitives", () => {
  it("Button fires onClick and shows loading state as disabled", () => {
    const fn = vi.fn();
    const { rerender } = wrap(<Button onClick={fn}>Go</Button>);
    fireEvent.click(screen.getByRole("button", { name: "Go" })); expect(fn).toHaveBeenCalledTimes(1);
    rerender(<MemoryRouter><ToastProvider><Button loading onClick={fn}>Go</Button></ToastProvider></MemoryRouter>);
    expect(screen.getByRole("button")).toBeDisabled();
  });
  it("Field shows an accessible error", () => {
    wrap(<Field label="Age" htmlFor="a" error="Required"><input id="a" /></Field>);
    expect(screen.getByRole("alert")).toHaveTextContent("Required"); expect(screen.getByLabelText("Age")).toBeInTheDocument();
  });
  it("Segmented reports selection with aria-pressed", () => {
    const fn = vi.fn();
    wrap(<Segmented label="Sex" value="m" onChange={fn} options={[{ value: "m", label: "Male" }, { value: "f", label: "Female" }]} />);
    expect(screen.getByRole("button", { name: "Male" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "Female" })); expect(fn).toHaveBeenCalledWith("f");
  });
  it("Stepper marks the current step", () => {
    wrap(<Stepper steps={["A", "B", "C"]} current={1} />);
    expect(screen.getByText("B").closest(".step")).toHaveAttribute("aria-current", "step");
  });
  it("Alert and Badge render content", () => {
    wrap(<><Alert tone="warn" title="Careful">text</Alert><Badge tone="high">High</Badge></>);
    expect(screen.getByText("Careful")).toBeInTheDocument(); expect(screen.getByText("High")).toBeInTheDocument();
  });
});

describe("cad task", () => {
  it("names the coronary task", () => { expect(taskName("cad")).toBe("Coronary artery screen"); });
});
