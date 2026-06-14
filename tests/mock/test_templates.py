from process_opt.mock.templates import DEVICE_TEMPLATES


def test_all_templates_have_array_results():
    for dtype, tmpl in DEVICE_TEMPLATES.items():
        assert isinstance(tmpl["results"], list), f"{dtype}: results should be a list"
        for item in tmpl["results"]:
            assert "name" in item
            assert "value" in item
            assert "result" in item
            assert "usl" in item
            assert "lsl" in item


def test_template_result_names_match_old_keys():
    for dtype, tmpl in DEVICE_TEMPLATES.items():
        for item in tmpl["results"]:
            assert item["result"] in ("pass", "fail")
            assert item["lsl"] <= item["value"] <= item["usl"], \
                f"{dtype}.{item['name']}: value must be within specs"
