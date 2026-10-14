# -*- coding: utf-8 -*-
"""
Olist Brazilian E-Commerce 数据预处理
数据来源: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

用法:
    python olist_preprocess.py --raw ./data --out ./clean

输出:
    clean/<table>.csv          9 张清洗后的表(可直接导入数据库, 与 schema.sql 对应)
    clean/fact_orders_wide.csv 订单级宽表(一行一个订单, 供分析/建模直接使用)
    clean/data_quality_report.csv  每一步处理影响的行数(可追溯)
"""
import argparse
import os
import re
import unicodedata

import numpy as np
import pandas as pd

LOG = []  # 数据质量日志: (table, step, affected_rows, note)


def log(table, step, n, note=""):
    LOG.append({"table": table, "step": step, "affected_rows": int(n), "note": note})
    print(f"[{table:<12}] {step:<45} {int(n):>9,}  {note}")


# ----------------------------------------------------------------------------
# 通用工具函数
# ----------------------------------------------------------------------------
def strip_accents(s: str) -> str:
    """去掉葡语重音: 'são paulo' -> 'sao paulo'"""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def normalize_city(s):
    """城市名统一: 小写、去重音、去掉 '/sp'、', brasil' 等后缀、统一撇号、压缩空格"""
    if pd.isna(s):
        return np.nan
    s = strip_accents(str(s)).lower().strip()
    s = s.replace("´", "'").replace("`", "'")
    s = re.split(r"\s*[/,\\]\s*", s)[0]          # 'cariacica / es' -> 'cariacica'
    s = re.sub(r"\(.*?\)", "", s)                  # 'arraial d'ajuda (porto seguro)'
    s = re.sub(r"\s+", " ", s).strip()
    if s == "" or s.isdigit() or "@" in s:          # '04482255', 邮箱等脏值
        return np.nan
    return s


def pad_zip(series):
    """邮编前缀在 CSV 中被当成整数读取, 丢了前导 0 (01037 -> 1037); 统一为 5 位字符串"""
    return series.astype("Int64").astype(str).str.zfill(5)


def clean_ids(df, cols):
    for c in cols:
        df[c] = df[c].astype(str).str.strip().str.lower()
    return df


def to_dt(df, cols):
    for c in cols:
        df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def read(raw, name, **kw):
    return pd.read_csv(os.path.join(raw, name), **kw)


# ----------------------------------------------------------------------------
# 1. geolocation -> 每个邮编前缀一行的维表
# ----------------------------------------------------------------------------
def clean_geolocation(raw):
    t = "geolocation"
    g = read(raw, "olist_geolocation_dataset.csv",
             dtype={"geolocation_zip_code_prefix": str})
    log(t, "raw rows", len(g))

    g["geolocation_zip_code_prefix"] = g["geolocation_zip_code_prefix"].str.zfill(5)

    n0 = len(g)
    g = g.drop_duplicates()
    log(t, "drop exact duplicate rows", n0 - len(g))

    # 巴西国境经纬度范围 (含海岛): lat -33.75~5.27, lng -73.99~-28.8
    out = ~(g.geolocation_lat.between(-33.75, 5.27) & g.geolocation_lng.between(-73.99, -28.8))
    log(t, "drop coords outside Brazil", out.sum())
    g = g[~out]

    g["geolocation_city"] = g["geolocation_city"].map(normalize_city)
    g["geolocation_state"] = g["geolocation_state"].str.upper().str.strip()

    # 同一邮编前缀有多个点 -> 取经纬度中位数(抗离群)、城市/州取众数
    mode = lambda s: s.mode().iat[0] if not s.mode().empty else np.nan
    geo = (g.groupby("geolocation_zip_code_prefix")
             .agg(lat=("geolocation_lat", "median"),
                  lng=("geolocation_lng", "median"),
                  city=("geolocation_city", mode),
                  state=("geolocation_state", mode),
                  n_points=("geolocation_lat", "size"))
             .reset_index()
             .rename(columns={"geolocation_zip_code_prefix": "zip_code_prefix"}))
    log(t, "aggregated to 1 row / zip prefix", len(geo), "PK = zip_code_prefix")
    return geo


