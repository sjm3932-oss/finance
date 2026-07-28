import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { OcrReviewPanel } from "@/components/OcrReviewPanel";

export const dynamic = "force-dynamic";

export default async function OcrReviewPage({
  searchParams,
}: {
  searchParams: Promise<{ id?: string }>;
}) {
  const sp = await searchParams;
  const supabase = await createClient();
  const { data: rows } = await supabase
    .from("ocr_staging")
    .select("id,status,image_url,parsed_json,created_at")
    .in("status", ["pending", "failed"])
    .order("created_at", { ascending: false })
    .limit(20);

  const items = [];
  for (const r of rows || []) {
    let signed: string | null = null;
    if (r.image_url) {
      const { data } = await supabase.storage
        .from("ocr-screenshots")
        .createSignedUrl(r.image_url, 3600);
      signed = data?.signedUrl || null;
    }
    items.push({ ...r, signed_url: signed });
  }

  return (
    <div className="space-y-5">
      <div>
        <p className="text-xs font-bold text-muted">
          <Link href="/ocr" className="text-brand">
            OCR
          </Link>{" "}
          / 검토
        </p>
        <h1 className="mt-1 text-xl font-extrabold tracking-tight">OCR 승인</h1>
        <p className="mt-1 text-sm text-muted">
          pending/failed만 표시 · 승인 시 DB 트리거가 반영
        </p>
      </div>
      <OcrReviewPanel items={items} focusId={sp.id} />
    </div>
  );
}
