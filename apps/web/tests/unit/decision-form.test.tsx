import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DecisionForm } from "@/components/trainee/decision-form";
import type { DecisionPoint } from "@/lib/types";

const point: DecisionPoint = {
  id: "dp1",
  key: "medevac_method",
  title: "Medical evacuation method",
  prompt: "How should the cell move the patients?",
  options: [
    { key: "ground_bridge", label: "Ground convoy across Bridge Orion" },
    { key: "sea_harbor", label: "Boat transfer to Harbor Delta" },
  ],
  allow_custom: false,
  require_rationale: true,
  status: "OPEN",
  opened_sim_time: 300,
  deadline_sim_time: 450,
  closed_sim_time: null,
  critical: true,
};

describe("DecisionForm", () => {
  it("requires an option and a rationale", async () => {
    const onSubmit = vi.fn();
    render(<DecisionForm point={point} simTime={320} onSubmit={onSubmit} />);
    await userEvent.click(screen.getByRole("button", { name: /submit decision/i }));
    expect(screen.getByRole("alert")).toHaveTextContent("Select an option.");
    await userEvent.click(screen.getByRole("radio", { name: /boat transfer/i }));
    await userEvent.click(screen.getByRole("button", { name: /submit decision/i }));
    expect(screen.getByRole("alert")).toHaveTextContent(/rationale is required/i);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits option, rationale and confidence", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<DecisionForm point={point} simTime={320} onSubmit={onSubmit} />);
    expect(screen.getByText(/left/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: /boat transfer/i }));
    await userEvent.type(screen.getByLabelText(/rationale/i), "Bridge reports conflict");
    const slider = screen.getByRole("slider", { name: "Confidence" });
    slider.focus();
    await userEvent.keyboard("{ArrowRight}{ArrowRight}");
    await userEvent.click(screen.getByRole("button", { name: /submit decision/i }));
    expect(onSubmit).toHaveBeenCalledWith({
      selected_option: "sea_harbor",
      decision_text: null,
      rationale: "Bridge reports conflict",
      confidence: 60,
    });
  });

  it("never shows the hidden truth-alignment rubric", () => {
    render(<DecisionForm point={{ ...point, options: [{ key: "a", label: "A", truth_alignment: 90 }] }} onSubmit={vi.fn()} />);
    expect(screen.queryByText("90")).not.toBeInTheDocument();
  });
});
