import json
import os
import calendar
from datetime import datetime, date
import tkinter as tk
from tkinter import ttk, messagebox

from utils import (
    PopupCalendar, SCRIPT_DIR, PROJECT_OPTIONS, BUSINESS_TYPE,
    load_shops, save_shops, load_contracts, save_contracts, delete_contract,
    check_shop_no_exists,
    load_opportunities, save_opportunities
)
import utils

CONTRACT_STATUS  = ["待生效", "执行中", "已终止"]
PAYMENT_CYCLE = ["月度", "季度", "半年", "年度"]
DEPOSIT_STATUS = ["未支付", "部分支付", "已支付", "已退还"]

def _fuzzy_match(keyword, text):
    """模糊匹配：大小写不敏感子串匹配"""
    if not keyword:
        return True
    return keyword.lower() in str(text).lower()

CONTRACT_FIELD = [
    "合同号", "签约主体", "商户名称", "经营业态",
    "所属项目", "关联铺位号",
    "保底租金(元/㎡/天)", "提成租金扣点(%)", "租金模式",
    "物业服务费单价（元/㎡/天）",
    "签约日期", "租赁开始日期", "租赁结束日期",
    "免租期(天)", "剩余租期(天)", "押金", "押金支付状态",
    "支付周期", "合同状态", "终止日期", "联系电话", "联系人", "备注"
]

# ================== 工具函数 ==================
def get_occupied_shopnos():
    contracts = load_contracts()
    return [c["关联铺位号"] for c in contracts if c.get("合同状态") in ["待生效", "执行中", "即将到期"]]

def is_contract_no_exist(contract_no, exclude_id=None):
    for c in load_contracts():
        if c["合同号"] == contract_no and c["合同号"] != exclude_id:
            return True
    return False

def sync_shop_status():
    """根据合同状态自动同步铺位状态"""
    contracts = load_contracts()
    shops = load_shops()

    active_shops = set()
    for c in contracts:
        shop_no = (c.get("关联铺位号") or "").strip()
        status = c.get("合同状态", "")
        if shop_no and status in ["待生效", "执行中"]:
            active_shops.add(shop_no)

    all_contracted = set()
    for c in contracts:
        shop_no = (c.get("关联铺位号") or "").strip()
        if shop_no:
            all_contracted.add(shop_no)

    modified = False
    for shop in shops:
        shop_no = shop.get("铺位号", "")
        if shop_no in active_shops:
            if shop.get("铺位状态") != "已出租":
                shop["铺位状态"] = "已出租"
                modified = True
        elif shop_no in all_contracted:
            if shop.get("铺位状态") != "空置":
                shop["铺位状态"] = "空置"
                modified = True

    if modified:
        save_shops(shops)

def auto_expire_contracts():
    """遍历所有合同，租赁结束日期已过期且状态为「执行中」的自动改为「已到期」"""
    contracts = load_contracts()
    today = date.today()
    modified = False
    for c in contracts:
        status = c.get("合同状态", "")
        end_str = c.get("租赁结束日期", "")
        if status == "执行中" and end_str:
            try:
                end_dt = datetime.strptime(end_str, "%Y-%m-%d").date()
                if end_dt < today:
                    c["合同状态"] = "已到期"
                    c["剩余租期(天)"] = "0"
                    modified = True
            except:
                pass
    if modified:
        save_contracts(contracts)
    return modified

