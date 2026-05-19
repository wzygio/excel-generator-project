import time
import base64
import hashlib
import json
import requests

# ================= 1. 基础配置信息 =================
# 注意：以下两个参数必须向 vivo 的对接人索要获取
INVOKER_NAME = "填写vivo提供的invokerName"
APP_SECRET = "填写vivo提供的secret"

# 测试环境 URL
URL = "https://cmpdev.vivo.xyz:8083/gw-api/cmp/oled/processData/push"

# ================= 2. 准备请求数据 =================
# 这里以发送 oledData 为例
payload = {
    "type": "oledData",
    "oledDataList": [
        {
            "date": "2025-12-19",
            "materialCode": "0090001",
            "dailyInputCount": "1000",
            "defectName": "boe缺陷名称1",
            "defectCount": "10",
            "defectRate": "1%"
        }
    ]
}

# 将字典转换为 JSON 字符串 (去除多余空格以确保和哈希值计算一致)
body_str = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))

# ================= 3. 核心：生成签名 =================
# 3.1 获取当前毫秒级时间戳
timestamp = str(int(time.time() * 1000))

# 3.2 对 invokerName 进行 Base64 编码
invoker_name_encoded = base64.b64encode(INVOKER_NAME.encode('utf-8')).decode('utf-8')

# 3.3 计算 SHA256 (appSecret + timestamp + body)
raw_str_for_hash = APP_SECRET + timestamp + body_str
body_encoded = hashlib.sha256(raw_str_for_hash.encode('utf-8')).hexdigest()

# 3.4 拼接最终的 gwSignature
join_mark = "@#"
gw_signature = f"{invoker_name_encoded}{join_mark}{timestamp}{join_mark}{body_encoded}"

print(">>> 生成的 Signature:", gw_signature)

# ================= 4. 发送网络请求 =================
headers = {
    "Content-Type": "application/json",
    "gwSignature": gw_signature
}

try:
    # verify=False 忽略 SSL 证书校验，测试环境通常需要加上
    response = requests.post(URL, headers=headers, data=body_str.encode('utf-8'), verify=False)
    print(">>> 响应状态码:", response.status_code)
    print(">>> 响应内容:", response.text)
    
    # 成功判断逻辑：文档指出 code 为 0 代表成功
    if response.json().get("code") == 0:
        print("✅ 数据推送成功！")
    else:
        print("❌ 数据推送失败，错误信息:", response.json().get("message"))
        
except requests.exceptions.ConnectionError:
    print("❌ 网络连接失败：请检查服务器是否能够访问 cmpdev.vivo.xyz 域名，或联系 vivo 添加 IP 白名单。")