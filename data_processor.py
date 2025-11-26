"""
data_processor.py (V3 - 最终稳定版)
集成 RAG 服务，清理冗余接口，确保与 analytics.py 和 ai_service.py 完美兼容。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from data_store import DataStore
from data_models import Course
import analytics
import knowledge
from knowledge import CorpusItem

# [关键] 导入 RAG 服务
from rag_service import RAGService

logger = logging.getLogger(__name__)


class DataProcessor:
    """
    数据处理总控类
    """

    def __init__(
        self,
        data_dir: str | Path = "SHUISHAN-CLAD",
        *,
        eager_load: bool = True,
        max_cache_size: Optional[int] = None,
        enable_fuzzy: bool = True,
    ) -> None:
        
        self.store = DataStore(
            data_dir=data_dir,
            eager_load=eager_load,
            max_cache_size=max_cache_size,
            enable_fuzzy=enable_fuzzy,
        )

        self._raw_cache: Dict[str, Dict[str, Any]] = {}
        self._statistics_cache: Dict[str, Dict[str, Any]] = {}
        self._learning_path_cache: Dict[str, Dict[str, Any]] = {}
        self._student_perf_cache: Dict[str, Dict[str, Any]] = {}
        self._resource_usage_cache: Dict[str, Dict[str, Any]] = {}
        self._corpus_cache: Dict[str, List[CorpusItem]] = {}

        # [关键] 初始化向量服务，并挂载到实例上
        # 这样 app.py 和 ai_service.py 就能通过 data_processor.vector_service 访问它
        self.vector_service = RAGService(self, persist_dir="./chroma_store")

    # ------------------------------------------------------------------
    # [关键] 主动触发向量化的方法 (供 init_vectors.py 使用)
    # ------------------------------------------------------------------
    def refresh_all_vectors(self):
        """扫描所有课程并强制重建向量索引"""
        print("[DataProcessor] 开始全量构建向量索引...")
        courses = self.get_all_courses()
        total = len(courses)
        for i, c in enumerate(courses, 1):
            cid = c['course_id']
            cname = c['course_name']
            print(f"[{i}/{total}] 正在处理: {cname} ({cid})...")
            try:
                # 调用 RAGService 的建索引功能
                self.vector_service.ensure_index(cid, reset=True)
            except Exception as e:
                print(f"  -> 失败: {e}")
        print("[DataProcessor] 全量索引构建完成！")

    # ------------------------------------------------------------------
    # 基础数据访问
    # ------------------------------------------------------------------

    def reload(self) -> None:
        self.store.reload()
        self._raw_cache.clear()
        self._statistics_cache.clear()
        self._learning_path_cache.clear()
        self._student_perf_cache.clear()
        self._resource_usage_cache.clear()
        self._corpus_cache.clear()

    def get_all_courses(self) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for course in self.store.list_courses():
            result.append(
                {
                    "course_id": course.course_id,
                    "course_name": course.course_name,
                    "file_name": course.file_name,
                    "liked": course.liked,
                    "viewed": course.viewed,
                    "create_time": course.create_time or "",
                    "update_time": course.update_time or "",
                }
            )
        return result

    def get_course_by_id(self, course_id: str) -> Optional[Dict[str, Any]]:
        course_id = str(course_id or "").strip()
        if not course_id:
            return None

        if course_id in self._raw_cache:
            return self._raw_cache[course_id]

        course = self.store.get_course(course_id)
        if course is None:
            return None

        # 兼容旧接口，返回字典
        # [修复] 确保 Course 对象里有 raw 字段 (data_models.py 已修复)
        raw = dict(getattr(course, 'raw', {}) or {})
        raw.setdefault("course_id", course.course_id)
        raw.setdefault("course_name", course.course_name)
        raw.setdefault("file_name", course.file_name)

        self._raw_cache[course.course_id] = raw
        if course.course_id != course_id:
            self._raw_cache[course_id] = raw

        return raw

    def _get_course_obj(self, course_or_id_or_raw: Any) -> Optional[Course]:
        if isinstance(course_or_id_or_raw, Course):
            return course_or_id_or_raw
        if isinstance(course_or_id_or_raw, str):
            return self.store.get_course(course_or_id_or_raw)
        if isinstance(course_or_id_or_raw, dict):
            cid = str(course_or_id_or_raw.get("course_id", "")).strip()
            if not cid:
                return None
            return self.store.get_course(cid)
        return None

    # ------------------------------------------------------------------
    # 统计与分析 (供前端 API 使用)
    # ------------------------------------------------------------------

    def analyze_course(self, course_data: Dict[str, Any]) -> Dict[str, Any]:
        course = self._get_course_obj(course_data)
        if course is None:
            raise ValueError("analyze_course: 无效的课程数据")
        return analytics.compute_overview(course)

    def get_statistics(self, course_data: Dict[str, Any]) -> Dict[str, Any]:
        course = self._get_course_obj(course_data)
        if course is None:
            raise ValueError("get_statistics: 无效的课程数据")
        cid = course.course_id
        if cid in self._statistics_cache:
            return self._statistics_cache[cid]
        stats = analytics.compute_statistics(course)
        self._statistics_cache[cid] = stats
        return stats

    def analyze_learning_path(self, course_data: Dict[str, Any]) -> Dict[str, Any]:
        course = self._get_course_obj(course_data)
        if course is None:
            raise ValueError("analyze_learning_path: 无效的课程数据")
        cid = course.course_id
        if cid in self._learning_path_cache:
            return self._learning_path_cache[cid]
        result = analytics.analyze_learning_path(course)
        self._learning_path_cache[cid] = result
        return result

    def analyze_student_performance(self, course_data: Dict[str, Any]) -> Dict[str, Any]:
        course = self._get_course_obj(course_data)
        if course is None:
            raise ValueError("analyze_student_performance: 无效的课程数据")
        cid = course.course_id
        if cid in self._student_perf_cache:
            return self._student_perf_cache[cid]
        result = analytics.analyze_student_performance(course)
        self._student_perf_cache[cid] = result
        return result

    def analyze_resource_usage(self, course_data: Dict[str, Any]) -> Dict[str, Any]:
        course = self._get_course_obj(course_data)
        if course is None:
            raise ValueError("analyze_resource_usage: 无效的课程数据")
        cid = course.course_id
        if cid in self._resource_usage_cache:
            return self._resource_usage_cache[cid]
        result = analytics.analyze_resource_usage(course)
        self._resource_usage_cache[cid] = result
        return result

    # ------------------------------------------------------------------
    # 语料构建 (供 RAG 使用)
    # ------------------------------------------------------------------

    def build_course_corpus(self, course_data: Dict[str, Any]) -> List[CorpusItem]:
        course = self._get_course_obj(course_data)
        if course is None:
            raise ValueError("build_course_corpus: 无效的课程数据")
        cid = course.course_id
        if cid in self._corpus_cache:
            return self._corpus_cache[cid]

        # 优先使用缓存的统计结果
        stats = self._statistics_cache.get(cid) or analytics.compute_statistics(course)
        lp = self._learning_path_cache.get(cid) or analytics.analyze_learning_path(course)
        sp = self._student_perf_cache.get(cid) or analytics.analyze_student_performance(course)
        ru = self._resource_usage_cache.get(cid) or analytics.analyze_resource_usage(course)

        # [修复] knowledge.build_course_corpus 会调用 analytics.analyze_attendance_events
        # 这里只需要透传即可，不需要我们在 data_processor 里再封装一层
        corpus = knowledge.build_course_corpus(
            course,
            stats=stats,
            learning_path=lp,
            student_performance=sp,
            resource_usage=ru,
        )
        self._corpus_cache[cid] = corpus
        return corpus