// 全局变量
let currentCourseId = null;
let currentTab = 'overview';
let charts = {};

function getChartInstance(key, elementId) {
    if (typeof echarts === 'undefined') return null;
    const container = document.getElementById(elementId);
    if (!container) {
        charts[key] = null;
        return null;
    }

    const existing = charts[key];
    if (existing && existing.getDom && existing.getDom() === container) {
        return existing;
    }

    if (existing && existing.dispose) {
        existing.dispose();
    }

    charts[key] = echarts.init(container);
    return charts[key];
}

const defaultKpis = {
    total: '--',
    resources: '--',
    learning: '--',
    assignments: '--',
    attendance: '--',
    warning: '--'
};

// API基础URL
const API_BASE = window.location.origin;

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    loadCourses();
    setupEventListeners();
    window.addEventListener('resize', () => {
        Object.values(charts).forEach(chart => chart && chart.resize());
    });
});

// 设置事件监听器
function setupEventListeners() {
    // 搜索按钮（兼容性保留）
    document.getElementById('search-btn')?.addEventListener('click', () => {
        const searchTerm = document.getElementById('course-search').value.trim();
        let courses = allCourses;
        
        if (searchTerm) {
            courses = allCourses.filter(course => 
                course.course_name.toLowerCase().includes(searchTerm.toLowerCase())
            );
        }
        
        displayCourses(courses, currentCategory);
    });

    // 搜索框实时搜索和回车
    const searchInput = document.getElementById('course-search');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const searchTerm = e.target.value.trim();
            let courses = allCourses;
            
            if (searchTerm) {
                courses = allCourses.filter(course => 
                    course.course_name.toLowerCase().includes(searchTerm.toLowerCase())
                );
            }
            
            displayCourses(courses, currentCategory);
        });
        
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
            }
        });
    }

    // 选项卡切换
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            switchTab(tab);
        });
    });

    // 分析按钮
    document.getElementById('analyze-path-btn').addEventListener('click', analyzeLearningPath);
    document.getElementById('analyze-performance-btn').addEventListener('click', analyzeStudentPerformance);
    document.getElementById('analyze-resource-btn').addEventListener('click', analyzeResourceUsage);

    // 聊天功能
    document.getElementById('send-btn').addEventListener('click', sendMessage);
    document.getElementById('chat-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    // 建议标签点击
    document.querySelectorAll('.suggestion-tag').forEach(tag => {
        tag.addEventListener('click', () => {
            const question = tag.dataset.question;
            document.getElementById('chat-input').value = question;
            sendMessage();
        });
    });
    
    // 分类标签切换
    document.querySelectorAll('.category-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            // 更新标签状态
            document.querySelectorAll('.category-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            // 更新当前分类
            currentCategory = tab.dataset.category;
            
            // 重新显示课程
            const searchTerm = document.getElementById('course-search').value.trim();
            let courses = allCourses;
            
            if (searchTerm) {
                courses = allCourses.filter(course => 
                    course.course_name.toLowerCase().includes(searchTerm.toLowerCase())
                );
            }

            displayCourses(courses, currentCategory);
        });
    });

    // 过滤与排序
    document.getElementById('course-filter')?.addEventListener('change', (e) => {
        currentFilter = e.target.value;
        displayCourses(allCourses, currentCategory);
    });

    document.getElementById('course-sort')?.addEventListener('change', (e) => {
        currentSort = e.target.value;
        displayCourses(allCourses, currentCategory);
    });
}

