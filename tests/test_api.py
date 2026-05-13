import requests

# 1. 目标 API 地址 (包含你的会话ID和文件路径)
url = "http://10.73.17.79:8087/EDA/commons/ia/export_data.do;jsessionid=FB9716F84C248DD84B047C15E882A0B6?REL_IA_CONFIG_FILE_PATH=schedule/E02182711BC452E7F5E0083D05E7FF24/073_DEFAULT_TREND/data_1778629727945_2/ia_config.properties"

# 2. 伪装头 (让服务器认为这是你通过 Chrome 浏览器发出的请求)
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": "http://10.73.17.79:8087/EDA/edatool3/chart/d3BigChart.jsp;jsessionid=FB9716F84C248DD84B047C15E882A0B6?from=chartlist&chartType=DEFAULT_TREND",
    "Upgrade-Insecure-Requests": "1"
}

print("正在向服务器发送请求，请稍候...")

# 3. 发送 GET 请求
try:
    # 注意：因为是内网IP，可能不需要代理。如果你开了代理软件(如Clash)，这里可能会报错，
    # 可以通过添加 proxies={"http": None, "https": None} 来绕过代理直连内网。
    response = requests.get(url, headers=headers, timeout=15, proxies={"http": None, "https": None, 'socks5': None })
    
    # 4. 检查是否成功 (HTTP 状态码 200 表示成功)
    if response.status_code == 200:
        # 将返回的二进制内容保存为 CSV 文件
        file_name = "output\\自动下载的图表数据.csv"
        with open(file_name, "wb") as f:
            f.write(response.content)
        print(f"🎉 成功！数据已保存至当前目录下的: {file_name}")
    else:
        print(f"❌ 下载失败！服务器返回状态码: {response.status_code}")
        print("错误信息:", response.text[:200]) # 打印前200个字符的错误提示

except Exception as e:
    print(f"❌ 发生网络错误: {e}")