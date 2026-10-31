def test_health_and_seed_records(client):
    assert client.get("/api/health").status_code == 200
    courses = client.get("/api/courses").json()
    assert len(courses) >= 3
    assert {c["name"] for c in courses} >= {"线性代数", "数据结构", "离散数学"}


def test_credibility_example_matches_requirements(client):
    course = next(c for c in client.get("/api/courses").json() if c["name"] == "线性代数")
    rows = client.get(f"/api/credibility?course_id={course['id']}").json()["results"]
    by_code = {row["source_code"]: row for row in rows}
    assert by_code["M1"]["score"] == 87.5
    assert by_code["M1"]["score_a"] == 80
    assert by_code["M1"]["score_s"] == 100
    assert by_code["M1"]["score_t"] == 100
    assert by_code["M1"]["score_d"] == 70
    assert by_code["M1"]["most_credible"] is True
    assert by_code["M2"]["score"] == 81.0
    assert by_code["M2"]["grade"] == "较高"
    assert by_code["M4"]["score"] == 57.0
    assert by_code["M3"]["score"] is None
    assert by_code["M3"]["most_credible"] is False


def test_search_hides_unpublished_negative_record(client):
    courses = client.get("/api/courses").json()
    network = next(c for c in courses if c["name"] == "计算机网络")
    response = client.get(f"/api/search?course_id={network['id']}&term=2025秋&q=负向测试记录")
    assert response.status_code == 200
    assert response.json()["count"] == 0


def test_only_link_sources_never_enter_qa_context(client):
    courses = client.get("/api/courses").json()
    ds = next(c for c in courses if c["name"] == "数据结构")
    search = client.get(f"/api/search?course_id={ds['id']}&term=2026春&q=仅可展示链接")
    assert any(x["source_code"] == "DEMO-LINK-01" for x in search.json()["results"])
    answer = client.post("/api/qa", json={"question":"请提供仅可展示链接的外部资料正文", "course_id":ds["id"], "term":"2026春"})
    assert answer.status_code == 200
    assert all(c["source_code"] != "DEMO-LINK-01" for c in answer.json()["citations"])


def test_qa_without_evidence_does_not_invent_citations(client):
    response = client.post("/api/qa", json={"question":"量子拓扑超级测验课程的特殊评分细则是什么"})
    assert response.status_code == 200
    body = response.json()
    assert body["citations"] == []
    assert "暂未找到足够" in body["answer"]


def test_submit_confirm_review_publish_cycle(client, tokens):
    headers = tokens("contributor_demo")
    courses = client.get("/api/courses").json()
    course = next(c for c in courses if c["name"] == "离散数学")
    created = client.post("/api/experiences", headers=headers, json={
        "course_id": course["id"], "term":"2026秋", "raw_text":"我复习离散数学时会先整理定义，再逐步写出证明过程，遇到逻辑题会先画真值表。"
    })
    assert created.status_code == 200, created.text
    exp = created.json()["experience"]
    assert exp["raw_text"].startswith("我复习离散数学")
    assert exp["status"] == "draft"
    assert created.json()["saved_original_first"] is True
    confirmed = client.post(f"/api/experiences/{exp['id']}/confirm", headers=headers, json={
        "difficulty":"逻辑题容易遗漏步骤", "assignments":"未提及", "assessment":"未提及", "advice":"先整理定义，再逐步写出证明过程，先画真值表", "confirm":True
    })
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["experience"]["status"] == "pending_review"
    reviewer = tokens("reviewer_demo")
    decision = client.post(f"/api/experiences/{exp['id']}/review", headers=reviewer, json={
        "action":"approve", "claim_group":"离散数学-证明题复习方法", "reason":"示例验收：内容适宜公开", "unresolved_conflict":False
    })
    assert decision.status_code == 200, decision.text
    assert decision.json()["experience"]["status"] == "published"
    search = client.get(f"/api/search?course_id={course['id']}&term=2026秋&q=真值表")
    assert any(x["experience_id"] == exp["id"] for x in search.json()["results"])


def test_contributor_without_login_is_blocked(client):
    response = client.post("/api/experiences", json={"course_id":1,"term":"2026春","raw_text":"这是一条足够长的课程经验内容。"})
    assert response.status_code == 401


