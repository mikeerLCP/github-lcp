import db, utils
from datetime import datetime, date

c = [x for x in db.load_contracts() if x.get('合同号') == 'menhutest1'][0]
plan = utils.generate_rent_plan(c, db.load_shops(), db.load_payments(), db.load_business_data())
today = date.today()
unpaid = [p for p in plan if p['已缴金额(元)'] < p['应缴金额(元)']]

# 下次缴费：未来未缴
future_unpaid = [p for p in unpaid if datetime.strptime(p['支付时间'], '%Y-%m-%d').date() >= today]
future_unpaid.sort(key=lambda x: x['支付时间'])
if future_unpaid:
    d = datetime.strptime(future_unpaid[0]['支付时间'], '%Y-%m-%d').date()
    diff = (d - today).days
    print(f"下次缴费日期: {future_unpaid[0]['支付时间']}")
    print(f"下次缴费剩余天数: {diff}")
else:
    print("下次缴费剩余天数: - (无未来未缴)")

# 逾期状态
has_overdue = any(datetime.strptime(p['支付时间'], '%Y-%m-%d').date() < today for p in unpaid)
print(f"租金逾期状态: {'已逾期' if has_overdue else '正常'}")
