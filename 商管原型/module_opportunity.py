import json
import os
import sys
from datetime import datetime, date
import tkinter as tk
from tkinter import ttk, messagebox

from utils import (
    PopupCalendar, SCRIPT_DIR, PROJECT_OPTIONS, BUSINESS_TYPE,
    load_opportunities, save_opportunities, delete_opportunity,
    load_shops
)
import utils

# ================== 商机模块专属常量 ==================
OPPORTUNITY_STAGES = [
    "初步接洽", "需求确认", "谈判协商", "意向确认", "已支付意向金", "已转合同"
]

FOLLOW_RESULT_OPTIONS = ["继续跟进", "阶段推进", "已流失", "已转合同"]

INTENT_DESTINATIONS = ["", "已转押金", "已退还", "已转租金"]

OPPORTUNITY_FILE = os.path.join(SCRIPT_DIR, "opportunities_data.json")

# ================== 模糊搜索工具 ==================
def _fuzzy_match(keyword, text):
    """模糊匹配：大小写不敏感子串匹配"""
    if not keyword:
        return True
    return keyword.lower() in str(text).lower()

# ================== 工具函数 ==================
def is_opp_no_exist(opp_no, exclude_id=None):
    for o in load_opportunities():
        if o.get("商机编号", "") == opp_no and o.get("商机编号", "") != exclude_id:
            return True
    return False

# ================== 商机跟进记录子窗口 ==================
class FollowUpWindow:
    """弹出的跟进记录历史窗口"""
    def __init__(self, parent, opp_data, on_save_callback, intent_payment_cb=None):
        self.parent            = parent
        self.opp_data          = opp_data
        self.on_save           = on_save_callback
        self.intent_payment_cb = intent_payment_cb

        self.win = tk.Toplevel(parent)
        self.win.title(f"跟进记录 - {opp_data.get('商户名称', '')}")
        self.win.geometry("700x520")
        self.win.transient(parent)
        self.win.grab_set()

        self._build_ui()

    def _build_ui(self):
        # 上方：历史跟进列表
        lf = ttk.LabelFrame(self.win, text="历史跟进记录")
        lf.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        cols = ["跟进日期", "阶段", "跟进内容", "跟进结果", "下次计划日期", "跟进人"]
        self.tree = ttk.Treeview(lf, columns=cols, show="headings", height=8)
        widths    = [100, 90, 260, 90, 110, 80]
        for c, w in zip(cols, widths):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w)
        self.tree.tag_configure("even", background="#f7faff")
        self.tree.tag_configure("odd",  background="#ffffff")
        vs = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vs.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_records()

        # 下方：新增跟进
        add_lf = ttk.LabelFrame(self.win, text="新增跟进记录")
        add_lf.pack(fill=tk.X, padx=10, pady=(0, 8))

        row = 0
        ttk.Label(add_lf, text="跟进日期：").grid(row=row, column=0, sticky=tk.W, padx=5, pady=3)
        self.v_date = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        e_date = ttk.Entry(add_lf, textvariable=self.v_date, state="readonly", width=14, cursor="arrow")
        e_date.grid(row=row, column=1, sticky=tk.W)
        e_date.bind("<Button-1>", lambda _: PopupCalendar(add_lf, self.v_date.set))

        ttk.Label(add_lf, text=" 阶段推进至：").grid(row=row, column=2, padx=8)
        self.v_stage = tk.StringVar(value=self.opp_data.get("当前阶段", OPPORTUNITY_STAGES[0]))
        ttk.Combobox(add_lf, textvariable=self.v_stage, values=OPPORTUNITY_STAGES, width=14, state="readonly").grid(row=row, column=3)
        row += 1

        ttk.Label(add_lf, text="跟进内容：").grid(row=row, column=0, sticky=tk.W, padx=5, pady=3)
        self.v_content = tk.StringVar()
        ttk.Entry(add_lf, textvariable=self.v_content, width=50).grid(row=row, column=1, columnspan=3, sticky=tk.W)
        row += 1

        ttk.Label(add_lf, text="跟进结果：").grid(row=row, column=0, sticky=tk.W, padx=5, pady=3)
        self.v_result = tk.StringVar(value="继续跟进")
        ttk.Combobox(add_lf, textvariable=self.v_result, values=FOLLOW_RESULT_OPTIONS, width=14, state="readonly").grid(row=row, column=1, sticky=tk.W)
        row += 1

        ttk.Label(add_lf, text="下次计划日期：").grid(row=row, column=2, padx=8)
        self.v_next = tk.StringVar()
        e_next = ttk.Entry(add_lf, textvariable=self.v_next, state="readonly", width=14, cursor="arrow")
        e_next.grid(row=row, column=3)
        e_next.bind("<Button-1>", lambda _: PopupCalendar(add_lf, self.v_next.set))
        row += 1

        ttk.Label(add_lf, text="跟进人：").grid(row=row, column=0, sticky=tk.W, padx=5, pady=3)
        self.v_follower = tk.StringVar(value=self.opp_data.get("负责人", ""))
        ttk.Entry(add_lf, textvariable=self.v_follower, width=20).grid(row=row, column=1, sticky=tk.W)
        row += 1

        btn_f = ttk.Frame(add_lf)
        btn_f.grid(row=row, column=0, columnspan=4, pady=6)
        ttk.Button(btn_f, text="保存跟进记录", command=self._save_record).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_f, text="关闭",          command=self.win.destroy).pack(side=tk.LEFT, padx=8)

    def _load_records(self):
        self.tree.delete(*self.tree.get_children())
        for i, rec in enumerate(reversed(self.opp_data.get("跟进记录", []))):
            tag = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", tk.END, tags=(tag,), values=[
                rec.get("跟进日期", ""), rec.get("阶段", ""),
                rec.get("跟进内容", ""), rec.get("跟进结果", ""),
                rec.get("下次计划日期", ""), rec.get("跟进人", "")
            ])

    def _save_record(self):
        if not self.v_content.get().strip():
            messagebox.showwarning("提示", "跟进内容不能为空", parent=self.win)
            return
        record = {
            "跟进日期":    self.v_date.get(),
            "阶段":        self.v_stage.get(),
            "跟进内容":    self.v_content.get().strip(),
            "跟进结果":    self.v_result.get(),
            "下次计划日期": self.v_next.get(),
            "跟进人":      self.v_follower.get().strip(),
        }
        opps = load_opportunities()
        opp_no = self.opp_data["商机编号"]
        for o in opps:
            if o["商机编号"] == opp_no:
                o.setdefault("跟进记录", []).append(record)
                o["最近跟进日期"] = self.v_date.get()
                o["当前阶段"]     = self.v_stage.get()
                o["跟进结果"]     = self.v_result.get()
                self.opp_data = o
                break
        save_opportunities(opps)
        utils.log_operation("修改", "商机", f"跟进记录 {opp_no}（{self.opp_data.get('商户名称','')}）", opp_no)
        messagebox.showinfo("成功", "跟进记录已保存！", parent=self.win)
        self._load_records()
        self.v_content.set("")
        if self.on_save:
            self.on_save()
        # 阶段推进至「已支付意向金」且尚未支付时，自动弹出意向金支付窗口
        new_stage = self.v_stage.get()
        if new_stage == "已支付意向金":
            amount = self.opp_data.get("意向金金额(元)", "")
            if not amount or amount in ("0", "0.0", "0.00"):
                self.win.destroy()
                if self.intent_payment_cb:
                    self.intent_payment_cb(self.opp_data)

