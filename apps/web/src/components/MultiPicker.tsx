import { Check, ChevronsUpDown, X } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

export interface PickerOption {
  value: string;
  label: string;
  group?: string;
}

function groups(options: PickerOption[]): [string, PickerOption[]][] {
  const map = new Map<string, PickerOption[]>();
  for (const o of options)
    map.set(o.group ?? "", [...(map.get(o.group ?? "") ?? []), o]);
  return [...map];
}

function OptionList({
  options,
  isSelected,
  onPick,
}: {
  options: PickerOption[];
  isSelected: (v: string) => boolean;
  onPick: (v: string) => void;
}) {
  return (
    <Command>
      <CommandInput placeholder="Search…" />
      <CommandList>
        <CommandEmpty>Nothing found.</CommandEmpty>
        {groups(options).map(([group, items]) => (
          <CommandGroup key={group} heading={group || undefined}>
            {items.map((o) => (
              <CommandItem
                key={o.value}
                value={`${o.label} ${o.value}`}
                onSelect={() => onPick(o.value)}
              >
                <Check
                  className={
                    isSelected(o.value) ? "size-4" : "size-4 opacity-0"
                  }
                  aria-hidden
                />
                {o.label}
              </CommandItem>
            ))}
          </CommandGroup>
        ))}
      </CommandList>
    </Command>
  );
}

export function MultiPicker({
  id,
  label,
  options,
  value,
  onChange,
  placeholder = "Choose…",
  disabled,
}: {
  id: string;
  label: string;
  options: PickerOption[];
  value: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const labelOf = (v: string) =>
    options.find((o) => o.value === v)?.label ?? "Unknown item";
  return (
    <div className="flex flex-col gap-1.5">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            id={id}
            type="button"
            variant="outline"
            className="justify-between font-normal"
            disabled={disabled}
            aria-label={label}
          >
            <span className="truncate text-muted-foreground">
              {value.length ? `${String(value.length)} selected` : placeholder}
            </span>
            <ChevronsUpDown className="size-4 opacity-60" aria-hidden />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-80 p-0" align="start">
          <OptionList
            options={options}
            isSelected={(v) => value.includes(v)}
            onPick={(v) =>
              onChange(
                value.includes(v)
                  ? value.filter((x) => x !== v)
                  : [...value, v],
              )
            }
          />
        </PopoverContent>
      </Popover>
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {value.map((v) => (
            <Badge key={v} variant="secondary" className="gap-1">
              {labelOf(v)}
              {!disabled && (
                <button
                  type="button"
                  aria-label={`Remove ${labelOf(v)}`}
                  onClick={() => onChange(value.filter((x) => x !== v))}
                >
                  <X className="size-3" aria-hidden />
                </button>
              )}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

export function SinglePicker({
  id,
  label,
  options,
  value,
  onChange,
  allowClear = false,
  placeholder = "Choose…",
}: {
  id: string;
  label: string;
  options: PickerOption[];
  value: string | null;
  onChange: (value: string | null) => void;
  allowClear?: boolean;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const current = options.find((o) => o.value === value);
  return (
    <div className="flex items-center gap-1">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            id={id}
            type="button"
            variant="outline"
            className="flex-1 justify-between font-normal"
            aria-label={label}
          >
            <span
              className={
                current ? "truncate" : "truncate text-muted-foreground"
              }
            >
              {current?.label ?? placeholder}
            </span>
            <ChevronsUpDown className="size-4 opacity-60" aria-hidden />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-80 p-0" align="start">
          <OptionList
            options={options}
            isSelected={(v) => v === value}
            onPick={(v) => {
              onChange(v);
              setOpen(false);
            }}
          />
        </PopoverContent>
      </Popover>
      {allowClear && value !== null && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label={`Clear ${label}`}
          onClick={() => onChange(null)}
        >
          <X className="size-4" aria-hidden />
        </Button>
      )}
    </div>
  );
}
