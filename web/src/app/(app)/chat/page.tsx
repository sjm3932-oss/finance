import { createClient } from "@/lib/supabase/server";
import { ChatClient } from "@/components/ChatClient";

export const dynamic = "force-dynamic";

export default async function ChatPage() {
  const supabase = await createClient();
  const { data: logs } = await supabase
    .from("ai_chat_logs")
    .select("user_query,ai_response,created_at")
    .neq("user_query", "morning_briefing")
    .order("created_at", { ascending: false })
    .limit(12);

  const initialTurns = (logs || [])
    .reverse()
    .flatMap((l) => {
      const turns: { role: "user" | "model"; content: string }[] = [];
      if (l.user_query) turns.push({ role: "user", content: l.user_query });
      if (l.ai_response) turns.push({ role: "model", content: l.ai_response });
      return turns;
    });

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-extrabold tracking-tight">자산 챗</h1>
        <p className="mt-1 text-sm text-muted">
          Edge Function · Gemini · 보유/시세 컨텍스트 기반
        </p>
      </div>
      <ChatClient initialTurns={initialTurns} />
    </div>
  );
}
