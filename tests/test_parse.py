#!/usr/bin/env python3
"""解析器回归测试。

样本是真实教务系统页面脱敏后的副本（课程名、教师、教室、学号都换成了虚构值，
HTML 结构与周次/节次等字段保持原样），因此可以在公开仓库里安全运行。
"""

from __future__ import annotations

import sys
from pathlib import Path

# Windows 默认控制台是 GBK，这里做一次兜底，避免个别字符导致脚本崩溃
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from hhu import parse  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_periods() -> None:
    data = parse.parse_schedule_page(load("xskb_list.html"))
    periods = data["periods"]
    check(len(periods) == 5, f"应有 5 个大节，实际 {len(periods)}")
    times = [p["time"] for p in periods]
    check(
        times == ["08:00-09:35", "09:50-12:15", "14:00-15:35", "15:50-17:25", "18:30-20:55"],
        f"节次时间不符：{times}",
    )
    check(periods[1]["sections"] == [3, 4, 5], f"第二大节小节号不符：{periods[1]['sections']}")
    check(periods[4]["sections"] == [10, 11, 12], f"第五大节小节号不符：{periods[4]['sections']}")


def test_schedule() -> None:
    data = parse.parse_schedule_page(load("xskb_list.html"))
    check(data["term"] == "2026-2027-1", f"学期解析错误：{data['term']}")
    courses = data["courses"]
    check(len(courses) == 20, f"课程块数应为 20，实际 {len(courses)}")

    # 同一门课同一格里的多段周次会被拆成多条，且每条都能独立判断周次。
    analysis = [c for c in courses if c["name"] == "分析课程戊" and c["day"] == 3 and c["bigPeriod"] == 3]
    check(len(analysis) == 3, f"周三第三大节应有 3 段安排，实际 {len(analysis)}")
    check(analysis[0]["weeks"] == [[1, 10]], f"周次解析错误：{analysis[0]['weeks']}")
    check(analysis[1]["weeks"] == [[15, 17]], f"周次解析错误：{analysis[1]['weeks']}")
    check(analysis[2]["weeks"] == [[18, 18]], f"周次解析错误：{analysis[2]['weeks']}")
    check(analysis[0]["sections"] == [6, 7, 8], f"节次解析错误：{analysis[0]['sections']}")
    check(analysis[2]["sections"] == [6, 7], f"节次解析错误：{analysis[2]['sections']}")
    check(analysis[0]["teacher"] == "教师卯", f"教师解析错误：{analysis[0]['teacher']}")
    check(analysis[0]["room"] == "四号楼404", f"教室解析错误：{analysis[0]['room']}")
    check("QQ群" in analysis[0]["note"], f"网课群号应作为备注保留：{analysis[0]['note']}")

    # 学时 (理论:32)、通知单编号、班级等字段不应被当成课程
    names = {c["name"] for c in courses}
    check(names == {"分析课程戊", "方法课程丁", "实践课程甲", "统计课程乙", "英语课程丙", "政策课程己"},
          f"课程名集合不符：{sorted(names)}")

    # 周日第二大节的英语课有 1 周与 5 周两段
    english = [c for c in courses if c["name"] == "英语课程丙" and c["day"] == 7]
    check(len(english) == 2, f"周日英语课应有 2 段，实际 {len(english)}")
    check([c["weeks"] for c in english] == [[[1, 1]], [[5, 5]]], "周日英语课周次解析错误")

    # 只填了群号（纯数字）的课程，群号应作为备注保留
    policy = [c for c in courses if c["name"] == "政策课程己"]
    check(len(policy) == 1 and policy[0]["note"] == "100000000", f"群号备注解析错误：{policy}")


def test_other_courses() -> None:
    data = parse.parse_schedule_page(load("xskb_list.html"))
    other = data["otherCourses"]
    check(len(other) == 1, f"应有 1 门无课表课程，实际 {len(other)}")
    check(other[0]["name"] == "实习课程庚", f"课程名错误：{other[0]['name']}")
    check(other[0]["teacher"] == "教师辰", f"教师错误：{other[0]['teacher']}")
    check(other[0]["kind"] == "实践课程", f"课程性质错误：{other[0]['kind']}")


def test_calendar() -> None:
    calendar = parse.parse_calendar_page(load("jxzl.html"))
    check(calendar["startDate"] == "2026-09-07", f"第 1 周起始日期错误：{calendar['startDate']}")
    check(calendar["totalWeeks"] == 20, f"总周数错误：{calendar['totalWeeks']}")
    check(calendar["term"] == "2026-2027-1", f"学期代码错误：{calendar['term']}")
    check(calendar["weeks"][0]["end"] == "2026-09-13", f"第 1 周结束日期错误：{calendar['weeks'][0]}")
    check(calendar["weeks"][-1]["start"] == "2027-01-18", f"第 20 周起始错误：{calendar['weeks'][-1]}")


def test_room_cleaning() -> None:
    """教室字段会把教学楼拼两遍，这里用真实形态校验收敛规则。"""
    cases = [
        ("博学楼博学楼B403", "【博学楼】", "博学楼B403"),
        ("励学楼励学楼110", "【励学楼】", "励学楼110"),
        ("致用楼A区致用楼417", "【致用楼A区】", "致用楼A区417"),
        ("2号楼C区2号楼C区C410", "【2号楼C区】", "2号楼C区C410"),
        ("普通教室101", "【某楼】", "普通教室101"),
        ("励学楼110", "【励学楼】", "励学楼110"),
    ]
    for room, building, expected in cases:
        got = parse._clean_room(room, building)
        check(got == expected, f"教室清洗错误：{room} + {building} -> {got}，期望 {expected}")


def test_weeks_parsing() -> None:
    cases = [
        ("1-10(周)[6-7-8节]", [[1, 10]], None, [6, 7, 8]),
        ("12(周)[3-4节]", [[12, 12]], None, [3, 4]),
        ("1-16(单周)", [[1, 16]], "单", []),
        ("2-16(双周)[1-2节]", [[2, 16]], "双", [1, 2]),
        ("1-8,10-12(周)", [[1, 8], [10, 12]], None, []),
        ("3-5,6-7(周)", [[3, 7]], None, []),
        ("", [], None, []),
    ]
    for raw, weeks, parity, sections in cases:
        got_weeks, got_parity = parse.parse_weeks(raw)
        got_sections = parse.parse_sections(raw)
        check(got_weeks == weeks, f"周次解析错误：{raw!r} -> {got_weeks}，期望 {weeks}")
        check(got_parity == parity, f"单双周解析错误：{raw!r} -> {got_parity}，期望 {parity}")
        check(got_sections == sections, f"节次解析错误：{raw!r} -> {got_sections}，期望 {sections}")


def main() -> int:
    tests = [
        test_periods,
        test_schedule,
        test_other_courses,
        test_calendar,
        test_room_cleaning,
        test_weeks_parsing,
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"  [OK] {test.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"  [FAIL] {test.__name__}: {exc}")
    print(f"解析测试：{len(tests) - failures}/{len(tests)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
