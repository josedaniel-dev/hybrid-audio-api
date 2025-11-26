# Tests for list_bucket_contents_v2

def test_list_bucket_contents_v2():
    """
    Ensures the bucket listing function returns a list.
    """
    from gcs_audit import list_bucket_contents_v2

    items = list_bucket_contents_v2(prefix="")
    assert isinstance(items, list)
