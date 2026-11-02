"""装扮查询的解析与摘要测试（离线，不联网）。"""

from pathlib import Path

import pytest

from snowluma_reverse.dress import (
    DressError,
    build_dress_url,
    extract_material,
    format_summary,
    parse_async_data,
    pick,
    summarize,
)

FIXTURE = Path(__file__).parent / "fixtures" / "aio_dress_10002000.html"


@pytest.fixture(scope="module")
def payload():
    return parse_async_data(FIXTURE.read_text(encoding="utf-8", errors="replace"))


def test_build_dress_url_carries_target_uin():
    url = build_dress_url(10001000)

    assert "targetUin=10001000" in url
    assert "chatId=10001000" in url
    assert url.startswith("https://zb.vip.qq.com/v2/pages/aioDressPage?")


def test_parse_rejects_html_without_async_data():
    with pytest.raises(DressError) as exc:
        parse_async_data("<html><body>redirect to ptlogin</body></html>")

    assert exc.value.kind == "parse"


def test_parse_reads_real_page(payload):
    assert payload["targetUin"] == "10002000"
    assert isinstance(payload["rawUsingList"], list)


def test_bubble_is_not_filtered_out(payload):
    data = summarize(payload)
    bubble = pick(data["items"], 2)

    assert bubble is not None, "appId=2 气泡不应被过滤"
    assert bubble["kind"] == "气泡"
    assert bubble["item_id"] == 2136042
    assert bubble["name"] == "简约克莱因"


def test_bubble_material_has_nine_slice_slices(payload):
    data = summarize(payload)
    bubble = pick(data["items"], 2)

    slices = bubble["material"]
    assert {"左上角", "右上角", "左下角", "右下角", "上边", "下边", "左边", "右边", "中心"} <= set(slices)
    assert slices["左上角"].startswith("https://tianquan.gtimg.cn/immersive/bubble/2136042/")


def test_extract_material_ignores_broken_json():
    assert extract_material({"extraappinfo": {"extraInfo": {"immersiveMaterial": "{not json"}}}) == {}
    assert extract_material({}) == {}


def test_format_summary_mentions_bubble(payload):
    text = format_summary(summarize(payload), "小鲸鱼")

    assert "小鲸鱼" in text
    assert "气泡：简约克莱因" in text
    assert "九宫格切片" in text
