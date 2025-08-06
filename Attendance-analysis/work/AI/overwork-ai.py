import requests
import json

# API 端点地址
url = "http://192.168.1.66/v1/chat-messages"

# 请求头
headers = {
    "Authorization": "Bearer app-G55syWxYqxnoOH2jOsskKMA6",
    "Content-Type": "application/json"
}

# 请求体内容
payload = {
    "inputs": {},
    "query": "1.EA5000N118装配，EOL测试，终处理，共27人   1.高群，王松，李飞，王能武，王星，刘杰，沈洋，田磊，刘成香，刘登，李炎炎，陈威，余东明，王洋，孙盼，林超，曹博文，高星，席智成，魏权，刘贤杰，万俊杰，叶成，李明，怀雄，刘卫宜，张磊磊   06：00-08：30",
    "user": "abc-123"
}

try:
    # 发起 POST 请求
    response = requests.post(url, headers=headers, data=json.dumps(payload))

    # 检查响应状态码
    if response.status_code == 200:
        print("✅ 请求成功！返回结果如下：")
        print(response.json())
    else:
        print(f"❌ 请求失败，状态码：{response.status_code}")
        print("响应内容：", response.text)

except requests.exceptions.RequestException as e:
    print("⚠️ 请求异常：", str(e))