// 加载课程列表
async function loadCourses(searchTerm = '') {
    try {
        const response = await fetch(`${API_BASE}/api/courses`);
        const result = await response.json();
        
        if (result.success) {
            let courses = result.data;
            
            // 保存所有课程
            allCourses = courses;
            
            // 搜索过滤
            if (searchTerm) {
                courses = courses.filter(course => 
                    course.course_name.toLowerCase().includes(searchTerm.toLowerCase())
                );
            }
            
            displayCourses(courses, currentCategory);
        } else {
            showError('加载课程列表失败: ' + result.error);
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
    }
}

// 课程分类函数
function categorizeCourse(courseName) {
    const name = courseName.toLowerCase();
    
    // 人工智能相关
    if (name.includes('人工智能') || name.includes('ai') || name.includes('机器学习') || 
        name.includes('深度学习') || name.includes('计算机视觉') || name.includes('cv') ||
        name.includes('神经网络') || name.includes('算法与人工智能')) {
        return 'ai';
    }
    
    // 编程开发
    if (name.includes('编程') || name.includes('程序') || name.includes('python') ||
        name.includes('c++') || name.includes('语言') || name.includes('开发') ||
        name.includes('软件') || name.includes('设计思维')) {
        return 'programming';
    }
    
    // 数据科学
    if (name.includes('数据') || name.includes('大数据') || name.includes('数据挖掘') ||
        name.includes('数据分析') || name.includes('统计')) {
        return 'data';
    }
    
    // 系统网络
    if (name.includes('系统') || name.includes('网络') || name.includes('计算机系统') ||
        name.includes('操作系统') || name.includes('云计算') || name.includes('分布式') ||
        name.includes('编译') || name.includes('数据结构')) {
        return 'system';
    }
    
    return 'other';
}

// 显示课程列表（支持分类）
let allCourses = [];
let currentCategory = 'all';
let currentFilter = 'all';
let currentSort = 'default';

function displayCourses(courses, category = 'all') {
    const courseList = document.getElementById('course-list');
    courseList.innerHTML = '';

    if (!courses || courses.length === 0) {
        courseList.innerHTML = '<div class="empty-state"><p>未找到课程</p></div>';
        return;
    }

    // 按分类过滤
    let filteredCourses = [...courses];
    if (category !== 'all') {
        filteredCourses = filteredCourses.filter(course => categorizeCourse(course.course_name) === category);
    }

    // 简单学期过滤（如果有相关字段）
    if (currentFilter !== 'all') {
        filteredCourses = filteredCourses.filter(course => (course.semester || '').toLowerCase().includes(currentFilter));
    }

    // 排序
    if (currentSort === 'students') {
        filteredCourses.sort((a, b) => (b.student_count || 0) - (a.student_count || 0));
    } else if (currentSort === 'active') {
        const getActiveScore = (item) => (item.viewed || 0) + (item.liked || 0);
        filteredCourses.sort((a, b) => getActiveScore(b) - getActiveScore(a));
    }

    if (filteredCourses.length === 0) {
        courseList.innerHTML = '<div class="empty-state"><p>未找到匹配课程</p></div>';
        return;
    }
    
    filteredCourses.forEach(course => {
        const card = document.createElement('div');
        card.className = 'course-card';
        const category = categorizeCourse(course.course_name);
        const categoryNames = {
            'ai': '人工智能',
            'programming': '编程开发',
            'data': '数据科学',
            'system': '系统网络',
            'other': '其他'
        };
        
        card.innerHTML = `
            <div class="course-badge">${categoryNames[category] || '课程'}</div>
            <h3>${course.course_name}</h3>
            <div class="course-meta">
                <span>点赞: ${course.liked || 0}</span>
                <span>浏览: ${course.viewed || 0}</span>
            </div>
            <div class="course-id">ID: ${course.course_id}</div>
        `;
        card.addEventListener('click', () => loadCourseDetail(course.course_id));
        courseList.appendChild(card);
    });
}

// 加载课程详情
async function loadCourseDetail(courseId) {
    currentCourseId = courseId;
    
    try {
        const response = await fetch(`${API_BASE}/api/course/${courseId}`);
        const result = await response.json();
        
        if (result.success) {
            displayCourseDetail(result.data);
            document.getElementById('course-detail').classList.remove('hidden');
            document.getElementById('course-detail').scrollIntoView({ behavior: 'smooth' });
        } else {
            showError('加载课程详情失败: ' + result.error);
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
    }
}

// 显示课程详情
function displayCourseDetail(data) {
    const courseInfo = data.course_info || {};
    const analysis = data.analysis || {};

    // 更新标题
    const courseName = analysis.course_name || courseInfo.course_name || '课程详情';
    document.getElementById('course-name').textContent = courseName;

    // 更新课程元信息
    const metaParts = [];
    if (courseInfo.start_time || courseInfo.start_date) metaParts.push(`开课：${courseInfo.start_time || courseInfo.start_date}`);
    if (courseInfo.class_name || courseInfo.class) metaParts.push(`班级：${courseInfo.class_name || courseInfo.class}`);
    if (courseInfo.teacher) metaParts.push(`教师：${courseInfo.teacher}`);
    document.getElementById('course-meta').textContent = metaParts.join(' · ') || '开课时间 · 班级信息待加载';

    // 更新课程统计信息
    const courseStats = document.getElementById('course-stats');
    courseStats.innerHTML = `
        <span>点赞: ${courseInfo.liked || 0}</span>
        <span>浏览: ${courseInfo.viewed || 0}</span>
    `;

    const warningCount = (analysis.warning_students && analysis.warning_students.length)
        || analysis.warning_count
        || 0;
    const statusText = warningCount > 5 ? '状态：需关注' : warningCount > 0 ? '状态：有风险点' : '状态：正常';
    const statusEl = document.getElementById('course-status');
    statusEl.textContent = statusText;
    statusEl.classList.remove('attention', 'alert');
    if (warningCount > 5) {
        statusEl.classList.add('alert');
    } else if (warningCount > 0) {
        statusEl.classList.add('attention');
    }

    // 更新仪表盘数据
    updateDashboard(courseInfo, analysis);

    // 总览文案
    const overviewInsights = document.getElementById('overview-insights');
    if (analysis.key_insights) {
        overviewInsights.innerHTML = analysis.key_insights.replace(/\n/g, '<br>');
    } else {
        overviewInsights.textContent = '可结合 AI 问答查看风险点与改进建议。';
    }

    const activitySnapshot = document.getElementById('activity-snapshot');
    if (analysis.activity_trends) {
        activitySnapshot.innerHTML = analysis.activity_trends.replace(/\n/g, '<br>');
    } else {
        activitySnapshot.textContent = '选择课程后将展示活跃度与风险点。';
    }

    // 切换到概览选项卡
    switchTab('overview');
    updateAssistantContext();
}

// 更新仪表盘视图
function updateDashboard(courseInfo = {}, analysis = {}) {
    const totalStudents = analysis.total_students
        || courseInfo.student_count
        || courseInfo.students
        || courseInfo.enrolled
        || defaultKpis.total;

    const resourceCount = analysis.resource_count
        || (analysis.resources && analysis.resources.total)
        || courseInfo.resource_count
        || defaultKpis.resources;

    const learningRecords = analysis.video_records
        || analysis.learning_records
        || courseInfo.video_count
        || defaultKpis.learning;

    const assignmentCount = analysis.homework_submissions
        || analysis.assignment_count
        || courseInfo.homework_count
        || defaultKpis.assignments;

    const attendanceCount = analysis.attendance_sessions
        || analysis.attendance_count
        || courseInfo.attendance_count
        || defaultKpis.attendance;

    const warningCount = (analysis.warning_students && analysis.warning_students.length)
        || analysis.warning_count
        || courseInfo.warning_count
        || defaultKpis.warning;

    setKpiValue('kpi-total', totalStudents);
    setKpiValue('kpi-resources', resourceCount);
    setKpiValue('kpi-learning', learningRecords);
    setKpiValue('kpi-assignments', assignmentCount);
    setKpiValue('kpi-attendance', attendanceCount);
    setKpiValue('kpi-warning', warningCount);

    updateCharts(analysis);
}

function setKpiValue(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = (value === undefined || value === null || value === '') ? '--' : value;
}

// 构建与更新 ECharts
function updateCharts(analysis = {}) {
    const performanceList = analysis.student_details || analysis.top_students || [];

    const scatterData = analysis.performance_points
        || (performanceList.length ? performanceList.map((student, index) => [
            index + 1,
            student.avg_exam_score || student.avg_homework_score || 0,
            student.student_id || `学生${index + 1}`
        ]) : null)
        || Array.from({ length: 15 }, (_, i) => [i + 1, Math.round(Math.random() * 40) + 60, `学生${i + 1}`]);

    const barSource = analysis.resource_usage
        || (analysis.resources && analysis.resources.top_used)
        || [];

    const barData = (barSource || []).slice(0, 10).map(item => ({
        name: item.title || item.name || '资源',
        value: item.views || item.popularity || item.students_count || 0
    }));

    if (barData.length === 0) {
        barData.push({ name: '视频', value: 120 });
        barData.push({ name: '作业', value: 98 });
        barData.push({ name: '讲义', value: 76 });
    }

    const resourceBreakdown = analysis.resource_breakdown
        || (analysis.resources && analysis.resources.by_type)
        || [];

    const resourcePieData = (resourceBreakdown || []).map(item => ({
        name: item.type || item.name || '资源',
        value: item.count || item.value || 0
    }));

    if (resourcePieData.length === 0) {
        resourcePieData.push({ name: '视频', value: 40 });
        resourcePieData.push({ name: '作业', value: 25 });
        resourcePieData.push({ name: '测验', value: 20 });
        resourcePieData.push({ name: '文档', value: 15 });
    }

    const behaviorStats = analysis.behavior_overview || {
        categories: ['出勤', '视频', '作业', '考试'],
        values: [80, 120, 95, 70]
    };

    renderResourcePie(resourcePieData);
    renderBehaviorChart(behaviorStats);
    renderScatterChart(scatterData);
    renderBarChart(barData);
}

function renderScatterChart(data) {
    const instance = getChartInstance('scatter', 'scatter-chart');
    if (!instance) return;

    instance.setOption({
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'item',
            formatter: (params) => `${params.data[2] || '学生'}<br/>成绩：${params.data[1]}`
        },
        xAxis: {
            name: '排名',
            splitLine: { show: false },
            axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
            axisLabel: { color: '#9ca3af' }
        },
        yAxis: {
            name: '成绩',
            axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
            axisLabel: { color: '#9ca3af' },
            splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
        },
        series: [{
            type: 'scatter',
            data,
            symbolSize: (val) => 12 + (val[1] / 10),
            itemStyle: {
                color: new echarts.graphic.RadialGradient(0.4, 0.3, 1, [{
                    offset: 0, color: '#60a5fa'
                }, {
                    offset: 1, color: '#1d4ed8'
                }])
            }
        }]
    });
}

function renderBarChart(data) {
    const instance = getChartInstance('bar', 'bar-chart');
    if (!instance) return;

    instance.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis' },
        grid: { left: 60, right: 20, top: 30, bottom: 50 },
        xAxis: {
            type: 'category',
            data: data.map(item => item.name),
            axisLabel: { color: '#9ca3af', rotate: 25 }
        },
        yAxis: {
            type: 'value',
            axisLabel: { color: '#9ca3af' },
            splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
        },
        series: [{
            type: 'bar',
            data: data.map(item => item.value),
            itemStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: '#60a5fa' },
                    { offset: 1, color: '#1d4ed8' }
                ])
            },
            barWidth: '55%'
        }]
    });
}

