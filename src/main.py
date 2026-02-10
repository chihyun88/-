from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class CollateralBasicInfo:
    address: str | None
    owner: str | None
    appraised_value: int | None
    prior_mortgage_amount: int
    usage: str | None


@dataclass
class ReviewInput:
    requested_loan_amount: int
    borrower_credit_grade: int
    purpose: str


@dataclass
class LtvResult:
    gross_ltv: float | None
    net_ltv: float | None


def _to_int(value: str | None) -> int | None:
    if not value:
        return None
    digits = re.sub(r"[^0-9]", "", value)
    return int(digits) if digits else None


def parse_registry_document(raw_text: str) -> CollateralBasicInfo:
    patterns = {
        "address": r"소재지\s*[:：]?\s*(.+)",
        "owner": r"소유자\s*[:：]?\s*(.+)",
        "appraised_value": r"(감정가|시가표준액)\s*[:：]?\s*([0-9,원\s]+)",
        "prior_mortgage_amount": r"(근저당권\s*채권최고액|선순위\s*담보)\s*[:：]?\s*([0-9,원\s]+)",
        "usage": r"용도\s*[:：]?\s*(.+)",
    }

    def match_line(pattern: str, group: int = 1) -> str | None:
        m = re.search(pattern, raw_text)
        return m.group(group).strip() if m else None

    appraised_value_raw = match_line(patterns["appraised_value"], group=2)
    prior_mortgage_raw = match_line(patterns["prior_mortgage_amount"], group=2)

    return CollateralBasicInfo(
        address=match_line(patterns["address"]),
        owner=match_line(patterns["owner"]),
        appraised_value=_to_int(appraised_value_raw),
        prior_mortgage_amount=_to_int(prior_mortgage_raw) or 0,
        usage=match_line(patterns["usage"]),
    )


def calculate_ltv(collateral: CollateralBasicInfo, review: ReviewInput) -> LtvResult:
    if not collateral.appraised_value or collateral.appraised_value <= 0:
        return LtvResult(gross_ltv=None, net_ltv=None)

    gross_ltv = review.requested_loan_amount / collateral.appraised_value * 100
    net_ltv = (
        (review.requested_loan_amount + collateral.prior_mortgage_amount)
        / collateral.appraised_value
        * 100
    )
    return LtvResult(gross_ltv=round(gross_ltv, 2), net_ltv=round(net_ltv, 2))


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_internal_policy(
    collateral: CollateralBasicInfo,
    review: ReviewInput,
    ltv: LtvResult,
    policy: dict[str, Any],
) -> list[str]:
    notes: list[str] = []

    max_ltv = policy.get("max_ltv", 70)
    if ltv.net_ltv is None:
        notes.append("LTV 산출 불가: 감정가/시가표준액을 확인하세요.")
    elif ltv.net_ltv > max_ltv:
        notes.append(f"내부 LTV 한도({max_ltv}%) 초과")
    else:
        notes.append("내부 LTV 한도 충족")

    banned_usage = set(policy.get("restricted_usage", []))
    if collateral.usage and collateral.usage in banned_usage:
        notes.append(f"제한 용도 자산: {collateral.usage}")

    min_credit_grade = policy.get("min_credit_grade", 5)
    if review.borrower_credit_grade > min_credit_grade:
        notes.append(
            f"신용등급 기준 미달(요구: {min_credit_grade}등급 이내, 입력: {review.borrower_credit_grade})"
        )

    if collateral.prior_mortgage_amount > 0:
        notes.append(f"선순위 담보 존재: {collateral.prior_mortgage_amount:,}원")

    if len(notes) == 1 and notes[0] == "내부 LTV 한도 충족":
        notes.append("추가 검토 이슈 없음")

    return notes


def recommend_lenders(
    ltv: LtvResult,
    review: ReviewInput,
    lenders: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if ltv.net_ltv is None:
        return []

    candidates: list[dict[str, Any]] = []
    for lender in lenders:
        max_ltv = lender.get("max_ltv", 0)
        min_credit = lender.get("min_credit_grade", 10)
        supported_purpose = lender.get("supported_purpose", [])

        if ltv.net_ltv <= max_ltv and review.borrower_credit_grade <= min_credit:
            if not supported_purpose or review.purpose in supported_purpose:
                candidates.append(lender)

    candidates.sort(key=lambda x: x.get("priority", 999))
    return candidates


def build_report(
    collateral: CollateralBasicInfo,
    review: ReviewInput,
    ltv: LtvResult,
    notes: list[str],
    lenders: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "담보기본정보": asdict(collateral),
        "심사입력": asdict(review),
        "LTV": asdict(ltv),
        "내부검토사항": notes,
        "추천금융사": lenders,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="부동산담보대출 심사 보조 프로그램")
    parser.add_argument("--registry-text", required=True, help="등기부등본 텍스트 파일 경로")
    parser.add_argument("--loan-amount", type=int, required=True, help="신청 대출금액(원)")
    parser.add_argument("--credit-grade", type=int, required=True, help="차주 신용등급(숫자, 낮을수록 우량)")
    parser.add_argument("--purpose", required=True, help="대출목적(예: 생활안정, 사업자금)")
    parser.add_argument(
        "--policy-config",
        default="src/config/internal_policy.json",
        help="내부조견표 JSON",
    )
    parser.add_argument(
        "--lender-config",
        default="src/config/lenders.json",
        help="외부 금융사 조견표 JSON",
    )

    args = parser.parse_args()

    raw_text = Path(args.registry_text).read_text(encoding="utf-8")
    policy = _load_json(Path(args.policy_config))
    lenders = _load_json(Path(args.lender_config)).get("lenders", [])

    collateral = parse_registry_document(raw_text)
    review = ReviewInput(
        requested_loan_amount=args.loan_amount,
        borrower_credit_grade=args.credit_grade,
        purpose=args.purpose,
    )
    ltv = calculate_ltv(collateral, review)
    notes = evaluate_internal_policy(collateral, review, ltv, policy)
    recommended = recommend_lenders(ltv, review, lenders)

    report = build_report(collateral, review, ltv, notes, recommended)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
