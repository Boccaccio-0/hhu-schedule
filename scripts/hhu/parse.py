"""解析河海大学教务系统（正方 jsxsd）的课表页与教学周历页。

页面实测特征：

* 课表页 ``/jsxsd/xskb/xskb_list.do`` 没有 charset 声明，实际编码是 UTF-8，
  必须显式按 UTF-8 解码，否则中文全是乱码。
* 课程信息位于 ``table#timetable`` 的 ``td > div.kbcontent`` 中；每个课程块由
  若干 ``<font>`` 组成，字段靠属性区分：
  ``title="教师"`` / ``title="周次(节次)"`` / ``title="教室"`` / ``title="教学楼"``，
  无 ``title`` 也无 ``name`` 的 ``<font>`` 是课程名；``name="wkxx"`` 是网课群号。
  隐藏字段（学时 ``xsks``、通知单编号 ``tzdbh``、班级 ``ktmcstr``）直接忽略。
* 同一个格子里的多段安排（例如第 2-11 周 + 第 12 周）用 ``-----`` 分隔成多个课程块。
* 教学周历页 ``/jsxsd/jxzl/jxzl_query`` 给出每周的起止日期与备注。
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

WEEKDAY_LABELS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

#: 解析不到节次时间时的兜底（正常情况都会被页面里的数据覆盖）。
DEFAULT_PERIODS = [
    {"index": 1, "name": "第一大节", "sections": [1, 2], "start": "", "end": "", "time": ""},
    {"index": 2, "name": "第二大节", "sections": [3, 4, 5], "start": "", "end": "", "time": ""},
    {"index": 3, "name": "第三大节", "sections": [6, 7], "start": "", "end": "", "time": ""},
    {"index": 4, "name": "第四大节", "sections": [8, 9], "start": "", "end": "", "time": ""},
    {"index": 5, "name": "第五大节", "sections": [10, 11, 12], "start": "", "end": "", "time": ""},
]

_PERIOD_RE = re.compile(
    r"(第[一二三四五六七八九十]+大节)\s*[（(]\s*(\d+)\s*-\s*(\d+)\s*小节\s*"
    r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\s*[)）]"
)
_WEEK_BLOCK_RE = re.compile(r"([\d\s\-–~,，、]+?)\s*[（(]\s*(周|单周|双周)\s*[)）]")
_WEEK_ITEM_RE = re.compile(r"(\d{1,2})(?:\s*[-–~]\s*(\d{1,2}))?")
_SECTION_RE = re.compile(r"\[([\d\-]+)\s*节\]")
_DATE_RE = re.compile(r"(\d{1,2})月(\d{1,2})日")
_TERM_RE = re.compile(r"(\d{4})-(\d{4})\s*学年\s*第\s*(\d+)\s*学期")


class ParseError(RuntimeError):
    """页面结构与预期不符时抛出。"""


def _text(node) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


# --------------------------------------------------------------------------- 节次


def parse_periods(soup: BeautifulSoup) -> list[dict]:
    """从页面红色小字里解析五个大节的节次与上课时间。"""
    periods: list[dict] = []
    for p in soup.find_all("p"):
        raw = _text(p).replace("\xa0", " ")
        for m in _PERIOD_RE.finditer(raw):
            name, sec_a, sec_b, start, end = m.groups()
            periods.append(
                {
                    "index": len(periods) + 1,
                    "name": name,
                    "sections": list(range(int(sec_a), int(sec_b) + 1)),
                    "start": start,
                    "end": end,
                    "time": f"{start}-{end}",
                }
            )
    return periods


# --------------------------------------------------------------------------- 周次/节次文本


def parse_weeks(raw: str) -> tuple[list[list[int]], str | None]:
    """解析 ``10-17(周)[1-2节]``、``1-8,10-12(周)`` 这类文本。

    返回 (周次区间列表, 单双周)。相邻或重叠的区间会被合并。
    """
    if not raw:
        return [], None
    spans: list[list[int]] = []
    parity: str | None = None
    for block in _WEEK_BLOCK_RE.finditer(raw):
        kind = block.group(2)
        if kind in ("单周", "双周") and parity is None:
            parity = "单" if kind == "单周" else "双"
        for item in _WEEK_ITEM_RE.finditer(block.group(1)):
            start = int(item.group(1))
            end = int(item.group(2)) if item.group(2) else start
            if end < start:
                start, end = end, start
            spans.append([start, end])
    spans.sort()
    merged: list[list[int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged, parity


def parse_sections(raw: str) -> list[int]:
    """解析 ``[6-7-8节]`` / ``[1-2节]``，返回小节号列表。"""
    m = _SECTION_RE.search(raw or "")
    if not m:
        return []
    parts = [p.strip() for p in m.group(1).split("-") if p.strip()]
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        a, b = int(parts[0]), int(parts[1])
        return list(range(min(a, b), max(a, b) + 1))
    return sorted({int(p) for p in parts if p.isdigit()})


def _clean_room(room: str, building: str) -> str:
    """页面会把教学楼名字拼在教室前面，有时会重复一遍。

    实测形态：

    * ``博学楼`` + ``博学楼B403`` → ``博学楼B403``
    * ``致用楼A区`` + ``致用楼417`` → ``致用楼A区417``（重复的是教学楼名的前缀）
    * ``2号楼C区`` + ``2号楼C区C410`` → ``2号楼C区C410``
    """
    room = room.strip()
    building = building.strip().strip("【】")
    if not building or not room.startswith(building):
        return room
    rest = room[len(building) :]
    for size in range(min(len(rest), len(building)), 1, -1):
        if building.startswith(rest[:size]):
            return building + rest[size:]
    return room


# --------------------------------------------------------------------------- 课程块


def _parse_font_blocks(div) -> list[dict]:
    """把一个课表格子里的课程块解析成字典列表。"""
    blocks: list[dict] = []
    current: dict | None = None

    def ensure_block() -> dict:
        nonlocal current
        if current is None:
            current = {"name": "", "teacher": "", "room": "", "building": "", "weeksRaw": "", "note": ""}
            blocks.append(current)
        return current

    for font in div.find_all("font"):
        title = font.get("title")
        name_attr = font.get("name")
        text = _text(font)

        if title == "教师":
            ensure_block()["teacher"] = text
        elif title == "周次(节次)":
            ensure_block()["weeksRaw"] = text
        elif title == "教室":
            ensure_block()["room"] = text
        elif title == "教学楼":
            ensure_block()["building"] = text
        elif title == "备注":
            note = re.sub(r"^备注\s*[:：]\s*", "", text).strip()
            if note:
                block = ensure_block()
                block["note"] = (block["note"] + " " + note).strip()
        elif title is not None:
            # 通知单编号 / 班级 等隐藏字段
            continue
        elif name_attr is not None:
            if name_attr == "wkxx" and text:
                block = ensure_block()
                block["note"] = (block["note"] + " " + text).strip()
            continue
        else:
            if not text:
                continue
            current = {"name": text, "teacher": "", "room": "", "building": "", "weeksRaw": "", "note": ""}
            blocks.append(current)

    return [b for b in blocks if b["name"]]


def _courses_in_cell(cell, day: int, big: int, periods_by_index: dict) -> list[dict]:
    divs = [d for d in cell.find_all("div") if "kbcontent" in (d.get("class") or [])]
    if not divs:
        return []
    # 同一格里 -2 是详版（含教师与具体节次），-1 是简版，取 font 最多的那个。
    detail = max(divs, key=lambda d: len(d.find_all("font")))
    fallback_sections = periods_by_index.get(big, {}).get("sections", [])
    courses = []
    for block in _parse_font_blocks(detail):
        weeks, parity = parse_weeks(block["weeksRaw"])
        sections = parse_sections(block["weeksRaw"]) or list(fallback_sections)
        courses.append(
            {
                "name": block["name"],
                "teacher": block["teacher"],
                "room": _clean_room(block["room"], block["building"]),
                "note": block["note"],
                "day": day,
                "bigPeriod": big,
                "sections": sections,
                "weeks": weeks,
                "parity": parity,
                "weeksRaw": block["weeksRaw"],
            }
        )
    return courses


def _course_id(course: dict) -> str:
    key = "|".join(
        [
            course["name"],
            str(course["day"]),
            str(course["bigPeriod"]),
            ",".join(str(s) for s in course["sections"]),
            course["weeksRaw"],
            course["room"],
        ]
    )
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


# --------------------------------------------------------------------------- 课表页


def _parse_term(soup: BeautifulSoup) -> tuple[str, str]:
    select = soup.find("select", id="xnxq01id")
    if not select:
        return "", ""
    selected = None
    for option in select.find_all("option"):
        if option.get("selected") is not None:
            selected = option.get("value")
            break
    if selected is None:
        options = select.find_all("option")
        selected = options[0].get("value") if options else ""
    term = (selected or "").strip()
    return term, term


def _parse_other_courses(soup: BeautifulSoup) -> list[dict]:
    """解析“无课表课程”表格（例如认识实习这类没有排课时间的课程）。"""
    table = soup.find("table", id="dataTables")
    if not table:
        return []
    rows = table.find_all("tr")

    header: list[str] = []
    body_rows: list = []
    for row in rows:
        cells = [_text(c) for c in row.find_all(["td", "th"])]
        if not header and "课程名称" in cells:
            header = cells
            continue
        if header:
            body_rows.append(cells)
    if not header:
        return []

    def index_of(*names: str) -> int | None:
        for i, cell in enumerate(header):
            if cell in names:
                return i
        return None

    idx_name = index_of("课程名称")
    idx_teacher = index_of("授课教师")
    idx_class = index_of("上课班级")
    idx_code = index_of("课程编号")
    idx_kind = index_of("课程性质")
    idx_attr = index_of("课程属性")
    if idx_name is None:
        return []

    result = []
    for cells in body_rows:
        if len(cells) <= idx_name or not cells[idx_name]:
            continue

        def pick(idx: int | None) -> str:
            return cells[idx] if idx is not None and idx < len(cells) else ""

        result.append(
            {
                "name": cells[idx_name],
                "teacher": pick(idx_teacher),
                "className": pick(idx_class),
                "courseCode": pick(idx_code),
                "kind": pick(idx_kind),
                "attribute": pick(idx_attr),
            }
        )
    return result


def parse_schedule_page(html: str) -> dict:
    """解析学期理论课表页，返回 {term, periods, courses, otherCourses}。"""
    soup = BeautifulSoup(html, "lxml")
    periods = parse_periods(soup) or [dict(p) for p in DEFAULT_PERIODS]
    periods_by_index = {p["index"]: p for p in periods}
    term, term_name = _parse_term(soup)

    table = soup.find("table", id="timetable")
    if not table:
        raise ParseError("课表页缺少 table#timetable，页面结构可能已改版")
    rows = table.find_all("tr")

    header_index = None
    for i, row in enumerate(rows):
        labels = [_text(c) for c in row.find_all(["td", "th"])]
        if any(label.startswith("星期一") for label in labels):
            header_index = i
            break
    if header_index is None:
        raise ParseError("课表页找不到星期一表头，页面结构可能已改版")

    courses: list[dict] = []
    for offset in range(1, 6):
        if header_index + offset >= len(rows):
            break
        row = rows[header_index + offset]
        cells = row.find_all(["th", "td"], recursive=False) or row.find_all(["th", "td"])
        if len(cells) < 8:
            continue
        for day in range(1, 8):
            courses.extend(_courses_in_cell(cells[day], day, offset, periods_by_index))

    for course in courses:
        course["id"] = _course_id(course)
    courses.sort(key=lambda c: (c["day"], c["bigPeriod"], c["name"]))

    return {
        "term": term,
        "termName": term_name,
        "periods": periods,
        "courses": courses,
        "otherCourses": _parse_other_courses(soup),
    }


# --------------------------------------------------------------------------- 教学周历页


def parse_calendar_page(html: str) -> dict:
    """解析教学周历页，返回 {termName, startDate, totalWeeks, weeks}。"""
    soup = BeautifulSoup(html, "lxml")
    page_text = _text(soup)
    term_name = ""
    term = ""
    m = _TERM_RE.search(page_text)
    year = None
    semester = 1
    if m:
        first_year, second_year, semester = int(m.group(1)), int(m.group(2)), int(m.group(3))
        year = first_year if semester == 1 else second_year
        term_name = f"{first_year}-{second_year} 学年 第 {semester} 学期"
        term = f"{first_year}-{second_year}-{semester}"

    weekly: list[tuple[int, date]] = []
    for row in soup.find_all("tr"):
        cells = [_text(c) for c in row.find_all(["td", "th"])]
        if len(cells) < 8 or not re.fullmatch(r"\d{1,2}", cells[0] or ""):
            continue
        week = int(cells[0])
        saturday = None
        for cell in cells[6:8]:
            dm = _DATE_RE.search(cell)
            if dm:
                saturday = (int(dm.group(1)), int(dm.group(2)))
                break
        if not saturday or year is None:
            continue
        month, day = saturday
        sat_year = year
        if semester == 1 and month <= 6:
            sat_year = year + 1
        monday = date(sat_year, month, day) - timedelta(days=5)
        weekly.append((week, monday))

    if not weekly:
        return {"term": term, "termName": term_name, "startDate": "", "totalWeeks": 0, "weeks": []}

    weekly.sort()
    base_week, base_monday = weekly[0]
    weeks = []
    for week, monday in weekly:
        monday = base_monday + timedelta(days=7 * (week - base_week))
        weeks.append(
            {
                "week": week,
                "start": monday.isoformat(),
                "end": (monday + timedelta(days=6)).isoformat(),
            }
        )
    return {
        "term": term,
        "termName": term_name,
        "startDate": base_monday.isoformat(),
        "totalWeeks": max(w["week"] for w in weeks),
        "weeks": weeks,
    }