# ----------------------------------------------------------------------------
# 2. customers
# ----------------------------------------------------------------------------
def clean_customers(raw, geo):
    t = "customers"
    c = read(raw, "olist_customers_dataset.csv")
    log(t, "raw rows", len(c))
    c = clean_ids(c, ["customer_id", "customer_unique_id"])
    c["customer_zip_code_prefix"] = pad_zip(c["customer_zip_code_prefix"])
    c["customer_city"] = c["customer_city"].map(normalize_city)
    c["customer_state"] = c["customer_state"].str.upper().str.strip()

    # 用 geolocation 回填缺失城市
    miss = c["customer_city"].isna()
    if miss.any():
        c.loc[miss, "customer_city"] = c.loc[miss, "customer_zip_code_prefix"].map(
            geo.set_index("zip_code_prefix")["city"])
    log(t, "city filled from geolocation", miss.sum())

    n_nogeo = (~c.customer_zip_code_prefix.isin(geo.zip_code_prefix)).sum()
    log(t, "zip prefix not in geolocation (kept)", n_nogeo, "坐标留空")

    # customer_id 是"每单一个"的, customer_unique_id 才是真实用户
    log(t, "distinct customer_unique_id", c.customer_unique_id.nunique(),
        "复购分析须用 unique_id")
    c["customer_total_orders"] = c.groupby("customer_unique_id")["customer_id"].transform("count")
    return c


# ----------------------------------------------------------------------------
# 3. sellers
# ----------------------------------------------------------------------------
def clean_sellers(raw, geo):
    t = "sellers"
    s = read(raw, "olist_sellers_dataset.csv")
    log(t, "raw rows", len(s))
    s = clean_ids(s, ["seller_id"])
    s["seller_zip_code_prefix"] = pad_zip(s["seller_zip_code_prefix"])
    before = s["seller_city"].copy()
    s["seller_city"] = s["seller_city"].map(normalize_city)
    log(t, "city text normalized (changed)", (before.str.lower() != s["seller_city"]).sum(),
        "去重音/去'/sp'后缀等")
    miss = s["seller_city"].isna()
    s.loc[miss, "seller_city"] = s.loc[miss, "seller_zip_code_prefix"].map(
        geo.set_index("zip_code_prefix")["city"])
    log(t, "invalid city -> filled from geolocation", miss.sum(), "如 '04482255'")
    s["seller_state"] = s["seller_state"].str.upper().str.strip()
    return s


# ----------------------------------------------------------------------------
# 4. category translation + products
# ----------------------------------------------------------------------------
TRANSLATION_FIX = {   # 官方翻译表中的拼写错误
    "fashio_female_clothing": "fashion_female_clothing",
    "costruction_tools_garden": "construction_tools_garden",
    "costruction_tools_tools": "construction_tools_tools",
    "home_confort": "home_comfort",
}
TRANSLATION_MISSING = {  # products 中出现但翻译表缺失的类目
    "pc_gamer": "pc_gamer",
    "portateis_cozinha_e_preparadores_de_alimentos": "portable_kitchen_food_preparers",
    "unknown": "unknown",
}


def clean_categories(raw):
    t = "category"
    cat = read(raw, "product_category_name_translation.csv")
    cat.columns = [c.lstrip("﻿") for c in cat.columns]
    n = cat["product_category_name_english"].isin(TRANSLATION_FIX).sum()
    cat["product_category_name_english"] = cat["product_category_name_english"].replace(TRANSLATION_FIX)
    log(t, "fix english typos", n)
    add = pd.DataFrame(list(TRANSLATION_MISSING.items()), columns=cat.columns)
    add = add[~add.product_category_name.isin(cat.product_category_name)]
    cat = pd.concat([cat, add], ignore_index=True)
    log(t, "add missing categories", len(add))
    return cat


def clean_products(raw, cat):
    t = "products"
    p = read(raw, "olist_products_dataset.csv")
    log(t, "raw rows", len(p))
    p = clean_ids(p, ["product_id"])
    # 原始列名拼写错误 lenght -> length
    p = p.rename(columns={"product_name_lenght": "product_name_length",
                          "product_description_lenght": "product_description_length"})

    miss_cat = p["product_category_name"].isna()
    p["product_category_name"] = p["product_category_name"].fillna("unknown")
    log(t, "missing category -> 'unknown'", miss_cat.sum())

    # 文本长度/照片数缺失与类目缺失同时出现 -> 记为 0 并加标记位
    p["is_listing_info_missing"] = p["product_name_length"].isna().astype(int)
    for col in ["product_name_length", "product_description_length", "product_photos_qty"]:
        p[col] = p[col].fillna(0).astype(int)

    # 重量为 0 不合理 -> 视为缺失
    dims = ["product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"]
    zero_w = (p["product_weight_g"] == 0).sum()
    p.loc[p["product_weight_g"] == 0, "product_weight_g"] = np.nan
    log(t, "weight == 0 -> NaN", zero_w)

    # 尺寸/重量缺失 -> 同类目中位数填补, 再不行用全局中位数
    n_miss = p[dims].isna().any(axis=1).sum()
    for col in dims:
        p[col] = p[col].fillna(p.groupby("product_category_name")[col].transform("median"))
        p[col] = p[col].fillna(p[col].median())
    log(t, "impute dims by category median", n_miss)

    p["product_volume_cm3"] = p["product_length_cm"] * p["product_height_cm"] * p["product_width_cm"]
    p = p.merge(cat, on="product_category_name", how="left")
    return p


