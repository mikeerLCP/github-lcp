"""
utils.py —— 小牛b商管系统 共享工具模块
提供所有模块共用的：路径配置、弹出式日历控件、常量定义、数据读写工具

存储后端选择：修改 STORAGE_BACKEND 切换 JSON / MySQL
  "json"  — 使用 JSON 文件（默认，零依赖）
  "mysql" — 使用 MySQL 数据库（需先运行 migrate_to_mysql.py）
"""

import json
import os
import sys
import calendar
import socket
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime

# ===================== 存储后端选择 =====================
STORAGE_BACKEND = "mysql"  # "json" 或 "mysql"

# ===================== 当前登录用户（由 login_window.py 设置）=====================
# 值为 None 或 dict: {"用户名", "角色", "所属项目"}
CURRENT_USER = None


# ===================== 操作日志 =====================
def log_operation(操作类型, 操作模块, 操作描述="", 记录ID=""):
    """
    写入操作日志到数据库（仅 MySQL 模式下生效）。
    自动从 CURRENT_USER 获取操作人和角色。

    参数：
        操作类型: "新增" / "修改" / "删除"
        操作模块: "商铺" / "合同" / "租金" / "经营数据" / "商机" / "用户"
        操作描述: 可读的变更摘要
        记录ID:   被操作的记录标识（铺位号/合同号等）
    """
    if STORAGE_BACKEND != "mysql":
        return
    try:
        user = CURRENT_USER or {}
        username = user.get("用户名", "未知")
        role     = user.get("角色", "")
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
        except Exception:
            local_ip = ""

        import pymysql
        conn = pymysql.connect(
            host="127.0.0.1", port=3306, user="root", password="adminhang",
            database="xiaoniu_shangguan", charset="utf8mb4"
        )
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO operation_log (操作人, 角色, 操作类型, 操作模块, 操作描述, 记录ID, IP地址) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (username, role, 操作类型, 操作模块, 操作描述, str(记录ID), local_ip)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[log_operation] 写入失败: {e}")


