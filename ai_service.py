"""
ai_service.py (V9.2 完整修复版 - 修复考勤统计与缩进，保留所有详细逻辑)
"""

import os
import logging
import json
import re
from typing import Optional, Dict, Any, List

# 配置日志
logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class AIService:
    """
    统一对外的 AI 能力入口：
    - llm_type='ecnu' 时走 ECNU 大模型 + Agent 工作流
    """

    def __init__(
        self,
        llm_type: str = "rule",
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.llm_type = llm_type
        self.model_name = model_name or os.getenv("ECNU_MODEL", "educhat-r1")
        self.openai_client = None

        if llm_type == "ecnu" and OPENAI_AVAILABLE:
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            base_url = base_url or os.getenv(
                "OPENAI_BASE_URL", "https://chat.ecnu.edu.cn/open/api/v1"
            )
            if api_key:
                try:
                    self.openai_client = OpenAI(api_key=api_key, base_url=base_url)
                    logger.info("ECNU API 初始化成功, model=%s", self.model_name)
                except Exception as e:
                    logger.error("ECNU API 初始化失败: %s", e)

    # ============================================================
    # 对外主入口
    # ============================================================

    def answer_question(
        self,
        question: str,
        course_data: Dict[str, Any],
        data_processor=None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        history = history or []
        course_id = course_data.get("course_id") or ""

        if self.llm_type == "ecnu" and self.openai_client and data_processor:
            try:
                return self._agent_workflow(question, course_id, course_data, data_processor, history)
            except Exception as e:
                logger.error("Agent 工作流异常: %s", e, exc_info=True)
                try:
                    return self._fallback_rag_only(question, course_id, data_processor)
                except Exception:
                    return "AI 思考过程中发生错误，请稍后重试。"

        # 规则模式 Fallback
        knowledge = self._extract_course_knowledge(course_data)
        return self._answer_with_rules(question, knowledge)

    # ============================================================
    # Agent Workflow (核心逻辑)
    # ============================================================

    def _agent_workflow(
        self,
        question: str,
        course_id: str,
        course_data: Dict[str, Any],
        data_processor,
        history: List[Dict[str, Any]],
    ) -> str:
        # 1. 意图识别
        intent = self._analyze_intent(question, history)
        logger.info("AI 意图识别结果: %s", intent)

        # 2. 数据执行
        structured_data = ""
        try:
            course_obj = None
            if hasattr(data_processor, "store") and hasattr(data_processor.store, "get_course"):
                course_obj = data_processor.store.get_course(course_id)

            if course_obj is not None:
                structured_data = self._execute_data_query(course_obj, intent)
        except Exception as e:
            logger.warning("数据查询失败: %s", e)

        # 3. RAG 补充
        rag_context = self._build_rag_context(question, course_id, data_processor)

        # 4. 最终生成
        final_prompt = self._generate_final_prompt(question, structured_data, rag_context, history)

        response = self.openai_client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "你是一个智能教学助手，必须严格基于提供的数据回答问题，不得编造。"},
                {"role": "user", "content": final_prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()

    # ============================================================
    # Step 1: 意图识别
    # ============================================================

    def _analyze_intent(self, question: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        system_prompt = """
你是一个“教学数据意图识别引擎”。你的任务是**只**输出 JSON。

支持的参数字段：
- "names": [列表] 具体人名
- "ids": [列表] 数字ID或学号
- "date": [字符串] 日期 (格式 YYYY-MM-DD 或 MM-DD)
- "score_filter": [对象] {"operator": "<" / ">", "value": 数字}
- "target": [字符串] 核心对象 ("考试", "考勤", "作业", "整体")

示例: "3月8日谁缺勤？" -> {"date": "03-08", "target": "考勤"}
示例: "有多少人不及格" -> {"score_filter": {"operator": "<", "value": 60}, "target": "考试"}
"""
        user_input = f"用户当前问题: {question}"
        if history and len(history) > 0:
            last_q = history[-1].get("question", "")
            if last_q:
                user_input = f"上一轮问题: {last_q}\n{user_input}"

        try:
            kwargs = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input},
                ],
                "temperature": 0.0,
            }
            try:
                kwargs["response_format"] = {"type": "json_object"}
            except Exception:
                pass

            resp = self.openai_client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content or ""
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content) if content else {}
        except Exception as e:
            logger.warning("意图识别失败: %s", e)
            return {}

    # ============================================================
    # Step 2: 数据执行器 (已修复 Bug)
    # ============================================================

    def _execute_data_query(self, course: Any, intent: Dict[str, Any]) -> str:
        results: List[str] = []

        target = (intent.get("target") or "").strip()
        target_ids = intent.get("ids", []) or []
        target_names = intent.get("names", []) or []
        target_date = intent.get("date", "") or ""
        score_filter = intent.get("score_filter")

        # 展平学生
        all_students = []
        if getattr(course, "teachclasses", None):
            for tc in course.teachclasses:
                students = getattr(tc, "students", []) or []
                all_students.extend(students)

        if not all_students:
            return ""

        # 1. 按ID / 姓名 查询学生 (保留完整逻辑)
        if target_ids or target_names:
            for stu in all_students:
                is_match = False
                sid = str(getattr(stu, "student_id", "") or "")
                username = str(getattr(stu, "username", "") or "")
                name = str(getattr(stu, "name", "") or "")

                # ID 匹配
                for tid in target_ids:
                    if tid and (tid in sid or (username and tid in username)):
                        is_match = True
                        break
                    # 检查记录ID
                    if not is_match:
                        for ex in getattr(stu, "exam_records", []):
                            if tid in str(getattr(ex, "record_id", "")): is_match = True; break
                        for hw in getattr(stu, "homework_records", []):
                            if tid in str(getattr(hw, "record_id", "")): is_match = True; break
                
                # 姓名匹配
                if not is_match and target_names:
                    for t_name in target_names:
                        if t_name and t_name in name: is_match = True; break

                if is_match:
                    # [保留] 完整画像
                    results.append(self._format_student_profile(stu))

            return "\n".join(results)

        # 2. 考勤（按日期） - [修复] 缩进错误与统计逻辑
        if target_date and (target == "考勤" or not target):
            absent_list: List[str] = []
            late_list: List[str] = []
            total_count = 0
            present_count = 0

            for stu in all_students:
                for rec in getattr(stu, "attendance_records", []) or []:
                    # 构造所有可能带日期的信息
                    ts_candidates = [
                        getattr(rec, "event_time", None),
                        getattr(rec, "start_time", None),
                        getattr(rec, "date", None),
                        getattr(rec, "name", None),
                    ]
                    ts_str = " ".join(str(x) for x in ts_candidates if x)
                    
                    # [修复] 调用 _match_date
                    if not self._match_date(ts_str, target_date):
                        continue

                    # [修复] 统计逻辑现在处于正确的缩进层级
                    total_count += 1
                    stu_name = getattr(stu, "name", None) or getattr(stu, "student_id", "")
                    
                    status = getattr(getattr(rec, "attend_status", None), "value", None) or str(getattr(rec, "attend_status", ""))
                    
                    if status in ("出勤", "到课", "Present"):
                        present_count += 1
                    elif status in ("缺勤", "旷课"):
                        absent_list.append(stu_name)
                    elif status == "迟到":
                        late_list.append(stu_name)

            if total_count > 0:
                rate = (present_count / total_count * 100)
                res = f"【{target_date} 考勤统计结果】\n"
                res += f"- 应到人数: {total_count}\n"
                res += f"- 实到人数: {present_count} (出勤率 {rate:.1f}%)\n"
                res += f"- 缺勤人员: {', '.join(sorted(set(absent_list))) or '无'}\n"
                res += f"- 迟到人员: {', '.join(sorted(set(late_list))) or '无'}\n"
                results.append(res)
            else:
                results.append(f"【系统反馈】未在 {target_date} 找到考勤记录。")

            return "\n\n".join(results)

        # 3. 考勤汇总 (不限日期)
        if target == "考勤":
            absent_students: set[str] = set()
            late_students: set[str] = set()
            total_records = 0

            for stu in all_students:
                for rec in getattr(stu, "attendance_records", []) or []:
                    total_records += 1
                    name = getattr(stu, "name", None) or getattr(stu, "student_id", "")
                    status = getattr(getattr(rec, "attend_status", None), "value", None) or str(getattr(rec, "attend_status", ""))
                    if status in ("缺勤", "旷课"):
                        absent_students.add(name)
                    elif status == "迟到":
                        late_students.add(name)

            res = "【考勤汇总查询】\n"
            res += f"- 有缺勤记录的学生人数: {len(absent_students)}，名单: {', '.join(sorted(absent_students)) or '无'}\n"
            res += f"- 有迟到记录的学生人数: {len(late_students)}，名单: {', '.join(sorted(late_students)) or '无'}\n"
            res += f"- 总考勤记录数: {total_records}"
            results.append(res)
            return "\n\n".join(results)

        # 4. 分数筛选 - [修复] 变量名冲突
        if score_filter:
            op = str(score_filter.get("operator", "<")).strip()
            try:
                val = float(score_filter.get("value", 60))
            except Exception:
                val = 60.0

            filtered_list: List[str] = []
            for stu in all_students:
                for ex in getattr(stu, "exam_records", []) or []:
                    try:
                        s = float(getattr(ex, "score", 0.0))
                    except Exception:
                        continue

                    is_match = False  # [修复] 使用 is_match 代替 match
                    if op == "<" and s < val: is_match = True
                    elif op == ">" and s > val: is_match = True
                    elif op in ("=", "==") and s == val: is_match = True

                    if is_match:
                        name = getattr(stu, "name", "") or getattr(stu, "student_id", "")
                        title = getattr(ex, "title", "考试") or getattr(ex, "name", "考试")
                        filtered_list.append(f"{name}（{title}: {s}分）")

            if filtered_list:
                head = f"【分数筛选结果 ({op} {val})】\n共 {len(filtered_list)} 条记录：\n"
                body = "\n".join(filtered_list[:20])
                tail = "\n...(名单过长，仅展示前20个)" if len(filtered_list) > 20 else ""
                results.append(head + body + tail)
            else:
                results.append(f"【系统反馈】未发现分数 {op} {val} 的记录。")

            return "\n\n".join(results)

        return ""

    # ============================================================
    # 辅助函数 (格式化、日期匹配、Prompt)
    # ============================================================

    def _match_date(self, text: str, target: str) -> bool:
        """[修复] 补充缺失的日期匹配函数"""
        text = str(text)
        target = str(target)
        if not target: return False
        if target in text: return True

        # 处理 "3月8日"
        m = re.search(r"(\d{1,2})月(\d{1,2})日", target)
        if m:
            mm, dd = int(m.group(1)), int(m.group(2))
            patterns = [f"{mm}-{dd}", f"{mm:02d}-{dd:02d}", f"{mm}/{dd}"]
            for p in patterns:
                if p in text: return True

        # 处理 "03-08" -> "3月8日"
        m = re.search(r"0?(\d{1,2})[-/](0?(\d{1,2}))", target)
        if m:
            mm, dd = int(m.group(1)), int(m.group(2))
            if f"{mm}月{dd}日" in text: return True
        return False

    # ============================================================
    # 请在 ai_service.py 中替换 _format_student_profile 函数
    # ============================================================

    def _format_student_profile(self, stu: Any) -> str:
        """
        格式化单个学生的全量数据。
        [修复]：将考试和作业改为换行列表格式，避免 AI 解析混乱。
        """
        name = getattr(stu, "name", "") or "(未命名)"
        sid = getattr(stu, "student_id", "") or ""
        username = getattr(stu, "username", "") or ""

        # 1. 考试 (列表格式)
        exam_items: List[str] = []
        for ex in getattr(stu, "exam_records", []):
            score = getattr(ex, "score", None)
            total = getattr(ex, "total_score", None)
            title = (
                getattr(ex, "title", None)
                or getattr(ex, "name", None)
                or getattr(ex, "type", None)
                or "考试"
            )
            if score is not None and total:
                exam_items.append(f"  - {title}: {score}/{total}")
            elif score is not None:
                exam_items.append(f"  - {title}: {score}分")
        
        # 使用换行符拼接
        exam_str = "\n".join(exam_items) if exam_items else "  (无考试记录)"

        # 2. 作业 (列表格式，只展示前 15 条防止超长)
        hw_items: List[str] = []
        all_hws = getattr(stu, "homework_records", [])
        for hw in all_hws[:15]:
            title = getattr(hw, "title", None) or "作业"
            score = getattr(hw, "score", None)
            if score is not None:
                hw_items.append(f"  - {title}: {score}分")
        
        if len(all_hws) > 15:
            hw_items.append(f"  - ... (还有 {len(all_hws)-15} 次作业未显示)")
            
        # 使用换行符拼接
        hw_str = "\n".join(hw_items) if hw_items else "  (无作业记录)"

        # 3. 考勤
        att_records = getattr(stu, "attendance_records", []) or []
        present_cnt = 0
        for a in att_records:
            status = getattr(getattr(a, "attend_status", None), "value", None) or str(
                getattr(a, "attend_status", "")
            )
            if status in ("出勤", "到课", "Present"):
                present_cnt += 1
        att_str = (
            f"出勤 {present_cnt}/{len(att_records)} 次 (出勤率 {(present_cnt/len(att_records)*100):.1f}%)" 
            if att_records else "无考勤记录"
        )

        return (
            f"====== 学生画像 ======\n"
            f"姓名: {name}\n"
            f"ID: {sid}\n"
            f"学号: {username}\n"
            f"--- 考试记录 ---\n{exam_str}\n"
            f"--- 作业记录 ---\n{hw_str}\n"
            f"--- 考勤统计 ---\n{att_str}\n"
            "=====================\n"
        )

    def _build_rag_context(self, question: str, course_id: str, data_processor) -> str:
        rag_context_parts = []
        try:
            vector_service = getattr(data_processor, "vector_service", None)
            if vector_service:
                chunks = vector_service.retrieve(course_id, question, top_k=4) or []
                for i, item in enumerate(chunks):
                    txt = item.get("text") if isinstance(item, dict) else str(item)
                    rag_context_parts.append(f"片段{i+1}: {txt}")
        except Exception as e:
            logger.warning("RAG 检索失败: %s", e)
        return "\n".join(rag_context_parts)

    def _generate_final_prompt(
        self, question: str, structured_data: str, rag_context: str, history: List
    ) -> str:
        # [保留] 详细的 Prompt 模板
        history_str = "无"
        if history:
            history_str = ""
            for h in history[-3:]:
                q_clean = str(h.get('question', '')).replace('\n', ' ')
                a_clean = str(h.get('answer', '')).replace('\n', ' ')[:200] + "..."
                history_str += f"User: {q_clean}\nAI: {a_clean}\n"

        return f"""
你是一个专业、细致的教学数据分析助手。请根据以下提供的【真实数据】回答用户问题。

=== 上下文记忆 ===
{history_str}

=== 数据来源 ===
【精确查询数据】(优先级最高，包含特定名单、分数或画像)：
{structured_data if structured_data else "（未命中精确数据，请参考 RAG）"}

【参考资料】(RAG 语义检索，补充背景)：
{rag_context or "（无额外语义片段）"}

=== 用户问题 ===
{question}

=== 回答要求 ===
1. **事实优先**：如果【精确查询数据】里有具体的名单、分数或数字，必须以此为准，直接引用，不要编造。
2. **聚焦意图**：
   - 如果数据是学生全量画像，但用户只问“考勤”，请只提取考勤部分回答。
   - 如果数据是“不及格名单”，请总结人数并列出名字。
3. **清晰结构**：优先用短句、列表形式给出结论。
4. **主动建议**：在回答最后，可以给出 1-2 个相关的后续分析建议。

请用简体中文、Markdown 格式输出。
"""

    # 规则模式回退
    def _fallback_rag_only(self, question: str, course_id: str, data_processor) -> str:
        return "Agent 模式异常，请检查日志。"
    
    def _extract_course_knowledge(self, course_data):
        return {} # Placeholder
    def _answer_with_rules(self, q, k):
        return "AI 服务未连接。"
    def _clean_html(self, text):
        return re.sub(r'<[^>]+>', '', text).strip() if text else ""