# 测试记录（原型 v0.1）

日期：2026-10-28  
测试基线：项目需求文档 V1.0（2026-10-17）

## 自动测试

执行命令：

```bash
cd backend
pytest -q
```

结果：`25 passed in 6.35s`（本机 Windows PowerShell，2026-10-28）。

覆盖范围包括：

- Health / 初始课程与演示数据；
- M1–M4评分值复算和转载不重复计分；
- 课程、学期、关键词组合检索及未发布负例过滤；
- 仅链接来源不泄露正文、不参与 RAG；
- 无证据时不编造答案或引用；
- 经验提交、贡献者确认、审核发布、权限和自审限制；
- 来源许可撤销/链接失效后从公开检索与问答中排除；
- 规则权重校验、规则版本快照；
- P1反馈 ID/处理状态、处理前后内容不被直接覆盖；
- P1维护建议不会自动合并或删除；P2聚合指标不返回个人身份字段；
- 管理配置变更日志和日志访问权限；
- 演示数据覆盖与隐私初筛/修订流程；
- 跨校资料隔离（V1.0 §6.2）：跨校来源不进入本校课程搜索/问答/可信度候选；
- 同课程同适用学校获准来源仍可正常使用；
- 来源 school 为空时选定课程的三入口排除。

其他检查：

- `python -m compileall -q backend/app scripts`：通过。
- `node --check backend/app/static/app.js`：通过。
- HTTP smoke check：`/`、`/static/app.js`、`/static/styles.css`、`/api/health`、`/api/auth/demo-accounts`、`/api/courses`、`/api/credibility` 均返回 200。
- 生产模式 smoke check：强密钥且 `SEED_DEMO_DATA=false` 可启动；不会预置或公开演示账号与演示课程。

## 未测试或待实测

- 仅 M1 时 75.5 且不标注"最可信参考"尚无直接自动化断言（现有测试针对 M1+M2+M4 共存场景）；
- 正式 Chrome / Edge / 移动浏览器操作流程；
- 30题 AI 评估集的真实模型运行与人工复核；
- NFR-05 性能压测；
- Docker build / compose；当前执行环境无 Docker CLI；
- Huawei Cloud CodeArts / RDS / MaaS 以及在线演示地址；
- 真实外部来源许可与失效链接逐条人工核验。

这些项目不得在最终汇报中填为"已通过"，直到真实执行并保存日志/截图/结果。


## Local Windows Test Verification

Date: 2026-10-28
Environment: Windows PowerShell
Working directory: campus_memory_ai/backend
Command: `python -m pytest -q`
Result: 25 passed in 6.35s

This is the real local execution result. The test suite includes
the original 22 acceptance tests plus 3 cross-school isolation
regression tests (cross-school exclusion, same-school usability,
empty-school exclusion).

Note on sandbox limitation: In the CodeArts agent sandbox, the
same test suite reports 25 errors because the sandbox network
policy blocks loopback 127.0.0.1, which Starlette's TestClient
requires for `socket.socketpair()`. This is an environment
restriction, not a code or assertion failure. The local Windows
result above is the current test evidence.

Status: Local automated test suite passed (25/25).
Scope: This result does not establish that all P0
acceptance tests, Huawei Cloud integrations, or deployment
requirements have passed.