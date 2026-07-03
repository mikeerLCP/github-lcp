"""
db.py —— 小牛b商管系统 MySQL 数据访问层
提供与 utils.py JSON 版本相同接口的 MySQL 实现，可直接替换
"""
import pymysql
import json

# ===================== 连接配置（部署时修改这里） =====================
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "adminhang",          # ← 填你的 MySQL root 密码
    "database": "xiaoniu_shangguan",
    "charset": "utf8mb4",
    "autocommit": True,
}

# ===================== 连接管理 =====================
def _get_conn():
    """获取数据库连接"""
    return pymysql.connect(**DB_CONFIG)

def _execute(sql, params=None, fetch=False):
    """执行 SQL，返回结果"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if fetch:
                return cur.fetchall()
        return None
    finally:
        conn.close()

def _execute_many(sql, params_list):
    """批量执行"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.executemany(sql, params_list)
        return None
    finally:
        conn.close()

# ===================== 商铺 =====================
SHOP_COLS = ["铺位号", "所属项目", "位置", "铺位状态", "适用业态", "建筑面积㎡", "使用面积㎡", "基准租金元㎡天", "备注"]

def load_shops():
    rows = _execute(
        "SELECT 铺位号, 所属项目, 位置, 铺位状态, 适用业态, 建筑面积㎡, 使用面积㎡, 基准租金元㎡天, 备注 FROM shops",
        fetch=True
    )
    if not rows:
        return []
    result = []
    for r in rows:
        # 直接按位置构建字典，避免裸字段名残留
        shop = {
            "铺位号":          r[0] or "",
            "所属项目":        r[1] or "",
            "位置":            r[2] or "",
            "铺位状态":        r[3] or "",
            "适用业态":        r[4] or "",
            "建筑面积(㎡)":    str(float(r[5])) if r[5] is not None else "",
            "使用面积(㎡)":    str(float(r[6])) if r[6] is not None else "",
            "基准租金(元/㎡/天)": str(float(r[7])) if r[7] is not None else "",
            "备注":            r[8] or "",
        }
        result.append(shop)
    return result

def save_shops(data):
    """增量合并商铺数据（按铺位号 upsert，不会误删其他铺位号）"""
    if not data:
        return True
    params_list = []
    for s in data:
        params_list.append((
            s.get("铺位号", ""),
            s.get("所属项目", ""),
            s.get("位置", ""),
            s.get("铺位状态", ""),
            s.get("适用业态", ""),
            float(s.get("建筑面积(㎡)", 0) or 0) if s.get("建筑面积(㎡)") else None,
            float(s.get("使用面积(㎡)", 0) or 0) if s.get("使用面积(㎡)") else None,
            float(s.get("基准租金(元/㎡/天)", 0) or 0),
            s.get("备注", ""),
        ))
    _execute_many(
        "INSERT INTO shops (铺位号, 所属项目, 位置, 铺位状态, 适用业态, 建筑面积㎡, 使用面积㎡, 基准租金元㎡天, 备注) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "所属项目=VALUES(所属项目), 位置=VALUES(位置), 铺位状态=VALUES(铺位状态), "
        "适用业态=VALUES(适用业态), 建筑面积㎡=VALUES(建筑面积㎡), 使用面积㎡=VALUES(使用面积㎡), "
        "基准租金元㎡天=VALUES(基准租金元㎡天), 备注=VALUES(备注)",
        params_list
    )
    return True

