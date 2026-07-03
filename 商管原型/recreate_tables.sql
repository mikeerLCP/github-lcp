-- 重建小牛b商管数据库表（列名对齐 JSON 字段结构）
USE xiaoniu_shangguan;

-- 先删旧表
DROP TABLE IF EXISTS payment_records;
DROP TABLE IF EXISTS business_data;
DROP TABLE IF EXISTS opportunities;
DROP TABLE IF EXISTS contracts;
DROP TABLE IF EXISTS shops;

-- ========== 商铺表 ==========
CREATE TABLE shops (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    铺位号                VARCHAR(50)  NOT NULL UNIQUE,
    所属项目              VARCHAR(50),
    位置                  VARCHAR(200),
    铺位状态              VARCHAR(20)  DEFAULT '空置',
    适用业态              VARCHAR(200),
    计租面积㎡            DECIMAL(10,2),
    基准租金元㎡天        DECIMAL(10,2),
    备注                  TEXT
) COMMENT '商铺信息表';

-- ========== 合同表 ==========
CREATE TABLE contracts (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    合同号                VARCHAR(50)  NOT NULL UNIQUE,
    商户名称              VARCHAR(100) NOT NULL,
    经营业态              VARCHAR(50),
    所属项目              VARCHAR(50),
    关联铺位号            VARCHAR(50),
    保底租金元㎡天        DECIMAL(12,2),
    提成租金扣点          DECIMAL(5,2),
    签约日期              DATE,
    租赁开始日期          DATE NOT NULL,
    租赁结束日期          DATE NOT NULL,
    终止日期              DATE,
    免租期天              INT DEFAULT 0,
    剩余租期天            INT DEFAULT 0,
    押金                DECIMAL(12,2),
    押金支付状态          VARCHAR(20),
    支付周期              VARCHAR(10),
    合同状态              VARCHAR(20),
    联系电话              VARCHAR(30),
    联系人                VARCHAR(50),
    备注                  TEXT,
    租金模式              VARCHAR(20) DEFAULT ''
) COMMENT '合同信息表';

-- ========== 缴费记录表 ==========
CREATE TABLE payment_records (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    合同号                VARCHAR(50)  NOT NULL,
    支付时间              VARCHAR(20)  NOT NULL,
    已缴金额元            DECIMAL(12,2) DEFAULT 0,
    UNIQUE KEY uk_contract_pay (合同号, 支付时间)
) COMMENT '租金缴费记录表';

-- ========== 经营数据表 ==========
CREATE TABLE business_data (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    合同号                VARCHAR(50)  NOT NULL,
    商户名称              VARCHAR(100),
    日期                  DATE NOT NULL,
    营业额                DECIMAL(12,2) NOT NULL,
    客流量                INT,
    成交量                INT,
    业态                  VARCHAR(50),
    录入时间              VARCHAR(30),
    备注                  TEXT,
    UNIQUE KEY uk_contract_date (合同号, 日期)
) COMMENT '每日经营数据表';

-- ========== 商机表 ==========
CREATE TABLE opportunities (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    商机编号              VARCHAR(50)  NOT NULL UNIQUE,
    商户名称              VARCHAR(100),
    联系人                VARCHAR(50),
    联系电话              VARCHAR(30),
    意向项目              VARCHAR(50),
    意向业态              VARCHAR(50),
    意向面积㎡            DECIMAL(10,2),
    商机来源              VARCHAR(50),
    当前阶段              VARCHAR(50),
    首次接洽日期          DATE,
    最近跟进日期          DATE,
    意向金金额元          DECIMAL(12,2),
    意向金支付日期        DATE,
    意向金去向            VARCHAR(50) DEFAULT '',
    跟进结果              VARCHAR(100),
    负责人                VARCHAR(50),
    备注                  TEXT,
    跟进记录              JSON
) COMMENT '商机跟进表';

SHOW TABLES;
