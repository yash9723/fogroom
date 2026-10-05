"use client";

import { formatSimTime } from "@fogroom/shared";
import { ChevronDown, ChevronRight, Plus, Save, Trash2 } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { ScenarioDecisionDoc, ScenarioDoc, ScenarioEventDoc } from "@/features/scenarios";
import { ApiError } from "@/lib/api";

const EVENT_TYPES = ["BRIEFING", "INFORMATION", "WEATHER", "REQUEST", "NOTICE", "CHANNEL_CHANGE", "DISRUPTION"];
const PRIORITIES = ["LOW", "NORMAL", "HIGH", "CRITICAL"];
const RELIABILITY = ["HIGH", "MEDIUM", "LOW"];

export const BLANK_SCENARIO: ScenarioDoc = {
  name: "New scenario",
  description: "",
  difficulty: "INTERMEDIATE",
  estimated_duration_minutes: 15,
  category: "General",
  briefing: "",
  objectives: [{ key: "objective_1", title: "Decision-making with incomplete information", description: "" }],
  initial_conditions: { facts: [], locations: [], map: {} },
  degradation_rules: {},
  roles: [{ key: "alpha", name: "Coordinator Alpha", callsign: "ALPHA", team: "Response Cell", description: "", objectives: [] }],
  channels: [{ key: "command", name: "Command Net", channel_type: "COMMAND", initial_status: "ONLINE", reliability: 0.95, latency_ms: 500, weight: 1, fallback_channel_key: null }],
  phases: [{ key: "normal", name: "Normal Operations", description: "", starts_at_seconds: 0 }],
  events: [],
  decision_points: [],
};

function slug(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 50) || "item";
}

function update<T>(list: T[], i: number, patch: Partial<T>): T[] {
  return list.map((x, idx) => (idx === i ? { ...x, ...patch } : x));
}

function JsonField({ label, value, onChange, id }: { label: string; value: unknown; onChange: (v: unknown) => void; id: string }) {
  const [text, setText] = useState(() => JSON.stringify(value ?? null, null, 2));
  const [error, setError] = useState<string | null>(null);
  return (
    <Field label={label} htmlFor={id} error={error} hint="Advanced - JSON">
      <Textarea
        id={id}
        className="font-mono text-xs"
        rows={5}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          try {
            onChange(JSON.parse(e.target.value || "null"));
            setError(null);
          } catch {
            setError("Invalid JSON");
          }
        }}
      />
    </Field>
  );
}

