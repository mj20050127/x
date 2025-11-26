"""
ai_service.py (V8 Agent版 - 基于 LLM 意图识别的智能数据查询)
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
    def __init__(self, llm_type='rule', api_key=None, model_name=None, base_url=None):
        self.llm_type = llm_type
        self.model_name = model_name or os.getenv('ECNU_MODEL', 'educhat-r1')
        self.openai_client = None

        if llm_type == 'ecnu' and OPENAI_AVAILABLE:
            api_key = api_key or os.getenv('OPENAI_API_KEY')
            base_url = base_url or os.getenv('OPENAI_BASE_URL', 'https://chat.ecnu.edu.cn/open/api/v1')
            if api_key:
                try:
                    self.openai_client = OpenAI(api_key=api_key, base_url=base_url)
                    logger.info(f"ECNU API 初始化成功: {self.model_name}")
                except Exception as e:
                    logger.error(f"ECNU API 初始化失败: {e}")

    def answer_question(self, question: str, course_data: Dict[str, Any], data_processor=None, history: List = []) -> str:
        course_id = course_data.get('course_id')
        
        # 优先使用 Agent 模式
        if self.llm_type == 'ecnu' and self.openai_client and data_processor:
            try:
                return self._agent_workflow(question, course_id, data_processor, history)
            except Exception as e:
                logger.error(f"Agent 运行出错: {e}")
                import traceback
                traceback.print_exc()
                return "AI 思考过程中发生错误，请稍后重试。"
        
        # 降级
        return "AI 服务未连接，无法智能分析。"

    # ============================================================
    # Agent Workflow (核心逻辑)
    # ============================================================

    def _agent_workflow(self, question: str, course_id: str, data_processor, history: List) -> str:
        """
        智能体工作流：
        1. [思考] 调用 LLM 分析用户意图，提取查询参数 (日期、人名、分数阈值等)。
        2. [执行] 根据参数在 Python 内存中精确查找数据。
        3. [回答] 结合查找结果和 RAG 片段，生成最终回答。
        """
        
        # --- Step 1: 意图识别 (LLM 做路由) ---
        # 我们让 AI 帮我们提取参数，而不是用正则去猜
        intent = self._analyze_intent(question, history)
        logger.info(f"AI 意图识别结果: {intent}")

        # --- Step 2: 数据工具执行 (Python 查数据) ---
        # 根据 AI 提取的参数，去 database/memory 里捞数据
        structured_data = ""
        try:
            course_obj = data_processor.store.get_course(course_id)
            if course_obj:
                structured_data = self._execute_data_query(course_obj, intent)
        except Exception as e:
            logger.warning(f"数据查询失败: {e}")

        # --- Step 3: RAG 补充 (语义检索) ---
        # 即使有了结构化数据，也还是查一下 RAG 补充背景信息
        rag_context = ""
        if hasattr(data_processor, 'vector_service'):
            chunks = data_processor.vector_service.retrieve(course_id, question, top_k=4)
            for i, item in enumerate(chunks):
                rag_context += f"片段{i+1}: {item.get('text', '')}\n"

        # --- Step 4: 最终生成 ---
        final_prompt = self._generate_final_prompt(question, structured_data, rag_context)
        
        response = self.openai_client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "你是一个智能教学助手，基于提供的数据回答问题。"},
                {"role": "user", "content": final_prompt}
            ],
            temperature=0.2 # 稍微高一点点，让语言更自然，但依然保持严谨
        )
        return response.choices[0].message.content.strip()

    # ============================================================
    # Step 1: 意图识别 (让 AI 提取参数)
    # ============================================================

    def _analyze_intent(self, question: str, history: List) -> Dict:
        """
        请求 LLM 将自然语言转换为结构化查询参数 (JSON)
        """
        # 构造 prompt 告诉 AI 如何提取参数
        system_prompt = """
你是一个“意图识别引擎”。请分析用户的问题，提取关键查询参数，并以 JSON 格式输出。
不要回答问题，只输出 JSON。

