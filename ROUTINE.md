# 일일 조사 루틴 설계

목표: 매일 인천 주요 공원의 행사를 조사해 새 행사·변경 사항이 있으면 `data/<공원>/YYYY-MM.json` 에 병합하고 NCP Object Storage 에 업로드한다.

## 파일 구조 (버킷도 동일)

```
index.html                     달력 (공원 선택 UI 포함, 루틴은 건드리지 않음)
data/config.json               카테고리, 공원 목록, 공원별 표시 범위·월별 안내, 최종 갱신일
data/cheongna/2026-09.json     청라호수공원 9월 행사   ← 루틴이 갱신
data/songdo/2026-09.json       송도 센트럴파크 9월 행사 ← 루틴이 갱신
```

- 달력은 `config.json` 의 `parks` 를 읽어 공원 선택 메뉴를 만들고, 선택된 공원의 `range` 에 해당하는 월 파일을 모두 읽습니다.
- 파일이 없는 달은 빈 달로 처리되므로, 미리 만들어 둘 필요는 없습니다.
- 기간 행사는 **시작 월** 파일에 한 번만 넣습니다. 달력이 종료일까지 이어서 표시합니다.
- 범위 밖의 행사를 병합하면 `merge_events.py` 가 `range` 를 자동으로 넓힙니다. 새 달을 수동으로 열 필요가 없습니다.

## 조사 대상 공원

| id | 이름 | 위치 |
|---|---|---|
| `cheongna` | 청라호수공원 | 인천 서구 청라국제도시 |
| `songdo` | 송도 센트럴파크 | 인천 연수구 송도국제도시 |

## 실행 주체

매일 오전 8시(KST)에 **이 Mac의 예약 작업**(`【매일 08:00】인천 공원 행사 업데이트`)이 실행합니다.
Claude 데스크톱 앱이 켜져 있어야 하며, 꺼져 있었다면 다음 실행 시 수행됩니다.

### 클라우드 루틴을 쓰지 않는 이유

2026-09-22 실측 결과, Claude 클라우드 샌드박스의 egress 프록시는 기본 거부에 개발 인프라만 허용합니다.

| 대상 | 결과 |
|---|---|
| WebSearch | 동작 |
| github.com, raw.githubusercontent.com, pypi.org | 통과 |
| kr.object.ncloudstorage.com | 차단 |
| insiseol.or.kr, ifez.go.kr | 차단 (WebFetch 도 EGRESS_BLOCKED) |

버킷뿐 아니라 조사 대상 공식 사이트까지 막혀 원문 교차 확인이 불가능하므로 클라우드는 적합하지 않습니다.
옮기려면 환경의 egress 허용 목록에 위 도메인들을 추가해야 하며, 조직 관리자 권한이 필요할 수 있습니다.

## 루틴 1회 실행 순서

1. **저장소 최신화**
   ```bash
   git pull --rebase origin main
   ```
2. **조사**: 공원별로 아래 채널을 확인해, 등록되지 않은 행사와 내용이 바뀐 행사를 찾습니다.

   공통
   - 인천경제자유구역청 축제/행사 https://www.ifez.go.kr/main/culture/event/list.do
   - 인천관광공사, 인천광역시 주요행사정보 https://www.incheon.go.kr/IC010501

   청라호수공원
   - 인천시설공단 청라공원 https://www.insiseol.or.kr/park/cheongna/
   - 행사일정 달력 `https://www.insiseol.or.kr/park_cheongna/scheduleCalendar.do?year_month=YYYY-MM&siteDiv=park_cheongna&schDiv=main`
   - 서구 전체행사 https://www.seohae.go.kr/open_content/festival/sub/event_all.jsp?view=2
   - 인천서구문화재단 https://www.iscf.kr/_new/html/event/festival.php
   - 청라닷컴 행사소식 https://www.cheongna.com/server/bbs/board.php?bo_table=sub_05_03

   송도 센트럴파크
   - 인천시설공단 송도공원 https://www.insiseol.or.kr/park/songdo/
   - 행사일정 달력 `https://www.insiseol.or.kr/park_songdo/scheduleCalendar.do?year_month=YYYY-MM&siteDiv=park_songdo&schDiv=main`
   - 연수구청 행사 안내

   웹 검색어: `<공원명> 행사`, `<공원명> 축제`, `<공원명> 공연`, `<공원명> YYYY년 M월`, `I♥FEsta 청라`, `I♥FEsta 송도`

