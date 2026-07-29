"use server";

import { revalidatePath } from "next/cache";
import { requireAllowedUser } from "@/lib/actions/auth";
import type { ActionResult } from "@/lib/record";

function fail(m: string): ActionResult {
  return { ok: false, message: m };
}
function ok(m: string): ActionResult {
  return { ok: true, message: m };
}

export async function saveOcrStaging(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase } = await requireAllowedUser();
    const id = String(formData.get("id") || "");
    const raw = String(formData.get("parsed_json") || "");
    if (!id) return fail("항목 id가 없습니다.");
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      return fail("JSON 형식이 올바르지 않습니다.");
    }
    const { error } = await supabase
      .from("ocr_staging")
      .update({ parsed_json: parsed })
      .eq("id", id);
    if (error) return fail(error.message);
    revalidatePath("/ocr");
    revalidatePath("/ocr/review");
    return ok("수정 내용을 저장했습니다.");
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패");
  }
}

export async function setOcrStatus(formData: FormData): Promise<ActionResult> {
  try {
    const { supabase, user } = await requireAllowedUser();
    const id = String(formData.get("id") || "");
    const status = String(formData.get("status") || "");
    const raw = String(formData.get("parsed_json") || "");
    if (!id) return fail("항목 id가 없습니다.");
    if (!["approved", "rejected", "pending"].includes(status)) {
      return fail("status를 확인하세요.");
    }

    const patch: Record<string, unknown> = {
      status,
      reviewed_by: user.id,
      reviewed_at: new Date().toISOString(),
    };
    if (raw) {
      try {
        patch.parsed_json = JSON.parse(raw);
      } catch {
        return fail("JSON 형식이 올바르지 않습니다.");
      }
    }

    const { error } = await supabase
      .from("ocr_staging")
      .update(patch)
      .eq("id", id);
    if (error) return fail(error.message);
    revalidatePath("/ocr");
    revalidatePath("/ocr/review");
    revalidatePath("/");
    revalidatePath("/holdings");
    revalidatePath("/pnl");
    revalidatePath("/flows");
    return ok(
      status === "approved"
        ? "승인했습니다. DB 트리거가 반영합니다."
        : status === "rejected"
          ? "거절했습니다."
          : "상태를 변경했습니다."
    );
  } catch (e) {
    return fail(e instanceof Error ? e.message : "실패");
  }
}
