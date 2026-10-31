import type { Meeting, MeetingCreate } from "@/types/meeting";

interface ValidationError {
  msg: string;
}

interface ErrorBody {
  detail?: ValidationError[] | string;
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as ErrorBody | null;
    const detail = body?.detail;
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((d) => d.msg).join("; ");
    }
  } catch {
    // fall through to the generic message
  }
  return `Request failed (${response.status})`;
}

export async function listMeetings(): Promise<Meeting[]> {
  const response = await fetch("/api/meetings");
  if (!response.ok) throw new Error(await errorMessage(response));
  return (await response.json()) as Meeting[];
}

export async function createMeeting(input: MeetingCreate): Promise<Meeting> {
  const response = await fetch("/api/meetings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  return (await response.json()) as Meeting;
}

export interface AgendaSavePayload {
  items: { topic: string; owner: string | null; minutes: number | null }[];
  action_items: { task: string; owner: string | null; due: string | null }[];
  ai_suggestion: unknown;
  ai_model: string | null;
  prompt_version: string | null;
}

export async function saveAgenda(meetingId: number, payload: AgendaSavePayload): Promise<void> {
  const response = await fetch(`/api/meetings/${meetingId}/agenda`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await errorMessage(response));
}
