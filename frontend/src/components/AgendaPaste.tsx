import { useRef, useState } from "react";
import { parseAgenda, ParseError, type ParsedAgenda, type ParseResult } from "@/api/agendaParser";
import { createMeeting, saveAgenda } from "@/api/meetings";
import { Button } from "@/components/ui/button";
import type { Meeting } from "@/types/meeting";

const MAX_TEXT = 10_000;
const inputClass = "mt-1 w-full rounded-md border p-2 text-sm";

interface Draft {
  title: string;
  startsAt: string;
  duration: string;
  items: { topic: string; owner: string; minutes: string }[];
  actions: { task: string; owner: string; due: string }[];
}

const emptyItem = () => ({ topic: "", owner: "", minutes: "" });

function emptyDraft(): Draft {
  return { title: "", startsAt: "", duration: "", items: [emptyItem()], actions: [] };
}

// Every field the model filled is remembered, so it can carry a "suggested" badge
function toDraft(a: ParsedAgenda): { draft: Draft; suggested: Set<string> } {
  const suggested = new Set<string>();
  const mark = (key: string, value: string) => {
    if (value !== "") suggested.add(key);
    return value;
  };
  const draft: Draft = {
    title: mark("title", a.title ?? ""),
    startsAt: mark("startsAt", a.starts_at ? a.starts_at.slice(0, 16) : ""),
    duration: mark("duration", a.duration_minutes?.toString() ?? ""),
    items: a.items.map((it, i) => ({
      topic: mark(`item.${i}.topic`, it.topic),
      owner: mark(`item.${i}.owner`, it.owner ?? ""),
      minutes: mark(`item.${i}.minutes`, it.minutes?.toString() ?? ""),
    })),
    actions: a.action_items.map((it, i) => ({
      task: mark(`action.${i}.task`, it.task),
      owner: mark(`action.${i}.owner`, it.owner ?? ""),
      due: mark(`action.${i}.due`, it.due ?? ""),
    })),
  };
  return { draft, suggested };
}

function Badge({ show }: { show: boolean }) {
  return show ? (
    <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-xs font-normal text-amber-800">
      suggested
    </span>
  ) : null;
}

interface AgendaPasteProps {
  meetings: Meeting[];
  onChanged: () => void;
}

