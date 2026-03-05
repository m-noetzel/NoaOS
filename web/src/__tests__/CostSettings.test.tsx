import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CostDashboard } from "../components/Cost/CostDashboard";
import { SettingsPanel } from "../components/Settings/SettingsPanel";
import { ModelSelector } from "../components/Settings/ModelSelector";
import { useSettingsStore } from "../store/settings";

beforeEach(() => {
  // Reset the store to defaults before each test
  useSettingsStore.setState({
    settings: {
      default_provider: "ollama",
      privacy_mode: "private",
      daily_token_cap: 100000,
      monthly_token_cap: 3000000,
    },
    usage: {
      daily: { used: 0, limit: 100000, cost_usd: 0 },
      monthly: { used: 0, limit: 3000000, cost_usd: 0 },
      messages: [],
    },
    loading: false,
    error: null,
  });
});

describe("CostDashboard", () => {
  it("renders per-message breakdown with model, tokens, and cost", () => {
    useSettingsStore.setState({
      usage: {
        daily: { used: 5000, limit: 100000, cost_usd: 0.05 },
        monthly: { used: 50000, limit: 3000000, cost_usd: 0.5 },
        messages: [
          {
            model: "claude-3-sonnet",
            prompt_tokens: 200,
            completion_tokens: 300,
            cost_usd: 0.003,
          },
          {
            model: "gpt-4",
            prompt_tokens: 150,
            completion_tokens: 250,
            cost_usd: 0.012,
          },
        ],
      },
    });

    render(<CostDashboard />);

    // Check model names appear
    expect(screen.getByText("claude-3-sonnet")).toBeInTheDocument();
    expect(screen.getByText("gpt-4")).toBeInTheDocument();

    // Check token counts appear
    expect(screen.getByText("200")).toBeInTheDocument();
    expect(screen.getByText("300")).toBeInTheDocument();
    expect(screen.getByText("150")).toBeInTheDocument();
    expect(screen.getByText("250")).toBeInTheDocument();

    // Check costs appear
    expect(screen.getByText("$0.0030")).toBeInTheDocument();
    expect(screen.getByText("$0.0120")).toBeInTheDocument();
  });

  it("daily progress bar shows usage vs budget", () => {
    useSettingsStore.setState({
      usage: {
        daily: { used: 40000, limit: 100000, cost_usd: 0.4 },
        monthly: { used: 200000, limit: 3000000, cost_usd: 2.0 },
        messages: [],
      },
    });

    render(<CostDashboard />);

    const dailyBar = screen.getByRole("progressbar", {
      name: /daily usage/i,
    });
    expect(dailyBar).toBeInTheDocument();
    expect(dailyBar).toHaveAttribute("aria-valuenow", "40");
  });

  it("monthly progress bar shows usage vs budget", () => {
    useSettingsStore.setState({
      usage: {
        daily: { used: 5000, limit: 100000, cost_usd: 0.05 },
        monthly: { used: 1500000, limit: 3000000, cost_usd: 15.0 },
        messages: [],
      },
    });

    render(<CostDashboard />);

    const monthlyBar = screen.getByRole("progressbar", {
      name: /monthly usage/i,
    });
    expect(monthlyBar).toBeInTheDocument();
    expect(monthlyBar).toHaveAttribute("aria-valuenow", "50");
  });

  it("warning displayed when daily usage exceeds 80%", () => {
    useSettingsStore.setState({
      usage: {
        daily: { used: 85000, limit: 100000, cost_usd: 0.85 },
        monthly: { used: 200000, limit: 3000000, cost_usd: 2.0 },
        messages: [],
      },
    });

    render(<CostDashboard />);

    expect(
      screen.getByText(/warning: daily usage exceeds 80% of budget/i),
    ).toBeInTheDocument();
  });

  it("budget exceeded state shows limit reached message", () => {
    useSettingsStore.setState({
      usage: {
        daily: { used: 100000, limit: 100000, cost_usd: 1.0 },
        monthly: { used: 200000, limit: 3000000, cost_usd: 2.0 },
        messages: [],
      },
    });

    render(<CostDashboard />);

    expect(screen.getByText(/budget limit reached/i)).toBeInTheDocument();
  });
});

describe("SettingsPanel", () => {
  it("renders with default provider selector", () => {
    render(<SettingsPanel />);

    const providerSelect = screen.getByLabelText(/default provider/i);
    expect(providerSelect).toBeInTheDocument();
    expect(providerSelect).toHaveValue("ollama");
  });

  it("privacy mode toggle switches between private and external", async () => {
    const user = userEvent.setup();
    render(<SettingsPanel />);

    const privacySelect = screen.getByLabelText(/privacy mode/i);
    expect(privacySelect).toHaveValue("private");

    await user.selectOptions(privacySelect, "external");
    expect(privacySelect).toHaveValue("external");

    await user.selectOptions(privacySelect, "private");
    expect(privacySelect).toHaveValue("private");
  });
});

describe("ModelSelector", () => {
  it("dropdown shows available providers", () => {
    render(<ModelSelector />);

    const select = screen.getByLabelText(/default provider/i);
    expect(select).toBeInTheDocument();

    const options = select.querySelectorAll("option");
    const values = Array.from(options).map((o) => o.getAttribute("value"));
    expect(values).toContain("ollama");
    expect(values).toContain("anthropic");
    expect(values).toContain("openai");
  });
});
