"""
utils.py —— 小牛b商管系统 共享工具（Web版）
去除 Tkinter 依赖，保留租金计算引擎和所有业务逻辑
"""
import json
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from config import CYCLE_MAP
import db

def generate_rent_plan(contract, _shops_cache=None, _payments_cache=None, _biz_cache=None):
    """
    生成合同租金缴纳计划。
    根据合同的"租金模式"自动切换计算方式：
      - 保底：应缴 = 保底租金单价 × 面积 × 有效天数（扣除免租）
      - 提成：应缴 = 本期营业额合计 × 提成扣点% × 有效天数比例
      - 取高：应缴 = max(保底金额, 提成金额)
    免租计划按天折算，落入免租时段的天数不计租金。
    """
    try:
        shop_no = contract.get("关联铺位号", "")
        area = 0.0
        if _shops_cache is not None:
            for shop in _shops_cache:
                if str(shop.get("铺位号", "")).strip() == str(shop_no).strip():
                    try:
                        area = float(shop.get("计租面积(㎡)", shop.get("建筑面积(㎡)", 0) or 0))
                    except:
                        area = 0.0
                    break
        else:
            area = db.get_shop_area(shop_no)

        rent_mode = contract.get("租金模式", "保底")
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
        # 合并重叠/相邻区间
        if len(free_ranges) > 1:
            free_ranges.sort()
            merged = [free_ranges[0]]
            for s, e in free_ranges[1:]:
                if s <= merged[-1][1] + timedelta(days=1):
                    merged[-1] = (merged[-1][0], max(merged[-1][1], e))
                else:
                    merged.append((s, e))
            free_ranges = merged

        # ── 解析分段计划（保底/提成/物业费）──
        def _parse_plan_json(key):
            raw = contract.get(key, [])
            if isinstance(raw, str):
                try: return json.loads(raw)
                except: return []
            if isinstance(raw, list): return raw
            return []

        base_rent_plans = _parse_plan_json("保底租金计划")
        comm_plans = _parse_plan_json("提成扣点计划")
        prop_fee_plans = _parse_plan_json("物业费计划")
        has_base_rent_plan = len(base_rent_plans) > 0
        has_comm_plan = len(comm_plans) > 0
        has_prop_fee_plan = len(prop_fee_plans) > 0

        # 辅助：在分段计划中查找某日期所在段的值，找不到则返回默认值
        def _get_plan_value(plans, dt_str, default=0.0):
            dt = datetime.strptime(dt_str, "%Y-%m-%d") if isinstance(dt_str, str) else dt_str
            for p in plans:
                try:
                    ps = datetime.strptime(p["start"], "%Y-%m-%d")
                    pe = datetime.strptime(p["end"], "%Y-%m-%d")
                    if ps <= dt <= pe:
                        return float(p.get("value", 0))
                except: pass
            return default

        # 辅助：计算一个缴费周期内落在各分段的天数加权金额
        def _weighted_amount(plans, period_start, period_end, default_rate, area_val, effective_day_count):
            """按天数加权计算：将缴费周期拆分到各分段，分别用各段的值计算后求和"""
            if not plans:
                return default_rate * area_val * effective_day_count
            total = 0.0
            for p in plans:
                try:
                    ps = datetime.strptime(p["start"], "%Y-%m-%d")
                    pe = datetime.strptime(p["end"], "%Y-%m-%d")
                except: continue
                # 该分段与缴费周期的交集
                o_start = max(period_start, ps)
                o_end = min(period_end, pe)
                if o_start <= o_end:
                    overlap_days = (o_end - o_start).days + 1
                    val = float(p.get("value", 0))
                    total += val * area_val * overlap_days
            return total if total > 0 else default_rate * area_val * effective_day_count

        cycle = contract.get("支付周期", "")
        cno = contract.get("合同号")
        months = CYCLE_MAP.get(cycle, 1)

        # 经营数据缓存
        biz_list = _biz_cache
        if _biz_cache is None and rent_mode in ("提成", "取高"):
            biz_list = db.load_business_data()

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

            # 计算本期免租天数
            free_days = 0
            for fs, fe in free_ranges:
                o_start = max(cur, fs)
                o_end = min(pe, fe)
                if o_start <= o_end:
                    free_days += (o_end - o_start).days + 1
            effective_days = max(days - free_days, 0)

            # 根据租金模式计算应缴金额（支持分段计划）
            if rent_mode == "保底":
                if has_base_rent_plan:
                    should = _weighted_amount(base_rent_plans, cur, pe, daily_rate, area, effective_days)
                else:
                    should = daily_rate * area * effective_days
            elif rent_mode == "提成":
                period_revenue = _get_period_revenue(biz_list, cno, cur, pe)
                if has_comm_plan:
                    # 分段提成：按天数加权提成百分比
                    comm_weighted = 0.0
                    for cp in comm_plans:
                        try:
                            cps = datetime.strptime(cp["start"], "%Y-%m-%d")
                            cpe = datetime.strptime(cp["end"], "%Y-%m-%d")
                            o_start = max(cur, cps)
                            o_end = min(pe, cpe)
                            if o_start <= o_end:
                                overlap_days = (o_end - o_start).days + 1
                                comm_weighted += float(cp.get("value", 0)) * overlap_days
                        except: pass
                    if comm_weighted == 0:
                        comm_weighted = commission_pct * effective_days
                    should = period_revenue * comm_weighted / (100.0 * effective_days) if effective_days > 0 else 0
                else:
                    should = period_revenue * commission_pct / 100.0
                    if days > 0:
                        should = should * effective_days / days
            elif rent_mode == "取高":
                if has_base_rent_plan:
                    base_rent = _weighted_amount(base_rent_plans, cur, pe, daily_rate, area, effective_days)
                else:
                    base_rent = daily_rate * area * effective_days
                period_revenue = _get_period_revenue(biz_list, cno, cur, pe)
                if has_comm_plan:
                    comm_weighted = 0.0
                    for cp in comm_plans:
                        try:
                            cps = datetime.strptime(cp["start"], "%Y-%m-%d")
                            cpe = datetime.strptime(cp["end"], "%Y-%m-%d")
                            o_start = max(cur, cps)
                            o_end = min(pe, cpe)
                            if o_start <= o_end:
                                overlap_days = (o_end - o_start).days + 1
                                comm_weighted += float(cp.get("value", 0)) * overlap_days
                        except: pass
                    if comm_weighted == 0:
                        comm_weighted = commission_pct * effective_days
                    comm_rent = period_revenue * comm_weighted / (100.0 * effective_days) if effective_days > 0 else 0
                else:
                    comm_rent = period_revenue * commission_pct / 100.0
                    if days > 0:
                        comm_rent = comm_rent * effective_days / days
                should = max(base_rent, comm_rent)
            else:
                should = daily_rate * area * effective_days

            pay_time_str = cur.strftime("%Y-%m-%d")
            if _payments_cache is not None:
                paid = paid_index.get((cno, pay_time_str), 0.0)
                prop_paid = property_paid_index.get((cno, pay_time_str), 0.0)
            else:
                paid = db.get_paid(cno, pay_time_str)
                prop_paid = db.get_property_fee_paid(cno, pay_time_str)

            # 物业费（支持分段计划）
            if has_prop_fee_plan:
                property_fee = round(_weighted_amount(prop_fee_plans, cur, pe, property_fee_rate, area, effective_days), 2)
            else:
                property_fee = round(property_fee_rate * area * effective_days, 2)
            # 查出本期的实际单价（有分段则取当期段值，无分段则用默认值）
            cur_daily = _get_plan_value(base_rent_plans, pay_time_str, daily_rate)
            cur_comm = _get_plan_value(comm_plans, pay_time_str, commission_pct)
            cur_prop = _get_plan_value(prop_fee_plans, pay_time_str, property_fee_rate)
            plan.append({
                "合同号": cno,
                "支付时间": pay_time_str,
                "应缴金额(元)": round(should, 2),
                "已缴金额(元)": paid,
                "应缴物业费": property_fee,
                "已缴物业费": prop_paid,
                "保底租金单价": cur_daily,
                "提成扣点": cur_comm,
                "物业费单价": cur_prop,
                "建筑面积": area,
            })
            cur = nxt
        return plan
    except:
        return []


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


def total_paid(contract):
    return round(sum(p["已缴金额(元)"] for p in generate_rent_plan(contract)), 2)


def total_rent(contract):
    return round(sum(p["应缴金额(元)"] for p in generate_rent_plan(contract)), 2)


def remaining_rent(contract):
    return round(total_rent(contract) - total_paid(contract), 2)


def next_days_label(contract):
    """返回 (标签, 天数) — 下次缴费还有几天"""
    try:
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
    """计算当前逾期金额"""
    try:
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
