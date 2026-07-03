"""
auth.py —— 小牛b商管系统（Web版）认证模块
基于 Flask session 的登录/权限验证
"""
from functools import wraps
from flask import session, redirect, url_for, flash
import db as database


def login_user(username, password):
    """验证用户登录，成功返回用户信息，失败返回 None"""
    user = database.verify_user(username, password)
    if user:
        session["user"] = {
            "用户名": user["用户名"],
            "角色": user["角色"],
            "所属项目": user.get("所属项目", ""),
        }
        return user
    return None


def logout_user():
    """退出登录"""
    session.pop("user", None)


def get_current_user():
    """获取当前登录用户信息"""
    return session.get("user", None)


def is_logged_in():
    """判断是否已登录"""
    return "user" in session


def login_required(f):
    """装饰器：要求已登录才能访问"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_logged_in():
            flash("请先登录", "warning")
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """装饰器：要求集团或子公司管理员角色"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_logged_in():
            flash("请先登录", "warning")
            return redirect(url_for("login_page"))
        user = get_current_user()
        if user["角色"] not in ("集团", "子公司"):
            flash("权限不足", "danger")
            return redirect(url_for("admin_dashboard"))
        return f(*args, **kwargs)
    return decorated


def group_required(f):
    """装饰器：要求集团管理员角色"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_logged_in():
            flash("请先登录", "warning")
            return redirect(url_for("login_page"))
        user = get_current_user()
        if user["角色"] != "集团":
            flash("仅集团管理员可操作", "danger")
            return redirect(url_for("admin_dashboard"))
        return f(*args, **kwargs)
    return decorated


def get_project_filter():
    """获取当前用户的项目过滤条件"""
    user = get_current_user()
    if not user:
        return None
    if user["角色"] == "集团":
        return None  # 集团看全部
    return user.get("所属项目", "")  # 子公司只看自己的项目


# ===================== 商户门户认证 =====================

def find_contract(contract_no, merchant_name):
    """根据合同号和商户名称查找合同，返回合同 dict 或 None"""
    for c in database.load_contracts():
        if (str(c.get("合同号", "")).strip() == contract_no.strip()
                and str(c.get("商户名称", "")).strip() == merchant_name.strip()):
            return c
    return None


def register_merchant(username, contract_no, merchant_name, password):
    """商户注册：验证合同存在 + 创建密码账户，返回 contract dict / 'username_exists' / 'contract_exists' / None"""
    c = find_contract(contract_no, merchant_name)
    if not c:
        return None  # 合同不存在
    import hashlib
    hashed = hashlib.md5(password.encode()).hexdigest()
    result = database.create_merchant_account(username, contract_no, merchant_name, hashed)
    if result == "username_exists":
        return "username_exists"
    if result == "contract_exists":
        return "contract_exists"
    return c


def merchant_login(username, password):
    """商户密码登录：验证用户名+密码，成功返回合同信息"""
    account = database.get_merchant_account_by_username(username)
    if not account:
        return None
    import hashlib
    hashed = hashlib.md5(password.encode()).hexdigest()
    if account["password"] != hashed:
        return None
    # 确认合同仍存在
    c = find_contract(account["contract_no"], account["merchant_name"])
    if not c:
        return None
    session["merchant"] = {
        "username": username,
        "contract_no": account["contract_no"],
        "merchant_name": account["merchant_name"],
    }
    return c


def reset_merchant_password(contract_no, merchant_name, new_password):
    """商户自助重置密码：验证合同号+商户名称已注册，重置密码，返回 True / 'not_registered' / 'not_found'"""
    c = find_contract(contract_no, merchant_name)
    if not c:
        return "not_found"  # 合同不存在
    if not database.check_merchant_registered(contract_no):
        return "not_registered"  # 合同存在但未注册
    import hashlib
    hashed = hashlib.md5(new_password.encode()).hexdigest()
    database.update_merchant_password(contract_no, hashed)
    return True


def merchant_logout():
    """商户退出登录"""
    session.pop("merchant", None)


def is_merchant_logged_in():
    """判断商户是否已登录"""
    return "merchant" in session


def get_merchant_contract():
    """获取当前登录商户的合同"""
    if not is_merchant_logged_in():
        return None
    m = session["merchant"]
    return find_contract(m["contract_no"], m["merchant_name"])


def merchant_required(f):
    """装饰器：要求商户已登录"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_merchant_logged_in():
            flash("请先登录商户门户", "warning")
            return redirect(url_for("merchant_login_page"))
        return f(*args, **kwargs)
    return decorated