function EventEditor({ ev, doc, onChange, onRemove }: { ev: ScenarioEventDoc; doc: ScenarioDoc; onChange: (p: Partial<ScenarioEventDoc>) => void; onRemove: () => void }) {
  const [open, setOpen] = useState(false);
  const recipients = ev.targeting_rules.recipients;
  return (
    <li className="rounded-md border border-line bg-panel-2">
      <button type="button" className="flex w-full items-center gap-3 px-3 py-2 text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
        {open ? <ChevronDown className="size-4" aria-hidden /> : <ChevronRight className="size-4" aria-hidden />}
        <span className="w-16 font-mono text-xs text-accent">{ev.scheduled_offset_seconds !== null ? formatSimTime(ev.scheduled_offset_seconds) : "manual"}</span>
        <span className="flex-1 truncate text-sm">{ev.title}</span>
        <Badge>{ev.event_type}</Badge>
        {ev.variants.length > 0 && <Badge tone="violet">{ev.variants.length} variant</Badge>}
      </button>
      {open && (
        <div className="space-y-3 border-t border-line p-3">
          <div className="grid gap-3 sm:grid-cols-4">
            <Field label="Key" htmlFor={`ev-key-${ev.key}`}><Input id={`ev-key-${ev.key}`} value={ev.key} onChange={(e) => onChange({ key: slug(e.target.value) })} /></Field>
            <Field label="Type" htmlFor={`ev-type-${ev.key}`}>
              <Select id={`ev-type-${ev.key}`} value={ev.event_type} onChange={(e) => onChange({ event_type: e.target.value })}>
                {EVENT_TYPES.map((t) => <option key={t}>{t}</option>)}
              </Select>
            </Field>
            <Field label="Trigger time (sim s, blank = manual)" htmlFor={`ev-t-${ev.key}`}>
              <Input
                id={`ev-t-${ev.key}`}
                type="number"
                min={0}
                value={ev.scheduled_offset_seconds ?? ""}
                onChange={(e) => onChange(e.target.value === "" ? { scheduled_offset_seconds: null, trigger_type: "MANUAL" } : { scheduled_offset_seconds: Number(e.target.value), trigger_type: "TIME" })}
              />
            </Field>
            <Field label="Phase" htmlFor={`ev-ph-${ev.key}`}>
              <Select id={`ev-ph-${ev.key}`} value={ev.phase_key ?? ""} onChange={(e) => onChange({ phase_key: e.target.value || null })}>
                <option value="">-</option>
                {doc.phases.map((p) => <option key={p.key} value={p.key}>{p.name}</option>)}
              </Select>
            </Field>
          </div>
          <Field label="Title" htmlFor={`ev-title-${ev.key}`}><Input id={`ev-title-${ev.key}`} value={ev.title} onChange={(e) => onChange({ title: e.target.value })} /></Field>
          <Field label="Description / report content" htmlFor={`ev-c-${ev.key}`}><Textarea id={`ev-c-${ev.key}`} value={ev.content} onChange={(e) => onChange({ content: e.target.value })} /></Field>
          <div className="grid gap-3 sm:grid-cols-4">
            <Field label="Delivery channel" htmlFor={`ev-ch-${ev.key}`}>
              <Select id={`ev-ch-${ev.key}`} value={ev.channel_key ?? ""} onChange={(e) => onChange({ channel_key: e.target.value || null })}>
                <option value="">None</option>
                {doc.channels.map((c) => <option key={c.key} value={c.key}>{c.name}</option>)}
              </Select>
            </Field>
            <Field label="Priority" htmlFor={`ev-pr-${ev.key}`}>
              <Select id={`ev-pr-${ev.key}`} value={ev.priority} onChange={(e) => onChange({ priority: e.target.value })}>{PRIORITIES.map((p) => <option key={p}>{p}</option>)}</Select>
            </Field>
            <Field label="Source reliability" htmlFor={`ev-rel-${ev.key}`}>
              <Select id={`ev-rel-${ev.key}`} value={ev.source_reliability} onChange={(e) => onChange({ source_reliability: e.target.value })}>{RELIABILITY.map((p) => <option key={p}>{p}</option>)}</Select>
            </Field>
            <Field label="Delivery reliability (0-1)" htmlFor={`ev-dr-${ev.key}`}>
              <Input id={`ev-dr-${ev.key}`} type="number" min={0} max={1} step={0.05} value={ev.reliability} onChange={(e) => onChange({ reliability: Number(e.target.value) })} />
            </Field>
          </div>
          <div className="grid gap-3 sm:grid-cols-4">
            <Field label="Source" htmlFor={`ev-src-${ev.key}`}><Input id={`ev-src-${ev.key}`} value={ev.source} onChange={(e) => onChange({ source: e.target.value })} /></Field>
            <Field label="Importance (1-5)" htmlFor={`ev-imp-${ev.key}`}><Input id={`ev-imp-${ev.key}`} type="number" min={1} max={5} value={ev.importance_weight} onChange={(e) => onChange({ importance_weight: Number(e.target.value) })} /></Field>
            <Field label="Fact key" htmlFor={`ev-fk-${ev.key}`}><Input id={`ev-fk-${ev.key}`} value={ev.fact_key ?? ""} onChange={(e) => onChange({ fact_key: e.target.value || null })} /></Field>
            <Field label="Fact value" htmlFor={`ev-fv-${ev.key}`}><Input id={`ev-fv-${ev.key}`} value={ev.fact_value ?? ""} onChange={(e) => onChange({ fact_value: e.target.value || null })} /></Field>
          </div>
          <fieldset>
            <legend className="mb-1 text-xs font-medium text-muted">Target participants</legend>
            <div className="flex flex-wrap gap-2 text-xs">
              <label className="flex items-center gap-1.5">
                <input type="checkbox" checked={recipients === "all"} onChange={(e) => onChange({ targeting_rules: { ...ev.targeting_rules, recipients: e.target.checked ? "all" : [] } })} /> All roles
              </label>
              {recipients !== "all" &&
                doc.roles.map((r) => (
                  <label key={r.key} className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={recipients.includes(r.key)}
                      onChange={(e) =>
                        onChange({ targeting_rules: { ...ev.targeting_rules, recipients: e.target.checked ? [...recipients, r.key] : recipients.filter((x) => x !== r.key) } })
                      }
                    />
                    {r.callsign}
                  </label>
                ))}
            </div>
          </fieldset>
          <div className="grid gap-3 lg:grid-cols-3">
            <JsonField id={`ev-ov-${ev.key}`} label="Per-role overrides" value={ev.targeting_rules.overrides} onChange={(v) => onChange({ targeting_rules: { ...ev.targeting_rules, overrides: (v as ScenarioEventDoc["targeting_rules"]["overrides"]) ?? {} } })} />
            <JsonField id={`ev-var-${ev.key}`} label="Conflicting variants" value={ev.variants} onChange={(v) => onChange({ variants: (v as ScenarioEventDoc["variants"]) ?? [] })} />
            <JsonField id={`ev-eff-${ev.key}`} label="Effects (channel change / disruption)" value={ev.effects} onChange={(v) => onChange({ effects: (v as Record<string, unknown>) ?? null })} />
          </div>
          <Button size="sm" variant="danger" onClick={onRemove}><Trash2 aria-hidden /> Remove event</Button>
        </div>
      )}
    </li>
  );
}