def test_reader_cannot_submit_or_administer_sources(client, tokens):
    reader = tokens("reader_demo")
    response = client.post("/api/experiences", headers=reader, json={"course_id":1,"term":"2026春","raw_text":"这是一条足够长的课程经验内容。"})
    assert response.status_code == 403
    response2 = client.post("/api/sources", headers=reader, json={"title":"Unauthorized source","claim_group":"test","permission":"pending"})
    assert response2.status_code == 403


def test_source_permission_revocation_removes_public_result(client, tokens):
    admin = tokens("admin_demo")
    courses = client.get("/api/courses").json()
    course = next(c for c in courses if c["name"] == "数据结构")
    created = client.post("/api/sources", headers=admin, json={
        "title":"权限撤销测试来源（合成测试）", "author":"测试作者", "url":"https://example.org/test-permission-revoke",
        "source_type":"external_answer", "course_id":course["id"], "term":"2026春",
        "claim_group":"ds-permission-test", "content_excerpt":"用来测试权限撤销后搜索不可见。",
        "permission":"abstract_allowed", "author_verified":True, "confirm_reviewed":True
    })
    assert created.status_code == 200, created.text
    source_id = created.json()["source"]["id"]
    assert client.get(f"/api/sources/{source_id}").status_code == 200
    updated = client.put(f"/api/sources/{source_id}/permission", headers=admin, json={"permission":"prohibited","reason":"测试权限撤销同步"})
    assert updated.status_code == 200
    assert client.get(f"/api/sources/{source_id}").status_code == 404
    search = client.get(f"/api/search?course_id={course['id']}&term=2026春&q=权限撤销测试来源")
    assert all(row["id"] != source_id for row in search.json()["results"])


def test_invalid_score_weight_sum_is_rejected(client, tokens):
    admin = tokens("admin_demo")
    response = client.put("/api/admin/scoring-config", headers=admin, json={"A":0.4,"S":0.25,"T":0.2,"D":0.2})
    assert response.status_code == 422


def test_link_only_does_not_disclose_body_in_search_or_detail(client):
    courses = client.get("/api/courses").json()
    ds = next(c for c in courses if c["name"] == "数据结构")
    response = client.get(f"/api/search?course_id={ds['id']}&term=2026春&q=仅可展示链接")
    link = next(x for x in response.json()["results"] if x["source_code"] == "DEMO-LINK-01")
    assert link.get("content_excerpt") in (None, "")
    assert "仅允许展示链接" in link.get("permission_note", "")
    detail = client.get(f"/api/sources/{link['id']}")
    assert detail.status_code == 200
    assert detail.json().get("content_excerpt") in (None, "")


def test_search_course_term_keyword_combination_is_exact(client):
    courses = client.get("/api/courses").json()
    linear = next(c for c in courses if c["name"] == "线性代数")
    ds = next(c for c in courses if c["name"] == "数据结构")
    expected = client.get(f"/api/search?course_id={linear['id']}&term=2026春&q=矩阵变换")
    assert expected.status_code == 200
    assert any(row["source_code"] == "M1" for row in expected.json()["results"])
    assert all(row["course_id"] == linear["id"] and row["term"] == "2026春" for row in expected.json()["results"])
    wrong_course = client.get(f"/api/search?course_id={ds['id']}&term=2026春&q=矩阵变换")
    assert wrong_course.json()["count"] == 0
    wrong_term = client.get(f"/api/search?course_id={linear['id']}&term=2024秋&q=矩阵变换")
    assert wrong_term.json()["count"] == 0


def test_scoring_rule_update_keeps_v1_snapshot(client, tokens):
    admin = tokens("admin_demo")
    updated = client.put("/api/admin/scoring-config", headers=admin, json={"A":0.4,"S":0.25,"T":0.2,"D":0.15})
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == "V2.0"
    old = client.get("/api/admin/scoring-config?version=V1.0", headers=admin)
    assert old.status_code == 200
    assert old.json()["weights"] == {"A":0.4,"S":0.25,"T":0.2,"D":0.15}