# ===================== 路径配置 =====================
def _get_base_dir():
    """获取程序运行基目录（兼容 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

SCRIPT_DIR = _get_base_dir()

# 数据文件路径
SHOPS_DATA_FILE  = os.path.join(SCRIPT_DIR, "shops_data.json")
CONTRACTS_FILE   = os.path.join(SCRIPT_DIR, "contracts_data.json")
PAYMENT_FILE     = os.path.join(SCRIPT_DIR, "payment_records.json")
BUSINESS_FILE    = os.path.join(SCRIPT_DIR, "business_data.json")
OPPORTUNITY_FILE = os.path.join(SCRIPT_DIR, "opportunities_data.json")

# ===================== 常量定义 =====================
PROJECT_OPTIONS = ["卢沟桥文化公园", "园博园", "园博大酒店", "长辛店", "凉水河"]
BUSINESS_TYPE   = ["轻餐", "重餐", "茶饮", "零售", "生活服务", "亲子娱乐/教培", "创意办公", "文化体验", "住宿"]
SHOP_STATUS     = ["空置", "已出租", "维修", "退场交接"]

# ===================== 弹出式万年历控件 =====================
class PopupCalendar:
    """弹出式万年历控件（共用组件，零外部依赖）"""
    def __init__(self, parent, callback):
        self.top = tk.Toplevel(parent)
        self.top.title("选择日期")
        self.top.geometry("360x380")
        self.top.transient(parent)
        self.top.grab_set()
        self.callback = callback

        self.today = date.today()
        self.selected_year = self.today.year
        self.selected_month = self.today.month

        self.year_list = [str(y) for y in range(2000, 2051)]
        self.month_list = [f"{m:02d}" for m in range(1, 13)]

        self.var_year = tk.StringVar(value=str(self.selected_year))
        self.var_month = tk.StringVar(value=f"{self.selected_month:02d}")

        self.var_year.trace_add("write", self.on_year_month_change)
        self.var_month.trace_add("write", self.on_year_month_change)

        self.create_widgets()
        self.render_days()

    def on_year_month_change(self, *args):
        self.validate_year_month()
        self.render_days()

    def validate_year_month(self, *args):
        try:
            y = int(self.var_year.get())
            m = int(self.var_month.get())
            if y < 2000 or y > 2050:
                self.var_year.set(str(self.selected_year))
            if m < 1 or m > 12:
                self.var_month.set(f"{self.selected_month:02d}")
        except (ValueError, TypeError):
            self.var_year.set(str(self.selected_year))
            self.var_month.set(f"{self.selected_month:02d}")

    def create_widgets(self):
        f1 = ttk.Frame(self.top)
        f1.pack(pady=8)
        ttk.Label(f1, text="年：").pack(side=tk.LEFT, padx=3)
        cb_year = ttk.Combobox(f1, textvariable=self.var_year, values=self.year_list, width=8, state="readonly")
        cb_year.pack(side=tk.LEFT, padx=3)
        ttk.Label(f1, text=" 月：").pack(side=tk.LEFT, padx=3)
        cb_month = ttk.Combobox(f1, textvariable=self.var_month, values=self.month_list, width=5, state="readonly")
        cb_month.pack(side=tk.LEFT, padx=3)

        f_week = ttk.Frame(self.top)
        f_week.pack()
        for w in ["一", "二", "三", "四", "五", "六", "日"]:
            ttk.Label(f_week, text=w, width=5).grid(row=0, column=["一", "二", "三", "四", "五", "六", "日"].index(w))

        self.day_frame = ttk.Frame(self.top)
        self.day_frame.pack(pady=6)
        ttk.Button(self.top, text="取消", command=self.top.destroy).pack(pady=4)

    def render_days(self):
        for w in self.day_frame.winfo_children():
            w.destroy()
        self.validate_year_month()
        try:
            y = int(self.var_year.get())
            m = int(self.var_month.get())
        except:
            y, m = self.today.year, self.today.month
        self.selected_year = y
        self.selected_month = m

        first_day = date(y, m, 1)
        start_week = first_day.weekday()
        month_days = calendar.monthrange(y, m)[1]

        row = 1
        col = start_week
        for d in range(1, month_days + 1):
            def click(day=d):
                try:
                    dt = date(y, m, day)
                    self.callback(dt.strftime("%Y-%m-%d"))
                    self.top.destroy()
                except Exception as e:
                    messagebox.showerror("错误", f"日期选择失败：{str(e)}")

            btn = ttk.Button(self.day_frame, text=str(d), width=5, command=click)
            btn.grid(row=row, column=col)
            col += 1
            if col > 6:
                col = 0
                row += 1

# ===================== 数据读写工具 =====================
# JSON 后端
def _load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def _save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

# MySQL 后端（延迟导入，避免 JSON 模式报错）
def _mysql():
    """延迟导入 db 模块"""
    import db
    return db

# ── 商铺 ──
def load_shops():
    if STORAGE_BACKEND == "mysql":
        data = _mysql().load_shops()
    else:
        data = _load_json(SHOPS_DATA_FILE)
    # 按当前用户过滤（子公司只能看自己项目的数据）
    if CURRENT_USER and CURRENT_USER.get("角色") == "子公司":
        proj = CURRENT_USER.get("所属项目", "")
        data = [s for s in data if s.get("所属项目", "") == proj]
    return data

def save_shops(data):
    if STORAGE_BACKEND == "mysql":
        return _mysql().save_shops(data)
    return _save_json(SHOPS_DATA_FILE, data)

def delete_shop(shop_no):
    """删除商铺及其关联数据（级联删除，MySQL/JSON 通用）"""
    if STORAGE_BACKEND == "mysql":
        return _mysql().delete_shop(shop_no)
    # JSON 后端：级联删除
    contracts = load_contracts()
    matched_contracts = [c for c in contracts if c.get("关联铺位号", "") == shop_no]
    matched_nos = [c.get("合同号", "") for c in matched_contracts]
    # 删除关联缴费记录
    payments = load_payment_records()
    payments = [p for p in payments if p.get("合同号", "") not in matched_nos]
    _save_json(PAYMENT_FILE, payments)
    # 删除关联经营数据
    biz_data = load_business_data()
    biz_data = [b for b in biz_data if b.get("合同号", "") not in matched_nos]
    _save_json(BUSINESS_FILE, biz_data)
    # 删除关联合同
    contracts = [c for c in contracts if c.get("合同号", "") not in matched_nos]
    _save_json(CONTRACTS_FILE, contracts)
    # 删除商铺
    shops = load_shops()
    shops = [s for s in shops if s.get("铺位号") != shop_no]
    return _save_json(SHOPS_DATA_FILE, shops)


def get_contracts_by_shop(shop_no):
    """查询关联某个铺位的所有合同（MySQL/JSON 通用）"""
    if STORAGE_BACKEND == "mysql":
        return _mysql().get_contracts_by_shop(shop_no)
    contracts = load_contracts()
    return [{"合同号": c.get("合同号", ""), "商户名称": c.get("商户名称", ""),
             "合同状态": c.get("合同状态", "")}
            for c in contracts if c.get("关联铺位号", "") == shop_no]


def check_shop_no_exists(shop_no):
    if STORAGE_BACKEND == "mysql":
        return _mysql().check_shop_no_exists(shop_no)
    shops = load_shops()
    for s in shops:
        if s.get("铺位号") == shop_no:
            return True
    return False

# ── 合同 ──
def load_contracts():
    if STORAGE_BACKEND == "mysql":
        data = _mysql().load_contracts()
    else:
        data = _load_json(CONTRACTS_FILE)
    if CURRENT_USER and CURRENT_USER.get("角色") == "子公司":
        proj = CURRENT_USER.get("所属项目", "")
        data = [c for c in data if c.get("所属项目", "") == proj]
    return data

def save_contracts(data):
    if STORAGE_BACKEND == "mysql":
        return _mysql().save_contracts(data)
    return _save_json(CONTRACTS_FILE, data)

def delete_contract(contract_no):
    """删除单个合同（MySQL/JSON 通用）"""
    if STORAGE_BACKEND == "mysql":
        return _mysql().delete_contract(contract_no)
    contracts = load_contracts()
    contracts = [c for c in contracts if c.get("合同号") != contract_no]
    return _save_json(CONTRACTS_FILE, contracts)

# ── 缴费记录 ──
def load_payments():
    if STORAGE_BACKEND == "mysql":
        data = _mysql().load_payments()
    else:
        data = _load_json(PAYMENT_FILE)
    if CURRENT_USER and CURRENT_USER.get("角色") == "子公司":
        proj = CURRENT_USER.get("所属项目", "")
        data = [p for p in data if p.get("所属项目", "") == proj]
    return data

def save_payments(data):
    if STORAGE_BACKEND == "mysql":
        return _mysql().save_payments(data)
    return _save_json(PAYMENT_FILE, data)

def delete_payment(contract_no, pay_time):
    """删除单条缴费记录（MySQL/JSON 通用）"""
    if STORAGE_BACKEND == "mysql":
        return _mysql().delete_payment(contract_no, pay_time)
    payments = load_payments()
    payments = [p for p in payments
                if not (p.get("合同号") == contract_no and p.get("支付时间") == pay_time)]
    return _save_json(PAYMENT_FILE, payments)

def get_paid(contract_no, pay_time):
    if STORAGE_BACKEND == "mysql":
        return _mysql().get_paid(contract_no, pay_time)
    payments = load_payments()
    for p in payments:
        if p.get("合同号") == contract_no and p.get("支付时间") == pay_time:
            return p.get("已缴金额(元)", 0)
    return 0.0

def update_paid(contract_no, pay_time, val):
    if STORAGE_BACKEND == "mysql":
        return _mysql().update_paid(contract_no, pay_time, val)
    payments = load_payments()
    found = False
    for p in payments:
        if p.get("合同号") == contract_no and p.get("支付时间") == pay_time:
            p["已缴金额(元)"] = round(float(val), 2)
            found = True
            break
    if not found:
        # 查找所属项目
        project = ""
        try:
            contracts = load_contracts()
            for c in contracts:
                if str(c.get("合同号", "")).strip() == str(contract_no).strip():
                    project = c.get("所属项目", "")
                    break
        except:
            pass
        payments.append({
            "合同号": contract_no,
            "支付时间": pay_time,
            "已缴金额(元)": round(float(val), 2),
            "所属项目": project,
        })
    save_payments(payments)

def get_property_fee_paid(contract_no, pay_time):
    if STORAGE_BACKEND == "mysql":
        return _mysql().get_property_fee_paid(contract_no, pay_time)
    payments = load_payments()
    for p in payments:
        if p.get("合同号") == contract_no and p.get("支付时间") == pay_time:
            return p.get("已缴物业费", 0)
    return 0.0

def update_property_fee_paid(contract_no, pay_time, val):
    if STORAGE_BACKEND == "mysql":
        return _mysql().update_property_fee_paid(contract_no, pay_time, val)
    payments = load_payments()
    found = False
    for p in payments:
        if p.get("合同号") == contract_no and p.get("支付时间") == pay_time:
            p["已缴物业费"] = round(float(val), 2)
            found = True
            break
    if not found:
        # 查找所属项目
        project = ""
        try:
            contracts = load_contracts()
            for c in contracts:
                if str(c.get("合同号", "")).strip() == str(contract_no).strip():
                    project = c.get("所属项目", "")
                    break
        except:
            pass
        payments.append({
            "合同号": contract_no,
            "支付时间": pay_time,
            "已缴金额(元)": 0,
            "所属项目": project,
            "已缴物业费": round(float(val), 2),
        })
    save_payments(payments)

# ── 经营数据 ──
def load_business_data():
    if STORAGE_BACKEND == "mysql":
        data = _mysql().load_business_data()
    else:
        data = _load_json(BUSINESS_FILE)
    if CURRENT_USER and CURRENT_USER.get("角色") == "子公司":
        proj = CURRENT_USER.get("所属项目", "")
        data = [b for b in data if b.get("所属项目", "") == proj]
    return data

def save_business_data(data):
    if STORAGE_BACKEND == "mysql":
        return _mysql().save_business_data(data)
    return _save_json(BUSINESS_FILE, data)

def delete_business_data(contract_no, date_val):
    """删除单条经营数据（MySQL/JSON 通用）"""
    if STORAGE_BACKEND == "mysql":
        return _mysql().delete_business_data(contract_no, date_val)
    data = load_business_data()
    data = [b for b in data
            if not (b.get("合同号") == contract_no and b.get("日期") == date_val)]
    return _save_json(BUSINESS_FILE, data)

# ── 商机 ──
def load_opportunities():
    if STORAGE_BACKEND == "mysql":
        data = _mysql().load_opportunities()
    else:
        data = _load_json(OPPORTUNITY_FILE)
    if CURRENT_USER and CURRENT_USER.get("角色") == "子公司":
        proj = CURRENT_USER.get("所属项目", "")
        data = [o for o in data if o.get("意向项目", "") == proj]
    return data

def save_opportunities(data):
    if STORAGE_BACKEND == "mysql":
        return _mysql().save_opportunities(data)
    return _save_json(OPPORTUNITY_FILE, data)

def delete_opportunity(opp_no):
    """删除单个商机（MySQL/JSON 通用）"""
    if STORAGE_BACKEND == "mysql":
        return _mysql().delete_opportunity(opp_no)
    opps = load_opportunities()
    opps = [o for o in opps if o.get("商机编号") != opp_no]
    return _save_json(OPPORTUNITY_FILE, opps)

# ===================== 通用搜索选择弹窗 =====================
def search_select_window(parent, title, candidates, width=400, height=420):
    """
    通用搜索选择弹窗：传入候选列表，返回用户选中的字符串（取消返回 None）。
    candidates: list[str]
    """
    if not candidates:
        messagebox.showwarning("提示", "没有可选项")
        return None

    result = {"value": None}
    win = tk.Toplevel(parent)
    win.title(title or "搜索选择")
    win.geometry(f"{width}x{height}")
    win.transient(parent)
    win.grab_set()
    win.resizable(True, True)

    # 搜索区
    search_frame = ttk.Frame(win)
    search_frame.pack(fill="x", padx=10, pady=(10, 5))
    ttk.Label(search_frame, text="搜索：").pack(side="left")
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
    search_entry.pack(side="left", padx=(4, 0), fill="x", expand=True)
    search_entry.focus()

    # 列表区
    list_frame = ttk.Frame(win)
    list_frame.pack(fill="both", expand=True, padx=10, pady=5)

    scrollbar = ttk.Scrollbar(list_frame)
    scrollbar.pack(side="right", fill="y")

    listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("微软雅黑", 10),
                          selectmode="single", activestyle="dotbox", height=18)
    listbox.pack(side="left", fill="both", expand=True)
    scrollbar.config(command=listbox.yview)

    # 全量数据 & 过滤
    all_items = candidates

    def _populate(*_):
        keyword = search_var.get().strip().lower()
        listbox.delete(0, "end")
        for item in all_items:
            if not keyword or keyword in item.lower():
                listbox.insert("end", item)

    search_var.trace_add("write", _populate)
    _populate()

    # 双击 / 回车 确认
    def _confirm(_=None):
        sel = listbox.curselection()
        if sel:
            result["value"] = listbox.get(sel[0])
            win.destroy()
        elif listbox.size() == 1:
            # 只有一个匹配项时直接确认
            result["value"] = listbox.get(0)
            win.destroy()
        else:
            messagebox.showwarning("提示", "请先选择一项")

    listbox.bind("<Double-1>", lambda _: _confirm())
    listbox.bind("<Return>", lambda _: _confirm())
    search_entry.bind("<Return>", lambda _: _confirm())

    # 按钮区
    btn_frame = ttk.Frame(win)
    btn_frame.pack(fill="x", padx=10, pady=(0, 10))
    ttk.Button(btn_frame, text="确认", command=_confirm).pack(side="left", padx=10)
    ttk.Button(btn_frame, text="取消", command=win.destroy).pack(side="left")

    win.wait_window()
    return result["value"]

# ===================== 租金计算工具 =====================
CYCLE_MAP = {"月度": 1, "季度": 3, "半年": 6, "年度": 12}

def get_shop_area(shop_no):
    shops = load_shops()
    for shop in shops:
        if str(shop.get("铺位号", "")).strip() == str(shop_no).strip():
            try:
                # 兼容旧字段名「计租面积」
                return float(shop.get("建筑面积(㎡)", shop.get("计租面积(㎡)", 0) or 0))
            except:
                return 0.0
    return 0.0

def _get_period_revenue(biz_list, cno, period_start, period_end):
    """汇总指定合同在 [period_start, period_end] 期间内的营业额总和"""
    total = 0.0
    if not biz_list:
        return total
    for biz in biz_list:
        if str(biz.get("合同号", "")) != str(cno):
            continue
        try:
            biz_date = datetime.strptime(biz.get("日期", ""), "%Y-%m-%d")
            if period_start <= biz_date <= period_end:
                total += float(biz.get("营业额", 0))
        except:
            pass
    return total

def generate_rent_plan(contract, _shops_cache=None, _payments_cache=None, _biz_cache=None):
    """
    生成合同租金缴纳计划。
    可选传入 _shops_cache / _payments_cache / _biz_cache 避免重复加载数据。
    根据合同的"租金模式"自动切换计算方式：
      - 保底：应缴 = 保底租金单价 × 面积 × 有效天数（扣除免租）
      - 提成：应缴 = 本期营业额合计 × 提成扣点% × 有效天数比例
      - 取高：应缴 = max(保底金额, 提成金额)
    免租计划按天折算，落入免租时段的天数不计租金。
    """
    try:
        from datetime import datetime, timedelta
        from dateutil.relativedelta import relativedelta
        shop_no = contract.get("关联铺位号", "")
        # 使用缓存或实时查询商铺面积
        area = 0.0
        if _shops_cache is not None:
            for shop in _shops_cache:
                if str(shop.get("铺位号", "")).strip() == str(shop_no).strip():
                    try:
                        # 兼容旧字段名「计租面积」
                        area = float(shop.get("建筑面积(㎡)", shop.get("计租面积(㎡)", 0) or 0))
                    except:
                        area = 0.0
                    break
        else:
            area = get_shop_area(shop_no)
        rent_mode = contract.get("租金模式", "保底")  # 默认保底兼容旧数据
        daily_rate = float(contract.get("保底租金(元/㎡/天)", 0))
        commission_pct = float(contract.get("提成租金扣点(%)", 0))
        property_fee_rate = float(contract.get("物业服务费单价（元/㎡/天）", 0) or 0)
        start = datetime.strptime(contract["租赁开始日期"], "%Y-%m-%d")
        end = datetime.strptime(contract["租赁结束日期"], "%Y-%m-%d")
        term_str = contract.get("终止日期", "")
        if term_str:
            try:
                term_dt = datetime.strptime(term_str, "%Y-%m-%d")
                end = min(end, term_dt)
            except:
                pass
        # ── 解析免租计划（按天折算）──
        free_plans_raw = contract.get("免租计划", [])
        if isinstance(free_plans_raw, str):
            try:
                free_plans_raw = json.loads(free_plans_raw)
            except:
                free_plans_raw = []
        if not isinstance(free_plans_raw, list):
            free_plans_raw = []
        free_ranges = []
        for fp in free_plans_raw:
            try:
                fs = datetime.strptime(fp["start"], "%Y-%m-%d")
                fe = datetime.strptime(fp["end"], "%Y-%m-%d")
                free_ranges.append((fs, fe))
            except:
                pass
        # 合并重叠/相邻区间，避免重复计算
        if len(free_ranges) > 1:
            free_ranges.sort()
            merged = [free_ranges[0]]
            for s, e in free_ranges[1:]:
                if s <= merged[-1][1] + timedelta(days=1):
                    merged[-1] = (merged[-1][0], max(merged[-1][1], e))
                else:
                    merged.append((s, e))
            free_ranges = merged

        cycle = contract.get("支付周期", "")
        cno = contract.get("合同号")
        months = CYCLE_MAP.get(cycle, 1)

        # 经营数据缓存（提成/取高模式需要）
        biz_list = _biz_cache
        if _biz_cache is None and rent_mode in ("提成", "取高"):
            biz_list = load_business_data()

        # 预构建缴费记录索引
        paid_index = {}
        property_paid_index = {}
        if _payments_cache is not None:
            for p in _payments_cache:
                key = (p.get("合同号", ""), p.get("支付时间", ""))
                paid_index[key] = p.get("已缴金额(元)", 0)
                property_paid_index[key] = p.get("已缴物业费", 0)

        plan = []
        cur = start
        while cur <= end:
            nxt = cur + relativedelta(months=months)
            pe = min(nxt - timedelta(days=1), end)
            days = (pe - cur).days + 1
            if days <= 0:
                break

            # ── 计算本期免租天数 ──
            free_days = 0
            for fs, fe in free_ranges:
                o_start = max(cur, fs)
                o_end = min(pe, fe)
                if o_start <= o_end:
                    free_days += (o_end - o_start).days + 1
            effective_days = max(days - free_days, 0)

            # ── 根据租金模式计算应缴金额 ──
            if rent_mode == "保底":
                should = daily_rate * area * effective_days
            elif rent_mode == "提成":
                period_revenue = _get_period_revenue(biz_list, cno, cur, pe)
                should = period_revenue * commission_pct / 100.0
                # 提成模式也按免租天数比例减免
                if days > 0:
                    should = should * effective_days / days
            elif rent_mode == "取高":
                base_rent = daily_rate * area * effective_days
                period_revenue = _get_period_revenue(biz_list, cno, cur, pe)
                comm_rent = period_revenue * commission_pct / 100.0
                if days > 0:
                    comm_rent = comm_rent * effective_days / days
                should = max(base_rent, comm_rent)
            else:
                # 未知模式回退保底
                should = daily_rate * area * effective_days

            pay_time_str = cur.strftime("%Y-%m-%d")
            if _payments_cache is not None:
                paid = paid_index.get((cno, pay_time_str), 0.0)
                prop_paid = property_paid_index.get((cno, pay_time_str), 0.0)
            else:
                paid = get_paid(cno, pay_time_str)
                prop_paid = get_property_fee_paid(cno, pay_time_str)
            # 物业费 = 物业费单价 × 建筑面积 × 有效天数
            property_fee = round(property_fee_rate * area * effective_days, 2)
            plan.append({
                "合同号": cno,
                "支付时间": pay_time_str,
                "应缴金额(元)": round(should, 2),
                "已缴金额(元)": paid,
                "应缴物业费": property_fee,
                "已缴物业费": prop_paid
            })
            cur = nxt
        return plan
    except:
        return []

def total_paid(contract):
    return round(sum(p["已缴金额(元)"] for p in generate_rent_plan(contract)), 2)

def total_rent(contract):
    return round(sum(p["应缴金额(元)"] for p in generate_rent_plan(contract)), 2)

def remaining_rent(contract):
    return round(total_rent(contract) - total_paid(contract), 2)

def next_days_label(contract):
    try:
        from datetime import datetime, date
        status = contract.get("合同状态", "")
        if status == "已到期":
            return "已到期", -1
        if status == "已终止":
            return "已终止", -1
        today = date.today()
        plan = generate_rent_plan(contract)
        unpaid = [p for p in plan if p["已缴金额(元)"] < p["应缴金额(元)"]]
        if not unpaid:
            return "已结清", 9999
        unpaid.sort(key=lambda x: x["支付时间"])
        for p in unpaid:
            d = datetime.strptime(p["支付时间"], "%Y-%m-%d").date()
            if d >= today:
                diff = (d - today).days
                return str(diff), diff
        return "已逾期", -1
    except:
        return "错误", 9999

def arrears(contract):
    try:
        from datetime import datetime, date
        today = date.today()
        plan = generate_rent_plan(contract)
        total = 0.0
        for p in plan:
            d = datetime.strptime(p["支付时间"], "%Y-%m-%d").date()
            if d < today:
                s = p["应缴金额(元)"]
                pd = p["已缴金额(元)"]
                total += max(s - pd, 0)
        return round(total, 2)
    except:
        return 0.0