function renderResourcePie(data) {
    const instance = getChartInstance('resourcePie', 'resource-pie');
    if (!instance) return;

    instance.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'item' },
        legend: {
            orient: 'vertical',
            left: 'left',
            textStyle: { color: '#9ca3af' }
        },
        series: [{
            name: '资源',
            type: 'pie',
            radius: ['40%', '70%'],
            avoidLabelOverlap: false,
            itemStyle: {
                borderRadius: 10,
                borderColor: '#0b1223',
                borderWidth: 2
            },
            label: { color: '#e5e7eb' },
            data
        }]
    });
}

function renderBehaviorChart(stats) {
    const instance = getChartInstance('behavior', 'behavior-chart');
    if (!instance) return;

    const categories = stats.categories || (Array.isArray(stats) ? stats.map(item => item.name || '指标') : []);
    const values = stats.values || (Array.isArray(stats) ? stats.map(item => item.value || 0) : []);

    instance.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis' },
        grid: { left: 40, right: 20, top: 30, bottom: 40 },
        xAxis: {
            type: 'category',
            data: categories,
            axisLabel: { color: '#9ca3af' }
        },
        yAxis: {
            type: 'value',
            axisLabel: { color: '#9ca3af' },
            splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
        },
        series: [{
            type: 'bar',
            data: values,
            itemStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: '#34d399' },
                    { offset: 1, color: '#0ea5e9' }
                ])
            },
            barWidth: '55%'
        }]
    });
}


