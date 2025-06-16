HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>用户数据概览</title>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        /* 基本样式 */
        body {
            margin: 0;
            padding: 20px;
            font-family: 'Noto Sans SC', 'Helvetica Neue', Arial, sans-serif;
            -webkit-font-smoothing: antialiased;
            color: #3D475C;
            background-color: #F0F2F5;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            box-sizing: border-box;
        }

        /* 主内容卡片 */
        .main-content-wrapper {
            width: 860px;
            max-width: 95%;
            background-color: #FFFFFF;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.07);
            display: flex;
            padding: 35px 40px;
            box-sizing: border-box;
            gap: 40px;
        }

        /* 左右两栏 */
        .left-column, .right-column {
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 30px; /* 模块间距 */
            min-width: 0;
        }

        /* 用户信息头部 */
        .header {
            display: flex;
            align-items: center;
            padding-bottom: 20px;
            border-bottom: 1px solid #F0F2F5;
        }

        .avatar {
            width: 75px;
            height: 75px;
            border-radius: 50%;
            margin-right: 20px;
            object-fit: cover;
            border: 4px solid #F0F2F5; /* 更柔和的边框 */
            flex-shrink: 0;
        }

        .user-info h1 {
            margin: 0;
            font-size: 26px;
            color: #2C3E50;
            font-weight: 700;
        }

        .user-info .score {
            margin: 6px 0 0;
            font-size: 17px;
            color: #7F8C8D;
        }

        .score-value {
            color: #27AE60;
            font-size: 19px;
            font-weight: 700;
            margin-left: 4px;
        }

        /* 模块标题 */
        .section-title {
            font-size: 18px;
            font-weight: 500;
            color: #3D475C;
            display: flex;
            align-items: center;
            gap: 10px;
            padding-bottom: 10px;
        }

        /* 模块内容容器 */
        .module-content {
            background-color: #F8F9FA;
            border-radius: 12px;
            padding: 20px;
        }

        /* 核心统计表格 */
        .stats-table {
            width: 100%;
            border-spacing: 0;
        }

        .stat-item {
            text-align: center;
            vertical-align: middle;
            padding: 10px 0;
        }
        .stats-table tr:first-child .stat-item {
            padding-bottom: 20px;
        }

        .stat-item .label {
            color: #7F8C8D;
            font-size: 14px;
            margin-bottom: 10px;
        }

        .stat-item .value {
            font-size: 28px;
            font-weight: 700;
            color: #2C3E50;
        }

        /* 事件列表 */
        .event-list-item {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            font-size: 15px;
            color: #555;
        }
        .event-list-item .event-name {
            color: #555;
        }
        .event-list-item .event-count {
            color: #888;
            font-weight: 500;
        }

        /* 每小时活动分布图 - 关键修改区域 */
        .hour-bar-container {
            display: flex;
            align-items: center;
            margin: 9px 0;
            height: 18px; /* 固定行高 */
        }

        .hour-label {
            width: 50px;
            text-align: left;
            color: #7F8C8D;
            font-size: 14px;
            flex-shrink: 0;
        }

        /* 包裹条形图和外部数值的容器 */
        .bar-wrapper {
            display: flex;
            align-items: center;
            flex-grow: 1;
            gap: 8px; /* 条形图与外部数值的间距 */
            min-width: 0;
        }

        .bar {
            height: 10px; /* 调整条形图高度 */
            background-color: #3A99EC; /* 更接近图片的蓝色 */
            border-radius: 5px;
            transition: width 0.3s ease-out;
            display: flex; /* 用于对齐内部数值 */
            justify-content: flex-end; /* 内部数值靠右 */
            align-items: center;
            overflow: hidden; /* 防止内部文字溢出 */
        }

        /* 数值在条形图外部的样式 */
        .hourly-value-outside {
            color: #7F8C8D;
            font-size: 13px;
            flex-shrink: 0;
        }

        /* 数值在条形图内部的样式 */
        .hourly-value-inside {
            color: white;
            font-size: 12px;
            padding: 0 8px; /* 内边距 */
            font-weight: 500;
            white-space: nowrap; /* 防止文字换行 */
        }

    </style>
</head>
<body>
    <div class="main-content-wrapper">
        <div class="left-column">
            <div>
                <div class="section-title">🔧 近期事件类型</div>
                <div class="module-content">
                    {{ event_list_html | safe }}
                </div>
            </div>
            <div>
                <div class="section-title">⏰ 每小时活动分布</div>
                <div class="module-content">
                    {{ hourly_chart_html | safe }}
                </div>
            </div>
        </div>

        <div class="right-column">
            <div class="header">
                <img src="{{ avatar_base64 }}" alt="avatar" class="avatar">
                <div class="user-info">
                    <h1>{{ username }}</h1>
                    <p class="score">🔥 内卷得分: <span class="score-value">{{ grind_score }}</span></p>
                </div>
            </div>
            <div>
                <div class="section-title">📊 核心统计</div>
                <div class="module-content">
                    <table class="stats-table">
                        <tr>
                            <td width="50%"><div class="stat-item"><div class="label">总事件</div><div class="value">{{ total_activity }}</div></div></td>
                            <td width="50%"><div class="stat-item"><div class="label">非工作时间</div><div class="value">{{ off_hour_count }}</div></div></td>
                        </tr>
                        <tr>
                            <td><div class="stat-item"><div class="label">活跃天数</div><div class="value">{{ active_days_count }}</div></div></td>
                            <td><div class="stat-item"><div class="label">周末事件</div><div class="value">{{ weekend_activity }}</div></div></td>
                        </tr>
                    </table>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""
