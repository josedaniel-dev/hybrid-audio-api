from cache_manager import compute_contract_signature
from config import (
    stem_label_name,
    stem_label_developer,
    stem_label_script,
)


def test_contract_signature_changes():
    """
    Signatures must differ when ANY significant field differs.
    """
    s1 = compute_contract_signature("hi", "v1", "sonic-3")
    s2 = compute_contract_signature("hi", "v2", "sonic-3")

    assert s1 != s2, "Signature must change when voice_id changes"


def test_contract_signature_stable():
    """
    Signatures must remain identical when all inputs are identical.
    """
    s1 = compute_contract_signature("text", "vx", "sonic-3")
    s2 = compute_contract_signature("text", "vx", "sonic-3")

    assert s1 == s2, "Signature must remain stable for identical parameters"


# ---------------------------------------------------------
# NEW v5.2 Tests — ensure subdirectory-aware labels
# ---------------------------------------------------------

def test_signature_differs_by_label_type():
    """
    Similar text, same voice/model — BUT different label category:
    stem.name.* vs stem.developer.* vs stem.script.* 
    MUST yield different signatures because storage paths differ.
    """

    name_label = stem_label_name("john")
    dev_label = stem_label_developer("john")
    script_label = stem_label_script("john")

    s_name = compute_contract_signature("john", name_label, "sonic-3")
    s_dev = compute_contract_signature("john", dev_label, "sonic-3")
    s_script = compute_contract_signature("john", script_label, "sonic-3")

    # All three must be distinct
    assert s_name != s_dev
    assert s_name != s_script
    assert s_dev != s_script


def test_signature_consistent_across_directory_resolution():
    """
    Label → category → subdirectory must not alter signature
    as long as label, voice_id and model_id do not change.
    """

    label1 = stem_label_script("alpha")
    label2 = stem_label_script("alpha")  # identical

    s1 = compute_contract_signature("hello", label1, "sonic-3")
    s2 = compute_contract_signature("hello", label2, "sonic-3")

    assert s1 == s2, "Signatures must be identical for equivalent labels"
