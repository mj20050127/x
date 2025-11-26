"""
knowledge.py (V4 - 适配考勤与学生画像的 RAG 语料构建)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from data_models import Course, Student, AttendStatus
import analytics

logger = logging.getLogger(__name__)


# ================== 数据结构定义 ================== #


@dataclass(frozen=True)
class CorpusItem:
    text: str
    meta: Dict[str, Any]


# 语料类型常量
CHUNK_TYPE_OVERVIEW = "overview"
CHUNK_TYPE_WEEKLY_OVERVIEW = "weekly_overview"
CHUNK_TYPE_LEARNING_PATH_SUMMARY = "learning_path_summary"
CHUNK_TYPE_STUDENT_PERFORMANCE_SUMMARY = "student_performance_summary"
CHUNK_TYPE_RESOURCE_USAGE = "resource_usage"
CHUNK_TYPE_STUDENT_PROFILE = "student_profile"
CHUNK_TYPE_ATTENDANCE_SUMMARY = "attendance_summary"
CHUNK_TYPE_ATTENDANCE_EVENT = "attendance_event"


# ================== 对外主入口 ================== #


def build_course_corpus(
    course: Course,
    *,
    stats: Optional[Dict[str, Any]] = None,
    learning_path: Optional[Dict[str, Any]] = None,
    student_performance: Optional[Dict[str, Any]] = None,
    resource_usage: Optional[Dict[str, Any]] = None,
    max_resource_chunks: int = 10,
) -> List[CorpusItem]:
    """
    构建某门课程的知识语料库，用于向量化检索。

    注意：
    - DataProcessor 会优先把已经算好的 stats / learning_path 等传进来；
      如果为 None，则在这里兜底计算一次。
    - 任何一步报错都不会中断整体构建，而是写日志并跳过对应部分。
    """
    corpus: List[CorpusItem] = []

    course_id = (course.course_id or "").strip()
    if not course_id:
        return corpus

    # 1. 宏观统计（概览 + 按周统计）
    if stats is None:
        try:
            stats = analytics.compute_statistics(course)
        except Exception as e:  # noqa: BLE001
            logger.warning("统计计算失败: %s", e)
            stats = None

    if stats:
        corpus.extend(_build_overview_chunks(course_id, course, stats))
        corpus.extend(_build_weekly_chunks(course_id, stats))

    # 2. 学习路径
    if learning_path is None:
        try:
            learning_path = analytics.analyze_learning_path(course)
        except Exception as e:  # noqa: BLE001
            logger.warning("学习路径分析失败: %s", e)
            learning_path = None

    if learning_path:
        corpus.extend(_build_learning_path_chunks(course_id, learning_path))

    # 3. 学生整体表现
    if student_performance is None:
        try:
            student_performance = analytics.analyze_student_performance(course)
        except Exception as e:  # noqa: BLE001
            logger.warning("学生表现分析失败: %s", e)
            student_performance = None

    if student_performance:
        corpus.extend(
            _build_student_performance_chunks(course_id, student_performance)
        )

    # 4. 资源使用情况
    if resource_usage is None:
        try:
            resource_usage = analytics.analyze_resource_usage(course)
        except Exception as e:  # noqa: BLE001
            logger.warning("资源使用分析失败: %s", e)
            resource_usage = None

    if resource_usage:
        corpus.extend(
            _build_resource_usage_chunks(
                course_id, resource_usage, max_chunks=max_resource_chunks
            )
        )

    # 5. 学生个体画像（核心：支持按学号 / 姓名查成绩、出勤等）
    try:
        corpus.extend(_build_student_profile_chunks(course_id, course))
    except Exception as e:  # noqa: BLE001
        logger.warning("学生画像构建失败: %s", e)

    # 6. 考勤事件（整体概览 + 每次考勤）
    try:
        att_data = analytics.analyze_attendance_events(course)
    except Exception as e:  # noqa: BLE001
        logger.warning("考勤事件分析失败: %s", e)
        att_data = None

    if att_data:
        corpus.extend(_build_attendance_event_chunks(course_id, att_data))

    return corpus


# ================== 各类语料构建子函数 ================== #


def _build_overview_chunks(
    course_id: str, course: Course, stats: Dict[str, Any]
) -> List[CorpusItem]:
    overview = stats.get("overview") or {}

    text_lines = [
        f"课程《{course.course_name}》(ID: {course_id})整体情况：",
        f"- 学生人数：{overview.get('total_students', 0)} 人",
        f"- 学习资源总数：{overview.get('resource_count', 0)} 个",
        f"- 视频学习记录：{overview.get('video_count', 0)} 条",
        f"- 作业记录：{overview.get('homework_count', 0)} 条",
        f"- 考试记录：{overview.get('exam_count', 0)} 条",
        f"- 考勤记录：{overview.get('attendance_count', 0)} 条",
    ]
    text = "\n".join(text_lines)

    return [
        CorpusItem(
            text=text,
            meta={
                "course_id": course_id,
                "type": CHUNK_TYPE_OVERVIEW,
            },
        )
    ]


def _build_weekly_chunks(course_id: str, stats: Dict[str, Any]) -> List[CorpusItem]:
    week_stats = stats.get("week_stats") or {}
    corpus: List[CorpusItem] = []

    for week, values in week_stats.items():
        text = (
            f"第 {week} 周教学概况：共有资源 {values.get('resources', 0)} 个，"
            f"其中视频 {values.get('videos', 0)} 个，作业 {values.get('homeworks', 0)} 个。"
        )
        corpus.append(
            CorpusItem(
                text=text,
                meta={
                    "course_id": course_id,
                    "type": CHUNK_TYPE_WEEKLY_OVERVIEW,
                    "week": int(week),
                },
            )
        )
    return corpus


def _build_learning_path_chunks(
    course_id: str, learning_path: Dict[str, Any]
) -> List[CorpusItem]:
    text = str(learning_path.get("analysis_text") or "").strip()
    if not text:
        return []
    return [
        CorpusItem(
            text=text,
            meta={
                "course_id": course_id,
                "type": CHUNK_TYPE_LEARNING_PATH_SUMMARY,
            },
        )
    ]


def _build_student_performance_chunks(
    course_id: str, student_performance: Dict[str, Any]
) -> List[CorpusItem]:
    text = str(student_performance.get("analysis_text") or "").strip()
    if not text:
        return []
    return [
        CorpusItem(
            text=text,
            meta={
                "course_id": course_id,
                "type": CHUNK_TYPE_STUDENT_PERFORMANCE_SUMMARY,
            },
        )
    ]


def _build_resource_usage_chunks(
    course_id: str, resource_usage: Dict[str, Any], max_chunks: int = 10
) -> List[CorpusItem]:
    usage_list = resource_usage.get("resource_usage") or []
    corpus: List[CorpusItem] = []

    for item in usage_list[:max_chunks]:
        title = str(item.get("title") or "")
        if not title:
            continue
        text = (
            f"资源《{title}》({item.get('type')}) 的使用情况："
            f"被 {item.get('students_count', 0)} 名学生使用，"
            f"浏览 {item.get('views', 0)} 次，下载 {item.get('downloads', 0)} 次。"
        )
        corpus.append(
            CorpusItem(
                text=text,
                meta={
                    "course_id": course_id,
                    "type": CHUNK_TYPE_RESOURCE_USAGE,
                    "resource_id": item.get("resource_id"),
                },
            )
        )
    return corpus


def _build_student_profile_chunks(
    course_id: str, course: Course
) -> List[CorpusItem]:
    """
    为每个学生生成一段“成绩 + 作业 + 视频”的画像文本，
    重点：在文本和 meta 里都写清 student_id / 学号，方便按 ID 检索。
    """
    corpus: List[CorpusItem] = []
    all_students: List[Student] = []

    if course.teachclasses:
        for tc in course.teachclasses:
            all_students.extend(tc.students)

    for stu in all_students:
        # 没任何记录的学生就不入库了
        if not (stu.homework_records or stu.exam_records or stu.video_records):
            continue

        # ---------- 考试详情 ----------
        exam_details = []
        for ex in stu.exam_records:
            exam_details.append(f"{ex.score}/{ex.total_score}")
        exam_str = "；".join(exam_details) if exam_details else "无考试记录"

        # ---------- 作业详情 ----------
        hw_scores = [h.score for h in stu.homework_records]
        if hw_scores:
            avg_hw = sum(hw_scores) / len(hw_scores)
            hw_str = f"提交 {len(hw_scores)} 次，平均 {avg_hw:.1f} 分"
        else:
            hw_str = "无作业记录"

        # ---------- 视频学习 ----------
        total_video_time = sum(v.view_time for v in stu.video_records)
        video_count = len(stu.video_records)

        # ---------- 拼接身份证明信息 ----------
        name = getattr(stu, "name", "") or ""
        username = getattr(stu, "username", "") or ""

        head_line = f"学生档案 - student_id={stu.student_id}"
        extra_info = []
        if username:
            extra_info.append(f"学号: {username}")
        if name:
            extra_info.append(f"姓名: {name}")
        if extra_info:
            head_line += "（" + "，".join(extra_info) + "）"

        # ---------- 最终文本 ----------
        text = (
            f"{head_line}\n"
            f"【成绩情况】\n"
            f"- 考试成绩：{exam_str}\n"
            f"- 作业情况：{hw_str}\n"
            f"【视频学习】\n"
            f"- 共 {video_count} 条观看记录，总时长约 {int(total_video_time)} 秒\n"
        )

        corpus.append(
            CorpusItem(
                text=text,
                meta={
                    "course_id": course_id,
                    "type": CHUNK_TYPE_STUDENT_PROFILE,
                    "student_id": stu.student_id,
                    "student_username": username,
                    "student_name": name,
                },
            )
        )

    return corpus



def _build_attendance_event_chunks(course_id: str, att_data: Dict[str, Any]) -> List[CorpusItem]:
    """
    生成考勤事件的自然语言描述，适配 analytics.analyze_attendance_events 的返回结构。
    """
    corpus: List[CorpusItem] = []

    # 1. 整体概览 / 总结
    analysis_text = str(att_data.get("analysis_text") or "").strip()
    if analysis_text:
        corpus.append(
            CorpusItem(
                text=analysis_text,
                meta={
                    "course_id": course_id,
                    "type": CHUNK_TYPE_ATTENDANCE_SUMMARY,
                },
            )
        )

    # 2. 每一次考勤事件的详细统计
    for ev in att_data.get("events", []):
        name = ev.get("name") or ""
        date_cn = ev.get("date_cn") or ev.get("date") or ""
        present = int(ev.get("present", 0))
        absent = int(ev.get("absent", 0))
        leave = int(ev.get("leave", 0))
        late = int(ev.get("late", 0))
        early_leave = int(ev.get("early_leave", 0))
        total = int(ev.get("total", 0)) or 1
        rate = float(ev.get("attendance_rate", 0.0))

        text_lines = [
            f"【考勤详情】{name}（{date_cn}）",
            f"- 应到 {total} 人，实到 {present} 人，缺勤 {absent} 人，请假 {leave} 人，迟到 {late} 人，早退 {early_leave} 人",
            f"- 出勤率：{rate:.1f}%",
        ]
        text = "\n".join(text_lines)

        corpus.append(
            CorpusItem(
                text=text,
                meta={
                    "course_id": course_id,
                    "type": CHUNK_TYPE_ATTENDANCE_EVENT,
                    "event_name": name,
                    "date": ev.get("date"),
                    "check_item_id": ev.get("check_item_id"),
                },
            )
        )

    return corpus
