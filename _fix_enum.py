import pymysql
c = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='adminhang', database='xiaoniu_shangguan')
cur = c.cursor()
cur.execute("ALTER TABLE users MODIFY 角色 enum('集团','子公司','商户') NOT NULL DEFAULT '子公司'")
c.commit()
print("OK - 角色枚举已扩展")
c.close()
