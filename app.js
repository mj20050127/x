// 全局变量
let currentCourseId = null;
let currentTab = 'overview';
let charts = {};
let currentView = 'course-center';   // 当前视图：课程中心 / 深度分析 / 设置 / 联系

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

function renderInsightPanel(title, text) {
    if (!text) return '';
    const formatted = text.replace(/\n/g, '<br>');

    return `
        <div class="insight-box">
            <div class="insight-box__header">
                <span class="insight-icon">🔍</span>
                <div>
                    <p class="eyebrow">AI 路径洞察报告</p>
                    <h5>${title}</h5>
                </div>
            </div>
            <div class="insight-box__body">
                <div class="insight-scroll">${formatted}</div>
            </div>
        </div>
    `;
}

// API基础URL
const API_BASE = window.location.origin;

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    loadCourses();
    setupEventListeners();
    switchView('course-center');
    setActiveNav('course-center');
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
    
    // 分类下拉切换
    document.getElementById('category-select')?.addEventListener('change', (e) => {
        currentCategory = e.target.value;
        const searchTerm = document.getElementById('course-search').value.trim();
        let courses = allCourses;

        if (searchTerm) {
            courses = allCourses.filter(course =>
                course.course_name.toLowerCase().includes(searchTerm.toLowerCase())
            );
        }

        displayCourses(courses, currentCategory);
    });

    // 排序
    document.getElementById('course-sort')?.addEventListener('change', (e) => {
        currentSort = e.target.value;
        displayCourses(allCourses, currentCategory);
    });

    // 左侧导航点击
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const view = item.dataset.view;
            if (!view) return;

            if (view === 'analysis' && !currentCourseId) {
                alert('请先在「课程中心」选择一门课程，再查看深度分析。');
                return;
            }

            switchView(view);
            setActiveNav(view);
        });
    });

    // 返回课程中心按钮
    const backBtn = document.getElementById('back-to-course-center');
    if (backBtn) {
        backBtn.addEventListener('click', () => {
            switchView('course-center');
            setActiveNav('course-center');
        });
    }
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

    // 排序
    if (currentSort === 'students') {
        filteredCourses.sort((a, b) => (b.student_count || 0) - (a.student_count || 0));
    } else if (currentSort === 'likes') {
        filteredCourses.sort((a, b) => (b.liked || 0) - (a.liked || 0));
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

            // 切换到深度分析视图
            switchView('analysis');
            setActiveNav('analysis');

            const detailEl = document.getElementById('course-detail');
            if (detailEl) {
                detailEl.scrollIntoView({ behavior: 'smooth' });
            }
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
    if (courseInfo.teacher) metaParts.push(`教师：${courseInfo.teacher}`);
    if (courseInfo.course_id) metaParts.push(`课程ID：${courseInfo.course_id}`);
    document.getElementById('course-meta').textContent = metaParts.join(' · ') || '课程基础信息加载中';

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

    const learningRecords = analysis.video_count
        || analysis.video_records
        || analysis.learning_records
        || courseInfo.video_count
        || defaultKpis.learning;

    const assignmentCount = analysis.homework_count
        || analysis.homework_submissions
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

// 构建图表数据（概览与详情共享）
function buildScatterData(analysis = {}) {
    const performanceList = analysis.student_details || analysis.top_students || [];

    return analysis.performance_points
        || (performanceList.length ? performanceList.map((student, index) => {
            const displayName = student.name
                || student.student_name
                || student.student_truename
                || student.student_id
                || `学生${index + 1}`;

            return [
                index + 1,
                student.avg_exam_score || student.avg_homework_score || 0,
                displayName
            ];
        }) : null)
        || Array.from({ length: 15 }, (_, i) => [i + 1, Math.round(Math.random() * 40) + 60, `学生${i + 1}`]);
}

function buildResourceBarData(analysis = {}) {
    // 优先使用资源使用分析结果
    if (Array.isArray(analysis.resource_usage) && analysis.resource_usage.length) {
        return analysis.resource_usage
            .map(item => ({
                name: item.title || item.name || '资源',
                value: Number(item.popularity) || Number(item.views) || Number(item.downloads) || 0
            }))
            .filter(item => item.name)
            .sort((a, b) => (b.value || 0) - (a.value || 0))
            .slice(0, 10);
    }

    // 兼容 compute_overview 返回的 resource_types/resource_stats
    const resourceStats = analysis.resource_stats || {};
    const resourceTypes = analysis.resource_types || {};
    const resourceList = Object.values(resourceTypes).flat().map(item => ({
        name: item.title || item.name || '资源',
        value: Number(item.view_times) || Number(item.download_times) || 0
    }));

    let barData = resourceList
        .filter(item => item.name)
        .sort((a, b) => (b.value || 0) - (a.value || 0))
        .slice(0, 10);

    if (barData.length === 0) {
        barData = Object.entries(resourceStats).map(([type, count]) => ({
            name: type || '资源',
            value: Number(count) || 0
        }));
    }

    return barData;
}

// 构建与更新 ECharts
function updateCharts(analysis = {}) {
    // 资源饼图：使用后端 compute_overview 提供的 resource_stats
    const resourceStats = analysis.resource_stats || {};
    const resourcePieData = Object.entries(resourceStats).map(([type, count]) => ({
        name: type || '资源',
        value: Number(count) || 0
    }));

    // 学习行为柱状：直接使用后端统计的真实计数
    const behaviorStats = {
        categories: ['出勤', '视频', '作业', '考试'],
        values: [
            Number(analysis.attendance_count) || 0,
            Number(analysis.video_count) || 0,
            Number(analysis.homework_count) || 0,
            Number(analysis.exam_count) || 0
        ]
    };

    renderResourcePie(resourcePieData);
    renderBehaviorChart(behaviorStats);
    renderScatterChart(buildScatterData(analysis));
    renderBarChart(buildResourceBarData(analysis));
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
            axisLine: { lineStyle: { color: 'rgba(15,23,42,0.2)' } },
            axisLabel: { color: '#6b7280' }
        },
        yAxis: {
            name: '成绩',
            axisLine: { lineStyle: { color: 'rgba(15,23,42,0.2)' } },
            axisLabel: { color: '#6b7280' },
            splitLine: { lineStyle: { color: 'rgba(15,23,42,0.08)' } }
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
            axisLabel: { color: '#6b7280', rotate: 25 }
        },
        yAxis: {
            type: 'value',
            axisLabel: { color: '#6b7280' },
            splitLine: { lineStyle: { color: 'rgba(15,23,42,0.08)' } }
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
                borderColor: '#f5f7fb',
                borderWidth: 2
            },
            label: { color: '#374151' },
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
            axisLabel: { color: '#6b7280' }
        },
        yAxis: {
            type: 'value',
            axisLabel: { color: '#6b7280' },
            splitLine: { lineStyle: { color: 'rgba(15,23,42,0.08)' } }
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
            let html = renderInsightPanel('AI 路径洞察报告', data.analysis_text);

            if (data.common_paths && data.common_paths.length > 0) {
                html += '<div class="path-card-list">';
                data.common_paths.forEach((path, index) => {
                    const pathTitles = path.path_titles || [];
                    const steps = pathTitles.map((title, idx) => {
                        const safeTitle = title || '未知资源';
                        return `<span class="step-chip">${safeTitle}</span>${idx < pathTitles.length - 1 ? '<span class="step-arrow">→</span>' : ''}`;
                    }).join('');

                    const examples = (path.examples || []).map(ex => ex.student_id?.slice(0, 8) || '学生').join('、');

                    html += `
                        <div class="path-card">
                            <div class="path-card__header">
                                <div class="path-index">#${index + 1}</div>
                                <div class="path-meta">
                                    <p class="path-title">典型路径</p>
                                    <p class="path-sub">${path.frequency || 0} 人 · ${path.percentage || 0}%</p>
                                </div>
                            </div>
                            <div class="path-steps">${steps || '<span class="muted">暂无资源节点</span>'}</div>
                            ${path.description ? `<p class="path-desc">${path.description}</p>` : ''}
                            ${examples ? `<p class="path-examples">示例学生：${examples}</p>` : ''}
                        </div>
                    `;
                });
                html += '</div>';
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
            let html = renderInsightPanel('AI 表现洞察', data.analysis_text);

            if (data.top_students && data.top_students.length > 0) {
                html += '<div class="stat-card-list">';
                data.top_students.forEach((student, index) => {
                    const homework = student.avg_homework_score > 0 ? `${student.avg_homework_score.toFixed(1)} 分` : '—';
                    const exam = student.avg_exam_score > 0 ? `${student.avg_exam_score.toFixed(1)} 分` : '—';
                    const displayName = student.name
                        || student.student_name
                        || student.student_truename
                        || student.student_id
                        || `学生${index + 1}`;

                    html += `
                        <div class="stat-card">
                            <div class="stat-rank">NO.${index + 1}</div>
                            <div class="stat-body">
                                <p class="stat-title">${displayName}</p>
                                <p class="stat-sub">作业均分 ${homework} ｜ 考试均分 ${exam}</p>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
            }

            resultBox.innerHTML = html || '<p>暂无数据</p>';

            // 学生表现散点图：使用后端的 student_details/top_students 更新详情页图表
            renderScatterChart(buildScatterData(data));
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
            let html = renderInsightPanel('AI 资源洞察', data.analysis_text);

            const zeroViewBadge = data.zero_view_count !== undefined
                ? `<span class="pill pill-warn">僵尸资源 ${data.zero_view_count}</span>`
                : '';

            html += `
                <div class="stat-card-list compact">
                    <div class="stat-card">
                        <div class="stat-rank">总量</div>
                        <div class="stat-body">
                            <p class="stat-title">资源总数</p>
                            <p class="stat-sub">${data.total_resources ?? '--'}</p>
                        </div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-rank">使用</div>
                        <div class="stat-body">
                            <p class="stat-title">已被访问</p>
                            <p class="stat-sub">${data.used_resources ?? '--'} ${zeroViewBadge}</p>
                        </div>
                    </div>
                </div>
                <h4 class="section-subtitle">资源热度排行</h4>
            `;

            const listData = data.resource_usage ? data.resource_usage.slice(0, 50) : [];
            if (listData.length) {
                html += '<div class="resource-list">';
                listData.forEach((item, index) => {
                    let icon = '📄';
                    if (item.type && item.type.includes('视频')) icon = '🎬';
                    if (item.type && item.type.includes('作业')) icon = '📝';

                    html += `
                        <div class="resource-card ${index < 3 ? 'highlight' : ''}">
                            <div class="resource-header">
                                <div class="resource-rank">${index + 1}</div>
                                <div class="resource-title">${icon} ${item.title || '未命名资源'}</div>
                            </div>
                            <div class="resource-meta">
                                <span>类型：${item.type || '未知'}</span>
                                <span>浏览：<strong>${item.views}</strong></span>
                                <span>下载：${item.downloads || 0}</span>
                                <span>使用人数：${item.students_count}</span>
                                <span class="muted">热度：${item.popularity}</span>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
            }

            resultBox.innerHTML = html || '<p>暂无数据</p>';

            // 资源热度柱状图：使用资源使用分析结果更新详情页图表
            renderBarChart(buildResourceBarData(data));

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

    // 智能判断是否为“报告类”长答案（例如学生成绩报告 / 课堂分析）
    const isReportLike =
        !isLoading &&
        type === 'assistant' &&
        (
            content.includes('成绩分析') ||
            content.includes('成绩报告') ||
            content.includes('学习路径') ||
            content.includes('分析报告') ||
            content.includes('【学生成绩分析报告】') ||
            content.split('\n').length >= 6  // 行数多时，也视为报告
        );

    if (isReportLike) {
        bubble.classList.add('report-bubble');
        messageDiv.classList.add('is-report');
    }

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
        time.textContent = new Date().toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
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

// ===== 导航视图切换 =====

function setActiveNav(view) {
    const items = document.querySelectorAll('.nav-item');
    items.forEach(btn => {
        if (btn.dataset.view === view) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

function switchView(view) {
    currentView = view;
    const moduleCourses = document.getElementById('module-courses');
    const courseDetail = document.getElementById('course-detail');
    const settingsPanel = document.getElementById('settings-panel');
    const contactPanel = document.getElementById('contact-panel');

    [moduleCourses, courseDetail, settingsPanel, contactPanel].forEach(el => {
        if (el) el.classList.add('hidden');
    });

    const heroTitle = document.querySelector('.hero h2');
    const heroSubtitle = document.querySelector('.hero .subtitle');

    if (view === 'course-center') {
        if (moduleCourses) moduleCourses.classList.remove('hidden');
        if (heroTitle) heroTitle.textContent = '课程中心';
        if (heroSubtitle) heroSubtitle.textContent = '先从课程列表中选择一门课程';
    } else if (view === 'analysis') {
        if (!currentCourseId) {
            alert('请先在「课程中心」选择一门课程');
            setActiveNav('course-center');
            if (moduleCourses) moduleCourses.classList.remove('hidden');
            return;
        }
        if (courseDetail) courseDetail.classList.remove('hidden');
        if (heroTitle) heroTitle.textContent = '课程深度分析';
        if (heroSubtitle) {
            const titleEl = document.getElementById('course-name');
            const title = titleEl ? titleEl.textContent : '';
            heroSubtitle.textContent = title ? `当前课程：${title}` : '基于教学行为数据的智能分析';
        }
    } else if (view === 'settings') {
        if (settingsPanel) settingsPanel.classList.remove('hidden');
        if (heroTitle) heroTitle.textContent = '系统设置';
        if (heroSubtitle) heroSubtitle.textContent = '配置教学分析参数与偏好';
    } else if (view === 'contact') {
        if (contactPanel) contactPanel.classList.remove('hidden');
        if (heroTitle) heroTitle.textContent = '联系我们';
        if (heroSubtitle) heroSubtitle.textContent = '有任何需求或反馈，欢迎联系教研团队';
    }
}

// 显示错误
function showError(message) {
    alert('错误: ' + message);
}