def delete_shop(shop_no):
    """删除商铺及其关联数据（事务级联删除）
    级联顺序：缴费记录 → 经营数据 → 合同 → 商铺
    任意一步失败则全部回滚
    """
    conn = pymysql.connect(**{**DB_CONFIG, "autocommit": False})
    try:
        with conn.cursor() as cur:
            # 1. 删除关联缴费记录（通过合同号 JOIN）
            cur.execute(
                "DELETE pr FROM payment_records pr "
                "INNER JOIN contracts c ON pr.合同号 = c.合同号 "
                "WHERE c.关联铺位号 = %s", (shop_no,)
            )
            deleted_payments = cur.rowcount
            # 2. 删除关联经营数据（通过合同号 JOIN）
            cur.execute(
                "DELETE bd FROM business_data bd "
                "INNER JOIN contracts c ON bd.合同号 = c.合同号 "
                "WHERE c.关联铺位号 = %s", (shop_no,)
            )
            deleted_biz = cur.rowcount
            # 3. 删除关联合同
            cur.execute("DELETE FROM contracts WHERE 关联铺位号 = %s", (shop_no,))
            deleted_contracts = cur.rowcount
            # 4. 删除商铺本身
            cur.execute("DELETE FROM shops WHERE 铺位号 = %s", (shop_no,))
            deleted_shop = cur.rowcount
        conn.commit()
        print(f"[级联删除] 商铺={shop_no} | 合同×{deleted_contracts} | 经营×{deleted_biz} | 缴费×{deleted_payments}")
        return deleted_shop > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_contracts_by_shop(shop_no):
    """查询关联某个铺位的所有合同（用于删除前确认）"""
    rows = _execute(
        "SELECT 合同号, 商户名称, 合同状态 FROM contracts WHERE 关联铺位号 = %s",
        (shop_no,), fetch=True
    )
    if not rows:
        return []
    return [{"合同号": r[0], "商户名称": r[1], "合同状态": r[2]} for r in rows]

def check_shop_no_exists(shop_no):
    rows = _execute("SELECT 1 FROM shops WHERE 铺位号 = %s", (shop_no,), fetch=True)
    return len(rows) > 0 if rows else False

def get_shop_area(shop_no):
    rows = _execute("SELECT 计租面积㎡ FROM shops WHERE 铺位号 = %s", (shop_no,), fetch=True)
    if rows and rows[0][0] is not None:
        return float(rows[0][0])
    return 0.0

# ===================== 合同 =====================
CONTRACT_COLS = [
    "合同号", "商户名称", "经营业态", "所属项目", "关联铺位号",
    "保底租金元㎡天", "提成租金扣点", "签约日期", "租赁开始日期", "租赁结束日期",
    "终止日期", "免租期天", "剩余租期天", "押金", "押金支付状态",
    "支付周期", "合同状态", "联系电话", "联系人", "备注", "签约主体", "租金模式",
    "物业服务费单价元㎡天", "免租计划"
]

def load_contracts():
    sql = "SELECT " + ", ".join(CONTRACT_COLS) + " FROM contracts"
    rows = _execute(sql, fetch=True)
    if not rows:
        return []
    result = []
    for r in rows:
        c = {}
        for i, col in enumerate(CONTRACT_COLS):
            val = r[i]
            if col == "保底租金元㎡天":
                c["保底租金(元/㎡/天)"] = str(float(val)) if val is not None else ""
            elif col == "提成租金扣点":
                c["提成租金扣点(%)"] = str(float(val)) if val is not None else ""
            elif col == "免租期天":
                c["免租期(天)"] = str(int(val)) if val is not None else ""
            elif col == "剩余租期天":
                c["剩余租期(天)"] = str(int(val)) if val is not None else ""
            elif col == "物业服务费单价元㎡天":
                c["物业服务费单价（元/㎡/天）"] = str(val) if val else ""
            elif col == "免租计划":
                if val and isinstance(val, str):
                    try:
                        c[col] = json.loads(val)
                    except:
                        c[col] = []
                elif isinstance(val, list):
                    c[col] = val
                else:
                    c[col] = []
            elif col == "签约日期" and isinstance(val, str):
                c[col] = val
            elif col in ("签约日期", "租赁开始日期", "租赁结束日期", "终止日期") and val is not None:
                c[col] = val.strftime("%Y-%m-%d") if hasattr(val, 'strftime') else str(val)
            elif val is None:
                c[col] = ""
            else:
                c[col] = str(val) if not isinstance(val, str) else val
        result.append(c)
    return result