支持的参数字段：
- "names": [列表] 问题中提到的具体人名 (如 "张三")
- "ids": [列表] 问题中提到的数字ID或学号
- "date": [字符串] 问题中提到的日期 (格式 YYYY-MM-DD 或 MM-DD)
- "score_filter": [对象] 分数筛选条件, 包含 "operator" (>/</=) 和 "value" (数字)。例如 "不及格" -> {"operator": "<", "value": 60}
- "target": [字符串] 用户关注的核心对象 (如 "考勤", "作业", "考试", "整体")

示例1: "3月8日谁缺勤了？"
JSON: {"date": "03-08", "target": "考勤"}

示例2: "id为12345的学生考了多少分"
JSON: {"ids": ["12345"], "target": "考试"}

示例3: "有多少人不及格？"
JSON: {"score_filter": {"operator": "<", "value": 60}, "target": "考试"}

示例4: "张三的表现怎么样"
JSON: {"names": ["张三"], "target": "整体"}
"""
        # 结合一点历史上下文，防止代词（"他"）无法解析
        user_input = f"用户当前问题: {question}"
        if history:
            last_q = history[-1].get('question', '')
            user_input = f"上一轮问题: {last_q}\n" + user_input

        try:
            resp = self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.0, # 必须是0，保证JSON格式稳定
                response_format={"type": "json_object"} # 强制 JSON (如果模型支持)
            )
            content = resp.choices[0].message.content
            # 清洗一下 markdown 代码块标记 (```json ... ```)
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
        except Exception as e:
            logger.warning(f"意图识别失败或非JSON格式: {e}")
            return {}

    # ============================================================
    # Step 2: 数据执行器 (Python 逻辑)
    # ============================================================

    def _execute_data_query(self, course: Any, intent: Dict) -> str:
        """
        根据 AI 提取的 intent，在内存中通过 Python 代码筛选数据。
        """
        results = []
        
        # 1. 获取意图参数
        target_ids = intent.get("ids", [])
        target_names = intent.get("names", [])
        target_date = intent.get("date", "")
        score_filter = intent.get("score_filter") # {operator, value}
        
        # 展平所有学生
        all_students = []
        if course.teachclasses:
            for tc in course.teachclasses:
                all_students.extend(tc.students)

        # --- 逻辑分支 A: 筛选学生 (按 ID 或 姓名) ---
        if target_ids or target_names:
            for stu in all_students:
                is_match = False
                # 匹配 ID
                for tid in target_ids:
                    # 模糊匹配，防止提取不全
                    if tid in str(stu.student_id) or (stu.username and tid in str(stu.username)):
                        is_match = True
                        break
                    # 检查该生名下的记录ID (考试/作业流水号)
                    if not is_match:
                        for ex in stu.exam_records:
                            if tid in str(ex.record_id): is_match = True; break
                        for hw in stu.homework_records:
                            if tid in str(hw.record_id): is_match = True; break
                
                # 匹配 姓名
                if not is_match and target_names:
                    s_name = str(stu.name or "")
                    for t_name in target_names:
                        if t_name in s_name: is_match = True; break
                
                if is_match:
                    # 提取该生全部信息，由 AI 决定用多少
                    results.append(self._format_student_profile(stu))

        # --- 逻辑分支 B: 筛选考勤 (按日期) ---
        elif target_date:
            # 归一化日期格式 "MM-DD" 或 "YYYY-MM-DD"
            # 简单起见，只要 event_time 包含这个字符串就算命中
            absent_list = []
            late_list = []
            
            for stu in all_students:
                for rec in stu.attendance_records:
                    if rec.event_time and target_date in rec.event_time:
                        name = stu.name or stu.student_id
                        status = rec.attend_status.value if hasattr(rec.attend_status, 'value') else str(rec.attend_status)
                        if status in ["缺勤", "旷课"]: absent_list.append(name)
                        if status == "迟到": late_list.append(name)
            
            if absent_list or late_list:
                res = f"【{target_date} 考勤查询结果】\n"
                res += f"- 缺勤人员: {', '.join(list(set(absent_list))) or '无'}\n"
                res += f"- 迟到人员: {', '.join(list(set(late_list))) or '无'}\n"
                results.append(res)
            else:
                results.append(f"【系统反馈】未在 {target_date} 找到考勤记录。")

        # --- 逻辑分支 C: 分数筛选 (不及格/高分) ---
        elif score_filter:
            op = score_filter.get("operator", "<")
            val = float(score_filter.get("value", 60))
            
            filtered_list = []
            for stu in all_students:
                for ex in stu.exam_records:
                    s = float(ex.score)
                    # 动态执行比较
                    match = False
                    if op == "<" and s < val: match = True
                    elif op == ">" and s > val: match = True
                    elif op == "=" and s == val: match = True
                    
                    if match:
                        name = stu.name or stu.student_id
                        title = ex.title or "考试"
                        filtered_list.append(f"{name} ({title}: {s}分)")
            
            if filtered_list:
                results.append(f"【分数筛选结果 ({op} {val})】\n共发现 {len(filtered_list)} 条记录：\n" + "\n".join(filtered_list[:20]))
                if len(filtered_list) > 20: results.append("...(名单过长，仅展示前20个)")
            else:
                results.append(f"【系统反馈】未发现分数 {op} {val} 的记录。")

        return "\n\n".join(results)

    def _format_student_profile(self, stu) -> str:
        """格式化单个学生的全量数据"""
        # 考试
        exams = [f"{ex.title}: {ex.score}/{ex.total_score}" for ex in stu.exam_records]
        exam_str = "、".join(exams) if exams else "无"
        # 作业
        hws = [f"{hw.title}: {hw.score}" for hw in stu.homework_records[:8]] # 只取前8
        hw_str = "、".join(hws) if hws else "无"
        # 考勤
        att_present = sum(1 for a in stu.attendance_records if a.attend_status.value == "出勤")
        att_str = f"出勤 {att_present}/{len(stu.attendance_records)} 次"
        
        return (
            f"======\n"
            f"学生: {stu.name} (ID: {stu.student_id}, 学号: {stu.username})\n"
            f"考试: {exam_str}\n"
            f"作业: {hw_str} ...\n"
            f"考勤: {att_str}\n"
            f"======\n"
        )

    # ============================================================
    # Step 4: 最终生成
    # ============================================================

    def _generate_final_prompt(self, question: str, structured_data: str, rag_context: str) -> str:
        return f"""
