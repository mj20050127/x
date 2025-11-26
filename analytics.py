"""
analytics.py (V3 深度分析版)
功能：提供深度教学分析，包含学业预警、相关性分析、资源利用率等综合评估。
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from datetime import datetime

from data_models import (
    Course,
    ResourceType,
    AttendStatus,
    Student,
    Resource,
    TeachClass,
)


# ================== 公共上下文 ================== #


@dataclass(frozen=True)
class CourseContext:
    course: Course
    resources: List[Resource]
    teachclasses: List[TeachClass]
    students: List[Student]
    total_students: int


def _build_context(course: Course) -> CourseContext:
    teachclasses: List[TeachClass] = list(course.teachclasses or [])
    students: List[Student] = [
        stu for tc in teachclasses for stu in (tc.students or [])
    ]
    resources: List[Resource] = list(course.resources.values())
    total_students = len(students)
    return CourseContext(
        course=course,
        resources=resources,
        teachclasses=teachclasses,
        students=students,
        total_students=total_students,
    )


def _format_time(seconds: float) -> str:
    """辅助函数：格式化时间"""
    seconds = float(seconds)
    if seconds <= 0:
        return "0分钟"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}小时{minutes}分钟"
    return f"{minutes}分钟"


# ================== 课程概览 & 统计 ================== #


def compute_overview(course: Course) -> Dict:
    ctx = _build_context(course)
    video_count = 0
    homework_count = 0
    exam_count = 0
    attendance_count = 0
    for stu in ctx.students:
        video_count += len(stu.video_records)
        homework_count += len(stu.homework_records)
        exam_count += len(stu.exam_records)
        attendance_count += len(stu.attendance_records)

    resource_stats: Dict[str, int] = defaultdict(int)
    resource_types: Dict[str, List[Dict]] = defaultdict(list)

    for res in ctx.resources:
        type_str = res.resource_type.value
        resource_stats[type_str] += 1
        resource_types[type_str].append(
            {
                "title": res.title,
                "resource_id": res.resource_id,
                "resource_type": type_str,
                "view_times": res.view_times,
                "download_times": res.download_times,
                "teaching_week": res.teaching_week,
            }
        )

    return {
        "course_name": course.course_name,
        "resource_count": len(ctx.resources),
        "resource_stats": dict(resource_stats),
        "resource_types": dict(resource_types),
        "total_students": ctx.total_students,
        "video_count": video_count,
        "homework_count": homework_count,
        "exam_count": exam_count,
        "attendance_count": attendance_count,
    }


def compute_statistics(course: Course) -> Dict:
    overview = compute_overview(course)
    resource_types: Dict[str, List[Dict]] = overview["resource_types"]
    total_students: int = overview["total_students"]

    resource_usage: List[Dict] = []
    for type_str, resources in resource_types.items():
        total_views = sum(r.get("view_times", 0) for r in resources)
        total_downloads = sum(r.get("download_times", 0) for r in resources)
        resource_usage.append(
            {
                "type": type_str,
                "count": len(resources),
                "total_views": int(total_views),
                "total_downloads": int(total_downloads),
            }
        )

    week_stats: Dict[int, Dict[str, int]] = defaultdict(
        lambda: {"resources": 0, "videos": 0, "homeworks": 0}
    )
    for type_str, resources in resource_types.items():
        for res in resources:
            week = res.get("teaching_week")
            if week is None:
                continue
            week_stats[week]["resources"] += 1
            if type_str == ResourceType.VIDEO.value:
                week_stats[week]["videos"] += 1
            elif type_str == ResourceType.HOMEWORK.value:
                week_stats[week]["homeworks"] += 1

    ctx = _build_context(course)
    homework_submissions: Dict[str, set] = defaultdict(set)
    for stu in ctx.students:
        sid = stu.student_id
        for hw in stu.homework_records:
            if hw.resource_id:
                homework_submissions[hw.resource_id].add(sid)

    homework_details: List[Dict] = []
    homework_resources = resource_types.get(ResourceType.HOMEWORK.value, [])

    for hw_res in homework_resources:
        rid = hw_res.get("resource_id")
        if not rid:
            continue
        submitted = homework_submissions.get(rid, set())
        submitted_count = len(submitted)
        completion_rate = (
            round(submitted_count / total_students * 100, 1)
            if total_students > 0
            else 0.0
        )

        homework_details.append(
            {
                "resource_id": rid,
                "title": hw_res.get("title", ""),
                "submitted_count": submitted_count,
                "total_students": total_students,
                "completion_rate": completion_rate,
                "teaching_week": hw_res.get("teaching_week", ""),
            }
        )

    homework_details.sort(
        key=lambda x: (
            x.get("teaching_week") or 0,
            x.get("title") or "",
        )
    )

    return {
        "overview": overview,
        "resource_usage": resource_usage,
        "week_stats": {int(k): v for k, v in week_stats.items()},
        "homework_details": homework_details,
    }


# ================== 学习路径分析 (增强版) ================== #


def analyze_learning_path(course: Course) -> Dict:
    """
    学习路径分析
    """
    ctx = _build_context(course)
    # 确保资源字典的键为字符串，避免 int/str 混用导致匹配失败
    resources_map = {str(k): v for k, v in course.resources.items()}
    learning_paths: List[Dict] = []
    
    # 路径多样性统计
    unique_patterns = set()

    for stu in ctx.students:
        if not stu.video_records:
            continue
        
        # 排序
        sorted_videos = sorted(
            stu.video_records,
            key=lambda v: (v.start_time is None, v.start_time or ""),
        )

        path = []
        path_ids = []
        for v in sorted_videos[:10]:
            res = resources_map.get(str(v.resource_id))
            title = res.title if res else "未知资源"
            path.append({
                "resource_id": str(v.resource_id),
                "title": title,
                "view_time": v.view_time,
                "start_time": v.start_time,
            })
            path_ids.append(str(v.resource_id))
        
        if path:
            learning_paths.append({"student_id": stu.student_id, "path": path})
            # 记录前3步作为模式指纹
            if len(path_ids) >= 3:
                unique_patterns.add(tuple(path_ids[:3]))

    # 统计最常见路径
    path_frequency: Dict[Tuple[str, ...], int] = defaultdict(int)
    path_examples: Dict[Tuple[str, ...], List[Dict]] = defaultdict(list)

    for lp in learning_paths:
        seq = tuple(v["resource_id"] for v in lp["path"][:5])
        if not seq:
            continue
        path_frequency[seq] += 1
        examples = path_examples[seq]
        if len(examples) < 3:
            examples.append({
                "student_id": lp["student_id"],
                "path_titles": [v["title"] for v in lp["path"][:5]],
            })

    sorted_paths = sorted(
        path_frequency.items(), key=lambda x: x[1], reverse=True
    )[:5]

    analyzed_students = len(learning_paths)
    common_paths_list = []
    
    # 生成报告文本
    lines: List[str] = [
        "【学习路径深度分析报告】",
        "",
        f"1. 概况：\n   分析了 {analyzed_students}/{ctx.total_students} 名学生的学习轨迹。",
    ]

    # 多样性评估
    diversity_ratio = len(unique_patterns) / analyzed_students if analyzed_students > 0 else 0
    diversity_desc = "高度一致" if diversity_ratio < 0.2 else "较为发散" if diversity_ratio < 0.6 else "非常个性化"
    lines.append(f"   学习模式多样性：{diversity_desc} (发现了 {len(unique_patterns)} 种不同的起始学习顺序)。")
    lines.append("")
    lines.append("2. 典型路径模式：")

    if sorted_paths:
        for idx, (seq, freq) in enumerate(sorted_paths, start=1):
            titles = []
            for rid in seq:
                res = resources_map.get(str(rid))
                titles.append(res.title if res else "未知资源")
            
            path_str = " → ".join(titles[:3])
            if len(titles) > 3:
                path_str += " → ..."
            
            percentage = round((freq / analyzed_students * 100), 1)
            description = f"{freq}名学生 ({percentage}%) 选择了此路径。"
            
            # 简单的路径逻辑判断 (Heuristic)
            path_insight = ""
            if "作业" in "".join(titles):
                path_insight = " [以作业为导向]"
            elif len(set(titles)) < len(titles):
                path_insight = " [存在重复学习]"
            
            description += path_insight
            
            lines.append(f"   模式 {idx}: {path_str}")
            lines.append(f"   - {description}")

            common_paths_list.append({
                "resource_ids": list(seq),
                "frequency": freq,
                "percentage": percentage,
                "examples": path_examples[seq],
                "path_titles": titles,
                "description": description 
            })
    else:
        lines.append("   暂未发现明显的聚集性学习路径，说明学生的学习顺序差异极大。")

    # 3. 综合评估
    lines.append("")
    lines.append("3. 综合评估：")
    if analyzed_students < ctx.total_students * 0.3:
        lines.append("   ⚠️ 大部分学生尚未开始产生连续的学习行为，建议提醒学生登录平台学习。")
    elif diversity_ratio > 0.8:
        lines.append("   💡 学生的学习路径非常分散，这可能意味着课程缺乏明确的引导，或者是开放式探索课程。")
    else:
        lines.append("   ✅ 大部分学生遵循了相对固定的学习节奏。")

    return {
        "total_students": ctx.total_students,
        "analyzed_students": analyzed_students,
        "learning_paths": learning_paths[:50],
        "common_paths": common_paths_list,
        "analysis_text": "\n".join(lines),
    }


# ================== 学生表现分析 (增强版) ================== #


def analyze_student_performance(course: Course) -> Dict:
    """
    学生表现分析:
    {
      "total_students": int,
      "performance_stats": {...},
      "average_stats": {...},
      "student_details": [...],
      "top_students": [...],
      "analysis_text": str
    }
    """
    ctx = _build_context(course)

    student_details: List[Dict] = []
    performance_stats = {
        "video_watch_time": [],
        "homework_scores": [],
        "exam_scores": [],
        "attendance_rate": [],
    }

    for stu in ctx.students:
        # 1) 视频总时长（按学生汇总）
        total_video_time = sum(v.view_time for v in stu.video_records)
        video_count = len(stu.video_records)
        if total_video_time > 0:
            performance_stats["video_watch_time"].append(total_video_time)

        # 2) 作业成绩（按每次作业记录）
        hw_scores: List[float] = []
        for hw in stu.homework_records:
            if hw.score > 0:
                hw_scores.append(hw.score)
                performance_stats["homework_scores"].append(hw.score)
        avg_homework_score = (
            sum(hw_scores) / len(hw_scores) if hw_scores else 0.0
        )

        # 3) 考试成绩（按每次考试记录，换算为百分制）
        exam_scores: List[float] = []
        for ex in stu.exam_records:
            if ex.score > 0 and ex.total_score > 0:
                percentage = ex.score / ex.total_score * 100
                exam_scores.append(percentage)
                performance_stats["exam_scores"].append(percentage)
        avg_exam_score = (
            sum(exam_scores) / len(exam_scores) if exam_scores else 0.0
        )

        # 4) 出勤率（按学生汇总）
        attendance_rate = 0.0
        if stu.attendance_records:
            present_count = sum(
                1
                for a in stu.attendance_records
                if a.attend_status == AttendStatus.PRESENT
            )
            attendance_rate = present_count / len(stu.attendance_records) * 100
            performance_stats["attendance_rate"].append(attendance_rate)

        # 5) 记录学生明细
        student_details.append(
            {
                "student_id": stu.student_id,
                "video_watch_time": total_video_time,
                "video_count": video_count,
                "homework_count": len(stu.homework_records),
                "avg_homework_score": avg_homework_score,
                "exam_count": len(stu.exam_records),
                "avg_exam_score": avg_exam_score,
                "attendance_rate": attendance_rate,
            }
        )

    # ===== 统计总体分布 (平均/最小/最大/数量) =====
    avg_stats: Dict[str, Dict[str, float]] = {}
    for key, values in performance_stats.items():
        if not values:
            continue
        avg_stats[key] = {
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "count": len(values),
        }

    def _format_time(seconds: float) -> str:
        seconds = float(seconds)
        if seconds <= 0:
            return "0分钟"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        if hours > 0:
            return f"{hours}小时{minutes}分钟"
        return f"{minutes}分钟"

    # 小工具函数，避免重复写 get(...)...
    def _s(metric: str, field: str, default: float = 0.0) -> float:
        return float(avg_stats.get(metric, {}).get(field, default) or 0.0)

    # ===== 生成文本报告（扩展为截图里的所有指标） =====
    lines: List[str] = [
        "学生表现分析报告",
        "",
        "总体概况:",
        f"- 课程共有 {ctx.total_students} 名学生",
        f"- 有学习行为记录的学生: {int(_s('video_watch_time', 'count'))} 名",
        f"- 有作业记录的学生: {int(_s('homework_scores', 'count'))} 名",
        f"- 有考试记录的学生: {int(_s('exam_scores', 'count'))} 名",
        f"- 有出勤记录的学生: {int(_s('attendance_rate', 'count'))} 名",
        "",
        "视频学习情况:",
        f"- 平均观看时长: {_format_time(_s('video_watch_time', 'avg'))}",
        f"- 最长观看时长: {_format_time(_s('video_watch_time', 'max'))}",
        f"- 最短观看时长: {_format_time(_s('video_watch_time', 'min'))}",
        "",
        "作业完成情况:",
        f"- 平均作业得分: {_s('homework_scores', 'avg'):.1f} 分",
        f"- 最高作业得分: {_s('homework_scores', 'max'):.1f} 分",
        f"- 最低作业得分: {_s('homework_scores', 'min'):.1f} 分",
        f"- 提交作业总数: {int(_s('homework_scores', 'count'))} 次",
        "",
        "考试表现情况:",
        f"- 平均考试成绩: {_s('exam_scores', 'avg'):.1f} 分",
        f"- 最高考试成绩: {_s('exam_scores', 'max'):.1f} 分",
        f"- 最低考试成绩: {_s('exam_scores', 'min'):.1f} 分",
        f"- 参加考试总数: {int(_s('exam_scores', 'count'))} 次",
        "",
        "出勤情况:",
        f"- 平均出勤率: {_s('attendance_rate', 'avg'):.1f}%",
        f"- 最高出勤率: {_s('attendance_rate', 'max'):.1f}%",
        f"- 最低出勤率: {_s('attendance_rate', 'min'):.1f}%",
        "",
        "表现较好的学生示例(最多5名):",
    ]

    # ===== 选出表现较好的学生（原逻辑保留） =====
    sorted_students = sorted(
        student_details,
        key=lambda s: (
            -s["avg_exam_score"],
            -s["avg_homework_score"],
            -s["video_watch_time"],
        ),
    )
    top_students = sorted_students[:5]
    for stu in top_students:
        parts: List[str] = [f"- 学生 {stu['student_id']}: "]
        if stu["avg_homework_score"] > 0:
            parts.append(f"作业均分 {stu['avg_homework_score']:.1f} 分")
        if stu["avg_exam_score"] > 0:
            parts.append(f"考试均分 {stu['avg_exam_score']:.1f} 分")
        if stu["video_watch_time"] > 0:
            parts.append(f"观看时长 {_format_time(stu['video_watch_time'])}")
        lines.append("，".join(parts))

    return {
        "total_students": ctx.total_students,
        "performance_stats": performance_stats,
        "average_stats": avg_stats,
        "student_details": student_details[:20],
        "top_students": top_students,
        "analysis_text": "\n".join(lines),
    }



# ================== 资源使用分析 (增强版) ================== #


def analyze_resource_usage(course: Course) -> Dict:
    """
    资源使用分析 (包含僵尸资源检测、二八定律分析)
    """
    ctx = _build_context(course)
    usage_map: Dict[str, Dict] = defaultdict(
        lambda: {"views": 0, "students_used": set()}
    )

    # 统计逻辑保持不变
    for stu in ctx.students:
        sid = stu.student_id
        for v in stu.video_records:
            if v.resource_id:
                usage_map[v.resource_id]["views"] += 1
                usage_map[v.resource_id]["students_used"].add(sid)
        for hw in stu.homework_records:
            if hw.resource_id:
                usage_map[hw.resource_id]["students_used"].add(sid)
        for ex in stu.exam_records:
            if ex.resource_id:
                usage_map[ex.resource_id]["students_used"].add(sid)

    usage_list: List[Dict] = []
    total_views_sum = 0
    
    for rid, usage in usage_map.items():
        res = course.resources.get(rid)
        if not res: continue
        popularity = usage["views"] + res.download_times
        total_views_sum += popularity
        usage_list.append({
            "resource_id": rid,
            "title": res.title,
            "type": res.resource_type.value,
            "views": usage["views"],
            "downloads": res.download_times,
            "students_count": len(usage["students_used"]),
            "popularity": popularity
        })

    # 补充未使用的资源（僵尸资源）
    all_resource_ids = set(course.resources.keys())
    used_resource_ids = set(usage_map.keys())
    unused_ids = all_resource_ids - used_resource_ids
    
    for rid in unused_ids:
        res = course.resources.get(rid)
        usage_list.append({
            "resource_id": rid,
            "title": res.title,
            "type": res.resource_type.value,
            "views": 0,
            "downloads": 0,
            "students_count": 0,
            "popularity": 0
        })

    usage_list.sort(key=lambda x: x["popularity"], reverse=True)
    
    # === 深度分析指标 ===
    total_resources = len(course.resources)
    zero_view_count = len(unused_ids)
    utilization_rate = (total_resources - zero_view_count) / total_resources * 100 if total_resources > 0 else 0
    
    # 帕累托分析 (二八定律): 前20%的资源占据了多少流量
    top_20_percent_count = max(1, int(total_resources * 0.2))
    top_traffic = sum(item["popularity"] for item in usage_list[:top_20_percent_count])
    traffic_concentration = (top_traffic / total_views_sum * 100) if total_views_sum > 0 else 0

    lines = [
        "【资源利用深度分析报告】",
        "",
        "1. 资源覆盖概况：",
        f"   - 课程共发布资源 {total_resources} 个。",
        f"   - 资源整体利用率: {utilization_rate:.1f}% ({total_resources - zero_view_count} 个资源被访问过)。",
    ]

    if zero_view_count > 0:
        lines.append(f"   ⚠️ 发现 {zero_view_count} 个“僵尸资源”（零访问），建议检查是否为非必须内容或发布位置不显眼。")
    
    lines.append("")
    lines.append("2. 流量集中度 (Pareto Analysis)：")
    lines.append(f"   - 头部 {top_20_percent_count} 个资源贡献了全课程 {traffic_concentration:.1f}% 的访问流量。")
    
    if traffic_concentration > 80:
        lines.append("   🔥 流量高度集中：说明学生极其依赖少数几个核心资源，其他辅助资源可能被忽视。")
    elif traffic_concentration < 40:
        lines.append("   ✨ 流量分布均匀：说明学生对各类资源的使用较为均衡。")

    lines.append("")
    lines.append("3. 热门 vs 冷门：")
    if usage_list:
        top = usage_list[0]
        lines.append(f"   🏆 最受欢迎: 《{top['title']}》 ({top['type']}) - {top['popularity']}热度")
        
        # 找一个有访问但很少的
        tail = next((x for x in reversed(usage_list) if x['popularity'] > 0), None)
        if tail:
            lines.append(f"   ❄️ 需关注冷门: 《{tail['title']}》 - 仅 {tail['popularity']}热度")

    return {
        "total_resources": total_resources,
        "used_resources": total_resources - zero_view_count,
        "utilization_rate": utilization_rate,
        "zero_view_count": zero_view_count,
        "resource_usage": usage_list[:50],
        "analysis_text": "\n".join(lines)
    }

def analyze_attendance(course: Course) -> Dict:
    """
    考勤分析（按考勤事件聚合 + 全局概览）

    返回结构示例:
    {
      "total_students": 280,
      "total_records": 3048,
      "event_count": 43,
      "summary": {
        "present": 2776,
        "absent": 235,
        "leave": 31,
        "late": 0,
        "early_leave": 0,
        "unknown": 6,
        "present_rate": 91.1,
        "absent_rate": 7.7,
      },
      "events": [
        {
          "check_item_id": "xxx",
          "name": "第1次考勤",
          "start_time": "2024-03-01T10:00:00",
          "due_time": "2024-03-01T10:15:00",
          "total": 71,
          "present": 6,
          "absent": 65,
          "leave": 0,
          "late": 0,
          "early_leave": 0,
          "unknown": 0,
          "present_rate": 8.5,
          "absent_rate": 91.5
        },
        ...
      ]
    }
    """
    ctx = _build_context(course)

    total_records = 0
    total_present = total_absent = total_leave = 0
    total_late = total_early = total_unknown = 0

    # key: check_item_id 优先；没有就用 name
    events: Dict[str, Dict[str, Any]] = {}

    for stu in ctx.students:
        for rec in stu.attendance_records:
            total_records += 1
            status = rec.attend_status

            if status == AttendStatus.PRESENT:
                total_present += 1
                status_key = "present"
            elif status == AttendStatus.ABSENT:
                total_absent += 1
                status_key = "absent"
            elif status == AttendStatus.LEAVE:
                total_leave += 1
                status_key = "leave"
            elif status == AttendStatus.LATE:
                total_late += 1
                status_key = "late"
            elif status == AttendStatus.EARLY_LEAVE:
                total_early += 1
                status_key = "early_leave"
            else:
                total_unknown += 1
                status_key = "unknown"

            key = rec.check_item_id or f"name:{rec.name or ''}"
            ev = events.get(key)
            if ev is None:
                ev = {
                    "check_item_id": rec.check_item_id,
                    "name": rec.name or "",
                    "start_time": rec.start_time,
                    "due_time": rec.due_time,
                    "total": 0,
                    "present": 0,
                    "absent": 0,
                    "leave": 0,
                    "late": 0,
                    "early_leave": 0,
                    "unknown": 0,
                }
                events[key] = ev

            ev["total"] += 1
            ev[status_key] += 1

    # 计算每个考勤事件的出勤率等
    event_list: List[Dict[str, Any]] = []
    for ev in events.values():
        total = ev["total"] or 1
        ev["present_rate"] = round(ev["present"] / total * 100, 1)
        ev["absent_rate"] = round(ev["absent"] / total * 100, 1)
        event_list.append(ev)

    # 排序：优先按 start_time，其次按 name
    event_list.sort(
        key=lambda e: (
            e.get("start_time") is None,
            e.get("start_time") or "",
            e.get("name") or "",
        )
    )

    global_total = total_records or 1
    summary = {
        "present": total_present,
        "absent": total_absent,
        "leave": total_leave,
        "late": total_late,
        "early_leave": total_early,
        "unknown": total_unknown,
        "present_rate": round(total_present / global_total * 100, 1),
        "absent_rate": round(total_absent / global_total * 100, 1),
    }

    return {
        "total_students": ctx.total_students,
        "total_records": total_records,
        "event_count": len(event_list),
        "summary": summary,
        "events": event_list,
    }


def _format_time_minutes(seconds: float) -> str:
    seconds = float(seconds or 0)
    if seconds <= 0:
        return "0分钟"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}小时{minutes}分钟"
    return f"{minutes}分钟"


def analyze_student_detail(
    course: Course,
    *,
    student_id: Optional[str] = None,
    username: Optional[str] = None,
    name: Optional[str] = None,
) -> Dict:
    """
    单个学生画像（出勤 + 作业 + 考试 + 视频）

    入口可以用 student_id / username / name 任选其一，优先级：
    student_id > username > name
    """
    ctx = _build_context(course)

    target: Optional[Student] = None

    for stu in ctx.students:
        if student_id and stu.student_id == student_id:
            target = stu
            break
    if target is None and username:
        for stu in ctx.students:
            if getattr(stu, "username", None) == username:
                target = stu
                break
    if target is None and name:
        for stu in ctx.students:
            if getattr(stu, "name", None) == name:
                target = stu
                break

    if target is None:
        raise ValueError("analyze_student_detail: 未找到指定学生")

    # ---------- 视频 ----------
    total_video_time = sum(v.view_time for v in target.video_records)
    video_count = len(target.video_records)

    # ---------- 作业 ----------
    homework_items: List[Dict[str, Any]] = []
    for hw in target.homework_records:
        res = course.resources.get(hw.resource_id)
        title = res.title if res else ""
        week = res.teaching_week if res else None
        percentage = (
            hw.score / hw.total_score * 100
            if hw.total_score > 0
            else None
        )
        homework_items.append(
            {
                "resource_id": hw.resource_id,
                "title": title,
                "score": hw.score,
                "total_score": hw.total_score,
                "percentage": percentage,
                "teaching_week": week,
            }
        )

    avg_hw = (
        sum(i["percentage"] for i in homework_items if i["percentage"] is not None)
        / len([i for i in homework_items if i["percentage"] is not None])
        if homework_items
        else 0.0
    )

    # ---------- 考试 ----------
    exam_items: List[Dict[str, Any]] = []
    for ex in target.exam_records:
        res = course.resources.get(ex.resource_id)
        title = res.title if res else ""
        week = res.teaching_week if res else None
        percentage = (
            ex.score / ex.total_score * 100
            if ex.total_score > 0
            else None
        )
        exam_items.append(
            {
                "resource_id": ex.resource_id,
                "title": title,
                "score": ex.score,
                "total_score": ex.total_score,
                "percentage": percentage,
                "teaching_week": week,
            }
        )

    avg_exam = (
        sum(i["percentage"] for i in exam_items if i["percentage"] is not None)
        / len([i for i in exam_items if i["percentage"] is not None])
        if exam_items
        else 0.0
    )

    # ---------- 出勤 ----------
    attend_total = len(target.attendance_records)
    present_cnt = absent_cnt = leave_cnt = late_cnt = early_cnt = unknown_cnt = 0

    event_details: List[Dict[str, Any]] = []

    for rec in target.attendance_records:
        status = rec.attend_status
        if status == AttendStatus.PRESENT:
            present_cnt += 1
        elif status == AttendStatus.ABSENT:
            absent_cnt += 1
        elif status == AttendStatus.LEAVE:
            leave_cnt += 1
        elif status == AttendStatus.LATE:
            late_cnt += 1
        elif status == AttendStatus.EARLY_LEAVE:
            early_cnt += 1
        else:
            unknown_cnt += 1

        event_details.append(
            {
                "check_item_id": rec.check_item_id,
                "name": rec.name,
                "start_time": rec.start_time,
                "due_time": rec.due_time,
                "attend_time": rec.attend_time,
                "status": status.value,
                "score": rec.score,
            }
        )

    attendance_rate = (
        present_cnt / attend_total * 100 if attend_total > 0 else 0.0
    )

    # 排序一下考勤记录，方便前端展示
    event_details.sort(
        key=lambda e: (
            e.get("start_time") is None,
            e.get("start_time") or "",
            e.get("name") or "",
        )
    )

    basic_info = {
        "student_id": target.student_id,
        "username": getattr(target, "username", None),
        "name": getattr(target, "name", None),
        "clazz": getattr(target, "clazz", None),
        "major": getattr(target, "major", None),
        "login_times": getattr(target, "login_times", 0),
        "final_score": getattr(target, "final_score", None),
    }

    # 简单文字总结，可直接在前端展示
    analysis_lines: List[str] = [
        f"学生 {basic_info.get('name') or basic_info['student_id']} 的学习画像：",
        f"- 视频学习：共 {video_count} 条记录，总时长 {_format_time_minutes(total_video_time)}。",
        f"- 作业：共 {len(homework_items)} 次，平均成绩约 {avg_hw:.1f} 分。",
        f"- 考试：共 {len(exam_items)} 场，平均成绩约 {avg_exam:.1f} 分。",
        f"- 出勤：共有 {attend_total} 条考勤记录，出勤 {present_cnt} 次，缺勤 {absent_cnt} 次，请假 {leave_cnt} 次，出勤率约 {attendance_rate:.1f}%。",
    ]

    return {
        "basic": basic_info,
        "video": {
            "total_time": total_video_time,
            "total_time_text": _format_time_minutes(total_video_time),
            "record_count": video_count,
        },
        "homeworks": homework_items,
        "exams": exam_items,
        "attendance": {
            "total": attend_total,
            "present": present_cnt,
            "absent": absent_cnt,
            "leave": leave_cnt,
            "late": late_cnt,
            "early_leave": early_cnt,
            "unknown": unknown_cnt,
            "attendance_rate": attendance_rate,
            "events": event_details,
        },
        "analysis_text": "\n".join(analysis_lines),
    }


def analyze_attendance_events(course: Course) -> Dict:
    """
    按“每一次考勤事件”统计出勤情况。
    (保留了详细的日期解析和多状态统计逻辑)
    """
    ctx = _build_context(course)

    # key 用 check_item_id；没有就退化为 name+event_time
    events_map: Dict[str, Dict] = {}

    for stu in ctx.students:
        for rec in stu.attendance_records:
            # [适配] 使用 event_time 替代 start_time
            time_val = rec.event_time or ""
            
            # 忽略完全缺少元信息的记录
            key = rec.check_item_id or (
                (rec.name or "").strip() + "|" + time_val
            )
            if not key.strip():
                continue

            ev = events_map.get(key)
            if ev is None:
                # 解析日期
                date_iso = ""
                date_cn = ""
                if time_val:
                    # 优先按 ISO 解析
                    try:
                        dt = datetime.fromisoformat(time_val)
                        date_iso = dt.date().isoformat()
                        date_cn = f"{dt.month}月{dt.day}日"
                    except Exception:
                        # 简单从 "YYYY-MM-DD" 拆
                        parts = time_val.split("T")[0].split("-")
                        if len(parts) >= 3:
                            date_iso = f"{parts[0]}-{parts[1]}-{parts[2]}"
                            try:
                                m = int(parts[1])
                                d = int(parts[2])
                                date_cn = f"{m}月{d}日"
                            except:
                                date_cn = date_iso
                        else:
                            date_cn = time_val

                ev = {
                    "check_item_id": rec.check_item_id or key,
                    "name": rec.name or "",
                    "start_time": time_val, # 这里的 key 保持 start_time 给前端/RAG用
                    "date": date_iso,
                    "date_cn": date_cn or date_iso,
                    "stats": {
                        AttendStatus.PRESENT: 0,
                        AttendStatus.ABSENT: 0,
                        AttendStatus.LEAVE: 0,
                        AttendStatus.LATE: 0,
                        AttendStatus.EARLY_LEAVE: 0,
                        AttendStatus.UNKNOWN: 0,
                    },
                }
                events_map[key] = ev

            s = rec.attend_status or AttendStatus.UNKNOWN
            if s not in ev["stats"]:
                # 容错：如果出现枚举定义之外的状态
                ev["stats"][s] = 0
            ev["stats"][s] += 1

    # 把 map 转成列表，并计算人数和出勤率
    events_list: List[Dict] = []
    for ev in events_map.values():
        stats = ev["stats"]
        total = int(sum(stats.values()))
        present = int(stats.get(AttendStatus.PRESENT, 0))
        absent = int(stats.get(AttendStatus.ABSENT, 0))
        leave = int(stats.get(AttendStatus.LEAVE, 0))
        late = int(stats.get(AttendStatus.LATE, 0))
        early_leave = int(stats.get(AttendStatus.EARLY_LEAVE, 0))
        unknown = int(stats.get(AttendStatus.UNKNOWN, 0))

        # 计算出勤率 (出勤+迟到+早退 通常都算到了，具体看业务定义，这里仅以 PRESENT 为准)
        attendance_rate = round(present / total * 100, 1) if total > 0 else 0.0

        events_list.append(
            {
                "check_item_id": ev["check_item_id"],
                "name": ev["name"],
                "date": ev["date"],
                "date_cn": ev["date_cn"],
                "start_time": ev["start_time"],
                "present": present,
                "absent": absent,
                "leave": leave,
                "late": late,
                "early_leave": early_leave,
                "unknown": unknown,
                "total": total,
                "attendance_rate": attendance_rate,
            }
        )

    # 按时间 + 名称排序
    events_list.sort(
        key=lambda e: (
            e.get("date") or "",
            e.get("start_time") or "",
            e.get("name") or "",
        )
    )

    # 写一小段总结文本，供 RAG 用
    lines: List[str] = [
        "【考勤整体概览】",
        f"- 课程共有学生 {ctx.total_students} 人，共记录考勤 {len(events_list)} 次。",
    ]
    if events_list:
        best = max(events_list, key=lambda e: e["attendance_rate"])
        worst = min(events_list, key=lambda e: e["attendance_rate"])

        lines += [
            "",
            f"- 最高出勤：{best['name']} ({best['date_cn']})，出勤率 {best['attendance_rate']}%",
            f"- 最低出勤：{worst['name']} ({worst['date_cn']})，出勤率 {worst['attendance_rate']}%",
        ]

    analysis_text = "\n".join(lines)

    return {
        "total_students": ctx.total_students,
        "events": events_list,
        "analysis_text": analysis_text,
    }