# ----------------------------------------------------------------------------
# 5. orders
# ----------------------------------------------------------------------------
DATE_COLS = ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
             "order_delivered_customer_date", "order_estimated_delivery_date"]


def clean_orders(raw):
    t = "orders"
    o = read(raw, "olist_orders_dataset.csv")
    log(t, "raw rows", len(o))
    o = clean_ids(o, ["order_id", "customer_id"])
    o["order_status"] = o["order_status"].str.strip().str.lower()
    o = to_dt(o, DATE_COLS)

    # --- 时间逻辑校验: 不删行, 只打标记 (删掉会破坏外键 & 销售额统计) ---
    f1 = o.order_delivered_carrier_date < o.order_purchase_timestamp
    f2 = o.order_delivered_customer_date < o.order_delivered_carrier_date
    f3 = (o.order_status == "delivered") & o.order_delivered_customer_date.isna()
    f4 = (o.order_status != "delivered") & o.order_delivered_customer_date.notna()
    log(t, "flag: carrier date < purchase", f1.sum())
    log(t, "flag: delivered < carrier date", f2.sum())
    log(t, "flag: status=delivered but no date", f3.sum())
    log(t, "flag: not delivered but has date", f4.sum())
    o["is_time_anomaly"] = (f1 | f2).astype(int)
    o["is_status_anomaly"] = (f3 | f4).astype(int)

    # --- 衍生字段 ---
    ts = o.order_purchase_timestamp
    o["purchase_date"] = ts.dt.date
    o["purchase_year"] = ts.dt.year
    o["purchase_month"] = ts.dt.to_period("M").astype(str)
    o["purchase_dow"] = ts.dt.dayofweek          # 0=Mon
    o["purchase_hour"] = ts.dt.hour

    day = lambda a, b: (a - b).dt.total_seconds() / 86400
    o["approve_hours"] = day(o.order_approved_at, ts) * 24
    o["delivery_days"] = day(o.order_delivered_customer_date, ts)
    o["estimated_days"] = day(o.order_estimated_delivery_date, ts)
    o["delay_days"] = day(o.order_delivered_customer_date, o.order_estimated_delivery_date)
    # 异常时间产生的负数时长不可信 -> 置空
    o.loc[o.is_time_anomaly == 1, ["delivery_days", "delay_days"]] = np.nan
    # 用可空整数 Int64, 写出 CSV 为 0/1/空, 而不是 0.0/1.0 (否则 SQL 的 SMALLINT 导入失败)
    o["is_late"] = (o.delay_days > 0).astype("Int64").where(o.delay_days.notna())
    # 审核超过 7 天的订单标记出来 (最长达 188 天, 属异常)
    o["is_slow_approval"] = (o.approve_hours > 24 * 7).astype(int)
    log(t, "flag: approved > 7 days after purchase", o.is_slow_approval.sum())

    # 2016-09/10/12 与 2018-09/10 订单极少, 属于采集首尾不完整期 -> 标记, 趋势分析时可排除
    o["is_full_period"] = ((o.purchase_month >= "2017-01") & (o.purchase_month <= "2018-08")).astype(int)
    log(t, "flag: outside 2017-01~2018-08", (o.is_full_period == 0).sum(), "首尾月份数据不完整")
    return o


