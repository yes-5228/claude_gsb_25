"""接口级测试：覆盖台账、巡查、问题整改与统计看板。"""

from datetime import datetime, timedelta

from tests.conftest import full_items


def test_health_and_dictionaries(client):
    assert client.get("/health").json()["status"] == "ok"
    payload = client.get("/api/v1/meta/dictionaries").json()
    assert "待整改" in payload["issue_status"]
    assert len(payload["inspection_check_items"]) == 8
    assert set(payload["shift_checklists"]) == {"早班", "中班", "晚班"}
    assert payload["shift_checklists"]["早班"] != payload["shift_checklists"]["晚班"]
    assert payload["issue_transitions"]["待整改"] == ["整改中", "已关闭"]


def test_restroom_crud_and_delete_guard(client, restroom):
    assert restroom["code"].startswith("WC-")

    listed = client.get("/api/v1/restrooms", params={"district": "测试区"}).json()
    assert listed["meta"]["total"] >= 1

    detail = client.get(f"/api/v1/restrooms/{restroom['id']}").json()
    assert detail["inspection_count"] == 0
    assert detail["open_issue_count"] == 0

    updated = client.patch(
        f"/api/v1/restrooms/{restroom['id']}", json={"status": "维修中", "manager": "新责任人"}
    ).json()
    assert updated["status"] == "维修中"
    assert updated["manager"] == "新责任人"

    # 存在关联数据时不允许直接删除
    client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": restroom["id"],
            "inspector": "测试巡查员",
            "shift": "早班",
            "items": full_items(9),
        },
    )
    blocked = client.delete(f"/api/v1/restrooms/{restroom['id']}")
    assert blocked.status_code == 409

    ok = client.delete(f"/api/v1/restrooms/{restroom['id']}", params={"force": "true"})
    assert ok.status_code == 200
    assert client.get(f"/api/v1/restrooms/{restroom['id']}").status_code == 404


def test_inspection_scoring_and_filter(client, restroom):
    good = client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": restroom["id"],
            "inspector": "李巡查",
            "shift": "中班",
            "items": full_items(9, "中班"),
            "remark": "整体良好",
        },
    ).json()
    assert good["score"] == 90.0
    assert good["grade"] == "优秀"
    assert good["result"] == "正常"

    bad_items = full_items(9, "晚班")
    bad_items[0]["score"] = 3
    bad_items[0]["remark"] = "地面污渍"
    bad = client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": restroom["id"],
            "inspector": "李巡查",
            "shift": "晚班",
            "items": bad_items,
        },
    ).json()
    assert bad["result"] == "发现问题"
    assert bad["score"] < 90

    filtered = client.get(
        "/api/v1/inspections", params={"result": "发现问题", "restroom_id": restroom["id"]}
    ).json()
    assert filtered["meta"]["total"] == 1
    assert filtered["items"][0]["id"] == bad["id"]
    assert filtered["items"][0]["restroom"]["name"] == restroom["name"]

    today = datetime.now().date().isoformat()
    ranged = client.get(
        "/api/v1/inspections", params={"date_from": today, "date_to": today}
    ).json()
    assert ranged["meta"]["total"] == 2

    duplicate = full_items(5) + [{"name": "地面与台阶清洁", "score": 4}]
    rejected = client.post(
        "/api/v1/inspections",
        json={"restroom_id": restroom["id"], "inspector": "李巡查", "items": duplicate},
    )
    assert rejected.status_code == 400

    empty = client.post(
        "/api/v1/inspections",
        json={"restroom_id": restroom["id"], "inspector": "李巡查", "items": []},
    )
    assert empty.status_code == 422


