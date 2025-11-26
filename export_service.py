"""
数据导出服务模块 - 支持导出为Excel、PDF、CSV等格式
"""

import json
import csv
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 注册中文字体 - 使用系统默认字体或fallback
_chinese_font_name = None
try:
    # 尝试注册SimSun(宋体) - Windows系统常见字体
    if os.name == 'nt':  # Windows
        font_paths = [
            ('C:/Windows/Fonts/simsun.ttc', 'SimSun'),
            ('C:/Windows/Fonts/simhei.ttf', 'SimHei'),
            ('C:/Windows/Fonts/msyh.ttc', 'MicrosoftYaHei'),
            ('C:/Windows/Fonts/simkai.ttf', 'SimKai')
        ]
        font_registered = False
        for font_path, font_name in font_paths:
            if os.path.exists(font_path):
                try:
                    if font_path.endswith('.ttc'):
                        # TTC文件需要指定字体索引
                        pdfmetrics.registerFont(TTFont(font_name, font_path, subfontIndex=0))
                    else:
                        pdfmetrics.registerFont(TTFont(font_name, font_path))
                    _chinese_font_name = font_name
                    font_registered = True
                    print(f"[OK] 成功注册中文字体: {font_name}")
                    break
                except Exception as e:
                    continue
        if not font_registered:
            # 如果没有找到字体，使用默认字体，但会有乱码问题
            print("[WARN] 未找到中文字体，PDF中文可能显示为方框")
    else:
        # Linux/Mac系统 - 尝试查找常见的中文字体
        linux_font_paths = [
            ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'DejaVuSans'),
            ('/System/Library/Fonts/STHeiti Light.ttc', 'STHeiti')
        ]
        font_registered = False
        for font_path, font_name in linux_font_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                    _chinese_font_name = font_name
                    font_registered = True
                    break
                except:
                    continue
        if not font_registered:
            print("[INFO] 非Windows系统，使用默认字体")
except Exception as e:
    print(f"[WARN] 字体注册失败: {e}, PDF中文可能显示异常")


