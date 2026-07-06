"""
db.py —— 小牛b商管系统 MySQL 数据访问层（Web版）
提供与原型一致的 MySQL CRUD 接口
"""
import pymysql
import json
from config import DB_CONFIG

# ===================== 连接管理 =====================
def _get_conn():
    return pymysql.connect(**DB_CONFIG)

def _execute(sql, params=None, fetch=False):
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
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.executemany(sql, params_list)
        return None
    finally:
        conn.close()

def _execute_insert(sql, params=None):
    """执行插入并返回自增ID"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.lastrowid
    finally:
        conn.close()

# ===================== 用户认证 =====================
def get_user_by_name(username):
    """根据用户名查找用户，返回 dict 或 None"""
    rows = _execute(
        "SELECT id, 用户名, 密码, 角色, 所属项目 FROM users WHERE BINARY 用户名 = %s",
        (username,), fetch=True
    )
    if not rows:
        return None
    r = rows[0]
    return {
        "id": r[0],
        "用户名": r[1] or "",
        "密码": r[2] or "",
        "角色": r[3] or "",
        "所属项目": r[4] or "",
    }

def get_all_users():
    """获取所有用户列表"""
    rows = _execute(
        "SELECT id, 用户名, 角色, 所属项目 FROM users ORDER BY id",
        fetch=True
    )
    if not rows:
        return []
    return [{"id": r[0], "用户名": r[1] or "", "角色": r[2] or "",
             "所属项目": r[3] or ""} for r in rows]

def save_user(data):
    """新增或更新用户（按用户名 upsert）"""
    import hashlib
    username = data.get("用户名", "")
    password = data.get("密码", "")
    role = data.get("角色", "")
    project = data.get("所属项目", "")

    if password and not password.startswith("$"):
        if len(password) != 32:
            password = hashlib.md5(password.encode()).hexdigest()

    existing = get_user_by_name(username)
    if existing:
        sql = "UPDATE users SET 角色=%s, 所属项目=%s WHERE 用户名=%s"
        params = (role, project, username)
        if password:
            sql = "UPDATE users SET 密码=%s, 角色=%s, 所属项目=%s WHERE 用户名=%s"
            params = (password, role, project, username)
        _execute(sql, params)
    else:
        _execute_insert(
            "INSERT INTO users (用户名, 密码, 角色, 所属项目) VALUES (%s, %s, %s, %s)",
            (username, password, role, project)
        )
    return True

def delete_user(username):
    """删除用户"""
    _execute("DELETE FROM users WHERE 用户名 = %s", (username,))
    return True

def verify_user(username, password):
    """验证用户名密码，成功返回用户信息，失败返回 None"""
    import hashlib
    user = get_user_by_name(username)
    if not user:
        return None
    hashed = hashlib.md5(password.encode()).hexdigest()
    if user["密码"] == hashed:
        return user
    return None

# ===================== 商铺 =====================
SHOP_COLS = ["铺位号", "所属项目", "位置", "铺位状态", "空间类型", "上下水", "电力功率上限kW", "装修情况", "租金报价元㎡天", "改造条件", "户型图路径", "现状照片路径", "建筑面积㎡", "使用面积㎡", "计租面积㎡", "基准租金元㎡天", "备注"]

def load_shops(project_filter=None):
    """加载商铺列表，可选按项目过滤"""
    if project_filter:
        rows = _execute(
            "SELECT 铺位号, 所属项目, 位置, 铺位状态, 空间类型, 上下水, 电力功率上限kW, 装修情况, 租金报价元㎡天, 改造条件, 户型图路径, 现状照片路径, 建筑面积㎡, 使用面积㎡, 计租面积㎡, 基准租金元㎡天, 备注 FROM shops WHERE 所属项目 = %s",
            (project_filter,), fetch=True
        )
    else:
        rows = _execute(
            "SELECT 铺位号, 所属项目, 位置, 铺位状态, 空间类型, 上下水, 电力功率上限kW, 装修情况, 租金报价元㎡天, 改造条件, 户型图路径, 现状照片路径, 建筑面积㎡, 使用面积㎡, 计租面积㎡, 基准租金元㎡天, 备注 FROM shops",
            fetch=True
        )
    if not rows:
        return []
    result = []
    for r in rows:
        shop = {
            "铺位号": r[0] or "",
            "所属项目": r[1] or "",
            "位置": r[2] or "",
            "铺位状态": r[3] or "",
            "空间类型": r[4] or "",
            "上下水": r[5] or "",
            "电力功率上限(kW)": str(float(r[6])) if r[6] is not None else "",
            "装修情况": r[7] or "",
            "租金报价(元/㎡/天)": str(float(r[8])) if r[8] is not None else "",
            "改造条件": r[9] or "",
            "户型图路径": r[10] or "",
            "现状照片路径": r[11] or "",
            "建筑面积(㎡)": str(float(r[12])) if r[12] is not None else "",
            "使用面积(㎡)": str(float(r[13])) if r[13] is not None else "",
            "计租面积(㎡)": str(float(r[14])) if r[14] is not None else "",
            "基准租金(元/㎡/天)": str(float(r[15])) if r[15] is not None else "",
            "备注": r[16] or "",
        }
        result.append(shop)
    return result

def save_shops(data):
    """增量合并商铺数据（按铺位号 upsert）"""
    if not data:
        return True
    params_list = []
    for s in data:
        params_list.append((
            s.get("铺位号", ""),
            s.get("所属项目", ""),
            s.get("位置", ""),
            s.get("铺位状态", ""),
            s.get("空间类型", ""),
            s.get("上下水", ""),
            float(s.get("电力功率上限(kW)", 0) or 0) if s.get("电力功率上限(kW)") else None,
            s.get("装修情况", ""),
            float(s.get("租金报价(元/㎡/天)", 0) or 0) if s.get("租金报价(元/㎡/天)") else None,
            s.get("改造条件", ""),
            s.get("户型图路径", ""),
            s.get("现状照片路径", ""),
            float(s.get("建筑面积(㎡)", 0) or 0) if s.get("建筑面积(㎡)") else None,
            float(s.get("使用面积(㎡)", 0) or 0) if s.get("使用面积(㎡)") else None,
            float(s.get("计租面积(㎡)", 0) or 0) if s.get("计租面积(㎡)") else None,
            float(s.get("基准租金(元/㎡/天)", 0) or 0),
            s.get("备注", ""),
        ))
    _execute_many(
        "INSERT INTO shops (铺位号, 所属项目, 位置, 铺位状态, 空间类型, 上下水, 电力功率上限kW, 装修情况, 租金报价元㎡天, 改造条件, 户型图路径, 现状照片路径, 建筑面积㎡, 使用面积㎡, 计租面积㎡, 基准租金元㎡天, 备注) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "所属项目=VALUES(所属项目), 位置=VALUES(位置), 铺位状态=VALUES(铺位状态), "
        "空间类型=VALUES(空间类型), 上下水=VALUES(上下水), 电力功率上限kW=VALUES(电力功率上限kW), "
        "装修情况=VALUES(装修情况), 租金报价元㎡天=VALUES(租金报价元㎡天), 改造条件=VALUES(改造条件), "
        "户型图路径=VALUES(户型图路径), 现状照片路径=VALUES(现状照片路径), "
        "建筑面积㎡=VALUES(建筑面积㎡), 使用面积㎡=VALUES(使用面积㎡), "
        "计租面积㎡=VALUES(计租面积㎡), "
        "基准租金元㎡天=VALUES(基准租金元㎡天), 备注=VALUES(备注)",
        params_list
    )
    return True

def delete_shop(shop_no):
    """删除商铺及其关联数据（事务级联删除）"""
    conn = pymysql.connect(**{**DB_CONFIG, "autocommit": False})
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE pr FROM payment_records pr "
                "INNER JOIN contracts c ON pr.合同号 = c.合同号 "
                "WHERE c.关联铺位号 = %s", (shop_no,)
            )
            cur.execute(
                "DELETE bd FROM business_data bd "
                "INNER JOIN contracts c ON bd.合同号 = c.合同号 "
                "WHERE c.关联铺位号 = %s", (shop_no,)
            )
            cur.execute("DELETE FROM contracts WHERE 关联铺位号 = %s", (shop_no,))
            cur.execute("DELETE FROM shops WHERE 铺位号 = %s", (shop_no,))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def get_contracts_by_shop(shop_no):
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

# ===================== 合同 =====================
CONTRACT_COLS = [
    "合同号", "商户名称", "经营业态", "所属项目", "关联铺位号",
    "保底租金元㎡天", "提成租金扣点", "签约日期", "租赁开始日期", "租赁结束日期",
    "终止日期", "免租期天", "剩余租期天", "押金", "押金支付状态",
    "意向金抵扣押金", "已付补缴押金",
    "支付周期", "合同状态", "联系电话", "联系人", "备注", "签约主体", "租金模式",
    "物业服务费单价元㎡天", "免租计划",
    "保底租金计划", "提成扣点计划", "物业费计划",
    "终止原因", "前序合同号"
]

def load_contracts(project_filter=None):
    """加载合同列表，可选按项目过滤"""
    base_sql = "SELECT " + ", ".join(CONTRACT_COLS) + " FROM contracts"
    if project_filter:
        sql = base_sql + " WHERE 所属项目 = %s"
        rows = _execute(sql, (project_filter,), fetch=True)
    else:
        rows = _execute(base_sql, fetch=True)
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
            elif col in ("免租计划", "保底租金计划", "提成扣点计划", "物业费计划"):
                if val and isinstance(val, str):
                    try:
                        c[col] = json.loads(val)
                    except:
                        c[col] = []
                elif isinstance(val, list):
                    c[col] = val
                else:
                    c[col] = []
            elif col in ("签约日期", "租赁开始日期", "租赁结束日期", "终止日期") and val is not None:
                c[col] = val.strftime("%Y-%m-%d") if hasattr(val, 'strftime') else str(val)
            elif val is None:
                c[col] = ""
            else:
                c[col] = str(val) if not isinstance(val, str) else val
        result.append(c)
    return result

def save_contracts(data):
    """增量合并合同数据（按合同号 upsert）"""
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
            float(c.get("意向金抵扣押金", 0) or 0),
            float(c.get("已付补缴押金", 0) or 0),
            c.get("支付周期", ""),
            c.get("合同状态", ""),
            c.get("联系电话", ""),
            c.get("联系人", ""),
            c.get("备注", ""),
            c.get("签约主体", ""),
            c.get("租金模式", ""),
            c.get("物业服务费单价（元/㎡/天）", ""),
            json.dumps(c.get("免租计划", []) if c.get("免租计划") else [], ensure_ascii=False),
            json.dumps(c.get("保底租金计划", []) if c.get("保底租金计划") else [], ensure_ascii=False),
            json.dumps(c.get("提成扣点计划", []) if c.get("提成扣点计划") else [], ensure_ascii=False),
            json.dumps(c.get("物业费计划", []) if c.get("物业费计划") else [], ensure_ascii=False),
            c.get("终止原因", ""),
            c.get("前序合同号", ""),
        ))
    _execute_many(
        "INSERT INTO contracts (" + ", ".join(CONTRACT_COLS) + ") "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "商户名称=VALUES(商户名称), 经营业态=VALUES(经营业态), 所属项目=VALUES(所属项目), "
        "关联铺位号=VALUES(关联铺位号), 保底租金元㎡天=VALUES(保底租金元㎡天), "
        "提成租金扣点=VALUES(提成租金扣点), 签约日期=VALUES(签约日期), "
        "租赁开始日期=VALUES(租赁开始日期), 租赁结束日期=VALUES(租赁结束日期), "
        "终止日期=VALUES(终止日期), 免租期天=VALUES(免租期天), 剩余租期天=VALUES(剩余租期天), "
        "押金=VALUES(押金), 押金支付状态=VALUES(押金支付状态), "
        "意向金抵扣押金=VALUES(意向金抵扣押金), 已付补缴押金=VALUES(已付补缴押金), "
        "支付周期=VALUES(支付周期), 合同状态=VALUES(合同状态), 联系电话=VALUES(联系电话), "
        "联系人=VALUES(联系人), 备注=VALUES(备注), 签约主体=VALUES(签约主体), 租金模式=VALUES(租金模式), "
        "物业服务费单价元㎡天=VALUES(物业服务费单价元㎡天), 免租计划=VALUES(免租计划), "
        "保底租金计划=VALUES(保底租金计划), 提成扣点计划=VALUES(提成扣点计划), 物业费计划=VALUES(物业费计划), "
        "终止原因=VALUES(终止原因), 前序合同号=VALUES(前序合同号)",
        params_list
    )
    return True

def delete_contract(contract_no):
    _execute("DELETE FROM contracts WHERE 合同号 = %s", (contract_no,))
    return True

def get_shop_area(shop_no):
    rows = _execute("SELECT 计租面积㎡ FROM shops WHERE 铺位号 = %s", (shop_no,), fetch=True)
    if rows and rows[0][0] is not None:
        return float(rows[0][0])
    rows2 = _execute("SELECT 建筑面积㎡ FROM shops WHERE 铺位号 = %s", (shop_no,), fetch=True)
    if rows2 and rows2[0][0] is not None:
        return float(rows2[0][0])
    return 0.0

# ===================== 缴费记录 =====================
def load_payments(project_filter=None):
    """加载缴费记录，可选按项目过滤"""
    if project_filter:
        rows = _execute(
            "SELECT 合同号, 支付时间, 已缴金额元, 所属项目, 已缴物业费元 FROM payment_records WHERE 所属项目 = %s",
            (project_filter,), fetch=True
        )
    else:
        rows = _execute(
            "SELECT 合同号, 支付时间, 已缴金额元, 所属项目, 已缴物业费元 FROM payment_records",
            fetch=True
        )
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

def delete_payment(contract_no, pay_time):
    _execute("DELETE FROM payment_records WHERE 合同号 = %s AND 支付时间 = %s", (contract_no, pay_time))
    return True

# ===================== 经营数据 =====================
def load_business_data(project_filter=None, contract_filter=None):
    """加载经营数据，可选按项目/合同过滤"""
    conditions = []
    params = []
    if project_filter:
        conditions.append("所属项目 = %s")
        params.append(project_filter)
    if contract_filter:
        conditions.append("合同号 = %s")
        params.append(contract_filter)

    sql = "SELECT 合同号, 商户名称, 日期, 营业额, 客流量, 成交量, 业态, 录入时间, 备注, 所属项目 FROM business_data"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY 日期 DESC"

    rows = _execute(sql, params if params else None, fetch=True)
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
    _execute("DELETE FROM business_data WHERE 合同号 = %s AND 日期 = %s", (contract_no, date))
    return True

# ===================== 商机 =====================
def load_opportunities(project_filter=None):
    sql = (
        "SELECT 商机编号, 商户名称, 联系人, 联系电话, 意向主体, 意向项目, 意向业态, "
        "意向租赁期限（年）, 意向铺位, 建筑面积㎡, "
        "商机来源, 当前阶段, 首次接洽日期, 意向租金单价元㎡天, 物业服务费单价元㎡月, 支付周期, "
        "最近跟进日期, 意向金金额元, 意向金支付日期, "
        "意向金去向, 跟进结果, 负责人, 备注, 跟进记录 FROM opportunities"
    )
    if project_filter:
        sql += " WHERE 意向项目 = %s"
        rows = _execute(sql, (project_filter,), fetch=True)
    else:
        rows = _execute(sql, fetch=True)
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
    _execute("DELETE FROM opportunities WHERE 商机编号 = %s", (opp_no,))
    return True

# ===================== 操作日志 =====================
def log_operation(username, role, op_type, module, description="", record_id=""):
    """写入操作日志"""
    try:
        import socket
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
        except:
            local_ip = ""
        _execute(
            "INSERT INTO operation_log (操作人, 角色, 操作类型, 操作模块, 操作描述, 记录ID, IP地址) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (username, role, op_type, module, description, str(record_id), local_ip)
        )
    except Exception as e:
        print(f"[log_operation] 写入失败: {e}")

def load_operation_logs(project_filter=None):
    """加载操作日志"""
    sql = "SELECT 操作人, 角色, 操作类型, 操作模块, 操作描述, 记录ID, IP地址, 操作时间 FROM operation_log ORDER BY 操作时间 DESC LIMIT 500"
    rows = _execute(sql, fetch=True)
    if not rows:
        return []
    result = []
    for r in rows:
        result.append({
            "操作人": r[0] or "",
            "角色": r[1] or "",
            "操作类型": r[2] or "",
            "操作模块": r[3] or "",
            "操作描述": r[4] or "",
            "记录ID": r[5] or "",
            "IP地址": r[6] or "",
            "操作时间": r[7].strftime("%Y-%m-%d %H:%M:%S") if hasattr(r[7], 'strftime') else str(r[7] or ""),
        })
    return result

# ===================== 商户账户 =====================
def create_merchant_account(username, contract_no, merchant_name, hashed_password):
    """创建商户账户，返回 True / 'username_exists' / 'contract_exists' / 抛异常"""
    # 先检查唯一性
    rows = _execute("SELECT 1 FROM merchant_accounts WHERE username = %s", (username,), fetch=True)
    if rows:
        return "username_exists"
    rows = _execute("SELECT 1 FROM merchant_accounts WHERE contract_no = %s", (contract_no,), fetch=True)
    if rows:
        return "contract_exists"
    _execute(
        "INSERT INTO merchant_accounts (username, contract_no, merchant_name, password) VALUES (%s, %s, %s, %s)",
        (username, contract_no, merchant_name, hashed_password)
    )
    return True


def get_merchant_account_by_username(username):
    """根据用户名获取商户账户，返回 dict 或 None"""
    rows = _execute(
        "SELECT username, contract_no, merchant_name, password FROM merchant_accounts WHERE BINARY username = %s",
        (username,), fetch=True
    )
    if not rows:
        return None
    return {
        "username": rows[0][0],
        "contract_no": rows[0][1],
        "merchant_name": rows[0][2],
        "password": rows[0][3],
    }


def check_merchant_registered(contract_no):
    """检查商户是否已注册"""
    rows = _execute(
        "SELECT 1 FROM merchant_accounts WHERE contract_no = %s",
        (contract_no,), fetch=True
    )
    return len(rows) > 0 if rows else False


def update_merchant_password(contract_no, new_hashed_password):
    """根据合同号重置密码，返回受影响行数"""
    _execute(
        "UPDATE merchant_accounts SET password = %s WHERE contract_no = %s",
        (new_hashed_password, contract_no)
    )
    return True

# ===================== 仪表板统计 =====================
def get_dashboard_stats(project_filter=None, year=None):
    """获取仪表板统计数据（完整版，与桌面原型对齐）"""
    from datetime import date, datetime
    today = date.today()

    where_clause = ""
    params_list = []
    if project_filter:
        where_clause = " WHERE 所属项目 = %s"
        params_list = [project_filter]

    # ── 商铺统计 ──
    base_params = tuple(params_list) if params_list else None
    sql = "SELECT COUNT(*) FROM shops" + where_clause
    total_shops = _execute(sql, base_params, fetch=True)
    total_shops = total_shops[0][0] if total_shops else 0

    sql = "SELECT COUNT(*) FROM shops" + (where_clause + (" AND" if where_clause else " WHERE") + " 铺位状态 = '已出租'" if project_filter or True else "")
    if project_filter:
        sql2 = "SELECT COUNT(*) FROM shops WHERE 所属项目 = %s AND 铺位状态 = '已出租'"
        rows = _execute(sql2, (project_filter,), fetch=True)
    else:
        rows = _execute("SELECT COUNT(*) FROM shops WHERE 铺位状态 = '已出租'", fetch=True)
    rented = rows[0][0] if rows else 0

    if project_filter:
        rows = _execute("SELECT COUNT(*) FROM shops WHERE 所属项目 = %s AND 铺位状态 = '空置'", (project_filter,), fetch=True)
    else:
        rows = _execute("SELECT COUNT(*) FROM shops WHERE 铺位状态 = '空置'", fetch=True)
    vacant = rows[0][0] if rows else 0

    if project_filter:
        rows = _execute("SELECT COUNT(*) FROM shops WHERE 所属项目 = %s AND 铺位状态 = '维修'", (project_filter,), fetch=True)
    else:
        rows = _execute("SELECT COUNT(*) FROM shops WHERE 铺位状态 = '维修'", fetch=True)
    repair = rows[0][0] if rows else 0

    # ── 合同统计 ──
    contracts = load_contracts(project_filter)
    total_contracts = len(contracts)
    active_ct = sum(1 for c in contracts if c.get("合同状态", "") == "执行中")
    expired_ct = sum(1 for c in contracts if c.get("合同状态", "") == "已到期")
    terminated_ct = sum(1 for c in contracts if c.get("合同状态", "") == "已终止")

    # 租金统计（遍历合同计算）
    shops_cache = load_shops(project_filter)
    payments_cache = load_payments(project_filter)

    sum_total_rent = 0.0
    sum_total_paid = 0.0
    sum_overdue = 0.0
    sum_due_rent = 0.0
    overdue_cnt = 0
    import utils as _utils
    for c in contracts:
        try:
            plan = _utils.generate_rent_plan(c, _shops_cache=shops_cache, _payments_cache=payments_cache)
            tr = sum(p["应缴金额(元)"] for p in plan)
            pd = sum(p["已缴金额(元)"] for p in plan)
            sum_total_rent += tr
            sum_total_paid += pd
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
        except:
            pass

    # ── 商机统计 ──
    opps = load_opportunities(project_filter)
    total_opps = len(opps)
    following_opps = sum(1 for o in opps if o.get("跟进结果", "") != "已流失"
                         and o.get("当前阶段", "") not in ("已支付意向金", "已转合同"))
    paid_opps = sum(1 for o in opps if o.get("当前阶段", "") == "已支付意向金")
    lost_opps = sum(1 for o in opps if o.get("跟进结果", "") == "已流失")

    # ── 本月实收 ──
    current_month_start = today.strftime("%Y-%m-01")
    if project_filter:
        rows = _execute(
            "SELECT COALESCE(SUM(已缴金额元), 0) FROM payment_records WHERE 所属项目 = %s AND 支付时间 >= %s",
            (project_filter, current_month_start), fetch=True
        )
    else:
        rows = _execute(
            "SELECT COALESCE(SUM(已缴金额元), 0) FROM payment_records WHERE 支付时间 >= %s",
            (current_month_start,), fetch=True
        )
    this_month_paid = float(rows[0][0]) if rows else 0.0

    collection_rate = round(sum_total_paid / sum_due_rent * 100, 1) if sum_due_rent else 0

    # ── 月度租金数据（本年1~12月） ──
    monthly_rent = {}
    for m in range(1, 13):
        monthly_rent[str(m)] = {"应收": 0.0, "已收": 0.0}
    cur_year = year if year else today.year
    for c in contracts:
        try:
            plan = _utils.generate_rent_plan(c, _shops_cache=shops_cache, _payments_cache=payments_cache)
            for p in plan:
                d = datetime.strptime(p["支付时间"], "%Y-%m-%d").date()
                if d.year == cur_year:
                    mk = str(d.month)
                    monthly_rent[mk]["应收"] += p["应缴金额(元)"]
                    monthly_rent[mk]["已收"] += p["已缴金额(元)"]
        except:
            pass
    # 计算收缴率
    for mk in monthly_rent:
        due = monthly_rent[mk]["应收"]
        paid = monthly_rent[mk]["已收"]
        monthly_rent[mk]["收缴率"] = round(paid / due * 100, 1) if due > 0 else 0
        monthly_rent[mk]["应收"] = round(due, 2)
        monthly_rent[mk]["已收"] = round(paid, 2)

    # ── 营业商铺业态分布（饼图） ──
    biz_dist = {}
    for c in contracts:
        status = c.get("合同状态", "")
        if status in ("执行中",):
            fmt = c.get("经营业态", "未知") or "未知"
            biz_dist[fmt] = biz_dist.get(fmt, 0) + 1

    return {
        # 商铺
        "total_shops": total_shops, "rented": rented,
        "vacant": vacant, "repair": repair,
        # 合同
        "total_contracts": total_contracts, "active_ct": active_ct,
        "expired_ct": expired_ct, "terminated_ct": terminated_ct,
        "overdue_ct": overdue_cnt,
        # 商机
        "total_opps": total_opps, "following_opps": following_opps,
        "paid_opps": paid_opps, "lost_opps": lost_opps,
        # 租金
        "sum_rent": round(sum_total_rent, 2),
        "sum_paid": round(sum_total_paid, 2),
        "sum_overdue": round(sum_overdue, 2),
        "sum_due": round(sum_due_rent, 2),
        "collection_rate": collection_rate,
        "this_month_paid": round(this_month_paid, 2),
        # 月度租金
        "monthly_rent": monthly_rent,
        # 业态分布
        "biz_dist": biz_dist,
    }


def get_business_dashboard_api(project_filter=None, date_str=None, biz_project=None):
    """返回经营数据看板所需的完整数据集（JSON）"""
    all_biz = load_business_data(project_filter)
    contracts = load_contracts(project_filter)
    shops = load_shops(project_filter)

    # 建立映射
    contract_map = {}
    for c in contracts:
        shop_no = str(c.get("关联铺位号", ""))
        shop = None
        for s in shops:
            if str(s.get("铺位号", "")) == shop_no:
                shop = s
                break
        contract_map[str(c.get("合同号", ""))] = (c, shop)

    # 补全字段
    enriched = []
    for r in all_biz:
        cno = str(r.get("合同号", ""))
        c_pair = contract_map.get(cno, (None, None))
        ct, sh = c_pair
        enriched.append({
            "合同号": cno,
            "商户名称": r.get("商户名称", ""),
            "日期": r.get("日期", ""),
            "营业额": float(r.get("营业额", 0) or 0),
            "客流量": int(r.get("客流量", 0) or 0),
            "成交量": int(r.get("成交量", 0) or 0),
            "业态": r.get("业态", "") or (ct.get("经营业态", "") if ct else ""),
            "项目": sh.get("所属项目", "") if sh else "",
            "面积": float(sh.get("建筑面积(㎡)", 0) or 0) if sh else 0.0,
            "录入时间": r.get("录入时间", ""),
        })

    # 项目筛选
    if biz_project and biz_project != "全部":
        enriched = [r for r in enriched if r.get("项目", "") == biz_project]

    # 注意：不在后端按 date_str 过滤 records，因为周趋势图需要当天往前 6 天的全量数据。
    # 前端 renderWeekChart() / renderFormatBar() / renderTop10() 各自自行按日期过滤。

    return {
        "records": enriched,
        "all_projects": sorted(set(s.get("所属项目", "") for s in shops if s.get("所属项目"))),
        "all_dates": sorted(set(r.get("日期", "") for r in all_biz if r.get("日期")), reverse=True),
    }


# ===================== 自检 =====================
if __name__ == "__main__":
    print("=" * 50)
    print("db.py 自检")
    try:
        conn = _get_conn()
        print(f"[OK] 连接成功 (MySQL {conn.get_server_info()})")
        conn.close()
    except Exception as e:
        print(f"[FAIL] 连接失败: {e}")
        exit(1)
    for tbl in ["shops", "contracts", "payment_records", "business_data", "opportunities"]:
        rows = _execute(f"SELECT COUNT(*) FROM {tbl}", fetch=True)
        print(f"   {tbl}: {rows[0][0]} 条")
    print("=" * 50)