def test_issue_lifecycle(client, restroom):
    inspection = client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": restroom["id"],
            "inspector": "王巡查",
            "items": full_items(4),
        },
    ).json()

    issue = client.post(
        "/api/v1/issues",
        json={
            "restroom_id": restroom["id"],
            "inspection_id": inspection["id"],
            "title": "地面污渍未清理",
            "description": "巡查发现地面有明显污渍",
            "category": "保洁不到位",
            "severity": "严重",
            "reporter": "王巡查",
            "assignee": "保洁班组",
            "deadline": (datetime.now() - timedelta(days=1)).isoformat(),
        },
    ).json()
    assert issue["status"] == "待整改"
    assert len(issue["records"]) == 1
    assert issue["records"][0]["action"] == "上报问题"

    # 越级流转被拒绝：待整改 -> 已完成
    invalid = client.post(
        f"/api/v1/issues/{issue['id']}/transitions",
        json={"to_status": "已完成", "operator": "值班长"},
    )
    assert invalid.status_code == 400
    assert "不允许流转" in invalid.json()["detail"]

    options = client.get(f"/api/v1/issues/{issue['id']}/transitions").json()
    assert {option["status"] for option in options} == {"整改中", "已关闭"}

    processing = client.post(
        f"/api/v1/issues/{issue['id']}/transitions",
        json={"to_status": "整改中", "operator": "保洁班组张伟", "remark": "已安排清洗"},
    ).json()
    assert processing["status"] == "整改中"
    assert processing["assignee"] == "保洁班组"

    reviewing = client.post(
        f"/api/v1/issues/{issue['id']}/transitions",
        json={"to_status": "待验收", "operator": "保洁班组张伟", "remark": "整改完成待验收"},
    ).json()
    assert reviewing["status"] == "待验收"

    # 验收驳回回到整改中
    rejected = client.post(
        f"/api/v1/issues/{issue['id']}/transitions",
        json={"to_status": "整改中", "operator": "王巡查", "remark": "角落仍有残留"},
    ).json()
    assert rejected["status"] == "整改中"
    assert rejected["records"][-1]["action"] == "验收驳回"

    for target in ("待验收", "已完成", "已关闭"):
        payload = {"to_status": target, "operator": "值班长", "remark": f"流转到{target}"}
        response = client.post(f"/api/v1/issues/{issue['id']}/transitions", json=payload)
        assert response.status_code == 200, response.text
    final = response.json()
    assert final["status"] == "已关闭"
    assert final["closed_at"] is not None
    assert [record["to_status"] for record in final["records"]][-1] == "已关闭"

    closed_record = client.post(
        f"/api/v1/issues/{issue['id']}/records",
        json={"action": "整改进度", "operator": "值班长", "remark": "补充说明"},
    )
    assert closed_record.status_code == 400

    overdue = client.get("/api/v1/issues", params={"overdue": "true"}).json()
    assert overdue["meta"]["total"] == 0

    # 巡查记录可反查关联问题数量
    detail = client.get(f"/api/v1/inspections/{inspection['id']}").json()
    assert detail["issue_count"] == 1


def test_issue_requires_matching_restroom(client, restroom):
    other = client.post(
        "/api/v1/restrooms",
        json={"name": "另一座公厕", "district": "测试区", "address": "测试路 2 号"},
    ).json()
    inspection = client.post(
        "/api/v1/inspections",
        json={"restroom_id": other["id"], "inspector": "周巡查", "items": full_items(9)},
    ).json()
    mismatch = client.post(
        "/api/v1/issues",
        json={
            "restroom_id": restroom["id"],
            "inspection_id": inspection["id"],
            "title": "关联错误",
        },
    )
    assert mismatch.status_code == 400
    assert "不一致" in mismatch.json()["detail"]


def test_dashboard_stats(client, restroom):
    payload = client.get("/api/v1/stats/dashboard", params={"trend_days": 7}).json()
    overview = payload["overview"]
    assert overview["restroom_total"] >= 1
    assert overview["inspection_total"] >= 1
    assert len(payload["inspection_trend"]) == 7
    assert {item["name"] for item in payload["issue_by_status"]} == {
        "待整改",
        "整改中",
        "待验收",
        "已完成",
        "已关闭",
    }
    assert payload["top_restrooms"]
    assert "rectification_rate" in overview


