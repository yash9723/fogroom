/**
 * Definition-of-Done E2E: instructor + three trainees in four isolated browser contexts
 * (each context = separate sessionStorage session, exactly like the single-laptop demo).
 *
 * Requires the API running (default http://localhost:8000, or as configured through
 * NEXT_PUBLIC_API_URL) with demo data seeded and DEMO_MODE=true.
 */
import { expect, test, type Browser, type Page } from "@playwright/test";

async function persona(browser: Browser, name: string, code?: string): Promise<Page> {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await page.goto(`/demo?persona=${name}${code ? `&code=${code}` : ""}`);
  return page;
}

async function skipNext(instructor: Page) {
  const button = instructor.getByTestId("skip-next");
  const before = await button.textContent();
  await button.click();
  await expect(button).not.toHaveText(before ?? "", { timeout: 20_000 });
}

const cardTitles = (page: Page) => page.getByTestId("info-card").locator("h3");

test("instructor runs Grey Signal; trainees see different information; AAR replays it", async ({ browser }) => {
  // Instructor launches the demo exercise.
  const instructor = await persona(browser, "instructor");
  await instructor.waitForURL(/\/dashboard\/?$/);
  await instructor.getByTestId("launch-demo").click();
  await instructor.waitForURL(/\/exercises\/room\/?\?id=[0-9a-f-]+$/);
  const roomUrl = instructor.url();
  const roomId = new URL(roomUrl).searchParams.get("id") as string;
  const code = (await instructor.getByTestId("room-code").textContent())?.trim() as string;
  expect(code).toMatch(/^GREY-\d+$/);

  // Three trainees join with the room code.
  const [alpha, bravo, charlie] = await Promise.all([
    persona(browser, "alpha", code),
    persona(browser, "bravo", code),
    persona(browser, "charlie", code),
  ]);
  for (const page of [alpha, bravo, charlie]) {
    await page.waitForURL(/\/exercise\/room\/?\?id=[0-9a-f-]+$/, { timeout: 60_000 });
    await expect(page.getByText(/Waiting for Operation Grey Signal to start/)).toBeVisible();
  }
  await expect(instructor.getByText("3 joined", { exact: false })).toBeVisible();

  // Start: everyone receives the briefing in real time.
  await instructor.getByTestId("start-exercise").click();
  await expect(instructor.getByTestId("sim-clock")).toBeVisible();
  for (const page of [alpha, bravo, charlie]) {
    await expect(cardTitles(page).filter({ hasText: "Initial situation briefing" })).toBeVisible();
  }

  // T+01:00 - Message A: Alpha on time, Bravo delayed, Charlie dropped.
  await skipNext(instructor);
  await expect(cardTitles(alpha).filter({ hasText: "Bridge Orion inspection" })).toBeVisible();
  await expect(cardTitles(bravo).filter({ hasText: "Bridge Orion inspection" })).toHaveCount(0);
  await expect(cardTitles(charlie).filter({ hasText: "Bridge Orion inspection" })).toHaveCount(0);

  // T+02:00 Command Net degrades; T+03:00 conflicting Message B reaches Bravo only.
  await skipNext(instructor);
  await skipNext(instructor);
  await expect(cardTitles(bravo).filter({ hasText: "Bridge Orion inspection" })).toBeVisible();
  await expect(cardTitles(bravo).filter({ hasText: "Bridge Orion structural damage" })).toBeVisible();
  await expect(cardTitles(alpha).filter({ hasText: "Bridge Orion structural damage" })).toHaveCount(0);
  await expect(cardTitles(charlie).filter({ hasText: "Bridge Orion inspection" })).toHaveCount(0);
  await expect(alpha.getByText("Degraded").first()).toBeVisible();

  // Instructor degrades another channel.
  await instructor.getByTestId("channel-medical").getByRole("button", { name: /degrade/i }).click();

  // T+05:00 decision point - trainees choose different actions with confidence + rationale.
  await skipNext(instructor);
  await skipNext(instructor);
  const decide = async (page: Page, option: RegExp, rationale: string) => {
    const form = page.getByTestId("decision-form-medevac_method");
    await expect(form).toBeVisible({ timeout: 30_000 });
    await form.getByRole("radio", { name: option }).check();
    await form.getByRole("textbox").last().fill(rationale);
    await form.getByRole("slider", { name: "Confidence" }).focus();
    await page.keyboard.press("ArrowRight");
    await form.getByRole("button", { name: /submit decision/i }).click();
    await expect(page.getByTestId("decision-panel").getByText(/% confidence/)).toBeVisible();
  };
  await decide(alpha, /ground convoy/i, "Port Authority reports the bridge is open.");
  await decide(bravo, /boat transfer/i, "Bridge reports conflict - avoid the bridge.");
  await decide(charlie, /hold and request verification/i, "No bridge information on my nets.");

  // End the exercise and open the AAR.
  await instructor.getByTestId("end-exercise").click();
  await instructor.getByTestId("confirm-end").click();
  await expect(instructor.getByText(/History is now immutable/)).toBeVisible();
  await expect(alpha.getByText(/The exercise has ended/)).toBeVisible();

  await instructor.goto(`/aar/report?id=${roomId}`);
  await instructor.getByTestId("generate-aar").click();
  await expect(instructor.getByText("Exercise summary")).toBeVisible({ timeout: 30_000 });

  // Replay: global truth vs participant views.
  await instructor.getByTestId("tab-replay").click();
  await expect(instructor.getByTestId("truth-view")).toBeVisible();
  await expect(instructor.getByTestId("truth-cell-M102-CHARLIE")).toContainText("Dropped");
  await instructor.getByTestId("view-BRAVO").click();
  await expect(instructor.getByTestId("replay-contradiction")).toContainText("Bridge Orion");
  await instructor.getByTestId("view-ALPHA").click();
  await expect(instructor.getByTestId("participant-view")).toContainText("Bridge Orion");

  // Decision inspection: available / missing / delayed / conflicting + confidence etc.
  await instructor.getByTestId("tab-decisions").click();
  await instructor.getByTestId("inspect-ALPHA-medevac_method").click();
  const inspection = instructor.getByTestId("decision-inspection");
  await expect(inspection).toBeVisible();
  for (const section of ["Available information", "Missing information", "Delayed information", "Conflicting information"]) {
    await expect(inspection.getByRole("region", { name: section })).toBeVisible();
  }
  await expect(inspection.getByTestId("inspection-confidence")).toContainText("%");
  await expect(inspection.getByTestId("inspection-rationale")).toContainText("bridge is open");
  await expect(inspection.getByTestId("inspection-response-time")).toContainText("s");
  await expect(inspection.getByTestId("inspection-uncertainty")).toContainText("Uncertainty score");
  await instructor.keyboard.press("Escape");

  // Export.
  const download = instructor.waitForEvent("download");
  await instructor.getByTestId("export-pdf").click();
  expect((await download).suggestedFilename()).toBe(`FOGROOM-AAR-${code}.pdf`);
});
