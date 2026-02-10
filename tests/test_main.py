from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.main import (  # noqa: E402
    ReviewInput,
    calculate_ltv,
    parse_registry_document,
)


def test_parse_registry_document_basic():
    text = """
    소재지: 부산광역시 해운대구 APT 101동
    소유자: 김철수
    용도: 아파트
    감정가: 900,000,000원
    근저당권 채권최고액: 100,000,000원
    """
    result = parse_registry_document(text)
    assert result.address == "부산광역시 해운대구 APT 101동"
    assert result.owner == "김철수"
    assert result.appraised_value == 900000000
    assert result.prior_mortgage_amount == 100000000


def test_calculate_ltv():
    collateral = parse_registry_document(
        "감정가: 1,000,000,000원\n근저당권 채권최고액: 200,000,000원"
    )
    review = ReviewInput(requested_loan_amount=300000000, borrower_credit_grade=4, purpose="생활안정")
    ltv = calculate_ltv(collateral, review)
    assert ltv.gross_ltv == 30.0
    assert ltv.net_ltv == 50.0
