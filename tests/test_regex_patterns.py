#%%
# tests/test_regex_fix.py
import re

def test_regex_patterns():
    """测试正则表达式替换"""
    
    # 测试用例 (我增加了一个带 \r\n 和空格的复杂用例)
    test_cases = [
        "1、当日异常\n\n\n\n",                 # 1. 多个 \n
        "1、当日异常\n\n",                     # 2. 两个 \n
        "1、当日异常\n无\n",                   # 3. 已有内容 (不应匹配)
        "2、各工厂还原时序\n\n\n\n",           # 4. 多个 \n
        "2、各工厂还原时序\n\n",               # 5. 两个 \n
        "2、各工厂还原时序\n无\n",             # 6. 已有内容 (不应匹配)
        "1、当日异常\n",                       # 7. 只有一个 \n (不应匹配)
        "1、当日异常\r\n \r\n   \r\n"        # 8. 复杂的Windows空白行 (健壮性测试)
    ]
    
    # 测试不同的替换方案
    patterns = [
        {
            'name': '方案1：使用非捕获组 (修正版)',
            'pattern1': r'1、当日异常\n(?:\n+)',
            'repl1': r'1、当日异常\n无\n', # <--- 已修正
            'pattern2': r'2、各工厂还原时序\n(?:\n+)',
            'repl2': r'2、各工厂还原时序\n无\n' # <--- 已修正
        },
        {
            'name': '方案2：使用捕获组 (健壮版)',
            'pattern1': r'(1、当日异常)((?:[ \t]*\r?\n){2,})',
            'repl1': r'\1\n无\n',
            'pattern2': r'(2、各工厂还原时序)((?:[ \t]*\r?\n){2,})',
            'repl2': r'\1\n无\n'
        }
    ]

    
    for i, scheme in enumerate(patterns):
        print(f"\n方案 {i+1}: {scheme['name']}")
        for j, text in enumerate(test_cases):
            try:
                # 确保两个模式都被应用
                result1 = re.sub(scheme['pattern1'], scheme['repl1'], text)
                result2 = re.sub(scheme['pattern2'], scheme['repl2'], result1)
                print(f"  测试{j+1}: {repr(text)} -> {repr(result2)}")
            except Exception as e:
                print(f"  测试{j+1}: {repr(text)} -> 错误: {e}")


if __name__ == '__main__':
    test_regex_patterns()

# %%