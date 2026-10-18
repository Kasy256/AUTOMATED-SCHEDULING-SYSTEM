import { apiResponse } from "@/api/client";

export async function downloadFromApi(
  url: string,
  fallbackName: string,
): Promise<void> {
  const res = await apiResponse(url);
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName;
  const href = URL.createObjectURL(await res.blob());
  const link = document.createElement("a");
  link.href = href;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(href);
}