export function AgendaPaste({ meetings, onChanged }: AgendaPasteProps) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [suggested, setSuggested] = useState<Set<string>>(new Set());
  const [suggestion, setSuggestion] = useState<ParseResult | null>(null);
  const [target, setTarget] = useState("new");
  const abortRef = useRef<AbortController | null>(null);

  async function handleParse() {
    const controller = new AbortController();
    abortRef.current = controller;
    setBusy(true);
    setError(null);
    setNotice(null);
    setDraft(null);
    try {
      const result = await parseAgenda(text, controller.signal);
      const converted = toDraft(result.agenda);
      setDraft(converted.draft);
      setSuggested(converted.suggested);
      setSuggestion(result);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setError(
        e instanceof ParseError
          ? e.message
          : "Щось пішло не так. Введіть порядок денний вручну.",
      );
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  }

  function startManual() {
    setDraft(emptyDraft());
    setSuggested(new Set());
    setSuggestion(null);
    setError(null);
    setNotice(null);
  }

  // The badge disappears as soon as the user edits a field
  function touch(key: string) {
    setSuggested((prev) => {
      if (!prev.has(key)) return prev;
      const next = new Set(prev);
      next.delete(key);
      return next;
    });
  }

  function setField(key: "title" | "startsAt" | "duration", value: string) {
    setDraft((d) => (d ? { ...d, [key]: value } : d));
    touch(key);
  }

  function setItem(i: number, field: "topic" | "owner" | "minutes", value: string) {
    setDraft((d) =>
      d
        ? { ...d, items: d.items.map((it, idx) => (idx === i ? { ...it, [field]: value } : it)) }
        : d,
    );
    touch(`item.${i}.${field}`);
  }

  function setAction(i: number, field: "task" | "owner" | "due", value: string) {
    setDraft((d) =>
      d
        ? {
            ...d,
            actions: d.actions.map((it, idx) => (idx === i ? { ...it, [field]: value } : it)),
          }
        : d,
    );
    touch(`action.${i}.${field}`);
  }

  function addItem() {
    setDraft((d) => (d ? { ...d, items: [...d.items, emptyItem()] } : d));
  }

  async function handleSave() {
    if (!draft) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const items = draft.items
        .filter((it) => it.topic.trim() !== "")
        .map((it) => ({
          topic: it.topic.trim(),
          owner: it.owner.trim() || null,
          minutes: it.minutes ? Number(it.minutes) : null,
        }));
      if (items.length === 0) {
        throw new Error("Додайте хоча б один пункт порядку денного.");
      }
      const actions = draft.actions
        .filter((it) => it.task.trim() !== "")
        .map((it) => ({
          task: it.task.trim(),
          owner: it.owner.trim() || null,
          due: it.due || null,
        }));

      let meetingId: number;
      if (target === "new") {
        if (!draft.title.trim() || !draft.startsAt || !draft.duration) {
          throw new Error("Для нової зустрічі вкажіть назву, початок і тривалість.");
        }
        const start = new Date(draft.startsAt);
        const end = new Date(start.getTime() + Number(draft.duration) * 60_000);
        const meeting = await createMeeting({
          title: draft.title.trim(),
          starts_at: start.toISOString(),
          ends_at: end.toISOString(),
          attendee_count: 0,
        });
        meetingId = meeting.id;
        setTarget(String(meeting.id)); // a retry then reuses this meeting instead of creating another
        onChanged();
      } else {
        meetingId = Number(target);
      }

      await saveAgenda(meetingId, {
        items,
        action_items: actions,
        ai_suggestion: suggestion?.agenda ?? null,
        ai_model: suggestion?.model ?? null,
        prompt_version: suggestion?.prompt_version ?? null,
      });
      setNotice("Порядок денний збережено.");
      setDraft(null);
      setSuggestion(null);
      setText("");
      setTarget("new");
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не вдалося зберегти.");
    } finally {
      setSaving(false);
    }
  }

  const tooLong = text.length > MAX_TEXT;

  return (
    <section className="mb-8 rounded-xl border bg-white p-4">
      <h2 className="text-lg font-semibold">Paste an agenda</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Вставте лист або нотатки. Ми запропонуємо порядок денний, а ви перевірите його перед
        збереженням.
      </p>

      <textarea
        rows={6}
        value={text}
        disabled={busy}
        onChange={(e) => setText(e.target.value)}
        className={inputClass}
      />
      <div className={`mt-1 text-xs ${tooLong ? "text-red-600" : "text-muted-foreground"}`}>
        {text.length} / {MAX_TEXT}
      </div>

      <div className="mt-3 flex items-center gap-2">
        <Button
          size="sm"
          disabled={busy || text.trim() === "" || tooLong}
          onClick={() => void handleParse()}
        >
          Parse
        </Button>
        {!draft && !busy && (
          <Button size="sm" onClick={startManual}>
            Ввести вручну
          </Button>
        )}
        {busy && (
          <>
            <span className="text-sm text-muted-foreground">
              Розбираємо текст... це може тривати до 10 секунд
            </span>
            <Button size="sm" onClick={() => abortRef.current?.abort()}>
              Cancel
            </Button>
          </>
        )}
      </div>

      {error && (
        <div className="mt-3 rounded-md bg-red-50 p-3 text-sm text-red-600">{error}</div>
      )}
      {notice && (
        <div className="mt-3 rounded-md bg-green-50 p-3 text-sm text-green-700">{notice}</div>
      )}

      {draft && (
        <div className="mt-5 space-y-4 border-t pt-4">
          {suggestion && draft.items.length === 0 && (
            <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-800">
              Пунктів порядку денного не знайдено. Схоже, у тексті його немає.
            </p>
          )}

          <div>
            <label className="text-sm font-medium">Куди зберегти</label>
            <select
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              className={inputClass}
            >
              <option value="new">Нова зустріч (за даними нижче)</option>
              {meetings.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.title} ({new Date(m.starts_at).toLocaleString("uk-UA")})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-sm font-medium">
              Назва
              <Badge show={suggested.has("title")} />
            </label>
            <input
              type="text"
              value={draft.title}
              onChange={(e) => setField("title", e.target.value)}
              className={inputClass}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium">
                Початок
                <Badge show={suggested.has("startsAt")} />
              </label>
              <input
                type="datetime-local"
                value={draft.startsAt}
                onChange={(e) => setField("startsAt", e.target.value)}
                className={inputClass}
              />
            </div>
            <div>
              <label className="text-sm font-medium">
                Тривалість, хв
                <Badge show={suggested.has("duration")} />
              </label>
              <input
                type="number"
                min={1}
                value={draft.duration}
                onChange={(e) => setField("duration", e.target.value)}
                className={inputClass}
              />
            </div>
          </div>

          <h3 className="text-sm font-semibold">Порядок денний</h3>
          {draft.items.map((it, i) => (
            <div key={i} className="grid grid-cols-[1fr_9rem_5rem] gap-2">
              <div>
                <label className="text-xs font-medium">
                  Тема
                  <Badge show={suggested.has(`item.${i}.topic`)} />
                </label>
                <input
                  type="text"
                  value={it.topic}
                  onChange={(e) => setItem(i, "topic", e.target.value)}
                  className={inputClass}
                />
              </div>
              <div>
                <label className="text-xs font-medium">
                  Хто
                  <Badge show={suggested.has(`item.${i}.owner`)} />
                </label>
                <input
                  type="text"
                  value={it.owner}
                  onChange={(e) => setItem(i, "owner", e.target.value)}
                  className={inputClass}
                />
              </div>
              <div>
                <label className="text-xs font-medium">
                  Хв
                  <Badge show={suggested.has(`item.${i}.minutes`)} />
                </label>
                <input
                  type="number"
                  min={1}
                  value={it.minutes}
                  onChange={(e) => setItem(i, "minutes", e.target.value)}
                  className={inputClass}
                />
              </div>
            </div>
          ))}
          <Button size="sm" onClick={addItem}>
            + Додати пункт
          </Button>

          {draft.actions.length > 0 && <h3 className="text-sm font-semibold">Завдання</h3>}
          {draft.actions.map((it, i) => (
            <div key={i} className="grid grid-cols-[1fr_9rem_9rem] gap-2">
              <div>
                <label className="text-xs font-medium">
                  Завдання
                  <Badge show={suggested.has(`action.${i}.task`)} />
                </label>
                <input
                  type="text"
                  value={it.task}
                  onChange={(e) => setAction(i, "task", e.target.value)}
                  className={inputClass}
                />
              </div>
              <div>
                <label className="text-xs font-medium">
                  Хто
                  <Badge show={suggested.has(`action.${i}.owner`)} />
                </label>
                <input
                  type="text"
                  value={it.owner}
                  onChange={(e) => setAction(i, "owner", e.target.value)}
                  className={inputClass}
                />
              </div>
              <div>
                <label className="text-xs font-medium">
                  До
                  <Badge show={suggested.has(`action.${i}.due`)} />
                </label>
                <input
                  type="date"
                  value={it.due}
                  onChange={(e) => setAction(i, "due", e.target.value)}
                  className={inputClass}
                />
              </div>
            </div>
          ))}

          <div className="flex justify-end border-t pt-4">
            <Button disabled={saving} onClick={() => void handleSave()}>
              {saving ? "Збереження..." : "Save"}
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
