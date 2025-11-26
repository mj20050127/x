"""
data_models.py
修复说明：
1. 在 Course 类中加回了 raw 字段，解决 'Course object has no attribute raw' 错误。
2. 保持了之前的 Enum 缓存修复和类型转换逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ========= 工具函数 ========= #

def _safe_float(value: Any, default: float = 0.0) -> float:
    """安全转换为 float，允许负数"""
    if value is None:
        return default
    if isinstance(value, (float, int)):
        return float(value)
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    """安全转换为 int，允许负数"""
    if value is None:
        return default
    if isinstance(value, int):
        return value
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


# ========= 枚举类型 ========= #

class AttendStatus(Enum):
    PRESENT = "出勤"
    ABSENT = "缺勤"
    LEAVE = "请假"
    LATE = "迟到"
    EARLY_LEAVE = "早退"
    UNKNOWN = "未知"

    @classmethod
    def from_raw(cls, raw_status: str) -> "AttendStatus":
        if not hasattr(cls, "_lookup_cache"):
            cache = {member.value: member for member in cls}
            cache.update({
                "到课": cls.PRESENT,
                "旷课": cls.ABSENT,
                "缺课": cls.ABSENT,
            })
            setattr(cls, "_lookup_cache", cache)
        
        cache = getattr(cls, "_lookup_cache")
        if not raw_status:
            return cls.UNKNOWN
        return cache.get(raw_status.strip(), cls.UNKNOWN)


class ResourceType(Enum):
    VIDEO = "视频"
    HOMEWORK = "作业"
    EXAM = "考试"
    ATTACHMENT = "附件"
    OTHER = "其他"

    @classmethod
    def from_raw(cls, raw_type: str) -> "ResourceType":
        if not hasattr(cls, "_lookup_cache"):
            cache = {member.value: member for member in cls}
            setattr(cls, "_lookup_cache", cache)

        cache = getattr(cls, "_lookup_cache")

        if not raw_type:
            return cls.OTHER
            
        raw_type = str(raw_type).strip()
        
        if raw_type in cache:
            return cache[raw_type]

        lower_type = raw_type.lower()
        result = cls.OTHER
        
        if "视频" in raw_type or "video" in lower_type:
            result = cls.VIDEO
        elif "作业" in raw_type or "homework" in lower_type:
            result = cls.HOMEWORK
        elif "考试" in raw_type or "exam" in lower_type or "测验" in raw_type:
            result = cls.EXAM
        elif "附件" in raw_type or "ppt" in lower_type or "pdf" in lower_type:
            result = cls.ATTACHMENT
        
        cache[raw_type] = result
        return result


# ========= 核心数据结构 ========= #

@dataclass(slots=True)
class VideoRecord:
    resource_id: str
    view_time: float = 0.0
    start_time: Optional[str] = None

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "VideoRecord":
        if not raw:
            return cls(resource_id="", view_time=0.0)
        
        raw_time = _safe_float(raw.get("view_time"))
        view_time = max(0.0, raw_time)
            
        return cls(
            resource_id=str(raw.get("resource_id", "")),
            view_time=view_time,
            start_time=raw.get("start_time"),
        )


@dataclass(slots=True)
class HomeworkRecord:
    resource_id: str
    score: float = 0.0
    total_score: float = 0.0

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "HomeworkRecord":
        if not raw: 
            return cls(resource_id="")

        total = max(0.0, _safe_float(raw.get("total_score")))
        score = _safe_float(raw.get("score"))
        
        if total > 0 and score > total:
            score = total
            
        return cls(
            resource_id=str(raw.get("resource_id", "")),
            score=score,
            total_score=total,
        )


@dataclass(slots=True)
class ExamRecord:
    resource_id: str
    score: float = 0.0
    total_score: float = 0.0

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "ExamRecord":
        if not raw: 
            return cls(resource_id="")

        total = max(0.0, _safe_float(raw.get("total_score")))
        score = _safe_float(raw.get("score"))
        
        if total > 0 and score > total:
            score = total

        return cls(
            resource_id=str(raw.get("resource_id", "")),
            score=score,
            total_score=total,
        )


# ============================================================
# 请在 data_models.py 中替换 AttendanceRecord 类
# ============================================================

@dataclass(slots=True)
class AttendanceRecord:
    attend_status: AttendStatus
    check_item_id: str = "" 
    event_time: str = ""
    name: str = ""  # [新增] 存储 "第1次考勤" 或 "3月8日考勤" 这种名称

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "AttendanceRecord":
        if not raw:
            return cls(attend_status=AttendStatus.UNKNOWN)
        
        # 获取时间
        raw_time = (
            raw.get("check_in_time") 
            or raw.get("create_time") 
            or raw.get("start_time") 
            or raw.get("time") 
            or ""
        )

        # [新增] 获取考勤名称
        raw_name = str(raw.get("name") or raw.get("title") or "未知考勤")
        
        return cls(
            attend_status=AttendStatus.from_raw(raw.get("attend_status", "")),
            check_item_id=str(raw.get("check_item_id") or ""),
            event_time=str(raw_time),
            name=raw_name 
        )


@dataclass(slots=True)
class Student:
    student_id: str
    # 新增字段：账号、姓名、专业等（都带默认值，兼容旧数据）
    username: Optional[str] = None
    name: Optional[str] = None
    clazz: Optional[str] = None
    major: Optional[str] = None
    login_times: int = 0
    final_score: Optional[float] = None

    # 行为数据
    video_records: List["VideoRecord"] = field(default_factory=list)
    homework_records: List["HomeworkRecord"] = field(default_factory=list)
    exam_records: List["ExamRecord"] = field(default_factory=list)
    attendance_records: List["AttendanceRecord"] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "Student":
        if not raw:
            return cls(student_id="")

        # 1）兼容 student_id / students_id 两种写法
        raw_sid = raw.get("student_id") or raw.get("students_id") or ""
        student_id = str(raw_sid)

        # 2）名字：你的 JSON 里是 student_truename
        name = (
            raw.get("student_truename")
            or raw.get("student_name")
            or raw.get("name")
        )

        # 3）学号：student_username
        username = raw.get("student_username") or raw.get("username")

        clazz = raw.get("class_name")
        major = raw.get("major")

        # 4）登录次数 / 期末成绩 等数值字段做安全转换
        login_times = _safe_int(raw.get("login_times"))

        final_score_raw = (
            raw.get("course_final_score")
            or raw.get("final_score")
            or raw.get("first_class_score")
        )
        final_score = (
            _safe_float(final_score_raw) if final_score_raw is not None else None
        )

        return cls(
            student_id=student_id,
            username=username,
            name=name,
            clazz=clazz,
            major=major,
            login_times=login_times,
            final_score=final_score,
            video_records=[
                VideoRecord.from_raw(v) for v in (raw.get("video_records") or [])
            ],
            homework_records=[
                HomeworkRecord.from_raw(h)
                for h in (raw.get("homework_records") or [])
            ],
            exam_records=[
                ExamRecord.from_raw(e) for e in (raw.get("exam_records") or [])
            ],
            attendance_records=[
                AttendanceRecord.from_raw(a)
                for a in (raw.get("attendance_records") or [])
            ],
        )



@dataclass(slots=True)
class Resource:
    resource_id: str
    title: str
    resource_type: ResourceType
    teaching_week: Optional[int] = None
    view_times: int = 0
    download_times: int = 0

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "Resource":
        if not raw:
            return cls(resource_id="", title="", resource_type=ResourceType.OTHER)

        raw_type = raw.get("resource_type") or raw.get("type") or ""
        week = raw.get("teaching_week") or raw.get("week")
        
        raw_views = _safe_int(raw.get("view_times"))
        raw_downloads = _safe_int(raw.get("download_times"))
        
        return cls(
            resource_id=str(raw.get("resource_id", "")),
            title=str(raw.get("title", "")),
            resource_type=ResourceType.from_raw(raw_type),
            teaching_week=_safe_int(week) if week is not None else None,
            view_times=max(0, raw_views),
            download_times=max(0, raw_downloads),
        )


@dataclass(slots=True)
class TeachClass:
    class_id: str
    class_name: Optional[str] = None
    students: List[Student] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "TeachClass":
        if not raw:
            return cls(class_id="")
        return cls(
            class_id=str(raw.get("class_id", "")),
            class_name=raw.get("class_name"),
            students=[Student.from_raw(s) for s in (raw.get("students") or [])],
        )


@dataclass(slots=True)
class Course:
    course_id: str
    course_name: str
    file_name: str
    liked: int = 0
    viewed: int = 0
    create_time: Optional[str] = None
    update_time: Optional[str] = None
    term: Optional[str] = None
    resources: Dict[str, Resource] = field(default_factory=dict)
    teachclasses: List[TeachClass] = field(default_factory=list)
    
    # [修复] 加回 raw 字段，用于兼容旧接口
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: Dict[str, Any], file_name: str) -> "Course":
        if not raw:
            return cls(course_id="", course_name=file_name, file_name=file_name)
            
        resources_list = raw.get("resources") or []
        resources = {
            str(r.get("resource_id", "")): Resource.from_raw(r)
            for r in resources_list
        }
        
        teachclasses_list = raw.get("teachclasses") or []
        teachclasses = [
            TeachClass.from_raw(tc) for tc in teachclasses_list
        ]

        raw_liked = _safe_int(raw.get("liked"))
        raw_viewed = _safe_int(raw.get("viewed"))

        return cls(
            course_id=str(raw.get("course_id", "")),
            course_name=str(raw.get("course_name") or file_name),
            file_name=file_name,
            liked=max(0, raw_liked),
            viewed=max(0, raw_viewed),
            create_time=raw.get("create_time"),
            update_time=raw.get("update_time"),
            term=raw.get("term"),
            resources=resources,
            teachclasses=teachclasses,
            raw=raw  # [修复] 将原始数据存入对象
        )