def save_contracts(data):
    """增量合并合同数据（按合同号 upsert，不会误删其他合同号）"""
    if not data:
        return True
    params_list = []
    for c in data:
        def to_date(v):
            if not v:
                return None
            return str(v)
        params_list.append((
            c.get("合同号", ""),
            c.get("商户名称", ""),
            c.get("经营业态", ""),
            c.get("所属项目", ""),
            c.get("关联铺位号", ""),
            float(c.get("保底租金(元/㎡/天)", 0) or 0),
            float(c.get("提成租金扣点(%)", 0) or 0),
            to_date(c.get("签约日期", "")),
            to_date(c.get("租赁开始日期", "")),
            to_date(c.get("租赁结束日期", "")),
            to_date(c.get("终止日期", "")),
            int(c.get("免租期(天)", 0) or 0),
            int(c.get("剩余租期(天)", 0) or 0),
            float(c.get("押金", 0) or 0),
            c.get("押金支付状态", ""),
            c.get("支付周期", ""),
            c.get("合同状态", ""),
            c.get("联系电话", ""),
            c.get("联系人", ""),
            c.get("备注", ""),
            c.get("签约主体", ""),
            c.get("租金模式", ""),
            c.get("物业服务费单价（元/㎡/天）", ""),
            json.dumps(c.get("免租计划", []) if c.get("免租计划") else [], ensure_ascii=False),
        ))
    _execute_many(
        "INSERT INTO contracts (" + ", ".join(CONTRACT_COLS) + ") "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "商户名称=VALUES(商户名称), 经营业态=VALUES(经营业态), 所属项目=VALUES(所属项目), "
        "关联铺位号=VALUES(关联铺位号), 保底租金元㎡天=VALUES(保底租金元㎡天), "
        "提成租金扣点=VALUES(提成租金扣点), 签约日期=VALUES(签约日期), "
        "租赁开始日期=VALUES(租赁开始日期), 租赁结束日期=VALUES(租赁结束日期), "
        "终止日期=VALUES(终止日期), 免租期天=VALUES(免租期天), 剩余租期天=VALUES(剩余租期天), "
        "押金=VALUES(押金), 押金支付状态=VALUES(押金支付状态), "
        "支付周期=VALUES(支付周期), 合同状态=VALUES(合同状态), 联系电话=VALUES(联系电话), "
        "联系人=VALUES(联系人), 备注=VALUES(备注), 签约主体=VALUES(签约主体), 租金模式=VALUES(租金模式), "
        "物业服务费单价元㎡天=VALUES(物业服务费单价元㎡天), 免租计划=VALUES(免租计划)",
        params_list
    )
    return True

def delete_contract(contract_no):
    """删除单个合同"""
    _execute("DELETE FROM contracts WHERE 合同号 = %s", (contract_no,))
    return True

# ===================== 缴费记录 =====================
def load_payments():
    rows = _execute("SELECT 合同号, 支付时间, 已缴金额元, 所属项目, 已缴物业费元 FROM payment_records", fetch=True)
    if not rows:
        return []
    result = []
    for r in rows:
        result.append({
            "合同号": r[0],
            "支付时间": r[1],
            "已缴金额(元)": float(r[2]) if r[2] is not None else 0.0,
            "所属项目": r[3] or "",
            "已缴物业费": float(r[4]) if r[4] is not None else 0.0,
        })
    return result

def save_payments(data):
    """增量合并缴费记录（按(合同号,支付时间) upsert）"""
    if not data:
        return True
    params_list = []
    for p in data:
        params_list.append((
            p.get("合同号", ""),
            p.get("支付时间", ""),
            float(p.get("已缴金额(元)", 0) or 0),
            p.get("所属项目", ""),
            float(p.get("已缴物业费", 0) or 0),
        ))
    _execute_many(
        "INSERT INTO payment_records (合同号, 支付时间, 已缴金额元, 所属项目, 已缴物业费元) "
        "VALUES (%s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "已缴金额元=VALUES(已缴金额元), 所属项目=VALUES(所属项目), 已缴物业费元=VALUES(已缴物业费元)",
        params_list
    )
    return True

