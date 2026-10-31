# Prompt for Huawei CodeArts Code Intelligent Agent — first task

> Paste the Chinese prompt below into the actual CodeArts Code Intelligent Agent. Save the real prompt and response as competition evidence.

你正在协助开发“校园集体记忆 AI 传承助手”。唯一需求基线是团队提供的《项目需求文档 V1.0》（2026-10-17）。当前代码是 FastAPI + SQLAlchemy + SQLite 的本地原型；自动化测试基线曾在开发环境记录为 22 项通过，但请在你当前的 CodeArts 环境中重新运行验证，不能直接把旧结果当作本次结果。

**本次任务只做需求理解与代码审查，不要直接重写或大规模修改代码。**

请先阅读：
1. `README.md`
2. `REQUIREMENTS_TRACEABILITY.md`
3. `IMPLEMENTATION_STATUS.md`
4. `CODEARTS_HANDOFF.md`
5. `backend/app/` 和 `backend/tests/`
6. 《项目需求文档 V1.0》中 FR-01 至 FR-15、NFR-01 至 NFR-11、AT-01 至 AT-18，以及第 5、6、7、8、9 章。若需求文档尚未导入仓库，请明确说明缺少文件，不要假定你已读取。

请完成以下工作：
- 运行当前项目测试，并提供实际命令、环境、完整结果和未通过项。
- 输出“需求编号 → 代码文件/接口 → 测试用例 → 当前状态 → 缺口/证据”的追踪表。
- 重点检查语义检索及关键词降级、外部来源权限（登记元数据与使用正文的区别）、跨校资料适用边界、FR-12 基础转载归并/下架同步、A/S/T/D 评分复现、未发布数据泄漏、隐私和密钥管理。
- 单独列出华为云集成缺口：CodeArts 实际工作流、RDS/MySQL 驱动及连接验证、Redis 是否可用及缓存失效、华为云获准模型/MaaS、云端部署、开源仓库与许可证、演示材料。
- 对于不在你的环境中可验证的功能，标记“未验证/需账号或资源”，不能写“已完成”。
- 提出最多 10 项按风险排序的改进建议，每项关联 FR/NFR/AT，并说明如何验证。

输出要求：中文、结构化表格；不打印密钥；不下载或抓取未经授权的网页正文；不修改生产配置；不自动迁移数据库；不做无关重构。完成审查后先停下来等待人工确认，再开展下一项编码任务。
