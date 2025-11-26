"""
init_vectors.py
手动执行此脚本，将所有课程数据向量化并存入 ChromaDB
"""
import sys
import os

# [新增] 1. 导入 dotenv
try:
    from dotenv import load_dotenv
    # [新增] 2. 手动加载 .env 文件中的环境变量
    load_dotenv()
    print("[Init] 已加载环境变量")
except ImportError:
    print("[Init] 警告: 未安装 python-dotenv，尝试直接读取系统环境变量")

# 解决 Windows 下编码问题（可选）
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# 注意：DataProcessor 的导入必须在 load_dotenv 之后
# 这样 DataProcessor 内部初始化 RAGService 时才能读到 key
from data_processor import DataProcessor

def main():
    # 检查 Key 是否存在，提前报错
    if not os.getenv("OPENAI_API_KEY"):
        print("\n❌ 错误: 未读取到 OPENAI_API_KEY。")
        print("请确认项目根目录下有 .env 文件，且包含 OPENAI_API_KEY 配置。")
        return

    print("="*50)
    print("   开始构建向量数据库 (RAG Initialization)")
    print("="*50)

    # 初始化 DataProcessor，它会自动带起 RAGService
    dp = DataProcessor()
    
    # 调用我们在 DataProcessor 里新加的方法
    dp.refresh_all_vectors()

    print("\n" + "="*50)
    print("   ✅ 所有数据已处理完毕！")
    print("   现在请运行 python app.py 启动服务")
    print("="*50)

if __name__ == "__main__":
    main()