你是一个智能教学助手。请根据以下【数据查询结果】和【参考资料】回答用户问题。

=== 数据查询结果 (Python 精确执行结果) ===
{structured_data if structured_data else "（未命中精确查询条件，请参考下方 RAG 资料）"}

=== 参考资料 (RAG 语义检索) ===
{rag_context}

=== 用户问题 ===
{question}

=== 回答要求 ===
1. **事实优先**：如果【数据查询结果】里有具体的名单、分数或数字，必须以此为准，直接引用，不要编造。
2. **分析意图**：如果【数据查询结果】列出了学生的所有成绩，但用户只问“考勤”，给出出勤人数，缺勤人数等内容，请你只从里面提取考勤信息回答，不要把考试成绩也念一遍。
3. **友好回复**：如果查不到数据，请礼貌告知。
4. **上下文理解**：如果用户问“他们是谁”或“还有谁”，请结合【上下文记忆】推断用户指的是上一轮提到的人群。
5. **精准回答**：如果是查考勤名单，请直接列出【精准匹配数据】里的名字和id。

请用 Markdown 格式输出。
"""

    # 规则模式提取逻辑（保持不变，略）
    def _extract_course_knowledge(self, course_data):
        # ... 原有代码 ...
        return {}
    def _answer_with_rules(self, q, k):
        return "AI 服务不可用。"