import db, utils
from datetime import datetime, date

contracts = db.load_contracts()
c = None
for ct in contracts:
    if 'menhutest1' in str(ct.get('商户名称', '')).lower() or 'menhutest1' in str(ct.get('合同号', '')).lower():
        c = ct
        break

if not c:
    print("未找到 menhutest1 合同")
    exit()

print("=== 合同 ===")
for k, v in c.items():
    print(f"  {k}: {v}")

payments = db.load_payments()
print("\n=== 缴费记录 ===")
for p in payments:
    if p.get('合同号') == c.get('合同号'):
        for k, v in p.items():
            print(f"  {k}: {v}")
        print()

plan = utils.generate_rent_plan(c, db.load_shops(), payments, db.load_business_data())
print("=== 收缴计划 ===")
print(f"  today = {date.today()}")
for i, p in enumerate(plan):
    d = datetime.strptime(p["支付时间"], "%Y-%m-%d").date()
    if d < date.today() and p["已缴金额(元)"] < p["应缴金额(元)"]:
        st = "逾期"
    elif d >= date.today():
        st = "未到期"
    else:
        st = "已缴"
    print(f"  [{i}] 支付时间={p['支付时间']} 应缴租金={p['应缴金额(元)']} 已缴租金={p['已缴金额(元)']} 应缴物业费={p.get('应缴物业费', '?')} 已缴物业费={p.get('已缴物业费', '?')} -> {st}")

# 模拟后端状态判断
today = date.today()
plan_data = plan
print("\n=== 模拟后端状态判断 ===")
unpaid = [p for p in plan_data if p["已缴金额(元)"] < p["应缴金额(元)"]]
print(f"  unpaid count = {len(unpaid)}")
if not unpaid:
    rent_status = "已结清"
else:
    found = False
    for p in unpaid:
        d = datetime.strptime(p["支付时间"], "%Y-%m-%d").date()
        print(f"  checking: 支付时间={p['支付时间']} 已缴={p['已缴金额(元)']} 应缴={p['应缴金额(元)']} d>=today={d >= today}")
        if d >= today:
            rent_status = "正常"
            found = True
            break
    if not found:
        rent_status = "已逾期"
print(f"  -> 租金逾期状态 = {rent_status}")
