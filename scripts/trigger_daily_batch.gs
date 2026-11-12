/**
 * ============================================================================
 * [방어선 4] LS 수급·차트 스크리너 평일 20:30 KST 정각 외부 웹훅 트리거 (Google Apps Script)
 * ============================================================================
 * GitHub Actions 내장 schedule(cron) 지연·드롭 및 GitHub App 푸시 제약을 100% 우회하여,
 * 평일(월~금) 저녁 20:30 KST 정각에 GitHub REST API(workflow_dispatch)를 즉시 호출합니다.
 *
 * [3분 설정 방법]
 * 1. GitHub 우측 상단 프로필 → Settings → Developer settings → Personal access tokens → Fine-grained tokens
 *    - Token name: ls-stock-screener-trigger
 *    - Repository access: Only select repositories → minseok2995-ai/ls-stock-screener 선택
 *    - Permissions → Repository permissions → Actions: "Read and write" 선택 후 토큰 발급
 * 2. https://script.google.com 접속 → [새 프로젝트] 생성 → 본 파일 내용을 붙여넣고 저장(Ctrl+S)
 *    - 좌측 톱니바퀴 [프로젝트 설정] → 시간대를 "(GMT+09:00) 한국 표준시 - 서울 (Asia/Seoul)"로 확인
 *    - 같은 화면 하단 [스크립트 속성] → [스크립트 속성 추가]:
 *      · 속성: GITHUB_PAT
 *      · 값:   발급받은 github_pat_... 토큰 문자열 붙여넣기 후 저장
 * 3. 상단 함수 선택 드롭다운에서 `setupDaily2030Trigger` 선택 후 [실행] 클릭 (최초 1회 권한 승인)
 *    → 매일 20:30 KST 정각 자동 실행 트리거가 즉시 등록됩니다 (주말은 코드 내부에서 자동 스킵).
 */

const GITHUB_OWNER = 'minseok2995-ai';
const GITHUB_REPO = 'ls-stock-screener';
const WORKFLOW_FILE = 'daily_batch.yml';
const TARGET_BRANCH = 'main';

/**
 * 평일(월~금) 20:30 KST에 실행되어 GitHub Actions `daily_batch.yml`을 트리거합니다.
 * - `skip_if_completed: "true"`를 함께 전달하므로 GitHub 내장 Cron(20:30/20:47/21:17 KST)과
 *   동시에 겹치더라도 concurrency 직렬화 + 98.5% 완주 멱등성 가드에 의해 단 1회만 실행됩니다.
 */
function triggerDailyStockBatch() {
  const nowKst = new Date(
    Utilities.formatDate(new Date(), 'Asia/Seoul', "yyyy-MM-dd'T'HH:mm:ss")
  );
  const dayOfWeek = nowKst.getDay(); // 0: 일요일, 1~5: 월~금, 6: 토요일
  if (dayOfWeek === 0 || dayOfWeek === 6) {
    console.log('[SKIP] 주말(토/일)이므로 배치를 호출하지 않습니다: ' + nowKst.toISOString());
    return;
  }

  dispatchWorkflow_({
    mode: 'daily',
    max_stocks: '0',
    skip_if_completed: 'true',
  });
}

/**
 * 수동 테스트용 함수 (주말 여부 및 기완주 여부와 무관하게 즉시 강제 실행 테스트 시 사용)
 */
function testTriggerForceNow() {
  dispatchWorkflow_({
    mode: 'daily',
    max_stocks: '0',
    skip_if_completed: 'false',
  });
}

/**
 * 최초 1회 실행하여 매일 20:30 KST 시간 기반 트리거를 자동 등록하는 헬퍼 함수
 */
function setupDaily2030Trigger() {
  const triggers = ScriptApp.getProjectTriggers();
  for (let i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'triggerDailyStockBatch') {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }

  ScriptApp.newTrigger('triggerDailyStockBatch')
    .timeBased()
    .everyDays(1)
    .atHour(20)
    .nearMinute(30)
    .inTimezone('Asia/Seoul')
    .create();

  console.log('[완료] 매일 20:30 KST (평일 자동 판별) triggerDailyStockBatch 트리거가 등록되었습니다.');
}

/**
 * GitHub REST API workflow_dispatch 호출 내부 유틸리티
 * (만약 원격 daily_batch.yml에 아직 skip_if_completed 입력이 반영되기 전이면 자동으로 기본 입력으로 폴백 호출)
 */
function dispatchWorkflow_(inputsObj) {
  const pat = PropertiesService.getScriptProperties().getProperty('GITHUB_PAT');
  if (!pat || !pat.trim()) {
    throw new Error(
      '스크립트 속성(Script Properties)에 GITHUB_PAT이 설정되어 있지 않습니다. [프로젝트 설정 > 스크립트 속성]에서 GITHUB_PAT을 추가해 주세요.'
    );
  }

  // POST /repos/minseok2995-ai/ls-stock-screener/actions/workflows/daily_batch.yml/dispatches
  const url =
    'https://api.github.com/repos/' +
    GITHUB_OWNER +
    '/' +
    GITHUB_REPO +
    '/actions/workflows/' +
    WORKFLOW_FILE +
    '/dispatches';

  const sendRequest = function (inputsPayload) {
    return UrlFetchApp.fetch(url, {
      method: 'post',
      contentType: 'application/json',
      headers: {
        Accept: 'application/vnd.github+json',
        Authorization: 'Bearer ' + pat.trim(),
        'X-GitHub-Api-Version': '2022-11-28',
      },
      payload: JSON.stringify({
        ref: TARGET_BRANCH,
        inputs: inputsPayload,
      }),
      muteHttpExceptions: true,
    });
  };

  let resp = sendRequest(inputsObj);
  let status = resp.getResponseCode();
  let body = resp.getContentText();

  // 구버전 워크플로우 YAML(skip_if_completed 미선언 상태) 호환 폴백
  if (status === 422 && body.indexOf('skip_if_completed') !== -1) {
    console.warn('원격 daily_batch.yml에 skip_if_completed 입력이 없어 기본 입력(mode, max_stocks)으로 재호출합니다.');
    resp = sendRequest({
      mode: inputsObj.mode || 'daily',
      max_stocks: inputsObj.max_stocks || '0',
    });
    status = resp.getResponseCode();
    body = resp.getContentText();
  }

  if (status === 204) {
    console.log('[성공] GitHub Actions daily_batch.yml 디스패치 완료 (HTTP 204)');
  } else {
    throw new Error('GitHub Actions 디스패치 실패 (HTTP ' + status + '): ' + body);
  }
}
