import { X } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";

export function TagInput({
  id,
  value,
  onChange,
  placeholder = "Type and press Enter",
}: {
  id: string;
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const tag = draft.trim().replace(/,$/, "");
    if (tag && !value.includes(tag)) onChange([...value, tag]);
    setDraft("");
  };
  return (
    <div className="flex min-h-9 flex-wrap items-center gap-1 rounded-md border border-input bg-card px-2 py-1 focus-within:ring-2 focus-within:ring-ring">
      {value.map((tag) => (
        <Badge key={tag} variant="secondary" className="gap-1">
          {tag}
          <button
            type="button"
            aria-label={`Remove ${tag}`}
            onClick={() => {
              onChange(value.filter((t) => t !== tag));
            }}
          >
            <X className="size-3" aria-hidden />
          </button>
        </Badge>
      ))}
      <input
        id={id}
        className="min-w-24 flex-1 bg-transparent text-sm outline-none"
        value={draft}
        placeholder={value.length ? "" : placeholder}
        onChange={(e) => {
          setDraft(e.target.value);
        }}
        onBlur={add}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            add();
          } else if (e.key === "Backspace" && !draft && value.length) {
            onChange(value.slice(0, -1));
          }
        }}
      />
    </div>
  );
}
