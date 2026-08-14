# -*- coding: utf-8 -*-
"""简历/文本去 AI 味后处理（雕龙技能复用——humanizer_scorer + DeepSeek 改写）

用法:
    python resume_humanize.py <输入文件.txt> [输出文件.txt]
    python resume_humanize.py <输入文件.txt> --score-only   # 只评分不改写

流程:
    1. humanizer_scorer 评分（0-100 人性化）
    2. 分数 < 阈值（默认 70）→ DeepSeek 按去 AI 味 prompt 改写
    3. 改写后重新评分 → 输出（含分数报告）
"""

import json
import os
import sys
import urllib.request

THRESHOLD = 70

# 中文 AI 味套话（humanizer_scorer 词表偏英文——补中文盲区）
CHINESE_AI_PHRASES = [
    "综上所述",
    "总而言之",
    "值得注意的是",
    "众所周知",
    "毋庸置疑",
    "赋能",
    "助力",
    "加持",
    "抓手",
    "闭环",
    "颗粒度",
    "底层逻辑",
    "显著提升",
    "大幅提升",
    "有效提升",
    "奠定基础",
    "保驾护航",
    "积极响应",
    "深入贯彻落实",
    "取得了阶段性成果",
    "意义重大",
    "全面覆盖",
    "深度赋能",
    "多维度",
    "全方位",
    "一站式",
]


def chinese_ai_score(text: str) -> float:
    """中文套话检测评分（0-100——命中越多分越低）"""
    hits = sum(text.count(p) for p in CHINESE_AI_PHRASES)
    if hits == 0:
        return 100.0
    return max(0.0, 100.0 - hits * 35)  # 中文套话=强信号——单命中即大幅拉低


def read_env_key():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    try:
        for line in open(env_path, encoding="utf-8"):
            if line.startswith("DEEPSEEK_API_KEY="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return os.environ.get("DEEPSEEK_API_KEY", "")


def llm_rewrite(text: str, api_key: str) -> str:
    """DeepSeek 去 AI 味改写（雕龙 Voice Profiles 思路——自然/口语化/去套话）"""
    system = (
        "你是一名资深文字打磨师，专长是消除'AI 味'，让文本像真人写的。"
        "改写规则：\n"
        "1. 删掉 AI 高频套话（'总之''值得注意的是''综上所述''赋能''助力'等）\n"
        "2. 长短句交错，避免每句等长（真人写作有节奏感）\n"
        "3. 用具体细节代替空泛形容词（'显著提升'→'从 3 秒降到 1 秒'）\n"
        "4. 保留所有事实、数字、项目名、技术名词——只改表达不改内容\n"
        "5. 不添加原文没有的信息\n"
        "6. 语气自然、克制，不夸大不煽情\n"
        "只输出改写后的文本，不要解释。"
    )
    payload = json.dumps(
        {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            "max_tokens": 2000,
            "temperature": 0.4,
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read())
        return d["choices"][0]["message"]["content"].strip()


def main():
    src = sys.argv[1]
    score_only = "--score-only" in sys.argv
    try:
        with open(src, encoding="utf-8") as f:
            text = f.read().strip()
    except OSError as e:
        print(f"读文件失败: {e}")
        sys.exit(1)

    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
    import humanizer_scorer as hs

    if hasattr(hs, "score_humanity"):
        base = float(hs.score_humanity(text)["humanity_score"])
    else:  # 兼容：取组合评分
        base = float(
            hs.score_ai_vocabulary(text)["score"]
            + hs.score_sentence_variance(text)["score"]
        )
    score = min(base, chinese_ai_score(text))
    print(
        f"原文本人性化评分: {score:.0f}/100（中文套话检测 {chinese_ai_score(text):.0f}）"
    )

    if score_only:
        return
    if score >= THRESHOLD:
        print(f"✅ 已达标（≥{THRESHOLD}）——无需改写")
        return

    api_key = read_env_key()
    if not api_key:
        print("❌ 未找到 DEEPSEEK_API_KEY（.env 或环境变量）")
        sys.exit(1)
    print("⚠️ 低于阈值——DeepSeek 改写中...")
    rewritten = llm_rewrite(text, api_key)
    if hasattr(hs, "score_humanity"):
        base2 = float(hs.score_humanity(rewritten)["humanity_score"])
    else:
        base2 = float(
            hs.score_ai_vocabulary(rewritten)["score"]
            + hs.score_sentence_variance(rewritten)["score"]
        )
    score2 = min(base2, chinese_ai_score(rewritten))
    print(f"改写后评分: {score2:.0f}/100")
    out = sys.argv[2] if len(sys.argv) > 2 and not score_only else src
    with open(out, "w", encoding="utf-8") as f:
        f.write(rewritten)
    print(f"输出: {out}")


if __name__ == "__main__":
    main()