class ExportService:
    """数据导出服务类"""
    
    def __init__(self, output_dir='exports'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def export_to_excel(self, data, filename=None, sheet_name='数据'):
        """导出数据为Excel格式"""
        if filename is None:
            filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        filepath = self.output_dir / filename
        
        # 处理统计数据
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            if isinstance(data, dict):
                # 1. 课程概览统计
                if 'overview' in data:
                    overview = data['overview']
                    overview_flat = {
                        'course_name': overview.get('course_name', ''),
                        'resource_count': overview.get('resource_count', 0),
                        'total_students': overview.get('total_students', 0),
                        'video_count': overview.get('video_count', 0),
                        'homework_count': overview.get('homework_count', 0),
                        'exam_count': overview.get('exam_count', 0),
                        'attendance_count': overview.get('attendance_count', 0)
                    }
                    df_overview = pd.DataFrame([overview_flat])
                    df_overview.to_excel(writer, sheet_name='课程概览', index=False)
                
                # 2. 资源使用统计
                if 'resource_usage' in data:
                    df_usage = pd.DataFrame(data['resource_usage'])
                    df_usage.to_excel(writer, sheet_name='资源使用统计', index=False)
                
                # 3. 按周次统计
                if 'week_stats' in data:
                    week_stats = data['week_stats']
                    week_data = []
                    for week, stats in week_stats.items():
                        week_data.append({
                            '周次': week,
                            '资源数': stats.get('resources', 0),
                            '视频数': stats.get('videos', 0),
                            '作业数': stats.get('homeworks', 0)
                        })
                    if week_data:
                        df_week = pd.DataFrame(week_data)
                        df_week.to_excel(writer, sheet_name='按周次统计', index=False)
                
                # 4. 详细资源列表（从overview中的resource_types展开）
                if 'overview' in data and 'resource_types' in data['overview']:
                    all_resources = []
                    for resource_type, resources in data['overview']['resource_types'].items():
                        for resource in resources:
                            all_resources.append({
                                '资源类型': resource_type,
                                '资源标题': resource.get('title', ''),
                                '资源ID': resource.get('resource_id', ''),
                                '浏览次数': resource.get('view_times', 0),
                                '下载次数': resource.get('download_times', 0),
                                '教学周次': resource.get('teaching_week', '')
                            })
                    if all_resources:
                        df_resources = pd.DataFrame(all_resources)
                        df_resources.to_excel(writer, sheet_name='资源详情', index=False)
            elif isinstance(data, list):
                df = pd.DataFrame(data)
                df.to_excel(writer, sheet_name=sheet_name, index=False)
            else:
                # 尝试展平字典
                try:
                    df = pd.json_normalize(data)
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                except:
                    df = pd.DataFrame([{'数据': str(data)}])
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        return str(filepath)
    
    def export_to_csv(self, data, filename=None):
        """导出数据为CSV格式"""
        if filename is None:
            filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        filepath = self.output_dir / filename
        
        # 转换为DataFrame，优先展开资源详情
        if isinstance(data, dict):
            # 优先导出详细资源列表
            if 'overview' in data and 'resource_types' in data['overview']:
                all_resources = []
                for resource_type, resources in data['overview']['resource_types'].items():
                    for resource in resources:
                        all_resources.append({
                            '资源类型': resource_type,
                            '资源标题': resource.get('title', ''),
                            '资源ID': resource.get('resource_id', ''),
                            '浏览次数': resource.get('view_times', 0),
                            '下载次数': resource.get('download_times', 0),
                            '教学周次': resource.get('teaching_week', '')
                        })
                if all_resources:
                    df = pd.DataFrame(all_resources)
                elif 'resource_usage' in data:
                    df = pd.DataFrame(data['resource_usage'])
                elif 'overview' in data:
                    # 展开overview，但不包含resource_types（已经在上面处理）
                    overview = data['overview'].copy()
                    overview.pop('resource_types', None)
                    overview.pop('resource_stats', None)
                    df = pd.DataFrame([overview])
                else:
                    try:
                        df = pd.json_normalize(data)
                    except:
                        df = pd.DataFrame([data])
            elif 'resource_usage' in data:
                df = pd.DataFrame(data['resource_usage'])
            elif 'overview' in data:
                overview = data['overview'].copy()
                overview.pop('resource_types', None)
                overview.pop('resource_stats', None)
                df = pd.DataFrame([overview])
            elif 'resources' in data:
                df = pd.DataFrame(data['resources'])
            else:
                try:
                    df = pd.json_normalize(data)
                except:
                    df = pd.DataFrame([data])
        elif isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            df = pd.DataFrame([data])
        
        # 写入CSV
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        return str(filepath)
    
    def export_to_pdf(self, course_data, analysis_data, filename=None):
        """导出课程分析报告为PDF格式"""
        if filename is None:
            filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        filepath = self.output_dir / filename
        
        # 创建PDF文档
        doc = SimpleDocTemplate(str(filepath), pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        # 尝试设置中文字体
        chinese_font = _chinese_font_name if _chinese_font_name else 'Helvetica'
        if chinese_font != 'Helvetica':
            try:
                # 检查字体是否已注册
                pdfmetrics.getFont(chinese_font)
            except:
                # 如果没有注册成功，使用默认字体
                chinese_font = 'Helvetica'
                print("[WARN] 字体注册检查失败，使用默认字体，中文可能显示异常")
        else:
            print("[WARN] 未找到中文字体，使用默认字体，中文可能显示为方框")
        
        # 标题样式
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            fontName=chinese_font,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=30,
            alignment=1  # 居中
        )
        
        # 创建自定义样式，支持中文
        normal_style = ParagraphStyle(
            'NormalChinese',
            parent=styles['Normal'],
            fontName=chinese_font,
            fontSize=10,
            leading=14
        )
        
        heading2_style = ParagraphStyle(
            'Heading2Chinese',
            parent=styles['Heading2'],
            fontName=chinese_font,
            fontSize=14,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=12
        )
        
        # 添加标题
        course_name = course_data.get('course_name', '课程分析报告')
        story.append(Paragraph(course_name, title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # 添加课程信息
        story.append(Paragraph("<b>课程基本信息</b>", heading2_style))
        info_data = [
            ['课程ID', course_data.get('course_id', '-')],
            ['课程名称', course_data.get('course_name', '-')],
            ['创建时间', course_data.get('create_time', '-')],
            ['更新时间', course_data.get('update_time', '-')],
            ['点赞数', str(course_data.get('liked', 0))],
            ['浏览数', str(course_data.get('viewed', 0))]
        ]
        
        info_table = Table(info_data, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f5f7fa')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), chinese_font if chinese_font != 'Helvetica' else 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), chinese_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 0.3*inch))
        
        # 添加统计分析
        if 'overview' in analysis_data:
            story.append(Paragraph("<b>统计分析</b>", heading2_style))
            stats = analysis_data['overview']
            stats_data = [
                ['指标', '数值'],
                ['学生人数', str(stats.get('total_students', 0))],
                ['学习资源数', str(stats.get('resource_count', 0))],
                ['视频观看次数', str(stats.get('video_count', 0))],
                ['作业提交次数', str(stats.get('homework_count', 0))],
                ['考试次数', str(stats.get('exam_count', 0))],
                ['考勤次数', str(stats.get('attendance_count', 0))]
            ]
            
            stats_table = Table(stats_data, colWidths=[3*inch, 3*inch])
            stats_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), chinese_font if chinese_font != 'Helvetica' else 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), chinese_font),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f7fa')])
            ]))
            
            story.append(stats_table)
            story.append(Spacer(1, 0.3*inch))
        
        # 添加资源使用情况
        if 'resource_usage' in analysis_data:
            story.append(Paragraph("<b>资源使用情况</b>", heading2_style))
            resources = analysis_data['resource_usage'][:10]  # 只显示前10个
            
            resource_data = [['类型', '数量', '浏览次数', '下载次数']]
            for r in resources:
                resource_data.append([
                    r.get('type', '-'),
                    str(r.get('count', 0)),
                    str(r.get('total_views', 0)),
                    str(r.get('total_downloads', 0))
                ])
            
            resource_table = Table(resource_data, colWidths=[1.5*inch, 1*inch, 1.5*inch, 1.5*inch])
            resource_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#283593')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), chinese_font if chinese_font != 'Helvetica' else 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), chinese_font),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f7fa')])
            ]))
            
            story.append(resource_table)
        
        # 添加生成时间
        story.append(Spacer(1, 0.2*inch))
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        story.append(Paragraph(f"<i>报告生成时间: {timestamp}</i>", normal_style))
        
        # 生成PDF
        doc.build(story)
        
        return str(filepath)
    
    def export_course_statistics(self, course_data, analysis_data, format='excel'):
        """导出课程统计数据"""
        if format.lower() == 'excel':
            return self.export_to_excel(analysis_data, 
                                      f"course_{course_data.get('course_id', 'unknown')}_{datetime.now().strftime('%Y%m%d')}.xlsx")
        elif format.lower() == 'csv':
            return self.export_to_csv(analysis_data,
                                    f"course_{course_data.get('course_id', 'unknown')}_{datetime.now().strftime('%Y%m%d')}.csv")
        elif format.lower() == 'pdf':
            return self.export_to_pdf(course_data, analysis_data,
                                     f"report_{course_data.get('course_id', 'unknown')}_{datetime.now().strftime('%Y%m%d')}.pdf")
        else:
            raise ValueError(f"不支持的格式: {format}")