# ================== 支付意向金 → 转入合同 弹窗 ==================
class IntentPaymentWindow:
    """记录意向金支付，并可选择一键跳转到合同模块新建合同"""
    def __init__(self, parent, opp_data, on_save_callback, open_contract_callback=None):
        self.parent   = parent
        self.opp_data = opp_data
        self.on_save  = on_save_callback
        self.open_contract_cb = open_contract_callback

        self.win = tk.Toplevel(parent)
        self.win.title(f"支付意向金 - {opp_data.get('商户名称', '')}")
        self.win.geometry("520x430")
        self.win.transient(parent)
        self.win.grab_set()

        self._build_ui()

    def _build_ui(self):
        lf = ttk.LabelFrame(self.win, text="意向金支付信息", padding=12)
        lf.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        row = 0
        ttk.Label(lf, text="商户名称：").grid(row=row, column=0, sticky=tk.W, pady=4)
        ttk.Label(lf, text=self.opp_data.get("商户名称", ""), foreground="#2980b9", font=("微软雅黑", 10, "bold")).grid(row=row, column=1, sticky=tk.W)
        row += 1

        ttk.Label(lf, text="意向项目：").grid(row=row, column=0, sticky=tk.W, pady=4)
        ttk.Label(lf, text=self.opp_data.get("意向项目", "")).grid(row=row, column=1, sticky=tk.W)
        row += 1

        ttk.Label(lf, text="意向金金额(元)：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self.v_amount = tk.StringVar(value=self.opp_data.get("意向金金额(元)", ""))
        v_num = lf.register(lambda a, v: v.replace(".", "", 1).isdigit() or v == "")
        ttk.Entry(lf, textvariable=self.v_amount, validate="key",
                  validatecommand=(v_num, "%d", "%P"), width=20).grid(row=row, column=1, sticky=tk.W)
        row += 1

        ttk.Label(lf, text="支付日期：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self.v_pay_date = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        e = ttk.Entry(lf, textvariable=self.v_pay_date, state="readonly", width=14, cursor="arrow")
        e.grid(row=row, column=1, sticky=tk.W)
        e.bind("<Button-1>", lambda _: PopupCalendar(lf, self.v_pay_date.set))
        row += 1

        ttk.Label(lf, text="备注：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self.v_remark = tk.StringVar()
        ttk.Entry(lf, textvariable=self.v_remark, width=32).grid(row=row, column=1, sticky=tk.W)
        row += 1

        ttk.Label(lf, text="意向金去向：").grid(row=row, column=0, sticky=tk.W, pady=4)
        self.v_destination = tk.StringVar(value=self.opp_data.get("意向金去向", ""))
        ttk.Combobox(lf, textvariable=self.v_destination,
                     values=INTENT_DESTINATIONS,
                     width=18, state="readonly").grid(row=row, column=1, sticky=tk.W)
        row += 1

        row += 1
        ttk.Separator(lf, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=3, sticky="ew", pady=8)
        row += 1

        tip = tk.Label(lf,
            text="💡 支付意向金后，阶段将自动更新为「已支付意向金」。\n     您可点击「保存并前往签合同」直接跳转到合同管理模块。",
            fg="#888", font=("微软雅黑", 8), justify=tk.LEFT)
        tip.grid(row=row, column=0, columnspan=3, sticky=tk.W)
        row += 1

        btn_f = ttk.Frame(lf)
        btn_f.grid(row=row, column=0, columnspan=3, pady=10)
        ttk.Button(btn_f, text="仅保存意向金",        command=self._save_only).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_f, text="保存并前往签合同",     command=self._save_and_go_contract).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_f, text="取消",                command=self.win.destroy).pack(side=tk.LEFT, padx=8)

    def _do_save(self):
        """保存意向金信息并将阶段推进为"已支付意向金"，返回是否成功"""
        amount = self.v_amount.get().strip()
        if not amount:
            messagebox.showwarning("提示", "请填写意向金金额", parent=self.win)
            return False
        try:
            if float(amount) <= 0:
                messagebox.showwarning("提示", "意向金金额需大于0", parent=self.win)
                return False
        except:
            messagebox.showwarning("提示", "意向金金额格式错误", parent=self.win)
            return False

        opps = load_opportunities()
        opp_no = self.opp_data["商机编号"]
        for o in opps:
            if o["商机编号"] == opp_no:
                o["意向金金额(元)"]    = amount
                o["意向金支付日期"]    = self.v_pay_date.get()
                o["意向金去向"]        = self.v_destination.get()
                o["当前阶段"]          = "已支付意向金"
                o["最近跟进日期"]      = date.today().strftime("%Y-%m-%d")
                o["跟进结果"]          = "阶段推进"
                if self.v_remark.get().strip():
                    o["备注"] = self.v_remark.get().strip()
                o.setdefault("跟进记录", []).append({
                    "跟进日期":    date.today().strftime("%Y-%m-%d"),
                    "阶段":        "已支付意向金",
                    "跟进内容":    f"支付意向金 ¥{amount} 元",
                    "跟进结果":    "阶段推进",
                    "下次计划日期": "",
                    "跟进人":      o.get("负责人", ""),
                })
                self.opp_data = o
                break
        save_opportunities(opps)
        utils.log_operation("修改", "商机", f"支付意向金 {opp_no}（¥{amount}）", opp_no)
        if self.on_save:
            self.on_save()
        return True

    def _save_only(self):
        if self._do_save():
            messagebox.showinfo("成功", "意向金信息已保存，阶段已更新为「已支付意向金」！", parent=self.win)
            self.win.destroy()

    def _save_and_go_contract(self):
        if self._do_save():
            self.win.destroy()
            if self.open_contract_cb:
                prefill = {
                    "商户名称": self.opp_data.get("商户名称", ""),
                    "经营业态": self.opp_data.get("意向业态", ""),
                    "所属项目": self.opp_data.get("意向项目", ""),
                    "联系电话": self.opp_data.get("联系电话", ""),
                    "联系人":   self.opp_data.get("联系人", ""),
                    "签约主体": self.opp_data.get("意向主体", ""),
                }
                self.open_contract_cb(prefill)
            else:
                messagebox.showinfo("提示", "意向金已保存！\n请手动前往合同管理模块创建合同。")

# ================== 商机详情/新增/编辑窗口 ==================
class OpportunityFormWindow:
    def __init__(self, parent, gui_ref, is_edit=False, opp_data=None):
        self.parent   = parent
        self.gui_ref  = gui_ref
        self.is_edit  = is_edit
        self.opp_data = opp_data or {}

        self.win = tk.Toplevel(parent)
        self.win.title("修改商机" if is_edit else "新增商机")
        self.win.geometry("640x720")
        self.win.transient(parent)
        self.win.grab_set()

        self._build_ui()

    def _build_ui(self):
        w = self.win
        main = ttk.Frame(w, padding=18)
        main.pack(fill=tk.BOTH, expand=True)
        main.columnconfigure(1, weight=1)  # 让输入控件列吸收多余空间，错误提示紧贴其后
        self._form_parent = main  # 供 _save 中的 _tip 使用

        v_num   = w.register(lambda a, v: v.replace(".", "", 1).isdigit() or v == "")
        v_phone = w.register(lambda a, v: v.isdigit() or v == "")
        d = self.opp_data

        LABEL_W = 18  # 统一标签宽度

        def _row(label_text, widget, row):
            """一行：右对齐标签 | 输入控件 | 错误提示区"""
            ttk.Label(main, text=label_text, width=LABEL_W, anchor=tk.E)\
                .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
            widget.grid(row=row, column=1, pady=5, sticky=tk.W)
            self._tip(main, row)

        row = 0

        # 意向主体
        self.v_entity_type = tk.StringVar(value=d.get("意向主体", ""))
        _row("意向主体：", ttk.Entry(main, textvariable=self.v_entity_type, width=30), row)
        row += 1

        # 商户名称
        self.v_name = tk.StringVar(value=d.get("商户名称", ""))
        _row("商户名称：", ttk.Entry(main, textvariable=self.v_name, width=30), row)
        row += 1

        # 联系人
        self.v_contact = tk.StringVar(value=d.get("联系人", ""))
        _row("联系人：", ttk.Entry(main, textvariable=self.v_contact, width=30), row)
        row += 1

        # 联系电话
        self.v_phone = tk.StringVar(value=d.get("联系电话", ""))
        _row("联系电话：", ttk.Entry(main, textvariable=self.v_phone, validate="key",
                   validatecommand=(v_phone, "%d", "%P"), width=30), row)
        row += 1

        # 意向项目
        self.v_project = tk.StringVar(value=d.get("意向项目", ""))
        _row("意向项目：", ttk.Combobox(main, textvariable=self.v_project,
              values=PROJECT_OPTIONS, width=28, state="readonly"), row)
        row += 1

        # 意向业态（分两行排列）
        ttk.Label(main, text="意向业态：", width=LABEL_W, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.NE)
        self.type_vars = {}
        type_frame = ttk.Frame(main)
        type_frame.grid(row=row, column=1, pady=5, sticky=tk.W)
        current_types = d.get("意向业态", "").split("、") if d.get("意向业态") else []
        for i, t in enumerate(BUSINESS_TYPE):
            c = i % 5
            r = i // 5
            var = tk.BooleanVar(value=(t in current_types))
            self.type_vars[t] = var
            ttk.Checkbutton(type_frame, text=t, variable=var)\
                .grid(row=r, column=c, padx=(0, 12), pady=1, sticky=tk.W)
        self._tip(main, row)
        row += 1

        # 意向租赁期限（年）
        self.v_lease_term = tk.StringVar(value=d.get("意向租赁期限（年）", ""))
        _row("意向租赁期限（年）：", ttk.Entry(main, textvariable=self.v_lease_term, validate="key",
                   validatecommand=(v_num, "%d", "%P"), width=30), row)
        row += 1

        # 意向铺位（弹窗选铺，按意向业态+意向项目筛选空置铺位）
        shop_frame = ttk.Frame(main)
        self.v_shop = tk.StringVar(value=d.get("意向铺位", ""))
        shop_entry = ttk.Entry(shop_frame, textvariable=self.v_shop, state="readonly", width=20)
        shop_entry.pack(side=tk.LEFT)

        def _choose_shop():
            proj = self.v_project.get()
            types = [t for t, v in self.type_vars.items() if v.get()]
            if not proj:
                self._show_err(3, "请先选择意向项目")
                return
            if not types:
                self._show_err(4, "请先选择意向业态")
                return
            # 弹出铺位选择窗口
            sel_win = tk.Toplevel(self.win)
            sel_win.title("选择意向铺位")
            sel_win.geometry("760x420")
            sel_win.transient(self.win)
            sel_win.grab_set()
            cols = ["铺位号", "所属项目", "适用业态", "建筑面积(㎡)", "基准租金(元/㎡/天)", "状态"]
            tree2 = ttk.Treeview(sel_win, columns=cols, show="headings")
            for c in cols:
                tree2.heading(c, text=c)
                tree2.column(c, width=115)
            tree2.tag_configure("even", background="#f7faff")
            tree2.tag_configure("odd",  background="#ffffff")
            all_shops = load_shops()
            idx2 = 0
            for s in all_shops:
                s_types = [x.strip() for x in s.get("适用业态", "").replace(",", "、").split("、") if x.strip()]
                if s.get("所属项目", "") == proj and any(t in s_types for t in types):
                    tag = "even" if idx2 % 2 == 0 else "odd"
                    tree2.insert("", tk.END, values=[
                        s.get("铺位号", ""),
                        s.get("所属项目", ""),
                        s.get("适用业态", ""),
                        s.get("建筑面积(㎡)", s.get("计租面积(㎡)", "")),
                        s.get("基准租金(元/㎡/天)", ""),
                        s.get("铺位状态", ""),
                    ], tags=(tag,))
                    idx2 += 1
            chosen = tk.StringVar()
            def on_sel(ev):
                sel2 = tree2.selection()
                if sel2:
                    chosen.set(tree2.item(sel2[0])["values"][0])
            tree2.bind("<<TreeviewSelect>>", on_sel)
            def confirm2():
                if chosen.get():
                    self.v_shop.set(chosen.get())
                    # 自动填充建筑面积
                    for s in all_shops:
                        if s.get("铺位号", "") == chosen.get():
                            area_val = s.get("建筑面积(㎡)", s.get("计租面积(㎡)", ""))
                            self.v_area.set(str(area_val))
                            break
                    sel_win.destroy()
            tree2.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
            bf2 = ttk.Frame(sel_win)
            bf2.pack(pady=(0, 8))
            ttk.Button(bf2, text="确认选择", command=confirm2).pack(side=tk.LEFT, padx=8)
            ttk.Button(bf2, text="取消",     command=sel_win.destroy).pack(side=tk.LEFT, padx=8)

        ttk.Button(shop_frame, text="选择铺位", command=_choose_shop).pack(side=tk.LEFT, padx=(6, 0))
        _row("意向铺位：", shop_frame, row)
        row += 1

        # 建筑面积（只读，联动意向铺位自动填充）
        self.v_area = tk.StringVar(value=d.get("建筑面积(㎡)", d.get("意向面积(㎡)", "")))
        area_entry = ttk.Entry(main, textvariable=self.v_area, state="readonly", width=30)
        _row("建筑面积(㎡)：", area_entry, row)
        row += 1

        # 商机来源
        self.v_source = tk.StringVar(value=d.get("商机来源", ""))
        src_opts = ["主动拓展", "商户咨询", "网络推广", "朋友介绍", "其他"]
        _row("商机来源：", ttk.Combobox(main, textvariable=self.v_source,
              values=src_opts, width=28, state="readonly"), row)
        row += 1

        # 当前阶段
        self.v_stage = tk.StringVar(value=d.get("当前阶段", OPPORTUNITY_STAGES[0]))
        _row("当前阶段：", ttk.Combobox(main, textvariable=self.v_stage,
              values=OPPORTUNITY_STAGES, width=28, state="readonly"), row)
        row += 1

        # 首次接洽日期
        self.v_first_date = tk.StringVar(value=d.get("首次接洽日期", date.today().strftime("%Y-%m-%d")))
        e1 = ttk.Entry(main, textvariable=self.v_first_date, state="readonly", width=16, cursor="arrow")
        e1.bind("<Button-1>", lambda _: PopupCalendar(main, self.v_first_date.set))
        _row("首次接洽日期：", e1, row)
        row += 1

        # 意向租金单价（手动录入）
        self.v_rent_price = tk.StringVar(value=d.get("意向租金单价(元/㎡/天)", ""))
        _row("意向租金单价(元/㎡/天)：", ttk.Entry(main, textvariable=self.v_rent_price, validate="key",
                   validatecommand=(v_num, "%d", "%P"), width=30), row)
        row += 1

        # 物业服务费单价（手动录入）
        self.v_property_fee = tk.StringVar(value=d.get("物业服务费单价(元/㎡/月)", ""))
        _row("物业服务费单价(元/㎡/月)：", ttk.Entry(main, textvariable=self.v_property_fee, validate="key",
                   validatecommand=(v_num, "%d", "%P"), width=30), row)
        row += 1

        # 支付周期
        self.v_pay_cycle = tk.StringVar(value=d.get("支付周期", ""))
        _row("支付周期：", ttk.Combobox(main, textvariable=self.v_pay_cycle,
              values=["月度", "季度", "半年", "年度"], width=28, state="readonly"), row)
        row += 1

        # 负责人
        self.v_owner = tk.StringVar(value=d.get("负责人", ""))
        _row("负责人：", ttk.Entry(main, textvariable=self.v_owner, width=30), row)
        row += 1

        # 备注
        self.v_remark = tk.StringVar(value=d.get("备注", ""))
        _row("备注：", ttk.Entry(main, textvariable=self.v_remark, width=30), row)
        row += 1

        self._form_row_count = row
        btn_f = ttk.Frame(main)
        btn_f.grid(row=row, column=0, columnspan=3, pady=(18, 0))
        ttk.Button(btn_f, text="保存", command=self._save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_f, text="取消", command=self.win.destroy).pack(side=tk.LEFT, padx=10)

    def _tip(self, parent, row, text="", is_show=False):
        tip_name = f"_tip_{row}"
        if hasattr(self, tip_name):
            getattr(self, tip_name).destroy()
            delattr(self, tip_name)
        if is_show and text:
            lbl = ttk.Label(parent, text=text, foreground="red", font=("微软雅黑", 9))
            lbl.grid(row=row, column=2, sticky=tk.W, padx=4)
            setattr(self, tip_name, lbl)

    def _show_err(self, row, msg):
        self._tip(self._form_parent, row, msg, is_show=True)

    def _save(self):
        w = self._form_parent  # 与 _build_ui 中 _tip 调用保持同一父容器
        for r in range(self._form_row_count):
            self._tip(w, r)
        is_valid = True

        if not self.v_name.get().strip():
            self._show_err(1, "商户名称不能为空")
            is_valid = False

        if not self.v_contact.get().strip():
            self._show_err(2, "联系人不能为空")
            is_valid = False

        if not self.v_project.get():
            self._show_err(4, "请选择意向项目")
            is_valid = False

        types_selected = [t for t, v in self.type_vars.items() if v.get()]
        if not types_selected:
            self._show_err(5, "至少选择一种意向业态")
            is_valid = False

        if not self.v_source.get():
            self._show_err(9, "请选择商机来源")
            is_valid = False

        if not self.v_first_date.get():
            self._show_err(11, "请选择首次接洽日期")
            is_valid = False

        if not is_valid:
            return

        # 新增时自动生成商机编号：取最大整数值 +1，首位为 001
        if not self.is_edit:
            all_opps = load_opportunities()
            max_no = 0
            for o in all_opps:
                try:
                    max_no = max(max_no, int(str(o.get("商机编号", "0"))))
                except ValueError:
                    pass
            opp_no = str(max_no + 1).zfill(3)
        else:
            opp_no = self.opp_data.get("商机编号", "")

        opp = {
            "商机编号":     opp_no,
            "商户名称":     self.v_name.get().strip(),
            "联系人":       self.v_contact.get().strip(),
            "联系电话":     self.v_phone.get().strip(),
            "意向项目":     self.v_project.get(),
            "意向业态":     "、".join(types_selected),
            "意向租赁期限（年）": self.v_lease_term.get().strip(),
            "意向铺位":     self.v_shop.get().strip(),
            "建筑面积(㎡)": self.v_area.get().strip(),
            "商机来源":     self.v_source.get(),
            "当前阶段":     self.v_stage.get(),
            "首次接洽日期": self.v_first_date.get(),
            "意向租金单价(元/㎡/天)": self.v_rent_price.get().strip(),
            "物业服务费单价(元/㎡/月)": self.v_property_fee.get().strip(),
            "支付周期":     self.v_pay_cycle.get(),
            "最近跟进日期": self.opp_data.get("最近跟进日期", ""),
            "意向金金额(元)":  self.opp_data.get("意向金金额(元)", ""),
            "意向金支付日期":  self.opp_data.get("意向金支付日期", ""),
            "意向金去向":     self.opp_data.get("意向金去向", ""),
            "跟进结果":     self.opp_data.get("跟进结果", "继续跟进"),
            "负责人":       self.v_owner.get().strip(),
            "备注":         self.v_remark.get().strip(),
            "意向主体":     self.v_entity_type.get().strip(),
            "跟进记录":     self.opp_data.get("跟进记录", []),
        }

        all_opps = load_opportunities()
        if self.is_edit:
            for i, o in enumerate(all_opps):
                if o["商机编号"] == opp_no:
                    all_opps[i] = opp
                    break
        else:
            all_opps.append(opp)

        save_opportunities(all_opps)
        op_type = "修改" if self.is_edit else "新增"
        utils.log_operation(op_type, "商机", f"{op_type}商机 {opp_no}（{opp['商户名称']}）", opp_no)
        messagebox.showinfo("成功", "商机信息已保存！", parent=self.win)
        self.win.destroy()
        self.gui_ref.refresh()

# ================== 主界面 ==================
class OpportunityManageGUI:
    def __init__(self, root, open_contract_callback=None):
        """
        root：父容器 Frame
        open_contract_callback：跳转到合同管理的回调函数（可传预填数据字典）
        """
        self.root = root
        self.open_contract_cb = open_contract_callback
        self.all_opps    = load_opportunities()
        self.filtered    = self.all_opps.copy()

        # 筛选变量
        self.fv_stage   = {s: tk.BooleanVar() for s in OPPORTUNITY_STAGES}
        self.fv_project = {p: tk.BooleanVar() for p in PROJECT_OPTIONS}
        self.fv_result  = {r: tk.BooleanVar() for r in FOLLOW_RESULT_OPTIONS}
        self.fv_keyword = tk.StringVar()

        self._build_ui()

    def _build_ui(self):
        # 顶部按钮栏
        top = ttk.Frame(self.root)
        top.pack(fill=tk.X, padx=10, pady=6)
        ttk.Button(top, text="新增商机",   command=self.add_opp).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="修改商机",   command=self.edit_opp).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="删除商机",   command=self.del_opp).pack(side=tk.LEFT, padx=4)
        ttk.Separator(top, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(top, text="跟进记录",   command=self.open_follow_up).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="支付意向金", command=self.open_intent_payment).pack(side=tk.LEFT, padx=4)

        # 筛选区
        self._build_filter()

        # 表格区
        table_f = ttk.Frame(self.root)
        table_f.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))

        cols = [
            "序号", "当前阶段", "最近跟进日期", "跟进结果",
            "意向主体", "商户名称", "意向项目", "意向租赁期限（年）", "意向业态", "意向铺位",
            "建筑面积", "意向租金单价(元/㎡/天)", "物业服务费单价(元/㎡/月)", "支付周期",
            "意向金金额(元)", "意向金支付日期", "意向金去向",
            "联系人", "联系电话", "负责人", "商机来源", "首次接洽时间", "备注"
        ]
        col_widths = [50, 90, 100, 80, 80, 100, 100, 90, 80, 80, 80, 120, 120, 70, 100, 100, 90, 70, 100, 70, 80, 100, 100]

        self.tree = ttk.Treeview(table_f, columns=cols, show="headings")
        vs = ttk.Scrollbar(table_f, orient=tk.VERTICAL,   command=self.tree.yview)
        hs = ttk.Scrollbar(table_f, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)

        for col, w in zip(cols, col_widths):
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=w, minwidth=60)

        # 阶段颜色标记
        self.tree.tag_configure("stage_paid",  background="#e8f5e9")   # 已支付意向金 - 绿色背景
        self.tree.tag_configure("stage_late",  background="#fff3e0")   # 谈判协商及之后 - 橙色
        self.tree.tag_configure("stage_lost",  background="#fce4ec")   # 已流失 - 红色
        self.tree.tag_configure("stage_early", background="#e3f2fd")   # 初步阶段 - 蓝色
        self.tree.tag_configure("even", background="#f7faff")
        self.tree.tag_configure("odd",  background="#ffffff")

        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        table_f.rowconfigure(0, weight=1)
        table_f.columnconfigure(0, weight=1)

        self._sort_col = "首次接洽时间"
        self._sort_rev = True
        self.refresh()

    def _build_filter(self):
        ff = ttk.LabelFrame(self.root, text="筛选条件")
        ff.pack(fill=tk.X, padx=10, pady=4)


        # 关键词 + 筛选按钮（第一行，子 Frame 打包）
        kw_frame = ttk.Frame(ff)
        kw_frame.grid(row=0, column=0, columnspan=8, sticky=tk.W, padx=5, pady=2)
        ttk.Label(kw_frame, text="关键词：").pack(side=tk.LEFT)
        ttk.Entry(kw_frame, textvariable=self.fv_keyword, width=14).pack(side=tk.LEFT, padx=2)
        ttk.Button(kw_frame, text="执行筛选", command=self._apply_filter).pack(side=tk.LEFT, padx=(6, 3))
        ttk.Button(kw_frame, text="清空条件", command=self._reset_filter).pack(side=tk.LEFT)

        row = 1
        ttk.Label(ff, text="意向项目：").grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        pf = ttk.Frame(ff)
        pf.grid(row=row, column=1, columnspan=6, sticky=tk.W)
        for i, (p, var) in enumerate(self.fv_project.items()):
            ttk.Checkbutton(pf, text=p, variable=var).grid(row=0, column=i, padx=4)
        row += 1

        ttk.Label(ff, text="当前阶段：").grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        sf = ttk.Frame(ff)
        sf.grid(row=row, column=1, columnspan=6, sticky=tk.W)
        for i, (s, var) in enumerate(self.fv_stage.items()):
            ttk.Checkbutton(sf, text=s, variable=var).grid(row=0, column=i, padx=4)
        row += 1

        ttk.Label(ff, text="跟进结果：").grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        rf = ttk.Frame(ff)
        rf.grid(row=row, column=1, columnspan=6, sticky=tk.W)
        for i, (r, var) in enumerate(self.fv_result.items()):
            ttk.Checkbutton(rf, text=r, variable=var).grid(row=0, column=i, padx=4)

    def _apply_filter(self):
        kw       = self.fv_keyword.get().strip()
        stages   = [s for s, v in self.fv_stage.items()   if v.get()]
        projects = [p for p, v in self.fv_project.items() if v.get()]
        results  = [r for r, v in self.fv_result.items()  if v.get()]

        self.filtered = []
        for o in self.all_opps:
            if kw and not (_fuzzy_match(kw, o.get("商户名称", ""))
                           or _fuzzy_match(kw, o.get("联系人", ""))
                           or _fuzzy_match(kw, o.get("联系电话", ""))
                           or _fuzzy_match(kw, o.get("意向业态", ""))
                           or _fuzzy_match(kw, o.get("意向主体", ""))):
                continue
            if stages and o.get("当前阶段", "") not in stages:
                continue
            if projects and o.get("意向项目", "") not in projects:
                continue
            if results and o.get("跟进结果", "") not in results:
                continue
            self.filtered.append(o)
        self._refresh_table(filtered=True)

    def _reset_filter(self):
        self.fv_keyword.set("")
        for v in self.fv_stage.values():   v.set(False)
        for v in self.fv_project.values(): v.set(False)
        for v in self.fv_result.values():  v.set(False)
        self.filtered = self.all_opps.copy()
        self._refresh_table()

    def refresh(self):
        self.all_opps = load_opportunities()
        self.filtered = self.all_opps.copy()
        self._refresh_table()

    def _sort_by(self, col):
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            self._sort_rev = True
        self._refresh_table()

    def _refresh_table(self, filtered=False):
        self.tree.delete(*self.tree.get_children())
        data = self.filtered if filtered else self.all_opps
        # 排序
        num_cols = {"建筑面积(㎡)", "意向金金额(元)", "意向租金单价(元/㎡/天)", "物业服务费单价(元/㎡/月)"}
        col_key_map = {"建筑面积": "建筑面积(㎡)", "首次接洽时间": "首次接洽日期"}
        def _key(row):
            key = col_key_map.get(self._sort_col, self._sort_col)
            v = row.get(key, "")
            if key in num_cols:
                try: return float(v)
                except: return 0.0
            return str(v)
        data = sorted(data, key=_key, reverse=self._sort_rev)
        for i, o in enumerate(data):
            stage  = o.get("当前阶段", "")
            result = o.get("跟进结果", "")
            if stage == "已支付意向金":
                stage_tag = "stage_paid"
            elif result == "已流失":
                stage_tag = "stage_lost"
            elif stage in ["谈判协商", "意向确认"]:
                stage_tag = "stage_late"
            else:
                stage_tag = "stage_early"
            parity = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", tk.END, iid=str(o.get("商机编号", "")), tags=(stage_tag, parity), values=[
                i + 1,
                o.get("当前阶段", ""),
                o.get("最近跟进日期", ""),
                o.get("跟进结果", ""),
                o.get("意向主体", ""),
                o.get("商户名称", ""),
                o.get("意向项目", ""),
                o.get("意向租赁期限（年）", ""),
                o.get("意向业态", ""),
                o.get("意向铺位", ""),
                o.get("建筑面积(㎡)", ""),
                o.get("意向租金单价(元/㎡/天)", ""),
                o.get("物业服务费单价(元/㎡/月)", ""),
                o.get("支付周期", ""),
                o.get("意向金金额(元)", ""),
                o.get("意向金支付日期", ""),
                o.get("意向金去向", ""),
                o.get("联系人", ""),
                o.get("联系电话", ""),
                o.get("负责人", ""),
                o.get("商机来源", ""),
                o.get("首次接洽日期", ""),
                o.get("备注", ""),
            ])

    def _get_selected_opp(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择一条商机记录")
            return None
        # sel[0] 就是 iid（商机编号），不走 values 避免 TreeView 吞前导零
        opp_no = str(sel[0]).strip()
        opps   = load_opportunities()
        opp    = next((o for o in opps if str(o["商机编号"]).strip() == opp_no), None)
        if not opp:
            # 兜底：万一 TreeView 还是吞了前导零（如 099→99），用整数比较
            if opp_no.isdigit():
                opp = next((o for o in opps
                            if str(o["商机编号"]).strip().isdigit()
                            and int(str(o["商机编号"]).strip()) == int(opp_no)), None)
        if not opp:
            messagebox.showwarning("提示", f"未找到商机编号：{opp_no}")
        return opp

    def add_opp(self):
        OpportunityFormWindow(self.root, self)

    def edit_opp(self):
        opp = self._get_selected_opp()
        if opp:
            OpportunityFormWindow(self.root, self, is_edit=True, opp_data=opp)

    def del_opp(self):
        opp = self._get_selected_opp()
        if not opp:
            return
        if messagebox.askyesno("确认删除", f"确定要删除商机「{opp['商户名称']}」？\n删除后不可恢复。"):
            delete_opportunity(opp["商机编号"])
            utils.log_operation("删除", "商机", f"删除商机 {opp['商机编号']}（{opp['商户名称']}）", opp["商机编号"])
            messagebox.showinfo("成功", "商机已删除！")
            self.refresh()

    def open_follow_up(self):
        opp = self._get_selected_opp()
        if opp:
            FollowUpWindow(self.root, opp, on_save_callback=self.refresh,
                           intent_payment_cb=lambda o: self._auto_open_intent(o))

    def _auto_open_intent(self, opp):
        """跟进记录阶段推进至「已支付意向金」时自动弹窗，不重复询问"""
        self.refresh()
        IntentPaymentWindow(
            self.root, opp,
            on_save_callback=self.refresh,
            open_contract_callback=self.open_contract_cb
        )

    def open_intent_payment(self):
        opp = self._get_selected_opp()
        if not opp:
            return
        if opp.get("当前阶段") == "已支付意向金":
            if not messagebox.askyesno("提示",
                    f"该商机已处于「已支付意向金」阶段。\n是否要更新意向金信息？"):
                return
        IntentPaymentWindow(
            self.root, opp,
            on_save_callback=self.refresh,
            open_contract_callback=self.open_contract_cb
        )

# ================== 单独运行入口 ==================
if __name__ == "__main__":
    root = tk.Tk()
    root.title("商机管理")
    root.geometry("1300x700")
    app = OpportunityManageGUI(root)
    root.mainloop()
