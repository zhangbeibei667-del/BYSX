"""初始化默认管理员账号。
运行：  python -m server.init_admin
首次部署时必须执行，或在 API 启动时自动检测。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

try:
    from .config import get_store
    from .auth import hash_password
except ImportError:
    from config import get_store
    from auth import hash_password


def ensure_admin(username: str = "admin", password: str = "admin123",
                 role: str = "admin") -> None:
    """确保至少有一个管理员账号存在。"""
    store = get_store()
    existing = store.get_user_by_username(username)
    if existing:
        print(f"[auth] 管理员 {username} 已存在，跳过创建")
        return
    store.create_user(username, hash_password(password), role)
    print(f"[auth] 已创建默认管理员: {username} / {password}（请登录后修改密码）")


if __name__ == "__main__":
    ensure_admin()
