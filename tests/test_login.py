import requests
import os

# 屏蔽内网代理
os.environ['NO_PROXY'] = '10.73.17.79' 

# 1. 创建一个“会话(Session)”对象
# Session 的魔力在于：它会自动帮你保管服务器发来的 Cookie 和 jsessionid，
# 就像真正的浏览器一样，后续的请求它会自动带上通行证！
client = requests.Session()

# 2. 登录的 API 地址 (注意去掉了后面的 jsessionid，让服务器重新给我们发一个)
login_url = "http://10.73.17.79:8087/EDA/logon.do"

# 3. 伪装头
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded"
}

# 4. 把你抓到的加密乱码原封不动地复制过来！(注意核对)
# 这里的 forwardStr 包含了你邮件里那个任务的最终跳转地址
payload = "username=avNIUQu5YzSrPT85klmRaVTB3%2Fs7XbYC%2FuRG0jCPrZf5X9LXYC5aNeKOaPtzUHk1mcgE7%2Fedasr7MStFxQfd5PnnQCPYwDi2KHwNZs1K9NUzUPMy5tdgOOSeCxgolO2DyC4e4LIyrWvOcuixJWt6b5QuVCxRtYOVzMegHpRFmp8%3D&password=h43XZDuE%2Blm4EJoPMO%2F5MxrAdlgL6RALHJnyKZHdHhLVomugbgwalUYs0Oy%2FZ%2FWD6HmMddSrp7VSZJMWG4Kr7cc9pIot4PXucmp5njWajfG7nCwUgmVZShY3v4XLOfdlK3murDIW1KFPjQc9VBmm%2FzFbaPaQTzwHiAfz%2BWjoflc%3D&Login=&linkSource=MAIL&resultSessionID=E02182711BC452E7F5E0083D05E7FF24&forwardStr=%2Fedatool%2Fschedule%2FviewjobHistory_main.do%3Bjsession%3D484EAFFE4217A6D8B4D5EE995090CE32%3Fmode%3Djob_summary%26jobNo%3D26704%26sessionID%3DE02182711BC452E7F5E0083D05E7FF24%26from%3Dmyfavorite%26myfavorJobName%3DArray%2520Inline%2520RS%2520Monitor%2520_V3.0%26LINK_SOURCE%3DMAIL%26location%3Djob_summary&resultType=&relResultPath="

print("尝试使用静态密文进行登录...")

# 5. 发送登录请求 (POST)
# allow_redirects=False 的意思是：如果登录成功，服务器通常会返回 302 跳转到首页。
# 我们拦截这个跳转，看看状态码是不是 302，来判断登录是否成功。
response = client.post(login_url, headers=headers, data=payload, allow_redirects=False, proxies={"http": None, "https": None, 'socks5': None })

if response.status_code == 302:
    print("🎉 恭喜！重放攻击成功！服务器接受了静态密文，你已经成功登录！")
    print(f"服务器指引我们跳转到了: {response.headers.get('Location')}")
    # 到这里，client 对象里就已经装满了 jsessionid，可以直接复用我们上一步的代码去抓图表了！
elif response.status_code == 200:
    print("❌ 登录失败。返回了 200 状态码，通常意味着账号密码错误，或者系统识破了旧的密文，让我们重新留在登录页。")
else:
    print(f"⚠️ 出现其他状态码: {response.status_code}")