# ----------------------------------------------------------------------------
# 6. order_items
# ----------------------------------------------------------------------------
def clean_items(raw):
    t = "order_items"
    i = read(raw, "olist_order_items_dataset.csv")
    log(t, "raw rows", len(i))
    i = clean_ids(i, ["order_id", "product_id", "seller_id"])
    i = to_dt(i, ["shipping_limit_date"])
    n = i.duplicated(["order_id", "order_item_id"]).sum()
    i = i.drop_duplicates(["order_id", "order_item_id"])
    log(t, "drop duplicated PK (order_id,item_id)", n)
    bad = (i.price <= 0) | (i.freight_value < 0)
    i = i[~bad]
    log(t, "drop price<=0 or freight<0", bad.sum())
    log(t, "freight == 0 (kept, free shipping)", (i.freight_value == 0).sum())
    i["item_total"] = i.price + i.freight_value
    i["freight_ratio"] = i.freight_value / i.price
    # 价格离群: IQR 方法只做标记, 不删除(高价商品是真实交易)
    q1, q3 = i.price.quantile([.25, .75])
    i["is_price_outlier"] = (i.price > q3 + 3 * (q3 - q1)).astype(int)
    log(t, "flag: price outlier (>Q3+3IQR)", i.is_price_outlier.sum())
    return i


# ----------------------------------------------------------------------------
# 7. order_payments
# ----------------------------------------------------------------------------
def clean_payments(raw):
    t = "payments"
    p = read(raw, "olist_order_payments_dataset.csv")
    log(t, "raw rows", len(p))
    p = clean_ids(p, ["order_id"])
    p["payment_type"] = p["payment_type"].str.strip().str.lower()
    n = (p.payment_installments < 1).sum()
    p.loc[p.payment_installments < 1, "payment_installments"] = 1
    log(t, "installments 0 -> 1", n)
    log(t, "payment_type = not_defined (kept)", (p.payment_type == "not_defined").sum())
    log(t, "payment_value == 0 (kept, voucher)", (p.payment_value == 0).sum())
    return p


# ----------------------------------------------------------------------------
# 8. order_reviews
# ----------------------------------------------------------------------------
def clean_reviews(raw):
    t = "reviews"
    r = read(raw, "olist_order_reviews_dataset.csv")
    log(t, "raw rows", len(r))
    r = clean_ids(r, ["review_id", "order_id"])
    r = to_dt(r, ["review_creation_date", "review_answer_timestamp"])
    # review_id 本身有重复(同一条评价挂在多个订单上), 故 PK 用 (review_id, order_id)
    log(t, "review_id duplicated (1 review->n orders)", r.review_id.duplicated().sum())
    n = r.duplicated(["review_id", "order_id"]).sum()
    r = r.drop_duplicates(["review_id", "order_id"])
    log(t, "drop duplicated PK (review_id,order_id)", n)

    for c in ["review_comment_title", "review_comment_message"]:
        r[c] = (r[c].fillna("").astype(str)
                 .str.replace(r"[\r\n\t]+", " ", regex=True)   # 换行会破坏 CSV / SQL 导入
                 .str.replace(r"\s+", " ", regex=True).str.strip())
    r["has_comment"] = (r.review_comment_message != "").astype(int)
    r["comment_length"] = r.review_comment_message.str.len()
    r["answer_hours"] = (r.review_answer_timestamp - r.review_creation_date).dt.total_seconds() / 3600
    r["sentiment_label"] = pd.cut(r.review_score, [0, 2, 3, 5], labels=["negative", "neutral", "positive"])
    log(t, "has text comment", r.has_comment.sum())
    return r


# ----------------------------------------------------------------------------
# 9. 参照完整性检查 + 订单级宽表
# ----------------------------------------------------------------------------
def check_fk(child, ccol, parent, pcol, name):
    n = (~child[ccol].isin(parent[pcol])).sum()
    log("FK", name, n, "OK" if n == 0 else "orphans!")
    return n


