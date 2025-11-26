"""
app.py (最终版 - 适配对话历史与 RAG)
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import sys
from pathlib import Path
from datetime import datetime

# 尝试加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from data_processor import DataProcessor
from ai_service import AIService

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

# 1. 初始化 DataProcessor (它会带起 RAGService)
data_processor = DataProcessor()

# 2. 初始化 AI 服务
llm_type = os.getenv('LLM_TYPE', 'rule')
ecnu_api_key = os.getenv('OPENAI_API_KEY')
ecnu_base_url = os.getenv('OPENAI_BASE_URL')
ecnu_model = os.getenv('ECNU_MODEL')

print(f"[INFO] AI模式: {llm_type}")
print(f"[INFO] 模型: {ecnu_model}")

ai_service = AIService(
    llm_type=llm_type, 
    api_key=ecnu_api_key, 
    model_name=ecnu_model, 
    base_url=ecnu_base_url
)

# 3. [新增] 全局对话历史 (用于多轮对话记忆)
chat_history = []

DATA_DIR = Path('SHUISHAN-CLAD')

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/courses', methods=['GET'])
def get_courses():
    try:
        courses = data_processor.get_all_courses()
        return jsonify({'success': True, 'data': courses, 'total': len(courses)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/course/<course_id>', methods=['GET'])
def get_course_detail(course_id):
    try:
        course_data = data_processor.get_course_by_id(course_id)
        if not course_data:
            return jsonify({'success': False, 'error': '课程不存在'}), 404
        analysis = data_processor.analyze_course(course_data)
        return jsonify({
            'success': True,
            'data': {
                'course_info': {
                    'course_id': course_data.get('course_id', course_id),
                    'course_name': course_data.get('course_name', ''),
                    'liked': course_data.get('liked', 0),
                    'viewed': course_data.get('viewed', 0),
                    'create_time': course_data.get('create_time', ''),
                    'update_time': course_data.get('update_time', '')
                },
                'analysis': analysis
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/course/<course_id>/chat', methods=['POST'])
def chat_with_course(course_id):
    """与课程AI助手对话"""
    try:
        data = request.json
        question = data.get('question', '')
        if not question:
            return jsonify({'success': False, 'error': '问题不能为空'}), 400
        
        course_data = data_processor.get_course_by_id(course_id)
        if not course_data:
            return jsonify({'success': False, 'error': '课程不存在'}), 404
        
        # [关键] 传入 history 和 data_processor
        # 这里必须与 ai_service.py 中的定义匹配
        answer = ai_service.answer_question(
            question, 
            course_data, 
            data_processor=data_processor,
            history=chat_history
        )
        
        if answer is None:
            answer = "抱歉，AI服务暂时无法响应。"
            
        # [关键] 更新历史记录
        chat_history.append({"question": question, "answer": answer})
        # 保持最近 10 轮对话，防止上下文过长
        if len(chat_history) > 10: 
            chat_history.pop(0)
        
        return jsonify({
            'success': True,
            'data': {
                'question': question,
                'answer': answer,
                'timestamp': datetime.now().isoformat()
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# --- 分析接口保持不变 ---

@app.route('/api/analyze/learning-path', methods=['POST'])
def analyze_learning_path():
    try:
        data = request.json
        return jsonify({'success': True, 'data': data_processor.analyze_learning_path(data_processor.get_course_by_id(data.get('course_id')))})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analyze/student-performance', methods=['POST'])
def analyze_student_performance():
    try:
        data = request.json
        return jsonify({'success': True, 'data': data_processor.analyze_student_performance(data_processor.get_course_by_id(data.get('course_id')))})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analyze/resource-usage', methods=['POST'])
def analyze_resource_usage():
    try:
        data = request.json
        return jsonify({'success': True, 'data': data_processor.analyze_resource_usage(data_processor.get_course_by_id(data.get('course_id')))})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # 确保数据目录存在
    DATA_DIR.mkdir(exist_ok=True)
    Path('exports').mkdir(exist_ok=True)
    
    # 设置输出编码
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    
    print("[INFO] AI教学分析助手服务启动中...")
    print(f"[INFO] 访问地址: http://0.0.0.0:5000")
    
    app.run(host='0.0.0.0', port=5000, debug=True)