def test_shift_checklists_versioning(client, restroom):
    # 各班次默认组合不同，初始版本均为 v1
    checklists = client.get("/api/v1/meta/checklists").json()
    by_shift = {row["shift"]: row for row in checklists}
    assert set(by_shift) == {"早班", "中班", "晚班"}
    assert all(row["version"] == 1 for row in checklists)
    assert by_shift["早班"]["items"] != by_shift["晚班"]["items"]
    morning_items = by_shift["早班"]["items"]

    # 组合外的项目提交被拒（通风除臭不在早班默认组合内）
    extra = full_items(9, "早班") + [{"name": "通风除臭", "score": 8}]
    response = client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": restroom["id"],
            "inspector": "李巡查",
            "shift": "早班",
            "items": extra,
        },
    )
    assert response.status_code == 400

    # 缺项同样被拒
    response = client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": restroom["id"],
            "inspector": "李巡查",
            "shift": "早班",
            "items": full_items(9, "早班")[1:],
        },
    )
    assert response.status_code == 400

    # 正常创建：绑定 v1，按组合顺序展开
    created = client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": restroom["id"],
            "inspector": "李巡查",
            "shift": "早班",
            "items": full_items(9, "早班"),
        },
    ).json()
    assert created["checklist_version"] == 1
    assert [item["name"] for item in created["items"]] == morning_items
    assert created["score"] == 90.0

    # 调整早班组合 → 生成 v2，只对之后的录入生效
    new_items = ["地面与台阶清洁", "便池蹲位清洁", "垃圾清运"]
    updated = client.put("/api/v1/meta/checklists/早班", json={"items": new_items}).json()
    assert updated["version"] == 2
    assert updated["items"] == new_items

    # 新录入按 v2 校验展开；仍按旧组合提交会被拒绝
    newer = client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": restroom["id"],
            "inspector": "李巡查",
            "shift": "早班",
            "items": [{"name": name, "score": 10} for name in new_items],
        },
    ).json()
    assert newer["checklist_version"] == 2
    assert [item["name"] for item in newer["items"]] == new_items
    assert newer["score"] == 100.0

    stale = client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": restroom["id"],
            "inspector": "李巡查",
            "shift": "早班",
            "items": full_items(9, "早班"),
        },
    )
    assert stale.status_code == 400

    # 历史记录仍按提交时的组合展示与算分
    old = client.get(f"/api/v1/inspections/{created['id']}").json()
    assert old["checklist_version"] == 1
    assert [item["name"] for item in old["items"]] == morning_items
    assert old["score"] == 90.0

    # 旧记录改分：项集合必须仍是原组合，不能混入新组合的项目
    rejected = client.patch(
        f"/api/v1/inspections/{created['id']}",
        json={"items": [{"name": name, "score": 8} for name in new_items]},
    )
    assert rejected.status_code == 400

    # 单独改班次被拒：需同时按新班次组合重新提交打分
    shift_only = client.patch(f"/api/v1/inspections/{created['id']}", json={"shift": "中班"})
    assert shift_only.status_code == 400

    # 组合校验：池外项目、空组合、重复项、未知班次
    assert (
        client.put("/api/v1/meta/checklists/早班", json={"items": ["不存在的项"]}).status_code
        == 400
    )
    assert client.put("/api/v1/meta/checklists/早班", json={"items": []}).status_code == 422
    assert (
        client.put(
            "/api/v1/meta/checklists/早班", json={"items": ["垃圾清运", "垃圾清运"]}
        ).status_code
        == 400
    )
    assert (
        client.put("/api/v1/meta/checklists/夜班", json={"items": ["垃圾清运"]}).status_code
        == 400
    )

    # 组合无变化时不产生新版本；历史版本可回溯
    again = client.put("/api/v1/meta/checklists/早班", json={"items": new_items}).json()
    assert again["version"] == 2
    history = client.get("/api/v1/meta/checklists/history", params={"shift": "早班"}).json()
    assert [row["version"] for row in history] == [2, 1]

    # 恢复早班默认组合，避免影响后续用例（生成 v3）
    from app.core.constants import DEFAULT_SHIFT_CHECKLISTS

    restored = client.put(
        "/api/v1/meta/checklists/早班", json={"items": DEFAULT_SHIFT_CHECKLISTS["早班"]}
    ).json()
    assert restored["items"] == DEFAULT_SHIFT_CHECKLISTS["早班"]


def test_shift_comparison(client, restroom):
    # 可比项目 = 三个班次现行组合的交集（默认组合下为这三项）
    payload = client.get("/api/v1/stats/shift-comparison").json()
    assert payload["comparable_items"] == ["地面与台阶清洁", "便池蹲位清洁", "垃圾清运"]
    assert payload["rule_note"]

    # 用同一批原始数据按固定规则手算，验证接口折算结果
    all_items = client.get("/api/v1/inspections", params={"page_size": 100}).json()["items"]
    comparable = set(payload["comparable_items"])
    for row in payload["shifts"]:
        records = [item for item in all_items if item["shift"] == row["shift"]]
        assert row["inspection_count"] == len(records)
        picked = []
        for record in records:
            scores = [entry["score"] for entry in record["items"] if entry["name"] in comparable]
            if scores:
                picked.append(sum(scores) / (len(scores) * 10) * 100)
        expected = round(sum(picked) / len(picked), 1) if picked else 0.0
        assert row["comparable_avg_score"] == expected
        raw = [record["score"] for record in records]
        assert row["avg_score"] == (round(sum(raw) / len(raw), 1) if raw else 0.0)

    # 同一批数据重复调用，折算结果完全一致，不会出现两个均分
    again = client.get("/api/v1/stats/shift-comparison").json()
    assert again == payload
