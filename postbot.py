# -*- coding: utf-8 -*-
"""
功能：使用 POST 方式登录中文维基百科（BotPasswords 推荐：action=login）
步骤：
1) GET 获取 login token（type=login）
2) POST 提交 lgname/lgpassword/lgtoken（action=login）
3) GET 查询 userinfo 验证是否登录成功
"""

import requests
from urllib.parse import urljoin


# =========================
# 1) 基础配置
# =========================
BASE_URL = "https://zh.wikipedia.org/"
API_URL = urljoin(BASE_URL, "w/api.php")

# 机器人账号：主账号@机器人名
USERNAME = "YourUserName@YourBotUsername"
# 机器人密码：Special:BotPasswords
PASSWORD = "yourBotPassword"

RETURN_URL = "https://zh.wikipedia.org/wiki/Main_Page"  # 保留不影响（本流程不强依赖）


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

    # 4) 你可以在这里继续做“登录后操作”
    #    例如：获取 CSRF token 后编辑沙盒、查看 watchlist 等。


if __name__ == "__main__":
    main()