def test_demo_data_coverage_is_three_courses_two_terms_and_30_approved_sources(client):
    courses = client.get("/api/courses").json()
    assert len(courses) >= 3
    results = client.get("/api/search?limit=100").json()["results"]
    permitted = [r for r in results if r["permission"] in {"abstract_allowed", "full_text_allowed"} and r["status"] == "active"]
    assert len(permitted) >= 30
    assert len({r["course_name"] for r in permitted}) >= 3
    assert len({r["term"] for r in permitted if r["term"]}) >= 2
    assert sum(1 for r in permitted if r["demo_data"] is True) >= 30


def test_invalid_external_link_is_removed_from_search_and_qa(client, tokens):
    admin = tokens("admin_demo")
    course = next(c for c in client.get("/api/courses").json() if c["name"] == "离散数学")
    created = client.post("/api/sources", headers=admin, json={
        "title":"链接失效测试资料", "author":"测试作者", "url":"https://example.org/expired-test",
        "source_type":"external_answer", "course_id":course["id"], "term":"2025秋",
        "claim_group":"expired-link-test", "content_excerpt":"特定测试短语：失效链接应从公开回答中排除。",
        "permission":"abstract_allowed", "author_verified":True, "confirm_reviewed":True
    })
    assert created.status_code == 200, created.text
    sid = created.json()["source"]["id"]
    assert created.json()["source"]["link_status"] == "unchecked"
    updated = client.put(f"/api/sources/{sid}/link-status", headers=admin, json={"link_status":"invalid","reason":"自动化测试：标记无效链接"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["source"]["link_status"] == "invalid"
    assert client.get(f"/api/sources/{sid}").status_code == 404
    search = client.get(f"/api/search?course_id={course['id']}&q=特定测试短语")
    assert all(row["id"] != sid for row in search.json()["results"])
    qa = client.post("/api/qa", json={"question":"特定测试短语：失效链接应从公开回答中排除", "course_id":course["id"], "term":"2025秋"}).json()
    assert all(cite["id"] != sid for cite in qa.get("citations", []))


def test_contributor_cannot_review_own_submission(client, tokens):
    contributor = tokens("contributor_demo")
    course = next(c for c in client.get("/api/courses").json() if c["name"] == "线性代数")
    created = client.post("/api/experiences", headers=contributor, json={
        "course_id":course["id"], "term":"2026秋", "raw_text":"自审核权限测试：这段文字仅用于验证作者不能审核自己提交的记录。"
    })
    assert created.status_code == 200
    exp = created.json()["experience"]
    confirmed = client.post(f"/api/experiences/{exp['id']}/confirm", headers=contributor, json={
        "difficulty":"未提及", "assignments":"未提及", "assessment":"未提及", "advice":"未提及", "confirm":True
    })
    assert confirmed.status_code == 200
    denied = client.post(f"/api/experiences/{exp['id']}/review", headers=contributor, json={
        "action":"approve", "claim_group":"自审核测试主题", "reason":"不应有权限"
    })
    assert denied.status_code == 403


def test_answerable_question_has_locatable_permitted_citations(client):
    course = next(c for c in client.get("/api/courses").json() if c["name"] == "线性代数")
    result = client.post("/api/qa", json={"question":"线性代数期末复习可以怎么准备？", "course_id":course["id"]})
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["citations"]
    codes = {item["source_code"] for item in body["citations"]}
    assert "M1" in codes or "M2" in codes
    assert "M3" not in codes
    assert all(item.get("id") and item.get("source_code") and item.get("score") is not None for item in body["citations"])


def test_privacy_scan_blocks_publish_and_redaction_keeps_original_snapshot(client, tokens):
    contributor = tokens("contributor_demo")
    reviewer = tokens("reviewer_demo")
    course = next(c for c in client.get("/api/courses").json() if c["name"] == "离散数学")
    original = "隐私验收测试内容：我复习时先列定义和证明步骤。联系邮箱 test.student@example.com"
    created = client.post("/api/experiences", headers=contributor, json={
        "course_id":course["id"], "term":"2026秋", "raw_text":original
    })
    assert created.status_code == 200
    exp = created.json()["experience"]
    assert exp["author_visibility"] == "anonymous"
    assert exp["original_snapshot_kept"] is True
    assert "可能包含邮箱地址" in exp["privacy_warnings"]
    confirmed = client.post(f"/api/experiences/{exp['id']}/confirm", headers=contributor, json={
        "difficulty":"未提及", "assignments":"未提及", "assessment":"未提及", "advice":"先列定义和证明步骤", "confirm":True
    })
    assert confirmed.status_code == 200
    blocked = client.post(f"/api/experiences/{exp['id']}/review", headers=reviewer, json={
        "action":"approve", "claim_group":"离散数学-证明准备", "reason":"检查隐私保护"
    })
    assert blocked.status_code == 422
    returned = client.post(f"/api/experiences/{exp['id']}/review", headers=reviewer, json={
        "action":"return", "reason":"需先删除个人邮箱再送审"
    })
    assert returned.status_code == 200
    sanitized = "隐私验收测试内容：我复习时先列定义和证明步骤，练习时逐步检查推导过程。"
    edited = client.patch(f"/api/experiences/{exp['id']}", headers=contributor, json={"raw_text":sanitized})
    assert edited.status_code == 200
    assert edited.json()["experience"]["raw_text"] == sanitized
    assert edited.json()["experience"]["original_snapshot_kept"] is True
    assert edited.json()["experience"]["privacy_warnings"] == []
    confirmed2 = client.post(f"/api/experiences/{exp['id']}/confirm", headers=contributor, json={
        "difficulty":"证明步骤容易遗漏", "assignments":"未提及", "assessment":"未提及", "advice":"逐步检查推导过程", "confirm":True
    })
    assert confirmed2.status_code == 200
    approved = client.post(f"/api/experiences/{exp['id']}/review", headers=reviewer, json={
        "action":"approve", "claim_group":"离散数学-证明准备", "reason":"脱敏后通过审核"
    })
    assert approved.status_code == 200
    source_id = approved.json()["experience"]["source_id"]
    public_detail = client.get(f"/api/sources/{source_id}")
    assert public_detail.status_code == 200
    assert "test.student@example.com" not in public_detail.text
    assert public_detail.json()["author"] == "匿名贡献者"


def test_external_source_excerpt_with_email_is_rejected(client, tokens):
    admin = tokens("admin_demo")
    course = next(c for c in client.get("/api/courses").json() if c["name"] == "线性代数")
    response = client.post("/api/sources", headers=admin, json={
        "title":"含个人信息的测试来源", "url":"https://example.org/privacy-test", "course_id":course["id"],
        "source_type":"external_answer", "claim_group":"privacy-test", "content_excerpt":"咨询请联系 person@example.com",
        "permission":"abstract_allowed", "confirm_reviewed":True
    })
    assert response.status_code == 422


def test_p1_feedback_has_id_and_review_does_not_directly_mutate_source(client, tokens):
    contributor = tokens("contributor_demo")
    reviewer = tokens("reviewer_demo")
    reader = tokens("reader_demo")
    linear = next(c for c in client.get("/api/courses").json() if c["name"] == "线性代数")
    source = next(x for x in client.get(f"/api/search?course_id={linear['id']}&q=矩阵变换").json()["results"] if x["source_code"] == "M1")
    source_id = source["id"]
    before = client.get(f"/api/sources/{source_id}").json()
    submitted = client.post("/api/feedback", headers=contributor, json={
        "target_type": "source", "target_id": source_id, "category": "outdated",
        "description": "测试P1反馈：请人工核对该演示记录的适用时间。"
    })
    assert submitted.status_code == 200, submitted.text
    feedback = submitted.json()
    assert feedback["feedback_id"] > 0 and feedback["feedback_code"].startswith("FB-") and feedback["status"] == "pending"
    denied = client.patch(f"/api/feedback/{feedback['feedback_id']}", headers=reader, json={
        "status": "updated", "handling_note": "无权限的测试处理"
    })
    assert denied.status_code == 403
    handled = client.patch(f"/api/feedback/{feedback['feedback_id']}", headers=reviewer, json={
        "status": "updated", "handling_note": "已记录处理结果；内容变更仍须通过正式审核流程。"
    })
    assert handled.status_code == 200 and handled.json()["status"] == "updated"
    after = client.get(f"/api/sources/{source_id}").json()
    assert after["content_excerpt"] == before["content_excerpt"]
    listed = client.get("/api/feedback", headers=contributor).json()["results"]
    assert any(item["id"] == feedback["feedback_id"] and item["status"] == "updated" for item in listed)


def test_p1_maintenance_only_suggests_candidates_and_p2_metrics_are_aggregated(client, tokens):
    admin = tokens("admin_demo")
    reader = tokens("reader_demo")
    before = client.get("/api/search?limit=100").json()
    before_credibility = client.get("/api/credibility").json()
    candidates_response = client.get("/api/admin/maintenance/candidates", headers=admin)
    assert candidates_response.status_code == 200, candidates_response.text
    candidates = candidates_response.json()["results"]
    assert any(item["type"] == "expiry_review" for item in candidates)
    assert "无自动合并" in candidates_response.json()["note"]
    after = client.get("/api/search?limit=100").json()
    after_credibility = client.get("/api/credibility").json()
    assert before["count"] == after["count"]
    assert {x["source_code"]: x.get("score") for x in before_credibility["results"]} == {
        x["source_code"]: x.get("score") for x in after_credibility["results"]
    }
    metrics = client.get("/api/admin/metrics", headers=admin)
    assert metrics.status_code == 200, metrics.text
    metric_body = metrics.json()
    assert "published_experiences" in metric_body and "feedback_total" in metric_body
    assert "username" not in metric_body and "user_id" not in metric_body
    assert client.get("/api/admin/metrics", headers=reader).status_code == 403


def test_p1_configuration_change_is_logged_and_logs_are_admin_only(client, tokens):
    admin = tokens("admin_demo")
    reader = tokens("reader_demo")
    changed = client.put("/api/admin/scoring-config", headers=admin, json={"A": 0.4, "S": 0.25, "T": 0.2, "D": 0.15})
    assert changed.status_code == 200, changed.text
    logs = client.get("/api/admin/logs", headers=admin)
    assert logs.status_code == 200, logs.text
    assert any(item["action"] == "scoring_config.update" for item in logs.json()["operation_logs"])
    assert client.get("/api/admin/logs", headers=reader).status_code == 403

def test_cross_school_source_is_excluded_from_course_evidence(client, tokens):
    """回归测试：跨校资料不能作为本校课程事实证据。

    把一条有效来源的 school 设置为所选课程之外的学校，即使其 course_id 指向所选课程，
    也不得进入该本校课程的搜索结果、AI问答证据或可信度评分候选。
    """
    from app.database import SessionLocal
    from app.models import SourceRecord

    admin = tokens("admin_demo")
    course = next(c for c in client.get("/api/courses").json() if c["name"] == "线性代数")
    created = client.post("/api/sources", headers=admin, json={
        "title": "跨校隔离测试来源（合成测试）", "author": "外校作者", "url": "https://example.org/cross-school-test",
        "source_type": "external_answer", "course_id": course["id"], "term": "2026春",
        "claim_group": "linear-algebra-cross-school-isolation", "content_excerpt": "跨校隔离测试短语：此资料不应作为本校线性代数课程的事实证据。",
        "permission": "abstract_allowed", "author_verified": True, "confirm_reviewed": True
    })
    assert created.status_code == 200, created.text
    source_id = created.json()["source"]["id"]
    # 创建时 school 自动设为课程所在学校；现在直接将其改为外校，模拟 course_id 指向本校但适用学校为外校的情况。
    with SessionLocal() as db:
        record = db.get(SourceRecord, source_id)
        assert record is not None
        record.school = "外校测试学校（非本校）"
        db.commit()
    # 搜索：不应返回该跨校来源
    search = client.get(f"/api/search?course_id={course['id']}&term=2026春&q=跨校隔离测试短语")
    assert search.status_code == 200
    assert all(row["id"] != source_id for row in search.json()["results"]), "跨校来源不应出现在本校课程搜索结果中"
    # AI问答：不应引用该跨校来源
    qa = client.post("/api/qa", json={
        "question": "跨校隔离测试短语：此资料不应作为本校线性代数课程的事实证据。",
        "course_id": course["id"], "term": "2026春"
    })
    assert qa.status_code == 200
    assert all(cite["id"] != source_id for cite in qa.json().get("citations", [])), "跨校来源不应出现在本校课程AI问答证据中"
    # 可信度列表：不应包含该跨校来源
    credibility = client.get(f"/api/credibility?course_id={course['id']}").json()
    assert all(row.get("source_id") != source_id for row in credibility["results"]), "跨校来源不应出现在本校课程可信度候选中"


def test_same_school_permitted_source_still_usable_for_course(client, tokens):
    """回归测试：同课程、同适用学校的获准来源仍可正常使用。

    确认 school 与课程 school 一致的获准来源，仍能出现在搜索结果和可信度列表中。
    """
    admin = tokens("admin_demo")
    course = next(c for c in client.get("/api/courses").json() if c["name"] == "线性代数")
    created = client.post("/api/sources", headers=admin, json={
        "title": "同校适用测试来源（合成测试）", "author": "本校作者", "url": "https://example.org/same-school-test",
        "source_type": "external_answer", "course_id": course["id"], "term": "2026春",
        "claim_group": "linear-algebra-same-school-usable", "content_excerpt": "同校适用测试短语：此资料应能正常用于本校线性代数课程。",
        "permission": "abstract_allowed", "author_verified": True, "confirm_reviewed": True
    })
    assert created.status_code == 200, created.text
    source = created.json()["source"]
    source_id = source["id"]
    # 提供了 course_id，school 应自动设为课程所在学校
    assert source["school"] == course["school"], "提供 course_id 时来源 school 应与课程 school 一致"
    # 搜索：应返回该同校来源
    search = client.get(f"/api/search?course_id={course['id']}&term=2026春&q=同校适用测试短语")
    assert search.status_code == 200
    assert any(row["id"] == source_id for row in search.json()["results"]), "同校获准来源应出现在本校课程搜索结果中"
    # 可信度列表：应包含该同校来源
    credibility = client.get(f"/api/credibility?course_id={course['id']}").json()
    assert any(row.get("source_id") == source_id for row in credibility["results"]), "同校获准来源应出现在本校课程可信度候选中"

def test_empty_school_source_excluded_when_course_selected(client, tokens):
    """边界回归：来源 school 为空且选定课程时，不得作为该课程事实证据。

    需求 V1.0 第6.2节：来源学校为空且无法确认适用范围的资料，不得作为该课程事实的检索证据或可信度候选。
    """
    from app.database import SessionLocal
    from app.models import SourceRecord

    admin = tokens("admin_demo")
    course = next(c for c in client.get("/api/courses").json() if c["name"] == "线性代数")
    created = client.post("/api/sources", headers=admin, json={
        "title": "空学校隔离测试来源（合成测试）", "author": "未知学校作者", "url": "https://example.org/empty-school-test",
        "source_type": "external_answer", "course_id": course["id"], "term": "2026春",
        "claim_group": "linear-algebra-empty-school-isolation", "content_excerpt": "空学校隔离测试短语：来源学校为空不应作为本校课程事实证据。",
        "permission": "abstract_allowed", "author_verified": True, "confirm_reviewed": True
    })
    assert created.status_code == 200, created.text
    source_id = created.json()["source"]["id"]
    with SessionLocal() as db:
        record = db.get(SourceRecord, source_id)
        assert record is not None
        record.school = ""
        db.commit()
    search = client.get(f"/api/search?course_id={course['id']}&term=2026春&q=空学校隔离测试短语")
    assert search.status_code == 200
    assert all(row["id"] != source_id for row in search.json()["results"]), "school 为空的来源不应出现在本校课程搜索结果中"
    qa = client.post("/api/qa", json={
        "question": "空学校隔离测试短语：来源学校为空不应作为本校课程事实证据。",
        "course_id": course["id"], "term": "2026春"
    })
    assert qa.status_code == 200
    assert all(cite["id"] != source_id for cite in qa.json().get("citations", [])), "school 为空的来源不应出现在本校课程AI问答证据中"
    credibility = client.get(f"/api/credibility?course_id={course['id']}").json()
    assert all(row.get("source_id") != source_id for row in credibility["results"]), "school 为空的来源不应出现在本校课程可信度候选中"
