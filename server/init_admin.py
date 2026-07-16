"""初始化默认管理员账号。
运行：  python -m server.init_admin
首次部署时必须执行，或在 API 启动时自动检测。
"""
import sys
import os
import secrets

sys.path.insert(0, os.path.dirname(__file__))

try:
    from .config import get_store
    from .auth import hash_password
except ImportError:
    from config import get_store
    from auth import hash_password


def _initial_password() -> tuple[str, str | None]:
    configured = os.getenv("ADMIN_PASSWORD", "").strip()
    if configured:
        return configured, None
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "data", ".admin_initial_password")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip(), path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    password = secrets.token_urlsafe(18)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(password)
    return password, path


def ensure_admin(username: str | None = None, password: str | None = None,
                 role: str = "admin") -> None:
    """确保至少有一个管理员账号存在。"""
    username = username or os.getenv("ADMIN_USERNAME", "admin")
    generated_path = None
    if password is None:
        password, generated_path = _initial_password()
    store = get_store()
    existing = store.get_user_by_username(username)
    if existing:
        print(f"[auth] 管理员 {username} 已存在，跳过创建")
        return
    store.create_user(username, hash_password(password), role)
    if generated_path:
        print(f"[auth] 已创建管理员 {username}；初始密码保存在 {generated_path}")
    else:
        print(f"[auth] 已按环境变量创建管理员 {username}")


if __name__ == "__main__":
    ensure_admin()
