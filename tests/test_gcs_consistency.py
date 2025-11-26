# Tests for the GCS consistency engine (v2 functions)

def test_compare_category_v2():
    """
    Ensures the compare_category_v2 function returns the required structure.
    """
    from gcs_consistency import compare_category_v2

    result = compare_category_v2("name")

    assert "category" in result
    assert "local_count" in result
    assert "gcs_count" in result
    assert "matches" in result
    assert "local_only" in result
    assert "gcs_only" in result
    assert "missing" in result


def test_summarize_all_categories_v2():
    """
    Ensures summarize_all_categories_v2 returns structured category data.
    """
    from gcs_consistency import summarize_all_categories_v2

    summary = summarize_all_categories_v2()

    assert "categories" in summary
    assert isinstance(summary["categories"], dict)
