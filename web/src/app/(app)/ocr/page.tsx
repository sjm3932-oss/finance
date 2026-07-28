import Link from "next/link";
import { OcrUploadForm } from "@/components/OcrUploadForm";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function OcrPage() {
  const supabase = await createClient();
  const { data: accounts } = await supabase
    .from("accounts")
    .select("id,institution")
    .order("institution");

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-extrabold tracking-tight">OCR</h1>
        <p className="mt-1 text-sm text-muted">
          Edge Function · Gemini Vision ·{" "}
          <Link href="/ocr/review" className="font-semibold text-brand">
            검토·승인
          </Link>
        </p>
      </div>
      <OcrUploadForm accounts={accounts || []} />
      <p className="text-xs text-muted">
        Supabase에 <code>ocr-parse</code> Function이 배포되어 있고{" "}
        <code>GEMINI_API_KEY</code> secret이 있어야 합니다.
      </p>
    </div>
  );
}