3. **결과 작성**: 공원마다 별도 파일로 저장합니다 (`new_cheongna.json`, `new_songdo.json`). 형식은 `scripts/new_events.sample.json` 참고. 새 내용이 없으면 `{"events": []}`.
4. **병합**
   ```bash
   python3 scripts/merge_events.py --park cheongna new_cheongna.json
   python3 scripts/merge_events.py --park songdo   new_songdo.json
   ```
   두 실행의 마지막 줄이 모두 `CHANGED=0` 이면 업로드를 생략합니다.
5. **배포**
   ```bash
   git add data/ && git commit -m "행사 일정 갱신" && git push origin main
   ```
   GitHub Pages 가 1분 안에 반영합니다. 주소: https://park-calendar.github.io/park-calendar/

6. **보고**: 공원별 추가·갱신 내역, 업로드 결과, 보류한 후보를 요약합니다.

## 권한

루틴이 승인 창에서 멈추지 않도록 `.claude/settings.json` 에 허용 규칙을 두었습니다.
웹 검색·조회, 프로젝트 스크립트 실행, `data/` 편집은 자동 허용입니다.
아래는 계속 차단되며 사람이 확인해야 합니다.

`sudo`, `rm -rf`, 직접 `aws` 호출, `git push`, `gh`, `ssh`, `scp`, `index.html` 편집, `.env`·AWS 자격증명 읽기.

## 공휴일

`data/holidays.json` 에 2026~2027년 공휴일이 들어 있습니다. 루틴은 이 파일을 건드리지 않습니다.
2028년치가 필요하면 직접 추가하세요. 두 가지를 주의하세요.

- 현충일은 국경일이 아니어서 **대체공휴일 대상이 아닙니다.**
- 제헌절(7/17)은 2026년 법 개정으로 **공휴일로 재지정**되었고 대체공휴일도 적용됩니다.

## 조사 품질 규칙

- **연도를 반드시 확인합니다.** 검색 결과에 과거 연도 기사가 많이 섞입니다. 기사 작성일과 본문 연도를 확인하고, 애매하면 추가하지 말고 보류 후보로 보고합니다.
- 출처 URL 이 없는 행사는 추가하지 않습니다.
- 장소가 공원 내부인 행사만 일반 카테고리로 넣고, 공원 밖이지만 해당 지역에 영향이 큰 행사는 `nearby` 로 넣습니다.
- 이미 등록된 행사는 실제로 바뀐 내용이 있을 때만 같은 `id` 로 바뀐 필드만 갱신합니다.
- 확정되지 않은 일정은 `status: "tentative"`.
- **행사가 없다는 안내(monthNotes)는 쓰지 않습니다.** "확인되지 않았습니다" 같은 문구는 보는 사람에게 도움이 되지 않습니다. 빈 달은 비워 두세요. monthNotes 는 공원 폐쇄·공사·장소 변경처럼 방문자가 실제로 알아야 할 일이 있을 때만 씁니다.

## 알려진 함정: PutObject AccessDenied

AWS CLI 2.23+ / boto3 1.36+ 는 업로드마다 CRC32 무결성 체크섬을 기본으로 붙이는데, NCP Object Storage 는 이를 지원하지 않고 **AccessDenied** 로 응답한다. 권한 문제로 오인하기 쉽다.
판별법: `copy-object` 는 되는데 `put-object` 만 AccessDenied 면 이 문제다 (복사도 쓰기 작업이므로 권한은 정상).
해결은 배포 스크립트에 이미 적용되어 있다. 직접 CLI 를 쓸 때는:
```bash
export AWS_REQUEST_CHECKSUM_CALCULATION=when_required
export AWS_RESPONSE_CHECKSUM_VALIDATION=when_required
```

## NCP Object Storage 설정 체크리스트

- 버킷 생성 시 **암호화 설정 안 함** (암호화 버킷은 정적 웹사이트 호스팅 불가)
- 버킷 권한 관리에서 **전체 공개 → 공개**
- 버킷 옵션 메뉴 → **정적 웹 사이트 호스팅** → 인덱스 파일 `index.html`
- 업로드 스크립트가 객체마다 `public-read` ACL 과 `no-cache` 를 붙임
- `index.html` 과 `data/` 가 같은 버킷이므로 CORS 설정 불필요
- 엔드포인트 `https://kr.object.ncloudstorage.com`, 리전 `kr-standard`
- 인증: 환경변수 `NCP_ACCESS_KEY` / `NCP_SECRET_KEY`, 또는 AWS CLI 프로필 `ncp`
