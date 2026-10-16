import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ShapLedger, RiskBadge, formatValue, GlobalImportance } from "../src/components/Explain";
import { Field, validateField, validateAll, lifestyleFrom } from "../src/components/Fields";
import { Login, Register } from "../src/pages/AuthPages";
import { AuthProvider } from "../src/auth";
import type { FieldSpec } from "../src/api";

const num: FieldSpec = { label: "Age", type: "number", min: 18, max: 100, unit: "years", required: true };
const opt: FieldSpec = { label: "Chest pain", type: "select", required: false,
  options: [{ value: 1, label: "Typical" }, { value: 4, label: "None" }] };
const yn: FieldSpec = { label: "Thirst", type: "select", required: true, options: [{ value: 1, label: "Yes" }, { value: 0, label: "No" }] };

function json(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }));
}

describe("validation helpers", () => {
  it("validates required, numeric and ranges", () => {
    expect(validateField(num, "")).toBe("This field is required.");
    expect(validateField(num, "abc")).toBe("Enter a number.");
    expect(validateField(num, "10")).toMatch(/at least 18/);
    expect(validateField(num, "101")).toMatch(/at most 100/);
    expect(validateField(num, "45")).toBe("");
    expect(validateField(opt, "")).toBe("");
  });
  it("collects all errors", () => {
    expect(Object.keys(validateAll({ a: num, b: yn, c: opt }, { a: "5" }))).toEqual(["a", "b"]);
  });
  it("maps lifestyle form values to API payload", () => {
    const l = lifestyleFrom({ height_cm: "170", weight_kg: "70", sleep_hours: "7", activity_minutes_week: "150",
      fruit_veg_servings_day: "5", alcohol_units_week: "0", smoking: "2", asian_bmi_cutoffs: "1" });
    expect(l).toMatchObject({ height_cm: 170, smoking: "current", asian_bmi_cutoffs: true });
  });
  it("formats values using spec labels and units", () => {
    expect(formatValue(opt, 4)).toBe("None");
    expect(formatValue(num, 50)).toBe("50 years");
    expect(formatValue(num, null)).toBe("Not provided");
  });
});

describe("Field", () => {
  it("renders yes/no as a radio group and reports changes", async () => {
    const onChange = vi.fn();
    render(<Field name="thirst" spec={yn} value="" onChange={onChange} />);
    await userEvent.click(screen.getByLabelText("Yes"));
    expect(onChange).toHaveBeenCalledWith("1");
  });
  it("shows optional select with 'Not known' and an accessible error", () => {
    render(<Field name="cp" spec={opt} value="" onChange={() => {}} error="Bad" />);
    expect(screen.getByRole("option", { name: "Not known" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Bad");
    expect(screen.getByLabelText(/Chest pain/)).toHaveAttribute("aria-invalid", "true");
  });
});

describe("ShapLedger", () => {
  it("shows base and final probability and signed contributions in order", () => {
    render(<ShapLedger base={0.4} final={0.75} outcome="Positive" limit={2}
      spec={{ a: num, b: yn, c: opt }}
      contributions={[{ feature: "b", value: 1, shap: 0.3 }, { feature: "a", value: 60, shap: -0.05 }, { feature: "c", value: 4, shap: 0.1 }]} />);
    expect(screen.getByText("40.0%")).toBeInTheDocument();
    expect(screen.getByText("75.0%")).toBeInTheDocument();
    const rows = screen.getAllByRole("listitem");
    expect(within(rows[0]).getByText("Thirst")).toBeInTheDocument();
    expect(within(rows[0]).getByText("+30.0")).toBeInTheDocument();
    expect(within(rows[1]).getByText("−5.0")).toBeInTheDocument();
    expect(within(rows[2]).getByText(/1 other inputs combined/)).toBeInTheDocument();
    expect(within(rows[2]).getByText("+10.0")).toBeInTheDocument();
  });
  it("renders global importance bars", () => {
    render(<GlobalImportance ranked={{ a: 0.1, b: 0.05 }} spec={{ a: num, b: yn }} />);
    expect(screen.getByText("10.0 pp")).toBeInTheDocument();
  });
  it("labels risk badges in words, not colour only", () => {
    render(<RiskBadge level="high" />);
    expect(screen.getByText("High risk")).toBeInTheDocument();
  });
});

describe("auth pages", () => {
  afterEach(() => vi.restoreAllMocks());

  function renderAt(path: string) {
    return render(
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/dashboard" element={<p>dashboard page</p>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>);
  }

  it("shows the server's error on failed login", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => json({ detail: "Incorrect email or password" }, 401));
    renderAt("/login");
    await userEvent.type(screen.getByLabelText("Email"), "a@b.test");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password");
  });

  it("logs in and navigates to the dashboard", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/auth/login")) return json({ access_token: "tok", expires_at: "2030-01-01" });
      if (url.endsWith("/auth/me")) return json({ id: 1, email: "a@b.test", full_name: "A", email_alerts_enabled: true, created_at: "" });
      return json({}, 404);
    });
    renderAt("/login");
    await userEvent.type(screen.getByLabelText("Email"), "a@b.test");
    await userEvent.type(screen.getByLabelText("Password"), "Passw0rd");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    await waitFor(() => expect(screen.getByText("dashboard page")).toBeInTheDocument());
  });

  it("validates registration fields before calling the API", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockImplementation(() => json({}, 401));
    renderAt("/register");
    await userEvent.type(screen.getByLabelText(/^Password/), "abcdefgh");
    await userEvent.type(screen.getByLabelText("Confirm password"), "different1");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(screen.getByText("Enter your name.")).toBeInTheDocument();
    expect(screen.getByText("Include at least one letter and one number.")).toBeInTheDocument();
    expect(screen.getByText("Passwords don't match.")).toBeInTheDocument();
    expect(spy.mock.calls.filter(([u]) => String(u).includes("register"))).toHaveLength(0);
  });
});
