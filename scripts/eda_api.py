import requests
import re
import os
from bs4 import BeautifulSoup

# ==========================================
# ⚙️ 爬虫配置中心 (未来修改只需动这里)
# ==========================================
TARGET_IP = "10.73.17.79"
TARGET_PORT = "8087"

# 1. 目标分类名称 (只下载该分类下的数据)
TARGET_CATEGORY = "Array RS Inline Monitor"

# 2. 登录加密数据包 (如果你换了账号密码，或邮件发来了新任务链接，请重新抓包替换这里)
# 注意：一定要包含最后的 forwardStr 等所有参数
CURRENT_PAYLOAD = "username=avNIUQu5YzSrPT85klmRaVTB3%2Fs7XbYC%2FuRG0jCPrZf5X9LXYC5aNeKOaPtzUHk1mcgE7%2Fedasr7MStFxQfd5PnnQCPYwDi2KHwNZs1K9NUzUPMy5tdgOOSeCxgolO2DyC4e4LIyrWvOcuixJWt6b5QuVCxRtYOVzMegHpRFmp8%3D&password=h43XZDuE%2Blm4EJoPMO%2F5MxrAdlgL6RALHJnyKZHdHhLVomugbgwalUYs0Oy%2FZ%2FWD6HmMddSrp7VSZJMWG4Kr7cc9pIot4PXucmp5njWajfG7nCwUgmVZShY3v4XLOfdlK3murDIW1KFPjQc9VBmm%2FzFbaPaQTzwHiAfz%2BWjoflc%3D&Login=&linkSource=MAIL&resultSessionID=E02182711BC452E7F5E0083D05E7FF24&forwardStr=%2Fedatool%2Fschedule%2FviewjobHistory_main.do%3Bjsession%3D484EAFFE4217A6D8B4D5EE995090CE32%3Fmode%3Djob_summary%26jobNo%3D26704%26sessionID%3DE02182711BC452E7F5E0083D05E7FF24%26from%3Dmyfavorite%26myfavorJobName%3DArray%2520Inline%2520RS%2520Monitor%2520_V3.0%26LINK_SOURCE%3DMAIL%26location%3Djob_summary&resultType=&relResultPath="

# ==========================================
# 🤖 核心爬虫引擎 (无需修改)
# ==========================================
# 告诉系统遇到内网 IP 绕过代理
os.environ['NO_PROXY'] = TARGET_IP

host = f"http://{TARGET_IP}:{TARGET_PORT}"
login_url = f"{host}/EDA/logon.do"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded"
}

# 创建会话对象，自动管理 Cookie 和 Token
client = requests.Session()

try:
    print("🚀 [1/3] 正在发送密文，执行自动登录...")
    # allow_redirects=False 拦截 302 重定向
    response_login = client.post(login_url, headers=headers, data=CURRENT_PAYLOAD, allow_redirects=False, timeout=15)

    if response_login.status_code == 302:
        redirect_path = response_login.headers.get('Location')
        next_url = host + redirect_path
        print(f"✅ 登录成功！准备跳转至任务面板。")

        # 提取动态生成的 jsessionid 和 sessionID
        jsessionid_match = re.search(r'jsessionid=([^?&]+)', redirect_path)
        session_id_match = re.search(r'sessionID=([^?&]+)', redirect_path)
        
        current_jsessionid = jsessionid_match.group(1) if jsessionid_match else ""
        current_session_id = session_id_match.group(1) if session_id_match else ""

        print(f"🔑 成功提取动态令牌! jsessionid: {current_jsessionid[:8]}...")
        print(f"📂 当前任务 ID: {current_session_id}")

        print("\n🚀 [2/3] 正在读取网页，并使用 BeautifulSoup 精准解析 DOM 树...")
        response_html = client.get(next_url, headers=headers, timeout=15)
        
        if response_html.status_code == 200:
            html_text = response_html.text
            soup = BeautifulSoup(html_text, "html.parser")
            
            # 1. 寻找所有的分类标题 (<p class="outputName">)
            target_title_p = None
            for p in soup.find_all('p', class_='outputName'):
                if TARGET_CATEGORY in p.get_text():
                    target_title_p = p
                    break

            if target_title_p:
                print(f"🎯 成功定位目标分类: [{TARGET_CATEGORY}]")
                
                # 2. 找到紧挨着这个标题的图片容器 (<div class="scroll">)
                scroll_container = target_title_p.find_next_sibling('div', class_='scroll')
                
                if scroll_container:
                    images = scroll_container.find_all('img')
                    print(f"📦 在该分类下共发现 {len(images)} 张图片")
                    
                    dynamic_paths = []
                    
                    # 3. 提取所有图片的动态路径
                    for img in images:
                        img_src = img.get('src', '')
                        # 从 src 提取我们需要的 data_时间戳 文件夹路径
                        match = re.search(rf"/schedule/{current_session_id}/([A-Z0-9_]+/data_\d+_\d+)", img_src)
                        if match:
                            path = match.group(1)
                            if path not in dynamic_paths:
                                dynamic_paths.append(path)
                    
                    print(f"✅ 最终解析出 {len(dynamic_paths)} 个独立的数据文件路径！")
                    
                    # ================= 3. 批量下载 CSV =================
                    print("\n🚀 [3/3] 开始批量下载数据...")
                    
                    for idx, dynamic_path in enumerate(dynamic_paths, start=1):
                        download_url = f"{host}/EDA/commons/ia/export_data.do;jsessionid={current_jsessionid}?REL_IA_CONFIG_FILE_PATH=schedule/{current_session_id}/{dynamic_path}/ia_config.properties"
                        
                        response_csv = client.get(download_url, headers=headers, timeout=15)
                        
                        if response_csv.status_code == 200:
                            # 提取时间戳部分作为文件名后缀
                            folder_name = dynamic_path.split('/')[-1]
                            file_name = f"output\\eda\\[{TARGET_CATEGORY}]_{idx}_{folder_name}.csv"
                            
                            with open(file_name, "wb") as f:
                                f.write(response_csv.content)
                            print(f"  📥 成功下载 ({idx}/{len(dynamic_paths)}): {file_name}")
                        else:
                            print(f"  ❌ 下载失败 ({idx}/{len(dynamic_paths)}): HTTP {response_csv.status_code}")
                            
                    print("\n🎉【完美收官】目标分类下的所有数据已全部自动化保存完毕！")

                else:
                    print(f"❌ 解析失败：找到了 [{TARGET_CATEGORY}] 标题，但没有找到包裹图片的容器。")
            else:
                print(f"❌ 定位失败：在网页中没有找到名为 '{TARGET_CATEGORY}' 的分类。")
        else:
            print(f"❌ 访问图表页面失败，状态码: {response_html.status_code}")
    else:
        print(f"❌ 登录失败！服务器拒绝重放攻击或加密包已失效，状态码: {response_login.status_code}")

except Exception as e:
    print(f"⚠️ 发生不可预料的网络或执行错误: {e}")
