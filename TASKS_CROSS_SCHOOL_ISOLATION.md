# 编码任务规划：跨校资料不能作为本校课程事实证据

> 基线：项目需求文档 V1.0 第 6.2 节
> 关联设计：`campus_memory_ai/DESIGN_CROSS_SCHOOL_ISOLATION.md`
> 当前状态：retrieval.py / main.py / test_acceptance.py 已由上一阶段完成代码修改，scoring.py 未改；测试因沙箱网络限制未实际运行
> 文档版本：v1.0（2026-10-28）

**任务规划原则**
1. 垂直切割：按业务功能分组，而非按技术层次分组
2. 可验收：每个任务必须有明确的完成标准
3. 原子性：一个任务只做一件事，避免冗长描述
4. 有序性：任务按依赖关系排序，被依赖者在前

> 标注约定：每个子任务末尾标注 `（优先级：X；依赖：Y）`，验收标准在任务描述中体现"做到什么程度"。

---

## 1. 代码实现一致性核对

核对已改动文件与实现方案文档的一致性，确认过滤逻辑在三个入口的正确性，确认 scoring.py 无需改动的理由成立。本组任务为只读核对，不产生代码变更。

### 1.1 核对 retrieval.py 新增辅助函数

- [ ] 核对 `_course_school`（`backend/app/services/retrieval.py:90-95`）实现，确认三种入参情形返回值：`course_id` 为空→None、课程不存在→None、正常→`course.school`。验收：返回值与设计文档 2.2.2 契约逐一对应。（优先级：高；依赖：无）
- [ ] 核对 `_matches_course_school`（`backend/app/services/retrieval.py:98-106`）5 个分支返回值，逐一对照设计文档 2.1.3 流程图：未选课程（`course_id` 为空）→True、课程无 school（`course_school` 为空）→True、来源 school 为空→False、来源 school 等于课程 school→True、来源 school 不等于课程 school→False。验收：5 分支全部与流程图一致。（优先级：高；依赖：无）

### 1.2 核对 search_sources 过滤插入位置

- [ ] 核对 `search_sources`（`backend/app/services/retrieval.py:109-144`）中跨校过滤插入位置在 `course_id` 过滤（122-123 行）之后、`term` 过滤（126 行）之前（124-125 行），符合设计文档决策 3"廉价判定前置"原则。验收：过滤顺序与设计文档 1.2.1 过滤链第 5→6→7 步一致。（优先级：高；依赖：1.1）
- [ ] 确认 `course_school = _course_school(db, course_id)`（111 行）在循环外预计算一次，避免每条来源重复查库。验收：`db.get(Course, course_id)` 在单次请求内最多调用一次。（优先级：中；依赖：1.1）

### 1.3 核对 retrieve_evidence 过滤插入位置

- [ ] 核对 `retrieve_evidence`（`backend/app/services/retrieval.py:147-188`）中跨校过滤插入位置在 `course_id` 过滤（161-162 行）之后、相关性计算（169 行起）之前（163-164 行），确保跨校来源不进入语义/关键词打分。验收：过滤先于 `source_content` 与 `semantic_scores` 使用，与设计文档 2.5 不变量"跨校过滤在相关性计算之前"一致。（优先级：高；依赖：1.1）
- [ ] 确认 `course_school` 在循环外预计算（149 行）。验收：同 1.2，单次请求最多一次主键查询。（优先级：中；依赖：1.1）

### 1.4 核对 /api/credibility 内联过滤

- [ ] 核对 `main.py` `/api/credibility`（`backend/app/main.py:510-528`）内联过滤逻辑（522-524 行）与 `retrieval._matches_course_school` 在 `course_id` 和 `course_school` 均非空时的行为等价：`bool(item.school) and item.school == course_school`。验收：内联条件与函数分支逻辑逐一比对一致。（优先级：高；依赖：1.1）
- [ ] 核对内联过滤在 `score_sources(db, rows)`（525 行）调用之前执行，确保跨校来源不进入评分候选。验收：过滤后的 `rows` 才传入 `score_sources`。（优先级：高；依赖：1.1）
- [ ] 核对 `course_school` 计算逻辑（512-515 行）：`course_id` 非空时查 `Course` 表取 `school`，课程不存在时为 None，此时不过滤（保守放行）。验收：与 `_course_school` 语义一致。（优先级：中；依赖：1.1）

### 1.5 确认 scoring.py 无需改动的理由成立

- [ ] 确认 `scoring.py` 分组键 `group_stmt`（`backend/app/services/scoring.py:103-110`）已包含 `SourceRecord.school == source.school`，外校来源天然不进入本校来源的独立佐证计数。验收：分组条件中 school 为等值约束，满足需求要点 3"不允许外校来源增加本校主张的独立佐证数量"。（优先级：高；依赖：无）
- [ ] 确认 `score_source` 入参为单条 `SourceRecord`（`scoring.py:89`），其 `group_stmt` 查询独立于调用方传入的候选列表，因此 `/api/credibility` 过滤掉跨校来源后留存来源的分数计算不变。验收：确认 group 查询不引用外部候选集。（优先级：高；依赖：无）
- [ ] 确认 M1/M2/M4 的 school 均为本校（参考 `seed.py`），跨校过滤不影响其 group，分数保持 87.5/81.0/57.0。验收：三条样例 school 字段均为本校值。（优先级：高；依赖：无）

