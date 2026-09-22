# 일일 조사 루틴 설계

목표: 매일 청라호수공원 행사를 조사해 새 행사·변경 사항이 있으면 `data/YYYY-MM.json` 에 병합하고 Object Storage 에 업로드한다.

## 파일 구조 (Object Storage 버킷도 동일)

```
index.html              달력 (수정 없음)
data/config.json        표시 범위·카테고리·월별 안내·최종 갱신일
data/2026-08.json       8월 시작 행사 목록   ← 루틴이 갱신하는 파일
data/2026-09.json
...
```

- 달력은 `config.range` 로 월 목록을 만들고 `data/YYYY-MM.json` 을 모두 읽습니다. 파일이 없는 달은 빈 달로 처리됩니다.
- 기간 행사는 **시작 월** 파일에 한 번만 넣습니다. 달력이 종료일까지 이어서 표시합니다.
- 범위를 늘릴 때는 `config.range.end` 만 바꾸면 됩니다 (예: `"2027-02"`).

## 루틴 1회 실행 순서

1. **현재 데이터 내려받기** (NCP Object Storage → 로컬 `data/`)
   ```bash
   aws --profile ncp --endpoint-url https://kr.object.ncloudstorage.com s3 sync s3://<버킷>/data ./data
   ```
2. **조사**: 아래 채널을 확인해 `data/*.json` 에 없는 행사, 또는 내용이 바뀐 행사(출연진 공개, 취소, 일정 변경)를 찾는다.
   - 인천시설공단 청라공원 공지·행사일정 https://www.insiseol.or.kr/park/cheongna/
   - 인천경제자유구역청 축제/행사 https://www.ifez.go.kr/main/culture/event/list.do
   - 서해구 전체행사 https://www.seohae.go.kr/open_content/festival/sub/event_all.jsp?view=2
   - 인천서해구문화재단 축제 https://www.iscf.kr/_new/html/event/festival.php
   - 청라닷컴 행사소식 https://www.cheongna.com/server/bbs/board.php?bo_table=sub_05_03
   - 뉴스 검색: `청라호수공원 행사`, `청라호수공원 축제`, `청라호수공원 공연`, `I♥FEsta 청라`, `청라페스티벌`
3. **결과를 JSON 으로 작성**: `scripts/new_events.sample.json` 형식. 새 행사가 없으면 `{"events": []}`.
   - 기존 행사를 고칠 때는 같은 `id` 를 쓰고 바뀐 필드만 넣는다.
   - 확정되지 않은 일정은 `"status": "tentative"`.
   - `sources` 에 반드시 출처 URL 을 넣는다.
4. **병합**
   ```bash
   python3 scripts/merge_events.py new_events.json
   ```
   마지막 줄이 `CHANGED=1` 이면 5번으로, `CHANGED=0` 이면 종료.
5. **업로드** (변경된 파일만)
   ```bash
   NCP_BUCKET=<버킷> ./scripts/deploy_ncp.sh data
   ```
   `index.html` 까지 올릴 때는 `./scripts/deploy_ncp.sh` (인자 없이). 화면을 고쳤을 때만 필요하다.

## 루틴(스케줄 에이전트)용 프롬프트 초안

```
당신은 인천 청라호수공원 행사 조사 담당입니다. 저장소 hosu_event 의 ROUTINE.md 를 따르세요.
1. data/*.json 을 읽어 이미 등록된 행사 목록을 파악합니다.
2. ROUTINE.md 의 채널을 웹 검색·조회해, 등록되지 않은 행사와 내용이 바뀐 행사를 찾습니다.
   조사 범위: 오늘부터 data/config.json 의 range.end 까지.
3. 결과를 new_events.json 으로 저장하고 python3 scripts/merge_events.py new_events.json 을 실행합니다.
4. CHANGED=1 이면 data/ 를 Object Storage 에 업로드하고, 추가·갱신된 행사 제목을 요약해 보고합니다.
   CHANGED=0 이면 "변경 없음"으로 보고합니다.
출처 없는 행사는 추가하지 않습니다. 호수공원 밖 행사는 category "nearby" 로만 넣습니다.
```

## NCP Object Storage 설정 체크리스트

- 버킷 생성 시 **암호화 설정 안 함** (암호화 버킷은 정적 웹사이트 호스팅 불가)
- 버킷 권한 관리에서 **전체 공개 → 공개**
- 버킷 옵션 메뉴 → **정적 웹 사이트 호스팅** → 인덱스 파일 `index.html`
- 업로드는 `scripts/deploy_ncp.sh` 사용 (객체마다 `public-read` ACL 과 `no-cache` 를 붙여 올림)
- `index.html` 과 `data/` 가 같은 버킷이므로 CORS 설정 불필요
- 엔드포인트 `https://kr.object.ncloudstorage.com`, 리전 `kr-standard`
