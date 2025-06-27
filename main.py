import httpx
import base64
from datetime import datetime, timezone
from collections import defaultdict

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig

from .constants import HTML_TEMPLATE


@register(
    "astrbot_plugin_github_analyzer",
    "lxfight",
    "https://github.com/lxfight/astrabot_plugin_github_analyzer",
    "1.0.0",
)
class GithubAnalyzerPlugin(Star):
    # 插件初始化函数，在插件加载时执行
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.http_client = httpx.AsyncClient()
        logger.info("GitHub 分析插件已加载。")

    async def terminate(self):
        await self.http_client.aclose()
        logger.info("GitHub 分析插件已卸载，HTTP 客户端已关闭。")

    @filter.command("gh_analyze")
    async def analyze_command(
        self, event: AstrMessageEvent, username: str, arg1: str = None, arg2: str = None
    ):
        try:
            token = self.config.get("github_token")
            if not token:
                yield event.plain_result("错误：未在插件配置中设置 GitHub Token。")
                return

            # 根据传入参数确定日期范围
            try:
                if arg1 is None and arg2 is None:
                    # Case 1: gh_analyze <user> -> 默认最近N天
                    start_day = self.config.get("lookback_days", 7)
                    end_day = 0
                elif arg2 is None:
                    # Case 2: gh_analyze <user> N -> 最近N天
                    start_day = int(arg1)
                    end_day = 0
                else:
                    # Case 3: gh_analyze <user> A B -> A天前到B天前
                    start_day = int(arg1)
                    end_day = int(arg2)

                if not 0 <= end_day < start_day:
                    yield event.plain_result(
                        "❌ 参数错误：日期范围无效。请确保起始天数大于截止天数，且均为非负数。"
                    )
                    return
            except (ValueError, TypeError):
                yield event.plain_result("❌ 参数错误：天数必须为有效的整数。")
                return

            # 更新提示信息
            if end_day == 0:
                yield event.plain_result(
                    f"正在分析用户 {username} 最近 {start_day} 天的活动，请稍候..."
                )
            else:
                yield event.plain_result(
                    f"正在分析用户 {username} 从 {start_day} 天前到 {end_day} 天前的活动，请稍候..."
                )

            render_payload = await self._analyze_and_prepare_data(
                username, token, start_day, end_day
            )

            if render_payload:
                image_url = await self.html_render(HTML_TEMPLATE, render_payload)
                yield event.image_result(image_url)
            else:
                if end_day == 0:
                    yield event.plain_result(
                        f"⚠️ 在最近 {start_day} 天内没有找到用户 {username} 的公开活动。"
                    )
                else:
                    yield event.plain_result(
                        f"⚠️ 在 {start_day} 天前到 {end_day} 天前的范围内没有找到用户 {username} 的公开活动。"
                    )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                yield event.plain_result(
                    f"❌ 分析失败：找不到用户 '{username}'。请检查用户名是否正确。"
                )
            else:
                logger.error(f"分析 {username} 时发生 GitHub API 错误: {e}")
                yield event.plain_result(
                    f"❌ 分析失败：GitHub API 返回错误 - {e.response.status_code}。"
                )
        except Exception as e:
            logger.error(f"分析 {username} 时发生未知错误: {e}", exc_info=True)
            yield event.plain_result("❌ 分析时发生未知错误，请检查后台日志。")

    async def _fetch_user_events(self, username: str, token: str):
        headers = {"Authorization": f"token {token}"}
        # 增加页数以获取更多数据，确保能覆盖 lookback_days
        for page in range(1, 11):
            url = f"https://api.github.com/users/{username}/events/public?page={page}"
            response = await self.http_client.get(url, headers=headers)
            response.raise_for_status()
            events = response.json()
            if not events:
                break
            for event in events:
                yield event

    async def _analyze_and_prepare_data(
        self, username: str, token: str, start_day: int, end_day: int
    ) -> dict:
        # 1. 获取用户基本信息和头像 (保持不变)
        user_api_url = f"https://api.github.com/users/{username}"
        headers = {"Authorization": f"token {token}"}
        user_response = await self.http_client.get(user_api_url, headers=headers)
        user_response.raise_for_status()
        user_data = user_response.json()
        avatar_url = user_data.get("avatar_url")

        avatar_base64 = ""
        if avatar_url:
            try:
                avatar_resp = await self.http_client.get(avatar_url)
                avatar_resp.raise_for_status()
                content_type = avatar_resp.headers.get("Content-Type", "image/png")
                avatar_base64 = f"data:{content_type};base64,{base64.b64encode(avatar_resp.content).decode('utf-8')}"
            except Exception as e:
                logger.warning(f"下载用户 {username} 的头像失败: {e}")

        # 2. 分析事件逻辑 (保持不变)
        work_start_hour = self.config.get("work_start_hour", 10)
        work_end_hour = self.config.get("work_end_hour", 18)
        hourly_activity, event_type_count = defaultdict(int), defaultdict(int)
        off_hour_count, midnight_activity, weekend_activity, total_activity = 0, 0, 0, 0
        active_days = set()
        local_tz = datetime.now().astimezone().tzinfo
        now = datetime.now(local_tz)

        async for event in self._fetch_user_events(username, token):
            created_at = event.get("created_at")
            if not created_at:
                continue
            try:
                utc_time = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                continue

            local_time = utc_time.astimezone(local_tz)
            days_diff = (now - local_time).days

            # 因为事件是按时间倒序的，一旦超出起始范围，后续的都会超出
            if days_diff >= start_day:
                break
            # 如果事件在截止范围之内（即过于近期），则跳过
            if days_diff < end_day:
                continue

            # 事件在指定范围内，开始统计
            active_days.add(local_time.strftime("%Y-%m-%d"))
            hourly_activity[local_time.hour] += 1
            event_type_count[event.get("type", "Unknown")] += 1
            total_activity += 1
            if local_time.hour < work_start_hour or local_time.hour >= work_end_hour:
                off_hour_count += 1
            if local_time.hour < 6:
                midnight_activity += 1
            if local_time.weekday() >= 5:
                weekend_activity += 1

        if total_activity == 0:
            return None

        # =================================================================
        #  3. 在 Python 代码中进行所有计算和 HTML 生成 (*** 这是修改的核心区域 ***)
        # =================================================================

        # 计算 Grind Score (保持不变)
        grind_score = (
            (off_hour_count / total_activity)
            + (0.1 * weekend_activity)
            + (0.2 * midnight_activity)
        )

        # 生成“事件类型分布”的 HTML，现在包含更具体的类名以匹配新样式
        # 去掉 [:5] 的限制，显示所有事件类型
        sorted_events = sorted(
            event_type_count.items(), key=lambda item: item[1], reverse=True
        )
        
        # 改回单列布局
        event_list_html_parts = []
        for event_type, count in sorted_events:
            event_list_html_parts.append(
                f'<div class="event-list-item">'
                f'<span class="event-name">{event_type}</span>'
                f'<span class="event-count">{count}</span>'
                f"</div>"
            )
        event_list_html = "".join(event_list_html_parts)

        # 生成“每小时活动分布”的 HTML，包含动态判断逻辑
        hourly_chart_html_parts = []
        # 安全地获取最大活动数，如果为空则为1，避免除零错误
        max_hourly_activity = max(hourly_activity.values()) if hourly_activity else 1

        # 定义一个阈值，决定数值显示在内部还是外部
        # 这个值可以根据实际效果微调，例如20%或25%
        threshold_percentage = 20

        for hour in range(24):
            count = hourly_activity.get(hour, 0)
            percentage = (count / max_hourly_activity) * 100

            html_segment = ""
            # CASE 1: 活动数大于0，且条形图足够长
            if count > 0 and percentage >= threshold_percentage:
                html_segment = f"""
                <div class="hour-bar-container">
                    <span class="hour-label">{hour:02d}:00</span>
                    <div class="bar-wrapper">
                        <div class="bar" style="width: {percentage}%;">
                            <span class="hourly-value-inside">({count})</span>
                        </div>
                    </div>
                </div>
                """
            # CASE 2: 活动数大于0，但条形图较短
            elif count > 0:
                html_segment = f"""
                <div class="hour-bar-container">
                    <span class="hour-label">{hour:02d}:00</span>
                    <div class="bar-wrapper">
                        <div class="bar" style="width: {percentage}%;"></div>
                        <span class="hourly-value-outside">({count})</span>
                    </div>
                </div>
                """
            # CASE 3: 活动数为0
            else:
                html_segment = f"""
                <div class="hour-bar-container">
                    <span class="hour-label">{hour:02d}:00</span>
                    <div class="bar-wrapper">
                        <!-- 对于0值，我们只显示数值，不显示空的bar div -->
                        <span class="hourly-value-outside">({count})</span>
                    </div>
                </div>
                """
            hourly_chart_html_parts.append(html_segment)

        hourly_chart_html = "".join(hourly_chart_html_parts)

        # 4. 返回一个扁平化的字典，所有键都与模板中的 {{...}} 直接对应
        return {
            "username": user_data.get("name") or username,  # 优先使用用户的显示名称
            "avatar_base64": avatar_base64,
            "grind_score": f"{grind_score:.2f}",
            "total_activity": total_activity,
            "off_hour_count": off_hour_count,
            "active_days_count": len(active_days),
            "weekend_activity": weekend_activity,
            "event_list_html": event_list_html,
            "hourly_chart_html": hourly_chart_html,
        }
