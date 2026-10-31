import { useCallback, useEffect, useState } from "react";
import {
  fetchAuthSession,
  getCurrentUser,
  signInWithRedirect,
  signOut,
} from "aws-amplify/auth";
import { Hub } from "aws-amplify/utils";
import { Plus } from "lucide-react";
import { listMeetings } from "@/api/meetings";
import { MeetingCard } from "@/components/MeetingCard";
import { NewMeetingDialog } from "@/components/NewMeetingDialog";
import { Button } from "@/components/ui/button";
import { AgendaPaste } from "@/components/AgendaPaste";
import type { Meeting } from "@/types/meeting";

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authLoading, setAuthLoading] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);

  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    const returningFromLogin = new URLSearchParams(window.location.search).has("code");

    async function checkUser() {
      try {
        await getCurrentUser();
        setIsAuthenticated(true);
        setAuthLoading(false);
        const session = await fetchAuthSession();
        const claim = session.tokens?.idToken?.payload.email;
        setEmail(typeof claim === "string" ? claim : null);
      } catch {
        // Amplify is still exchanging the code; the Hub event below will call us again
        if (returningFromLogin) return;
        setAuthLoading(false);
        await signInWithRedirect();
      }
    }

    const stop = Hub.listen("auth", ({ payload }) => {
      if (payload.event === "signInWithRedirect") {
        window.history.replaceState({}, "", window.location.pathname);
        void checkUser();
      }
      if (payload.event === "signInWithRedirect_failure") {
        setAuthLoading(false);
        setAuthError("Не вдалося увійти. Спробуйте ще раз.");
      }
    });

    void checkUser();
    return stop;
  }, []);

  const load = useCallback(async () => {
    try {
      setError(null);
      setMeetings(await listMeetings());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не вдалося завантажити зустрічі");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      void load();
    }
  }, [isAuthenticated, load]);

  if (authLoading) {
    return <div className="p-8 text-center text-muted-foreground">Завантаження...</div>;
  }

  if (!isAuthenticated) {
    return (
      <div className="p-8 text-center text-muted-foreground">
        <p>{authError ?? "Перенаправлення на вхід..."}</p>
        <Button className="mt-4" onClick={() => void signInWithRedirect()}>
          Увійти
        </Button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-50">
      <main className="mx-auto max-w-2xl px-6 py-14">
        <header className="mb-8 flex items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">Meetings</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {email ? `Ви увійшли як ${email}` : "Заплановані відеодзвінки та події"}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button size="sm" className="gap-1.5" onClick={() => setDialogOpen(true)}>
              <Plus className="h-4 w-4" />
              New meeting
            </Button>
            <Button size="sm" onClick={() => void signOut()}>
              Sign out
            </Button>
          </div>
        </header>

        <AgendaPaste meetings={meetings} onChanged={() => void load()} />

        <NewMeetingDialog
          open={dialogOpen}
          onOpenChange={setDialogOpen}
          onCreated={() => void load()}
        />

        {error && (
          <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-600">{error}</div>
        )}

        {loading ? (
          <p className="text-sm text-muted-foreground">Завантаження розкладу...</p>
        ) : meetings.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            У вас поки немає запланованих зустрічей.
          </p>
        ) : (
          <div className="space-y-3">
            {meetings.map((m) => (
              <MeetingCard key={m.id} meeting={m} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