# ================== 主界面 ==================
class ContractManageGUI:
    def __init__(self, root):
        self.root = root
        self.all_shops = load_shops()
        self.all_contracts = load_contracts()
        auto_expire_contracts()
        self.all_contracts = load_contracts()
        self.filtered = self.all_contracts.copy()

        self.filter_business_types = {t: tk.BooleanVar() for t in BUSINESS_TYPE}
        self.filter_projects = {p: tk.BooleanVar() for p in PROJECT_OPTIONS}
        self.filter_status = {s: tk.BooleanVar() for s in CONTRACT_STATUS}
        self.filter_deposit_status = {ds: tk.BooleanVar() for ds in DEPOSIT_STATUS}
        self.filter_rent_min = tk.StringVar()
        self.filter_rent_max = tk.StringVar()
        self.filter_commission_min = tk.StringVar()
        self.filter_commission_max = tk.StringVar()
        self.filter_sign_start = tk.StringVar(value="")
        self.filter_sign_end = tk.StringVar(value="")
        self.filter_remain_min = tk.StringVar()
        self.filter_remain_max = tk.StringVar()
        self.filter_keyword = tk.StringVar()

        self.create_widgets()

    def create_widgets(self):
        top = ttk.Frame(self.root)
        top.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(top, text="新增合同", command=self.add_contract).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="修改合同", command=self.edit_contract).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="删除合同", command=self.del_contract).pack(side=tk.LEFT, padx=5)

        self.create_filter_frame()

        frame = ttk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.tree = ttk.Treeview(frame, columns=CONTRACT_FIELD, show="headings")
        vs = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        hs = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)

        for col in CONTRACT_FIELD:
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=100)

        self.tree.tag_configure("even", background="#f7faff")
        self.tree.tag_configure("odd",  background="#ffffff")

        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self._sort_col = "合同号"
        self._sort_rev = True
        self.refresh_table()

    def create_filter_frame(self):
        filter_frame = ttk.LabelFrame(self.root, text="筛选条件")
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        v_num = filter_frame.register(lambda a, v: v.replace(".", "", 1).isdigit() or v == "")
        v_int = filter_frame.register(lambda a, v: v.isdigit() or v == "")

        # 关键词 + 筛选按钮（第一行，子 Frame 打包）
        kw_frame = ttk.Frame(filter_frame)
        kw_frame.grid(row=0, column=0, columnspan=8, sticky=tk.W, padx=5, pady=2)
        ttk.Label(kw_frame, text="关键词：").pack(side=tk.LEFT)
        ttk.Entry(kw_frame, textvariable=self.filter_keyword, width=14).pack(side=tk.LEFT, padx=2)
        ttk.Button(kw_frame, text="执行筛选", command=self.apply_filter).pack(side=tk.LEFT, padx=(6, 3))
        ttk.Button(kw_frame, text="清空条件", command=self.reset_filter).pack(side=tk.LEFT)

        row = 1
        # 经营业态
        biz_row = ttk.Frame(filter_frame)
        biz_row.grid(row=row, column=0, columnspan=8, sticky=tk.W, padx=5, pady=2)
        ttk.Label(biz_row, text="经营业态：").pack(side=tk.LEFT)
        for t in self.filter_business_types:
            ttk.Checkbutton(biz_row, text=t, variable=self.filter_business_types[t]).pack(side=tk.LEFT, padx=3)

        row += 1
        # 所属项目
        proj_row = ttk.Frame(filter_frame)
        proj_row.grid(row=row, column=0, columnspan=8, sticky=tk.W, padx=5, pady=2)
        ttk.Label(proj_row, text="所属项目：").pack(side=tk.LEFT)
        for p in self.filter_projects:
            ttk.Checkbutton(proj_row, text=p, variable=self.filter_projects[p]).pack(side=tk.LEFT, padx=3)

        row += 1
        # 合同状态
        status_row = ttk.Frame(filter_frame)
        status_row.grid(row=row, column=0, columnspan=8, sticky=tk.W, padx=5, pady=2)
        ttk.Label(status_row, text="合同状态：").pack(side=tk.LEFT)
        for s in self.filter_status:
            ttk.Checkbutton(status_row, text=s, variable=self.filter_status[s]).pack(side=tk.LEFT, padx=3)

        row += 1
        # 保证金支付状态
        deposit_row = ttk.Frame(filter_frame)
        deposit_row.grid(row=row, column=0, columnspan=8, sticky=tk.W, padx=5, pady=2)
        ttk.Label(deposit_row, text="保证金支付状态：").pack(side=tk.LEFT)
        for ds in self.filter_deposit_status:
            ttk.Checkbutton(deposit_row, text=ds, variable=self.filter_deposit_status[ds]).pack(side=tk.LEFT, padx=3)

        row += 1
        # 保底租金
        rent_row = ttk.Frame(filter_frame)
        rent_row.grid(row=row, column=0, columnspan=8, sticky=tk.W, padx=5, pady=2)
        ttk.Label(rent_row, text="保底租金(元/㎡/天)：", width=19, anchor=tk.W).pack(side=tk.LEFT)
        ttk.Entry(rent_row, textvariable=self.filter_rent_min, validate="key",
                 validatecommand=(v_num, "%d", "%P"), width=12).pack(side=tk.LEFT, padx=2)
        ttk.Label(rent_row, text="至").pack(side=tk.LEFT, padx=2)
        ttk.Entry(rent_row, textvariable=self.filter_rent_max, validate="key",
                 validatecommand=(v_num, "%d", "%P"), width=12).pack(side=tk.LEFT)

        row += 1
        # 提成租金扣点
        comm_row = ttk.Frame(filter_frame)
        comm_row.grid(row=row, column=0, columnspan=8, sticky=tk.W, padx=5, pady=2)
        ttk.Label(comm_row, text="提成租金扣点(%)：", width=19, anchor=tk.W).pack(side=tk.LEFT)
        ttk.Entry(comm_row, textvariable=self.filter_commission_min, validate="key",
                 validatecommand=(v_num, "%d", "%P"), width=12).pack(side=tk.LEFT, padx=2)
        ttk.Label(comm_row, text="至").pack(side=tk.LEFT, padx=2)
        ttk.Entry(comm_row, textvariable=self.filter_commission_max, validate="key",
                 validatecommand=(v_num, "%d", "%P"), width=12).pack(side=tk.LEFT)

        row += 1
        # 签约日期
        sign_row = ttk.Frame(filter_frame)
        sign_row.grid(row=row, column=0, columnspan=8, sticky=tk.W, padx=5, pady=2)
        ttk.Label(sign_row, text="签约日期：", width=19, anchor=tk.W).pack(side=tk.LEFT)
        e1 = ttk.Entry(sign_row, textvariable=self.filter_sign_start, state="readonly", width=12, cursor="arrow")
        e1.pack(side=tk.LEFT, padx=2)
        e1.bind("<Button-1>", lambda _: PopupCalendar(filter_frame, self.filter_sign_start.set))
        ttk.Label(sign_row, text="至").pack(side=tk.LEFT, padx=2)
        e2 = ttk.Entry(sign_row, textvariable=self.filter_sign_end, state="readonly", width=12, cursor="arrow")
        e2.pack(side=tk.LEFT)
        e2.bind("<Button-1>", lambda _: PopupCalendar(filter_frame, self.filter_sign_end.set))

        row += 1
        # 剩余租期
        remain_row = ttk.Frame(filter_frame)
        remain_row.grid(row=row, column=0, columnspan=8, sticky=tk.W, padx=5, pady=2)
        ttk.Label(remain_row, text="剩余租期(天)：", width=19, anchor=tk.W).pack(side=tk.LEFT)
        ttk.Entry(remain_row, textvariable=self.filter_remain_min, validate="key",
                 validatecommand=(v_int, "%d", "%P"), width=12).pack(side=tk.LEFT, padx=2)
        ttk.Label(remain_row, text="至").pack(side=tk.LEFT, padx=2)
        ttk.Entry(remain_row, textvariable=self.filter_remain_max, validate="key",
                 validatecommand=(v_int, "%d", "%P"), width=12).pack(side=tk.LEFT)

    def apply_filter(self):
        selected_business = [t for t, var in self.filter_business_types.items() if var.get()]
        selected_projects = [p for p, var in self.filter_projects.items() if var.get()]
        selected_status = [s for s, var in self.filter_status.items() if var.get()]
        selected_deposit_status = [ds for ds, var in self.filter_deposit_status.items() if var.get()]
        kw = self.filter_keyword.get().strip()

        rent_min = self.filter_rent_min.get()
        rent_max = self.filter_rent_max.get()
        commission_min = self.filter_commission_min.get()
        commission_max = self.filter_commission_max.get()
        sign_start = self.filter_sign_start.get()
        sign_end = self.filter_sign_end.get()
        remain_min = self.filter_remain_min.get()
        remain_max = self.filter_remain_max.get()

        try:
            rent_min = float(rent_min) if rent_min else None
            rent_max = float(rent_max) if rent_max else None
            commission_min = float(commission_min) if commission_min else None
            commission_max = float(commission_max) if commission_max else None
            remain_min = int(remain_min) if remain_min else None
            remain_max = int(remain_max) if remain_max else None
        except ValueError:
            messagebox.showwarning("警告", "筛选条件格式错误，请检查数值输入")
            return

        try:
            sign_start = datetime.strptime(sign_start, "%Y-%m-%d").date() if sign_start else None
            sign_end   = datetime.strptime(sign_end,   "%Y-%m-%d").date() if sign_end   else None
        except ValueError:
            messagebox.showwarning("警告", "签约日期格式错误，请重新选择")
            return

        self.filtered = []
        for contract in self.all_contracts:
            if kw and not (_fuzzy_match(kw, contract.get("合同号", ""))
                           or _fuzzy_match(kw, contract.get("商户名称", ""))
                           or _fuzzy_match(kw, contract.get("经营业态", ""))
                           or _fuzzy_match(kw, contract.get("所属项目", ""))
                           or _fuzzy_match(kw, contract.get("关联铺位号", ""))
                           or _fuzzy_match(kw, contract.get("联系人", ""))
                           or _fuzzy_match(kw, contract.get("联系电话", ""))
                           or _fuzzy_match(kw, contract.get("签约主体", ""))):
                continue
            if selected_business and not any(t in contract["经营业态"] for t in selected_business):
                continue
            if selected_projects and contract["所属项目"] not in selected_projects:
                continue
            if selected_status and contract["合同状态"] not in selected_status:
                continue
            if selected_deposit_status and contract.get("押金支付状态", "") not in selected_deposit_status:
                continue
            try:
                rent_val = float(contract["保底租金(元/㎡/天)"])
                if rent_min is not None and rent_val < rent_min:
                    continue
                if rent_max is not None and rent_val > rent_max:
                    continue
            except:
                continue
            try:
                commission_val = float(contract["提成租金扣点(%)"]) if contract["提成租金扣点(%)"] else 0
                if commission_min is not None and commission_val < commission_min:
                    continue
                if commission_max is not None and commission_max < commission_val:
                    continue
            except:
                continue
            try:
                sign_date = datetime.strptime(contract["签约日期"], "%Y-%m-%d").date()
                if sign_start is not None and sign_date < sign_start:
                    continue
                if sign_end is not None and sign_date > sign_end:
                    continue
            except:
                if sign_start is not None or sign_end is not None:
                    continue
            try:
                remain_val = int(contract["剩余租期(天)"])
                if remain_min is not None and remain_val < remain_min:
                    continue
                if remain_max is not None and remain_max < remain_val:
                    continue
            except:
                continue
            self.filtered.append(contract)
        self.refresh_table(filtered=True)

    def reset_filter(self):
        for var in self.filter_business_types.values():
            var.set(False)
        for var in self.filter_projects.values():
            var.set(False)
        for var in self.filter_status.values():
            var.set(False)
        for var in self.filter_deposit_status.values():
            var.set(False)
        self.filter_rent_min.set("")
        self.filter_rent_max.set("")
        self.filter_commission_min.set("")
        self.filter_commission_max.set("")
        self.filter_sign_start.set("")
        self.filter_sign_end.set("")
        self.filter_remain_min.set("")
        self.filter_remain_max.set("")
        self.filter_keyword.set("")
        self.filtered = self.all_contracts.copy()
        self.refresh_table()

    def _sort_by(self, col):
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            self._sort_rev = True
        self.refresh_table()

    def refresh_table(self, filtered=False):
        if auto_expire_contracts():
            self.all_contracts = load_contracts()
            if not filtered:
                self.filtered = self.all_contracts.copy()
        data = self.filtered if filtered else self.all_contracts
        # 排序
        num_cols = {"保底租金(元/㎡/天)", "提成租金扣点(%)", "免租期(天)", "剩余租期(天)", "押金"}
        def _key(row):
            v = row.get(self._sort_col, "")
            if self._sort_col in num_cols:
                try: return float(v)
                except: return 0.0
            return str(v)
        data = sorted(data, key=_key, reverse=self._sort_rev)
        self.tree.delete(*self.tree.get_children())
        today = date.today()
        for i, row in enumerate(data):
            tag = "even" if i % 2 == 0 else "odd"
            values = []
            for col in CONTRACT_FIELD:
                v = row.get(col, "")
                # 未起租：当前日期 < 租赁开始日期时，剩余租期显示"未起租"
                if col == "剩余租期(天)":
                    try:
                        start_str = row.get("租赁开始日期", "")
                        if start_str:
                            start_dt = datetime.strptime(start_str, "%Y-%m-%d").date()
                            if today < start_dt:
                                v = "未起租"
                    except:
                        pass
                values.append(v)
            self.tree.insert("", tk.END, values=values, tags=(tag,))

    def select_shop(self, parent_win, project, types):
        self.all_shops = load_shops()
        occupied = get_occupied_shopnos()
        select_win = tk.Toplevel(parent_win)
        select_win.title("选择空置铺位")
        select_win.geometry("800x450")
        select_win.transient(parent_win)
        select_win.grab_set()

        selected_shop = tk.StringVar()

        tree = ttk.Treeview(select_win, columns=["铺位号", "项目", "业态", "建筑面积(㎡)", "基准租金(元/㎡/天)", "状态"], show="headings")
        for c in tree["columns"]:
            tree.heading(c, text=c)
            tree.column(c, width=120)
        tree.tag_configure("even", background="#f7faff")
        tree.tag_configure("odd",  background="#ffffff")

        idx = 0
        for shop in self.all_shops:
            s_p = shop.get("所属项目", "")
            s_t = shop.get("适用业态", "")
            s_no = shop.get("铺位号", "")
            match_type = any(t in s_t for t in types)
            if s_p == project and match_type and s_no not in occupied:
                tag = "even" if idx % 2 == 0 else "odd"
                tree.insert("", tk.END, values=[
                    shop["铺位号"], shop["所属项目"], shop["适用业态"],
                    shop.get("建筑面积(㎡)", shop.get("计租面积(㎡)", "")), shop["基准租金(元/㎡/天)"], "空置"
                ], tags=(tag,))
                idx += 1

        def on_select(event):
            selected_items = tree.selection()
            if selected_items:
                item = tree.item(selected_items[0])
                selected_shop.set(item["values"][0])
        tree.bind("<<TreeviewSelect>>", on_select)

        def confirm():
            if selected_shop.get():
                select_win.destroy()

        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        btn_frame = ttk.Frame(select_win)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(btn_frame, text="已选中铺位：").pack(side=tk.LEFT, padx=5)
        ttk.Label(btn_frame, textvariable=selected_shop, foreground="blue").pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="确定选择", command=confirm).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=select_win.destroy).pack(side=tk.RIGHT, padx=5)

        parent_win.wait_window(select_win)
        return selected_shop.get()

    def show_error_tip(self, parent, row, col, text, is_show=True, widget=None):
        tip_widget_name = f"tip_{row}_{col}"
        if hasattr(self, tip_widget_name):
            getattr(self, tip_widget_name).destroy()
            delattr(self, tip_widget_name)
        if widget:
            try:
                if isinstance(widget, ttk.Entry):
                    widget.configure(style="TEntry")
                elif isinstance(widget, ttk.Combobox):
                    widget.configure(style="TCombobox")
                elif isinstance(widget, ttk.Checkbutton):
                    widget.configure(style="TCheckbutton")
                else:
                    widget.configure(bg="white", fg="black")
            except tk.TclError:
                pass

        if is_show and text:
            tip = ttk.Label(parent, text=text, foreground="red", font=("微软雅黑", 9))
            tip.grid(row=row, column=col, sticky=tk.W, padx=5)
            setattr(self, tip_widget_name, tip)

            if widget:
                try:
                    if isinstance(widget, ttk.Entry):
                        style = ttk.Style()
                        style.configure("Error.TEntry", fieldbackground="#ffebee", foreground="red")
                        widget.configure(style="Error.TEntry")
                    elif isinstance(widget, ttk.Combobox):
                        style = ttk.Style()
                        style.configure("Error.TCombobox", fieldbackground="#ffebee", foreground="red")
                        widget.configure(style="Error.TCombobox")
                    elif isinstance(widget, ttk.Checkbutton):
                        style = ttk.Style()
                        style.configure("Error.TCheckbutton", foreground="red")
                        widget.configure(style="Error.TCheckbutton")
                    else:
                        widget.configure(bg="#ffebee", fg="red")
                except tk.TclError:
                    pass

    def disable_backspace(self, event):
        if event.keysym in ('BackSpace', 'Delete'):
            return "break"

    def create_contract_window(self, is_edit=False, contract_data=None):
        win = tk.Toplevel()
        win.title("修改合同" if is_edit else "新增合同")
        win.geometry("680x780")
        win.transient(self.root)
        win.grab_set()

        # 主容器
        main = ttk.Frame(win, padding=16)
        main.pack(fill=tk.BOTH, expand=True)
        main.columnconfigure(1, weight=1)  # 让输入控件列吸收多余空间，左对齐统一

        v_num = win.register(lambda a, v: v.replace(".", "", 1).isdigit() or v == "")
        v_int = win.register(lambda a, v: v.isdigit() or v == "")
        v_phone = win.register(lambda a, v: v.isdigit() or v == "")

        # 兼容无预填数据（新增合同从合同管理入口点击时 contract_data 为 None）
        contract_data = contract_data or {}

        contract_no = tk.StringVar(value=contract_data.get("合同号", ""))
        merchant = tk.StringVar(value=contract_data.get("商户名称", ""))
        phone = tk.StringVar(value=contract_data.get("联系电话", ""))
        contact_person = tk.StringVar(value=contract_data.get("联系人", ""))
        project = tk.StringVar(value=contract_data.get("所属项目", ""))
        shop_no = tk.StringVar(value=contract_data.get("关联铺位号", ""))
        guarantee_rent = tk.StringVar(value=contract_data.get("保底租金(元/㎡/天)", ""))
        commission = tk.StringVar(value=contract_data.get("提成租金扣点(%)", ""))
        property_fee = tk.StringVar(value=contract_data.get("物业服务费单价（元/㎡/天）", ""))
        free = tk.StringVar(value=contract_data.get("免租期(天)", contract_data.get("免租期(天)") or "0"))
        deposit = tk.StringVar(value=contract_data.get("押金", ""))
        pay_cycle = tk.StringVar(value=contract_data.get("支付周期", ""))
        status = tk.StringVar(value=contract_data.get("合同状态", ""))
        deposit_status = tk.StringVar(value=contract_data.get("押金支付状态", ""))
        remark = tk.StringVar(value=contract_data.get("备注", ""))
        signing_entity = tk.StringVar(value=contract_data.get("签约主体", ""))
        termination_date = tk.StringVar(value=contract_data.get("终止日期", ""))
        rent_mode = tk.StringVar(value=contract_data.get("租金模式", ""))

        sign_date_str = contract_data.get("签约日期", "")
        start_date_str = contract_data.get("租赁开始日期", "")
        end_date_str = contract_data.get("租赁结束日期", "")

        sign_date = tk.StringVar(value=sign_date_str)
        start = tk.StringVar(value=start_date_str)
        end = tk.StringVar(value=end_date_str)

        biz_type = tk.StringVar(value=contract_data.get("经营业态", ""))

        LABEL_W = 18  # 统一标签宽度

        row = 0
        ttk.Label(main, text="合同号：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        contract_entry = tk.Entry(main, textvariable=contract_no, width=35)
        if is_edit:
            contract_entry.config(state="readonly")
        contract_entry.grid(row=row, column=1, sticky=tk.W)
        self.show_error_tip(main, row, 2, "", False)
        row += 1

        ttk.Label(main, text="签约主体：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        ent = ttk.Entry(main, textvariable=signing_entity, width=35)
        if is_edit:
            ent.config(state="readonly")
        ent.grid(row=row, column=1, sticky=tk.W)
        self.show_error_tip(main, row, 2, "", False)
        row += 1

        ttk.Label(main, text="商户名称：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        merchant_entry = ttk.Entry(main, textvariable=merchant, width=35)
        if is_edit:
            merchant_entry.config(state="disabled")
        merchant_entry.grid(row=row, column=1, sticky=tk.W)
        self.show_error_tip(main, row, 2, "", False)
        row += 1

        # 经营业态（单选下拉框）
        ttk.Label(main, text="经营业态：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        biz_combo = ttk.Combobox(main, textvariable=biz_type, values=BUSINESS_TYPE,
                                  width=33, state="readonly")
        if is_edit:
            biz_combo.config(state="disabled")
        biz_combo.grid(row=row, column=1, sticky=tk.W)
        self.show_error_tip(main, row, 2, "", False)
        row += 1

        ttk.Label(main, text="所属项目：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        project_combo = ttk.Combobox(main, textvariable=project, values=PROJECT_OPTIONS, width=33, state="readonly")
        if is_edit:
            project_combo.config(state="disabled")
        project_combo.grid(row=row, column=1, sticky=tk.W)
        self.show_error_tip(main, row, 2, "", False)
        row += 1

        ttk.Label(main, text="关联铺位号：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        shop_frame = ttk.Frame(main)
        shop_frame.grid(row=row, column=1, sticky=tk.W)
        shop_entry = ttk.Entry(shop_frame, textvariable=shop_no, width=20, state="disabled")
        shop_entry.pack(side=tk.LEFT)
        self.show_error_tip(main, row, 2, "", False)

        def choose_shop():
            p = project.get()
            bt = biz_type.get()
            ts = [bt] if bt else []
            if not p:
                self.show_error_tip(main, 4, 2, "请先选择所属项目", project_combo)
                return
            if not ts:
                self.show_error_tip(main, 3, 2, "请先选择经营业态", biz_combo)
                return
            res = self.select_shop(main, p, ts)
            if res:
                shop_no.set(res)
                self.show_error_tip(main, row, 2, "", False, shop_entry)

        if not is_edit:
            ttk.Button(shop_frame, text="选择铺位", command=choose_shop).pack(side=tk.LEFT, padx=(6, 0))
        row += 1

        # 租金模式下拉（编辑时禁止修改）
        ttk.Label(main, text="租金模式：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        mode_state = "disabled" if is_edit else "readonly"
        mode_combo = ttk.Combobox(main, textvariable=rent_mode, values=["保底", "提成", "取高"],
                                  state=mode_state, width=10)
        mode_combo.grid(row=row, column=1, sticky=tk.W)
        self.show_error_tip(main, row, 2, "", False)
        row += 1

        ttk.Label(main, text="保底租金(元/㎡/天)：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        rent_entry = tk.Entry(main, textvariable=guarantee_rent, validate="key", validatecommand=(v_num, "%d", "%P"), width=35)
        if is_edit:
            rent_entry.config(state="readonly")
        rent_entry.grid(row=row, column=1, sticky=tk.W)
        self.show_error_tip(main, row, 2, "", False)
        row += 1

        ttk.Label(main, text="提成租金扣点(%)：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        commission_entry = ttk.Entry(main, textvariable=commission, validate="key", validatecommand=(v_num, "%d", "%P"), width=35)
        if is_edit:
            commission_entry.config(state="disabled")
        commission_entry.grid(row=row, column=1, sticky=tk.W)
        self.show_error_tip(main, row, 2, "", False)
        row += 1

        ttk.Label(main, text="物业费（元/㎡/天）：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        property_fee_entry = ttk.Entry(main, textvariable=property_fee, validate="key", validatecommand=(v_num, "%d", "%P"), width=35)
        if is_edit:
            property_fee_entry.config(state="disabled")
        property_fee_entry.grid(row=row, column=1, sticky=tk.W)
        self.show_error_tip(main, row, 2, "", False)
        row += 1

        ttk.Label(main, text="支付周期：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        cycle_combo = ttk.Combobox(main, textvariable=pay_cycle, values=PAYMENT_CYCLE, width=33, state="readonly")
        if is_edit:
            cycle_combo.config(state="disabled")
        cycle_combo.grid(row=row, column=1, sticky=tk.W)
        self.show_error_tip(main, row, 2, "", False)
        row += 1

        def _toggle_rent_fields(*_):
            m = rent_mode.get()
            if m == "保底":
                rent_entry.config(state="normal" if not is_edit else "readonly")
                commission_entry.config(state="disabled")
                commission.set("")
            elif m == "提成":
                rent_entry.config(state="disabled")
                guarantee_rent.set("")
                commission_entry.config(state="normal" if not is_edit else "disabled")
            elif m == "取高":
                rent_entry.config(state="normal" if not is_edit else "readonly")
                commission_entry.config(state="normal" if not is_edit else "disabled")
            else:
                rent_entry.config(state="normal" if not is_edit else "readonly")
                commission_entry.config(state="normal" if not is_edit else "disabled")

        rent_mode.trace_add("write", _toggle_rent_fields)

        ttk.Label(main, text="签约日期：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        date1_entry = ttk.Entry(main, textvariable=sign_date, width=33, cursor="arrow")
        if is_edit:
            date1_entry.config(state="disabled")
            date1_entry.bind("<Button-1>", lambda e: "break")
        else:
            date1_entry.config(state="readonly")
            date1_entry.bind("<Button-1>", lambda _: PopupCalendar(main, sign_date.set))
        date1_entry.grid(row=row, column=1, sticky=tk.W)
        self.show_error_tip(main, row, 2, "", False)
        row += 1

        ttk.Label(main, text="租赁开始：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        date2_entry = ttk.Entry(main, textvariable=start, width=33, cursor="arrow")
        if is_edit:
            date2_entry.config(state="disabled")
            date2_entry.bind("<Button-1>", lambda e: "break")
        else:
            date2_entry.config(state="readonly")
            date2_entry.bind("<Button-1>", lambda _: PopupCalendar(main, start.set))
        date2_entry.grid(row=row, column=1, sticky=tk.W)
        self.show_error_tip(main, row, 2, "", False)
        row += 1

        ttk.Label(main, text="租赁结束：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        date3_entry = ttk.Entry(main, textvariable=end, width=33, cursor="arrow")
        if is_edit:
            date3_entry.config(state="disabled")
            date3_entry.bind("<Button-1>", lambda e: "break")
        else:
            date3_entry.config(state="readonly")
            date3_entry.bind("<Button-1>", lambda _: PopupCalendar(main, end.set))
        date3_entry.grid(row=row, column=1, sticky=tk.W)
        self.show_error_tip(main, row, 2, "", False)
        row += 1

        # ── 免租计划 ──
        self._rent_free_plans = []
        if contract_data:
            raw_plans = contract_data.get("免租计划", [])
            if isinstance(raw_plans, str):
                try:
                    self._rent_free_plans = json.loads(raw_plans)
                except:
                    self._rent_free_plans = []
            elif isinstance(raw_plans, list):
                self._rent_free_plans = raw_plans

        def _calc_free_days():
            total = 0
            for p in self._rent_free_plans:
                try:
                    s = datetime.strptime(p["start"], "%Y-%m-%d").date()
                    e = datetime.strptime(p["end"], "%Y-%m-%d").date()
                    if e >= s:
                        total += (e - s).days + 1
                except:
                    pass
            return total

        # 首次加载时自动计算免租天数
        free.set(str(_calc_free_days()))

        def _open_free_plan():
            # 修改模式仅可查看，不可增删
            self._show_free_plan_window(win, free, _calc_free_days, readonly=is_edit,
                                        lease_start=start.get(), lease_end=end.get())

        ttk.Label(main, text="免租期(天)：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        free_frame = ttk.Frame(main)
        free_entry = ttk.Entry(free_frame, textvariable=free, state="readonly", width=20)
        free_entry.pack(side=tk.LEFT)
        ttk.Button(free_frame, text="免租计划", command=_open_free_plan).pack(side=tk.LEFT, padx=(6, 0))
        free_frame.grid(row=row, column=1, sticky=tk.W)
        self.show_error_tip(main, row, 2, "", False)
        row += 1

        ttk.Label(main, text="押金：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        deposit_entry = ttk.Entry(main, textvariable=deposit, validate="key", validatecommand=(v_num, "%d", "%P"), width=35)
        if is_edit:
            deposit_entry.config(state="disabled")
        deposit_entry.grid(row=row, column=1, sticky=tk.W)
        self.show_error_tip(main, row, 2, "", False)
        row += 1

        ttk.Label(main, text="押金支付状态：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        deposit_status_combo = ttk.Combobox(main, textvariable=deposit_status, values=DEPOSIT_STATUS, width=33, state="readonly")
        deposit_status_combo.grid(row=row, column=1, sticky=tk.W)
        self.show_error_tip(main, row, 2, "", False)
        row += 1

        ttk.Label(main, text="合同状态：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        status_combo = ttk.Combobox(main, textvariable=status, values=CONTRACT_STATUS, width=33, state="readonly")
        status_combo.grid(row=row, column=1, sticky=tk.W)
        self.show_error_tip(main, row, 2, "", False)
        row += 1

        ttk.Label(main, text="终止日期：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        term_state = "readonly" if is_edit else "disabled"
        termination_entry = ttk.Entry(main, textvariable=termination_date, width=33, state=term_state, cursor="arrow")
        if is_edit:
            termination_entry.bind("<Button-1>", lambda _: PopupCalendar(main, termination_date.set))
        termination_entry.grid(row=row, column=1, sticky=tk.W)
        self.show_error_tip(main, row, 2, "", False)
        row += 1

        ttk.Label(main, text="联系电话：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        phone_entry = ttk.Entry(main, textvariable=phone, validate="key", validatecommand=(v_phone, "%d", "%P"), width=35)
        phone_entry.grid(row=row, column=1, sticky=tk.W)
        self.show_error_tip(main, row, 2, "", False)
        row += 1

        ttk.Label(main, text="联系人：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        contact_entry = ttk.Entry(main, textvariable=contact_person, width=35)
        contact_entry.grid(row=row, column=1, sticky=tk.W)
        self.show_error_tip(main, row, 2, "", False)
        row += 1

        ttk.Label(main, text="备注：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
        remark_entry = ttk.Entry(main, textvariable=remark, width=35)
        remark_entry.grid(row=row, column=1, sticky=tk.W)
        self.show_error_tip(main, row, 2, "", False)
        row += 1

        def save():
            self.all_shops = load_shops()
            for r in range(row):
                self.show_error_tip(main, r, 2, "", False)

            is_valid = True

            if is_edit:
                if not status.get():
                    self.show_error_tip(main, 17, 2, "请选择合同状态", status_combo)
                    status_combo.focus()
                    is_valid = False
                if status.get() == "已终止" and not termination_date.get():
                    self.show_error_tip(main, 18, 2, "请选择终止日期", termination_entry)
                    termination_entry.focus()
                    is_valid = False
                phone_val = phone.get()
                if phone_val and not phone_val.isdigit():
                    self.show_error_tip(main, 19, 2, "联系电话只能是数字", phone_entry)
                    phone_entry.focus()
                    is_valid = False
                if not deposit_status.get():
                    self.show_error_tip(main, 16, 2, "请选择押金支付状态", deposit_status_combo)
                    deposit_status_combo.focus()
                    is_valid = False
            else:
                c_no = contract_no.get().strip()
                if not c_no:
                    self.show_error_tip(main, 0, 2, "合同号不能为空", contract_entry)
                    contract_entry.focus()
                    is_valid = False
                elif is_contract_no_exist(c_no):
                    self.show_error_tip(main, 0, 2, f"合同号{c_no}已存在", contract_entry)
                    contract_entry.focus()
                    is_valid = False
                if not merchant.get().strip():
                    self.show_error_tip(main, 2, 2, "商户名称不能为空", merchant_entry)
                    merchant_entry.focus()
                    is_valid = False
                business_types = biz_type.get()
                if not business_types:
                    self.show_error_tip(main, 3, 2, "请选择经营业态", biz_combo)
                    is_valid = False
                pj = project.get()
                if not pj:
                    self.show_error_tip(main, 4, 2, "请选择所属项目", project_combo)
                    project_combo.focus()
                    is_valid = False
                sn = shop_no.get()
                if not sn:
                    self.show_error_tip(main, 5, 2, "请选择关联铺位", shop_entry)
                    shop_entry.focus()
                    is_valid = False
                # ── 保底租金校验（提成模式跳过）──
                rm = rent_mode.get()
                if rm in ("保底", "取高", ""):
                    gr = guarantee_rent.get()
                    if not gr:
                        self.show_error_tip(main, 7, 2, "保底租金不能为空", rent_entry)
                        rent_entry.focus()
                        is_valid = False
                    else:
                        try:
                            gr_float = float(gr)
                            shop = next((s for s in self.all_shops if s["铺位号"] == sn), None)
                            if shop:
                                base_rent = float(shop.get("基准租金(元/㎡/天)", "0"))
                                if gr_float < base_rent:
                                    self.show_error_tip(main, 7, 2, f"保底租金不能低于基准租金{base_rent}", rent_entry)
                                    rent_entry.focus()
                                    is_valid = False
                        except:
                            self.show_error_tip(main, 7, 2, "保底租金格式错误", rent_entry)
                            rent_entry.focus()
                            is_valid = False
                # ── 提成扣点校验 ──
                if rm in ("提成", "取高"):
                    # 提成/取高模式：扣点必须填且 >0
                    if not commission.get():
                        self.show_error_tip(main, 8, 2, f"{rm}模式扣点不能为空", commission_entry)
                        commission_entry.focus()
                        is_valid = False
                    else:
                        try:
                            commission_float = float(commission.get())
                            if commission_float <= 0 or commission_float > 100:
                                self.show_error_tip(main, 8, 2, "提成扣点需在0-100之间且大于0", commission_entry)
                                commission_entry.focus()
                                is_valid = False
                        except:
                            self.show_error_tip(main, 8, 2, "提成扣点格式错误", commission_entry)
                            commission_entry.focus()
                            is_valid = False
                else:
                    # 保底模式或无租金模式：扣点可为0
                    if not commission.get():
                        commission.set("0")
                    try:
                        commission_float = float(commission.get())
                        if commission_float < 0 or commission_float > 100:
                            self.show_error_tip(main, 8, 2, "提成扣点需在0-100之间", commission_entry)
                            commission_entry.focus()
                            is_valid = False
                    except:
                        self.show_error_tip(main, 8, 2, "提成扣点格式错误", commission_entry)
                        commission_entry.focus()
                        is_valid = False
                if not sign_date.get():
                    self.show_error_tip(main, 11, 2, "请选择签约日期", date1_entry)
                    date1_entry.focus()
                    is_valid = False
                else:
                    try:
                        sign_dt = datetime.strptime(sign_date.get(), "%Y-%m-%d").date()
                        if sign_dt > date.today():
                            self.show_error_tip(main, 11, 2, "签约日期不能晚于今天", date1_entry)
                            date1_entry.focus()
                            is_valid = False
                    except:
                        self.show_error_tip(main, 11, 2, "签约日期格式错误", date1_entry)
                        date1_entry.focus()
                        is_valid = False
                if not start.get():
                    self.show_error_tip(main, 12, 2, "请选择租赁开始日期", date2_entry)
                    date2_entry.focus()
                    is_valid = False
                else:
                    try:
                        start_dt = datetime.strptime(start.get(), "%Y-%m-%d").date()
                        if start_dt < sign_dt:
                            self.show_error_tip(main, 12, 2, "租赁开始日期不能早于签约日期", date2_entry)
                            date2_entry.focus()
                            is_valid = False
                    except:
                        self.show_error_tip(main, 12, 2, "租赁开始日期格式错误", date2_entry)
                        date2_entry.focus()
                        is_valid = False
                if not end.get():
                    self.show_error_tip(main, 13, 2, "请选择租赁结束日期", date3_entry)
                    date3_entry.focus()
                    is_valid = False
                else:
                    try:
                        end_dt = datetime.strptime(end.get(), "%Y-%m-%d").date()
                        if end_dt <= start_dt:
                            self.show_error_tip(main, 13, 2, "租赁结束日期需晚于开始日期", date3_entry)
                            date3_entry.focus()
                            is_valid = False
                    except:
                        self.show_error_tip(main, 13, 2, "租赁结束日期格式错误", date3_entry)
                        date3_entry.focus()
                        is_valid = False
                if not deposit.get():
                    self.show_error_tip(main, 15, 2, "押金不能为空", deposit_entry)
                    deposit_entry.focus()
                    is_valid = False
                else:
                    try:
                        deposit_float = float(deposit.get())
                        if deposit_float < 0:
                            self.show_error_tip(main, 15, 2, "押金不能为负数", deposit_entry)
                            deposit_entry.focus()
                            is_valid = False
                    except:
                        self.show_error_tip(main, 15, 2, "押金格式错误", deposit_entry)
                        deposit_entry.focus()
                        is_valid = False
                if not pay_cycle.get():
                    self.show_error_tip(main, 10, 2, "请选择支付周期", cycle_combo)
                    cycle_combo.focus()
                    is_valid = False
                if not rent_mode.get():
                    self.show_error_tip(main, 6, 2, "请选择租金模式", mode_combo)
                    mode_combo.focus()
                    is_valid = False
                if not status.get():
                    self.show_error_tip(main, 17, 2, "请选择合同状态", status_combo)
                    status_combo.focus()
                    is_valid = False
                if status.get() == "已终止" and not termination_date.get():
                    self.show_error_tip(main, 18, 2, "请选择终止日期", termination_entry)
                    termination_entry.focus()
                    is_valid = False
                if phone.get() and not phone.get().isdigit():
                    self.show_error_tip(main, 19, 2, "联系电话只能是数字", phone_entry)
                    phone_entry.focus()
                    is_valid = False
                if not deposit_status.get():
                    self.show_error_tip(main, 16, 2, "请选择押金支付状态", deposit_status_combo)
                    deposit_status_combo.focus()
                    is_valid = False

            if not is_valid:
                return

            try:
                end_dt = datetime.strptime(end.get(), "%Y-%m-%d").date()
                remain_days = (end_dt - date.today()).days
                remain_days = max(0, remain_days)
            except:
                remain_days = 0

            business_types_str = biz_type.get()
            # 免租期按免租计划自动计算
            free.set(str(_calc_free_days()))

            contract_data = {
                "合同号": contract_no.get().strip(),
                "商户名称": merchant.get().strip(),
                "经营业态": business_types_str,
                "所属项目": project.get(),
                "关联铺位号": shop_no.get(),
                "保底租金(元/㎡/天)": guarantee_rent.get().strip(),
                "提成租金扣点(%)": commission.get().strip(),
                "租金模式": rent_mode.get(),
                "物业服务费单价（元/㎡/天）": property_fee.get().strip(),
                "签约日期": sign_date.get(),
                "租赁开始日期": start.get(),
                "租赁结束日期": end.get(),
                "免租期(天)": free.get().strip(),
                "剩余租期(天)": str(remain_days),
                "押金": deposit.get().strip(),
                "押金支付状态": deposit_status.get(),
                "支付周期": pay_cycle.get(),
                "合同状态": status.get(),
                "终止日期": termination_date.get(),
                "联系电话": phone.get().strip(),
                "联系人": contact_person.get().strip(),
                "备注": remark.get().strip(),
                "签约主体": signing_entity.get().strip(),
                "免租计划": self._rent_free_plans,
            }

            all_contracts = load_contracts()
            if is_edit:
                target_no = contract_no.get().strip()
                for i, c in enumerate(all_contracts):
                    if str(c["合同号"]).strip() == target_no:
                        all_contracts[i] = contract_data
                        break
            else:
                sn = shop_no.get()
                occupied = [c["合同号"] for c in all_contracts
                            if c["关联铺位号"] == sn
                            and c["合同状态"] in ["待生效", "执行中", "即将到期"]]
                if occupied:
                    messagebox.showwarning("铺位冲突",
                        f"铺位 {sn} 已被合同 {occupied[0]} 占用，请选择其他铺位")
                    return
                all_contracts.append(contract_data)

            save_contracts(all_contracts)

            # 自动同步商机阶段：将相同商户名称的商机更新为"已转合同"
            try:
                _opp_list = load_opportunities()
                _merchant_name = contract_data.get("商户名称", "").strip()
                _updated = False
                for _o in _opp_list:
                    if (_o.get("商户名称", "").strip().lower() == _merchant_name.lower()
                            and _o.get("当前阶段", "") != "已转合同"):
                        _o["当前阶段"] = "已转合同"
                        _updated = True
                if _updated:
                    save_opportunities(_opp_list)
            except Exception as e:
                print(f"[商机同步] 自动更新商机阶段失败: {e}")

            sync_shop_status()
            cno = contract_data["合同号"]
            op_type = "修改" if is_edit else "新增"
            utils.log_operation(op_type, "合同", f"{op_type}合同 {cno}（{merchant.get().strip()}）", cno)
            messagebox.showinfo("成功", "合同保存成功！")
            win.destroy()
            self.all_contracts = load_contracts()
            self.filtered = self.all_contracts.copy()
            try:
                self.refresh_table()
            except tk.TclError:
                pass

        btn_f = ttk.Frame(main)
        btn_f.grid(row=row, column=0, columnspan=3, pady=(18, 0))
        ttk.Button(btn_f, text="保存", command=save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_f, text="取消", command=win.destroy).pack(side=tk.LEFT, padx=10)

    def _show_free_plan_window(self, parent, free_var, calc_free_days, readonly=False,
                                lease_start="", lease_end=""):
        """免租计划弹窗：readonly=True 时只能查看"""
        win = tk.Toplevel(parent)
        win.title("查看免租计划" if readonly else "编辑免租计划")
        win.geometry("560x460")
        win.transient(parent)
        win.grab_set()

        # 解析租赁日期用于验证
        ls_dt = None
        le_dt = None
        try:
            if lease_start:
                ls_dt = datetime.strptime(lease_start, "%Y-%m-%d").date()
            if lease_end:
                le_dt = datetime.strptime(lease_end, "%Y-%m-%d").date()
        except:
            pass

        f = ttk.Frame(win, padding=10)
        f.pack(fill="both", expand=1)

        # ── 添加区域（仅非只读显示）──
        if not readonly:
            add_f = ttk.LabelFrame(f, text="添加免租时间段", padding=8)
            add_f.pack(fill="x", pady=(0, 8))
            start_var = tk.StringVar()
            end_var = tk.StringVar()

            row_f = ttk.Frame(add_f)
            row_f.pack(fill="x", pady=2)
            ttk.Label(row_f, text="开始日期：", width=12, anchor=tk.E).pack(side=tk.LEFT)
            e1 = ttk.Entry(row_f, textvariable=start_var, state="readonly", width=14, cursor="arrow")
            e1.pack(side=tk.LEFT, padx=4)
            e1.bind("<Button-1>", lambda _, sv=start_var: PopupCalendar(add_f, sv.set))
            ttk.Label(row_f, text="结束日期：", width=12, anchor=tk.E).pack(side=tk.LEFT, padx=(12, 0))
            e2 = ttk.Entry(row_f, textvariable=end_var, state="readonly", width=14, cursor="arrow")
            e2.pack(side=tk.LEFT, padx=4)
            e2.bind("<Button-1>", lambda _, sv=end_var: PopupCalendar(add_f, sv.set))

            def _add():
                s = start_var.get()
                e = end_var.get()
                if not s or not e:
                    messagebox.showwarning("提示", "请选择开始和结束日期")
                    return
                try:
                    sd = datetime.strptime(s, "%Y-%m-%d").date()
                    ed = datetime.strptime(e, "%Y-%m-%d").date()
                    if ed < sd:
                        messagebox.showwarning("提示", "结束日期不能早于开始日期")
                        return
                except:
                    messagebox.showwarning("提示", "日期格式错误")
                    return
                # 验证免租时间段必须在租赁日期范围内
                if ls_dt and sd < ls_dt:
                    messagebox.showwarning("提示", f"免租开始日期不能早于租赁开始日期（{lease_start}）")
                    return
                if le_dt and ed > le_dt:
                    messagebox.showwarning("提示", f"免租结束日期不能晚于租赁结束日期（{lease_end}）")
                    return
                self._rent_free_plans.append({"start": s, "end": e})
                _refresh_tree()
                start_var.set("")
                end_var.set("")
                free_var.set(str(calc_free_days()))
            ttk.Button(add_f, text="添加", command=_add).pack(anchor=tk.W, pady=(6, 0))

        # ── 列表区域 ──
        list_f = ttk.LabelFrame(f, text="免租时间段列表", padding=8)
        list_f.pack(fill="both", expand=1, pady=(0, 8))

        cols = ["序号", "开始日期", "结束日期", "天数"]
        tree = ttk.Treeview(list_f, columns=cols, show="headings", height=8)
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=90 if c == "序号" else 130)
        tree.tag_configure("even", background="#f7faff")
        tree.tag_configure("odd", background="#ffffff")

        vs = ttk.Scrollbar(list_f, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=1)
        vs.pack(side="right", fill="y")

        def _refresh_tree():
            tree.delete(*tree.get_children())
            for i, p in enumerate(self._rent_free_plans):
                try:
                    s = datetime.strptime(p["start"], "%Y-%m-%d").date()
                    e = datetime.strptime(p["end"], "%Y-%m-%d").date()
                    days = (e - s).days + 1
                except:
                    days = 0
                tag = "even" if i % 2 == 0 else "odd"
                tree.insert("", "end", values=[i + 1, p["start"], p["end"], days], tags=(tag,))
        _refresh_tree()

        # ── 底部按钮行（删除按钮在左，确定按钮在右）──
        btn_f = ttk.Frame(f)
        btn_f.pack(fill="x", pady=(6, 0))
        if not readonly:
            def _del():
                sel = tree.selection()
                if not sel:
                    messagebox.showwarning("提示", "请选择要删除的记录")
                    return
                idx = tree.index(sel[0])
                del self._rent_free_plans[idx]
                _refresh_tree()
                free_var.set(str(calc_free_days()))
            ttk.Button(btn_f, text="删除选中", command=_del).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_f, text="确定", command=win.destroy).pack(side=tk.RIGHT, padx=5)

    def add_contract(self):
        self.create_contract_window(is_edit=False)

    def edit_contract(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择要修改的合同！")
            return
        try:
            item = self.tree.item(selected[0])
            contract_no = str(item["values"][0]).strip()
            contracts = load_contracts()
            contract_data = next((c for c in contracts if str(c["合同号"]).strip() == contract_no), None)
            if contract_data:
                self.create_contract_window(is_edit=True, contract_data=contract_data)
            else:
                all_nos = [str(c.get("合同号", "?")).strip() for c in contracts]
                messagebox.showwarning("警告",
                    f"未找到合同号: {contract_no}\n"
                    f"文件中共 {len(contracts)} 条合同: {', '.join(all_nos[:10])}")
        except Exception as e:
            messagebox.showerror("错误", f"打开编辑窗口失败:\n{type(e).__name__}: {e}")

    def del_contract(self):
        selected = self.tree.selection()
        if not selected:
            return
        if not messagebox.askyesno("确认", "确定要删除选中的合同吗？"):
            return
        item = self.tree.item(selected[0])
        contract_no = str(item["values"][0]).strip()
        delete_contract(contract_no)
        sync_shop_status()
        utils.log_operation("删除", "合同", f"删除合同 {contract_no}", contract_no)
        messagebox.showinfo("成功", "合同删除成功！")
        self.all_contracts = load_contracts()
        self.filtered = self.all_contracts.copy()
        try:
            self.refresh_table()
        except tk.TclError:
            pass

if __name__ == "__main__":
    root = tk.Tk()
    root.title("合同管理系统")
    root.geometry("1200x600")
    app = ContractManageGUI(root)
    root.mainloop()
