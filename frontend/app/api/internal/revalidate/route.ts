import {timingSafeEqual} from "node:crypto";
import {revalidatePath, revalidateTag} from "next/cache";
import {NextResponse} from "next/server";

export async function POST(request: Request) {
  const secret = process.env.CATALOG_REVALIDATION_SECRET;
  const provided = request.headers.get("authorization") || "";
  const expected = `Bearer ${secret || ""}`;
  if (!secret || Buffer.byteLength(provided) !== Buffer.byteLength(expected) ||
      !timingSafeEqual(Buffer.from(provided), Buffer.from(expected))) {
    return NextResponse.json({error: "Unauthorized"}, {status: 401, headers: {"Cache-Control": "private, no-store"}});
  }
  revalidateTag("catalog", {expire: 0});
  revalidateTag("project-details", {expire: 0});
  revalidatePath("/[locale]", "page");
  revalidatePath("/[locale]/projects/[slug]", "page");
  return NextResponse.json({revalidated: true}, {headers: {"Cache-Control": "private, no-store"}});
}