def delete_payment(contract_no, pay_time):
    """删除单条缴费记录"""
    _execute("DELETE FROM payment_records WHERE 合同号 = %s AND 支付时间 = %s", (contract_no, pay_time))
    return True

def get_paid(contract_no, pay_time):
    rows = _execute(
        "SELECT 已缴金额元 FROM payment_records WHERE 合同号 = %s AND 支付时间 = %s",
        (contract_no, pay_time), fetch=True
    )
    if rows and rows[0][0] is not None:
        return float(rows[0][0])
    return 0.0

def get_property_fee_paid(contract_no, pay_time):
    rows = _execute(
        "SELECT 已缴物业费元 FROM payment_records WHERE 合同号 = %s AND 支付时间 = %s",
        (contract_no, pay_time), fetch=True
    )
    if rows and rows[0][0] is not None:
        return float(rows[0][0])
    return 0.0

def update_paid(contract_no, pay_time, val):
    rows = _execute(
        "SELECT id FROM payment_records WHERE 合同号 = %s AND 支付时间 = %s",
        (contract_no, pay_time), fetch=True
    )
    val = round(float(val), 2)
    if rows:
        _execute(
            "UPDATE payment_records SET 已缴金额元 = %s WHERE 合同号 = %s AND 支付时间 = %s",
            (val, contract_no, pay_time)
        )
    else:
        # 从 contracts 表查所属项目
        proj = _execute(
            "SELECT 所属项目 FROM contracts WHERE 合同号 = %s",
            (contract_no,), fetch=True
        )
        project = proj[0][0] if proj and proj[0][0] else ""
        _execute(
            "INSERT INTO payment_records (合同号, 支付时间, 已缴金额元, 所属项目) VALUES (%s, %s, %s, %s)",
            (contract_no, pay_time, val, project)
        )

def update_property_fee_paid(contract_no, pay_time, val):
    rows = _execute(
        "SELECT id FROM payment_records WHERE 合同号 = %s AND 支付时间 = %s",
        (contract_no, pay_time), fetch=True
    )
    val = round(float(val), 2)
    if rows:
        _execute(
            "UPDATE payment_records SET 已缴物业费元 = %s WHERE 合同号 = %s AND 支付时间 = %s",
            (val, contract_no, pay_time)
        )
    else:
        # 从 contracts 表查所属项目
        proj = _execute(
            "SELECT 所属项目 FROM contracts WHERE 合同号 = %s",
            (contract_no,), fetch=True
        )
        project = proj[0][0] if proj and proj[0][0] else ""
        _execute(
            "INSERT INTO payment_records (合同号, 支付时间, 已缴金额元, 所属项目) VALUES (%s, %s, 0, %s)",
            (contract_no, pay_time, project)
        )
        _execute(
            "UPDATE payment_records SET 已缴物业费元 = %s WHERE 合同号 = %s AND 支付时间 = %s",
            (val, contract_no, pay_time)
        )

# ===================== 经营数据 =====================
def load_business_data():
    rows = _execute(
        "SELECT 合同号, 商户名称, 日期, 营业额, 客流量, 成交量, 业态, 录入时间, 备注, 所属项目 FROM business_data ORDER BY 日期 DESC",
        fetch=True
    )
    if not rows:
        return []
    result = []
    for r in rows:
        result.append({
            "合同号": r[0],
            "商户名称": r[1] or "",
            "日期": r[2].strftime("%Y-%m-%d") if hasattr(r[2], 'strftime') else str(r[2]),
            "营业额": float(r[3]) if r[3] is not None else 0.0,
            "客流量": int(r[4]) if r[4] is not None else "",
            "成交量": int(r[5]) if r[5] is not None else "",
            "业态": r[6] or "",
            "录入时间": r[7] or "",
            "备注": r[8] or "",
            "所属项目": r[9] or "",
        })
    return result

