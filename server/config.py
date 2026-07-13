import os

try:
    from .store_base import GraphStore
except ImportError:
    from store_base import GraphStore

# STORE_BACKEND = memory | mysql | neo4j | hybrid (MySQL + Neo4j 双写)
STORE_BACKEND = os.getenv("STORE_BACKEND", "hybrid")

# Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "Qaz123456")

# MySQL
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "Qaz123456")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "tcm")

# MySQL 连接串（供组员 SQL Agent 直连或你自己的管理工具）
MYSQL_DSN = os.getenv(
    "MYSQL_DSN",
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}",
)

# JWT
JWT_SECRET = os.getenv("JWT_SECRET", "tcm-kg-jwt-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

# Memory（回退用, 生产不推荐）
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.getenv("DATA_FILE", os.path.join(_ROOT, "data", "store.json"))

_store: GraphStore | None = None


def get_store() -> GraphStore:
    """全局单例。FastAPI 依赖注入和 graph_tools 都从这里拿。"""
    global _store
    if _store is None:
        if STORE_BACKEND == "neo4j":
            try:
                from .store_neo4j import Neo4jStore
            except ImportError:
                from store_neo4j import Neo4jStore
            _store = Neo4jStore(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        elif STORE_BACKEND == "mysql":
            try:
                from .store_mysql import MySQLStore
            except ImportError:
                from store_mysql import MySQLStore
            _store = MySQLStore(MYSQL_HOST, MYSQL_PORT, MYSQL_USER,
                                MYSQL_PASSWORD, MYSQL_DATABASE)
        elif STORE_BACKEND == "hybrid":
            try:
                from .store_mysql import MySQLStore
                from .store_neo4j import Neo4jStore
                from .store_hybrid import HybridStore
            except ImportError:
                from store_mysql import MySQLStore
                from store_neo4j import Neo4jStore
                from store_hybrid import HybridStore
            mysql = MySQLStore(MYSQL_HOST, MYSQL_PORT, MYSQL_USER,
                               MYSQL_PASSWORD, MYSQL_DATABASE)
            neo4j = Neo4jStore(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
            _store = HybridStore(mysql, neo4j)
        else:
            try:
                from .store_memory import MemoryStore
            except ImportError:
                from store_memory import MemoryStore
            _store = MemoryStore(DATA_FILE)
    return _store