function DecisionEditor({ dp, doc, onChange, onRemove }: { dp: ScenarioDecisionDoc; doc: ScenarioDoc; onChange: (p: Partial<ScenarioDecisionDoc>) => void; onRemove: () => void }) {
  return (
    <li className="space-y-3 rounded-md border border-line bg-panel-2 p-3">
      <div className="grid gap-3 sm:grid-cols-4">
        <Field label="Key" htmlFor={`dp-k-${dp.key}`}><Input id={`dp-k-${dp.key}`} value={dp.key} onChange={(e) => onChange({ key: slug(e.target.value) })} /></Field>
        <Field label="Opens at (sim s)" htmlFor={`dp-o-${dp.key}`}>
          <Input id={`dp-o-${dp.key}`} type="number" min={0} value={dp.opens_at_seconds ?? ""} onChange={(e) => onChange(e.target.value === "" ? { opens_at_seconds: null, trigger_type: "MANUAL" } : { opens_at_seconds: Number(e.target.value), trigger_type: "TIME" })} />
        </Field>
        <Field label="Window (s)" htmlFor={`dp-d-${dp.key}`}><Input id={`dp-d-${dp.key}`} type="number" min={10} value={dp.deadline_seconds} onChange={(e) => onChange({ deadline_seconds: Number(e.target.value) })} /></Field>
        <div className="flex flex-col justify-end gap-1 text-xs">
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={dp.allow_custom} onChange={(e) => onChange({ allow_custom: e.target.checked })} /> Allow custom</label>
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={dp.require_rationale} onChange={(e) => onChange({ require_rationale: e.target.checked })} /> Require rationale</label>
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={dp.critical} onChange={(e) => onChange({ critical: e.target.checked })} /> Critical</label>
        </div>
      </div>
      <Field label="Title" htmlFor={`dp-t-${dp.key}`}><Input id={`dp-t-${dp.key}`} value={dp.title} onChange={(e) => onChange({ title: e.target.value })} /></Field>
      <Field label="Prompt" htmlFor={`dp-p-${dp.key}`}><Textarea id={`dp-p-${dp.key}`} value={dp.prompt} onChange={(e) => onChange({ prompt: e.target.value })} /></Field>
      <fieldset>
        <legend className="mb-1 text-xs font-medium text-muted">Target roles (none = everyone)</legend>
        <div className="flex flex-wrap gap-3 text-xs">
          {doc.roles.map((r) => (
            <label key={r.key} className="flex items-center gap-1.5">
              <input type="checkbox" checked={dp.target_roles.includes(r.key)} onChange={(e) => onChange({ target_roles: e.target.checked ? [...dp.target_roles, r.key] : dp.target_roles.filter((x) => x !== r.key) })} />
              {r.callsign}
            </label>
          ))}
        </div>
      </fieldset>
      <div>
        <div className="mb-1 text-xs font-medium text-muted">Options (truth alignment = scenario-designer rubric 0-100, hidden from trainees)</div>
        <ul className="space-y-2">
          {dp.options.map((o, i) => (
            <li key={i} className="grid grid-cols-[140px_1fr_90px_auto] gap-2">
              <Input aria-label="Option key" value={o.key} onChange={(e) => onChange({ options: update(dp.options, i, { key: slug(e.target.value) }) })} />
              <Input aria-label="Option label" value={o.label} onChange={(e) => onChange({ options: update(dp.options, i, { label: e.target.value }) })} />
              <Input aria-label="Truth alignment" type="number" min={0} max={100} value={o.truth_alignment} onChange={(e) => onChange({ options: update(dp.options, i, { truth_alignment: Number(e.target.value) }) })} />
              <Button size="icon" variant="ghost" aria-label="Remove option" onClick={() => onChange({ options: dp.options.filter((_, idx) => idx !== i) })}><Trash2 /></Button>
            </li>
          ))}
        </ul>
        <Button size="sm" variant="ghost" className="mt-2" onClick={() => onChange({ options: [...dp.options, { key: `option_${dp.options.length + 1}`, label: "New option", description: "", truth_alignment: 50 }] })}>
          <Plus aria-hidden /> Add option
        </Button>
      </div>
      <Button size="sm" variant="danger" onClick={onRemove}><Trash2 aria-hidden /> Remove decision point</Button>
    </li>
  );
}

