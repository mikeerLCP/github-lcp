"""
用户管理模块 — 集团角色专用
功能：查看用户列表、新增用户、修改密码、修改角色/项目、删除用户
"""
import tkinter as tk
from tkinter import ttk, messagebox
import pymysql
import hashlib

import utils

# ── 数据库连接配置（与 db.py / login_window.py 一致）─────────────────────────────
DB_CONFIG = dict(
    host="127.0.0.1",
    port=3306,
    user="root",
    password="adminhang",
    database="xiaoniu_shangguan",
    charset="utf8mb4"
)


def _hash_pwd(pwd: str) -> str:
    return hashlib.md5(pwd.encode("utf-8")).hexdigest()


def _get_conn():
    return pymysql.connect(**DB_CONFIG)


# ── 用户管理窗口 ──────────────────────────────────────────────────────────────────
class UserManageWindow:
    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("用户管理")
        self.window.geometry("600x450")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_widgets()

        self._sort_col = "用户名"
        self._sort_rev = True
        self._load_users()

        # 居中
        self.window.update_idletasks()
        w, h = 600, 450
        x = (self.window.winfo_screenwidth()  - w) // 2
        y = (self.window.winfo_screenheight() - h) // 2
        self.window.geometry(f"{w}x{h}+{x}+{y}")

    # ── 界面构建 ───────────────────────────────────────────────────────────────────
    def _build_widgets(self):
        main = ttk.Frame(self.window, padding=15)
        main.pack(fill="both", expand=True)

        # 标题
        ttk.Label(main, text="用户管理", font=("黑体", 14, "bold")).pack(anchor="w", pady=(0, 10))

        # ── 用户列表（Treeview）───────────────────────────────────────────────────
        list_frame = ttk.Frame(main)
        list_frame.pack(fill="both", expand=True)

        cols = ("用户名", "角色", "所属项目")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=10)
        for col in cols:
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=180, anchor="center")
        self.tree.tag_configure("even", background="#f7faff")
        self.tree.tag_configure("odd",  background="#ffffff")
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # ── 操作按钮 ──────────────────────────────────────────────────────────────
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x", pady=(12, 0))

        ttk.Button(btn_frame, text="新增用户", width=12, command=self._add_user).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="修改密码", width=12, command=self._change_pwd).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="修改角色/项目", width=14, command=self._change_role).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="删除用户", width=12, command=self._delete_user).pack(side="left", padx=4)
        ttk.Separator(btn_frame, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(btn_frame, text="📋 查看日志", width=12, command=self._open_log_viewer).pack(side="left", padx=4)

        # ── 状态栏 ────────────────────────────────────────────────────────────────
        self.status_var = tk.StringVar(value="请选择用户后操作")
        ttk.Label(main, textvariable=self.status_var, foreground="#888888", font=("微软雅黑", 8)).pack(anchor="w", pady=(8, 0))

    def _sort_by(self, col):
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            self._sort_rev = True
        self._load_users()

    # ── 数据加载 ─────────────────────────────────────────────────────────────────
    def _load_users(self):
        """从 users 表加载用户列表"""
        try:
            conn = _get_conn()
            cur = conn.cursor()
            cur.execute("SELECT 用户名, 角色, 所属项目 FROM users")
            rows = list(cur.fetchall())
            conn.close()

            # 本地排序
            col_idx = {"用户名": 0, "角色": 1, "所属项目": 2}.get(self._sort_col, 0)
            rows.sort(key=lambda r: str(r[col_idx] or ""), reverse=self._sort_rev)

            self.tree.delete(*self.tree.get_children())
            for i, row in enumerate(rows):
                tag = "even" if i % 2 == 0 else "odd"
                self.tree.insert("", "end", values=(row[0], row[1], row[2] or ""), tags=(tag,))
        except Exception as e:
            messagebox.showerror("错误", f"加载用户列表失败：\n{e}")

    # ── 选择事件 ─────────────────────────────────────────────────────────────────
    def _on_select(self, _event):
        sel = self.tree.selection()
        if sel:
            vals = self.tree.item(sel[0])["values"]
            self.status_var.set(f"已选择：{vals[0]}  ({vals[1]})")
        else:
            self.status_var.set("请选择用户后操作")

    def _get_selected_user(self):
        """获取当前选中的用户名，未选中则提示"""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择用户")
            return None
        return self.tree.item(sel[0])["values"][0]

    # ── 新增用户 ─────────────────────────────────────────────────────────────────
    def _add_user(self):
        self._open_edit_window(mode="add")

    # ── 修改密码 ─────────────────────────────────────────────────────────────────
    def _change_pwd(self):
        username = self._get_selected_user()
        if username is None:
            return
        self._open_pwd_window(username)

    # ── 修改角色/项目 ────────────────────────────────────────────────────────────
    def _change_role(self):
        username = self._get_selected_user()
        if username is None:
            return
        self._open_edit_window(mode="edit", username=username)

    # ── 删除用户 ─────────────────────────────────────────────────────────────────
    def _delete_user(self):
        username = self._get_selected_user()
        if username is None:
            return

        # 不能删自己
        if username == utils.CURRENT_USER.get("用户名"):
            messagebox.showwarning("提示", "不能删除当前登录账号")
            return

        if not messagebox.askyesno("确认删除", f"确定要删除用户「{username}」吗？\n删除后无法恢复。"):
            return

        try:
            conn = _get_conn()
            cur = conn.cursor()
            cur.execute("DELETE FROM users WHERE 用户名=%s", (username,))
            conn.commit()
            conn.close()
            utils.log_operation("删除", "用户", f"删除用户 {username}", username)
            self.status_var.set(f"已删除用户：{username}")
            self._load_users()
        except Exception as e:
            messagebox.showerror("错误", f"删除失败：\n{e}")

    # ── 新增/编辑弹窗 ────────────────────────────────────────────────────────────
    def _open_edit_window(self, mode, username=None):
        """
        mode="add"  → 新增用户
        mode="edit" → 修改角色/项目（用户名不可改）
        """
        win = tk.Toplevel(self.window)
        win.title("新增用户" if mode == "add" else "修改角色/项目")
        win.geometry("360x280")
        win.resizable(False, False)
        win.transient(self.window)
        win.grab_set()

        f = ttk.Frame(win, padding=25)
        f.pack(fill="both", expand=True)

        # 用户名
        ttk.Label(f, text="用户名：").grid(row=0, column=0, sticky="e", pady=8)
        user_var = tk.StringVar(value=username or "")
        user_entry = ttk.Entry(f, textvariable=user_var, width=22,
                                state="normal" if mode == "add" else "disabled")
        user_entry.grid(row=0, column=1, sticky="w", pady=8, padx=(8, 0))
        if mode == "add":
            user_entry.focus()

        # 密码（仅新增时显示）
        pwd_var = tk.StringVar()
        if mode == "add":
            ttk.Label(f, text="密  码：").grid(row=1, column=0, sticky="e", pady=8)
            pwd_entry = ttk.Entry(f, textvariable=pwd_var, width=22, show="*")
            pwd_entry.grid(row=1, column=1, sticky="w", pady=8, padx=(8, 0))
            pwd_entry.bind("<Return>", lambda _: role_combo.focus())
            row_offset = 0
        else:
            row_offset = -1

        # 角色
        ttk.Label(f, text="角  色：").grid(row=2 + row_offset, column=0, sticky="e", pady=8)
        role_var = tk.StringVar()
        role_combo = ttk.Combobox(f, textvariable=role_var, width=19,
                                  values=["集团", "子公司"], state="readonly")
        role_combo.grid(row=2 + row_offset, column=1, sticky="w", pady=8, padx=(8, 0))
        role_combo.set("子公司")

        # 所属项目（仅子公司需要）
        ttk.Label(f, text="所属项目：").grid(row=3 + row_offset, column=0, sticky="e", pady=8)
        proj_var = tk.StringVar()
        proj_combo = ttk.Combobox(f, textvariable=proj_var, width=19,
                                  values=utils.PROJECT_OPTIONS, state="readonly")
        proj_combo.grid(row=3 + row_offset, column=1, sticky="w", pady=8, padx=(8, 0))

        # 角色切换时控制项目必填
        def _on_role_change(*_args):
            if role_var.get() == "子公司":
                proj_combo.config(state="readonly")
            else:
                proj_combo.config(state="disabled")
                proj_var.set("")
        role_var.trace_add("write", _on_role_change)

        # 编辑模式：加载当前值
        if mode == "edit" and username:
            try:
                conn = _get_conn()
                cur = conn.cursor()
                cur.execute("SELECT 角色, 所属项目 FROM users WHERE 用户名=%s", (username,))
                row = cur.fetchone()
                conn.close()
                if row:
                    role_var.set(row[0])
                    proj_var.set(row[1] or "")
            except Exception as e:
                messagebox.showerror("错误", str(e))

        # 提示
        hint_var = tk.StringVar()
        ttk.Label(f, textvariable=hint_var, foreground="#c0392b", font=("微软雅黑", 8)) \
            .grid(row=4 + row_offset, column=0, columnspan=2, pady=(4, 0))

        # 确认按钮
        def _do_save():
            u = user_var.get().strip()
            pwd = pwd_var.get()
            role = role_var.get()
            proj = proj_var.get().strip()

            if not u:
                hint_var.set("请输入用户名")
                return
            if mode == "add" and not pwd:
                hint_var.set("请输入密码")
                return
            if role == "子公司" and not proj:
                hint_var.set("子公司必须选择所属项目")
                return

            try:
                conn = _get_conn()
                cur = conn.cursor()

                if mode == "add":
                    pwd_hash = _hash_pwd(pwd)
                    cur.execute(
                        "INSERT INTO users (用户名, 密码, 角色, 所属项目) VALUES (%s, %s, %s, %s)",
                        (u, pwd_hash, role, proj if role == "子公司" else None)
                    )
                else:
                    cur.execute(
                        "UPDATE users SET 角色=%s, 所属项目=%s WHERE 用户名=%s",
                        (role, proj if role == "子公司" else None, u)
                    )

                conn.commit()
                conn.close()
                utils.log_operation("新增" if mode == "add" else "修改", "用户",
                                    f"{'新增' if mode == 'add' else '修改'}用户 {u}（{role}）", u)
                win.destroy()
                self._load_users()
                self.status_var.set(f"{'新增' if mode == 'add' else '修改'}成功：{u}")
            except pymysql.IntegrityError:
                hint_var.set("用户名已存在")
            except Exception as e:
                messagebox.showerror("错误", str(e))

        btn_frame = ttk.Frame(f)
        btn_frame.grid(row=5 + row_offset, column=0, columnspan=2, pady=(16, 0))

        ttk.Button(btn_frame, text="确  认", width=12, command=_do_save).pack(side="left", padx=15)
        ttk.Button(btn_frame, text="取  消", width=12, command=win.destroy).pack(side="left", padx=15)

        # 居中
        win.update_idletasks()
        w, h = 360, 280
        x = (win.winfo_screenwidth()  - w) // 2
        y = (win.winfo_screenheight() - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")

    # ── 修改密码弹窗 ──────────────────────────────────────────────────────────────
    def _open_pwd_window(self, username):
        win = tk.Toplevel(self.window)
        win.title("修改密码")
        win.geometry("320x200")
        win.resizable(False, False)
        win.transient(self.window)
        win.grab_set()

        f = ttk.Frame(win, padding=25)
        f.pack(fill="both", expand=True)

        ttk.Label(f, text=f"修改用户「{username}」的密码", font=("微软雅黑", 9)).pack(pady=(0, 12))

        ttk.Label(f, text="新密码：").pack(anchor="w")
        pwd_var = tk.StringVar()
        pwd_entry = ttk.Entry(f, textvariable=pwd_var, width=26, show="*")
        pwd_entry.pack(fill="x", pady=(4, 8))
        pwd_entry.focus()

        ttk.Label(f, text="确认密码：").pack(anchor="w")
        confirm_var = tk.StringVar()
        confirm_entry = ttk.Entry(f, textvariable=confirm_var, width=26, show="*")
        confirm_entry.pack(fill="x", pady=(4, 8))

        hint_var = tk.StringVar()
        ttk.Label(f, textvariable=hint_var, foreground="#c0392b", font=("微软雅黑", 8)).pack(pady=(4, 0))

        def _do_change():
            pwd1 = pwd_var.get()
            pwd2 = confirm_var.get()

            if not pwd1:
                hint_var.set("请输入新密码")
                return
            if pwd1 != pwd2:
                hint_var.set("两次密码不一致")
                return
            if len(pwd1) < 3:
                hint_var.set("密码长度至少3位")
                return

            try:
                conn = _get_conn()
                cur = conn.cursor()
                cur.execute("UPDATE users SET 密码=%s WHERE 用户名=%s",
                            (_hash_pwd(pwd1), username))
                conn.commit()
                conn.close()
                utils.log_operation("修改", "用户", f"修改用户 {username} 密码", username)
                win.destroy()
                self.status_var.set(f"已修改「{username}」的密码")
                messagebox.showinfo("成功", f"「{username}」的密码已修改")
            except Exception as e:
                messagebox.showerror("错误", str(e))

        confirm_entry.bind("<Return>", lambda _: _do_change())

        btn_frame = ttk.Frame(f)
        btn_frame.pack(pady=(12, 0))
        ttk.Button(btn_frame, text="确  认", width=12, command=_do_change).pack(side="left", padx=15)
        ttk.Button(btn_frame, text="取  消", width=12, command=win.destroy).pack(side="left", padx=15)

        # 居中
        win.update_idletasks()
        w, h = 320, 200
        x = (win.winfo_screenwidth()  - w) // 2
        y = (win.winfo_screenheight() - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")

    # ── 查看操作日志 ──────────────────────────────────────────────────────────────
    def _open_log_viewer(self):
        win = tk.Toplevel(self.window)
        win.title("操作日志")
        win.geometry("900x520")
        win.transient(self.window)
        win.grab_set()

        main = ttk.Frame(win, padding=12)
        main.pack(fill="both", expand=True)

        # 筛选栏
        filter_f = ttk.Frame(main)
        filter_f.pack(fill="x", pady=(0, 8))

        ttk.Label(filter_f, text="操作人：").pack(side="left")
        op_var = tk.StringVar(value="全部")
        op_combo = ttk.Combobox(filter_f, textvariable=op_var, width=10, state="readonly")
        op_combo.pack(side="left", padx=(2, 12))

        ttk.Label(filter_f, text="模块：").pack(side="left")
        mod_var = tk.StringVar(value="全部")
        mod_combo = ttk.Combobox(filter_f, textvariable=mod_var, width=10, state="readonly",
                                  values=["全部", "商铺", "合同", "租金", "经营数据", "商机", "用户"])
        mod_combo.pack(side="left", padx=(2, 12))

        ttk.Label(filter_f, text="类型：").pack(side="left")
        type_var = tk.StringVar(value="全部")
        type_combo = ttk.Combobox(filter_f, textvariable=type_var, width=8, state="readonly",
                                   values=["全部", "新增", "修改", "删除"])
        type_combo.pack(side="left", padx=(2, 12))

        refresh_btn = ttk.Button(filter_f, text="🔍 筛选")
        refresh_btn.pack(side="left", padx=4)
        ttk.Button(filter_f, text="重置", command=lambda: [op_var.set("全部"), mod_var.set("全部"), type_var.set("全部"), _load()]).pack(side="left", padx=4)

        # 日志表格
        table_f = ttk.Frame(main)
        table_f.pack(fill="both", expand=True)

        cols = ("操作时间", "操作人", "角色", "模块", "类型", "操作描述", "记录ID", "IP地址")
        tree = ttk.Treeview(table_f, columns=cols, show="headings", height=15)
        widths = [150, 70, 60, 70, 50, 260, 100, 120]
        for c, w in zip(cols, widths):
            tree.heading(c, text=c)
            tree.column(c, width=w, anchor="center")
        tree.column("操作描述", anchor="w")
        tree.tag_configure("even", background="#f7faff")
        tree.tag_configure("odd",  background="#ffffff")

        vs = ttk.Scrollbar(table_f, orient="vertical", command=tree.yview)
        hs = ttk.Scrollbar(table_f, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        table_f.rowconfigure(0, weight=1)
        table_f.columnconfigure(0, weight=1)

        # 总计
        count_var = tk.StringVar()
        ttk.Label(main, textvariable=count_var, font=("微软雅黑", 8), foreground="#888").pack(anchor="w", pady=(6, 0))

        def _load():
            tree.delete(*tree.get_children())
            try:
                conn = _get_conn()
                cur = conn.cursor()

                # 获取操作人列表
                cur.execute("SELECT DISTINCT 操作人 FROM operation_log ORDER BY 操作人")
                ops = ["全部"] + [r[0] for r in cur.fetchall()]
                op_combo["values"] = ops

                # 构建查询
                sql = "SELECT 操作时间, 操作人, 角色, 操作模块, 操作类型, 操作描述, 记录ID, IP地址 FROM operation_log WHERE 1=1"
                params = []
                if op_var.get() != "全部":
                    sql += " AND 操作人=%s"
                    params.append(op_var.get())
                if mod_var.get() != "全部":
                    sql += " AND 操作模块=%s"
                    params.append(mod_var.get())
                if type_var.get() != "全部":
                    sql += " AND 操作类型=%s"
                    params.append(type_var.get())

                sql += " ORDER BY id DESC LIMIT 500"
                cur.execute(sql, params)
                rows = cur.fetchall()
                conn.close()

                for i, r in enumerate(rows):
                    tag = "even" if i % 2 == 0 else "odd"
                    tree.insert("", "end", values=(
                        str(r[0]) if r[0] else "",
                        r[1] or "", r[2] or "", r[3] or "",
                        r[4] or "", r[5] or "", r[6] or "", r[7] or ""
                    ), tags=(tag,))
                count_var.set(f"共 {len(rows)} 条记录（最多显示 500 条）")
            except Exception as e:
                messagebox.showerror("错误", f"加载日志失败：\n{e}", parent=win)

        refresh_btn.config(command=_load)
        _load()

        # 居中
        win.update_idletasks()
        w_, h_ = 900, 520
        x = (win.winfo_screenwidth()  - w_) // 2
        y = (win.winfo_screenheight() - h_) // 2
        win.geometry(f"{w_}x{h_}+{x}+{y}")

    # ── 关闭 ──────────────────────────────────────────────────────────────────────
    def _on_close(self):
        self.window.destroy()


# ── 便捷函数 ──────────────────────────────────────────────────────────────────────
def popup_user_manage(parent):
    """弹出用户管理窗口"""
    UserManageWindow(parent)