// 分析学习路径
async function analyzeLearningPath() {
    if (!currentCourseId) return;
    
    const resultBox = document.getElementById('path-analysis-result');
    resultBox.innerHTML = '<div class="loading"></div> 正在分析...';
    
    try {
        const response = await fetch(`${API_BASE}/api/analyze/learning-path`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ course_id: currentCourseId })
        });
        
        const result = await response.json();
        
        if (result.success) {
            const data = result.data;
            let html = '';
            
            // 显示分析文本
            if (data.analysis_text) {
                html += `<div class="analysis-text">${data.analysis_text.replace(/\n/g, '<br>')}</div>`;
            }
            
            // 显示常见路径详情
            if (data.common_paths && data.common_paths.length > 0) {
                html += '<h4>详细路径分析:</h4><ul class="path-list">';
                data.common_paths.forEach((path, index) => {
                    html += `<li><strong>路径 ${index + 1}:</strong> ${path.description}</li>`;
                });
                html += '</ul>';
            }
            
            resultBox.innerHTML = html || '<p>暂无数据</p>';
        } else {
            resultBox.innerHTML = `分析失败: ${result.error}`;
        }
    } catch (error) {
        resultBox.innerHTML = `网络错误: ${error.message}`;
    }
}

// 分析学生表现
async function analyzeStudentPerformance() {
    if (!currentCourseId) return;
    
    const resultBox = document.getElementById('performance-analysis-result');
    resultBox.innerHTML = '<div class="loading"></div> 正在分析...';
    
    try {
        const response = await fetch(`${API_BASE}/api/analyze/student-performance`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ course_id: currentCourseId })
        });
        
        const result = await response.json();
        
        if (result.success) {
            const data = result.data;
            let html = '';
            
            // 显示分析文本
            if (data.analysis_text) {
                html += `<div class="analysis-text">${data.analysis_text.replace(/\n/g, '<br>')}</div>`;
            }
            
            // 显示优秀学生详情
            if (data.top_students && data.top_students.length > 0) {
                html += '<h4>详细表现数据:</h4><ul class="performance-list">';
                data.top_students.forEach((student, index) => {
                    html += `<li><strong>第${index + 1}名:</strong> 学生ID ${student.student_id.substring(0, 8)}... `;
                    if (student.avg_homework_score > 0) {
                        html += `作业均分: ${student.avg_homework_score.toFixed(1)}分, `;
                    }
                    if (student.avg_exam_score > 0) {
                        html += `考试均分: ${student.avg_exam_score.toFixed(1)}分`;
                    }
                    html += '</li>';
                });
                html += '</ul>';
            }
            
            resultBox.innerHTML = html || '<p>暂无数据</p>';
        } else {
            resultBox.innerHTML = `分析失败: ${result.error}`;
        }
    } catch (error) {
        resultBox.innerHTML = `网络错误: ${error.message}`;
    }
}

