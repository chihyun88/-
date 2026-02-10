# 부동산담보대출 심사 프로그램 (프로토타입)

인터넷등기소 기본양식 등기부등본에서 추출한 텍스트를 입력받아 아래를 자동 산출합니다.

- 담보기본정보 파싱
- LTV 계산(단순 LTV, 선순위 반영 LTV)
- 자사 내부조견표 기반 검토사항 도출
- 타사 조견표 기반 추천 금융사 목록 제시

## 빠른 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/main.py \
  --registry-text sample/registry_sample.txt \
  --loan-amount 300000000 \
  --credit-grade 5 \
  --purpose 생활안정
```

## 입력 포맷

현재 버전은 등기부등본 **텍스트 추출 결과**를 입력으로 받습니다.
(실제 PDF/HWP 업로드 및 OCR은 다음 단계 확장 포인트)

필수 라벨 예시:

- `소재지:`
- `소유자:`
- `용도:`
- `감정가:` 또는 `시가표준액:`
- `근저당권 채권최고액:` 또는 `선순위 담보:`

## 룰 커스터마이징

- 내부조견표: `src/config/internal_policy.json`
- 금융사 조견표: `src/config/lenders.json`

운영에 맞게 JSON 값만 수정하면 심사 기준과 추천 결과를 바꿀 수 있습니다.