export function ScenarioEditor({ initial, onSave, saving }: { initial: ScenarioDoc; onSave: (doc: ScenarioDoc) => Promise<void>; saving?: boolean }) {
  const [doc, setDoc] = useState<ScenarioDoc>(initial);
  const [error, setError] = useState<string | null>(null);
  const set = (patch: Partial<ScenarioDoc>) => setDoc((d) => ({ ...d, ...patch }));

  const save = async () => {
    setError(null);
    try {
      await onSave(doc);
    } catch (e) {
      if (e instanceof ApiError) {
        const details = e.details as { errors?: { msg: string; loc: unknown[] }[] } | undefined;
        setError(details?.errors?.map((x) => `${x.loc.slice(1).join(".")}: ${x.msg}`).join("\n") ?? e.message);
      } else setError("Save failed");
    }
  };

  const events = [...doc.events].sort((a, b) => (a.scheduled_offset_seconds ?? 1e9) - (b.scheduled_offset_seconds ?? 1e9));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted">Rooms keep a frozen copy of the scenario, so edits never change exercises that already ran.</p>
        <Button variant="primary" onClick={save} loading={saving}><Save aria-hidden /> Save scenario</Button>
      </div>
      {error && <pre role="alert" className="whitespace-pre-wrap rounded-md border border-crit/40 bg-crit-soft p-3 text-xs text-crit">{error}</pre>}
      <Tabs defaultValue="basics">
        <TabsList className="flex flex-wrap">
          <TabsTrigger value="basics">Basics</TabsTrigger>
          <TabsTrigger value="roles">Roles &amp; channels</TabsTrigger>
          <TabsTrigger value="phases">Phases &amp; objectives</TabsTrigger>
          <TabsTrigger value="events">Events ({doc.events.length})</TabsTrigger>
          <TabsTrigger value="decisions">Decision points ({doc.decision_points.length})</TabsTrigger>
          <TabsTrigger value="degradation">Degradation</TabsTrigger>
        </TabsList>

        <TabsContent value="basics">
          <Card><CardBody className="grid gap-4 md:grid-cols-2">
            <Field label="Name" htmlFor="sc-name"><Input id="sc-name" value={doc.name} onChange={(e) => set({ name: e.target.value })} /></Field>
            <Field label="Category" htmlFor="sc-cat"><Input id="sc-cat" value={doc.category} onChange={(e) => set({ category: e.target.value })} /></Field>
            <Field label="Difficulty" htmlFor="sc-diff" hint="Sets default delay/drop/conflict rates (overridable)">
              <Select id="sc-diff" value={doc.difficulty} onChange={(e) => set({ difficulty: e.target.value as ScenarioDoc["difficulty"] })}>
                <option>BEGINNER</option><option>INTERMEDIATE</option><option>ADVANCED</option>
              </Select>
            </Field>
            <Field label="Estimated duration (minutes)" htmlFor="sc-dur"><Input id="sc-dur" type="number" min={1} value={doc.estimated_duration_minutes} onChange={(e) => set({ estimated_duration_minutes: Number(e.target.value) })} /></Field>
            <Field label="Description" htmlFor="sc-desc" className="md:col-span-2"><Textarea id="sc-desc" value={doc.description} onChange={(e) => set({ description: e.target.value })} /></Field>
            <Field label="Initial briefing" htmlFor="sc-brief" className="md:col-span-2"><Textarea id="sc-brief" rows={4} value={doc.briefing} onChange={(e) => set({ briefing: e.target.value })} /></Field>
            <div className="md:col-span-2"><JsonField id="sc-ic" label="Initial conditions (ground-truth facts timeline, fictional map locations)" value={doc.initial_conditions} onChange={(v) => set({ initial_conditions: v as ScenarioDoc["initial_conditions"] })} /></div>
          </CardBody></Card>
        </TabsContent>

        <TabsContent value="roles" className="space-y-4">
          <Card><CardBody className="space-y-2">
            <h3 className="text-sm font-semibold">Participant roles</h3>
            {doc.roles.map((r, i) => (
              <div key={i} className="grid grid-cols-[120px_1fr_120px_1fr_auto] gap-2">
                <Input aria-label="Role key" value={r.key} onChange={(e) => set({ roles: update(doc.roles, i, { key: slug(e.target.value) }) })} />
                <Input aria-label="Role name" value={r.name} onChange={(e) => set({ roles: update(doc.roles, i, { name: e.target.value }) })} />
                <Input aria-label="Callsign" value={r.callsign} onChange={(e) => set({ roles: update(doc.roles, i, { callsign: e.target.value.toUpperCase() }) })} />
                <Input aria-label="Description" value={r.description} onChange={(e) => set({ roles: update(doc.roles, i, { description: e.target.value }) })} />
                <Button size="icon" variant="ghost" aria-label="Remove role" onClick={() => set({ roles: doc.roles.filter((_, idx) => idx !== i) })}><Trash2 /></Button>
              </div>
            ))}
            <Button size="sm" variant="ghost" onClick={() => set({ roles: [...doc.roles, { key: `role_${doc.roles.length + 1}`, name: "New role", callsign: `R${doc.roles.length + 1}`, team: "Response Cell", description: "", objectives: [] }] })}><Plus aria-hidden /> Add role</Button>
          </CardBody></Card>
          <Card><CardBody className="space-y-2">
            <h3 className="text-sm font-semibold">Communication channels</h3>
            {doc.channels.map((c, i) => (
              <div key={i} className="grid grid-cols-[110px_1fr_110px_90px_90px_120px_auto] gap-2">
                <Input aria-label="Channel key" value={c.key} onChange={(e) => set({ channels: update(doc.channels, i, { key: slug(e.target.value) }) })} />
                <Input aria-label="Channel name" value={c.name} onChange={(e) => set({ channels: update(doc.channels, i, { name: e.target.value }) })} />
                <Select aria-label="Initial status" value={c.initial_status} onChange={(e) => set({ channels: update(doc.channels, i, { initial_status: e.target.value as "ONLINE" }) })}><option>ONLINE</option><option>DEGRADED</option><option>OFFLINE</option></Select>
                <Input aria-label="Reliability" type="number" min={0} max={1} step={0.05} value={c.reliability} onChange={(e) => set({ channels: update(doc.channels, i, { reliability: Number(e.target.value) }) })} />
                <Input aria-label="Latency ms" type="number" min={0} value={c.latency_ms} onChange={(e) => set({ channels: update(doc.channels, i, { latency_ms: Number(e.target.value) }) })} />
                <Select aria-label="Fallback channel" value={c.fallback_channel_key ?? ""} onChange={(e) => set({ channels: update(doc.channels, i, { fallback_channel_key: e.target.value || null }) })}>
                  <option value="">No fallback</option>
                  {doc.channels.filter((x) => x.key !== c.key).map((x) => <option key={x.key} value={x.key}>{x.name}</option>)}
                </Select>
                <Button size="icon" variant="ghost" aria-label="Remove channel" onClick={() => set({ channels: doc.channels.filter((_, idx) => idx !== i) })}><Trash2 /></Button>
              </div>
            ))}
            <Button size="sm" variant="ghost" onClick={() => set({ channels: [...doc.channels, { key: `channel_${doc.channels.length + 1}`, name: "New channel", channel_type: "VOICE", initial_status: "ONLINE", reliability: 0.9, latency_ms: 800, weight: 1, fallback_channel_key: null }] })}><Plus aria-hidden /> Add channel</Button>
          </CardBody></Card>
        </TabsContent>

        <TabsContent value="phases" className="space-y-4">
          <Card><CardBody className="space-y-2">
            <h3 className="text-sm font-semibold">Scenario phases</h3>
            {doc.phases.map((p, i) => (
              <div key={i} className="grid grid-cols-[120px_1fr_120px_auto] gap-2">
                <Input aria-label="Phase key" value={p.key} onChange={(e) => set({ phases: update(doc.phases, i, { key: slug(e.target.value) }) })} />
                <Input aria-label="Phase name" value={p.name} onChange={(e) => set({ phases: update(doc.phases, i, { name: e.target.value }) })} />
                <Input aria-label="Starts at (s)" type="number" min={0} value={p.starts_at_seconds} onChange={(e) => set({ phases: update(doc.phases, i, { starts_at_seconds: Number(e.target.value) }) })} />
                <Button size="icon" variant="ghost" aria-label="Remove phase" onClick={() => set({ phases: doc.phases.filter((_, idx) => idx !== i) })}><Trash2 /></Button>
              </div>
            ))}
            <Button size="sm" variant="ghost" onClick={() => set({ phases: [...doc.phases, { key: `phase_${doc.phases.length + 1}`, name: "New phase", description: "", starts_at_seconds: 0 }] })}><Plus aria-hidden /> Add phase</Button>
          </CardBody></Card>
          <Card><CardBody className="space-y-2">
            <h3 className="text-sm font-semibold">Training objectives</h3>
            {doc.objectives.map((o, i) => (
              <div key={i} className="grid grid-cols-[140px_1fr_auto] gap-2">
                <Input aria-label="Objective key" value={o.key} onChange={(e) => set({ objectives: update(doc.objectives, i, { key: slug(e.target.value) }) })} />
                <Input aria-label="Objective title" value={o.title} onChange={(e) => set({ objectives: update(doc.objectives, i, { title: e.target.value }) })} />
                <Button size="icon" variant="ghost" aria-label="Remove objective" onClick={() => set({ objectives: doc.objectives.filter((_, idx) => idx !== i) })}><Trash2 /></Button>
              </div>
            ))}
            <Button size="sm" variant="ghost" onClick={() => set({ objectives: [...doc.objectives, { key: `objective_${doc.objectives.length + 1}`, title: "New objective", description: "" }] })}><Plus aria-hidden /> Add objective</Button>
          </CardBody></Card>
        </TabsContent>

        <TabsContent value="events">
          <Card><CardBody className="space-y-3">
            <p className="text-xs text-muted">Timeline editor - events sorted by trigger time. Expand an event to edit targeting, controlled variants and effects.</p>
            <ul className="space-y-2">
              {events.map((ev) => {
                const i = doc.events.indexOf(ev);
                return (
                  <EventEditor key={i} ev={ev} doc={doc} onChange={(p) => set({ events: update(doc.events, i, p) })} onRemove={() => set({ events: doc.events.filter((_, idx) => idx !== i) })} />
                );
              })}
            </ul>
            <Button
              size="sm"
              variant="secondary"
              onClick={() =>
                set({
                  events: [
                    ...doc.events,
                    {
                      key: `event_${doc.events.length + 1}`, event_type: "INFORMATION", title: "New report", content: "", trigger_type: "TIME",
                      scheduled_offset_seconds: 60, trigger_decision_key: null, phase_key: null, channel_key: doc.channels[0]?.key ?? null,
                      priority: "NORMAL", source: "Coordination Centre", source_reliability: "MEDIUM", reliability: 1, importance_weight: 1,
                      fact_key: null, fact_value: null, location_key: null, targeting_rules: { recipients: "all", overrides: {} }, variants: [], effects: null, metadata: {},
                    },
                  ],
                })
              }
            >
              <Plus aria-hidden /> Add event
            </Button>
          </CardBody></Card>
        </TabsContent>

        <TabsContent value="decisions">
          <Card><CardBody className="space-y-3">
            <ul className="space-y-3">
              {doc.decision_points.map((dp, i) => (
                <DecisionEditor key={i} dp={dp} doc={doc} onChange={(p) => set({ decision_points: update(doc.decision_points, i, p) })} onRemove={() => set({ decision_points: doc.decision_points.filter((_, idx) => idx !== i) })} />
              ))}
            </ul>
            <Button
              size="sm"
              variant="secondary"
              onClick={() =>
                set({
                  decision_points: [
                    ...doc.decision_points,
                    {
                      key: `decision_${doc.decision_points.length + 1}`, title: "New decision", prompt: "What should the team do?",
                      options: [{ key: "option_a", label: "Option A", description: "", truth_alignment: 50 }, { key: "option_b", label: "Option B", description: "", truth_alignment: 50 }],
                      trigger_type: "TIME", opens_at_seconds: 120, trigger_decision_key: null, deadline_seconds: 120, allow_custom: false,
                      require_rationale: true, target_roles: [], phase_key: null, critical: false, relevant_fact_keys: [],
                    },
                  ],
                })
              }
            >
              <Plus aria-hidden /> Add decision point
            </Button>
          </CardBody></Card>
        </TabsContent>

        <TabsContent value="degradation">
          <Card><CardBody className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {(
              [
                ["delay_probability", "Delay probability"],
                ["drop_probability", "Drop probability"],
                ["conflict_probability", "Conflict probability"],
                ["jitter_seconds", "Delivery jitter (s)"],
                ["channel_loss_factor", "Channel loss factor"],
              ] as const
            ).map(([k, label]) => (
              <Field key={k} label={label} htmlFor={`deg-${k}`} hint="blank = difficulty default">
                <Input
                  id={`deg-${k}`}
                  type="number"
                  min={0}
                  step={k === "jitter_seconds" ? 1 : 0.01}
                  value={doc.degradation_rules[k] ?? ""}
                  onChange={(e) => set({ degradation_rules: { ...doc.degradation_rules, [k]: e.target.value === "" ? null : Number(e.target.value) } })}
                />
              </Field>
            ))}
          </CardBody></Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
