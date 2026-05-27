import requests
import re
import os
import pandas as pd
from bs4 import BeautifulSoup

# ==========================================
# ⚙️ 核心配置中心
# ==========================================
# 绕过内网代理
os.environ['NO_PROXY'] = '10.73.17.76'
host = "http://10.73.17.76:8080"

# 1. 登录配置 (保持原样即可，除非你修改了密码)
LOGIN_PAYLOAD = {
    "username": "V0141351",
    "password": "PnM59pIOFbEAzj5pq7YYPA==",
    "validity": -1,
    "sliderToken": "",
    "origin": "",
    "encrypted": True
}

# 2. 目标报表的访问入口 URL（从成功请求中提取的 entry/access 链接）
ENTRY_ACCESS_URL = f"{host}/webroot/decision/v10/entry/access/22ce8bfb-620c-485f-a521-2fae23f53b63"

# 3. 筛选条件配置
#   - 参数名: cmcbEQPID（控件名，必须用 form-data 方式提交）
#   - 可用值: 3TED01 ~ 3TED08（参考 widget 查询结果）
FILTER_PARAM = "cmcbEQPID"  # 筛选参数名（控件 widgetName）
FILTER_VALUE = "3TED01"     # 筛选值

# 全局基础请求头
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest"
}

# 实例化 Session (它会自动帮我们在各个请求之间传递 Cookie 和 Token)
client = requests.Session()

def main():
    print("=============================================")
    print("🤖 帆软报表全自动抓取引擎 v1.0 启动")
    print("=============================================\n")

    try:
        # ================= 第一步：自动登录获取 Token =================
        print("🚀 [1/4] 正在执行自动登录...")
        login_url = f"{host}/webroot/decision/login"
        
        # 发送 POST 请求进行登录 (注意帆软用的是 json 格式传递 payload)
        response_login = client.post(login_url, json=LOGIN_PAYLOAD, headers=headers, timeout=15)
        
        if response_login.status_code == 200:
            # 登录成功，token 在 JSON 响应体的 data.accessToken 字段中（而非 Cookie）
            login_data = response_login.json()
            auth_token = login_data.get("data", {}).get("accessToken")
            
            if not auth_token:
                print(f"❌ 登录可能失败：服务器返回 200，但 JSON 响应中缺少 data.accessToken。")
                print(f"   响应内容预览: {response_login.text[:500]}")
                return
                
            print(f"🔑 登录成功！已获取最新 Token: {auth_token[:15]}...")
            
            # 将最新的 Token 注入到全局 Header 中，供后续请求使用
            headers["Authorization"] = f"Bearer {auth_token}"
            
            # ⚠️ 帆软同时依赖 Cookie 中的 fine_auth_token（参考 PowerShell 成功请求）
            client.cookies.set("fine_auth_token", auth_token, domain="10.73.17.76", path="/")
            
        else:
            print(f"❌ 登录请求失败，状态码: {response_login.status_code}")
            return


        # ================= 第二步：初始化报表获取 sessionID =================
        print("\n🚀 [2/4] 正在初始化目标报表，抓取底层 sessionID...")
        response_init = client.get(ENTRY_ACCESS_URL, headers=headers, timeout=15)
        
        if response_init.status_code == 200:
            # 使用正则精准提取
            id_pattern = r"FR\.SessionMgr\.register\(['\"]([a-f0-9\-]{36})['\"]"
            match = re.search(id_pattern, response_init.text)
            
            if match:
                dynamic_session_id = match.group(1)
                print(f"🎯 成功捕获会话 ID: {dynamic_session_id}")
            else:
                print("❌ 提取失败：未在报表页面中找到 FR.SessionMgr.register 标识。")
                return
        else:
            print(f"❌ 报表初始化失败，状态码: {response_init.status_code}")
            return


        # ================= 第三步：设置筛选条件（设备筛选） =================
        print("\n🚀 [3/4] 正在设置筛选条件...")
        
        # 准备带 sessionID 的请求头（parameters_d 和 page_content 都需要）
        data_headers = headers.copy()
        data_headers["sessionID"] = dynamic_session_id
        
        params_url = f"{host}/webroot/decision/view/report?op=fr_dialog&cmd=parameters_d&sessionID={dynamic_session_id}"
        
        # ⚠️ 必须用 form-data (data=) 而非 JSON (json=)，parameters_d 端点只认 form-data
        response_param = client.post(
            params_url,
            headers=data_headers,  # ⚠️ 必须带 sessionID Header
            data={FILTER_PARAM: FILTER_VALUE},
            timeout=15
        )
        
        if response_param.status_code == 200:
            print(f"✅ 筛选条件已设置: {FILTER_PARAM}={FILTER_VALUE}")
        else:
            print(f"⚠️ 筛选条件设置返回异常状态码: {response_param.status_code}")


        # ================= 第四步：请求筛选后的报表数据并清洗为 CSV =================
        print("\n🚀 [4/4] 正在请求筛选后的底层表格数据...")
        data_url = f"{host}/webroot/decision/view/report?op=page_content&pn=1&sessionID={dynamic_session_id}"
        
        # 这里复用上面已定义的 data_headers（含 sessionID）
        
        response_data = client.get(data_url, headers=data_headers, timeout=20)
        
        if response_data.status_code == 200:
            print("✅ 成功获取 JSON 数据包，正在清洗 HTML 表格...")
            html_content = response_data.json().get("html", "")
            
            if html_content:
                soup = BeautifulSoup(html_content, "html.parser")
                table = soup.find('table', class_='x-table')
                
                if table:
                    parsed_data = []
                    for row in table.find_all('tr'):
                        row_data = [td.get_text(strip=True) for td in row.find_all('td')]
                        if any(cell != "" for cell in row_data):  # 过滤纯空行
                            parsed_data.append(row_data)
                    
                    if parsed_data:
                        file_name = "帆软自动报表_终极版.csv"
                        df = pd.DataFrame(parsed_data)
                        df.to_csv(file_name, index=False, header=False, encoding='utf-8-sig')
                        print(f"\n🎉【完美收官】无人值守抓取成功！共提取 {len(parsed_data)} 行数据。")
                        print(f"📁 文件已保存至: {file_name}")
                    else:
                        print("⚠️ 解析到了表格，但没有文字内容。")
                else:
                    print("❌ HTML 中未找到 class='x-table' 的表格标签。")
            else:
                print("❌ 服务器返回的 JSON 中缺少 'html' 字段。")
        else:
            print(f"❌ 数据请求失败，状态码: {response_data.status_code}")

    except Exception as e:
        print(f"\n⚠️ 发生不可预料的系统错误: {e}")

if __name__ == "__main__":
    main()
