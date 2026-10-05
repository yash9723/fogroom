import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { LoginForm } from "@/components/auth/login-form";
import { ApiError } from "@/lib/api";

describe("LoginForm", () => {
  it("validates fields before submitting", async () => {
    const onSubmit = vi.fn();
    render(<LoginForm onSubmit={onSubmit} />);
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText("Enter a valid email address")).toBeInTheDocument();
    expect(screen.getByText("Password is required")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits credentials", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<LoginForm onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText("Email"), "alpha@fogroom.demo");
    await userEvent.type(screen.getByLabelText("Password"), "secret-123");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(onSubmit).toHaveBeenCalledWith({ email: "alpha@fogroom.demo", password: "secret-123" });
  });

  it("shows the API error message", async () => {
    const onSubmit = vi.fn().mockRejectedValue(new ApiError(401, "INVALID_CREDENTIALS", "Invalid email or password."));
    render(<LoginForm onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText("Email"), "alpha@fogroom.demo");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password.");
  });
});