def build_wide(o, c, i, p, r, prod, s, geo):
    # 商品层 -> 订单层
    ip = i.merge(prod[["product_id", "product_category_name_english", "product_weight_g"]],
                 on="product_id", how="left")
    items_agg = ip.groupby("order_id").agg(
        n_items=("order_item_id", "count"),
        n_products=("product_id", "nunique"),
        n_sellers=("seller_id", "nunique"),
        items_price=("price", "sum"),
        items_freight=("freight_value", "sum"),
        total_weight_g=("product_weight_g", "sum"),
        main_category=("product_category_name_english", lambda x: x.mode().iat[0] if not x.mode().empty else np.nan),
        main_seller_id=("seller_id", "first"),
    ).reset_index()
    items_agg["items_total"] = items_agg.items_price + items_agg.items_freight

    pay_agg = p.groupby("order_id").agg(
        payment_total=("payment_value", "sum"),
        n_payments=("payment_sequential", "count"),
        max_installments=("payment_installments", "max"),
        main_payment_type=("payment_type", lambda x: x.value_counts().index[0]),
    ).reset_index()

    # 一个订单可能有多条评价 -> 取最新一条
    rev = (r.sort_values("review_answer_timestamp")
             .drop_duplicates("order_id", keep="last")
             [["order_id", "review_score", "has_comment", "sentiment_label"]])

    w = (o.merge(c, on="customer_id", how="left")
          .merge(items_agg, on="order_id", how="left")
          .merge(pay_agg, on="order_id", how="left")
          .merge(rev, on="order_id", how="left")
          .merge(s[["seller_id", "seller_zip_code_prefix", "seller_state"]],
                 left_on="main_seller_id", right_on="seller_id", how="left")
          .drop(columns="seller_id"))

    gi = geo.set_index("zip_code_prefix")
    for who in ["customer", "seller"]:
        z = w[f"{who}_zip_code_prefix"]
        w[f"{who}_lat"] = z.map(gi.lat)
        w[f"{who}_lng"] = z.map(gi.lng)

    # Haversine 距离 (km): 买卖双方距离对运费 / 时效分析非常关键
    lat1, lng1, lat2, lng2 = map(np.radians, [w.customer_lat, w.customer_lng, w.seller_lat, w.seller_lng])
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2
    w["distance_km"] = 6371 * 2 * np.arcsin(np.sqrt(a))
    w["is_same_state"] = (w.customer_state == w.seller_state).astype(float).where(w.seller_state.notna())

    diff = (w.payment_total - w.items_total).abs()
    w["is_payment_mismatch"] = (diff > 1).astype(int).where(w.items_total.notna() & w.payment_total.notna())
    log("wide", "flag: |payment - items| > 1 BRL", w.is_payment_mismatch.fillna(0).sum(),
        "多为利息/优惠券, 保留")
    log("wide", "orders without items", w.n_items.isna().sum(), "多为 unavailable/canceled")
    # 计数/标记列在 merge 后因缺失变成 float, 统一转回可空整数
    int_cols = ["n_items", "n_products", "n_sellers", "n_payments", "max_installments",
                "review_score", "has_comment", "is_same_state", "is_payment_mismatch", "is_late"]
    w[int_cols] = w[int_cols].round().astype("Int64")
    log("wide", "final rows", len(w))
    return w


# ----------------------------------------------------------------------------
def main(raw, out):
    os.makedirs(out, exist_ok=True)
    geo = clean_geolocation(raw)
    cust = clean_customers(raw, geo)
    sell = clean_sellers(raw, geo)
    cat = clean_categories(raw)
    prod = clean_products(raw, cat)
    orders = clean_orders(raw)
    items = clean_items(raw)
    pays = clean_payments(raw)
    revs = clean_reviews(raw)

    print("\n--- referential integrity ---")
    check_fk(orders, "customer_id", cust, "customer_id", "orders.customer_id -> customers")
    check_fk(items, "order_id", orders, "order_id", "order_items.order_id -> orders")
    check_fk(items, "product_id", prod, "product_id", "order_items.product_id -> products")
    check_fk(items, "seller_id", sell, "seller_id", "order_items.seller_id -> sellers")
    check_fk(pays, "order_id", orders, "order_id", "payments.order_id -> orders")
    check_fk(revs, "order_id", orders, "order_id", "reviews.order_id -> orders")
    check_fk(prod, "product_category_name", cat, "product_category_name", "products.category -> category")

    print("\n--- wide table ---")
    wide = build_wide(orders, cust, items, pays, revs, prod, sell, geo)

    tables = {
        "geolocation": geo, "customers": cust, "sellers": sell, "product_category": cat,
        "products": prod.drop(columns="product_category_name_english"),
        "orders": orders, "order_items": items, "order_payments": pays,
        "order_reviews": revs, "fact_orders_wide": wide,
    }
    for name, df in tables.items():
        # 浮点数保留 4 位小数, 文件更小、导入更稳
        fcols = df.select_dtypes("float").columns
        df[fcols] = df[fcols].round(4)
        df.to_csv(os.path.join(out, f"{name}.csv"), index=False, encoding="utf-8")
    pd.DataFrame(LOG).to_csv(os.path.join(out, "data_quality_report.csv"), index=False, encoding="utf-8-sig")
    print(f"\nDone. Files written to {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="./data", help="原始 CSV 所在目录")
    ap.add_argument("--out", default="./clean", help="输出目录")
    a = ap.parse_args()
    main(a.raw, a.out)
