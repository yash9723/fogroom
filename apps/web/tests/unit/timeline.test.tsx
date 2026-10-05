import type { RoomEvent } from "@fogroom/shared";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TimelineList } from "@/components/aar/aar-timeline";
import { EventFeed } from "@/components/instructor/event-feed";

const ev = (seq: number, event_type: string, sim_time: number, payload: Record<string, unknown>): RoomEvent => ({
  seq,
  event_type,
  sim_time,
  timestamp: null,
  visibility: "INSTRUCTOR",
  payload,
});

const events: RoomEvent[] = [
  ev(1, "simulation.started", 0, {}),
  ev(2, "message.dropped", 60, { label: "M102", callsign: "CHARLIE", reasons: ["Scenario rule: drop"] }),
  ev(3, "message.delayed", 60, { label: "M102", callsign: "BRAVO", delay_seconds: 100, reasons: [] }),
  ev(4, "metrics.updated", 90, { participants: [] }),
  ev(5, "decision.submitted", 301, {
    decision_id: "d-1",
    callsign: "ALPHA",
    selected_label: "Ground convoy",
    decision_point_title: "Medevac",
    confidence: 85,
    uncertainty_index: 30,
  }),
];

describe("Timeline rendering", () => {
  it("renders events in order with simulation timestamps and hides metric noise", () => {
    render(<TimelineList events={events} />);
    const rows = screen.getAllByTestId("timeline-row");
    expect(rows).toHaveLength(4);
    expect(rows[1]).toHaveTextContent("T+01:00");
    expect(rows[1]).toHaveTextContent("M102 dropped for CHARLIE");
    expect(rows[2]).toHaveTextContent("M102 delayed for BRAVO");
    expect(rows[3]).toHaveTextContent("T+05:01");
  });

  it("makes decision events inspectable", async () => {
    const onDecision = vi.fn();
    render(<TimelineList events={events} onDecision={onDecision} />);
    await userEvent.click(screen.getByRole("button", { name: /ALPHA decided: Ground convoy/ }));
    expect(onDecision).toHaveBeenCalledWith("d-1");
  });

  it("filters the live event feed by category", async () => {
    render(<EventFeed events={[...events].reverse()} />);
    expect(screen.getByText("M102 dropped for CHARLIE")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Decisions" }));
    expect(screen.queryByText("M102 dropped for CHARLIE")).not.toBeInTheDocument();
    expect(screen.getByText(/ALPHA decided/)).toBeInTheDocument();
  });
});
