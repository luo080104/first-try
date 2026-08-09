# errors.py - 采集/搜索异常分类（WorkBuddy 审核意见：失败要分类）
# CaptchaError：验证码拦截 → 采集时该词立即暂停（不重试不计数）


class CaptchaError(Exception):
    """验证码拦截异常（按项目合规原则：不绕验证码，立即停止）"""
    pass
