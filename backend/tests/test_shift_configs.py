"""班次检查项组合、历史快照与跨班次可比折算的接口测试。"""

from tests.conftest import shift_items


def _create_restroom(client, name: str = "班次测试公厕") -> dict:
    response = client.post(
        "/api/v1/restrooms",
        json={"name": name, "district": "班次区", "address": "测试路 9 号"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _config(client, shift: str) -> dict:
    return client.get(f"/api/v1/shift-check-configs/{shift}").json()


def test_default_shift_combos_differ(client):
    configs = {item["shift"]: item for item in client.get("/api/v1/shift-check-configs").json()}
    assert list(configs) == ["早班", "中班", "晚班"]
    assert configs["早班"]["version"] == 1
    assert len(configs["早班"]["check_items"]) == 8
    assert len(configs["中班"]["check_items"]) == 6
    assert len(configs["晚班"]["check_items"]) == 6
    assert configs["中班"]["comparable_covered"] is True


def test_config_change_only_affects_later_submissions(client, restroom):
    middle_v1 = _config(client, "中班")["check_items"]

    # 调整前提交一条中班巡查（v1，6 项）
    before = client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": restroom["id"],
            "inspector": "赵快照",
            "shift": "中班",
            "items": shift_items(client, "中班", 8),
        },
    ).json()
    before_score = before["score"]
    assert before["check_config_version"] == 1
    assert before["check_items"] == middle_v1

    # 调整中班组合：移除「耗材补充」，版本 +1
    new_combo = [name for name in middle_v1 if name != "耗材补充"]
    updated = client.put(
        "/api/v1/shift-check-configs/中班",
        json={"check_items": new_combo, "updated_by": "管理员", "remark": "中班不再查耗材"},
    ).json()
    assert updated["version"] == 2
    assert updated["check_items"] == new_combo
    assert updated["updated_by"] == "管理员"

    # 历史记录仍按提交当时的组合快照展示与算分，未被回改
    history = client.get(f"/api/v1/inspections/{before['id']}").json()
    assert history["check_items"] == middle_v1
    assert history["items"] and len(history["items"]) == 6
    assert history["score"] == before_score
    assert history["check_config_version"] == 1

    # 旧组合提交被拒，新组合才能提交；新记录绑定 v2 快照
    stale = client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": restroom["id"],
            "inspector": "赵快照",
            "shift": "中班",
            "items": [{"name": name, "score": 8} for name in middle_v1],
        },
    )
    assert stale.status_code == 400

    after = client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": restroom["id"],
            "inspector": "赵快照",
            "shift": "中班",
            "items": [{"name": name, "score": 8} for name in new_combo],
        },
    ).json()
    assert after["check_config_version"] == 2
    assert after["check_items"] == new_combo


