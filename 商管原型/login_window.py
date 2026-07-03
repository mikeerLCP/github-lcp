"""
登录窗口 — 集团/子公司账号密码登录
登录成功后返回用户信息 dict：{"用户名", "角色", "所属项目"}
"""
import tkinter as tk
from tkinter import ttk, messagebox
import pymysql
import hashlib

# ── 数据库连接配置（与 db.py 一致）──────────────────────────────────────────────
DB_CONFIG = dict(
    host="127.0.0.1",
    port=3306,
    user="root",
    password="adminhang",
    database="xiaoniu_shangguan",
    charset="utf8mb4"
)


def _hash_pwd(pwd: str) -> str:
    """简单密码哈希（与存储一致即可）"""
    return hashlib.md5(pwd.encode("utf-8")).hexdigest()


def verify_user(username: str, password: str):
    """
    验证用户名密码（密码用 MD5 哈希后与数据库存储的哈希值比较），
    返回用户信息 dict 或 None
    """
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cur = conn.cursor()
        pwd_hash = _hash_pwd(password)
        cur.execute(
            "SELECT 用户名, 角色, 所属项目 FROM users WHERE 用户名=%s AND 密码=%s",
            (username, pwd_hash)
        )
        row = cur.fetchone()
        conn.close()
        if row:
            return {"用户名": row[0], "角色": row[1], "所属项目": row[2] or ""}
        return None
    except Exception as e:
        print(f"登录验证错误: {e}")
        return None


# ── 登录窗口（独立 Tk 实例，不依赖外部 parent）───────────────────────────────────
class LoginWindow:
    def __init__(self):
        self.result = None
        self.root = tk.Tk()
        self.root.title("LCP商管系统 — 登录")
        self.root.geometry("360x240")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_widgets()

        # 居中显示
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth()  - 360) // 2
        y = (self.root.winfo_screenheight() - 240) // 2
        self.root.geometry(f"360x240+{x}+{y}")

    def _build_widgets(self):
        f = ttk.Frame(self.root, padding=30)
        f.pack(fill="both", expand=True)

        ttk.Label(f, text="LCP商管系统", font=("黑体", 16, "bold")).pack(pady=(0, 20))

        # 用户名
        row1 = ttk.Frame(f)
        row1.pack(fill="x", pady=6)
        ttk.Label(row1, text="用户名：", width=8).pack(side="left")
        self.user_var = tk.StringVar()
        user_entry = ttk.Entry(row1, textvariable=self.user_var, width=22)
        user_entry.pack(side="left", fill="x", expand=True)

        # 密码
        row2 = ttk.Frame(f)
        row2.pack(fill="x", pady=6)
        ttk.Label(row2, text="密  码：", width=8).pack(side="left")
        self.pwd_var = tk.StringVar()
        pwd_entry = ttk.Entry(row2, textvariable=self.pwd_var, width=22, show="*")
        pwd_entry.pack(side="left", fill="x", expand=True)

        # 提示
        self.hint_var = tk.StringVar()
        ttk.Label(f, textvariable=self.hint_var, foreground="#c0392b", font=("微软雅黑", 8)).pack(pady=(4, 0))

        # 按钮
        btn_frame = ttk.Frame(f)
        btn_frame.pack(fill="x", pady=(16, 0))
        ttk.Button(btn_frame, text="登  录", command=self._do_login, width=12).pack(side="left", padx=20)
        ttk.Button(btn_frame, text="退  出", command=self._on_close, width=12).pack(side="right", padx=20)

        # 回车绑定
        user_entry.bind("<Return>", lambda _: pwd_entry.focus())
        pwd_entry.bind("<Return>", lambda _: self._do_login())
        user_entry.focus()

    def _do_login(self):
        username = self.user_var.get().strip()
        password = self.pwd_var.get()

        if not username or not password:
            self.hint_var.set("请输入用户名和密码")
            return

        user_info = verify_user(username, password)
        if user_info is None:
            self.hint_var.set("用户名或密码错误")
            self.pwd_var.set("")
            return

        self.result = user_info
        self.root.quit()       # 退出 mainloop

    def _on_close(self):
        self.result = None
        self.root.quit()       # 退出 mainloop

    def run(self):
        """运行登录窗口，阻塞等待结果，返回用户信息 dict 或 None"""
        self.root.mainloop()
        self.root.destroy()
        return self.result


# ── 便捷函数：直接弹出登录窗口 ───────────────────────────────────────────────────
def popup_login():
    """
    弹出登录窗口（独立 Tk 实例），返回用户信息 dict，取消/关闭返回 None
    """
    login = LoginWindow()
    return login.run()


# ── 独立测试 ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    user = popup_login()
    if user:
        print("登录成功：", user)
    else:
        print("登录取消")
