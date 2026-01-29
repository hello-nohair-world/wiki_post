# -*- coding: utf-8 -*-
"""
功能：使用 POST 方式登录中文维基百科（BotPasswords 推荐：action=login），并爬取“新闻动态”页面的新闻。
步骤：
1) GET 获取 login token（type=login）
2) POST 提交 lgname/lgpassword/lgtoken（action=login）
3) GET 查询 userinfo 验证是否登录成功
4) GET 请求新闻动态页面
5) 解析新闻内容，按序号、新闻、日期格式输出，并保存到多种格式。
"""
import re
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import csv
import json
import pandas as pd
import pymysql
import os


# =========================
# 1) 基础配置
# =========================
BASE_URL = "https://zh.wikipedia.org/"
API_URL = urljoin(BASE_URL, "w/api.php")

# 机器人账号：主账号@机器人名
USERNAME = "Wisdom666666@python-login-mytest"
# 机器人密码：Special:BotPasswords
PASSWORD = "38jbgqoq3do6ms4t548r1g4hanolql33"

# 新闻动态页面的URL (简体中文移动版)
NEWS_PORTAL_URL = "https://zh.m.wikipedia.org/wiki/Portal:新闻动态"


# =========================
# 2) 获取 login token
# =========================
def get_login_token(session: requests.Session) -> str:
    params = {
        "action": "query",
        "meta": "tokens",
        "type": "login",
        "format": "json",
    }
    r = session.get(API_URL, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    return data["query"]["tokens"]["logintoken"]


# =========================
# 3) POST 登录（BotPasswords：action=login）
# =========================
def botpassword_login(session: requests.Session, username: str, password: str) -> dict:
    lgtoken = get_login_token(session)

    data = {
        "action": "login",
        "format": "json",
        "lgname": username,
        "lgpassword": password,
        "lgtoken": lgtoken,
    }

    r = session.post(API_URL, data=data, timeout=20)
    r.raise_for_status()
    return r.json()


# =========================
# 4) 验证登录状态
# =========================
def get_user_info(session: requests.Session) -> dict:
    params = {
        "action": "query",
        "meta": "userinfo",
        "uiprop": "groups|rights|editcount",
        "format": "json",
    }
    r = session.get(API_URL, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


# =========================
# 5) 爬取新闻动态页面并解析新闻
# =========================
def scrape_news_portal(session: requests.Session) -> list:
    """
    从新闻动态页面抓取新闻，并返回一个包含字典的列表，每个字典包含 'date', 'news_text', 'index' 字段。
    解析过程中会移除新闻末尾的引用标记（如 <sup> 标签），并且如果某天没有有效新闻，则不记录该日期。
    """
    print(f"\n[+] 正在请求新闻动态页面: {NEWS_PORTAL_URL}")
    r = session.get(NEWS_PORTAL_URL, timeout=20)
    r.raise_for_status()
    r.encoding = 'utf-8' # 明确指定编码

    soup = BeautifulSoup(r.text, 'html.parser')

    news_list = []

    # 查找所有代表日期的 h2 标题，其 id 符合 "数字月数字日" 的模式 (例如 "1月17日", "2月1日")
    # 使用 lambda 函数和正则表达式来匹配
    date_headers = soup.find_all('h2', id=lambda x: x and re.match(r'^\d+月\d+日$', x))

    # 添加一个计数器，用于跳过第一个日期
    day_counter = 0

    for header in date_headers:
        day_counter += 1

        # 跳过第一个日期（最新的日期）
        if day_counter == 1:
            continue

        # 提取日期文本，例如 "1月17日" 
        date_text = header.get_text(strip=True)
        if not date_text:
            continue

        # 找到该日期标题所在的父级 div (class='mw-heading mw-heading2')
        parent_div = header.find_parent('div', class_='mw-heading mw-heading2')
        if not parent_div:
            print(f"[WARNING] Could not find parent div for date: {date_text}")
            continue

        # 在父级 div 内查找下一个同级的 div (class_='excerpt-block')
        excerpt_block = parent_div.find_next_sibling('div', class_='excerpt-block')
        if not excerpt_block:
            print(f"[WARNING] Could not find excerpt block for date: {date_text}")
            continue

        # 在 excerpt_block 中找到 <ul> 列表
        ul_element = excerpt_block.find('ul')
        if not ul_element:
            print(f"[INFO] No <ul> found in excerpt block for date: {date_text}, skipping this date.")
            continue # 可能某天没有新闻，跳过整个日期

        # 遍历 <ul> 中的所有 <li> 元素
        li_elements = ul_element.find_all('li')
        day_news_items = [] # 临时存储当天的有效新闻
        for i, li in enumerate(li_elements, 1):
            # 在提取文本前，先移除 <sup> 标签
            for sup_tag in li.find_all('sup'):
                sup_tag.decompose() # decompose() 会完全移除标签及其内容

            # 使用 .get_text(strip=True) 提取纯文本
            news_text = li.get_text(strip=True)
            # -----------------------------

            if news_text:
                day_news_items.append(news_text)
            else:
                print(f"[INFO] Empty news item found for date: {date_text} after cleaning.")

        # 只有当当天有至少一条有效新闻时，才添加到最终列表
        if len(day_news_items) > 0:
            # 将当天的所有有效新闻都添加到总列表中
            for news_item in day_news_items:
                news_list.append({
                    'index': len(news_list) + 1, # 为每条新闻分配一个全局序号
                    'news': news_item, # 使用 'news' 作为键名
                    'date': date_text  # 使用 'date' 作为键名
                })
        else:
            print(f"[INFO] No valid news found for date: {date_text}, skipping this date.")

    return news_list

# =========================
# 6) 文件和数据库保存相关函数/类
# =========================

# 创建 results 文件夹，用于存储爬取到的数据文件
def ensure_results_dir():
    # 检查 results 文件夹是否存在
    if not os.path.exists('results'):
        # 若不存在，则创建该文件夹
        os.makedirs('results')

# 保存到 TXT
def save_to_txt(data, filename='results/wiki_news.txt'):
    # 检查数据是否为空
    if not data:
        print("TXT 数据为空，未保存。")
        return
    # 以写入模式打开文件
    with open(filename, 'w', encoding='utf-8') as f:
        for item in data:
            # 写入新闻编号、新闻内容、日期
            f.write(f"{item['index']}. {item['news']} - {item['date']}\n\n")
    print(f"已保存 TXT 到 {filename}")

# 保存到 JSON
def save_to_json(data, filename='results/wiki_news.json'):
    # 检查数据是否为空
    if not data:
        print("JSON 数据为空，未保存。")
        return
    # 以写入模式打开文件
    with open(filename, 'w', encoding='utf-8') as f:
        # 将数据以JSON格式写入文件，设置不使用ASCII编码，缩进为4个空格
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"已保存 JSON 到 {filename}")

# 保存到 CSV
def save_to_csv(data, filename='results/wiki_news.csv'):
    # 检查数据是否为空
    if not data:
        print("CSV 数据为空，未保存。")
        return
    # 以写入模式打开文件，设置编码和换行符
    with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
        # 创建 CSV 写入器，指定字段名
        writer = csv.DictWriter(f, fieldnames=['index', 'news', 'date']) # 根据数据结构调整字段名
        # 写入表头
        writer.writeheader()
        # 写入数据行
        writer.writerows(data)
    print(f"已保存 CSV 到 {filename}")

# 保存到 Excel
def save_to_excel(data, filename='results/wiki_news.xlsx'):
    # 检查数据是否为空
    if not data:
        print("Excel 数据为空，未保存。")
        return
    # 将数据转换为 Pandas 的 DataFrame 对象
    df = pd.DataFrame(data)
    # 将 DataFrame 保存为 Excel 文件，不保存索引
    df.to_excel(filename, index=False, engine='openpyxl')
    print(f"已保存 Excel 到 {filename}")

# 数据库保存类
class MySQLPipeline:
    def __init__(self):
        # 连接到 MySQL 数据库
        # 请根据您的实际情况修改 host, user, password
        self.conn = pymysql.connect(
            host='localhost',
            user='root',
            password='root',
            charset='utf8mb4'
        )
        # 创建游标对象
        self.cursor = self.conn.cursor()
        # 创建数据库（如果不存在）
        self.cursor.execute("CREATE DATABASE IF NOT EXISTS spider")
        # 使用指定的数据库
        self.cursor.execute("USE spider")
        # 创建数据表（如果不存在）
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS wiki_news (
            `index` INT PRIMARY KEY,
            `news` TEXT,
            `date` VARCHAR(50)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        # 提交数据库操作
        self.conn.commit()

    def process_item(self, item):
        # SQL 插入语句，若主键冲突则更新数据
        sql = """
        INSERT INTO wiki_news (`index`, `news`, `date`)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            `news` = VALUES(`news`),
            `date` = VALUES(`date`)
        """
        # 执行 SQL 语句
        self.cursor.execute(sql, (
            item['index'], item['news'], item['date']
        ))
        # 提交数据库操作
        self.conn.commit()

    def close(self):
        # 关闭数据库连接
        self.cursor.close()
        self.conn.close()


def main():
    session = requests.Session()

    # （可选）加 UA，减少被当成异常脚本
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/143.0.0.0 Safari/537.36"
    })

    # 1) 登录
    login_result = botpassword_login(session, USERNAME, PASSWORD)
    print("=== login_result ===")
    print(login_result)

    # 2) 判断登录结果（action=login 的返回结构不同）
    lg = login_result.get("login", {})
    if lg.get("result") != "Success":
        print("\n[!] 登录失败：")
        print("result =", lg.get("result"))
        print("reason =", lg.get("reason"))
        return

    # 3) 验证登录态
    userinfo = get_user_info(session)
    print("\n=== userinfo ===")
    print(userinfo)

    # 4) 爬取新闻
    try:
        news_data = scrape_news_portal(session)
        print(f"\n[+] 成功获取 {len(news_data)} 条新闻。")
    except Exception as e:
        print(f"\n[!] 爬取新闻时发生错误: {e}")
        return

    # 5) 按照要求格式输出：序号 新闻 日期
    print("\n=== 新闻列表 ===")
    if news_data: # 检查是否有数据再打印表头
        print("序号\t新闻\t日期")
        print("-" * 120) # 增加分隔线宽度以适应更长的新闻文本
        for item in news_data:
            # 为了更好的显示，可以对过长的新闻文本进行截断或换行处理
            # 这里简单地打印出来，实际应用中可能需要更复杂的处理
            print(f"{item['index']}\t{item['news']}\t{item['date']}")
    else:
        print("未找到任何新闻。")

    # 6) 保存数据到文件和数据库
    if news_data:
        # 创建 results 文件夹
        ensure_results_dir()

        print("\n[+] 正在保存数据...")
        save_to_txt(news_data)
        save_to_json(news_data)
        save_to_csv(news_data)
        save_to_excel(news_data)

        # 保存到数据库 (可选，如果不想存数据库，可以注释掉这部分)
        try:
            db = MySQLPipeline()
            for item in news_data:
                db.process_item(item)
            db.close()
            print("已保存到 MySQL 数据库 (spider.wiki_news)。")
        except Exception as e:
            print(f"[!] 保存到数据库时发生错误: {e}")
    else:
        print("\n[-] 没有数据需要保存。")


if __name__ == "__main__":
    main()