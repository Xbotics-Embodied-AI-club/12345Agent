import importlib
import platform
import sqlite3
import sys

# 检查清单与 backend/requirements.txt 对齐（导入名可能与 pip 包名不同，如
# python-dotenv -> dotenv、python-multipart -> multipart、rank-bm25 -> rank_bm25）。
# 注意：本项目 RAG 使用 chromadb（langchain-chroma），不使用 qdrant_client；
# 测试均为同步用例，不依赖 pytest_asyncio。
MODULES = [
    # Agent、数据结构与配置
    "langgraph",
    "langgraph.checkpoint.sqlite",
    "langchain",
    "pydantic",
    "pydantic_settings",
    "dotenv",
    "tenacity",
    "orjson",
    "aiosqlite",
    # Excel 与业务数据处理
    "pandas",
    "openpyxl",
    # 后端 API
    "fastapi",
    "uvicorn",
    "multipart",
    # 大模型：OpenAI 或兼容接口
    "openai",
    "langchain_openai",
    # 录音转写
    "faster_whisper",
    # RAG 与检索
    "chromadb",
    "langchain_chroma",
    "torch",
    "sentence_transformers",
    "rank_bm25",
    # LangChain 文档加载与分片
    "langchain_community",
    "langchain_text_splitters",
    "pypdf",
    "docx2txt",
    "bs4",
    # 快速演示界面
    "streamlit",
    # 测试
    "pytest",
    "httpx",
]

print("Python:", sys.version)
print("System:", platform.platform())
print("SQLite:", sqlite3.sqlite_version)

failed = []
for name in MODULES:
    try:
        importlib.import_module(name)
        print(f"[OK] {name}")
    except Exception as exc:
        failed.append(name)
        print(f"[FAIL] {name}: {exc}")

if failed:
    raise SystemExit(f"Environment check failed: {failed}")

print("Environment check passed.")
