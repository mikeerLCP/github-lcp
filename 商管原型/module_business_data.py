"""
module_business_data.py
本地经营数据管理模块（Tkinter）
功能：
  - 查看所有商户的每日经营数据
  - 按商户/日期/项目筛选
  - 折线图趋势展示（可选，需要 matplotlib）
  - 导出当前视图为 CSV
  - 支持手动补录/修改/删除经营记录（管理员权限操作）
"""

import json
import os
import sys
import csv
import calendar
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, datetime, timedelta

from utils import (
    PopupCalendar, SCRIPT_DIR, BUSINESS_FILE, CONTRACTS_FILE, SHOPS_DATA_FILE,
    load_business_data, save_business_data, delete_business_data,
    load_contracts, load_shops,
    BUSINESS_TYPE
)
import utils

def _fuzzy_match(keyword, text):
    """模糊匹配：大小写不敏感子串匹配"""
    if not keyword:
        return True
    return keyword.lower() in str(text).lower()

def get_merchant_list():
    """从合同数据提取商户名称列表（去重）"""
    contracts = load_contracts()
    names = sorted(set(c.get("商户名称", "") for c in contracts if c.get("商户名称")))
    return names

def _get_shop_format(merchant_name):
    """根据商户名称查找对应合同的经营业态"""
    contracts = load_contracts()
    for c in contracts:
        if c.get("商户名称", "").strip() == merchant_name.strip():
            return c.get("经营业态", "")
    return ""

