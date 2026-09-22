import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AboutDialog } from "@/components/shell/about-dialog";
import { Button } from "@/components/ui/button";
import { TextField } from "@/components/ui/text-field";

describe("Button", () => {
  it("supports keyboard activation without submitting an enclosing form by default", async () => {
    const user = userEvent.setup();
    const clicked = vi.fn();
    const submitted = vi.fn((event) => event.preventDefault());
    render(
      <form onSubmit={submitted}>
        <Button onClick={clicked}>Continue</Button>
      </form>,
    );
    await user.tab();
    await user.keyboard("{Enter}");
    expect(clicked).toHaveBeenCalledOnce();
    expect(submitted).not.toHaveBeenCalled();
  });

  it("prevents repeat activation while busy and preserves its accessible name", async () => {
    const user = userEvent.setup();
    const clicked = vi.fn();
    render(
      <Button loading onClick={clicked}>
        Save changes
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Save changes" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    await user.click(button);
    expect(clicked).not.toHaveBeenCalled();
  });

  it("preserves explicit submit behavior", async () => {
    const user = userEvent.setup();
    const submitted = vi.fn((event) => event.preventDefault());
    render(
      <form onSubmit={submitted}>
        <Button type="submit">Save</Button>
      </form>,
    );
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(submitted).toHaveBeenCalledOnce();
  });
});

describe("TextField", () => {
  it("associates a visible label and hint with an editable input", async () => {
    const user = userEvent.setup();
    render(<TextField label="Name" hint="Use a recognizable name." />);
    const input = screen.getByRole("textbox", { name: "Name" });
    expect(input).toHaveAccessibleDescription("Use a recognizable name.");
    await user.type(input, "Example");
    expect(input).toHaveValue("Example");
  });

  it("announces validation errors alongside hints and removes invalid state after correction", () => {
    const { rerender } = render(
      <TextField label="Name" hint="Required." error="Enter a name." />,
    );
    const input = screen.getByRole("textbox", { name: "Name" });
    expect(input).toBeInvalid();
    expect(input).toHaveAccessibleDescription("Required. Enter a name.");
    rerender(<TextField label="Name" hint="Required." />);
    expect(input).not.toBeInvalid();
    expect(input).toHaveAccessibleDescription("Required.");
  });

  it("keeps separate fields uniquely labeled and preserves caller descriptions", () => {
    render(
      <>
        <p id="context">Private to your account.</p>
        <TextField label="First name" aria-describedby="context" />
        <TextField label="Last name" />
      </>,
    );
    const first = screen.getByRole("textbox", { name: "First name" });
    const last = screen.getByRole("textbox", { name: "Last name" });
    expect(first.id).not.toEqual(last.id);
    expect(first).toHaveAccessibleDescription("Private to your account.");
  });
});

describe("Dialog", () => {
  it("moves focus inside, traps tab navigation, and returns focus when Escape closes it", async () => {
    const user = userEvent.setup();
    render(<AboutDialog trigger={<Button>About this preview</Button>} />);
    const trigger = screen.getByRole("button", { name: "About this preview" });
    await user.tab();
    await user.keyboard("{Enter}");
    const dialog = screen.getByRole("dialog", { name: "About DevPulse" });
    expect(dialog).toHaveAccessibleDescription(/Reliability at a glance/);
    expect(dialog).toContainElement(document.activeElement as HTMLElement);
    await user.tab();
    await user.tab();
    expect(dialog).toContainElement(document.activeElement as HTMLElement);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("provides a working explicit dismiss action", async () => {
    const user = userEvent.setup();
    render(<AboutDialog trigger={<Button>About this preview</Button>} />);
    await user.click(
      screen.getByRole("button", { name: "About this preview" }),
    );
    await user.click(screen.getByRole("button", { name: "Got it" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
