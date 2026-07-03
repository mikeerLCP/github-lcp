import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime, timedelta
from collections import defaultdict
import calendar
import subprocess
import sys
import os
import json
import utils           # 用于设置 CURRENT_USER

# 导入模块
from module_shop import ShopManageGUI
from module_contract import ContractManageGUI
from module_rent_collection import RentCollectionGUI
from module_opportunity import OpportunityManageGUI, load_opportunities, OPPORTUNITY_STAGES
from module_business_data import BusinessDataGUI
from utils import PopupCalendar, SCRIPT_DIR, load_shops, load_contracts, load_business_data, load_payments, generate_rent_plan

class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LCP商管系统")
        self.root.geometry("1200x700")
        self.root.state("zoomed")

        # 左侧菜单
        self.sidebar = ttk.Frame(root, width=200)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)

        # 右侧内容
        self.content = ttk.Frame(root)
        self.content.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 菜单标题
        ttk.Label(self.sidebar, text="功能菜单", font=("黑体", 14)).pack(pady=20)

        # ── 菜单按钮（tk.Button 可改背景色高亮当前模块） ──
        self.menu_buttons = {}
        self.current_module = None

        MENU_FG = "#2c3e50"      # 默认文字色
        MENU_BG = "#ecf0f1"      # 默认背景色
        MENU_ACTIVE_BG = "#3498db"  # 高亮背景色
        MENU_ACTIVE_FG = "white"    # 高亮文字色

        menu_items = [
            ("home",     "🏠 主页",     self.show_home),
            ("shop",     "🏬 商铺管理", self.open_shop),
            ("opp",      "🎯 商机管理", self.open_opportunity),
            ("contract", "📄 合同管理", self.open_contract),
            ("rent",     "💰 租金收缴", self.open_rent_collection),
            ("biz",      "📋 经营数据", self.open_business_data),
        ]

        for module_id, text, cmd in menu_items:
            btn = tk.Button(self.sidebar, text=text,
                            font=("微软雅黑", 10), anchor="w", padx=12, pady=8,
                            bd=0, relief="flat", cursor="hand2",
                            bg=MENU_BG, fg=MENU_FG, activebackground="#d5dbdb",
                            command=lambda mid=module_id, c=cmd: self._switch_module(mid, c))
            btn.pack(fill="x", padx=8, pady=2)
            self.menu_buttons[module_id] = btn

        # 分隔线
        ttk.Separator(self.sidebar, orient="horizontal").pack(fill="x", padx=10, pady=8)

        # 用户管理（仅集团角色显示）
        if utils.CURRENT_USER and utils.CURRENT_USER.get("角色") == "集团":
            ttk.Button(self.sidebar, text="👤 用户管理", command=self.open_user_manage, width=18).pack(pady=5)

        # ── 商户门户入口（仅集团角色可操作启停）──
        self._portal_btn = None
        self._portal_btn_text = tk.StringVar(value="🌐 启动商户门户")
        self.portal_status_var = tk.StringVar(value="")
        self._portal_proc = None
        self._portal_enabled = utils.CURRENT_USER and utils.CURRENT_USER.get("角色") == "集团"

        if self._portal_enabled:
            self._portal_btn = ttk.Button(self.sidebar, textvariable=self._portal_btn_text,
                                        command=self.toggle_merchant_portal, width=18)
            self._portal_btn.pack(pady=3)
            ttk.Label(self.sidebar, textvariable=self.portal_status_var,
                      font=("微软雅黑", 8), foreground="#27ae60",
                      wraplength=160, justify="center").pack(pady=(0, 5))

        # 关闭主窗口时自动清理门户进程
        self.root.protocol("WM_DELETE_WINDOW", self._on_main_close)
        # 启动时自动打开门户（仅集团角色）
        if self._portal_enabled:
            self.root.after(300, self.toggle_merchant_portal)

        self.root.after(100, lambda: self._switch_module("home", self.show_home))

    def clear_content(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def _switch_module(self, module_id, callback):
        """统一菜单切换：先高亮再执行回调"""
        self._highlight_menu(module_id)
        callback()

    def _highlight_menu(self, module_id):
        """视觉高亮当前模块菜单按钮"""
        self.current_module = module_id
        for mid, btn in self.menu_buttons.items():
            if mid == module_id:
                btn.config(bg="#3498db", fg="white")
            else:
                btn.config(bg="#ecf0f1", fg="#2c3e50")

    # ==================== 看板卡片组件 ====================
    def _stat_card(self, parent, title, value, row, col, value_color="#333", columnspan=1):
        """单个统计卡片：标题 + 数值"""
        card = tk.Frame(parent, bg="white", relief="solid", bd=1, padx=4, pady=3)
        card.grid(row=row, column=col, columnspan=columnspan, sticky="nsew", padx=1, pady=1)
        tk.Label(card, text=title, font=("微软雅黑", 8), fg="#999", bg="white").pack(expand=True)
        tk.Label(card, text=str(value), font=("黑体", 20, "bold"), fg=value_color, bg="white").pack(expand=True)


    # ==================== 数据加载 ====================
    def _get_shop_stats(self):
        shops = load_shops()
        total = len(shops)
        rented = sum(1 for s in shops if s.get("铺位状态", "") == "已出租")
        vacant  = sum(1 for s in shops if s.get("铺位状态", "") == "空置")
        repair  = sum(1 for s in shops if s.get("铺位状态", "") == "维修")
        return total, rented, vacant, repair

    def _get_contract_stats(self):
        """合同统计：每个合同只生成一次租金计划，使用缓存加速"""
        contracts = load_contracts()
        total = len(contracts)
        active     = sum(1 for c in contracts if c.get("合同状态", "") == "执行中")
        expired    = sum(1 for c in contracts if c.get("合同状态", "") == "已到期")
        terminated = sum(1 for c in contracts if c.get("合同状态", "") == "已终止")
        today = date.today()

        # 预加载缓存
        shops_cache = load_shops()
        payments_cache = load_payments()

        sum_total_rent  = 0.0
        sum_total_paid  = 0.0
        sum_overdue     = 0.0
        sum_due_rent    = 0.0
        overdue_cnt     = 0
        for c in contracts:
            plan = generate_rent_plan(c, _shops_cache=shops_cache, _payments_cache=payments_cache)
            tr = sum(p["应缴金额(元)"] for p in plan)
            pd = sum(p["已缴金额(元)"] for p in plan)
            sum_total_rent += tr
            sum_total_paid += pd
            # 逾期
            ar = 0.0
            due = 0.0
            for p in plan:
                d = datetime.strptime(p["支付时间"], "%Y-%m-%d").date()
                if d < today:
                    ar += max(p["应缴金额(元)"] - p["已缴金额(元)"], 0)
                if d <= today:
                    due += p["应缴金额(元)"]
            sum_overdue += ar
            sum_due_rent += due
            if ar > 0:
                overdue_cnt += 1
        sum_total_rent  = round(sum_total_rent, 2)
        sum_total_paid  = round(sum_total_paid, 2)
        sum_overdue     = round(sum_overdue, 2)
        sum_due_rent    = round(sum_due_rent, 2)
        return total, active, expired, terminated, overdue_cnt, \
               sum_total_rent, sum_total_paid, sum_overdue, sum_due_rent

    def _get_opportunity_stats(self):
        opps = load_opportunities()
        total      = len(opps)
        following  = sum(1 for o in opps if o.get("跟进结果", "") != "已流失"
                         and o.get("当前阶段", "") != "已支付意向金")
        paid       = sum(1 for o in opps if o.get("当前阶段", "") == "已支付意向金")
        lost       = sum(1 for o in opps if o.get("跟进结果", "") == "已流失")
        return total, following, paid, lost


    # ==================== 主页看板 ====================
    def show_home(self):
        self.clear_content()

        # 内容区背景
        self.content.configure(style="Content.TFrame")
        style = ttk.Style()
        style.configure("Content.TFrame", background="#f0f2f5")
        style.configure("Card.TLabelframe", background="#f0f2f5")
        style.configure("Card.TLabelframe.Label", background="#f0f2f5", font=("微软雅黑", 10, "bold"), foreground="#555")

        # ── 整体 Canvas + 右侧大滚动条 ──
        canvas = tk.Canvas(self.content, bg="#f0f2f5", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.content, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg="#f0f2f5")

        scroll_frame.bind("<Configure>",
                          lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        win_id = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

        def _on_canvas_configure(event):
            canvas.itemconfig(win_id, width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 鼠标滚轮
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        # 顶部标题栏
        header = tk.Frame(scroll_frame, bg="#2980b9", height=48)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🏠  欢迎使用LCP商管系统", font=("黑体", 16, "bold"),
                 fg="white", bg="#2980b9").pack(side=tk.LEFT, padx=22, pady=10)

        # 数据准备
        s_total, s_rented, s_vacant, s_repair = self._get_shop_stats()
        c_total, c_active, c_expired, c_terminated, c_overdue_cnt, \
            c_sum_rent, c_sum_paid, c_sum_overdue, c_sum_due = self._get_contract_stats()
        o_total, o_following, o_paid, o_lost = self._get_opportunity_stats()

        # ── 卡片行：商铺（左） + 商机/合同（中） + 租金总览（右） ──
        cards_row = tk.Frame(scroll_frame, bg="#f0f2f5")
        cards_row.pack(fill="x", padx=16, pady=(12, 6))

        # 左：商铺信息
        shop_frame = ttk.LabelFrame(cards_row, text="  商铺信息  ", padding=8, style="Card.TLabelframe")
        shop_frame.pack(side=tk.LEFT, fill="both", expand=True, padx=(0, 3))

        for i in range(2):
            shop_frame.columnconfigure(i, weight=1)
        for i in range(2):
            shop_frame.rowconfigure(i, weight=1)

        self._stat_card(shop_frame, "商铺总数", s_total,  0, 0, "#2980b9")
        self._stat_card(shop_frame, "已出租",   s_rented, 0, 1, "#2980b9")
        self._stat_card(shop_frame, "空置",     s_vacant, 1, 0, "#2980b9")
        self._stat_card(shop_frame, "维修",     s_repair, 1, 1, "#2980b9")

        # 中：商机概况（上）+ 合同状态（下）
        mid_col = tk.Frame(cards_row, bg="#f0f2f5")
        mid_col.pack(side=tk.LEFT, fill="both", expand=True, padx=3)

        opp_frame = ttk.LabelFrame(mid_col, text="  商机概况  ", padding=8, style="Card.TLabelframe")
        opp_frame.pack(side=tk.TOP, fill="x")

        for i in range(4):
            opp_frame.columnconfigure(i, weight=1)
        opp_frame.rowconfigure(0, weight=1)

        self._stat_card(opp_frame, "商机总数",       o_total,     0, 0, "#2980b9")
        self._stat_card(opp_frame, "跟进中",         o_following, 0, 1, "#2980b9")
        self._stat_card(opp_frame, "已支付意向金",   o_paid,      0, 2, "#2980b9")
        self._stat_card(opp_frame, "已流失",         o_lost,      0, 3, "#2980b9")

        contract_frame = ttk.LabelFrame(mid_col, text="  合同状态  ", padding=8, style="Card.TLabelframe")
        contract_frame.pack(side=tk.TOP, fill="x", pady=(4, 0))

        for i in range(5):
            contract_frame.columnconfigure(i, weight=1)
        contract_frame.rowconfigure(0, weight=1)


        self._stat_card(contract_frame, "合同总数", c_total,          0, 0, "#2980b9")
        self._stat_card(contract_frame, "履约中",   c_active,         0, 1, "#2980b9")
        self._stat_card(contract_frame, "已到期",   c_expired,        0, 2, "#2980b9")
        self._stat_card(contract_frame, "已终止",   c_terminated,     0, 3, "#2980b9")
        self._stat_card(contract_frame, "已逾期",   c_overdue_cnt,    0, 4, "#2980b9")

        # 右：租金总览
        collection_rate = (c_sum_paid / c_sum_due * 100) if c_sum_due else 0

        def _fmt(v):
            return f"{v:,.0f}" if v < 10000 else f"{v/10000:.1f}万"

        rent_frame = ttk.LabelFrame(cards_row, text="  租金总览  ", padding=8, style="Card.TLabelframe")
        rent_frame.pack(side=tk.LEFT, fill="both", expand=True, padx=(3, 0))

        for i in range(2):
            rent_frame.columnconfigure(i, weight=1)
        for i in range(2):
            rent_frame.rowconfigure(i, weight=1)

        self._stat_card(rent_frame, "已签订租金总额",   _fmt(c_sum_rent),  0, 0, "#2980b9")
        self._stat_card(rent_frame, "到期应收租金总额", _fmt(c_sum_due),   0, 1, "#2980b9")
        self._stat_card(rent_frame, "已收租金总额",     _fmt(c_sum_paid),  1, 0, "#2980b9")
        self._stat_card(rent_frame, "租金收缴率",       f"{collection_rate:.1f}%", 1, 1, "#2980b9")

        # ── 经营数据总览（内嵌至主页） ──
        self._render_home_biz_section(scroll_frame)

    # ==================== 模块入口 ====================
    def open_shop(self):
        self.clear_content()
        ShopManageGUI(self.content)

    def open_opportunity(self):
        self.clear_content()
        OpportunityManageGUI(self.content, open_contract_callback=self._open_contract_with_prefill)

    def open_contract(self):
        self.clear_content()
        ContractManageGUI(self.content)

    def _open_contract_with_prefill(self, prefill: dict):
        """从商机模块跳转到合同模块，并弹出预填了商户信息的新增合同窗口"""
        self._highlight_menu("contract")
        self.clear_content()
        gui = ContractManageGUI(self.content)
        # 直接打开新增窗口，并把商机带来的信息预填进去
        gui.create_contract_window(is_edit=False, contract_data=prefill)

    def open_rent_collection(self):
        self.clear_content()
        RentCollectionGUI(self.content)

    def open_business_data(self):
        self.clear_content()
        BusinessDataGUI(self.content)

    def open_user_manage(self):
        """弹出用户管理窗口（仅集团角色可调用）"""
        from module_user_management import popup_user_manage
        popup_user_manage(self.root)

    # ==================== 经营数据看板 ====================
    def _load_biz_dashboard_data(self):
        """加载看板所需的所有数据并做关联（使用 utils.SCRIPT_DIR）"""
        biz = load_business_data()
        contracts = load_contracts()
        shops = load_shops()
        # 建立映射：合同号 -> (合同信息, 商铺信息)
        contract_map = {}
        for c in contracts:
            shop_no = str(c.get("关联铺位号", ""))
            shop = None
            for s in shops:
                if str(s.get("铺位号", "")) == shop_no:
                    shop = s
                    break
            contract_map[str(c.get("合同号", ""))] = (c, shop)

        # 为每条经营记录补全字段
        enriched = []
        for r in biz:
            cno = str(r.get("合同号", ""))
            c_pair = contract_map.get(cno, (None, None))
            contract = c_pair[0]
            shop    = c_pair[1]
            r["_项目"]   = shop.get("所属项目", "") if shop else ""
            r["_面积"]   = float(shop.get("计租面积(㎡)", 0)) if shop else 0.0
            r["_业态"]   = r.get("业态", "") or (contract.get("经营业态", "") if contract else "")
            r["_铺位号"] = contract.get("关联铺位号", "") if contract else ""
            r["_营业额"] = float(r.get("营业额", 0)) if r.get("营业额", "") != "" else 0.0
            r["_客流量"] = int(r.get("客流量", 0)) if r.get("客流量", "") != "" else 0
            r["_成交量"] = int(r.get("成交量", 0)) if r.get("成交量", "") != "" else 0
            enriched.append(r)
        return enriched, shops, contracts

    def _agg_by_period(self, records, granularity):
        """按时间颗粒度聚合数据，返回 [(period_label, start_date, end_date, 营业额, 客流量, 成交量)]"""
        if not records:
            return []
        periods = defaultdict(lambda: {"营业额": 0.0, "客流量": 0, "成交量": 0})

        for r in records:
            try:
                d = datetime.strptime(r.get("日期", ""), "%Y-%m-%d")
            except Exception:
                continue
            if granularity == "日":
                key = d.strftime("%Y-%m-%d")
                start = end = d
            elif granularity == "周":
                iso = d.isocalendar()
                key = f"{iso[0]}-W{iso[1]:02d}"
                start = d - timedelta(days=d.weekday())
                end   = start + timedelta(days=6)
            elif granularity == "月":
                key = d.strftime("%Y-%m")
                start = d.replace(day=1)
                end   = (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            elif granularity == "季":
                q = (d.month - 1) // 3 + 1
                key = f"{d.year}-Q{q}"
                start = d.replace(month=3 * q - 2, day=1)
                end   = (start + timedelta(days=92)).replace(day=1) - timedelta(days=1)
            elif granularity == "年":
                key = str(d.year)
                start = d.replace(month=1, day=1)
                end   = d.replace(month=12, day=31)
            else:
                key = d.strftime("%Y-%m")
                start = d.replace(day=1)
                end   = (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            periods[key]["营业额"] += r.get("_营业额", 0)
            periods[key]["客流量"] += r.get("_客流量", 0)
            periods[key]["成交量"] += int(r.get("_成交量", 0))
            if "_start" not in periods[key] or start < periods[key]["_start"]:
                periods[key]["_start"] = start
                periods[key]["_end"]   = end

        result = []
        for key, v in sorted(periods.items()):
            result.append((key, v["_start"], v["_end"], round(v["营业额"], 2), v["客流量"], v["成交量"]))
        return result

    def _calc_mom_yoy(self, current, previous, same_last_year):
        """计算环比和同比变化率"""
        def _rate(a, b):
            if b and b != 0:
                return round((a - b) / b * 100, 1)
            return 0.0
        return _rate(current, previous), _rate(current, same_last_year)

    def show_business_dashboard(self):
        self.clear_content()
        self.content.configure(background="#f0f2f5")

        data, all_shops, all_contracts = self._load_biz_dashboard_data()

        # ── 顶部标题 ──
        header = tk.Frame(self.content, bg="#2980b9", height=44)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="📊  经营数据看板", font=("黑体", 15, "bold"),
                 fg="white", bg="#2980b9").pack(side=tk.LEFT, padx=22, pady=8)
        ttk.Button(header, text="📋 数据管理", command=self.open_business_data).pack(side=tk.RIGHT, padx=16, pady=6)

        if not data:
            tk.Label(self.content, text="暂无经营数据", font=("微软雅黑", 14),
                     fg="#999", bg="#f0f2f5").pack(expand=True)
            return

        # ── 筛选区 ──
        filter_frame = tk.Frame(self.content, bg="white", bd=0, relief="solid", padx=12, pady=8)
        filter_frame.pack(fill="x", padx=12, pady=(8, 0))

        # 时间颗粒度
        tk.Label(filter_frame, text="颗粒度：", font=("微软雅黑", 9), bg="white").pack(side=tk.LEFT)
        gran_var = tk.StringVar(value="月")
        gran_cb = ttk.Combobox(filter_frame, textvariable=gran_var,
                               values=["日", "周", "月", "季", "年"], width=5, state="readonly")
        gran_cb.pack(side=tk.LEFT, padx=(2, 12))

        # 日期范围
        tk.Label(filter_frame, text="日期：", font=("微软雅黑", 9), bg="white").pack(side=tk.LEFT)
        ds_var = tk.StringVar(value="")
        e1 = ttk.Entry(filter_frame, textvariable=ds_var, state="readonly", width=11, cursor="arrow")
        e1.pack(side=tk.LEFT, padx=2)
        e1.bind("<Button-1>", lambda _: PopupCalendar(filter_frame, ds_var.set))
        tk.Label(filter_frame, text="至", font=("微软雅黑", 9), bg="white").pack(side=tk.LEFT)
        de_var = tk.StringVar(value="")
        e2 = ttk.Entry(filter_frame, textvariable=de_var, state="readonly", width=11, cursor="arrow")
        e2.pack(side=tk.LEFT, padx=2)
        e2.bind("<Button-1>", lambda _: PopupCalendar(filter_frame, de_var.set))

        # 快捷
        def _set_quick(days):
            end = date.today()
            start = end - timedelta(days=days - 1)
            ds_var.set(start.strftime("%Y-%m-%d"))
            de_var.set(end.strftime("%Y-%m-%d"))
        ttk.Button(filter_frame, text="30天", width=5, command=lambda: _set_quick(30)).pack(side=tk.LEFT, padx=4)
        ttk.Button(filter_frame, text="90天", width=5, command=lambda: _set_quick(90)).pack(side=tk.LEFT, padx=2)
        ttk.Button(filter_frame, text="365天", width=6, command=lambda: _set_quick(365)).pack(side=tk.LEFT, padx=4)

        # 项目
        tk.Label(filter_frame, text="项目：", font=("微软雅黑", 9), bg="white").pack(side=tk.LEFT, padx=(10, 0))
        proj_var = tk.StringVar(value="全部")
        projects = ["全部"] + sorted(set(s.get("所属项目", "") for s in all_shops if s.get("所属项目")))
        proj_cb = ttk.Combobox(filter_frame, textvariable=proj_var, values=projects, width=10, state="readonly")
        proj_cb.pack(side=tk.LEFT, padx=2)

        # 业态
        tk.Label(filter_frame, text="业态：", font=("微软雅黑", 9), bg="white").pack(side=tk.LEFT, padx=(8, 0))
        fmt_var = tk.StringVar(value="全部")
        all_formats = sorted(set(r.get("_业态", "") for r in data if r.get("_业态")))
        fmt_cb = ttk.Combobox(filter_frame, textvariable=fmt_var, values=["全部"] + all_formats, width=8, state="readonly")
        fmt_cb.pack(side=tk.LEFT, padx=2)

        # 刷新按钮
        ttk.Button(filter_frame, text="🔍 查询", command=lambda: self._refresh_dashboard(
            data, gran_var, ds_var, de_var, proj_var, fmt_var, table_frame, chart_frame, summary_frame
        )).pack(side=tk.LEFT, padx=12)

        # ── 汇总卡片区 ──
        summary_frame = tk.Frame(self.content, bg="#f0f2f5")
        summary_frame.pack(fill="x", padx=12, pady=(8, 0))

        # ── 图表区 ──
        chart_frame = tk.Frame(self.content, bg="white", relief="solid", bd=1)
        chart_frame.pack(fill="x", padx=12, pady=8)
        chart_frame.pack_propagate(False)
        chart_frame.configure(height=280)

        # ── 商铺列表区 ──
        table_frame = tk.Frame(self.content, bg="white", relief="solid", bd=1)
        table_frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # 首次渲染
        self._refresh_dashboard(data, gran_var, ds_var, de_var, proj_var, fmt_var,
                                table_frame, chart_frame, summary_frame)

    def _refresh_dashboard(self, data, gran_var, ds_var, de_var, proj_var, fmt_var,
                           table_frame, chart_frame, summary_frame):
        """根据当前筛选条件刷新看板"""
        granularity = gran_var.get()
        ds = ds_var.get().strip()
        de = de_var.get().strip()
        project   = proj_var.get()
        bfmt      = fmt_var.get()

        # 筛选数据
        filtered = list(data)
        if ds:
            filtered = [r for r in filtered if r.get("日期", "") >= ds]
        if de:
            filtered = [r for r in filtered if r.get("日期", "") <= de]
        if project and project != "全部":
            filtered = [r for r in filtered if r.get("_项目", "") == project]
        if bfmt and bfmt != "全部":
            filtered = [r for r in filtered if r.get("_业态", "") == bfmt]

        # 按店铺分组
        shop_groups = defaultdict(list)
        for r in filtered:
            key = r.get("商户名称", "")
            shop_groups[key].append(r)

        # ── 计算总览指标 ──
        total_footfall   = sum(r.get("_客流量", 0) for r in filtered)
        total_sales      = sum(r.get("_营业额", 0) for r in filtered)
        total_deals      = sum(int(r.get("_成交量", 0)) for r in filtered)
        conversion_rate  = round(total_deals / total_footfall * 100, 1) if total_footfall > 0 else 0.0

        total_area = 0.0
        seen_shops = set()
        for r in filtered:
            n = r.get("商户名称", "")
            if n not in seen_shops:
                seen_shops.add(n)
                total_area += r.get("_面积", 0)
        pingxiao = round(total_sales / total_area, 2) if total_area > 0 else 0.0

        # 环比 / 同比
        agg = self._agg_by_period(filtered, granularity)
        current_period_sum = sum(p[3] for p in agg)  # 营业额
        mom_val, yoy_val = 0.0, 0.0
        if agg:
            # 取最后一个 period 算环比同比
            last_period = agg[-1]
            label = last_period[0]
            p_start = last_period[1]
            p_end   = last_period[2]
            p_len   = (p_end - p_start).days + 1
            prev_start = p_start - timedelta(days=p_len)
            prev_end   = p_start - timedelta(days=1)
            same_start = p_start - timedelta(days=365)
            same_end   = p_end - timedelta(days=365)

            prev_data   = [r for r in data if prev_start.strftime("%Y-%m-%d") <= r.get("日期", "") <= prev_end.strftime("%Y-%m-%d")]
            same_data   = [r for r in data if same_start.strftime("%Y-%m-%d") <= r.get("日期", "") <= same_end.strftime("%Y-%m-%d")]
            prev_sum    = sum(r.get("_营业额", 0) for r in prev_data)
            same_sum    = sum(r.get("_营业额", 0) for r in same_data)
            mom_val, yoy_val = self._calc_mom_yoy(last_period[3], prev_sum, same_sum)

        # ── 清空并重绘汇总卡片 ──
        for w in summary_frame.winfo_children():
            w.destroy()

        def _fmt(v):
            if isinstance(v, float):
                if abs(v) >= 10000:
                    return f"{v/10000:.1f}万"
                return f"{v:,.2f}"
            return str(v)

        cards_data = [
            ("进店客流", f"{total_footfall:,} 人次", "#2980b9"),
            ("销售额", f"¥{_fmt(total_sales)}", "#27ae60"),
            ("成单数量", f"{total_deals:,} 单", "#8e44ad"),
            ("转化率", f"{conversion_rate}%", "#e67e22"),
            ("坪效", f"¥{_fmt(pingxiao)}/㎡", "#2c3e50"),
            ("环比", f"{mom_val:+.1f}%" if mom_val else "—", "#c0392b" if mom_val < 0 else "#27ae60"),
            ("同比", f"{yoy_val:+.1f}%" if yoy_val else "—", "#c0392b" if yoy_val < 0 else "#27ae60"),
        ]
        for i, (title, val, color) in enumerate(cards_data):
            card = tk.Frame(summary_frame, bg="white", relief="solid", bd=1, padx=4, pady=3)
            card.pack(side=tk.LEFT, fill="both", expand=True, padx=1)
            tk.Label(card, text=title, font=("微软雅黑", 8), fg="#999", bg="white").pack(anchor="center")
            tk.Label(card, text=val, font=("黑体", 16, "bold"), fg=color, bg="white").pack(anchor="center")

        # ── 图表区 ──
        for w in chart_frame.winfo_children():
            w.destroy()

        if agg and len(agg) >= 1:
            try:
                import matplotlib
                matplotlib.use("TkAgg")
                import matplotlib.pyplot as plt
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
                plt.rcParams["axes.unicode_minus"] = False

                fig = plt.Figure(figsize=(8, 2.4), dpi=100)
                fig.patch.set_facecolor("#ffffff")

                labels = [p[0] for p in agg[-20:]]
                sales  = [p[3] for p in agg[-20:]]
                deals  = [p[5] for p in agg[-20:]]

                ax1 = fig.add_subplot(111)
                bars = ax1.bar(range(len(labels)), sales, color="#74b9d9", width=0.55, label="销售额(元)")
                ax1.set_xticks(range(len(labels)))
                ax1.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
                ax1.set_ylabel("销售额", fontsize=8, color="#2980b9")
                ax1.tick_params(axis="y", labelcolor="#2980b9", labelsize=7)

                ax2 = ax1.twinx()
                ax2.plot(range(len(labels)), deals, "o-", color="#e67e22", linewidth=1.8, markersize=4, label="成交量(单)")
                ax2.set_ylabel("成交量", fontsize=8, color="#e67e22")
                ax2.tick_params(axis="y", labelcolor="#e67e22", labelsize=7)

                for i, (s, d) in enumerate(zip(sales, deals)):
                    if s > 0:
                        ax1.text(i, s, f"{s/10000:.1f}w" if s >= 10000 else f"{s:,.0f}",
                                ha="center", va="bottom", fontsize=6, color="#2980b9")
                    if d > 0:
                        ax2.text(i, d, str(d), ha="center", va="bottom", fontsize=6, color="#e67e22")

                ax1.set_title(f"经营趋势 ({granularity})", fontsize=10, fontweight="bold", color="#333")
                fig.tight_layout()

                canvas = FigureCanvasTkAgg(fig, master=chart_frame)
                canvas.draw()
                canvas.get_tk_widget().pack(fill="both", expand=True)
            except ImportError:
                tk.Label(chart_frame, text="⚠️ 图表需要 matplotlib 库\npip install matplotlib",
                        font=("微软雅黑", 10), fg="#999", bg="white").pack(expand=True)
            except Exception as e:
                tk.Label(chart_frame, text=f"图表渲染失败: {e}",
                        font=("微软雅黑", 9), fg="#c0392b", bg="white").pack(expand=True)
        else:
            tk.Label(chart_frame, text="暂无数据可绘图", font=("微软雅黑", 10),
                    fg="#999", bg="white").pack(expand=True)

        # ── 商铺列表 ──
        for w in table_frame.winfo_children():
            w.destroy()

        # 表头
        cols = ["商铺", "业态", "项目", "面积(㎡)", "进店客流", "销售额", "成单", "转化率", "坪效"]
        tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="none")
        col_widths = [130, 70, 110, 70, 80, 100, 60, 70, 80]
        for c, w in zip(cols, col_widths):
            tree.heading(c, text=c)
            tree.column(c, width=w, anchor="center")
        tree.heading("商铺", text="商铺")
        tree.column("商铺", anchor="w")

        vs = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side=tk.LEFT, fill="both", expand=True)
        vs.pack(side=tk.RIGHT, fill="y")

        # 各行数据
        for name, recs in sorted(shop_groups.items()):
            f_sum = sum(r.get("_客流量", 0) for r in recs)
            s_sum = sum(r.get("_营业额", 0) for r in recs)
            d_sum = sum(int(r.get("_成交量", 0)) for r in recs)
            conv  = round(d_sum / f_sum * 100, 1) if f_sum > 0 else 0.0
            area  = recs[0].get("_面积", 0)
            px    = round(s_sum / area, 2) if area > 0 else 0.0
            proj  = recs[0].get("_项目", "")
            fmt2  = recs[0].get("_业态", "")
            tree.insert("", "end", values=[
                name, fmt2, proj, f"{area:.1f}" if area else "—",
                f"{f_sum:,}", f"¥{s_sum:,.0f}", f"{d_sum:,}",
                f"{conv}%", f"¥{px:,.2f}"
            ])

    # ──────────── 每日经营情况（内嵌主页） ────────────
    def _render_home_biz_section(self, parent):
        """在主页租金总览下方渲染每日经营情况看板（无筛选，仅 TOP10 切换）"""
        biz_data, all_shops, all_contracts = self._load_biz_dashboard_data()

        # 缓存到实例变量，供 _refresh_home_biz 复用
        self._biz_data       = biz_data
        self._biz_shops      = all_shops
        self._biz_contracts  = all_contracts

        # 外层容器
        biz_frame = tk.Frame(parent, bg="#f0f2f5")
        biz_frame.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        if not biz_data:
            empty = tk.Frame(biz_frame, bg="white", relief="solid", bd=1)
            empty.pack(fill="x")
            tk.Label(empty, text="📊  每日经营情况", font=("微软雅黑", 11, "bold"),
                     fg="#333", bg="white").pack(anchor="w", padx=14, pady=(10, 0))
            tk.Label(empty, text="暂无经营数据，请先在「📋 经营数据」中添加",
                     font=("微软雅黑", 10), fg="#999", bg="white").pack(pady=10)
            return

        # 计算最新数据日期 + 星期
        all_dates = [r.get("日期", "") for r in biz_data if r.get("日期")]
        latest_date_str = max(all_dates) if all_dates else date.today().strftime("%Y-%m-%d")

        # ── 标题行（日期选择器在右侧） ──
        title_bar = tk.Frame(biz_frame, bg="white", relief="solid", bd=1)
        title_bar.pack(fill="x")

        def _fmt_title(ds, project=""):
            try:
                dt = datetime.strptime(ds, "%Y-%m-%d")
                weekdays_cn = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
                base = f"📊  每日经营情况（{ds} {weekdays_cn[dt.weekday()]}）"
                if project and project != "所有项目":
                    return f"{base} - {project}"
                return base
            except Exception:
                return "📊  每日经营情况"

        title_label = tk.Label(title_bar, text=_fmt_title(latest_date_str, ""),
                               font=("微软雅黑", 11, "bold"), fg="#333", bg="white")
        title_label.pack(side=tk.LEFT, padx=14, pady=(10, 2))

        # 项目筛选（日期左侧）
        project_filter_frame = tk.Frame(title_bar, bg="white")
        project_filter_frame.pack(side=tk.RIGHT, padx=(0, 10), pady=(10, 2))

        # 获取所有项目列表
        all_projects = sorted(set(s.get("所属项目", "") for s in all_shops if s.get("所属项目", "")))
        project_values = ["所有项目"] + all_projects

        tk.Label(project_filter_frame, text="项目：", font=("微软雅黑", 9), fg="#888", bg="white").pack(side=tk.LEFT)
        project_var = tk.StringVar(value="所有项目")
        project_combo = ttk.Combobox(project_filter_frame, textvariable=project_var,
                                      values=project_values, state="readonly", width=12)
        project_combo.pack(side=tk.LEFT, padx=2)

        date_picker_frame = tk.Frame(title_bar, bg="white")
        date_picker_frame.pack(side=tk.RIGHT, padx=(0, 14), pady=(10, 2))
        tk.Label(date_picker_frame, text="日期：", font=("微软雅黑", 9), fg="#888", bg="white").pack(side=tk.LEFT)
        sel_date_var = tk.StringVar(value=latest_date_str)
        sel_date_entry = ttk.Entry(date_picker_frame, textvariable=sel_date_var, state="readonly", width=11, cursor="arrow")
        sel_date_entry.pack(side=tk.LEFT, padx=2)
        sel_date_entry.bind("<Button-1>", lambda e: PopupCalendar(title_bar, sel_date_var.set))

        # ── 第一行：左侧 KPI+饼图叠放 ｜ 右侧折线图撑满 ──
        main_row = tk.Frame(biz_frame, bg="#f0f2f5")
        main_row.pack(fill="both", expand=True)
        main_row.columnconfigure(0, weight=2)  # 左侧 40%
        main_row.columnconfigure(1, weight=3)  # 右侧 60%
        main_row.rowconfigure(0, weight=1)

        # 左侧列：KPI（上）+ TOP10（下）
        left_col = tk.Frame(main_row, bg="#f0f2f5")
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        kpi_container = tk.Frame(left_col, bg="white", relief="solid", bd=1)
        kpi_container.pack(side=tk.TOP, fill="x")

        top10_frame = tk.Frame(left_col, bg="white", relief="solid", bd=1)
        top10_frame.pack(side=tk.TOP, fill="both", expand=True, pady=(4, 0))

        # 右侧列：折线图（撑满高度）
        right_col = tk.Frame(main_row, bg="white", relief="solid", bd=1)
        right_col.grid(row=0, column=1, sticky="nsew")

        line_chart_frame = tk.Frame(right_col, bg="white")
        line_chart_frame.pack(fill="both", expand=True)

        # ── main_row 第二行：业态条形图(row=1,col=0) + 业态排名(row=1,col=1) ──
        # 与 row=0 共享同一套 columnconfigure，列宽强制对齐
        main_row.rowconfigure(1, weight=0)

        pie_chart_frame = tk.Frame(main_row, bg="white", relief="solid", bd=1)
        pie_chart_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 4), pady=(4, 0))

        format_rank_frame = tk.Frame(main_row, bg="white", relief="solid", bd=1)
        format_rank_frame.grid(row=1, column=1, sticky="nsew", padx=(0, 0), pady=(4, 0))

        # ── 第四行：商铺明细表（全宽） ──
        shop_table_frame = tk.Frame(biz_frame, bg="white", relief="solid", bd=1)
        shop_table_frame.pack(fill="both", expand=True)

        top10_var = tk.StringVar(value="销售额")

        # 日期/项目切换刷新回调
        def _on_filter_change(*args):
            ds = sel_date_var.get()
            proj = project_var.get()
            if ds:
                title_label.config(text=_fmt_title(ds, proj))
            else:
                title_label.config(text=_fmt_title("", proj))
            self._refresh_home_biz(kpi_container, line_chart_frame, pie_chart_frame,
                                   shop_table_frame, top10_frame, format_rank_frame, top10_var,
                                   selected_date_str=ds if ds else None,
                                   selected_project=proj if proj != "所有项目" else None)

        sel_date_var.trace_add("write", _on_filter_change)
        project_var.trace_add("write", _on_filter_change)

        # 首次渲染
        self._refresh_home_biz(kpi_container, line_chart_frame, pie_chart_frame,
                               shop_table_frame, top10_frame, format_rank_frame, top10_var,
                               selected_date_str=latest_date_str,
                               selected_project=None)

    def _refresh_home_biz(self, kpi_row, line_chart_frame, pie_chart_frame,
                          shop_table_frame, top10_frame, format_rank_frame, top10_var,
                          selected_date_str=None, selected_project=None):
        """无筛选条件刷新每日经营情况的 KPI、图表和表格"""
        data = getattr(self, "_biz_data", [])

        # 项目筛选：根据项目名称过滤数据（直接影响周趋势图等全局计算）
        if selected_project:
            data = [r for r in data if r.get("_项目", "") == selected_project]

        # ── 确定日期（优先使用传入日期） ──
        if selected_date_str:
            latest_date = selected_date_str
        else:
            all_dates = [r.get("日期", "") for r in data if r.get("日期")]
            latest_date = max(all_dates) if all_dates else date.today().strftime("%Y-%m-%d")

        # 最新日期 + 前一日 + 上周同日
        try:
            latest_dt = datetime.strptime(latest_date, "%Y-%m-%d")
            prev_dt   = latest_dt - timedelta(days=1)
            last_wk_dt = latest_dt - timedelta(days=7)
            prev_date   = prev_dt.strftime("%Y-%m-%d")
            last_wk_date = last_wk_dt.strftime("%Y-%m-%d")
        except Exception:
            prev_date   = ""
            last_wk_date = ""

        # 筛选最新日期 + 前一日 + 上周同日 数据
        latest_records  = [r for r in data if r.get("日期", "") == latest_date]
        prev_records    = [r for r in data if r.get("日期", "") == prev_date]
        last_wk_records = [r for r in data if r.get("日期", "") == last_wk_date]

        # 项目筛选：直接根据 _项目 字段过滤（数据加载时已补全该字段）
        if selected_project:
            latest_records  = [r for r in latest_records  if r.get("_项目", "") == selected_project]
            prev_records    = [r for r in prev_records    if r.get("_项目", "") == selected_project]
            last_wk_records = [r for r in last_wk_records if r.get("_项目", "") == selected_project]

        # ── 计算 KPI（最新日期当日汇总） ──
        total_footfall = sum(r.get("_客流量", 0) for r in latest_records)
        total_sales    = sum(r.get("_营业额", 0) for r in latest_records)
        total_deals    = sum(int(r.get("_成交量", 0)) for r in latest_records)
        conv_rate      = round(total_deals / total_footfall * 100, 1) if total_footfall > 0 else 0.0

        seen = set()
        total_area = 0.0
        for r in latest_records:
            n = r.get("商户名称", "")
            if n not in seen:
                seen.add(n)
                total_area += r.get("_面积",0)
        px = round(total_sales / total_area, 2) if total_area > 0 else 0.0

        # 日环比 / 同比上周（基于销售额）
        prev_sales = sum(r.get("_营业额", 0) for r in prev_records)
        last_wk_sales = sum(r.get("_营业额", 0) for r in last_wk_records)
        mom_val, wow_val = self._calc_mom_yoy(total_sales, prev_sales, last_wk_sales)

        # 本周累计 / 本月累计（以选定日期为基准）
        this_monday = latest_dt - timedelta(days=latest_dt.weekday())
        this_month_start = latest_dt.replace(day=1)
        this_week_total = sum(r.get("_营业额", 0) for r in data
                              if r.get("日期", "") and this_monday.strftime("%Y-%m-%d") <= r["日期"] <= latest_date)
        this_month_total = sum(r.get("_营业额", 0) for r in data
                               if r.get("日期", "") and this_month_start.strftime("%Y-%m-%d") <= r["日期"] <= latest_date)

        def _fmt(v):
            if isinstance(v, float):
                if abs(v) >= 10000:
                    return f"{v/10000:.1f}万"
                return f"{v:,.2f}"
            return str(v)

        # ── 刷新 KPI 卡片（2×4 grid 布局） ──
        for w in kpi_row.winfo_children():
            w.destroy()

        kpi_grid = tk.Frame(kpi_row, bg="white")
        kpi_grid.pack(fill="both", expand=True, padx=2, pady=2)

        for i in range(2):
            kpi_grid.rowconfigure(i, weight=1)
        for i in range(3):
            kpi_grid.columnconfigure(i, weight=1)

        cards = [
            ("进店客流", f"{total_footfall:,} 人次", "#2980b9"),
            ("销售额",   f"￥{_fmt(total_sales)}",  "#2980b9"),
            (
                "日环比", f"{mom_val:+.1f}%" if mom_val else "—",
                "#2980b9" if mom_val == 0 or not mom_val else ("#c0392b" if mom_val > 0 else "#27ae60"),
            ),
            (
                "同比上周", f"{wow_val:+.1f}%" if wow_val else "—",
                "#2980b9" if wow_val == 0 or not wow_val else ("#c0392b" if wow_val > 0 else "#27ae60"),
            ),
            ("本周累计", f"￥{_fmt(this_week_total)}", "#2980b9"),
            ("本月累计", f"￥{_fmt(this_month_total)}", "#2980b9"),
        ]
        for idx, (title, val, color) in enumerate(cards):
            r, c = divmod(idx, 3)
            card = tk.Frame(kpi_grid, bg="white", relief="solid", bd=1)
            card.grid(row=r, column=c, sticky="ew", padx=1, pady=1, ipady=6)
            tk.Label(card, text=title, font=("微软雅黑", 8), fg="#999", bg="white").pack(anchor="center")
            tk.Label(card, text=val, font=("黑体", 20, "bold"), fg=color, bg="white").pack(anchor="center")

        # ── 按日汇总销售额（全量数据） ──
        daily_sales = defaultdict(float)
        for r in data:
            d = r.get("日期", "")
            if d:
                daily_sales[d] += r.get("_营业额", 0)

        # ── 本周 vs 上周（以选定日期所在自然周为基准：周一 ~ 周日） ──
        ref_dt = latest_dt  # 跟随选定日期，而非 date.today()
        this_monday = ref_dt - timedelta(days=ref_dt.weekday())
        last_monday = this_monday - timedelta(days=7)

        week_labels = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        this_week_vals = []
        last_week_vals = []
        for i in range(7):
            day = this_monday + timedelta(days=i)
            day_str = day.strftime("%Y-%m-%d")
            v = daily_sales.get(day_str, 0)
            this_week_vals.append(v if v > 0 else float("nan"))
            lday = last_monday + timedelta(days=i)
            lv = daily_sales.get(lday.strftime("%Y-%m-%d"), 0)
            last_week_vals.append(lv if lv > 0 else float("nan"))

        # ── 绘制周销售额趋势折线图 ──
        for w in line_chart_frame.winfo_children():
            w.destroy()
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
            plt.rcParams["axes.unicode_minus"] = False

            fig = plt.Figure(figsize=(6.0, 3.5), dpi=100)
            fig.patch.set_facecolor("#ffffff")
            ax = fig.add_subplot(111)

            x_range = range(7)
            ax.plot(x_range, this_week_vals, "o-", color="#2980b9", linewidth=2.5,
                   markersize=7, label="本周", zorder=5)
            ax.plot(x_range, last_week_vals, "s--", color="#95a5a6", linewidth=1.8,
                   markersize=6, label="上周", zorder=4)

            # 本周数据标签（上方 + 引导线）
            for i, v in enumerate(this_week_vals):
                if v != v:  # NaN 跳过
                    continue
                ax.annotate(f"{v/10000:.0f}万", xy=(i, v),
                           xytext=(0, 10), textcoords="offset points",
                           ha="center", va="bottom", fontsize=7.5, color="#2980b9",
                           arrowprops=dict(arrowstyle="-", color="#b0c4de", lw=0.6),
                           zorder=6)

            # 上周数据标签（下方 + 引导线）
            for i, v in enumerate(last_week_vals):
                if v != v:  # NaN 跳过
                    continue
                ax.annotate(f"{v/10000:.0f}万", xy=(i, v),
                           xytext=(0, -10), textcoords="offset points",
                           ha="center", va="top", fontsize=7, color="#95a5a6",
                           arrowprops=dict(arrowstyle="-", color="#d3d3d3", lw=0.5),
                           zorder=6)

            # 自动扩展 y 轴留出标签空间
            all_valid = [v for v in this_week_vals + last_week_vals if not (v != v)]
            if all_valid:
                y_max = max(all_valid) * 1.25
                y_min = min(all_valid) * 0.5
                ax.set_ylim(bottom=max(0, y_min), top=max(y_max, 1))

            ax.set_xticks(list(x_range))
            ax.set_xticklabels(week_labels, fontsize=8.5)
            ax.set_ylabel("销售额(元)", fontsize=9, color="#333")
            ax.tick_params(axis="y", labelsize=8)
            ax.set_title("周销售额趋势", fontsize=12, fontweight="bold", color="#333")
            ax.legend(fontsize=8, loc="upper left")
            ax.grid(axis="y", alpha=0.3)
            fig.subplots_adjust(left=0.10, right=0.93, top=0.88, bottom=0.18)
            fig.tight_layout(pad=0.8)

            canvas = FigureCanvasTkAgg(fig, master=line_chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
        except ImportError:
            tk.Label(line_chart_frame, text="⚠️ matplotlib 未安装\npip install matplotlib",
                    font=("微软雅黑", 9), fg="#999", bg="white").pack(expand=True)
        except Exception as e:
            tk.Label(line_chart_frame, text=f"图表错误: {e}",
                    font=("微软雅黑", 8), fg="#c0392b", bg="white").pack(expand=True)

        # ── 绘制业态饼图（最新日期当日） ──
        for w in pie_chart_frame.winfo_children():
            w.destroy()
        fmt_sales = defaultdict(float)
        for r in latest_records:
            fmt = r.get("_业态", "")
            if not fmt:
                fmt = "未知"
            fmt_sales[fmt] += r.get("_营业额", 0)
        if fmt_sales:
            try:
                import matplotlib
                matplotlib.use("TkAgg")
                import matplotlib.pyplot as plt
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
                plt.rcParams["axes.unicode_minus"] = False

                import numpy as np

                fig2 = plt.Figure(figsize=(4.8, 2.4), dpi=100)
                fig2.patch.set_facecolor("#ffffff")
                ax2 = fig2.add_subplot(111)
                labels = list(fmt_sales.keys())
                values = list(fmt_sales.values())
                total = sum(values)
                colors = ["#2980b9", "#27ae60", "#e67e22", "#8e44ad", "#c0392b", "#16a085", "#2c3e50", "#f39c12"]

                # 按值降序排列
                sorted_items = sorted(zip(labels, values, colors), key=lambda x: x[1], reverse=True)
                sorted_labels = [x[0] for x in sorted_items]
                sorted_values = [x[1] for x in sorted_items]
                sorted_colors = [x[2] for x in sorted_items]

                bars = ax2.barh(range(len(sorted_labels)), sorted_values, height=0.55,
                               color=sorted_colors, edgecolor="white", linewidth=0.5)
                ax2.set_yticks(range(len(sorted_labels)))
                ax2.set_yticklabels(sorted_labels, fontsize=8)
                ax2.invert_yaxis()  # 最大在上面
                ax2.set_xlim(0, max(sorted_values) * 1.35)
                ax2.tick_params(axis="x", labelsize=7, colors="#999")
                ax2.tick_params(axis="y", pad=2)
                ax2.set_frame_on(False)
                ax2.xaxis.set_visible(False)

                # 条尾标注：金额 + 占比
                for bar, val in zip(bars, sorted_values):
                    pct = val / total * 100 if total else 0
                    ax2.text(bar.get_width() + max(sorted_values) * 0.02,
                            bar.get_y() + bar.get_height() / 2,
                            f"￥{val:,.0f}  {pct:.1f}%",
                            va="center", fontsize=7.5, color="#555")

                ax2.set_title("业态销售占比", fontsize=10, fontweight="bold", color="#333", pad=6)
                fig2.subplots_adjust(left=0.12, right=0.92, top=0.90, bottom=0.10)

                canvas2 = FigureCanvasTkAgg(fig2, master=pie_chart_frame)
                canvas2.draw()
                canvas2.get_tk_widget().pack(fill="both", expand=True)
            except ImportError:
                tk.Label(pie_chart_frame, text="⚠️ matplotlib 未安装",
                        font=("微软雅黑", 9), fg="#999", bg="white").pack(expand=True)
            except Exception as e:
                tk.Label(pie_chart_frame, text=f"饼图错误: {e}",
                        font=("微软雅黑", 8), fg="#c0392b", bg="white").pack(expand=True)
        else:
            # 占位容器保持与饼图 canvas 一致的宽度，防止第一行布局变形
            placeholder = tk.Frame(pie_chart_frame, bg="white", width=420, height=250)
            placeholder.pack(fill="both", expand=True)
            placeholder.pack_propagate(False)
            tk.Label(placeholder, text="暂无数据", font=("微软雅黑", 9),
                    fg="#999", bg="white").pack(expand=True)

        # ── 构建商铺对比数据字典（前一日 / 上周同日） ──
        prev_map = {}    # {商铺名: {"_营业额":, "_成交量":, "_客流量":}}
        last_wk_map = {}
        for r in prev_records:
            name = r.get("商户名称", "")
            if name not in prev_map:
                prev_map[name] = r
        for r in last_wk_records:
            name = r.get("商户名称", "")
            if name not in last_wk_map:
                last_wk_map[name] = r

        def _dod_rate(cur_val, prev_val):
            if prev_val and prev_val != 0:
                return round((cur_val - prev_val) / prev_val * 100, 1)
            return None

        # ── 刷新商铺表格（加小标题 + 日环比 + 同比上周 + 涨红跌绿） ──
        for w in shop_table_frame.winfo_children():
            w.destroy()

        # 小标题
        subtitle = tk.Frame(shop_table_frame, bg="white")
        subtitle.pack(fill="x")
        tk.Label(subtitle, text="🏪  商铺经营明细", font=("微软雅黑", 10, "bold"),
                 fg="#333", bg="white").pack(anchor="w", padx=10, pady=(6, 2))

        shop_latest = {}
        for r in latest_records:
            name = r.get("商户名称", "")
            if name not in shop_latest:
                shop_latest[name] = r

        shop_rows = []
        for name, r in shop_latest.items():
            s_sum   = r.get("_营业额", 0)
            d_sum   = int(r.get("_成交量", 0))
            f_sum   = r.get("_客流量", 0)
            conv    = round(d_sum / f_sum * 100, 1) if f_sum > 0 else 0.0
            avg_val = round(s_sum / d_sum, 2) if d_sum > 0 else 0.0
            area    = r.get("_面积", 0)
            px_val  = round(s_sum / area, 2) if area > 0 else 0.0
            fmt2    = r.get("_业态", "")

            # 前一日对比
            pr = prev_map.get(name, {})
            ps = pr.get("_营业额", None)
            dod = _dod_rate(s_sum, ps) if ps is not None else None

            # 上周同日对比
            lr = last_wk_map.get(name, {})
            ls = lr.get("_营业额", None)
            wow = _dod_rate(s_sum, ls) if ls is not None else None

            shop_rows.append((s_sum, name, fmt2, d_sum, avg_val, conv, px_val, dod, wow))
        shop_rows.sort(key=lambda x: x[0], reverse=True)

        row_count = len(shop_rows)
        tree_height = max(row_count, 1)

        cols = ["商铺", "业态", "销售额", "成单", "客单价", "转化率", "日坪效", "日环比", "同比上周"]
        tree = ttk.Treeview(shop_table_frame, columns=cols, show="headings",
                           selectmode="none", height=tree_height)
        tree.pack(fill="both", expand=True)

        col_widths = [100, 55, 85, 45, 60, 50, 80, 52, 55]
        for c, w in zip(cols, col_widths):
            tree.heading(c, text=c)
            tree.column(c, width=w, anchor="center")
        tree.heading("商铺", text="商铺")
        tree.column("商铺", anchor="w")

        for s_sum, name, fmt2, d_sum, avg_val, conv, px_val, dod, wow in shop_rows:
            # 日环比 / 同比上周用 ▲▼ 符号标记涨跌（仅这两列生效）
            if dod is not None:
                symbol = "▲" if dod > 0 else ("▼" if dod < 0 else "●")
                dod_str = f"{symbol} {dod:+.1f}%"
            else:
                dod_str = "—"
            if wow is not None:
                symbol = "▲" if wow > 0 else ("▼" if wow < 0 else "●")
                wow_str = f"{symbol} {wow:+.1f}%"
            else:
                wow_str = "—"

            tree.insert("", "end", values=[
                name, fmt2, f"￥{s_sum:,.0f}",
                f"{d_sum:,}", f"￥{avg_val:,.2f}", f"{conv}%", f"￥{px_val:,.2f}/㎡·天",
                dod_str, wow_str
            ])

        # ── 刷新 TOP10 排行表（用最新日期当日数据） ──
        for w in top10_frame.winfo_children():
            w.destroy()

        # TOP10 标题 + 切换栏
        top10_header = tk.Frame(top10_frame, bg="white")
        top10_header.pack(fill="x", padx=6, pady=(4, 0))
        tk.Label(top10_header, text="🏆 TOP10", font=("微软雅黑", 10, "bold"),
                 fg="black", bg="white").pack(side=tk.LEFT)

        def _switch_top10():
            self._render_top10_table(top10_frame, latest_records, top10_var.get())

        # 创建切换按钮（无背景色，无蓝色圆圈）
        for metric in ["销售额", "进店客流", "日坪效", "转化率"]:
            tk.Radiobutton(top10_header, text=metric, variable=top10_var,
                           value=metric, command=_switch_top10,
                           fg="#333333",
                           font=("微软雅黑", 9),
                           selectcolor="white",
                           relief="flat",
                           padx=8, pady=2,
                           borderwidth=0,
                           bg="white",
                           activebackground="white").pack(side=tk.LEFT, padx=4)

        self._render_top10_table(top10_frame, latest_records, top10_var.get())

        # ── 渲染业态排名表 ──
        self._render_format_rank_table(format_rank_frame, latest_records, prev_records, last_wk_records)

    def _render_top10_table(self, parent, records, metric):
        """在给定容器中渲染 TOP10 排行表"""
        # 清空表格区（保留 header）
        children = parent.winfo_children()
        for c in children:
            if isinstance(c, ttk.Treeview) or isinstance(c, ttk.Scrollbar) or isinstance(c, tk.Frame):
                # 只杀表格和滚动条，保留 header（通常是最先 pack 的那个 Frame）
                if isinstance(c, tk.Frame) and c.winfo_children():
                    # 检查是不是 header
                    has_label = False
                    for sub in c.winfo_children():
                        if isinstance(sub, tk.Label):
                            has_label = True
                            break
                    if has_label:
                        continue
                c.destroy()

        table_area = tk.Frame(parent, bg="white")
        table_area.pack(fill="both", expand=True, padx=0, pady=(0, 0))

        # 按商户汇总
        shop_agg = {}
        for r in records:
            name = r.get("商户名称", "")
            if name not in shop_agg:
                shop_agg[name] = {"销售额": 0.0, "客流量": 0, "成交量": 0, "_业态": r.get("_业态", ""), "_area": r.get("_面积", 0)}
            shop_agg[name]["销售额"] += r.get("_营业额", 0)
            shop_agg[name]["客流量"] += r.get("_客流量", 0)
            shop_agg[name]["成交量"] += int(r.get("_成交量", 0))

        # 计算各项指标
        rows = []
        for name, v in shop_agg.items():
            px_val = round(v["销售额"] / v["_area"], 2) if v["_area"] > 0 else 0.0
            conv   = round(v["成交量"] / v["客流量"] * 100, 1) if v["客流量"] > 0 else 0.0
            rows.append({
                "商铺": name,
                "业态": v["_业态"],
                "销售额": v["销售额"],
                "进店客流": v["客流量"],
                "坪效": px_val,
                "转化率": conv,
            })

        key_map = {"销售额": "销售额", "进店客流": "进店客流", "日坪效": "坪效", "转化率": "转化率"}
        sort_key = key_map.get(metric, "销售额")
        rows.sort(key=lambda x: x[sort_key], reverse=True)
        top10 = rows[:10]

        cols = ["排名", "商铺", "业态", metric]
        tree = ttk.Treeview(table_area, columns=cols, show="headings", selectmode="none", height=10)
        col_widths = [40, 90, 55, 85]
        for c, w in zip(cols, col_widths):
            tree.heading(c, text=c)
            tree.column(c, width=w, anchor="center")
        tree.heading("商铺", text="商铺")
        tree.column("商铺", anchor="w")

        # 10 行全部显示，不需要滚动条
        tree.pack(fill="both", expand=True)

        for i, row in enumerate(top10):
            val = row[key_map.get(metric, metric)]
            if metric == "销售额":
                disp = f"￥{val:,.0f}"
            elif metric == "日坪效":
                disp = f"￥{val:,.2f}/㎡·天"
            elif metric == "转化率":
                disp = f"{val}%"
            else:
                disp = f"{val:,}"
            tree.insert("", "end", values=[i + 1, row["商铺"], row["业态"], disp])

    def _render_format_rank_table(self, parent, latest_records, prev_records, last_wk_records):
        """渲染业态排名表：业态、销售额、日环比、同比上周"""
        # 清空
        for w in parent.winfo_children():
            w.destroy()

        # 标题
        tk.Label(parent, text="🏷 业态排名", font=("微软雅黑", 10, "bold"),
                 fg="#333", bg="white").pack(anchor="w", padx=8, pady=(6, 2))

        # 按业态汇总最新日期销售额
        fmt_sales = defaultdict(float)
        for r in latest_records:
            fmt = r.get("_业态", "") or "未知"
            fmt_sales[fmt] += r.get("_营业额", 0)

        # 前一日业态销售额
        prev_fmt = defaultdict(float)
        for r in prev_records:
            fmt = r.get("_业态", "") or "未知"
            prev_fmt[fmt] += r.get("_营业额", 0)

        # 上周同日业态销售额
        last_wk_fmt = defaultdict(float)
        for r in last_wk_records:
            fmt = r.get("_业态", "") or "未知"
            last_wk_fmt[fmt] += r.get("_营业额", 0)

        # 排序
        fmt_rows = sorted(fmt_sales.items(), key=lambda x: x[1], reverse=True)

        cols = ["业态", "销售额", "日环比", "同比上周"]
        tree = ttk.Treeview(parent, columns=cols, show="headings", selectmode="none", height=max(len(fmt_rows), 1))
        col_widths = [65, 90, 70, 70]
        for c, w in zip(cols, col_widths):
            tree.heading(c, text=c)
            tree.column(c, width=w, anchor="center")

        def _rate(cur, prev):
            if prev and prev != 0:
                return round((cur - prev) / prev * 100, 1)
            return None

        for fmt, s_sum in fmt_rows:
            mom = _rate(s_sum, prev_fmt.get(fmt, 0))
            wow = _rate(s_sum, last_wk_fmt.get(fmt, 0))

            mom_str = f"▲ {mom:+.1f}%" if mom is not None and mom > 0 else (
                      f"▼ {mom:+.1f}%" if mom is not None and mom < 0 else (
                      f"● {mom:+.1f}%" if mom is not None else "—"))
            wow_str = f"▲ {wow:+.1f}%" if wow is not None and wow > 0 else (
                      f"▼ {wow:+.1f}%" if wow is not None and wow < 0 else (
                      f"● {wow:+.1f}%" if wow is not None else "—"))

            tree.insert("", "end", values=[fmt, f"￥{s_sum:,.0f}", mom_str, wow_str])

        tree.pack(fill="both", expand=True, padx=4, pady=(0, 4))

    # ──────────── 商户 Web 门户（升级时暂停/恢复） ────────────
    def _find_pid_on_port(self, port=5050):
        """查找占用指定端口的 PID，未占用返回 None"""
        try:
            output = subprocess.check_output(
                ["netstat", "-ano"], text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
        except Exception:
            return None
        for line in output.split("\n"):
            if f":{port}" in line and "LISTENING" in line:
                parts = line.strip().split()
                if parts:
                    return parts[-1]
        return None

    def _kill_portal_on_port(self):
        """杀掉占用 5050 的 Python 进程（只杀 Python 进程，不影响其他应用）"""
        pid = self._find_pid_on_port(5050)
        if not pid:
            return False
        try:
            # 先检查是不是 Python 进程
            detail = subprocess.check_output(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            if "python" not in detail.lower():
                messagebox.showwarning("商户门户", f"端口 5050 被非 Python 进程（PID={pid}）占用，无法自动停止")
                return False
            subprocess.call(
                ["taskkill", "/PID", pid, "/F"],
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            return True
        except Exception:
            return False

    def toggle_merchant_portal(self):
        """启动/暂停商户门户（仅集团角色可操作）"""
        if not self._portal_enabled:
            return
        pid_on_port = self._find_pid_on_port(5050)

        if pid_on_port:
            # 5050 上有进程在跑 → 执行暂停
            if self._kill_portal_on_port():
                self._portal_proc = None
                self._portal_btn_text.set("🌐 启动商户门户")
                self.portal_status_var.set("")
                messagebox.showinfo("商户门户", "已暂停商户门户服务\n升级完成后请重新启动")
            return

        # 5050 空闲 → 执行启动
        portal_script = os.path.join(SCRIPT_DIR, "merchant_portal.py")
        if not os.path.exists(portal_script):
            messagebox.showerror("错误", f"找不到商户门户文件：\n{portal_script}")
            return

        # 检测 flask 是否已安装
        try:
            import flask  # noqa: F401
        except ImportError:
            if messagebox.askyesno(
                "缺少依赖",
                "商户门户需要 Flask 库\n点击「是」自动安装（使用清华镜像），「否」取消"
            ):
                ret = subprocess.call([
                    sys.executable, "-m", "pip", "install",
                    "flask", "python-dateutil",
                    "-i", "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple",
                    "--trusted-host", "mirrors.tuna.tsinghua.edu.cn"
                ])
                if ret != 0:
                    messagebox.showerror("安装失败", "Flask 安装失败，请手动运行：\npip install flask python-dateutil")
                    return
            else:
                return

        # 在独立进程中启动 Flask
        self._portal_proc = subprocess.Popen(
            [sys.executable, portal_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )

        # 获取本机局域网 IP（用于提示）
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = "127.0.0.1"

        self._portal_btn_text.set("⏸ 暂停商户门户")
        self.portal_status_var.set(f"●运行中\n{local_ip}:5050")
        messagebox.showinfo(
            "商户门户已启动",
            f"商户 Web 门户已在后台启动！\n\n"
            f"本机访问：http://127.0.0.1:5050\n"
            f"手机访问（同一局域网）：\nhttp://{local_ip}:5050\n\n"
            f"商户使用【合同号 + 商户名称】登录\n\n"
            f"如需升级系统，请先点击「暂停商户门户」"
        )

    def _on_main_close(self):
        """关闭主窗口前清理门户进程"""
        self._kill_portal_on_port()
        self.root.destroy()

if __name__ == "__main__":
    from login_window import popup_login

    # 先弹出独立登录窗口（有自己的 Tk 实例，登录完自动销毁）
    user = popup_login()
    if user is None:
        sys.exit(0)

    # 登录成功，写入全局用户状态
    utils.CURRENT_USER = user

    # 创建主窗口并启动
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()
