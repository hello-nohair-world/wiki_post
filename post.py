# -*- coding: utf-8 -*-
"""
功能：使用 POST 方式登录中文维基百科（MediaWiki API：clientlogin）
步骤：
1) GET 获取 login token
2) POST 提交 username/password/logintoken
3) GET 查询 userinfo 验证是否登录成功
"""

import requests
from urllib.parse import urljoin


# =========================
# 1) 基础配置
# =========================
BASE_URL = "https://zh.wikipedia.org/"
API_URL = urljoin(BASE_URL, "w/api.php")

USERNAME = "YourUserName"
PASSWORD = "YourPassport"
RETURN_URL = "https://zh.wikipedia.org/wiki/Main_Page"


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
# 3) POST 登录（clientlogin）
# =========================
def client_login(session: requests.Session, username: str, password: str) -> dict:
    logintoken = get_login_token(session)

    data = {
        "action": "clientlogin",
        "format": "json",
        "username": username,
        "password": password,
        "logintoken": logintoken,
        "loginreturnurl": RETURN_URL,
        "rememberMe": "1",
    }

    # 注意：这里就是你要练习的 POST
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
    })

    # 1) 登录
    login_result = client_login(session, USERNAME, PASSWORD)
    print("=== login_result ===")
    print(login_result)

    # 2) 判断登录结果
    cl = login_result.get("clientlogin", {})
    status = cl.get("status")
    if status != "PASS":
        print("\n[!] 登录失败：")
        print("status =", status)
        print("message =", cl.get("message"))
        print("reason  =", cl.get("reason"))
        return

    # 3) 验证登录态
    userinfo = get_user_info(session)
    print("\n=== userinfo ===")
    print(userinfo)

    # 4) 你可以在这里继续做“登录后操作”
    #    例如：访问需要登录的页面、查询 watchlist（权限相关）、后续编辑（需CSRF token）等。


if __name__ == "__main__":
    main()