def save_business_data(data):
    """增量合并经营数据（按(合同号,日期) upsert）"""
    if not data:
        return True
    params_list = []
    for b in data:
        params_list.append((
            b.get("合同号", ""),
            b.get("商户名称", ""),
            b.get("日期", ""),
            float(b.get("营业额", 0) or 0),
            int(b.get("客流量", 0) or 0) if b.get("客流量") != "" else None,
            int(b.get("成交量", 0) or 0) if b.get("成交量") != "" else None,
            b.get("业态", ""),
            b.get("录入时间", ""),
            b.get("备注", ""),
            b.get("所属项目", ""),
        ))
    _execute_many(
        "INSERT INTO business_data (合同号, 商户名称, 日期, 营业额, 客流量, 成交量, 业态, 录入时间, 备注, 所属项目) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "商户名称=VALUES(商户名称), 营业额=VALUES(营业额), 客流量=VALUES(客流量), "
        "成交量=VALUES(成交量), 业态=VALUES(业态), 录入时间=VALUES(录入时间), "
        "备注=VALUES(备注), 所属项目=VALUES(所属项目)",
        params_list
    )
    return True

def delete_business_data(contract_no, date):
    """删除单条经营数据"""
    _execute("DELETE FROM business_data WHERE 合同号 = %s AND 日期 = %s", (contract_no, date))
    return True

# ===================== 商机 =====================
def load_opportunities():
    rows = _execute(
        "SELECT 商机编号, 商户名称, 联系人, 联系电话, 意向主体, 意向项目, 意向业态, "
        "意向租赁期限（年）, 意向铺位, 建筑面积㎡, "
        "商机来源, 当前阶段, 首次接洽日期, 意向租金单价元㎡天, 物业服务费单价元㎡月, 支付周期, "
        "最近跟进日期, 意向金金额元, 意向金支付日期, "
        "意向金去向, 跟进结果, 负责人, 备注, 跟进记录 FROM opportunities",
        fetch=True
    )
    if not rows:
        return []
    result = []
    for r in rows:
        follow = r[23]
        if isinstance(follow, str):
            follow = json.loads(follow) if follow else []
        result.append({
            "商机编号": r[0],
            "商户名称": r[1] or "",
            "联系人": r[2] or "",
            "联系电话": r[3] or "",
            "意向主体": r[4] or "",
            "意向项目": r[5] or "",
            "意向业态": r[6] or "",
            "意向租赁期限（年）": r[7] or "",
            "意向铺位": r[8] or "",
            "建筑面积(㎡)": str(float(r[9])) if r[9] is not None else "",
            "商机来源": r[10] or "",
            "当前阶段": r[11] or "",
            "首次接洽日期": r[12].strftime("%Y-%m-%d") if hasattr(r[12], 'strftime') else str(r[12] or ""),
            "意向租金单价(元/㎡/天)": str(float(r[13])) if r[13] is not None else "",
            "物业服务费单价(元/㎡/月)": str(float(r[14])) if r[14] is not None else "",
            "支付周期": r[15] or "",
            "最近跟进日期": r[16].strftime("%Y-%m-%d") if hasattr(r[16], 'strftime') else str(r[16] or ""),
            "意向金金额(元)": str(float(r[17])) if r[17] is not None else "",
            "意向金支付日期": r[18].strftime("%Y-%m-%d") if hasattr(r[18], 'strftime') else str(r[18] or ""),
            "意向金去向": r[19] or "",
            "跟进结果": r[20] or "",
            "负责人": r[21] or "",
            "备注": r[22] or "",
            "跟进记录": follow,
        })
    return result

