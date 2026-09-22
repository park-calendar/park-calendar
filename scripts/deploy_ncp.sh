#!/usr/bin/env bash
# NCP Object Storage 에 달력을 배포한다.
#
# 사전 준비 (1회)
#   aws configure --profile ncp
#     AWS Access Key ID     : NCP 콘솔 > 마이페이지 > 계정 관리 > 인증키 관리 의 Access Key
#     AWS Secret Access Key : 같은 화면의 Secret Key
#     Default region name   : kr-standard
#     Default output format : json
#
# 사용법
#   NCP_BUCKET=버킷이름 ./scripts/deploy_ncp.sh          # index.html + data/ 전체 업로드
#   NCP_BUCKET=버킷이름 ./scripts/deploy_ncp.sh data     # data/ 만 업로드 (루틴용)
#
set -euo pipefail

BUCKET="${NCP_BUCKET:?NCP_BUCKET 환경변수에 버킷 이름을 넣어주세요}"
PROFILE="${NCP_PROFILE:-ncp}"
ENDPOINT="${NCP_ENDPOINT:-https://kr.object.ncloudstorage.com}"
MODE="${1:-all}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

AWS=(aws --profile "$PROFILE" --endpoint-url "$ENDPOINT")

echo "▶ bucket=$BUCKET profile=$PROFILE mode=$MODE"

# data/*.json : 항상 최신을 읽도록 no-cache
"${AWS[@]}" s3 sync "$ROOT/data" "s3://$BUCKET/data" \
  --exclude "*" --include "*.json" \
  --acl public-read \
  --content-type "application/json; charset=utf-8" \
  --cache-control "no-cache" \
  --delete

if [[ "$MODE" == "all" ]]; then
  "${AWS[@]}" s3 cp "$ROOT/index.html" "s3://$BUCKET/index.html" \
    --acl public-read \
    --content-type "text/html; charset=utf-8" \
    --cache-control "no-cache"
fi

echo "✔ 업로드 완료"
echo "  파일 URL : $ENDPOINT/$BUCKET/index.html"
echo "  웹사이트 : 콘솔의 '정적 웹 사이트 호스팅' 에 표시된 버킷 웹 사이트 엔드포인트"