---

## 2. 测试执行与断言验证

在无网络限制环境（开发者本机或 CI，具备正常 loopback 127.0.0.1）运行测试套件，确认全绿及关键断言通过。本组任务依赖组 1 核对完成。

### 2.1 在无网络限制环境运行测试套件

- [ ] 在具备正常 loopback 的环境执行 `pytest -q backend/tests`（工作目录 `campus_memory_ai/backend`），确认无 TestClient socketpair 环境错误。验收：测试套件正常收集并执行完毕，无因网络限制导致的 collection error。（优先级：高；依赖：1.1-1.5）

### 2.2 确认测试总数与通过数

- [ ] 确认测试通过总数为 24（原 22 个既有测试 + 新增 2 个跨校隔离回归测试），全部 passed，0 failed，0 error。验收：`pytest -q` 输出 `24 passed`。（优先级：高；依赖：2.1）

### 2.3 确认既有评分样例断言通过

- [ ] 确认 `test_credibility_example_matches_requirements`（`backend/tests/test_acceptance.py:8-22`）中 M1=87.5、M2=81.0、M4=57.0 断言通过，M3 不计分。验收：三组分数断言与需求文档 V1.0 样例表一致，跨校过滤未改变既有样例分数。（优先级：高；依赖：2.2）

### 2.4 确认跨校隔离测试断言通过

- [ ] 确认 `test_cross_school_source_is_excluded_from_course_evidence`（`backend/tests/test_acceptance.py:336-374`）三个入口断言通过：搜索结果不含跨校来源、AI 问答 citations 不含跨校来源、可信度 results 不含跨校来源。验收：三条 `assert all(...)` 均通过。（优先级：高；依赖：2.2）

### 2.5 确认同校可用测试断言通过

- [ ] 确认 `test_same_school_permitted_source_still_usable_for_course`（`backend/tests/test_acceptance.py:377-401`）断言通过：同校来源出现在搜索结果中、出现在可信度候选中、`source.school == course.school`。验收：两条 `assert any(...)` 及 school 一致断言均通过。（优先级：高；依赖：2.2）

---

## 3. 边界场景补强

评估并视情况补强设计文档 2.6.3 标注的"未单独构造测试用例"的边界分支，确保每个边界行为有测试覆盖或明确记录为既有约束。本组任务依赖组 1、组 2 完成。

### 3.1 评估并补强"来源 school 为空"分支测试

- [ ] 评估 `_matches_course_school` 在 `source.school` 为空字符串时的返回值（应为 False，即选定课程时排除 school 为空的来源），确认该分支已被 `bool(source.school)` 判定覆盖。验收：代码审查确认空字符串 falsy 判定正确。（优先级：中；依赖：1.1）
- [ ] 视评估结果在 `backend/tests/test_acceptance.py` 新增一个测试用例：创建来源后直接改 DB 将 `school` 设为空字符串，验证选定课程时该来源被三入口排除。验收：新增测试在无网络限制环境运行通过。（优先级：中；依赖：2.5、3.1 评估）

### 3.2 评估并补强"课程 school 为空"保守放行分支测试

- [ ] 评估 `_matches_course_school` 在 `course_school` 为 None 时的保守放行策略（返回 True，不过滤），确认该策略与设计文档 2.7.3 取舍一致：避免课程元数据缺失导致结果全空。验收：代码审查确认 `not course_school` 分支返回 True。（优先级：中；依赖：1.1）
- [ ] 视评估结果在 `backend/tests/test_acceptance.py` 新增一个测试用例：创建一门 school 为空的课程及一条指向它的来源，验证该来源仍可被检索（保守放行）。验收：新增测试在无网络限制环境运行通过，或明确记录为"演示课程均有 school，此分支属数据治理约束"。（优先级：低；依赖：2.5、3.2 评估）

### 3.3 确认"未指定 course_id"时不过滤跨校的行为

- [ ] 确认 `search_sources` / `retrieve_evidence` / `/api/credibility` 在 `course_id` 为 None 时 `_matches_course_school` 返回 True（不过滤），全库检索保留所有来源。验收：三个入口在无 course_id 时均不触发跨校过滤，与设计文档 2.1.3 分支表"未选课程→True"一致。（优先级：中；依赖：1.1-1.4）

### 3.4 评估 main.py 内联过滤是否应复用 _matches_course_school

- [ ] 评估 `main.py:522-524` 内联过滤与 `retrieval._matches_course_school` 存在逻辑重复，评估是否应重构为复用函数以消除重复、保证未来逻辑变更单点维护。验收：给出明确结论——若复用则提交重构且测试全绿；若保持内联则在代码注释中标注"与 retrieval._matches_course_school 保持同步"。（优先级：低；依赖：1.4、2.2）

---

