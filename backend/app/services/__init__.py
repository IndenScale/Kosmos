"""Services模块，统一暴露所有服务类以避免循环导入问题。"""

# 使用延迟导入避免循环导入问题
def __getattr__(name):
    if name == 'JobService':
        from .job.facade import JobService
        return JobService
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = ['JobService']