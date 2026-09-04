#!/usr/bin/env python3
"""
Whoop Daily Report - GitHub Actions Edition
- Auto-refreshes token using refresh_token
- Fetches recovery/cycle/sleep/workout data from Whoop API
- Generates formatted report
- Pushes to WeChat via Server酱 (ServerChan)
- Updates token back to GitHub repo via API (so refresh_token persists across runs)
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import ssl
from datetime import datetime, timezone, timedelta

# ============ Config ============
CLIENT_ID = os.environ.get("WHOOP_CLIENT_ID", "c687642d-38a9-4ae2-afb5-79d1828aa081")
CLIENT_SECRET = os.environ.get("WHOOP_CLIENT_SECRET", "a6c2af3c646fc98aef04aa5584ee7f7d12f0ebb97722fc1e7fe686aad256df3a")
SERVERCHAN_KEY = os.environ.get("SERVERCHAN_KEY", "")
BASE = "https://api.prod.whoop.com/developer/v2"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# GitHub repo token persistence (optional - if set, writes updated token back to repo)
GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "")  # e.g. "username/whoop-report"
TOKEN_FILE_PATH = "whoop_token.json"

# Initial token from environment (first run) or from file
INITIAL_TOKEN_JSON = os.environ.get("WHOOP_TOKEN_JSON", "")

tz8 = timezone(timedelta(hours=8))
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def api_post(url, data_dict):
    """POST with form-encoded data, return parsed JSON."""
    data = urllib.parse.urlencode(data_dict).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", UA)
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        return json.loads(resp.read().decode())


def api_get(url, access_token):
    """GET with Bearer auth, return parsed JSON."""
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("User-Agent", UA)
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        return json.loads(resp.read().decode())


def load_token():
    """Load token from file, or from env var on first run."""
    # Try file first
    if os.path.exists(TOKEN_FILE_PATH):
        with open(TOKEN_FILE_PATH) as f:
            return json.load(f)
    # Try env var (for first run in GitHub Actions)
    if INITIAL_TOKEN_JSON:
        token = json.loads(INITIAL_TOKEN_JSON)
        # Save to file for subsequent runs
        with open(TOKEN_FILE_PATH, "w") as f:
            json.dump(token, f, indent=2)
        return token
    print("ERROR: No token found. Set WHOOP_TOKEN_JSON env var or provide whoop_token.json file.")
    sys.exit(1)


def refresh_token(token):
    """Refresh access token using refresh_token. Returns updated token dict."""
    rt = token.get("refresh_token")
    if not rt:
        print("ERROR: No refresh_token in token file")
        sys.exit(1)

    result = api_post(TOKEN_URL, {
        "grant_type": "refresh_token",
        "refresh_token": rt,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    })
    # Keep old refresh_token if new one not provided
    if "refresh_token" not in result:
        result["refresh_token"] = rt
    # Save locally
    with open(TOKEN_FILE_PATH, "w") as f:
        json.dump(result, f, indent=2)
    print("Token refreshed OK")
    return result


def save_token_to_repo(token):
    """Push updated token back to GitHub repo so it persists across runs."""
    if not GH_TOKEN or not GH_REPO:
        return  # Not configured, skip
    try:
        url = f"https://api.github.com/repos/{GH_REPO}/contents/{TOKEN_FILE_PATH}"
        # Get current file SHA
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"token {GH_TOKEN}")
        req.add_header("User-Agent", "whoop-report-action")
        import base64
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                current = json.loads(resp.read().decode())
                sha = current.get("sha")
        except:
            sha = None
        # Update file
        content = base64.b64encode(json.dumps(token, indent=2).encode()).decode()
        data = json.dumps({"message": "chore: update whoop token", "content": content, "sha": sha}).encode()
        req = urllib.request.Request(url, data=data, method="PUT")
        req.add_header("Authorization", f"token {GH_TOKEN}")
        req.add_header("User-Agent", "whoop-report-action")
        with urllib.request.urlopen(req, timeout=10) as resp:
            print("Token saved to repo OK")
    except Exception as e:
        print(f"Warning: could not save token to repo: {e}")


def fmt_time(ms):
    if not ms:
        return "N/A"
    h = ms / 3600000
    m = (ms % 3600000) / 60000
    return f"{int(h)}h {int(m)}min"


def fmt_dt(dt_str):
    if not dt_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        dt = dt.astimezone(tz8)
        return dt.strftime("%m-%d %H:%M")
    except:
        return dt_str


def generate_report(recovery, cycle, sleep, workout):
    """Generate the formatted text report."""
    now_str = datetime.now(tz8).strftime("%Y-%m-%d %H:%M")

    rec = recovery["records"][0] if recovery["records"] else None
    rec_score = rec["score"] if rec and rec.get("score") else {}

    cyc = cycle["records"][0] if cycle["records"] else None
    cyc_score = cyc["score"] if cyc and cyc.get("score") else {}
    cyc_prev = cycle["records"][1] if len(cycle["records"]) > 1 else None
    cyc_prev_score = cyc_prev["score"] if cyc_prev and cyc_prev.get("score") else {}

    slp = sleep["records"][0] if sleep["records"] else None
    slp_score = slp["score"] if slp and slp.get("score") else {}

    wkts = workout.get("records", [])

    lines = []
    lines.append("📊 WHOOP 每日身体报告")
    lines.append(f"生成时间: {now_str}")
    lines.append("")

    # Recovery
    lines.append("【恢复评分】")
    if rec_score:
        rec_val = rec_score.get("recovery_score", 0)
        rhr = rec_score.get("resting_heart_rate", 0)
        hrv = rec_score.get("hrv_rmssd_milli", 0)
        spo2 = rec_score.get("spo2_percentage", 0)
        skin_t = rec_score.get("skin_temp_celsius", 0)
        rec_status = "🔴低" if rec_val < 34 else ("🟡中" if rec_val < 67 else "🟢好")
        rhr_status = "🔴高" if rhr > 80 else ("🟡偏高" if rhr > 70 else ("✅优秀" if rhr < 60 else "🟢正常"))
        hrv_status = "🔴过低" if hrv < 25 else ("🟡偏低" if hrv < 40 else ("✅良好" if hrv < 60 else "🏆优秀"))
        spo2_status = "⚠️危险" if spo2 < 90 else ("🔴偏低" if spo2 < 95 else ("🟡稍低" if spo2 < 97 else "✅正常"))
        skin_status = "🟡偏高" if skin_t > 35 else ("🟡偏低" if skin_t < 33 else "✅正常")
        lines.append(f"  恢复评分: {rec_val}% {rec_status} (参考: 34-66%中等, 67%+良好)")
        lines.append(f"  静息心率: {rhr} bpm {rhr_status} (参考: 60-70正常, <60优秀)")
        lines.append(f"  心率变异性(HRV): {hrv:.1f} ms {hrv_status} (参考: 40-60正常, 60+良好)")
        lines.append(f"  血氧饱和度: {spo2:.1f}% {spo2_status} (参考: 97-100%正常)")
        lines.append(f"  皮肤温度: {skin_t:.2f}°C {skin_status} (参考: 33-35°C正常)")
    else:
        lines.append("  无数据")

    # Strain
    lines.append("")
    lines.append("【身体负荷 Strain】")
    if cyc_score:
        lines.append(f"  当前负荷: {cyc_score.get('strain', 0):.1f}")
        kj = cyc_score.get("kilojoule", 0)
        lines.append(f"  消耗热量: {kj:.0f} kJ ({kj / 4.184:.0f} kcal)")
        lines.append(f"  平均心率: {cyc_score.get('average_heart_rate', 'N/A')} bpm")
        lines.append(f"  最高心率: {cyc_score.get('max_heart_rate', 'N/A')} bpm")
    if cyc_prev_score:
        lines.append(f"  上一周期负荷: {cyc_prev_score.get('strain', 0):.1f} ({cyc_prev_score.get('kilojoule', 0) / 4.184:.0f} kcal)")

    # Sleep
    lines.append("")
    lines.append("【睡眠分析】")
    if slp_score:
        stage = slp_score.get("stage_summary", {})
        needed = slp_score.get("sleep_needed", {})
        total_sleep = (stage.get("total_light_sleep_time_milli", 0) +
                       stage.get("total_slow_wave_sleep_time_milli", 0) +
                       stage.get("total_rem_sleep_time_milli", 0))
        lines.append(f"  睡眠表现: {slp_score.get('sleep_performance_percentage', 'N/A')}% (参考: 85%+良好)")
        lines.append(f"  睡眠效率: {slp_score.get('sleep_efficiency_percentage', 'N/A')}% (参考: 95%+优秀)")
        lines.append(f"  实际睡眠: {fmt_time(total_sleep)} (参考: 7-9h)")
        lines.append(f"  浅睡眠: {fmt_time(stage.get('total_light_sleep_time_milli', 0))}")
        lines.append(f"  深睡眠: {fmt_time(stage.get('total_slow_wave_sleep_time_milli', 0))} (参考: 1.5-2h)")
        lines.append(f"  REM睡眠: {fmt_time(stage.get('total_rem_sleep_time_milli', 0))} (参考: 1.5-2h)")
        lines.append(f"  呼吸频率: {slp_score.get('respiratory_rate', 'N/A')} 次/分 (参考: 12-20)")
        lines.append(f"  需要睡眠: {fmt_time(needed.get('baseline_milli', 0))}")
        if slp.get("start") and slp.get("end"):
            lines.append(f"  入睡: {fmt_dt(slp.get('start'))} → 起床: {fmt_dt(slp.get('end'))}")
    else:
        lines.append("  无数据")

    # Workouts
    lines.append("")
    lines.append("【锻炼记录】")
    if wkts:
        for w in wkts:
            w_score = w.get("score", {})
            lines.append(f"  {w.get('sport_name', '运动')}: 负荷{w_score.get('strain', '?')}, 时长{fmt_time(w_score.get('duration_milli', 0))}")
    else:
        lines.append("  今日无锻炼")

    # Suggestions
    lines.append("")
    lines.append("【今日建议】")
    rec_val = rec_score.get("recovery_score", 50) if rec_score else 50
    rhr = rec_score.get("resting_heart_rate", 0) if rec_score else 0
    hrv = rec_score.get("hrv_rmssd_milli", 0) if rec_score else 0
    spo2 = rec_score.get("spo2_percentage", 0) if rec_score else 0

    if rec_val < 34:
        lines.append("  🔴 恢复较低，身体处于疲劳状态")
        lines.append("  • 今天以休息和轻度活动为主（散步、拉伸）")
        lines.append("  • 避免高强度训练，给身体恢复时间")
        lines.append("  • 今晚早睡，目标睡眠8小时+")
    elif rec_val < 67:
        lines.append("  🟡 恢复中等，可以进行适度训练")
        lines.append("  • 适合中等强度运动（慢跑、游泳、瑜伽）")
        lines.append("  • 注意身体反馈，感觉疲劳随时停止")
        lines.append("  • 保持规律作息")
    else:
        lines.append("  🟢 恢复良好，身体状态佳")
        lines.append("  • 适合高强度训练或突破极限")
        lines.append("  • 可以增加运动量或尝试新项目")
        lines.append("  • 保持当前作息节奏")

    if hrv and hrv < 30:
        lines.append(f"  ⚠️ HRV偏低({hrv:.0f}ms)，自主神经系统恢复不足")
        lines.append("  • 减少压力源，尝试深呼吸或冥想")
    elif hrv and hrv > 60:
        lines.append(f"  ✅ HRV优秀({hrv:.0f}ms)，身体适应能力强")

    if rhr and rhr > 70:
        lines.append(f"  ⚠️ 静息心率偏高({rhr:.0f}bpm)，可能未完全恢复")
    elif rhr and rhr < 60:
        lines.append(f"  ✅ 静息心率优秀({rhr:.0f}bpm)，心血管功能好")

    if spo2 and spo2 < 95:
        lines.append(f"  ⚠️ 血氧偏低({spo2:.1f}%)，注意呼吸和通风")

    # Sleep advice
    if slp_score:
        perf = slp_score.get("sleep_performance_percentage", 0)
        stage = slp_score.get("stage_summary", {})
        total_sleep_ms = (stage.get("total_light_sleep_time_milli", 0) +
                          stage.get("total_slow_wave_sleep_time_milli", 0) +
                          stage.get("total_rem_sleep_time_milli", 0))
        sleep_h = total_sleep_ms / 3600000
        deep_h = stage.get("total_slow_wave_sleep_time_milli", 0) / 3600000
        rem_h = stage.get("total_rem_sleep_time_milli", 0) / 3600000
        disturbances = stage.get("disturbance_count", 0)
        consistency = slp_score.get("sleep_consistency_percentage", 0)

        lines.append("")
        lines.append("【睡眠建议】")
        if sleep_h < 6:
            lines.append(f"  😴 严重睡眠不足({sleep_h:.1f}h)，今晚务必早睡")
            lines.append("  • 目标: 比昨晚多睡2小时以上")
            lines.append("  • 睡前1小时不看手机")
        elif sleep_h < 7:
            lines.append(f"  ⚠️ 睡眠不足({sleep_h:.1f}h)，建议7-9小时")
            lines.append("  • 今晚提前30分钟上床")
        elif sleep_h >= 8:
            lines.append(f"  ✅ 睡眠充足({sleep_h:.1f}h)，保持这个节奏")

        if perf < 70:
            lines.append(f"  📉 睡眠表现差({perf:.0f}%)，睡眠质量需改善")
            lines.append("  • 保持卧室凉爽(18-20°C)、安静、全黑")
            lines.append("  • 避免睡前饮酒和咖啡因")
        elif perf >= 90:
            lines.append(f"  ✅ 睡眠表现优秀({perf:.0f}%)")

        if deep_h < 1.0:
            lines.append(f"  ⚠️ 深睡眠不足({deep_h:.1f}h)，影响身体修复")
            lines.append("  • 深睡眠促进生长激素分泌，建议保证1.5h+")
        if rem_h < 0.8:
            lines.append(f"  ⚠️ REM睡眠不足({rem_h:.1f}h)，影响记忆和情绪")
        if disturbances > 10:
            lines.append(f"  ⚠️ 夜间干扰{disturbances}次较多，睡眠不连续")
        if consistency < 50 and consistency > 0:
            lines.append(f"  ⚠️ 睡眠一致性低({consistency:.0f}%)，作息不规律")
            lines.append("  • 尽量每天同一时间入睡和起床")

    # Strain advice
    if cyc_score:
        strain = cyc_score.get("strain", 0)
        if rec_val < 34 and strain > 10:
            lines.append("")
            lines.append("【负荷提醒】")
            lines.append(f"  ⚠️ 恢复低但负荷高({strain:.1f})，有过度训练风险")
            lines.append("  • 建议今天降低运动强度")
        elif rec_val > 67 and strain < 5:
            lines.append("")
            lines.append("【负荷提醒】")
            lines.append(f"  💡 恢复好但负荷低({strain:.1f})，可以加大运动量")

    # Workout advice
    if not wkts:
        if rec_val >= 50:
            lines.append("")
            lines.append("【运动建议】")
            lines.append("  • 今天还没有锻炼记录，状态允许可以安排一次")
            if rec_val >= 67:
                lines.append("  • 推荐: 高强度间歇、力量训练、长跑")
            else:
                lines.append("  • 推荐: 中等强度有氧30-45分钟")

    return "\n".join(lines)


def push_to_serverchan(title, content):
    """Send report to WeChat via Server酱."""
    if not SERVERCHAN_KEY:
        print("SERVERCHAN_KEY not set, skipping push. Report printed above.")
        return False
    url = f"https://sctapi.ftqq.com/{SERVERCHAN_KEY}.send"
    data = urllib.parse.urlencode({
        "title": title,
        "desp": content,
    }).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", UA)
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            result = json.loads(resp.read().decode())
            if result.get("code") == 0:
                print("Server酱推送成功!")
                return True
            else:
                print(f"Server酱推送失败: {result}")
                return False
    except Exception as e:
        print(f"Server酱推送异常: {e}")
        return False


def main():
    # 1. Load & refresh token
    token = load_token()
    token = refresh_token(token)
    access_token = token["access_token"]

    # 2. Fetch all data
    print("Fetching Whoop data...")
    recovery = api_get(f"{BASE}/recovery", access_token)
    cycle = api_get(f"{BASE}/cycle", access_token)
    sleep = api_get(f"{BASE}/activity/sleep", access_token)
    workout = api_get(f"{BASE}/activity/workout", access_token)
    print("Data fetched OK")

    # 3. Generate report
    report = generate_report(recovery, cycle, sleep, workout)
    print("\n" + "=" * 50)
    print(report)
    print("=" * 50)

    # 4. Push to Server酱
    today = datetime.now(tz8).strftime("%m-%d")
    title = f"Whoop日报 {today}"
    push_to_serverchan(title, report)

    # 5. Save updated token back to repo for next run
    save_token_to_repo(token)

    print("\nDone!")


if __name__ == "__main__":
    main()