def test_record_cannot_mix_old_and_new_combo(client, restroom):
    # 仅改班次不整套重提检查项 → 拒绝，避免一条记录跨两版组合
    created = client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": restroom["id"],
            "inspector": "钱一致",
            "shift": "中班",
            "items": shift_items(client, "中班", 9),
        },
    ).json()
    shift_only = client.patch(
        f"/api/v1/inspections/{created['id']}", json={"shift": "早班"}
    )
    assert shift_only.status_code == 400

    # 连检查项一起按早班当前组合整套重提才允许改班次
    ok = client.patch(
        f"/api/v1/inspections/{created['id']}",
        json={"shift": "早班", "items": shift_items(client, "早班", 7)},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["shift"] == "早班"
    assert len(body["check_items"]) == 8


def test_config_validation(client):
    original = _config(client, "晚班")["check_items"]
    # 空组合
    assert client.put("/api/v1/shift-check-configs/晚班", json={"check_items": []}).status_code == 422
    # 不存在的检查项
    bad_name = client.put(
        "/api/v1/shift-check-configs/晚班",
        json={"check_items": original[:-1] + ["不存在的项目"]},
    )
    assert bad_name.status_code == 400
    # 重复项
    duplicate = client.put(
        "/api/v1/shift-check-configs/晚班",
        json={"check_items": original + [original[0]]},
    )
    assert duplicate.status_code == 400
    # 与当前一致无需调整
    same = client.put("/api/v1/shift-check-configs/晚班", json={"check_items": original})
    assert same.status_code == 400
    # 不存在的班次
    assert client.get("/api/v1/shift-check-configs/夜班").status_code == 404


def _set_scores(names: list[str], scores: dict[str, float]) -> list[dict]:
    return [{"name": name, "score": scores.get(name, 9)} for name in names]


def test_cross_shift_average_uses_fixed_comparable_items(client):
    room = _create_restroom(client, "折算测试公厕")
    basis_before = client.get("/api/v1/stats/dashboard").json()["score_basis"]

    comparable = ["地面与台阶清洁", "便池蹲位清洁", "垃圾清运"]
    # 早班：3 个可比项均 10 → 可比得分 100；非可比项压到 0 也不影响折算
    morning_names = _config(client, "早班")["check_items"]
    morning_scores = {name: (10 if name in comparable else 0) for name in morning_names}
    # 中班：3 个可比项均 5 → 可比得分 50；非可比项给 10
    middle_names = _config(client, "中班")["check_items"]
    middle_scores = {name: (5 if name in comparable else 10) for name in middle_names}

    client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": room["id"],
            "inspector": "孙折算",
            "shift": "早班",
            "items": _set_scores(morning_names, morning_scores),
        },
    )
    client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": room["id"],
            "inspector": "孙折算",
            "shift": "中班",
            "items": _set_scores(middle_names, middle_scores),
        },
    )

    detail = client.get(f"/api/v1/restrooms/{room['id']}").json()
    # (100 + 50) / 2 = 75，按固定可比项目折算而非各自组合的原始均分
    assert detail["avg_score"] == 75.0
    assert detail["avg_score_included_count"] == 2
    assert detail["avg_score_excluded_count"] == 0

    # 全库口径：两条都纳入；折算依据随接口返回
    basis_after = client.get("/api/v1/stats/dashboard").json()["score_basis"]
    assert basis_after["comparable_items"] == comparable
    assert basis_after["included_count"] == basis_before["included_count"] + 2
    assert "可比项目" in basis_after["rule"]

    # 同一批数据重复计算结果唯一，不会因取值不同出现两个均分
    again = client.get("/api/v1/stats/dashboard").json()["score_basis"]
    overview_a = client.get("/api/v1/stats/overview").json()["avg_score_week"]
    overview_b = client.get("/api/v1/stats/overview").json()["avg_score_week"]
    assert again == basis_after
    assert overview_a == overview_b


def test_records_missing_comparable_items_are_excluded_deterministically(client, restroom):
    # 把晚班组合改成不覆盖任何固定可比项
    night_new = ["洗手台与镜面", "通风除臭", "耗材补充", "工具与标识摆放", "墙面门窗卫生"]
    updated = client.put(
        "/api/v1/shift-check-configs/晚班",
        json={"check_items": night_new, "remark": "晚班不再覆盖基础可比项"},
    ).json()
    assert updated["comparable_covered"] is False

    basis_before = client.get("/api/v1/stats/dashboard").json()["score_basis"]

    # 新晚班记录没有可比项 → 不纳入折算，但仍可正常提交、按自身 5 项算分
    created = client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": restroom["id"],
            "inspector": "李剔除",
            "shift": "晚班",
            "items": [{"name": name, "score": 7} for name in night_new],
        },
    ).json()
    assert created["score"] == 70.0
    assert created["check_items"] == night_new

    basis_after = client.get("/api/v1/stats/dashboard").json()["score_basis"]
    assert basis_after["included_count"] == basis_before["included_count"]
    assert basis_after["excluded_count"] == basis_before["excluded_count"] + 1

    # 同一批数据两次折算结果一致（口径固定，不随当前配置漂移）
    basis_once_more = client.get("/api/v1/stats/dashboard").json()["score_basis"]
    assert basis_once_more == basis_after
