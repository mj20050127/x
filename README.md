# AI教学分析助手

基于水杉平台CS空间的AI教学分析助手，通过大语言模型(LLM)技术结合前端开发，实现智能化的教学行为数据分析和问答功能。

## 功能特点

- **AI助手**: 智能问答系统，支持自然语言查询，基于规则或LLM进行回答
- **智能分析**: 学习路径分析、学生表现分析、资源使用分析
- **教学评估**: 为教学评估和学生学习分析提供智能化支持

## 项目结构

```
.
├── app.py                      # Flask后端主应用
├── data_processor.py           # 数据处理和分析模块
├── ai_service.py               # AI服务模块（支持规则、ECNU API）
├── run.py                      # 快速启动脚本
├── requirements.txt            # Python依赖包
├── README.md                   # 项目说明文档
├── config.example.env          # 配置文件示例
├── static/                     # 前端静态文件
│   ├── index.html              # 主页面
│   ├── style.css               # 样式文件
│   └── app.js                  # 前端JavaScript逻辑
└── SHUISHAN-CLAD/              # 教学行为数据目录（课程数据JSON文件）
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 准备数据

确保 `SHUISHAN-CLAD` 目录中包含教学行为数据的JSON文件。

### 3. 配置LLM API (可选)

项目默认使用基于规则的问答系统。如需使用大语言模型，请配置ECNU开发者平台API：

#### 配置ECNU开发者平台API

1. 复制配置文件：
   ```bash
   copy config.example.env .env
   ```
   (Linux/Mac: `cp config.example.env .env`)

2. 编辑 `.env` 文件，填入ECNU API配置：
   ```env
   LLM_TYPE=ecnu
   OPENAI_BASE_URL=https://chat.ecnu.edu.cn/open/api/v1
   OPENAI_API_KEY=sk-your-ecnu-api-key-here
   ECNU_MODEL=educhat-r1
   ```

3. 安装 openai 库（ECNU API使用OpenAI兼容接口）：
   ```bash
   pip install openai
   ```

**获取ECNU API Key**: 访问 https://developer.ecnu.edu.cn 获取开发者平台API密钥

### 4. 运行服务

#### 方式一: 使用快速启动脚本(推荐)

```bash
python run.py
```

该脚本会自动检查依赖和数据目录，然后启动服务。

#### 方式二: 直接运行Flask应用

```bash
python app.py
```

服务将在 `http://localhost:5000` 启动。

### 5. 访问应用

在浏览器中打开 `http://localhost:5000` 即可使用。

## 功能说明

### 1. 课程管理
- 浏览所有课程列表
- 按分类筛选课程（AI、编程、数据、系统等）
- 搜索课程
- 查看课程详细信息

### 2. 智能分析
- **学习路径分析**: 分析学生的学习路径和访问顺序，识别常见学习模式，提供详细的分析报告
- **学生表现分析**: 分析学生的视频观看时长、作业提交、考试成绩、出勤率等，生成综合性评估
- **资源使用分析**: 分析学习资源的使用情况和受欢迎程度，识别热门资源和冷门资源

### 3. AI助手
支持自然语言查询，例如：
- "这门课程有多少学生？"
- "第1周有哪些学习内容？"
- "最受欢迎的资源是什么？"
- "视频观看情况如何？"
- "哪些章节更受欢迎？"
- "学生的学习路径是怎样的？"
- "学生的整体表现如何？"

**LLM支持**: 
- **rule** (默认): 基于规则的问题理解和回答
- **ecnu**: 华东师范大学开发者平台API（推荐用于教学场景）

## API接口

### 课程相关
- `GET /api/courses` - 获取所有课程列表
- `GET /api/course/<course_id>` - 获取课程详细信息

### AI助手
- `POST /api/course/<course_id>/chat` - AI问答
  ```json
  {
    "question": "问题内容"
  }
  ```

### 智能分析
- `POST /api/analyze/learning-path` - 分析学习路径
  ```json
  {
    "course_id": "课程ID"
  }
  ```
- `POST /api/analyze/student-performance` - 分析学生表现
- `POST /api/analyze/resource-usage` - 分析资源使用情况

## 技术栈

- **后端**: Flask + Python
- **前端**: HTML5 + CSS3 + JavaScript
- **数据处理**: JSON处理、数据分析和统计
- **AI服务**: 
  - 基于规则的问答系统（默认）
  - ECNU开发者平台API（可选，推荐）

## 配置说明

### LLM类型配置

在 `.env` 文件中设置 `LLM_TYPE`：

- `rule`: 基于规则的问答（默认，无需API密钥）
- `ecnu`: 华东师范大学开发者平台API（推荐）

### ECNU API配置

```env
LLM_TYPE=ecnu
OPENAI_BASE_URL=https://chat.ecnu.edu.cn/open/api/v1
OPENAI_API_KEY=sk-your-ecnu-api-key-here
ECNU_MODEL=educhat-r1
```

推荐的ECNU模型：
- `educhat-r1` - 教育大模型（推荐用于教学场景）
- `ecnu-max` - 最强的通用推理模型
- `ecnu-plus` - 通用的推理能力
- `ecnu-turbo` - 推理速度优化

详细文档: https://developer.ecnu.edu.cn/vitepress/llm/model.html

## 开发说明

### 数据处理流程

1. 读取原始JSON数据文件
2. 提取课程信息、资源信息、学生行为数据
3. 进行数据清洗和统计分析
4. 为AI问答提供结构化的知识库

### AI服务实现

- **规则模式**: 通过关键词匹配和规则逻辑回答问题
- **ECNU API模式**: 将课程数据格式化为上下文，调用ECNU开发者平台API进行深度分析

## 依赖说明

### 必需依赖
- Flask - Web框架
- flask-cors - 跨域支持
- python-dotenv - 环境变量管理

### 可选依赖
- openai - ECNU API支持（ECNU API使用OpenAI兼容接口）

## 常见问题

### Q: 如何切换LLM模式？
A: 在 `.env` 文件中修改 `LLM_TYPE` 的值，重启服务即可。

### Q: 支持哪些数据格式？
A: 当前支持从 `SHUISHAN-CLAD` 目录读取JSON格式的教学行为数据。

### Q: 智能分析的结果如何查看？
A: 选择课程后，点击"智能分析"选项卡，可以分别进行学习路径分析、学生表现分析和资源使用分析，每个分析都会生成详细的分析报告。

## 许可证

本项目仅供学习和研究使用。

## 作者

华东师范大学数据学院
