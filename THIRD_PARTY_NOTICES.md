# 第三方依赖许可证记录（测试环境直接依赖）

以下版本来自本原型验证环境中已安装发行包的元数据，并与 `backend/requirements.txt` 直接依赖版本一致。它们不是完整的传递依赖 SBOM；正式公开分发或打包前，还需要为部署环境生成完整依赖清单、逐项核对传递依赖许可证并按各自条款保留声明。

| 包 | 测试版本 | SPDX 许可证标识 | 用途 |
|---|---:|---|---|
| FastAPI | 0.128.2 | MIT | Web API 框架 |
| Uvicorn | 0.48.0 | BSD-3-Clause | ASGI 应用服务器（含 standard extras） |
| SQLAlchemy | 2.0.50 | MIT | ORM / 数据库访问 |
| Pydantic | 2.13.5 | MIT | 请求与数据模型验证 |
| HTTPX | 0.28.1 | BSD-3-Clause | 异步 HTTP 客户端，用于可选模型服务 |
| pytest | 9.0.2 | MIT | 自动化测试（开发依赖） |

## 上游许可证

- FastAPI: https://github.com/fastapi/fastapi/blob/master/LICENSE
- Uvicorn: https://github.com/encode/uvicorn/blob/master/LICENSE.md
- SQLAlchemy: https://github.com/sqlalchemy/sqlalchemy/blob/main/LICENSE
- Pydantic: https://github.com/pydantic/pydantic/blob/main/LICENSE
- HTTPX: https://github.com/encode/httpx/blob/master/LICENSE.md
- pytest: https://github.com/pytest-dev/pytest/blob/main/LICENSE

## 项目自身许可证（待团队决定）

项目原创代码的对外许可证尚未由团队决定。本文件不代表向第三方授予项目代码的开放许可。公开代码仓库或提交正式开源交付前，由团队选择并添加项目 `LICENSE` 文件；不要在未决定许可证时声称本项目为 MIT 或其他开源许可证项目。
