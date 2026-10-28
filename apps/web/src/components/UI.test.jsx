import React from "react";
import { render, screen, cleanup } from "@testing-library/react";
import { describe, it, expect, afterEach } from "vitest";
import { Empty, CallTable, Transcript } from "./UI";
afterEach(cleanup);
describe("call and transcript presentation", () => {
  it("displays an honest empty state", () => {
    render(<Empty title="No calls yet" />);
    expect(screen.getByText("No calls yet")).toBeInTheDocument();
  });
  it("renders real call records and status", () => {
    render(
      <CallTable
        calls={[
          {
            id: 7,
            caller_number: "Browser",
            agent_name: "Support",
            direction: "browser",
            duration: 65,
            status: "interrupted",
            created_at: "2026-10-28T10:00:00",
          },
        ]}
      />,
    );
    expect(screen.getByText("1m 5s")).toBeInTheDocument();
    expect(screen.getByText("interrupted")).toBeInTheDocument();
  });
  it("renders both conversation participants safely as text", () => {
    render(
      <Transcript
        messages={[
          { role: "user", content: "<script>alert(1)</script>" },
          { role: "assistant", content: "Hello" },
        ]}
      />,
    );
    expect(screen.getByText("<script>alert(1)</script>")).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
    expect(screen.getByText("AI ASSISTANT")).toBeInTheDocument();
  });
});
