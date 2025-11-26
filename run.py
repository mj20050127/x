"""
快速启动脚本 - 用于快速启动AI教学分析助手
"""

import os
import sys
from pathlib import Path

def check_dependencies():
    """检查依赖是否已安装"""
    try:
        import flask
        import flask_cors
        print("✅ 依赖检查通过")
        return True
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请运行: pip install -r requirements.txt")
        return False

def check_data_dir():
    """检查数据目录是否存在"""
    data_dir = Path('SHUISHAN-CLAD')
    if not data_dir.exists():
        print(f"⚠️  数据目录 {data_dir} 不存在")
        print("请确保SHUISHAN-CLAD目录存在并包含教学行为数据JSON文件")
        return False
    
    json_files = list(data_dir.glob('*.json'))
    json_files = [f for f in json_files if '_cleaned' not in f.name]
    
    if len(json_files) == 0:
        print(f"⚠️  数据目录 {data_dir} 中没有找到JSON文件")
        return False
    
    print(f"✅ 找到 {len(json_files)} 个数据文件")
    return True

def main():
    """主函数"""
    print("=" * 60)
    print("🎓 AI教学分析助手 - 启动检查")
    print("=" * 60)
    
    # 检查依赖
    print("\n1. 检查依赖...")
    if not check_dependencies():
        sys.exit(1)
    
    # 检查数据目录
    print("\n2. 检查数据目录...")
    if not check_data_dir():
        print("⚠️  数据目录检查失败,但可以继续启动服务")
    
    # 创建必要的目录
    print("\n3. 创建必要的目录...")
    Path('cleaned_data').mkdir(exist_ok=True)
    Path('static').mkdir(exist_ok=True)
    print("✅ 目录创建完成")
    
    # 启动服务
    print("\n4. 启动服务...")
    print("=" * 60)
    print("🚀 服务启动中...")
    print("📁 数据目录: SHUISHAN-CLAD/")
    print("🌐 访问地址: http://localhost:5000")
    print("=" * 60)
    print("\n按 Ctrl+C 停止服务\n")
    
    # 导入并启动Flask应用
    from app import app
    app.run(host='0.0.0.0', port=5000, debug=True)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 服务已停止")
        sys.exit(0)