## 4. 文档同步更新

更新项目文档以反映跨校隔离已实现，但不夸大未在独立环境验证的项。本组任务依赖组 2、组 3 完成。

### 4.1 更新 IMPLEMENTATION_STATUS.md

- [ ] 在 `campus_memory_ai/IMPLEMENTATION_STATUS.md` "当前交付"新增条目：跨校资料隔离——选定课程时搜索/问答/可信度三入口排除 school 不匹配的来源，来源 school 为空亦排除，课程 school 为空时保守放行。验收：条目准确描述实现行为，不含未实现内容。（优先级：高；依赖：2.2）
- [ ] 更新 `IMPLEMENTATION_STATUS.md` "当前验证结果"中 `pytest -q backend/tests` 通过数：将"22 passed"更新为"24 passed"，并明确标注"含跨校隔离回归测试 2 个；测试待在具备正常 loopback 的独立环境复现，沙箱因网络限制未能运行"。验收：数字准确且不夸大为已在本环境验证通过。（优先级：高；依赖：2.2）
- [ ] 在 `IMPLEMENTATION_STATUS.md` "尚未完成/不能声称已通过"中确认跨校隔离测试的独立环境复现项已列入（若 2.1 已在独立环境通过则移除该项，否则保留）。验收：文档状态与实际验证结果一致。（优先级：中；依赖：2.1）

### 4.2 更新 REQUIREMENTS_TRACEABILITY.md

- [ ] 在 `campus_memory_ai/REQUIREMENTS_TRACEABILITY.md` P0 功能需求表中新增跨校隔离需求条目（对应需求文档 V1.0 第 6.2 节），说明当前实现：`search_sources`/`retrieve_evidence`/`/api/credibility` 三入口在选定课程时按 `source.school == course.school` 过滤，来源 school 为空排除，课程 school 为空保守放行，scoring 分组键已含 school。验收：条目覆盖需求要点 1-4，验收/限制列标注"测试待独立环境复现"。（优先级：高；依赖：2.2）
- [ ] 确认 `REQUIREMENTS_TRACEABILITY.md` 中既有条目（FR-01 检索、FR-06 问答、FR-09 评分）的"验收/限制"列是否需补充跨校隔离相关说明，避免文档前后矛盾。验收：既有条目与新条目无语义冲突。（优先级：中；依赖：4.2 新增条目）

---

## 5. 最终验收确认

最终验证确保交付质量，确认代码审查、设计一致性与变更范围。

### 5.1 代码审查确认

- [ ] 审查本次变更涉及的 3 个文件（`retrieval.py`、`main.py`、`test_acceptance.py`）的 diff，确认无意外改动、无调试残留代码、无未删除的临时代码。验收：diff 仅包含跨校隔离相关的新增函数、过滤插入与测试。（优先级：高；依赖：1.1-1.5）
- [ ] 确认 `scoring.py`、`models.py`、`seed.py`、`ai.py`、`embeddings.py`、`security.py`、`config.py`、`database.py` 及前端静态资源均未触碰，与设计文档 2.7.5 修改文件清单一致。验收：未触碰文件清单与设计文档一致。（优先级：高；依赖：1.5）

### 5.2 设计一致性与变更范围确认

- [ ] 核对实现与设计文档 2.4 四项架构决策的对应关系：决策 1（在 retrieval/main 层过滤而非 scoring 层）、决策 2（不改 scoring.py）、决策 3（过滤顺序 course_id 之后 term 之前）、决策 4（/api/credibility Python 层过滤）。验收：四项决策均有对应代码实现且无偏离。（优先级：高；依赖：1.1-1.5）
- [ ] 确认变更范围严格限于"跨校资料不能作为本校课程事实证据"单一需求，未引入配置开关、未改变对外接口签名、未修改表结构。验收：与设计文档 2.2.1"返回集合只缩不增"的向后兼容收紧一致。（优先级：高；依赖：5.1）

---

## 任务依赖关系总览

```
组 1（代码核对）  ──无依赖──→  可最先执行
组 2（测试验证）  ──依赖组 1──→  确认代码正确后运行测试
组 3（边界补强）  ──依赖组 1、组 2──→  确认现有实现与测试后评估补强
组 4（文档同步）  ──依赖组 2、组 3──→  测试结果与补强完成后准确更新文档
组 5（最终验收）  ──依赖组 1-4──→  全部完成后最终确认
```

## 验收总标准

- 代码与设计文档 `DESIGN_CROSS_SCHOOL_ISOLATION.md` 完全一致
- `pytest -q backend/tests` 在无网络限制环境输出 `24 passed`
- M1=87.5 / M2=81.0 / M4=57.0 及跨校隔离、同校可用断言全部通过
- 边界分支（来源 school 为空、课程 school 为空、未选 course_id）均有测试覆盖或明确记录
- `IMPLEMENTATION_STATUS.md` 与 `REQUIREMENTS_TRACEABILITY.md` 准确反映实现状态，不夸大未验证项
- 变更范围严格限于 3 个文件，未触碰设计文档 2.7.5 清单外文件