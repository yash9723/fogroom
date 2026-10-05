import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { JoinForm } from "@/components/trainee/join-form";
import { ApiError } from "@/lib/api";

describe("JoinForm (room join)", () => {
  it("rejects malformed codes", async () => {
    const onJoin = vi.fn();
    render(<JoinForm onJoin={onJoin} />);
    await userEvent.type(screen.getByLabelText("Room code"), "hello");
    await userEvent.click(screen.getByRole("button", { name: /join exercise/i }));
    expect(screen.getByText(/enter the room code/i)).toBeInTheDocument();
    expect(onJoin).not.toHaveBeenCalled();
  });

  it("normalises the code before joining", async () => {
    const onJoin = vi.fn().mockResolvedValue(undefined);
    render(<JoinForm onJoin={onJoin} />);
    await userEvent.type(screen.getByLabelText("Room code"), "grey42");
    await userEvent.click(screen.getByRole("button", { name: /join exercise/i }));
    expect(onJoin).toHaveBeenCalledWith("GREY-42");
  });

  it("surfaces server errors such as an unknown room", async () => {
    const onJoin = vi.fn().mockRejectedValue(new ApiError(404, "ROOM_NOT_FOUND", "No exercise found with that room code."));
    render(<JoinForm onJoin={onJoin} />);
    await userEvent.type(screen.getByLabelText("Room code"), "GREY-99");
    await userEvent.click(screen.getByRole("button", { name: /join exercise/i }));
    expect(await screen.findByText("No exercise found with that room code.")).toBeInTheDocument();
  });
});