# ─────────────────────────── 主界面 ───────────────────────────
class BusinessDataGUI:
    def __init__(self, parent):
        self.parent = parent
        self.all_data = []
        self.filtered_data = []
        self.refresh_data()
        self.create_widgets()

    def refresh_data(self):
        self.all_data = load_business_data()
        self.filtered_data = list(self.all_data)

    def create_widgets(self):
        for w in self.parent.winfo_children():
            w.destroy()

        # ── 操作按钮 ──
        btn_frame = ttk.Frame(self.parent)
        btn_frame.pack(fill="x", padx=10, pady=3)
        ttk.Button(btn_frame, text="补录数据", command=self.add_record).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="修改选中", command=self.edit_record).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="删除选中", command=self.delete_record).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="刷新",     command=self.refresh_and_render).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="导出 CSV", command=self.export_csv).pack(side="left", padx=4)

        # ── 汇总信息 ──
        self.summary_var = tk.StringVar(value="")
        ttk.Label(btn_frame, textvariable=self.summary_var,
                  font=("微软雅黑", 9), foreground="#555").pack(side="right", padx=10)

        # ── 筛选区 ──
        filter_frame = ttk.LabelFrame(self.parent, text="筛选条件", padding=6)
        filter_frame.pack(fill="x", padx=10, pady=5)

        # 关键词搜索 + 筛选按钮（第一行，子 Frame 打包）
        kw_frame = ttk.Frame(filter_frame)
        kw_frame.grid(row=0, column=0, columnspan=8, sticky=tk.W, padx=5, pady=2)
        self.filter_keyword = tk.StringVar()
        ttk.Label(kw_frame, text="关键词：").pack(side=tk.LEFT)
        ttk.Entry(kw_frame, textvariable=self.filter_keyword, width=15).pack(side=tk.LEFT, padx=2)
        ttk.Button(kw_frame, text="执行筛选", command=self.apply_filter).pack(side=tk.LEFT, padx=(6, 3))
        ttk.Button(kw_frame, text="清空条件", command=self.reset_filter).pack(side=tk.LEFT)

        # 日期范围 + 快捷按钮（第二行）
        ttk.Label(filter_frame, text="日期从：").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.filter_date_start = tk.StringVar(value="")
        e_ds = ttk.Entry(filter_frame, textvariable=self.filter_date_start, state="readonly", width=12, cursor="arrow")
        e_ds.grid(row=1, column=1)
        e_ds.bind("<Button-1>", lambda _: PopupCalendar(filter_frame, self.filter_date_start.set))

        ttk.Label(filter_frame, text="至：", width=2).grid(row=1, column=2)
        self.filter_date_end = tk.StringVar(value="")
        e_de = ttk.Entry(filter_frame, textvariable=self.filter_date_end, state="readonly", width=12, cursor="arrow")
        e_de.grid(row=1, column=3)
        e_de.bind("<Button-1>", lambda _: PopupCalendar(filter_frame, self.filter_date_end.set))

        ttk.Label(filter_frame, text="快捷：").grid(row=1, column=4, sticky="w", padx=5)
        quick_frame = ttk.Frame(filter_frame)
        quick_frame.grid(row=1, column=5, padx=4)
        ttk.Button(quick_frame, text="近7天",  width=6, command=lambda: self._set_quick(7)).pack(side="left", padx=2)
        ttk.Button(quick_frame, text="近30天", width=7, command=lambda: self._set_quick(30)).pack(side="left", padx=2)
        ttk.Button(quick_frame, text="近90天", width=7, command=lambda: self._set_quick(90)).pack(side="left", padx=2)

        # ── 表格 ──
        table_frame = ttk.Frame(self.parent)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)

        cols = ["序号", "商户名称", "日期", "业态", "营业额(元)", "进店客流(人次)", "成交量(单)", "录入时间", "备注"]
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        col_widths = [50, 130, 100, 90, 120, 110, 100, 140, 160]
        for c, w in zip(cols, col_widths):
            self.tree.heading(c, text=c, command=lambda col=c: self._sort_by(col))
            self.tree.column(c, width=w)

        vs = ttk.Scrollbar(table_frame, orient="vertical",   command=self.tree.yview)
        hs = ttk.Scrollbar(table_frame, orient="horizontal",  command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.tree.tag_configure("even", background="#f7faff")
        self.tree.tag_configure("odd",  background="#ffffff")

        self._sort_col = "日期"
        self._sort_rev = True
        self.render_list()

    # ─────────────── 辅助 ───────────────
    def _set_quick(self, days):
        end   = date.today()
        start = end - timedelta(days=days - 1)
        self.filter_date_start.set(start.strftime("%Y-%m-%d"))
        self.filter_date_end.set(end.strftime("%Y-%m-%d"))
        self.apply_filter()

    def _sort_by(self, col):
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            self._sort_rev = True
        self.render_list()

    def render_list(self):
        try:
            self.tree.delete(*self.tree.get_children())
        except tk.TclError:
            return

        col_map = {
            "序号": None,
            "商户名称": "商户名称",
            "日期": "日期",
            "业态": "业态",
            "营业额(元)": "营业额",
            "进店客流(人次)": "客流量",
            "成交量(单)": "成交量",
            "录入时间": "录入时间",
            "备注": "备注"
        }
        sort_key = col_map.get(self._sort_col, "日期")

        def _key(r):
            v = r.get(sort_key, "") if sort_key else ""
            if sort_key in ("营业额", "客流量", "成交量"):
                try:
                    return float(v)
                except Exception:
                    return -1
            return str(v)

        data = sorted(self.filtered_data, key=_key, reverse=self._sort_rev)
        self.filtered_data = data

        total_rev  = 0.0
        total_foot = 0
        total_deal = 0
        for idx, r in enumerate(data):
            rev  = r.get("营业额", "")
            foot = r.get("客流量", "")
            deal = r.get("成交量", "")
            try:
                total_rev += float(rev)
            except Exception:
                pass
            try:
                total_foot += int(foot)
            except Exception:
                pass
            try:
                total_deal += int(deal)
            except Exception:
                pass
            tag = "even" if idx % 2 == 0 else "odd"
            self.tree.insert("", "end", iid=str(idx), values=[
                idx + 1,
                r.get("商户名称", ""),
                r.get("日期", ""),
                r.get("业态", ""),
                f"{float(rev):,.2f}" if rev != "" else "",
                foot if foot != "" else "—",
                deal if deal != "" else "—",
                r.get("录入时间", "")[:16] if r.get("录入时间") else "",
                r.get("备注", "")
            ], tags=(tag,))

        n = len(data)
        avg = round(total_rev / n, 2) if n > 0 else 0
        conv = round(total_deal / total_foot * 100, 1) if total_foot > 0 else 0
        self.summary_var.set(
            f"共 {n} 条记录 | 营业额合计 ¥{total_rev:,.2f} | 日均 ¥{avg:,.2f} | "
            f"客流合计 {total_foot} 人次 | 成单 {total_deal} | 转化率 {conv}%"
        )

    def apply_filter(self):
        kw = self.filter_keyword.get().strip()
        ds = self.filter_date_start.get().strip()
        de = self.filter_date_end.get().strip()

        result = self.all_data
        if kw:
            result = [r for r in result if _fuzzy_match(kw, r.get("商户名称", ""))
                                             or _fuzzy_match(kw, r.get("业态", ""))
                                             or _fuzzy_match(kw, r.get("备注", ""))]
        if ds:
            result = [r for r in result if r.get("日期", "") >= ds]
        if de:
            result = [r for r in result if r.get("日期", "") <= de]
        self.filtered_data = result
        self.render_list()

    def reset_filter(self):
        self.filter_keyword.set("")
        self.filter_date_start.set("")
        self.filter_date_end.set("")
        self.filtered_data = list(self.all_data)
        self.render_list()

    def refresh_and_render(self):
        self.refresh_data()
        self.filtered_data = list(self.all_data)
        self.apply_filter()

    # ─────────────── 获取选中行原始数据 ───────────────
    def _get_selected_raw(self):
        sel = self.tree.selection()
        if not sel:
            return None
        idx = int(sel[0])
        if idx < len(self.filtered_data):
            return self.filtered_data[idx]
        return None

    # ─────────────── 补录/修改 ───────────────
    def _open_edit_window(self, record=None):
        """record=None 表示新增，否则为修改"""
        is_edit = record is not None
        win = tk.Toplevel(self.parent)
        win.title("修改经营记录" if is_edit else "补录经营数据")
        win.geometry("440x480")
        win.transient(self.parent)
        win.grab_set()

        merchants = get_merchant_list()

        row = 0
        ttk.Label(win, text="商户名称：").grid(row=row, column=0, sticky="w", padx=10, pady=6)
        merchant_var = tk.StringVar(value=record.get("商户名称", "") if is_edit else "")

        # 改为搜索选择：只读 Entry + 搜索按钮
        merch_frame = ttk.Frame(win)
        merch_frame.grid(row=row, column=1, padx=10, sticky="w")
        merchant_entry = ttk.Entry(merch_frame, textvariable=merchant_var,
                                   width=22, state="readonly")
        merchant_entry.pack(side="left")

        def _open_merchant_search():
            """弹出搜索选择窗口"""
            chosen = utils.search_select_window(
                win, "选择商户（搜索）", merchants, width=420, height=450
            )
            if chosen:
                merchant_var.set(chosen)
                _on_merchant_change()

        ttk.Button(merch_frame, text="🔍 搜索选择",
                    command=_open_merchant_search).pack(side="left", padx=(6, 0))

        def _on_merchant_change(event=None):
            fmt = _get_shop_format(merchant_var.get())
            if fmt:
                format_var.set(fmt)

        row += 1

        ttk.Label(win, text="日期：").grid(row=row, column=0, sticky="w", padx=10, pady=6)
        date_var = tk.StringVar(value=record.get("日期", date.today().strftime("%Y-%m-%d")) if is_edit
                                else date.today().strftime("%Y-%m-%d"))
        de = ttk.Entry(win, textvariable=date_var, state="readonly", width=27, cursor="arrow")
        de.grid(row=row, column=1, padx=10)
        de.bind("<Button-1>", lambda _: PopupCalendar(win, date_var.set))
        row += 1

        ttk.Label(win, text="营业额(元)：").grid(row=row, column=0, sticky="w", padx=10, pady=6)
        revenue_var = tk.StringVar(value=str(record.get("营业额", "")) if is_edit else "")
        ttk.Entry(win, textvariable=revenue_var, width=27).grid(row=row, column=1, padx=10)
        row += 1

        ttk.Label(win, text="进店客流(人次)：").grid(row=row, column=0, sticky="w", padx=10, pady=6)
        footfall_var = tk.StringVar(value=str(record.get("客流量", "")) if is_edit else "")
        ttk.Entry(win, textvariable=footfall_var, width=27).grid(row=row, column=1, padx=10)
        row += 1

        ttk.Label(win, text="成交量(单)：").grid(row=row, column=0, sticky="w", padx=10, pady=6)
        deal_var = tk.StringVar(value=str(record.get("成交量", "")) if is_edit else "")
        ttk.Entry(win, textvariable=deal_var, width=27).grid(row=row, column=1, padx=10)
        ttk.Label(win, text="（成交订单数）", foreground="#888",
                  font=("微软雅黑", 8)).grid(row=row, column=2, sticky="w")
        row += 1

        ttk.Label(win, text="业态：").grid(row=row, column=0, sticky="w", padx=10, pady=6)
        format_var = tk.StringVar(value=record.get("业态", "") if is_edit else "")
        format_entry = ttk.Entry(win, textvariable=format_var, width=27, state="readonly")
        format_entry.grid(row=row, column=1, padx=10)
        ttk.Label(win, text="自动从合同同步", foreground="#888",
                  font=("微软雅黑", 8)).grid(row=row, column=2, sticky="w")
        row += 1

        if is_edit and merchant_var.get():
            _on_merchant_change()

        ttk.Label(win, text="备注：").grid(row=row, column=0, sticky="w", padx=10, pady=6)
        remark_var = tk.StringVar(value=record.get("备注", "") if is_edit else "")
        ttk.Entry(win, textvariable=remark_var, width=27).grid(row=row, column=1, padx=10)
        row += 1

        err_var = tk.StringVar()
        ttk.Label(win, textvariable=err_var, foreground="red",
                  font=("微软雅黑", 9)).grid(row=row, column=0, columnspan=3, padx=10)
        row += 1

        def save():
            name = merchant_var.get().strip()
            d    = date_var.get().strip()
            rev  = revenue_var.get().strip()
            foot = footfall_var.get().strip()
            deal = deal_var.get().strip()
            fmt  = format_var.get().strip()
            rmk  = remark_var.get().strip()

            if not name:
                err_var.set("请选择商户名称")
                return
            try:
                datetime.strptime(d, "%Y-%m-%d")
            except Exception:
                err_var.set("日期格式错误，请使用 YYYY-MM-DD")
                return
            if not rev:
                err_var.set("营业额不能为空")
                return
            try:
                rev_f = round(float(rev), 2)
            except Exception:
                err_var.set("营业额请输入数字")
                return
            foot_val = ""
            if foot:
                try:
                    foot_val = int(foot)
                except Exception:
                    err_var.set("进店客流请输入整数")
                    return
            deal_val = ""
            if deal:
                try:
                    deal_val = int(deal)
                except Exception:
                    err_var.set("成交量请输入整数")
                    return

            cno = ""
            project = ""
            for c in load_contracts():
                if c.get("商户名称", "").strip() == name:
                    cno = c.get("合同号", "")
                    project = c.get("所属项目", "")
                    break

            all_data = load_business_data()

            # 提取旧记录标识（编辑模式用）
            old_cno  = record.get("合同号", "") if is_edit else ""
            old_date = record.get("日期", "")   if is_edit else ""

            # ── 重复检查 ──
            is_same = is_edit and (cno == old_cno and d == old_date)
            if not is_same:
                existing = [r for r in all_data
                           if r.get("合同号") == cno and r.get("日期") == d]
                if existing:
                    exist_name = existing[0].get("商户名称", name)
                    if not messagebox.askyesno(
                        "重复记录",
                        f"「{exist_name}」在 {d} 已有经营记录\n\n是否覆盖已有记录？"
                    ):
                        return

            if is_edit:
                # 先删除旧记录（MySQL UPSERT 不会自动清理 key 变更后的旧行）
                delete_business_data(old_cno, old_date)
                updated = False
                for i, r in enumerate(all_data):
                    if r.get("合同号") == old_cno and r.get("日期") == old_date:
                        all_data[i] = {
                            "合同号":   cno,
                            "商户名称": name,
                            "日期":     d,
                            "营业额":   rev_f,
                            "客流量":   foot_val,
                            "成交量":   deal_val,
                            "业态":     fmt,
                            "录入时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "备注":     rmk,
                            "所属项目": project
                        }
                        updated = True
                        break
                if not updated:
                    err_var.set("未找到原记录，请刷新后重试")
                    return
            else:
                all_data = [r for r in all_data
                            if not (r.get("合同号") == cno and r.get("日期") == d)]
                all_data.append({
                    "合同号":   cno,
                    "商户名称": name,
                    "日期":     d,
                    "营业额":   rev_f,
                    "客流量":   foot_val,
                    "成交量":   deal_val,
                    "业态":     fmt,
                    "录入时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "备注":     rmk,
                    "所属项目": project
                })

            save_business_data(all_data)
            op_type = "修改" if is_edit else "新增"
            utils.log_operation(op_type, "经营数据", f"{op_type}经营记录 {name} {d}", cno)
            win.destroy()
            self.refresh_and_render()
            messagebox.showinfo("成功", "经营数据已保存！")

        btn_row = ttk.Frame(win)
        btn_row.grid(row=row, column=0, columnspan=3, pady=10)
        ttk.Button(btn_row, text="保存", command=save).pack(side="left", padx=10)
        ttk.Button(btn_row, text="取消", command=win.destroy).pack(side="left", padx=10)

    def add_record(self):
        self._open_edit_window(record=None)

    def edit_record(self):
        rec = self._get_selected_raw()
        if not rec:
            messagebox.showwarning("提示", "请先选择一条记录")
            return
        self._open_edit_window(record=rec)

    def delete_record(self):
        rec = self._get_selected_raw()
        if not rec:
            messagebox.showwarning("提示", "请先选择一条记录")
            return
        name = rec.get("商户名称", "")
        d    = rec.get("日期", "")
        cno  = rec.get("合同号", "")
        if not messagebox.askyesno("确认删除",
                f"确定要删除【{name}】在【{d}】的经营数据吗？\n此操作不可撤销。"):
            return
        delete_business_data(cno, d)
        utils.log_operation("删除", "经营数据", f"删除经营记录 {name} {d}", cno)
        self.refresh_and_render()
        messagebox.showinfo("成功", "记录已删除")

    # ─────────────── 趋势图 ───────────────
    def show_chart(self):
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            import matplotlib.pyplot as plt
            import matplotlib.font_manager as fm
        except ImportError:
            messagebox.showwarning(
                "缺少依赖",
                "绘图功能需要 matplotlib 库\n"
                "请在命令行执行：pip install matplotlib\n然后重新启动程序")
            return

        try:
            plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
            plt.rcParams["axes.unicode_minus"] = False
        except Exception:
            pass

        if not self.filtered_data:
            messagebox.showinfo("提示", "当前没有数据可绘图，请先筛选数据")
            return

        merchant = self.filter_merchant.get()

        if merchant and merchant != "全部":
            groups = {merchant: [r for r in self.filtered_data if r.get("商户名称") == merchant]}
        else:
            groups = {}
            for r in self.filtered_data:
                m = r.get("商户名称", "未知")
                groups.setdefault(m, []).append(r)

        fig, axes = plt.subplots(1, 1, figsize=(10, 5))
        ax2 = axes.twinx()
        fig.suptitle("营业额 & 成交量趋势", fontsize=14)

        for m_name, records in groups.items():
            records_sorted = sorted(records, key=lambda x: x.get("日期", ""))
            dates = [r.get("日期", "") for r in records_sorted]
            revs  = []
            deals = []
            for r in records_sorted:
                try:
                    revs.append(float(r.get("营业额", 0)))
                except Exception:
                    revs.append(0)
                try:
                    deals.append(int(r.get("成交量", 0)))
                except Exception:
                    deals.append(0)
            if dates and revs:
                axes.plot(dates, revs, marker="o", markersize=4, label=f"{m_name} 营业额", linewidth=1.5)
            if dates and any(d > 0 for d in deals):
                ax2.plot(dates, deals, marker="s", markersize=4, linestyle="--", label=f"{m_name} 成交量", linewidth=1, alpha=0.7)

        if len(groups) <= 3:
            lines1, labels1 = axes.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            axes.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc="upper left")
        axes.set_xlabel("日期", fontsize=10)
        axes.set_ylabel("营业额（元）", fontsize=10, color="#2980b9")
        ax2.set_ylabel("成交量（单）", fontsize=10, color="#e67e22")
        axes.tick_params(axis="y", labelcolor="#2980b9")
        ax2.tick_params(axis="y", labelcolor="#e67e22")
        axes.tick_params(axis="x", rotation=45, labelsize=8)
        axes.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        plt.show()

    # ─────────────── 导出 CSV ───────────────
    def export_csv(self):
        if not self.filtered_data:
            messagebox.showinfo("提示", "当前没有数据可导出")
            return
        path = filedialog.asksaveasfilename(
            title="导出经营数据 CSV",
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
            initialfile=f"经营数据_{date.today().strftime('%Y%m%d')}.csv"
        )
        if not path:
            return
        headers = ["商户名称", "日期", "业态", "营业额(元)", "进店客流(人次)", "成交量(单)", "录入时间", "备注"]
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for r in sorted(self.filtered_data,
                                key=lambda x: (x.get("商户名称", ""), x.get("日期", ""))):
                    writer.writerow([
                        r.get("商户名称", ""),
                        r.get("日期", ""),
                        r.get("业态", ""),
                        r.get("营业额", ""),
                        r.get("客流量", ""),
                        r.get("成交量", ""),
                        r.get("录入时间", ""),
                        r.get("备注", "")
                    ])
            messagebox.showinfo("导出成功", f"已导出 {len(self.filtered_data)} 条记录\n{path}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    root.title("经营数据管理")
    root.geometry("1100x700")
    root.state("zoomed")
    BusinessDataGUI(root)
    root.mainloop()