// 分析资源使用
// ============================================================
// 请用这段代码完全覆盖 app.js 里的 analyzeResourceUsage 函数
// ============================================================

async function analyzeResourceUsage() {
    if (!currentCourseId) return;
    
    // 1. 获取正确的容器 (修正 ID 为 resource-analysis-result)
    const resultBox = document.getElementById('resource-analysis-result');
    resultBox.innerHTML = '<div class="loading"></div> 正在分析资源使用情况...';
    
    try {
        const response = await fetch(`${API_BASE}/api/analyze/resource-usage`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ course_id: currentCourseId })
        });
        
        const result = await response.json();
        
        if (result.success) {
            const data = result.data; // 这里拿到的是后端返回的字典
            
            // --- A. 构建深度报告 (新增部分) ---
            let reportHtml = '';
            if (data.analysis_text) {
                // 使用 <pre> 标签保留后端的换行格式，并加点样式美化
                reportHtml = `
                    <div style="background: #f8f9fa; border-left: 5px solid #17a2b8; padding: 15px; margin-bottom: 20px; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                        <h4 style="margin-top: 0; color: #0c5460; border-bottom: 1px solid #ddd; padding-bottom: 10px;">📊 AI 深度洞察</h4>
                        <pre style="white-space: pre-wrap; font-family: inherit; color: #333; margin: 0; font-size: 14px; line-height: 1.6;">${data.analysis_text}</pre>
                    </div>
                `;
            }

            // --- B. 构建基础统计 ---
            // 尝试读取新加的字段 zero_view_count 等，如果没有则不显示
            const zeroViewHtml = data.zero_view_count !== undefined 
                ? `<span style="margin-left: 15px; color: #dc3545;">(⚠️ 僵尸资源: ${data.zero_view_count}个)</span>` 
                : '';

            const statsHtml = `
                <div style="margin-bottom: 15px; font-size: 15px;">
                    <p><strong>总资源数:</strong> ${data.total_resources}</p>
                    <p><strong>已使用资源数:</strong> ${data.used_resources} ${zeroViewHtml}</p>
                </div>
                <h4 style="margin-top: 20px;">资源热度排行:</h4>
            `;

            // --- C. 构建列表 ---
            let listHtml = '<ul style="list-style: none; padding-left: 0;">';
            
            // 显示前 50 条，避免页面太长
            const listData = data.resource_usage ? data.resource_usage.slice(0, 50) : [];
            
            listData.forEach((item, index) => {
                // 根据类型给个小图标
                let icon = '📄';
                if (item.type && item.type.includes('视频')) icon = '🎬';
                if (item.type && item.type.includes('作业')) icon = '📝';
                
                // 给前三名加个高亮背景
                const bgStyle = index < 3 ? 'background-color: #fff3cd;' : 'background-color: #fff;';
                
                listHtml += `
                    <li style="${bgStyle} border: 1px solid #eee; margin-bottom: 8px; padding: 10px; border-radius: 4px;">
                        <div style="font-weight: bold; color: #333;">${index + 1}. ${icon} ${item.title}</div>
                        <div style="font-size: 12px; color: #666; margin-top: 4px;">
                            类型: ${item.type || '未知'} | 
                            浏览: <span style="color: #007bff; font-weight: bold;">${item.views}</span> | 
                            下载: ${item.downloads || 0} | 
                            使用人数: ${item.students_count} | 
                            <span style="color: #d63384;">综合热度: ${item.popularity}</span>
                        </div>
                    </li>`;
            });
            listHtml += '</ul>';

            // --- D. 渲染到页面 ---
            resultBox.innerHTML = reportHtml + statsHtml + listHtml;
            
        } else {
            resultBox.innerHTML = `<div style="color: red;">分析失败: ${result.error}</div>`;
        }
    } catch (error) {
        console.error(error);
        resultBox.innerHTML = `<div style="color: red;">网络错误: ${error.message}</div>`;
    }
}

