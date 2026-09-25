from services.sisc_cifras_pdf import _comparison_table, _styles, SUPPRESSED_LABEL


def test_comparison_table_suppresses_variation_when_cell_is_protected():
    table = _comparison_table(
        [
            {
                "indicator_name": "Homicidio",
                "value": 1,
                "comparison_value": 0,
                "variation_absolute": 1,
                "variation_percentage": None,
            }
        ],
        _styles(),
    )

    rendered_text = " ".join(
        cell.getPlainText()
        for row in table._cellvalues
        for cell in row
        if hasattr(cell, "getPlainText")
    )

    assert SUPPRESSED_LABEL in rendered_text
    assert "+1" not in rendered_text
    assert "No comparable" not in rendered_text


def test_comparison_table_suppresses_both_periods_when_one_period_is_protected():
    table = _comparison_table(
        [
            {
                "indicator_name": "Hurto a personas",
                "value": 3,
                "comparison_value": 14,
                "variation_absolute": -11,
                "variation_percentage": -78.6,
            }
        ],
        _styles(),
    )

    rendered_text = " ".join(
        cell.getPlainText()
        for row in table._cellvalues
        for cell in row
        if hasattr(cell, "getPlainText")
    )

    assert rendered_text.count(SUPPRESSED_LABEL) == 4
    assert "14" not in rendered_text
    assert "-11" not in rendered_text
    assert "-78.6%" not in rendered_text
