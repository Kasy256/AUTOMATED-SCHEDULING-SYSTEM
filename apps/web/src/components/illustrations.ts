import empty from "@/assets/illustrations/empty.svg";
import importFiles from "@/assets/illustrations/import.svg";
import setup from "@/assets/illustrations/setup.svg";
import signIn from "@/assets/illustrations/sign-in.svg";
import team from "@/assets/illustrations/team.svg";

// unDraw illustrations (https://undraw.co, free licence, recoloured to the brand teal on download).
export const ILLUSTRATIONS = {
  empty,
  import: importFiles,
  setup,
  "sign-in": signIn,
  team,
} as const;
export type IllustrationName = keyof typeof ILLUSTRATIONS;
