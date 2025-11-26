from __future__ import annotations

import json
import logging
import time
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional

from data_models import Course

logger = logging.getLogger(__name__)


class DataStore:
    """
    统一的数据访问层（增强版）：
    - 支持懒加载 / 全量加载
    - LRU 缓存，控制内存占用
    - 完整的异常处理和数据验证
    - 更安全的模糊匹配逻辑
    """

    def __init__(
        self,
        data_dir: str | Path = "SHUISHAN-CLAD",
        *,
        eager_load: bool = True,
        max_cache_size: Optional[int] = None,
        enable_fuzzy: bool = True,
    ) -> None:
        """
        :param data_dir: JSON 数据所在目录
        :param eager_load: True=启动时解析所有课程；False=按需加载
        :param max_cache_size: 最大缓存课程数，None 表示不限制
        :param enable_fuzzy: 是否允许模糊匹配（找不到精确 course_id 时）
        """
        self.data_dir = Path(data_dir)
        self.eager_load = eager_load
        self.max_cache_size = max_cache_size
        self.enable_fuzzy = enable_fuzzy

        # course_id -> Course（使用有序 dict, 实现 LRU）
        self._course_cache: "OrderedDict[str, Course]" = OrderedDict()
        # course_id -> Path
        self._index: Dict[str, Path] = {}
        # file_name -> error message
        self._load_errors: Dict[str, str] = {}

        # 监控指标
        self.last_scan_seconds: float = 0.0
        self.total_files: int = 0
        self.total_courses: int = 0

        self._scan_data_dir(eager_load=self.eager_load)

    # ================== 对外接口 ================== #

    def reload(self) -> None:
        """
        重新扫描目录。会清空缓存和索引。
        """
        self._scan_data_dir(eager_load=self.eager_load)

    def list_courses(self) -> List[Course]:
        """
        返回所有课程对象。
        - eager_load=True 时，直接返回缓存中的所有课程；
        - eager_load=False 时，会按需加载所有索引到缓存再返回。
        """
        if not self.eager_load:
            # 懒加载模式下，确保所有 index 中的课程都被加载一次
            for course_id in list(self._index.keys()):
                _ = self.get_course(course_id)

        return list(self._course_cache.values())

    def get_course(self, course_id: str) -> Optional[Course]:
        """
        根据 course_id 获取 Course 对象。

        匹配顺序：
        1. 精确匹配缓存中的 course_id
        2. 精确匹配索引中的 course_id（懒加载）
        3. 精确匹配文件名 / 文件名（不含后缀）
        4. （可选）模糊匹配：前缀匹配 / 子串匹配
        """
        course_id = str(course_id).strip()
        if not course_id:
            return None

        # 1. 先从缓存取（LRU 访问）
        course = self._get_from_cache(course_id)
        if course is not None:
            return course

        # 2. 精确按 course_id 在索引中找
        if course_id in self._index:
            course = self._load_course_from_path(self._index[course_id])
            if course:
                self._add_to_cache(course.course_id, course)
            return course

        # 3. 按文件名 / 文件名（不带后缀）精确匹配
        file_matches: List[str] = []
        for cid, path in self._index.items():
            stem = path.stem  # 不带 .json
            if course_id == path.name or course_id == stem:
                file_matches.append(cid)

        if len(file_matches) == 1:
            cid = file_matches[0]
            course = self._get_from_cache(cid)
            if course is not None:
                return course
            course = self._load_course_from_path(self._index[cid])
            if course:
                self._add_to_cache(course.course_id, course)
            return course
        elif len(file_matches) > 1:
            logger.warning(
                "DataStore.get_course(%s) 文件名匹配到多个课程：%s，"
                "请使用准确的 course_id",
                course_id,
                file_matches,
            )
            return None

        # 4. 可选的模糊匹配（前缀 + 子串），只在启用时尝试
        if self.enable_fuzzy:
            fuzzy_candidates: List[str] = []

            # 4.1 前缀匹配
            for cid in self._index.keys():
                if cid.startswith(course_id):
                    fuzzy_candidates.append(cid)

            # 4.2 子串匹配（只在前缀匹配没有结果时才考虑）
            if not fuzzy_candidates:
                for cid in self._index.keys():
                    if course_id in cid:
                        fuzzy_candidates.append(cid)

            if len(fuzzy_candidates) == 1:
                cid = fuzzy_candidates[0]
                logger.info(
                    "DataStore.get_course(%s) 使用模糊匹配命中课程 %s", course_id, cid
                )
                course = self._get_from_cache(cid)
                if course is not None:
                    return course
                course = self._load_course_from_path(self._index[cid])
                if course:
                    self._add_to_cache(course.course_id, course)
                return course

            if len(fuzzy_candidates) > 1:
                logger.warning(
                    "DataStore.get_course(%s) 模糊匹配到多个课程：%s，"
                    "为避免误用，未返回任何课程。",
                    course_id,
                    fuzzy_candidates,
                )
                return None

        # 5. 未找到
        logger.warning("DataStore.get_course(%s) 未找到任何匹配课程", course_id)
        return None

    def get_load_errors(self) -> Dict[str, str]:
        """
        返回最近一次扫描中加载失败的文件及原因：
        {file_name: error_message}
        """
        return dict(self._load_errors)

    @property
    def stats(self) -> Dict[str, int | float]:
        """
        简单的运行指标，方便监控/调试
        """
        return {
            "total_files": self.total_files,
            "total_courses": self.total_courses,
            "cached_courses": len(self._course_cache),
            "load_error_files": len(self._load_errors),
            "last_scan_seconds": self.last_scan_seconds,
        }

    # ================== 内部实现 ================== #

    def _scan_data_dir(self, *, eager_load: bool) -> None:
        """
        扫描数据目录，构建 course_id -> Path 索引，
        在 eager_load=True 时顺便解析所有课程。
        """
        start = time.perf_counter()

        if not self.data_dir.exists():
            raise FileNotFoundError(f"数据目录不存在: {self.data_dir}")

        json_files = [
            f for f in self.data_dir.glob("*.json") if "_cleaned" not in f.name
        ]

        self._index.clear()
        self._course_cache.clear()
        self._load_errors.clear()

        self.total_files = len(json_files)
        self.total_courses = 0

        for path in json_files:
            try:
                course_id = self._extract_course_id(path)
                if not course_id:
                    raise ValueError("JSON 中缺少非空字段 'course_id'")

                # 重复 course_id 处理：保留第一个，记录错误但不覆盖
                if course_id in self._index:
                    raise ValueError(
                        f"检测到重复的 course_id='{course_id}', "
                        f"已有文件: {self._index[course_id].name}"
                    )

                self._index[course_id] = path
                self.total_courses += 1

                # 如果启用 eager_load，立刻解析为 Course 对象并进入缓存
                if eager_load:
                    course = self._load_course_from_path(path, course_id_hint=course_id)
                    if course:
                        self._add_to_cache(course.course_id, course)

            except Exception as exc:  # noqa: BLE001
                logger.exception("加载课程文件 %s 失败: %s", path, exc)
                self._load_errors[path.name] = str(exc)

        self.last_scan_seconds = time.perf_counter() - start
        logger.info(
            "DataStore 扫描完成: 目录=%s, 文件数=%d, 课程数=%d, 缓存数=%d, 耗时=%.3fs",
            self.data_dir,
            self.total_files,
            self.total_courses,
            len(self._course_cache),
            self.last_scan_seconds,
        )

    def _extract_course_id(self, path: Path) -> Optional[str]:
        """
        从 JSON 文件中提取 course_id，用于建立索引。
        只做最小解析，避免在懒加载模式下浪费时间。
        """
        with path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        if not isinstance(raw, dict):
            raise ValueError("顶层 JSON 必须是对象(dict)")
        course_id = str(raw.get("course_id", "")).strip()
        if not course_id:
            return None
        return course_id

    def _load_course_from_path(
        self, path: Path, course_id_hint: Optional[str] = None
    ) -> Optional[Course]:
        """
        真正把某个 JSON 文件解析为 Course 对象。
        :param course_id_hint: 如果调用方已经知道 course_id，可传入用于校验
        """
        try:
            with path.open("r", encoding="utf-8") as fh:
                raw = json.load(fh)
            if not isinstance(raw, dict):
                raise ValueError("顶层 JSON 必须是对象(dict)")

            course = Course.from_raw(raw, file_name=path.name)

            if course_id_hint and course.course_id != course_id_hint:
                logger.warning(
                    "文件 %s 中的 course_id=%s 与索引中的 %s 不一致，"
                    "以 JSON 中的为准。",
                    path,
                    course.course_id,
                    course_id_hint,
                )

            return course
        except Exception as exc:  # noqa: BLE001
            logger.exception("解析课程文件 %s 失败: %s", path, exc)
            self._load_errors[path.name] = str(exc)
            return None

    # -------- LRU 缓存辅助 -------- #

    def _get_from_cache(self, course_id: str) -> Optional[Course]:
        """
        从缓存中获取并更新 LRU 顺序。
        """
        course = self._course_cache.get(course_id)
        if course is not None:
            # OrderedDict: 最近访问的移动到末尾
            self._course_cache.move_to_end(course_id, last=True)
        return course

    def _add_to_cache(self, course_id: str, course: Course) -> None:
        """
        把课程加入缓存，超出 max_cache_size 时使用 LRU 淘汰。
        """
        if course_id in self._course_cache:
            # 更新已有条目并移动到末尾
            self._course_cache[course_id] = course
            self._course_cache.move_to_end(course_id, last=True)
            return

        # 如果设置了缓存上限，先淘汰最久未使用的
        if self.max_cache_size is not None and self.max_cache_size > 0:
            while len(self._course_cache) >= self.max_cache_size:
                evicted_id, _ = self._course_cache.popitem(last=False)
                logger.debug("DataStore 缓存已满, 淘汰课程 %s", evicted_id)

        self._course_cache[course_id] = course
        self._course_cache.move_to_end(course_id, last=True)
