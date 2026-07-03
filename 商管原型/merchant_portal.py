"""
merchant_portal.py
商户端 Web 门户 —— 手机/电脑浏览器均可访问
提供：
  1. 商户登录（合同号 + 商户名）
  2. 合同详情查看
  3. 租金缴费进度查看
  4. 每日经营数据录入与历史查看
运行：python merchant_portal.py
访问：http://本机IP:5050  （手机和电脑在同一局域网即可）
"""

import os
import sys
import json
from datetime import datetime, date, timedelta
from functools import wraps

from flask import (Flask, request, session, redirect, url_for,
                   render_template_string, jsonify, abort)
from dateutil.relativedelta import relativedelta

# ─────────────────────────── 路径 & 数据工具（从 utils 导入） ───────────────────────────
from utils import (
    _get_base_dir, CYCLE_MAP, get_shop_area, get_paid,
    get_property_fee_paid,
    load_contracts, load_business_data, save_business_data,
    _get_period_revenue, generate_rent_plan
)

# ─────────────────────────── 经营数据工具 ───────────────────────────
def get_merchant_business(contract_no):
    return [r for r in load_business_data() if r.get("合同号") == contract_no]

# ─────────────────────────── Flask 应用 ───────────────────────────
app = Flask(__name__)
app.secret_key = "xiaoniu_b_portal_2026"

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("contract_no"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def find_contract(contract_no, merchant_name):
    for c in load_contracts():
        if (str(c.get("合同号", "")).strip() == contract_no.strip()
                and str(c.get("商户名称", "")).strip() == merchant_name.strip()):
            return c
    return None

# ──────────────────────────────────────────────────────────────────
#  公共 HTML 模板（响应式，兼容手机）
# ──────────────────────────────────────────────────────────────────
BASE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
<title>LCP商管 · 商户门户</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f7fa;color:#333;font-size:15px}
  .topbar{background:#2980b9;color:#fff;padding:12px 16px;display:flex;align-items:center;justify-content:space-between}
  .topbar h1{font-size:18px;font-weight:700}
  .topbar a{color:#dce9f5;font-size:13px;text-decoration:none}
  .nav{display:flex;background:#1a6699;overflow-x:auto}
  .nav a{color:#c8dff0;padding:10px 18px;text-decoration:none;white-space:nowrap;font-size:14px}
  .nav a.active,.nav a:hover{background:#2980b9;color:#fff}
  .container{padding:16px;max-width:900px;margin:0 auto}
  .card{background:#fff;border-radius:8px;padding:16px;margin-bottom:14px;box-shadow:0 1px 4px rgba(0,0,0,.08)}
  .card h2{font-size:16px;color:#2980b9;margin-bottom:10px;border-bottom:1px solid #e8f0fa;padding-bottom:6px}
  .kv{display:flex;flex-wrap:wrap;gap:8px 0}
  .kv-item{width:50%;min-width:160px;padding:3px 0}
  .kv-item .k{color:#888;font-size:13px}
  .kv-item .v{font-weight:600;color:#222}
  table{width:100%;border-collapse:collapse;font-size:14px}
  th{background:#e8f0fa;color:#2980b9;padding:8px 10px;text-align:left}
  td{padding:8px 10px;border-bottom:1px solid #f0f0f0}
  tr:last-child td{border:none}
  .badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600}
  .badge-green{background:#e8f8f5;color:#27ae60}
  .badge-red{background:#fdf0f0;color:#e74c3c}
  .badge-blue{background:#eaf4fb;color:#2980b9}
  .badge-gray{background:#f0f0f0;color:#888}
  .stat-row{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px}
  .stat-box{flex:1 1 100px;min-width:100px;background:#fff;border-radius:8px;padding:10px 8px;
            box-shadow:0 1px 4px rgba(0,0,0,.08);text-align:center;overflow:hidden}
  .stat-box .label{font-size:11px;color:#888;margin-bottom:4px;white-space:nowrap}
  .stat-box .num{font-size:16px;font-weight:700;word-break:break-all;overflow-wrap:break-word}
  form label{display:block;margin:10px 0 3px;font-size:14px;color:#555;font-weight:600}
  form input,form select,form textarea{
    width:100%;padding:9px 11px;border:1px solid #d0d8e4;border-radius:6px;
    font-size:14px;color:#333;background:#fff;margin-bottom:4px}
  form textarea{min-height:80px;resize:vertical}
  .btn{display:inline-block;padding:10px 24px;border:none;border-radius:6px;
       font-size:15px;font-weight:600;cursor:pointer;text-align:center}
  .btn-primary{background:#2980b9;color:#fff}
  .btn-primary:hover{background:#1a6699}
  .btn-danger{background:#e74c3c;color:#fff}
  .alert{padding:10px 14px;border-radius:6px;margin-bottom:12px;font-size:14px}
  .alert-error{background:#fdf0f0;color:#c0392b;border:1px solid #f5c6cb}
  .alert-success{background:#e8f8f5;color:#1a7a4a;border:1px solid #b2dfdb}
  .overdue td{background:#fff5f5;color:#c0392b}
  @media(max-width:600px){.kv-item{width:100%}.stat-box{min-width:80px}}
</style>
</head>
<body>
<div class="topbar">
  <h1>🏬 LCP商管 · 商户门户</h1>
  {% if session.contract_no %}
  <a href="{{ url_for('logout') }}">退出登录</a>
  {% endif %}
</div>
{% if session.contract_no %}
<div class="nav">
  <a href="{{ url_for('dashboard') }}" class="{{ 'active' if active_page=='dashboard' else '' }}">🏠 我的主页</a>
  <a href="{{ url_for('contract_view') }}" class="{{ 'active' if active_page=='contract' else '' }}">📄 合同详情</a>
  <a href="{{ url_for('rent_view') }}" class="{{ 'active' if active_page=='rent' else '' }}">💰 租金情况</a>
  <a href="{{ url_for('business_history') }}" class="{{ 'active' if active_page=='history' else '' }}">📊 经营数据</a>
</div>
{% endif %}
<div class="container">
{% with messages = get_flashed_messages(with_categories=True) %}
{% for cat, msg in messages %}
<div class="alert alert-{{ cat }}">{{ msg }}</div>
{% endfor %}
{% endwith %}
{{ content | safe }}
</div>
</body>
</html>"""

from flask import flash

def render_page(content, active_page=""):
    return render_template_string(BASE_HTML, content=content, active_page=active_page)

# ─────────────────────────── 路由 ───────────────────────────

@app.route("/", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        cno  = request.form.get("contract_no", "").strip()
        name = request.form.get("merchant_name", "").strip()
        c = find_contract(cno, name)
        if c:
            session["contract_no"]    = cno
            session["merchant_name"]  = name
            return redirect(url_for("dashboard"))
        else:
            error = "合同号或商户名称不正确，请重新输入"

    form_html = f"""
    <div class="card" style="max-width:420px;margin:40px auto">
      <h2 style="text-align:center;margin-bottom:20px">商户登录</h2>
      {'<div class="alert alert-error">' + error + '</div>' if error else ''}
      <form method="post">
        <label>合同号</label>
        <input type="text" name="contract_no" placeholder="请输入合同号" required autocomplete="off">
        <label>商户名称</label>
        <input type="text" name="merchant_name" placeholder="请输入商户名称" required autocomplete="off">
        <br>
        <button class="btn btn-primary" style="width:100%;margin-top:6px" type="submit">登 录</button>
      </form>
    </div>"""
    return render_page(form_html)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    cno  = session["contract_no"]
    name = session["merchant_name"]
    c    = find_contract(cno, name)
    if not c:
        session.clear()
        return redirect(url_for("login"))

    today     = date.today()
    plan      = generate_rent_plan(c)
    end_dt    = datetime.strptime(c["租赁结束日期"], "%Y-%m-%d").date()
    days_left = (end_dt - today).days
    lease_start = c.get("租赁开始日期", "")

    # ── 逾期金额（含租金 + 物业费）──
    overdue_rent = 0.0
    overdue_prop = 0.0
    overdue_rows = ""  # 逾期明细表格行
    for i, p in enumerate(plan, 1):
        pay_dt = datetime.strptime(p["支付时间"], "%Y-%m-%d").date()
        if pay_dt < today:
            diff_rent = max(p["应缴金额(元)"] - p["已缴金额(元)"], 0)
            diff_prop = max(p["应缴物业费"] - p.get("已缴物业费", 0), 0)
            if diff_rent > 0 or diff_prop > 0:
                overdue_rent += diff_rent
                overdue_prop += diff_prop
                overdue_rows += (
                    f"<tr class=\"overdue\"><td>{i}</td><td>{p['支付时间']}</td>"
                    f"<td>¥{p['应缴金额(元)']:,.2f}</td><td>¥{p['已缴金额(元)']:,.2f}</td>"
                    f"<td>¥{diff_rent:,.2f}</td>"
                    f"<td>¥{diff_prop:,.2f}</td>"
                    f"<td>¥{diff_rent + diff_prop:,.2f}</td></tr>"
                )
    overdue_total = round(overdue_rent + overdue_prop, 2)

    # ── 下次缴费信息（只取未来未结清的最近一期）──
    next_days = "—"
    next_rent = 0.0
    next_prop = 0.0
    for p in plan:
        pay_dt = datetime.strptime(p["支付时间"], "%Y-%m-%d").date()
        if pay_dt <= today:
            continue
        diff = max(p["应缴金额(元)"] - p["已缴金额(元)"], 0) + max(p.get("应缴物业费", 0) - p.get("已缴物业费", 0), 0)
        if diff > 0:
            next_days = (pay_dt - today).days
            next_rent = p["应缴金额(元)"]
            next_prop = p.get("应缴物业费", 0)
            break

    stat_html = f"""
    <div class="card"><h2>📊 概要</h2>
    <div class="stat-row">
      <div class="stat-box"><div class="label">租赁开始日期</div>
        <div class="num" style="color:#2980b9">{lease_start}</div></div>
      <div class="stat-box"><div class="label">合同剩余天数</div>
        <div class="num" style="color:{'#27ae60' if days_left>90 else '#e74c3c'}">{days_left}</div></div>
      <div class="stat-box"><div class="label">距下次缴费天数</div>
        <div class="num" style="color:#27ae60">{next_days}</div></div>
      <div class="stat-box"><div class="label">下次缴费租金</div>
        <div class="num" style="color:#2980b9">¥{next_rent:,.2f}</div></div>
      <div class="stat-box"><div class="label">下次缴费物业费</div>
        <div class="num" style="color:#8e44ad">¥{next_prop:,.2f}</div></div>
      <div class="stat-box"><div class="label">逾期金额</div>
        <div class="num" style="color:#e74c3c">¥{overdue_total:,.2f}</div></div>
    </div></div>"""

    overdue_html = f"""
    <div class="card">
      <h2>⚠️ 逾期金额明细</h2>"""
    if overdue_rows:
        overdue_html += f"""
      <table>
        <tr><th>期次</th><th>应缴日期</th><th>应缴租金</th><th>已缴租金</th><th>欠缴租金</th><th>欠缴物业费</th><th>合计欠款</th></tr>
        {overdue_rows}
      </table>"""
    else:
        overdue_html += """
      <p style="color:#27ae60;margin:10px 0;font-weight:600">🎉 无逾期</p>"""
    overdue_html += """
    </div>"""

    return render_page(stat_html + overdue_html, active_page="dashboard")


@app.route("/contract")
@login_required
def contract_view():
    cno  = session["contract_no"]
    name = session["merchant_name"]
    c    = find_contract(cno, name)
    if not c:
        return redirect(url_for("login"))

    today  = date.today()
    end_dt = datetime.strptime(c["租赁结束日期"], "%Y-%m-%d").date()
    days_left = (end_dt - today).days
    status = c.get("合同状态", "")
    badge_class = {"执行中": "badge-green", "已到期": "badge-red",
                   "已终止": "badge-gray", "待生效": "badge-blue"}.get(status, "badge-gray")

    # ── KV 字段（跳过免租计划，单独渲染）──
    skip_fields = {"自动租金计划", "免租计划"}
    items = [(k, v) for k, v in c.items() if k not in skip_fields]
    kv_html = "".join(
        f'<div class="kv-item"><div class="k">{k}</div><div class="v">{v}</div></div>'
        for k, v in items
    )

    # ── 免租计划格式化 ──
    import json
    free_html = ""
    free_plans_raw = c.get("免租计划", [])
    if isinstance(free_plans_raw, str):
        try:
            free_plans_raw = json.loads(free_plans_raw)
        except:
            free_plans_raw = []
    if isinstance(free_plans_raw, list) and free_plans_raw:
        free_rows = ""
        for i, fp in enumerate(free_plans_raw, 1):
            try:
                s = datetime.strptime(fp["start"], "%Y-%m-%d").date()
                e = datetime.strptime(fp["end"], "%Y-%m-%d").date()
                d = (e - s).days + 1
            except:
                d = 0
            free_rows += f"<tr><td>{i}</td><td>{fp.get('start','')}</td><td>{fp.get('end','')}</td><td>{d}</td></tr>"
        free_html = f"""
    <div class="card">
      <h2>📅 免租计划</h2>
      <table>
        <tr><th>序号</th><th>开始日期</th><th>结束日期</th><th>天数</th></tr>
        {free_rows}
      </table>
    </div>"""

    html = f"""
    <div class="card">
      <h2>📄 合同详情</h2>
      <div style="margin-bottom:10px">
        合同状态：<span class="badge {badge_class}">{status}</span>
        &nbsp; 距到期：<strong style="color:{'#27ae60' if days_left>90 else '#e74c3c'}">{days_left} 天</strong>
      </div>
      <div class="kv">{kv_html}</div>
    </div>
    {free_html}"""
    return render_page(html, active_page="contract")


@app.route("/rent")
@login_required
def rent_view():
    cno  = session["contract_no"]
    name = session["merchant_name"]
    c    = find_contract(cno, name)
    if not c:
        return redirect(url_for("login"))

    today = date.today()
    plan  = generate_rent_plan(c)

    # ── 汇总统计 ──
    total_rent  = round(sum(p["应缴金额(元)"] for p in plan), 2)
    paid_rent   = round(sum(p["已缴金额(元)"] for p in plan), 2)
    total_prop  = round(sum(p.get("应缴物业费", 0) for p in plan), 2)
    paid_prop   = round(sum(p.get("已缴物业费", 0) for p in plan), 2)
    remain_rent = round(total_rent - paid_rent, 2)
    remain_prop = round(total_prop - paid_prop, 2)

    # ── 逾期金额（租金逾期 + 物业费逾期）──
    overdue_total = 0.0
    for p in plan:
        pay_dt = datetime.strptime(p["支付时间"], "%Y-%m-%d").date()
        if pay_dt < today:
            overdue_total += max(p["应缴金额(元)"] - p["已缴金额(元)"], 0)
            overdue_total += max(p.get("应缴物业费", 0) - p.get("已缴物业费", 0), 0)
    overdue_total = round(overdue_total, 2)

    # ── 明细表格 ──
    rows_html = ""
    for i, p in enumerate(plan, 1):
        pay_dt = datetime.strptime(p["支付时间"], "%Y-%m-%d").date()
        rent_val = p["应缴金额(元)"]
        paid_val = p["已缴金额(元)"]
        prop_val = p.get("应缴物业费", 0)
        prop_paid = p.get("已缴物业费", 0)
        diff_rent = round(rent_val - paid_val, 2)
        diff_prop = round(prop_val - prop_paid, 2)

        is_overdue = pay_dt < today and (diff_rent > 0 or diff_prop > 0)
        if is_overdue:
            tr_class = "overdue"
            badge = f'<span class="badge badge-red">逾期</span>'
        elif diff_rent <= 0 and diff_prop <= 0:
            tr_class = ""
            badge = '<span class="badge badge-green">已结清</span>'
        else:
            tr_class = ""
            badge = '<span class="badge badge-blue">待缴</span>'

        rows_html += (
            f'<tr class="{tr_class}"><td>{i}</td><td>{p["支付时间"]}</td>'
            f'<td>¥{rent_val:,.2f}</td><td>¥{prop_val:,.2f}</td>'
            f'<td>¥{rent_val + prop_val:,.2f}</td>'
            f'<td>¥{paid_val:,.2f}</td><td>¥{prop_paid:,.2f}</td>'
            f'<td>{badge}</td></tr>'
        )

    html = f"""
    <div class="stat-row">
      <div class="stat-box"><div class="label">租金总额</div>
        <div class="num" style="color:#2980b9">¥{total_rent:,.2f}</div></div>
      <div class="stat-box"><div class="label">已缴租金</div>
        <div class="num" style="color:#27ae60">¥{paid_rent:,.2f}</div></div>
      <div class="stat-box"><div class="label">租金待缴</div>
        <div class="num" style="color:#e67e22">¥{remain_rent:,.2f}</div></div>
      <div class="stat-box"><div class="label">物业费总额</div>
        <div class="num" style="color:#8e44ad">¥{total_prop:,.2f}</div></div>
      <div class="stat-box"><div class="label">已缴物业费</div>
        <div class="num" style="color:#27ae60">¥{paid_prop:,.2f}</div></div>
      <div class="stat-box"><div class="label">物业费待缴</div>
        <div class="num" style="color:#e67e22">¥{remain_prop:,.2f}</div></div>
    </div>
    <div class="stat-row">
      <div class="stat-box"><div class="label">逾期金额合计</div>
        <div class="num" style="color:#e74c3c">¥{overdue_total:,.2f}</div></div>
    </div>
    <div class="card">
      <h2>💰 缴费计划明细</h2>
      <table>
        <tr><th>#</th><th>应缴日期</th><th>应缴租金</th><th>应缴物业费</th><th>本期应缴</th><th>已缴租金</th><th>已缴物业费</th><th>状态</th></tr>
        {rows_html}
      </table>
    </div>"""
    return render_page(html, active_page="rent")


@app.route("/business/input", methods=["GET", "POST"])
@login_required
def business_input():
    """录入经营数据 — POST 处理提交后跳转到历史页"""
    cno  = session["contract_no"]
    name = session["merchant_name"]

    if request.method == "POST":
        biz_date  = request.form.get("biz_date", "").strip()
        revenue   = request.form.get("revenue", "").strip()
        footfall  = request.form.get("footfall", "").strip()
        deals     = request.form.get("deals", "").strip()
        remark    = request.form.get("remark", "").strip()

        errors = []
        if not biz_date:
            errors.append("请选择日期")
        if not revenue:
            errors.append("营业额不能为空")
        else:
            try:
                revenue = float(revenue)
            except Exception:
                errors.append("营业额格式错误，请填写数字")
        if footfall:
            try:
                footfall = int(footfall)
            except Exception:
                errors.append("客流量请填写整数")
        else:
            footfall = ""
        deal_val = ""
        if deals:
            try:
                deal_val = int(deals)
            except Exception:
                errors.append("成交量请填写整数")
        else:
            deal_val = ""

        # 获取商户的经营业态（从合同）
        biz_format = ""
        c = find_contract(cno, session.get("merchant_name", ""))
        if c:
            biz_format = c.get("经营业态", "")

        if not errors:
            data = load_business_data()
            data = [r for r in data if not (r.get("合同号") == cno and r.get("日期") == biz_date)]
            project = c.get("所属项目", "") if c else ""
            data.append({
                "合同号":    cno,
                "商户名称":  name,
                "日期":      biz_date,
                "营业额":    round(float(revenue), 2),
                "客流量":    footfall,
                "成交量":    deal_val,
                "业态":      biz_format,
                "录入时间":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "备注":      remark,
                "所属项目":  project
            })
            save_business_data(data)
            flash("数据保存成功！", "success")
        else:
            flash("；".join(errors), "error")

        # POST 后重定向到历史页（PRG 模式，避免刷新重复提交）
        return redirect(url_for("business_history"))

    # GET 请求直接跳转到历史页
    return redirect(url_for("business_history"))


@app.route("/business/history", methods=["GET", "POST"])
@login_required
def business_history():
    cno   = session["contract_no"]
    name  = session["merchant_name"]
    today_str = date.today().strftime("%Y-%m-%d")

    # ── POST：内联录入 ──
    if request.method == "POST":
        biz_date  = request.form.get("biz_date", today_str).strip()
        revenue   = request.form.get("revenue", "").strip()
        footfall  = request.form.get("footfall", "").strip()
        deals     = request.form.get("deals", "").strip()
        remark    = request.form.get("remark", "").strip()

        errors = []
        if not biz_date:
            errors.append("请选择日期")
        if not revenue:
            errors.append("营业额不能为空")
        else:
            try:
                revenue = float(revenue)
            except Exception:
                errors.append("营业额格式错误")
        if footfall:
            try: footfall = int(footfall)
            except: errors.append("客流量请填写整数")
        else:
            footfall = ""
        deal_val = ""
        if deals:
            try: deal_val = int(deals)
            except: errors.append("成交量请填写整数")
        else:
            deal_val = ""

        biz_format = ""
        project = ""
        c = find_contract(cno, name)
        if c:
            biz_format = c.get("经营业态", "")
            project = c.get("所属项目", "")

        if not errors:
            data = load_business_data()
            data = [r for r in data if not (r.get("合同号") == cno and r.get("日期") == biz_date)]
            data.append({
                "合同号": cno, "商户名称": name, "日期": biz_date,
                "营业额": round(float(revenue), 2), "客流量": footfall,
                "成交量": deal_val, "业态": biz_format,
                "录入时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "备注": remark,
                "所属项目": project
            })
            save_business_data(data)
            flash("✅ 数据保存成功！", "success")
            return redirect(url_for("business_history"))
        else:
            for e in errors:
                flash(e, "error")
            return redirect(url_for("business_history"))

    # ── GET：展示历史 + 内联录入表单 ──
    all_records = sorted(get_merchant_business(cno),
                         key=lambda x: x.get("日期", ""), reverse=True)

    # ── 时间范围筛选 ──
    start_date = request.args.get("start_date", "").strip()
    end_date   = request.args.get("end_date", "").strip()
    if start_date and end_date:
        records = [r for r in all_records if start_date <= r.get("日期", "") <= end_date]
    elif start_date:
        records = [r for r in all_records if r.get("日期", "") >= start_date]
    elif end_date:
        records = [r for r in all_records if r.get("日期", "") <= end_date]
    else:
        records = all_records

    # ── 筛选表单 HTML ──
    filter_html = f"""
    <div class="card" style="padding:10px 14px;margin-bottom:10px">
      <form method="get" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
        <span style="font-size:13px;color:#888;white-space:nowrap">📅 时间范围：</span>
        <input type="date" name="start_date" value="{start_date}" style="width:auto;min-width:140px;padding:7px 10px;font-size:13px;margin:0">
        <span style="font-size:13px;color:#888">至</span>
        <input type="date" name="end_date" value="{end_date}" style="width:auto;min-width:140px;padding:7px 10px;font-size:13px;margin:0">
        <button class="btn btn-primary" type="submit" style="font-size:13px;padding:7px 14px;margin:0">筛选</button>
        {'<a href="?" class="btn" style="font-size:13px;padding:7px 14px;background:#ddd;color:#333;text-decoration:none;margin:0">清除</a>' if (start_date or end_date) else ''}
      </form>
    </div>"""

    # 检查今日是否已有录入（仅用于提示，不预填数据）
    existing = next((r for r in all_records if r.get("日期") == today_str), None)
    existing_tip = '<p style="color:#e67e22;font-size:13px;margin:0 0 8px">⚠️ 今日已有录入数据，提交将覆盖原记录</p>' if existing else ""

    # ── 构造内联录入表单 HTML ──
    input_form_html = f"""
    <div class="card" id="inputCard" style="display:none">
      <h2>📝 录入经营数据</h2>
      {existing_tip}
      <form method="post">
        <label>日期</label>
        <input type="date" name="biz_date" value="{today_str}" max="{today_str}" required>
        <label>营业额（元）</label>
        <input type="number" step="0.01" min="0" name="revenue" placeholder="请输入今日营业额" required>
        <label>客流量（人次，选填）</label>
        <input type="number" min="0" name="footfall" placeholder="今日到店客流人次">
        <label>成交量（单，选填）</label>
        <input type="number" min="0" name="deals" placeholder="今日成交订单数">
        <label>备注（选填）</label>
        <textarea name="remark" placeholder="促销活动、特殊情况等"></textarea>
        <div style="display:flex;gap:8px;margin-top:8px">
          <button class="btn btn-primary" type="submit">💾 保存</button>
          <button class="btn" type="button" onclick="document.getElementById('inputCard').style.display='none';document.getElementById('addBizBtn').style.display='inline-block'" style="background:#ddd;color:#333">取消</button>
        </div>
      </form>
    </div>"""

    if not records:
        html = f"""
        {filter_html}
        <div style="text-align:right;margin-bottom:10px">
          <button class="btn btn-primary" id="addBizBtn" style="font-size:14px" onclick="document.getElementById('inputCard').style.display='block';this.style.display='none'">➕ 录入数据</button>
        </div>
        {input_form_html}
        <div class="card"><h2>📊 经营数据历史</h2><p style="color:#888;margin:10px 0">暂无数据{'（可调整筛选范围）' if (start_date or end_date) else ''}</p></div>"""
        return render_page(html, active_page="history")

    # 统计摘要
    revenues = [r.get("营业额", 0) for r in records if r.get("营业额", 0)]
    deals_l  = [int(r.get("成交量", 0)) for r in records if r.get("成交量", "") != ""]
    total_rev = sum(revenues)
    total_deals = sum(deals_l)
    avg_rev   = round(total_rev / len(revenues), 2) if revenues else 0
    max_rev   = max(revenues) if revenues else 0
    total_footfall = sum(int(r.get("客流量", 0)) for r in records if r.get("客流量", "") != "")
    conv_rate = round(total_deals / total_footfall * 100, 1) if deals_l and total_footfall else 0

    rows = "".join(
        f"<tr><td>{r['日期']}</td><td>¥{r.get('营业额',''):,.2f}</td>"
        f"<td>{r.get('客流量','—')}</td><td>{r.get('成交量','—')}</td>"
        f"<td>{r.get('业态','—')}</td><td>{r.get('录入时间','')[:10]}</td>"
        f"<td>{r.get('备注','')}</td></tr>"
        for r in records
    )

    # 筛选提示
    range_note = ""
    if start_date or end_date:
        range_note = f'（{start_date or "最早"} ~ {end_date or "最新"}）'

    html = f"""
    {filter_html}
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
      <span style="font-size:14px;color:#888">共 {len(records)} 条记录{range_note}（共 {len(all_records)} 条）</span>
      <button class="btn btn-primary" id="addBizBtn" style="font-size:14px" onclick="document.getElementById('inputCard').style.display='block';this.style.display='none'">➕ 录入数据</button>
    </div>
    {input_form_html}
    <div class="stat-row">
      <div class="stat-box"><div class="label">累计天数</div>
        <div class="num" style="color:#2980b9">{len(revenues)}</div></div>
      <div class="stat-box"><div class="label">累计营业额</div>
        <div class="num" style="color:#27ae60">¥{total_rev:,.2f}</div></div>
      <div class="stat-box"><div class="label">日均营业额</div>
        <div class="num" style="color:#8e44ad">¥{avg_rev:,.2f}</div></div>
      <div class="stat-box"><div class="label">单日最高</div>
        <div class="num" style="color:#e67e22">¥{max_rev:,.2f}</div></div>
      <div class="stat-box"><div class="label">成单转化率</div>
        <div class="num" style="color:#2c3e50">{conv_rate}%</div></div>
    </div>
    <div class="card">
      <h2>📊 经营数据{range_note}</h2>
      <table>
        <tr><th>日期</th><th>营业额</th><th>客流量</th><th>成交量</th><th>业态</th><th>录入时间</th><th>备注</th></tr>
        {rows}
      </table>
    </div>"""
    return render_page(html, active_page="history")


# ─────────────────────────── 启动 ───────────────────────────
if __name__ == "__main__":
    import socket
    # 获取本机局域网 IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    print("=" * 55)
    print("  LCP商管 · 商户门户已启动")
    print(f"  访问地址：http://localhost:5050")
    print("  商户使用合同号 + 商户名称登录")
    print("=" * 55)
    app.run(host="127.0.0.1", port=5050, debug=False)
