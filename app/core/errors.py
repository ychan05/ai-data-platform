from fastapi import HTTPException


class AppError(Exception):
    """所有业务异常的基类。"""

    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, resource: str, id: str | int = ""):
        super().__init__(
            code="NOT_FOUND",
            message=f"{resource} 不存在" + (f" (id={id})" if id else ""),
            status_code=404,
        )


class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(code="VALIDATION_ERROR", message=message, status_code=422)


class LLMError(AppError):
    def __init__(self, message: str = "LLM 服务暂时不可用"):
        super().__init__(code="LLM_ERROR", message=message, status_code=502)


class SQLGenerationError(AppError):
    def __init__(self, message: str = "SQL 生成失败"):
        super().__init__(code="SQL_GENERATION_ERROR", message=message, status_code=500)


class PermissionDeniedError(AppError):
    def __init__(self, message: str = "权限不足"):
        super().__init__(code="PERMISSION_DENIED", message=message, status_code=403)