import type { UserBatchItem } from "./types";

export interface RosterParse {
  items: UserBatchItem[];
  /** Lines that had no separable employee number and name, quoted back so the admin can fix them. */
  invalid: string[];
}

// A roster pasted from Excel arrives tab-separated; one typed by hand uses
// spaces or Chinese punctuation. Accept all of them so nobody has to reformat.
const SEPARATOR = /[\s,，、;；]+/;
const HEADER_WORDS = new Set(["工号", "姓名", "教师", "教师姓名", "教工号", "序号"]);

export function parseTeacherRoster(text: string): RosterParse {
  const items: UserBatchItem[] = [];
  const invalid: string[] = [];
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    const tokens = line.split(SEPARATOR).filter(Boolean);
    if (tokens.every((token) => HEADER_WORDS.has(token))) continue;
    if (tokens.length < 2) {
      invalid.push(line);
      continue;
    }
    // Names never contain digits and employee numbers usually do; when a line
    // is pasted as "姓名 工号" instead, take whichever token carries digits.
    const [first, ...rest] = tokens;
    const last = tokens[tokens.length - 1];
    if (!/\d/.test(first) && /\d/.test(last)) {
      items.push({ employee_no: last, name: tokens.slice(0, -1).join("") });
    } else {
      items.push({ employee_no: first, name: rest.join("") });
    }
  }
  return { items, invalid };
}
