import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ChannelControls, DisruptionForm, LifecycleControls } from "@/components/instructor/control-panel";
import type { Channel } from "@/lib/types";

const channel: Channel = {
  id: "c1",
  key: "command",
  name: "Command Net",
  channel_type: "COMMAND",
  status: "ONLINE",
  base_status: "ONLINE",
  reliability: 0.95,
  latency_ms: 500,
  health: 95,
  weight: 2,
  fallback_channel_key: "backup",
};

describe("Instructor controls", () => {
  it("pauses a running exercise and requires confirmation to end", async () => {
    const onAction = vi.fn();
    render(<LifecycleControls status="RUNNING" onAction={onAction} />);
    await userEvent.click(screen.getByRole("button", { name: /pause/i }));
    expect(onAction).toHaveBeenCalledWith("pause");
    await userEvent.click(screen.getByRole("button", { name: /end exercise/i }));
    expect(onAction).not.toHaveBeenCalledWith("end");
    await userEvent.click(screen.getByRole("button", { name: /confirm end/i }));
    expect(onAction).toHaveBeenCalledWith("end");
  });

  it("offers resume when paused", async () => {
    const onAction = vi.fn();
    render(<LifecycleControls status="PAUSED" onAction={onAction} />);
    await userEvent.click(screen.getByRole("button", { name: /resume/i }));
    expect(onAction).toHaveBeenCalledWith("resume");
  });

  it("degrades, disables and restores channels with status shown as text", async () => {
    const onChange = vi.fn();
    render(<ChannelControls channels={[channel]} onChange={onChange} />);
    const row = screen.getByTestId("channel-command");
    expect(within(row).getByText("Online")).toBeInTheDocument();
    await userEvent.click(within(row).getByRole("button", { name: /degrade/i }));
    expect(onChange).toHaveBeenCalledWith("c1", expect.objectContaining({ status: "DEGRADED", latency_ms: 8000 }));
    await userEvent.click(within(row).getByRole("button", { name: /disable/i }));
    expect(onChange).toHaveBeenCalledWith("c1", expect.objectContaining({ status: "OFFLINE" }));
    await userEvent.click(within(row).getByRole("button", { name: /restore/i }));
    expect(onChange).toHaveBeenCalledWith("c1", expect.objectContaining({ restore: true }));
  });

  it("builds a targeted delay disruption", async () => {
    const onSubmit = vi.fn();
    render(
      <DisruptionForm
        participants={[{ id: "p-bravo", callsign: "BRAVO" }, { id: "p-alpha", callsign: "ALPHA" }]}
        channels={[{ id: "c1", name: "Command Net" }]}
        onSubmit={onSubmit}
      />,
    );
    await userEvent.click(screen.getByRole("checkbox", { name: "BRAVO" }));
    await userEvent.click(screen.getByRole("button", { name: /start disruption/i }));
    expect(onSubmit).toHaveBeenCalledWith({
      disruption_type: "DELAY",
      target_participant_ids: ["p-bravo"],
      target_channel_ids: [],
      delay_seconds: 60,
      duration_seconds: 120,
    });
  });

  it("requires a channel for channel failure", async () => {
    render(<DisruptionForm participants={[]} channels={[{ id: "c1", name: "Command Net" }]} onSubmit={vi.fn()} />);
    await userEvent.selectOptions(screen.getByLabelText("Disruption"), "CHANNEL_FAILURE");
    expect(screen.getByRole("button", { name: /start disruption/i })).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox", { name: "Command Net" }));
    expect(screen.getByRole("button", { name: /start disruption/i })).toBeEnabled();
  });
});
