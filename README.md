# 인천 공원 행사 달력

청라호수공원과 송도 센트럴파크의 행사 일정을 달력으로 보여줍니다. 제목을 클릭해 공원을 전환합니다.

| 경로 | 역할 |
|---|---|
| `index.html` | 달력 화면. `data/` 의 JSON 을 읽어 렌더링 |
| `data/config.json` | 카테고리, 공원 목록, 공원별 표시 범위·월별 안내, 최종 갱신일 |
| `data/<공원>/YYYY-MM.json` | 해당 공원의 월별 행사 목록. **루틴이 갱신하는 파일** |
| `data/holidays.json` | 대한민국 공휴일(2026~2027). 달력에 빨간 날짜와 이름으로 표시 |
| `.claude/settings.json` | 루틴이 승인 없이 돌도록 하는 권한 규칙 |
| `scripts/merge_events.py` | 새 행사 JSON 을 월 파일에 병합(중복 제거·갱신) |
| `scripts/new_events.sample.json` | 루틴이 만들어야 하는 입력 형식 예시 |
| `scripts/deploy_ncp.sh` | NCP 업로드, AWS CLI 사용 (`NCP_BUCKET=버킷 ./scripts/deploy_ncp.sh`) |
| `scripts/deploy_ncp.py` | NCP 업로드·내려받기, boto3 사용 (클라우드 루틴용) |
| `ROUTINE.md` | 일일 조사 루틴 절차와 NCP 설정 체크리스트 |

## 로컬에서 보기
브라우저는 `file://` 에서 JSON 읽기를 막으므로 간단한 서버로 띄웁니다.
```bash
python3 -m http.server 8765
```
그 다음 http://localhost:8765 접속. Object Storage 정적 호스팅에 올리면 서버 없이 바로 열립니다.

## 행사 추가·수정
1. `scripts/new_events.sample.json` 형식으로 `new_events.json` 작성
2. `python3 scripts/merge_events.py --park cheongna new_events.json`
3. 새로 고침 (Object Storage 라면 `data/` 업로드)

행사 필드: `id`(생략 시 자동), `title`, `short`, `category`(festival·concert·sports·facility·regular·nearby), `start`, `end`, `time`, `place`, `host`, `summary`, `details[]`, `fee`, `contact`, `status`(confirmed·tentative·ended), `sources[{label,url}]`, `note`.

## NCP Object Storage 배포
1. 콘솔에서 버킷 생성(암호화 없음) → 권한 관리 전체 공개 → 정적 웹 사이트 호스팅(인덱스 `index.html`)
2. 인증키 등록: `aws configure --profile ncp` (리전 `kr-standard`)
3. 업로드: `NCP_BUCKET=pjs ./scripts/deploy_ncp.sh`
4. 데이터만 갱신할 때: `NCP_BUCKET=pjs ./scripts/deploy_ncp.sh data`

현재 배포 주소: http://pjs.s3-website.kr.object.ncloudstorage.com
