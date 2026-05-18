import logging
import re
import time

from playwright.sync_api import Frame, Page


class OLEDPortalAdapter:
    """
    [Infrastructure Adapter]
    纯粹的底层网页/帆软报表操作适配器。
    【严格规范】：本类中绝对禁止出现任何具体业务的名称（如报表名、产品型号等）。
    """

    def __init__(self, page: Page, timeout: int = 30000):
        self.page = page  # 保存 Playwright 的 Page 对象实例
        self.default_timeout = timeout  # 统一的默认超时时间设置

        # --- 基础门户元素定位器 (固定不变的底层组件) ---
        self.SELECTOR_LOGIN_USER = "input[placeholder='用户名']"  # 登录用户名输入框
        self.SELECTOR_LOGIN_PWD = "input[placeholder='密码']"  # 登录密码输入框
        self.SELECTOR_LOGIN_BTN = "div.login-button"  # 登录按钮
        self.SELECTOR_SEARCH_ICON = "div.platform-search-font"  # 首页的搜索放大镜图标
        self.SELECTOR_SEARCH_INPUT = "input.bi-input[type='text']"  # 搜索弹窗内的文本输入框
        self.SELECTOR_CLEAR_SEARCH_BTN = "div.close-font"  # 清除搜索内容的按钮

    # ==========================================
    # 第一层：基础网页与门户操作 (Basic Web Actions)
    # ==========================================

    def navigate_to_home(self, url: str):
        """访问系统主页"""
        logging.info(f"正在访问系统: {url}")  # 记录访问动作
        self.page.goto(url)  # 执行浏览器跳转

    def login(self, username, password):
        """执行系统登录"""
        logging.info("检查是否需要登录...")  # 开始登录检查
        try:
            if self.page.is_visible(self.SELECTOR_LOGIN_USER):  # 判断登录框是否可见
                logging.info("检测到登录界面，开始自动登录...")  # 确认需要登录
                self.page.fill(self.SELECTOR_LOGIN_USER, username)  # 填入用户名
                self.page.fill(self.SELECTOR_LOGIN_PWD, password)  # 填入密码
                self.page.click(self.SELECTOR_LOGIN_BTN)  # 点击登录

                self.page.wait_for_selector(
                    self.SELECTOR_SEARCH_ICON,
                    state="visible",
                    timeout=self.default_timeout
                )  # 等待主页的搜索图标出现，作为登录成功的标志
                logging.info("登录成功。")  # 记录成功日志
            else:
                logging.info("未检测到登录框，跳过。")  # 如果已经是登录状态则跳过
        except Exception as e:
            logging.error(f"登录失败: {e}")  # 捕获并记录异常
            raise e  # 向上层抛出异常

    def search_and_enter_report(self, report_name: str, report_path: str = ""):
        """搜索并点击进入指定报表"""
        logging.info(f"准备搜索报表: {report_name}")  # 记录搜索目标

        self.page.click(self.SELECTOR_SEARCH_ICON)  # 展开搜索框
        self.page.wait_for_selector(self.SELECTOR_SEARCH_INPUT, state="visible", timeout=self.default_timeout)  # 等待输入框就绪
        self.page.fill(self.SELECTOR_SEARCH_INPUT, "")  # 清空可能的旧内容
        self.page.type(self.SELECTOR_SEARCH_INPUT, report_name, delay=100)  # 模拟人类逐字输入报表名
        self.page.wait_for_timeout(1000)  # 给予下拉联想结果加载的时间

        try:
            if report_path:  # 如果提供了精确的菜单路径
                target_report = self.page.locator("div") \
                    .filter(has_text=report_name) \
                    .filter(has_text=report_path) \
                    .last  # 通过组合条件精准定位目标
                target_report.get_by_text(report_name).click(timeout=3000)  # 点击该节点
            else:
                self.page.get_by_text(report_name).first.click(timeout=3000)  # 否则直接点击第一个匹配项

            logging.info(f"已点击报表: {report_name}")  # 记录点击成功
        except Exception as e:
            logging.error(f"无法定位报表: {report_name}。错误: {e}")  # 记录定位失败
            raise e  # 向上抛出异常

        self.page.wait_for_timeout(3000)  # 等待报表 Iframe 开始加载

    def get_active_frame(self, target_indicator: str = ".fr-trigger-texteditor") -> Frame:
        """
        [泛化] 智能获取当前激活的帆软报表 Iframe。
        通过检测 Iframe 内部是否包含帆软特有的 UI 元素来判定。
        """
        for frame in self.page.frames:  # 遍历页面上所有的 Iframe
            if frame == self.page.main_frame:
                continue  # 排除主框架本身
            try:
                if frame.frame_element().is_visible():  # 必须是肉眼可见的 Iframe
                    if frame.locator(target_indicator).count() > 0:  # 检查是否包含帆软的特征元素
                        return frame  # 返回匹配成功的 Iframe 对象
            except Exception:
                continue  # 忽略跨域或已被销毁的死 Frame

        raise Exception("未找到包含目标帆软控件的可见 Iframe。")  # 遍历完仍未找到时报错

    def wait_for_report_frame(self, timeout: int = 60000) -> Frame:
        """
        等待报表参数面板的 iframe 加载就绪（轮询 get_active_frame）。

        在点击报表后调用此方法，可以确保参数面板的 UI 元素（日期输入框等）
        已经完整渲染，避免后续操作因时序问题找不到组件。

        Args:
            timeout: 超时时间（毫秒），默认 60 秒

        Returns:
            就绪的 Frame 对象

        Raises:
            TimeoutError: 超时后仍未检测到
        """
        logging.info(f"等待报表参数面板加载（超时 {timeout}ms）...")
        deadline = time.time() + timeout / 1000
        while time.time() < deadline:
            try:
                frame = self.get_active_frame()
                logging.info("✅ 报表参数面板已就绪")
                return frame
            except Exception:
                self.page.wait_for_timeout(500)
        raise TimeoutError(f"等待报表参数面板超时（{timeout}ms）")

    # ==========================================
    # 第二层：帆软特有 UI 组件操作 (FineReport UI Actions)
    # 统一加上 fr_ 前缀以表明其专门针对帆软系统
    # ==========================================
    def fr_click_query(self):
        logging.info("点击 [查询] 按钮...")
        frame = self.get_active_frame()
        try:
            # 1. 【核心：指纹提取】点击查询前，抓取当前页面上旧报表的动态 ID 指纹
            self._old_session_suffix = None
            try:
                # 寻找包含 id 的 td 单元格 (帆软单元格格式如 id="A1-0-76348")
                old_td = frame.locator("td[id]").first
                if old_td.is_visible(timeout=500):
                    old_id = old_td.get_attribute("id") or ""
                    parts = old_id.split("-")
                    # 提取最后的动态数字后缀 (如 76348)
                    if len(parts) >= 2 and parts[-1].isdigit():
                        self._old_session_suffix = parts[-1]
                        logging.info(f"提取到旧版报表渲染指纹: {self._old_session_suffix}")
            except Exception:
                pass

            # 2. 执行查询动作
            query_btn = frame.locator("button", has_text="查询").first
            query_btn.click()
            self.page.wait_for_timeout(1000) # 给网络请求一点起步时间
        except Exception as e:
            logging.error(f"点击查询按钮失败: {e}")
            raise e

    def fr_fill_text_by_name(self, input_name: str, value: str):
        """
        [原子操作] 填写帆软基于 name 属性的普通文本框 (如：月、周)
        """
        frame = self.get_active_frame()  # 锁定目标操作区域
        try:
            input_locator = frame.locator(f"input[name='{input_name}']")  # 绝对定位 Input 元素
            input_locator.wait_for(state="visible", timeout=self.default_timeout)  # 等待其渲染可见
            input_locator.fill("")  # 清空原生内容
            input_locator.fill(str(value))  # 填入目标值
            input_locator.press("Tab")  # 必须按下 Tab 键以触发帆软内部的 onchange 事件引擎
        except Exception as e:
            logging.error(f"填写文本框 [{input_name}] 失败: {e}")  # 记录错误
            raise e

    def _get_dropdown_trigger_locator(self, frame: Frame, label_text: str):
        """
        [内部智能锚定引擎]
        核心逻辑：根据传入的中文名称，寻找其所在的容器，然后提取下一个紧挨着的下拉框容器中的按钮。
        """
        # 这是一个极其强大的 XPath 语句，完美契合您的 HTML 分析结论：
        # 1. //div[...] -> 寻找一个大 div
        # 2. .//pre[contains(@class, 'fr-label') and contains(text(), '{label_text}')] -> 里面包含对应的中文标签
        # 3. /following-sibling::div[contains(@class, 'fr-trigger-editor')][1] -> 找它下面紧挨着的第一个下拉框兄弟节点
        # 4. //div[contains(@class, 'fr-trigger-btn-up')] -> 获取这个兄弟节点里面的下拉三角按钮
        xpath = (
            f"//div[.//pre[contains(@class, 'fr-label') and contains(text(), '{label_text}')]]"
            f"/following-sibling::div[contains(@class, 'fr-trigger-editor')][1]"
            f"//div[contains(@class, 'fr-trigger-btn-up')]"
        )
        return frame.locator(xpath).first

    def fr_dropdown_select_all(self, label_text: str):
        """[原子操作] 操作帆软下拉复选框：强制设为“全选”状态"""
        frame = self.get_active_frame()
        try:
            # 1. 智能定位并展开下拉菜单
            trigger = self._get_dropdown_trigger_locator(frame, label_text)
            trigger.wait_for(state="visible", timeout=5000)
            trigger.click()
            self.page.wait_for_timeout(500)

            # 2. 【核心修复】必须寻找当前可见的 (visible) 列表框，过滤掉被帆软隐藏的历史菜单
            select_all_span = frame.locator("div.fr-checkbox-list:visible div.fr-checkbox-control span.x-text", has_text="全选/不选").first
            select_all_span.wait_for(state="visible", timeout=20000)

            # 3. 判断状态
            class_str = select_all_span.get_attribute("class") or ""
            if "fr-checkbox-checkoff" in class_str:
                select_all_span.click(force=True)

            # 4. 收起菜单
            frame.locator(f"//pre[contains(@class, 'fr-label') and contains(text(), '{label_text}')]").first.click(force=True)
            self.page.wait_for_timeout(300)

        except Exception as e:
            logging.error(f"设置下拉框 [{label_text}] 为全选失败: {e}")
            raise e

    def fr_dropdown_select_specific(self, label_text: str, target_options: list):
        """[原子操作] 操作帆软下拉复选框：清空当前选择，并精准勾选特定选项"""
        frame = self.get_active_frame()
        try:
            # 1. 智能定位并展开
            trigger = self._get_dropdown_trigger_locator(frame, label_text)
            trigger.wait_for(state="visible", timeout=5000)
            trigger.click()
            self.page.wait_for_timeout(500)

            # 2. 【核心修复】：回退至 UI 交互式重置逻辑
            # 定位“全选/不选”按钮
            select_all_span = frame.locator("div.fr-checkbox-list:visible div.fr-checkbox-control span.x-text", has_text="全选/不选").first
            select_all_span.wait_for(state="visible", timeout=3000)

            # 判断当前全选按钮的状态
            class_str = select_all_span.get_attribute("class") or ""
            if "fr-checkbox-checkon" in class_str:
                # 情况 A：如果当前已经是全选状态，单击一次即可全部清空
                select_all_span.click(force=True)
                self.page.wait_for_timeout(300)
            else:
                # 情况 B：如果是未勾选状态（可能是一片空白，也可能是部分勾选了几个）
                # 模拟双击：第一次点击强制全选，第二次点击强制全清空
                select_all_span.click(force=True)
                self.page.wait_for_timeout(300)  # 等待第一次渲染完成
                select_all_span.click(force=True)
                self.page.wait_for_timeout(300)  # 等待第二次渲染完成，此时必然全空

            # 3. 在当前可见的列表框里勾选特定目标
            for option in target_options:
                target_span = frame.locator(f"div.fr-checkbox-list:visible div.fr-combo-list-item[title='{option}'] span.x-text").first
                target_span.scroll_into_view_if_needed()

                # 如果是未勾选状态，则点击勾选
                if "fr-checkbox-checkoff" in (target_span.get_attribute("class") or ""):
                    target_span.click(force=True)

            # 4. 收起菜单
            frame.locator(f"//pre[contains(@class, 'fr-label') and contains(text(), '{label_text}')]").first.click(force=True)
            self.page.wait_for_timeout(300)

        except Exception as e:
            logging.error(f"勾选下拉框 [{label_text}] 指定选项 {target_options} 失败: {e}")
            raise e



    def fr_export_excel_original(self):
        """
        [原子操作] 执行标准帆软导出操作 (导出 -> Excel -> 原样导出 -> 忽略弹窗)
        """
        logging.info("触发 [原样导出] 流程...")  # 启动导出工作流
        try:
            frame = self.get_active_frame()  # 再次确认 Frame
            frame.locator(".x-emb-export").click()  # 点击工具栏的统一导出图标
            frame.locator("div.menu-text").filter(has_text="Excel").click()  # 悬浮展开并选择 Excel
            frame.locator("div.menu-text").filter(has_text="原样导出").click()  # 点击原样导出

            # 应对大数据量导出时出现的 "继续" 确认弹窗
            try:
                continue_btn = frame.locator("span.fr-core-btn-text", has_text="继续")  # 尝试捕获继续按钮
                if continue_btn.is_visible():  # 判断是否真的弹出了
                    continue_btn.click()  # 点击放行
            except Exception:
                pass  # 若没弹出，属正常情况，直接略过

            time.sleep(1)  # 给予底层事件发送的最终余量
        except Exception as e:
            logging.error(f"导出操作链发生异常: {e}")  # 报告导出故障
            raise e

    # ==========================================
    # 第三层：智能显式等待工具 (Wait Mechanisms)
    # ==========================================


    def fr_wait_for_specific_text(self, target_text: str, timeout: int = 120000):
        logging.info(f"等待报表数据渲染 (寻找标志性文本: '{target_text}')...")
        frame = self.get_active_frame()
        try:
            # 3. 【核心：指纹校验】如果有旧指纹，使用 XPath 过滤掉包含该指纹的旧节点
            if getattr(self, "_old_session_suffix", None):
                old_suffix = self._old_session_suffix
                logging.info(f"启用防假死指纹校验，排查旧指纹: {old_suffix}")

                # 强大的 XPath：寻找包含该文本的 td，且它的 id 不能包含旧指纹
                # xpath 中的 `.` 代表该节点内的所有文本，这能完美兼容嵌套标签
                xpath = f"//td[contains(., '{target_text}') and not(contains(@id, '-{old_suffix}'))]"
                element = frame.locator(xpath).first
            else:
                element = frame.get_by_text(target_text).first

            element.wait_for(state="visible", timeout=timeout)
            self.page.wait_for_timeout(1000) # 渲染稳定缓冲

            # 使用完毕后清空指纹，避免污染下一次独立等待
            self._old_session_suffix = None
        except Exception as e:
            logging.error(f"等待特征文本 '{target_text}' 加载超时: {e}")
            raise e

    def fr_wait_for_report_ready(self, timeout: int = 120000):
        """通用结构等待（兜底策略）的指纹校验版"""
        logging.info("等待报表数据渲染 (检测通用 heavytd 结构)...")
        frame = self.get_active_frame()
        try:
            if getattr(self, "_old_session_suffix", None):
                old_suffix = self._old_session_suffix
                logging.info(f"启用防假死指纹校验，排查旧指纹: {old_suffix}")
                # 寻找新的带有 id 的 td，其 id 必须不包含旧指纹
                xpath = f"//td[contains(@id, '-') and not(contains(@id, '-{old_suffix}'))]"
                element = frame.locator(xpath).first
            else:
                element = frame.locator("div[heavytd]").first

            element.wait_for(state="visible", timeout=timeout)
            self.page.wait_for_timeout(1000)

            self._old_session_suffix = None
        except Exception as e:
            logging.error(f"等待报表通用结构加载超时: {e}")
            raise e

    def fr_fill_date_by_label(self, label_text: str, date_str: str):
        """
        [原子操作] 智能操作帆软日期选择器（输入法）
        根据标签文本寻找紧邻的日期输入框，并强校验输入格式。

        :param label_text: 标签文本，如 "结束日期:"
        :param date_str: 日期字符串，必须严格符合 "YYYY-MM-DD" 格式
        """
        # 1. 严格校验日期格式防呆（防止业务层传错格式导致帆软系统报错）
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            raise ValueError(f"⚠️ 日期参数错误: '{date_str}' 不符合 'YYYY-MM-DD' 格式要求！")

        frame = self.get_active_frame()
        try:
            # 2. 多级 XPath 策略智能锚定日期输入框
            # 策略一（原版）：div[含pre.label] → following-sibling div.fr-trigger-editor → input
            xpath_v1 = (
                f"//div[.//pre[contains(@class, 'fr-label') and contains(text(), '{label_text}')]]"
                f"/following-sibling::div[contains(@class, 'fr-trigger-editor')][1]"
                f"//input[contains(@class, 'fr-trigger-texteditor') or @type='text']"
            )
            # 策略二：直接找 label → following input（兼容 table/tr/td 布局，label 在 input 之前）
            xpath_v2 = (
                f"//pre[contains(@class, 'fr-label') and contains(text(), '{label_text}')]"
                f"/following::input[contains(@class, 'fr-trigger-texteditor')][1]"
            )
            # 策略三：label 可能在 span/div 中 → 向上找 fr-trigger-editor 容器 → 向下找 input
            xpath_v3 = (
                f"//*[contains(@class, 'fr-label') and contains(text(), '{label_text}')]"
                f"/ancestor::div[contains(@class, 'fr-trigger-editor')]"
                f"//input"
            )
            # 策略四：找 input，其最近的 preceding *[fr-label] 包含 label_text
            # ✅ 智能规避：产品型号等非目标 input 的最近 preceding fr-label 不匹配 label_text
            xpath_v4 = (
                f"//input[contains(@class, 'fr-trigger-texteditor')]"
                f"[preceding::*[contains(@class, 'fr-label')][1]"
                f"  [contains(text(), '{label_text}')]]"
            )
            # 策略五：label 可能在任意元素中 → 在相同 <tr> 容器中找 input
            # 兼容 input 在 label 前/后的 table 布局
            xpath_v5 = (
                f"//*[contains(text(), '{label_text}')]"
                f"/ancestor::tr[1]"
                f"//input[contains(@class, 'fr-trigger-texteditor')]"
            )
            # 策略六：极端兜底 — "结束"取最后一个 input，"开始"取第一个
            # 因为参数面板通常按 [开始日期 input] [结束日期 input] [产品型号 filter] 排列
            if "结束" in label_text:
                xpath_v6 = "//input[contains(@class, 'fr-trigger-texteditor')]"
            else:
                xpath_v6 = "(//input[contains(@class, 'fr-trigger-texteditor')])[1]"

            date_input = None
            last_error = None
            strategies = [(xpath_v1, 1), (xpath_v2, 2), (xpath_v3, 3),
                          (xpath_v4, 4), (xpath_v5, 5), (xpath_v6, 6)]
            for xpath, idx in strategies:
                try:
                    if idx == 6 and "结束" in label_text:
                        # 策略六的特殊处理：结束日期取最后一个
                        candidate = frame.locator(xpath).last
                    else:
                        candidate = frame.locator(xpath).first
                    candidate.wait_for(state="visible", timeout=3000)
                    date_input = candidate
                    logging.info(f"  XPath 策略 {idx} 匹配成功")
                    break
                except Exception as e:
                    last_error = e
                    continue

            if date_input is None:
                raise Exception(
                    f"所有 XPath 策略均未能定位日期组件 [{label_text}]。最后错误: {last_error}"
                )

            # 3. 交互执行
            date_input.click()         # 先点击激活输入框
            date_input.fill("")        # 强行清空里面的旧日期
            date_input.fill(date_str)  # 填入严格格式化后的新日期

            # 4. 触发底层引擎校验
            # 极其重要：帆软的日期组件在填完文本后，必须按 Enter 或 Tab 才能触发它内部的 JS 校验并更新绑定的变量
            date_input.press("Enter")
            self.page.wait_for_timeout(300)  # 给 JS 引擎一点点缓冲时间

            logging.info(f"✅ 成功将日期组件 [{label_text}] 设置为: {date_str}")

        except Exception as e:
            logging.error(f"设置日期组件 [{label_text}] 失败: {e}")
            raise e

    def reset_search_state(self):
        """重置主框架的搜索栏状态"""
        try:
            if self.page.is_visible(self.SELECTOR_CLEAR_SEARCH_BTN):  # 检测是否有清空按钮（X图标）
                self.page.click(self.SELECTOR_CLEAR_SEARCH_BTN)  # 点击清空搜索词
                self.page.wait_for_selector(self.SELECTOR_SEARCH_ICON, state="visible", timeout=3000)  # 确保重置完成
        except Exception:
            pass  # 无关紧要的清理操作，失败也不应阻塞主流程
