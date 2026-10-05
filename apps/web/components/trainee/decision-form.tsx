"use client";

import { formatSimTime } from "@fogroom/shared";
import { AlarmClock, Send } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Textarea } from "@/components/ui/form";
import { Slider } from "@/components/ui/slider";
import { ApiError } from "@/lib/api";
import type { DecisionPoint } from "@/lib/types";
import { cn } from "@/lib/utils";

export type DecisionValues = {
  selected_option: string | null;
  decision_text: string | null;
  rationale: string | null;
  confidence: number;
};

/** Decision prompt with options / custom response, confidence slider and rationale. */
export function DecisionForm({
  point,
  simTime,
  onSubmit,
}: {
  point: DecisionPoint;
  simTime?: number;
  onSubmit: (values: DecisionValues) => Promise<void>;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [custom, setCustom] = useState("");
  const [rationale, setRationale] = useState("");
  const [confidence, setConfidence] = useState(50);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const remaining = point.deadline_sim_time !== null && simTime !== undefined ? point.deadline_sim_time - simTime : null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected && !(point.allow_custom && custom.trim())) {
      setError(point.allow_custom ? "Select an option or describe a custom decision." : "Select an option.");
      return;
    }
    if (point.require_rationale && !rationale.trim()) {
      setError("A rationale is required for this decision.");
      return;
    }
    setError(null);
    setPending(true);
    try {
      await onSubmit({
        selected_option: selected,
        decision_text: selected ? null : custom.trim(),
        rationale: rationale.trim() || null,
        confidence,
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Submission failed");
    } finally {
      setPending(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4" aria-label={`Decision: ${point.title}`} data-testid={`decision-form-${point.key}`}>
      <div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">{point.title}</h3>
          <div className="flex gap-1">
            {point.critical && <Badge tone="crit">Critical</Badge>}
            {remaining !== null && (
              <Badge tone={remaining < 30 ? "crit" : "warn"}>
                <AlarmClock aria-hidden /> {remaining > 0 ? `${formatSimTime(remaining).slice(2)} left` : "closing"}
              </Badge>
            )}
          </div>
        </div>
        <p className="mt-1 text-sm text-muted">{point.prompt}</p>
      </div>

      <fieldset>
        <legend className="sr-only">Options</legend>
        <div className="grid gap-2">
          {point.options.map((o) => (
            <label
              key={o.key}
              className={cn(
                "flex cursor-pointer items-start gap-3 rounded-md border px-3 py-2.5 text-sm transition-colors",
                selected === o.key ? "border-accent bg-accent-soft" : "border-line bg-panel-2 hover:border-line-strong",
              )}
            >
              <input
                type="radio"
                name={`dp-${point.key}`}
                value={o.key}
                checked={selected === o.key}
                onChange={() => setSelected(o.key)}
                className="mt-1 accent-[#4fc1d6]"
              />
              <span>
                <span className="font-medium">{o.label}</span>
                {o.description && <span className="block text-xs text-muted">{o.description}</span>}
              </span>
            </label>
          ))}
          {point.allow_custom && (
            <label
              className={cn(
                "flex cursor-pointer items-start gap-3 rounded-md border px-3 py-2.5 text-sm",
                selected === null && custom ? "border-accent bg-accent-soft" : "border-line bg-panel-2",
              )}
            >
              <input type="radio" name={`dp-${point.key}`} checked={selected === null && custom.length > 0} onChange={() => setSelected(null)} className="mt-1" />
              <span className="flex-1">
                <span className="font-medium">Custom response</span>
                <Textarea
                  aria-label="Custom decision"
                  className="mt-1.5 min-h-14"
                  value={custom}
                  onChange={(e) => {
                    setCustom(e.target.value);
                    setSelected(null);
                  }}
                />
              </span>
            </label>
          )}
        </div>
      </fieldset>

      <div>
        <div className="mb-1 flex items-center justify-between text-xs">
          <label htmlFor={`conf-${point.key}`} className="font-medium text-muted">
            Confidence
          </label>
          <span className="font-mono text-sm tabular text-fg" aria-live="polite">
            {confidence}%
          </span>
        </div>
        <Slider
          id={`conf-${point.key}`}
          value={[confidence]}
          min={0}
          max={100}
          step={5}
          thumbLabel="Confidence"
          onValueChange={([v]) => setConfidence(v)}
        />
      </div>

      <Field label={`Rationale${point.require_rationale ? " (required)" : ""}`} htmlFor={`rat-${point.key}`}>
        <Textarea
          id={`rat-${point.key}`}
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          placeholder="What information drove this decision? What are you unsure about?"
        />
      </Field>

      {error && (
        <p role="alert" className="text-sm text-crit">
          {error}
        </p>
      )}
      <Button type="submit" variant="primary" loading={pending} className="w-full">
        <Send aria-hidden /> Submit decision
      </Button>
    </form>
  );
}
