import { describe, expect, it } from "vitest";

import { parseTeacherRoster } from "./teacherRoster";

describe("parseTeacherRoster", () => {
  it("reads tab-separated rows pasted from a spreadsheet and skips the header", () => {
    const parsed = parseTeacherRoster("工号\t姓名\n2019001\t张明\n2019002\t李华\n");

    expect(parsed.items).toEqual([
      { employee_no: "2019001", name: "张明" },
      { employee_no: "2019002", name: "李华" }
    ]);
    expect(parsed.invalid).toEqual([]);
  });

  it("accepts spaces and Chinese punctuation as separators", () => {
    const parsed = parseTeacherRoster("2019001 张明\n2019002，李华\n2019003、王 芳");

    expect(parsed.items.map((item) => item.name)).toEqual(["张明", "李华", "王芳"]);
  });

  it("puts the token carrying digits in the employee number when the order is reversed", () => {
    const parsed = parseTeacherRoster("张明 2019001");

    expect(parsed.items).toEqual([{ employee_no: "2019001", name: "张明" }]);
  });

  it("reports lines that cannot be split so the admin fixes them instead of importing junk", () => {
    const parsed = parseTeacherRoster("2019001 张明\n只有一个词\n\n2019002 李华");

    expect(parsed.items).toHaveLength(2);
    expect(parsed.invalid).toEqual(["只有一个词"]);
  });
});
