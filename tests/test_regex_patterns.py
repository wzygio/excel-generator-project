#%%
# tests/test_regex_patterns.py
import re

def test_patterns():
    # 测试用例
    test_cases = [
        "1、当日异常\n\n\n\n",
        "1、当日异常\n\n",
        "1、当日异常\n无\n",
        "2、各工厂还原时序\n\n\n",
        "2、各工厂还原时序\n无\n",
    ]

    # 测试当前的正则表达式
    pattern1 = r'(1、当日异常\n)\n+'
    replacement1 = r'\1无\n'
    
    pattern2 = r'(2、各工厂还原时序\n)\n+'
    replacement2 = r'\1无\n'

    print("测试当前正则表达式：")
    for text in test_cases:
        result1 = re.sub(pattern1, replacement1, text)
        result2 = re.sub(pattern2, replacement2, result1)
        print(f"原文：{repr(text)}")
        print(f"结果：{repr(result2)}")
        print("-" * 50)

if __name__ == '__main__':
    test_patterns()
