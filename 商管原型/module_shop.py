import json
import tkinter as tk
from tkinter import ttk, messagebox

from module_contract import sync_shop_status
from utils import (
    SCRIPT_DIR, PROJECT_OPTIONS, BUSINESS_TYPE, SHOP_STATUS,
    load_shops, save_shops, delete_shop, check_shop_no_exists,
    get_contracts_by_shop
)
import utils

DATA_FILE = SCRIPT_DIR + "\\shops_data.json"

FIELD_LIST = [
    "铺位号", "所属项目", "位置", "铺位状态", "适用业态",
    "建筑面积(㎡)", "使用面积(㎡)", "基准租金(元/㎡/天)"
]

class ShopManageGUI:
    def __init__(self, root):
        self.root = root
        sync_shop_status()          # 打开即同步合同→铺位状态
        self.all_data = load_shops()
        self.filtered_data = self.all_data.copy()
        self.create_btn()
        self.create_filter()
        self.create_table()
        self.refresh_table()

    def create_filter(self):
        f = ttk.LabelFrame(self.root, text="筛选条件")
        f.pack(fill=tk.X, padx=10, pady=5)

        self.f_project = tk.StringVar()
        self.f_status = tk.StringVar()
        self.f_area_min = tk.StringVar()
        self.f_area_max = tk.StringVar()
        self.f_price_min = tk.StringVar()
        self.f_price_max = tk.StringVar()
        self.f_business_types = {t: tk.BooleanVar() for t in BUSINESS_TYPE}

        ttk.Label(f, text="项目：").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        cb_p = ttk.Combobox(f, textvariable=self.f_project, values=[""] + PROJECT_OPTIONS, state="readonly", width=15)
        cb_p.grid(row=0, column=1, pady=2)

        ttk.Label(f, text="状态：").grid(row=0, column=2, sticky=tk.W, padx=5, pady=2)
        cb_s = ttk.Combobox(f, textvariable=self.f_status, values=[""] + SHOP_STATUS, state="readonly", width=15)
        cb_s.grid(row=0, column=3, pady=2)

        ttk.Label(f, text="面积：").grid(row=0, column=4, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(f, textvariable=self.f_area_min, width=8).grid(row=0, column=5, pady=2)
        ttk.Label(f, text="~").grid(row=0, column=6, pady=2)
        ttk.Entry(f, textvariable=self.f_area_max, width=8).grid(row=0, column=7, pady=2)

        ttk.Label(f, text="基准租金：").grid(row=0, column=8, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(f, textvariable=self.f_price_min, width=8).grid(row=0, column=9, pady=2)
        ttk.Label(f, text="~").grid(row=0, column=10, pady=2)
        ttk.Entry(f, textvariable=self.f_price_max, width=8).grid(row=0, column=11, pady=2)

        ttk.Button(f, text="执行筛选", command=self.do_filter).grid(row=0, column=12, padx=5, pady=2)
        ttk.Button(f, text="清空条件", command=self.clear_filter).grid(row=0, column=13, padx=5, pady=2)

        # 适用业态勾选
        ttk.Label(f, text="适用业态：").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        type_frame = ttk.Frame(f)
        type_frame.grid(row=1, column=1, columnspan=13, sticky=tk.W)
        for i, t in enumerate(BUSINESS_TYPE):
            ttk.Checkbutton(type_frame, text=t, variable=self.f_business_types[t]).grid(row=0, column=i, padx=5)

    def create_btn(self):
        f = ttk.Frame(self.root)
        f.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(f, text="新增商铺", command=self.add).pack(side=tk.LEFT, padx=5)
        ttk.Button(f, text="修改商铺", command=self.edit).pack(side=tk.LEFT, padx=5)
        ttk.Button(f, text="删除商铺", command=self.del_shop).pack(side=tk.LEFT, padx=5)

    def create_table(self):
        f = ttk.Frame(self.root)
        f.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.tree = ttk.Treeview(f, columns=FIELD_LIST, show="headings")
        y = ttk.Scrollbar(f, orient=tk.VERTICAL, command=self.tree.yview)
        x = ttk.Scrollbar(f, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)

        for col in FIELD_LIST:
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=120)

        self.tree.tag_configure("even", background="#f7faff")
        self.tree.tag_configure("odd",  background="#ffffff")

        self.tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        f.rowconfigure(0, weight=1)
        f.columnconfigure(0, weight=1)

        self._sort_col = "铺位号"
        self._sort_rev = True

    def _sort_by(self, col):
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            self._sort_rev = True
        self.refresh_table()

    def refresh_table(self, resync=False):
        if resync:
            sync_shop_status()
            self.all_data = load_shops()
            self.filtered_data = self.all_data.copy()
        # 排序
        num_cols = {"建筑面积(㎡)", "使用面积(㎡)", "基准租金(元/㎡/天)"}
        def _key(row):
            v = row.get(self._sort_col, "")
            if self._sort_col in num_cols:
                try: return float(v)
                except: return 0.0
            return str(v)
        data = sorted(self.filtered_data, key=_key, reverse=self._sort_rev)
        self.filtered_data = data
        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(data):
            tag = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", tk.END, values=[row.get(f, "") for f in FIELD_LIST], tags=(tag,))

    def do_filter(self):
        sync_shop_status()
        self.all_data = load_shops()
        selected_types = [t for t, var in self.f_business_types.items() if var.get()]
        res = []
        for shop in self.all_data:
            if self.f_project.get() and shop["所属项目"] != self.f_project.get():
                continue
            if self.f_status.get() and shop["铺位状态"] != self.f_status.get():
                continue
            if selected_types:
                shop_types = [x.strip() for x in shop.get("适用业态", "").replace(",", "、").split("、") if x.strip()]
                if not any(t in shop_types for t in selected_types):
                    continue
            try:
                a = float(shop.get("建筑面积(㎡)", shop.get("计租面积(㎡)", "0") or "0"))
                if self.f_area_min.get() and a < float(self.f_area_min.get()):
                    continue
                if self.f_area_max.get() and a > float(self.f_area_max.get()):
                    continue
                p = float(shop["基准租金(元/㎡/天)"])
                if self.f_price_min.get() and p < float(self.f_price_min.get()):
                    continue
                if self.f_price_max.get() and p > float(self.f_price_max.get()):
                    continue
            except:
                pass
            res.append(shop)
        self.filtered_data = res
        self.refresh_table()

    def clear_filter(self):
        sync_shop_status()
        self.all_data = load_shops()
        self.f_project.set("")
        self.f_status.set("")
        self.f_area_min.set("")
        self.f_area_max.set("")
        self.f_price_min.set("")
        self.f_price_max.set("")
        for var in self.f_business_types.values():
            var.set(False)
        self.filtered_data = self.all_data.copy()
        try:
            self.refresh_table()
        except tk.TclError:
            pass

    # ─────── 共享表单构建器 ───────
    def _build_shop_form(self, win, title, defaults=None):
        """构建商铺表单布局，返回 (main_frame, last_row, widgets, check_vars, err_labels, clear_errors)"""
        win.title(title)
        win.resizable(False, False)

        main = ttk.Frame(win, padding=20)
        main.pack(fill=tk.BOTH, expand=True)

        widgets   = {}
        check_vars = {t: tk.BooleanVar() for t in BUSINESS_TYPE}
        err_labels = {}
        ERR_FONT   = ("微软雅黑", 9)

        def v_num(a, v):
            return v.replace('.', '', 1).isdigit() if a == '1' else True
        vcmd = (win.register(v_num), '%d', '%P')

        # 预填值（编辑模式）
        prefill = defaults or {}

        def _row(label_text, field_key, widget, sticky_err="W"):
            """添加一行：标签 | 输入控件 | 错误提示"""
            nonlocal row
            ttk.Label(main, text=label_text, width=18, anchor=tk.E)\
                .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.E)
            widget.grid(row=row, column=1, pady=5, sticky=tk.W)
            err = ttk.Label(main, text="", foreground="red", font=ERR_FONT)
            err.grid(row=row, column=2, padx=(8, 0), pady=5, sticky=sticky_err)
            err_labels[field_key] = err
            widgets[field_key] = widget
            row += 1

        row = 0

        # 铺位号
        e_no = ttk.Entry(main, width=32)
        e_no.insert(0, prefill.get("铺位号", ""))
        _row("铺位号：", "铺位号", e_no)

        # 所属项目
        e_prj = ttk.Combobox(main, values=PROJECT_OPTIONS, state="readonly", width=30)
        if prefill.get("所属项目"):
            e_prj.set(prefill["所属项目"])
        _row("所属项目：", "所属项目", e_prj)

        # 位置
        e_loc = ttk.Entry(main, width=32)
        e_loc.insert(0, prefill.get("位置", ""))
        _row("位置：", "位置", e_loc)

        # 铺位状态
        e_st = ttk.Combobox(main, values=SHOP_STATUS, state="readonly", width=30)
        if prefill.get("铺位状态"):
            e_st.set(prefill["铺位状态"])
        _row("铺位状态：", "铺位状态", e_st)

        # 适用业态（checkbuttons 分两行排列）
        ttk.Label(main, text="适用业态：", width=18, anchor=tk.E)\
            .grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.NE)
        type_frame = ttk.Frame(main)
        type_frame.grid(row=row, column=1, pady=5, sticky=tk.W)
        old_types = prefill.get("适用业态", "").split("、") if prefill else []
        for i, t in enumerate(BUSINESS_TYPE):
            c = i % 5
            r = i // 5
            if t in old_types:
                check_vars[t].set(True)
            ttk.Checkbutton(type_frame, text=t, variable=check_vars[t])\
                .grid(row=r, column=c, padx=(0, 12), pady=1, sticky=tk.W)
        err_type = ttk.Label(main, text="", foreground="red", font=ERR_FONT)
        err_type.grid(row=row, column=2, padx=(8, 0), pady=5, sticky=tk.NW)
        err_labels["适用业态"] = err_type
        row += 1

        # 建筑面积
        e_area = ttk.Entry(main, width=32, validate="key", validatecommand=vcmd)
        e_area.insert(0, prefill.get("建筑面积(㎡)", prefill.get("计租面积(㎡)", "")))
        _row("建筑面积(㎡)：", "建筑面积(㎡)", e_area)

        # 使用面积
        e_use_area = ttk.Entry(main, width=32, validate="key", validatecommand=vcmd)
        e_use_area.insert(0, prefill.get("使用面积(㎡)", ""))
        _row("使用面积(㎡)：", "使用面积(㎡)", e_use_area)

        # 基准租金
        e_rent = ttk.Entry(main, width=32, validate="key", validatecommand=vcmd)
        e_rent.insert(0, prefill.get("基准租金(元/㎡/天)", ""))
        _row("基准租金(元/㎡/天)：", "基准租金(元/㎡/天)", e_rent)

        def clear_errors():
            for lbl in err_labels.values():
                lbl.configure(text="")

        return main, row, widgets, check_vars, err_labels, clear_errors

    # ─────── 新增 ───────
    def add(self):
        win = tk.Toplevel(self.root)
        main, last_row, widgets, check_vars, err_labels, clear_errors = \
            self._build_shop_form(win, "新增商铺")

        def submit():
            clear_errors()
            has_err = False

            no = widgets["铺位号"].get().strip()
            if not no:
                err_labels["铺位号"].configure(text="铺位号不能为空")
                has_err = True
            elif check_shop_no_exists(no):
                err_labels["铺位号"].configure(text="铺位号已存在")
                has_err = True

            if not widgets["所属项目"].get():
                err_labels["所属项目"].configure(text="请选择所属项目")
                has_err = True

            if not widgets["铺位状态"].get():
                err_labels["铺位状态"].configure(text="请选择铺位状态")
                has_err = True

            # 使用面积不能大于建筑面积
            ba = widgets["建筑面积(㎡)"].get().strip()
            ua = widgets["使用面积(㎡)"].get().strip()
            if ba and ua:
                try:
                    if float(ua) > float(ba):
                        err_labels["使用面积(㎡)"].configure(text="使用面积不能大于建筑面积")
                        has_err = True
                except ValueError:
                    pass

            if has_err:
                return

            d = {
                "铺位号": no,
                "所属项目": widgets["所属项目"].get(),
                "位置": widgets["位置"].get().strip(),
                "铺位状态": widgets["铺位状态"].get(),
                "适用业态": "、".join([t for t, v in check_vars.items() if v.get()]),
                "建筑面积(㎡)": widgets["建筑面积(㎡)"].get().strip(),
                "使用面积(㎡)": widgets["使用面积(㎡)"].get().strip(),
                "基准租金(元/㎡/天)": widgets["基准租金(元/㎡/天)"].get().strip()
            }
            self.all_data.append(d)
            if save_shops(self.all_data):
                utils.log_operation("新增", "商铺", f"新增商铺 {no}", no)
                win.destroy()
                self.clear_filter()

        # 按钮行
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=last_row, column=0, columnspan=3, pady=(15, 0))
        ttk.Button(btn_frame, text="保存", command=submit).pack(side=tk.LEFT, padx=5)

    def edit(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请选择")
            return
        idx = self.tree.index(sel[0])
        old = self.filtered_data[idx]
        win = tk.Toplevel(self.root)
        main, last_row, widgets, check_vars, err_labels, clear_errors = \
            self._build_shop_form(win, "修改商铺", defaults=old)

        def submit():
            clear_errors()
            has_err = False

            new_no = widgets["铺位号"].get().strip()
            if not new_no:
                err_labels["铺位号"].configure(text="铺位号不能为空")
                has_err = True
            elif new_no != old["铺位号"] and check_shop_no_exists(new_no):
                err_labels["铺位号"].configure(text="铺位号已存在")
                has_err = True

            if not widgets["所属项目"].get():
                err_labels["所属项目"].configure(text="请选择所属项目")
                has_err = True

            if not widgets["铺位状态"].get():
                err_labels["铺位状态"].configure(text="请选择铺位状态")
                has_err = True

            # 使用面积不能大于建筑面积
            ba = widgets["建筑面积(㎡)"].get().strip()
            ua = widgets["使用面积(㎡)"].get().strip()
            if ba and ua:
                try:
                    if float(ua) > float(ba):
                        err_labels["使用面积(㎡)"].configure(text="使用面积不能大于建筑面积")
                        has_err = True
                except ValueError:
                    pass

            if has_err:
                return

            old["铺位号"] = new_no
            old["所属项目"] = widgets["所属项目"].get()
            old["位置"] = widgets["位置"].get().strip()
            old["铺位状态"] = widgets["铺位状态"].get()
            old["适用业态"] = "、".join([t for t, v in check_vars.items() if v.get()])
            old["建筑面积(㎡)"] = widgets["建筑面积(㎡)"].get().strip()
            old["使用面积(㎡)"] = widgets["使用面积(㎡)"].get().strip()
            old["基准租金(元/㎡/天)"] = widgets["基准租金(元/㎡/天)"].get().strip()

            if save_shops(self.all_data):
                utils.log_operation("修改", "商铺", f"修改商铺 {new_no}", new_no)
                win.destroy()
                self.clear_filter()

        # 按钮行
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=last_row, column=0, columnspan=3, pady=(15, 0))
        ttk.Button(btn_frame, text="保存", command=submit).pack(side=tk.LEFT, padx=5)

    def del_shop(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择要删除的商铺")
            return

        idx = self.tree.index(sel[0])
        real_idx = self.all_data.index(self.filtered_data[idx])
        shop_no = self.all_data[real_idx].get("铺位号", "")

        # 检查关联合同
        related = get_contracts_by_shop(shop_no)
        if related:
            lines = [f"铺位「{shop_no}」下有 {len(related)} 个关联合同："]
            for c in related:
                lines.append(f"  · {c['合同号']}（{c['商户名称']}）[{c['合同状态']}]")
            lines.append("")
            lines.append("⚠️ 删除商铺将同时删除上述合同的：")
            lines.append("  · 缴费记录")
            lines.append("  · 经营数据")
            lines.append("  · 合同本身")
            msg = "\n".join(lines)
        else:
            msg = f"确认删除铺位「{shop_no}」？\n\n此操作不可逆。"

        if not messagebox.askyesno("确认删除", msg):
            return

        # 执行删除
        del self.all_data[real_idx]
        success = delete_shop(shop_no)
        if success:
            utils.log_operation("删除", "商铺",
                f"删除商铺 {shop_no}（含 {len(related)} 个关联合同）" if related else f"删除商铺 {shop_no}",
                shop_no)
            messagebox.showinfo("成功", f"铺位「{shop_no}」已删除")
            # 删除后同步受影响铺位状态
            sync_shop_status()
        else:
            messagebox.showerror("失败", f"铺位「{shop_no}」删除失败，请重试")
        self.clear_filter()

if __name__ == "__main__":
    root = tk.Tk()
    app = ShopManageGUI(root)
    root.mainloop()