// 发送消息
let currentLoadingMessageId = null;

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const question = input.value.trim();
    
    if (!question || !currentCourseId) return;
    
    // 防止重复发送
    if (currentLoadingMessageId) {
        console.log('[WARN] 已有请求正在处理，请等待...');
        return;
    }
    
    // 显示用户消息
    addMessage('user', question);
    input.value = '';
    
    // 清除之前的加载状态（如果有）
    clearLoadingMessage();
    
    // 显示加载状态
    currentLoadingMessageId = addMessage('assistant', '正在思考...', true);
    
    try {
        const response = await fetch(`${API_BASE}/api/course/${currentCourseId}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ question: question })
        });
        
        const result = await response.json();
        
        // 确保移除加载消息
        clearLoadingMessage();
        
        if (result.success) {
            addMessage('assistant', result.data.answer);
        } else {
            addMessage('assistant', '抱歉，处理您的问题时出错: ' + result.error);
        }
    } catch (error) {
        // 确保移除加载消息
        clearLoadingMessage();
        addMessage('assistant', '网络错误: ' + error.message);
    }
}

// 清除加载消息
function clearLoadingMessage() {
    if (currentLoadingMessageId) {
        const loadingMsg = document.getElementById(currentLoadingMessageId);
        if (loadingMsg) {
            loadingMsg.remove();
        }
        currentLoadingMessageId = null;
    }
    
    // 额外清除：移除所有包含"正在思考..."的消息（防止遗留）
    const messagesContainer = document.getElementById('chat-messages');
    if (messagesContainer) {
        const allMessages = messagesContainer.querySelectorAll('.message.assistant');
        allMessages.forEach(msg => {
            const bubble = msg.querySelector('.message-bubble');
            if (bubble && (bubble.textContent.includes('正在思考') || bubble.querySelector('.loading'))) {
                msg.remove();
            }
        });
    }
}

// 添加消息
function addMessage(type, content, isLoading = false) {
    const messagesContainer = document.getElementById('chat-messages');
    if (!messagesContainer) return null;
    
    // 确保唯一ID（使用时间戳+随机数）
    const messageId = 'msg-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    messageDiv.id = messageId;
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    if (isLoading) {
        bubble.innerHTML = '<div class="loading"></div> <span>' + content + '</span>';
    } else {
        // 支持 Markdown 与换行
        if (window.marked) {
            bubble.innerHTML = marked.parse(content);
        } else {
            bubble.innerHTML = content.replace(/\n/g, '<br>');
        }
    }
    
    messageDiv.appendChild(bubble);
    
    if (!isLoading) {
        const time = document.createElement('div');
        time.className = 'message-time';
        time.textContent = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        messageDiv.appendChild(time);
    }
    
    messagesContainer.appendChild(messageDiv);
    // 滚动到底部
    setTimeout(() => {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }, 10);
    
    return messageId;
}

// 切换选项卡
function switchTab(tabName) {
    // 更新按钮状态
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.tab === tabName) {
            btn.classList.add('active');
        }
    });

    // 更新内容显示
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
        if (content.id === `tab-${tabName}`) {
            content.classList.add('active');
        }
    });

    currentTab = tabName;
    updateAssistantContext();
}

function updateAssistantContext() {
    const contextEl = document.getElementById('assistant-context');
    if (!contextEl) return;

    if (!currentCourseId) {
        contextEl.textContent = '当前未选择课程';
        return;
    }

    const courseName = document.getElementById('course-name')?.textContent || '当前课程';
    contextEl.textContent = `当前课程：${courseName} ｜ 分析视角：${getTabLabel(currentTab)}`;
}

function getTabLabel(tab) {
    const map = {
        overview: '概览',
        student: '学生表现',
        resources: '资源使用',
        attendance: '考勤与课堂行为',
        exams: '考试与成绩',
        chat: 'AI 助手'
    };
    return map[tab] || '概览';
}

// 显示错误
function showError(message) {
    alert('错误: ' + message);
}