def save_opportunities(data):
    """增量合并商机数据（按商机编号 upsert）"""
    if not data:
        return True
    params_list = []
    for o in data:
        def to_date(v):
            if not v:
                return None
            return str(v)
        follow = o.get("跟进记录", [])
        if isinstance(follow, list):
            follow = json.dumps(follow, ensure_ascii=False)
        params_list.append((
            o.get("商机编号", ""),
            o.get("商户名称", ""),
            o.get("联系人", ""),
            o.get("联系电话", ""),
            o.get("意向主体", ""),
            o.get("意向项目", ""),
            o.get("意向业态", ""),
            o.get("意向租赁期限（年）", ""),
            o.get("意向铺位", ""),
            float(o.get("建筑面积(㎡)", 0) or 0) if o.get("建筑面积(㎡)") else None,
            o.get("商机来源", ""),
            o.get("当前阶段", ""),
            to_date(o.get("首次接洽日期", "")),
            float(o.get("意向租金单价(元/㎡/天)", 0) or 0) if o.get("意向租金单价(元/㎡/天)") else None,
            float(o.get("物业服务费单价(元/㎡/月)", 0) or 0) if o.get("物业服务费单价(元/㎡/月)") else None,
            o.get("支付周期", ""),
            to_date(o.get("最近跟进日期", "")),
            float(o.get("意向金金额(元)", 0) or 0),
            to_date(o.get("意向金支付日期", "")),
            o.get("意向金去向", ""),
            o.get("跟进结果", ""),
            o.get("负责人", ""),
            o.get("备注", ""),
            follow,
        ))
    _execute_many(
        "INSERT INTO opportunities (商机编号, 商户名称, 联系人, 联系电话, 意向主体, 意向项目, 意向业态, "
        "意向租赁期限（年）, 意向铺位, 建筑面积㎡, 商机来源, 当前阶段, 首次接洽日期, "
        "意向租金单价元㎡天, 物业服务费单价元㎡月, 支付周期, "
        "最近跟进日期, 意向金金额元, 意向金支付日期, "
        "意向金去向, 跟进结果, 负责人, 备注, 跟进记录) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "商户名称=VALUES(商户名称), 联系人=VALUES(联系人), 联系电话=VALUES(联系电话), 意向主体=VALUES(意向主体), "
        "意向项目=VALUES(意向项目), 意向业态=VALUES(意向业态), 意向租赁期限（年）=VALUES(意向租赁期限（年）), "
        "意向铺位=VALUES(意向铺位), "
        "建筑面积㎡=VALUES(建筑面积㎡), 商机来源=VALUES(商机来源), 当前阶段=VALUES(当前阶段), "
        "首次接洽日期=VALUES(首次接洽日期), "
        "意向租金单价元㎡天=VALUES(意向租金单价元㎡天), 物业服务费单价元㎡月=VALUES(物业服务费单价元㎡月), "
        "支付周期=VALUES(支付周期), 最近跟进日期=VALUES(最近跟进日期), "
        "意向金金额元=VALUES(意向金金额元), 意向金支付日期=VALUES(意向金支付日期), "
        "意向金去向=VALUES(意向金去向), 跟进结果=VALUES(跟进结果), 负责人=VALUES(负责人), "
        "备注=VALUES(备注), 跟进记录=VALUES(跟进记录)",
        params_list
    )
    return True

def delete_opportunity(opp_no):
    """删除单个商机"""
    _execute("DELETE FROM opportunities WHERE 商机编号 = %s", (opp_no,))
    return True


# ===================== 自检 =====================
if __name__ == "__main__":
    print("=" * 50)
    print("db.py 自检")

    try:
        conn = _get_conn()
        print(f"✅ 连接成功 (MySQL {conn.get_server_info()})")
        conn.close()
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        print("   请修改 DB_CONFIG 中的 password")
        exit(1)

    # 查看各表行数
    for tbl in ["shops", "contracts", "payment_records", "business_data", "opportunities"]:
        rows = _execute(f"SELECT COUNT(*) FROM {tbl}", fetch=True)
        print(f"   {tbl}: {rows[0][0]} 条")

    print("=" * 50)
