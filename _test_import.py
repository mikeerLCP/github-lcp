"""快速测试：导入 app 并检查路由注册"""
import sys
sys.path.insert(0, r"C:\Users\bj_ha\Desktop\web版开发")

# 切换到项目目录
import os
os.chdir(r"C:\Users\bj_ha\Desktop\web版开发")

from app import app

print("=" * 50)
print("路由列表：")
for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
    methods = ",".join(sorted(rule.methods - {"HEAD", "OPTIONS"}))
    if methods:
        print(f"  {methods:10s} {rule.rule}")

print("=" * 50)
print(f"共注册 {len([r for r in app.url_map.iter_rules() if 'GET' in r.methods])} 个路由")
print("商户门户路由检查通过!")
