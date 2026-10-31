import { fetchAuthSession } from "aws-amplify/auth";

export interface ParsedAgendaItem {
  topic: string;
  owner: string | null;
  minutes: number | null;
}

export interface ParsedActionItem {
  task: string;
  owner: string | null;
  due: string | null;
}

export interface ParsedAgenda {
  title: string | null;
  starts_at: string | null;
  duration_minutes: number | null;
  items: ParsedAgendaItem[];
  action_items: ParsedActionItem[];
  language: string;
}

export interface ParseResult {
  agenda: ParsedAgenda;
  model: string;
  prompt_version: string;
}

export class ParseError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.status = status;
  }
}

const PARSER_URL = import.meta.env.VITE_PARSER_URL as string;

// YYYY-MM-DD in the user's own time zone, not UTC
function todayLocal(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

async function errorFrom(response: Response): Promise<ParseError> {
  let serverMessage = "";
  try {
    const body = (await response.json()) as { error?: string };
    serverMessage = body.error ?? "";
  } catch {
    // no JSON body
  }
  switch (response.status) {
    case 401:
      return new ParseError("Сесія завершилась. Увійдіть знову.", 401);
    case 413:
      return new ParseError("Текст задовгий (максимум 10 000 символів).", 413);
    case 422:
      return new ParseError(
        "Не вдалося знайти порядок денний у тексті. Введіть його вручну.",
        422,
      );
    case 429:
      return new ParseError("Сервіс зайнятий. Спробуйте за хвилину.", 429);
    default:
      return new ParseError(
        serverMessage || "Сервіс недоступний. Введіть порядок денний вручну.",
        response.status,
      );
  }
}

export async function parseAgenda(text: string, signal?: AbortSignal): Promise<ParseResult> {
  const session = await fetchAuthSession();
  const token = session.tokens?.accessToken?.toString();
  if (!token) throw new ParseError("Сесія завершилась. Увійдіть знову.", 401);

  let response: Response;
  try {
    response = await fetch(PARSER_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        text,
        today: todayLocal(),
        tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
      }),
      signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ParseError("Немає зв'язку з сервісом. Введіть порядок денний вручну.");
  }
  if (!response.ok) throw await errorFrom(response);
  return (await response.json()) as ParseResult;
}
