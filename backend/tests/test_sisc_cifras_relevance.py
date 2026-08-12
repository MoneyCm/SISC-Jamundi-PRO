from services.sisc_cifras_service import calculate_relevance, pct_change


def test_pct_change_handles_zero_previous():
    assert pct_change(10, 0) is None
    assert pct_change(15, 10) == 50


def test_relevance_rewards_change_volume_and_quality():
    validated = calculate_relevance(
        value=40,
        variation_percentage=35,
        priority=1.0,
        quality_status="VALIDADO",
    )
    incomplete = calculate_relevance(
        value=40,
        variation_percentage=35,
        priority=1.0,
        quality_status="INCOMPLETO",
    )
    not_publishable = calculate_relevance(
        value=40,
        variation_percentage=35,
        priority=1.0,
        quality_status="NO PUBLICABLE",
    )

    assert validated > incomplete > not_publishable
    assert not_publishable == 0
