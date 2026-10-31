from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import settings
from .database import Base, engine
from .models import User, Course, Experience, SourceRecord, SystemSetting
from .security import hash_password

DEMO_PASSWORD = "demo123!"

def dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def seed_database(db: Session) -> None:
    Base.metadata.create_all(bind=engine)
    if db.scalar(select(User.id).limit(1)):
        return
    users = [
        User(username="reader_demo", display_name="演示查询者", password_hash=hash_password(DEMO_PASSWORD), roles=["reader"], active=True),
        User(username="contributor_demo", display_name="演示贡献者", password_hash=hash_password(DEMO_PASSWORD), roles=["reader", "contributor"], active=True),
        User(username="reviewer_demo", display_name="演示审核员", password_hash=hash_password(DEMO_PASSWORD), roles=["reader", "reviewer"], active=True),
        User(username="admin_demo", display_name="演示管理员", password_hash=hash_password(DEMO_PASSWORD), roles=["reader", "admin", "reviewer"], active=True),
    ]
    db.add_all(users); db.flush()
    u = {item.username: item for item in users}
    courses = [
        Course(school=settings.app_school_name, code="MATH101", name="线性代数", default_term="2026春", active=True),
        Course(school=settings.app_school_name, code="CS201", name="数据结构", default_term="2026春", active=True),
        Course(school=settings.app_school_name, code="MATH203", name="离散数学", default_term="2025秋", active=True),
        Course(school=settings.app_school_name, code="CS205", name="计算机网络", default_term="2025秋", active=True),
    ]
    db.add_all(courses); db.flush()
    c = {item.name: item for item in courses}

    exp_m1 = Experience(
        course_id=c["线性代数"].id, submitter_id=u["contributor_demo"].id, term="2026春",
        raw_text="演示经验：期末复习时可以整理课堂笔记，并按章节提前完成对应练习。部分同学觉得矩阵变换的几何意义比较难理解。",
        difficulty="矩阵变换的几何意义比较难理解", assignments="未提及", assessment="期末复习（原文未说明具体考核安排）",
        advice="整理课堂笔记，并按章节提前完成对应练习", status="published", confirmed=True, ai_mode="演示数据", demo_data=True,
        created_at=dt("2026-06-15T10:00:00"), updated_at=dt("2026-06-15T10:00:00"))
    exp_m4 = Experience(
        course_id=c["线性代数"].id, submitter_id=u["contributor_demo"].id, term="2024秋",
        raw_text="演示经验：期末要提前复习。", difficulty="未提及", assignments="未提及", assessment="期末（无具体考核信息）",
        advice="期末要提前复习", status="published", confirmed=True, ai_mode="演示数据", demo_data=True,
        created_at=dt("2024-09-01T10:00:00"), updated_at=dt("2024-09-01T10:00:00"))
    exp_ds = Experience(
        course_id=c["数据结构"].id, submitter_id=u["contributor_demo"].id, term="2026春",
        raw_text="演示经验：复习树与图时，先手动画出小规模例子，再练习遍历过程。实验通常要求解释算法思路。",
        difficulty="树与图的遍历过程容易混淆", assignments="实验要求解释算法思路", assessment="未提及",
        advice="先手动画出小规模例子，再练习遍历过程", status="published", confirmed=True, ai_mode="演示数据", demo_data=True,
        created_at=dt("2026-04-20T10:00:00"), updated_at=dt("2026-04-20T10:00:00"))
    exp_dm = Experience(
        course_id=c["离散数学"].id, submitter_id=u["contributor_demo"].id, term="2025秋",
        raw_text="演示经验：命题逻辑部分建议把真值表和等价变形配合练习；遇到证明题时先写清楚使用的定义。",
        difficulty="证明题不容易组织步骤", assignments="未提及", assessment="未提及",
        advice="将真值表与等价变形配合练习；证明题先写清使用的定义", status="published", confirmed=True, ai_mode="演示数据", demo_data=True,
        created_at=dt("2025-10-18T10:00:00"), updated_at=dt("2025-10-18T10:00:00"))
    exp_negative = Experience(
        course_id=c["计算机网络"].id, submitter_id=u["contributor_demo"].id, term="2025秋",
        raw_text="负向测试记录：这条内容处于待审核状态，公开查询不应返回。", difficulty="未提及", assignments="未提及", assessment="未提及", advice="未提及",
        status="pending_review", confirmed=True, ai_mode="演示数据", demo_data=True,
        created_at=dt("2025-11-05T10:00:00"), updated_at=dt("2025-11-05T10:00:00"))
    db.add_all([exp_m1, exp_m4, exp_ds, exp_dm, exp_negative]); db.flush()
    for seeded_experience in (exp_m1, exp_m4, exp_ds, exp_dm, exp_negative):
        seeded_experience.original_raw_text = seeded_experience.raw_text

    reference_date = dt("2026-10-14T12:00:00")
    m1 = SourceRecord(
        source_code="M1", experience_id=exp_m1.id, course_id=c["线性代数"].id,
        title="M1 本校课程经验（合成演示数据）", author="演示学生 A（稳定记录标识）", school=settings.app_school_name,
        course_name="线性代数", term="2026春", claim_group="linear-algebra-final-review",
        content_excerpt="整理课堂笔记，并按章节提前完成对应练习。部分同学觉得矩阵变换的几何意义比较难理解。",
        permission="full_text_allowed", status="active", author_verified=True, has_concrete_scenario=True, has_actionable_detail=False,
        experience_date=dt("2026-06-15T12:00:00"), score_reference_date=reference_date,
        created_by=u["admin_demo"].id, demo_data=True)
    m2 = SourceRecord(
        source_code="M2", course_id=c["线性代数"].id, title="M2 外部已有回答（合成演示数据）",
        author="演示作者（可核验）", organization="示例公开问答平台（虚构）", url="https://example.org/demo-m2",
        source_type="external_answer", school=settings.app_school_name, course_name="线性代数", term="",
        claim_group="linear-algebra-final-review",
        content_excerpt="建议按章节整理笔记、列出易错点，并提前完成对应习题。该示例未注明经历学期。",
        permission="abstract_allowed", status="active", link_status="demo_placeholder", author_verified=True, has_concrete_scenario=True, has_actionable_detail=True,
        published_at=dt("2025-02-15T12:00:00"), score_reference_date=reference_date,
        created_by=u["admin_demo"].id, demo_data=True)
    db.add_all([m1, m2]); db.flush()
    m3 = SourceRecord(
        source_code="M3", course_id=c["线性代数"].id, title="M3 M2 的转载版本（合成演示数据）",
        author="未知转载者（演示）", url="https://example.org/demo-m3", source_type="external_answer",
        school=settings.app_school_name, course_name="线性代数", term="", claim_group="linear-algebra-final-review",
        content_excerpt="转载 M2 的建议，没有新增独立经验。", permission="abstract_allowed", status="active",
        duplicate_of_id=m2.id, link_status="demo_placeholder", published_at=dt("2025-03-10T12:00:00"), score_reference_date=reference_date,
        created_by=u["admin_demo"].id, demo_data=True)
    m4 = SourceRecord(
        source_code="M4", experience_id=exp_m4.id, course_id=c["线性代数"].id,
        title="M4 本校课程经验（合成演示数据）", author="演示学生 B（稳定记录标识）", school=settings.app_school_name,
        course_name="线性代数", term="2024秋", claim_group="linear-algebra-generic-review",
        content_excerpt="期末要提前复习。", permission="full_text_allowed", status="active", author_verified=True,
        has_concrete_scenario=False, has_actionable_detail=False,
        experience_date=dt("2024-09-01T12:00:00"), score_reference_date=reference_date,
        created_by=u["admin_demo"].id, demo_data=True)
    ds_source = SourceRecord(
        source_code="DEMO-DS-01", experience_id=exp_ds.id, course_id=c["数据结构"].id,
        title="数据结构复习经验（合成演示数据）", author="演示学生（稳定记录标识）", school=settings.app_school_name,
        course_name="数据结构", term="2026春", claim_group="data-structures-tree-graph-review",
        content_excerpt=exp_ds.raw_text, permission="full_text_allowed", status="active", author_verified=True,
        has_concrete_scenario=True, has_actionable_detail=True, experience_date=dt("2026-04-20T12:00:00"),
        created_by=u["admin_demo"].id, demo_data=True)
    dm_source = SourceRecord(
        source_code="DEMO-DM-01", experience_id=exp_dm.id, course_id=c["离散数学"].id,
        title="离散数学复习经验（合成演示数据）", author="演示学生（稳定记录标识）", school=settings.app_school_name,
        course_name="离散数学", term="2025秋", claim_group="discrete-math-review",
        content_excerpt=exp_dm.raw_text, permission="full_text_allowed", status="active", author_verified=True,
        has_concrete_scenario=True, has_actionable_detail=True, experience_date=dt("2025-10-18T12:00:00"),
        created_by=u["admin_demo"].id, demo_data=True)
    link_only = SourceRecord(
        source_code="DEMO-LINK-01", course_id=c["数据结构"].id, title="仅可展示链接的外部资料（合成演示数据）",
        author="来源方未核验", url="https://example.org/link-only-demo", source_type="external_answer",
        school=settings.app_school_name, course_name="数据结构", term="2026春", claim_group="data-structures-reference",
        content_excerpt="",
        permission="link_only", status="active", link_status="demo_placeholder", author_verified=False, published_at=dt("2026-01-01T12:00:00"),
        created_by=u["admin_demo"].id, demo_data=True)
    db.add_all([m3, m4, ds_source, dm_source, link_only])
    db.flush()

    # Add synthetic, clearly labelled, approved demonstration entries so the local prototype
    # can exercise multi-course / multi-term search without inventing real student research.
    bulk_specs = [
        ("线性代数", "2025秋", "复习矩阵运算时，先用小规模数值例子检查计算步骤，再核对符号。"),
        ("线性代数", "2026春", "复习向量空间时，先区分定义、判定条件与典型反例。"),
        ("线性代数", "2025秋", "遇到线性方程组题目，可以先判断解的存在性，再进行消元。"),
        ("线性代数", "2026春", "练习特征值问题时，将计算过程与几何解释分开记录。"),
        ("线性代数", "2025春", "复习正交与投影时，配合图示检查向量关系。"),
        ("线性代数", "2026春", "整理错题时，记录错误原因和可重复使用的检查步骤。"),
        ("线性代数", "2025秋", "计算行列式前先确认矩阵阶数和可用性质。"),
        ("线性代数", "2026秋", "学习线性变换时，先写清输入、输出和所选基。"),
        ("线性代数", "2025春", "复习二次型时，将配方法与矩阵表示对应起来。"),
        ("数据结构", "2025秋", "复习链表时，画出节点、指针和边界情况再写代码。"),
        ("数据结构", "2026春", "练习栈与队列时，为每一步操作记录状态变化。"),
        ("数据结构", "2025秋", "比较排序算法时，同时记录稳定性、复杂度和适用场景。"),
        ("数据结构", "2026春", "理解二叉树遍历时，先手工写出一棵小树的访问次序。"),
        ("数据结构", "2025春", "练习图算法时，区分顶点集合、边集合和访问标记。"),
        ("数据结构", "2026春", "分析哈希表时，分别考虑冲突处理与装载因子。"),
        ("数据结构", "2025秋", "复习递归时，先说明终止条件，再检查每层参数变化。"),
        ("数据结构", "2026秋", "调试算法时，记录最小输入、预期输出和实际输出。"),
        ("数据结构", "2025春", "学习堆时，用数组下标标记父子节点关系。"),
        ("离散数学", "2025秋", "练习命题逻辑时，使用真值表核验等价变形。"),
        ("离散数学", "2026春", "复习集合运算时，分别检查元素属于关系和集合包含关系。"),
        ("离散数学", "2025秋", "写证明题时，先列出已知条件、目标和允许使用的定义。"),
        ("离散数学", "2025春", "学习关系性质时，用小集合构造满足或不满足的例子。"),
        ("离散数学", "2026春", "复习计数问题时，先判断顺序是否重要以及是否允许重复。"),
        ("离散数学", "2025秋", "练习归纳证明时，分别写出基础情形、归纳假设和归纳步骤。"),
        ("离散数学", "2026秋", "整理图论概念时，把定义、性质和反例放在同一张复习卡中。"),
    ]
    bulk_experiences = []
    term_date = {"2025春": "2025-04-15T12:00:00", "2025秋": "2025-10-15T12:00:00", "2026春": "2026-04-15T12:00:00", "2026秋": "2026-10-15T12:00:00"}
    for idx, (course_name, term, text) in enumerate(bulk_specs, start=1):
        exp = Experience(
            course_id=c[course_name].id, submitter_id=u["contributor_demo"].id, term=term,
            raw_text=f"演示合成经验（第{idx:02d}条）：{text}",
            original_raw_text=f"演示合成经验（第{idx:02d}条）：{text}",
            difficulty="演示字段：具体难点须由真实贡献者确认", assignments="未提及", assessment="未提及",
            advice=text, status="published", confirmed=True, ai_mode="演示数据", demo_data=True,
            created_at=dt(term_date[term]), updated_at=dt(term_date[term]))
        bulk_experiences.append((idx, course_name, term, text, exp))
    db.add_all([item[4] for item in bulk_experiences]); db.flush()
    bulk_sources = []
    for idx, course_name, term, text, exp in bulk_experiences:
        bulk_sources.append(SourceRecord(
            source_code=f"DEMO-BULK-{idx:02d}", experience_id=exp.id, course_id=c[course_name].id,
            title=f"演示课程经验 {idx:02d}（合成数据）", author=f"演示贡献者 {idx:02d}（合成身份）",
            school=settings.app_school_name, course_name=course_name, term=term,
            claim_group=f"demo-bulk-claim-{idx:02d}", content_excerpt=exp.raw_text,
            permission="full_text_allowed", status="active", author_verified=True,
            has_concrete_scenario=True, has_actionable_detail=True,
            experience_date=dt(term_date[term]), score_reference_date=reference_date,
            created_by=u["admin_demo"].id, demo_data=True))
    db.add_all(bulk_sources)
    db.add(SystemSetting(key="score_weights", value={"A": 0.40, "S": 0.25, "T": 0.20, "D": 0.15}, version="V1.0", updated_by=u["admin_demo"].id))
    db.commit()
