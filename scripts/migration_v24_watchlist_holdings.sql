-- =====================================================================
-- v2.4 마이그레이션: 영구제외 · 관심종목 · 보유종목(청산 히스토리) 테이블 3종
-- Supabase 대시보드 > SQL Editor 에 전체를 붙여넣고 [Run] 한 번으로 실행하세요.
-- (기존 stocks_master / daily_chart / daily_investor_supply 는 변경하지 않으며, 여러 번 실행해도 안전합니다)
-- =====================================================================

-- 5. 영구 제외 종목 사전 (은행·전력·통신 등 사용자 비선호/저변동 상단막힘 종목 영구 차단)
CREATE TABLE IF NOT EXISTS excluded_stocks (
    shcode VARCHAR(6) PRIMARY KEY,              -- 종목코드 (6자리)
    hname VARCHAR(100) NOT NULL,                -- 종목명
    market VARCHAR(10) DEFAULT '',              -- 시장구분 (KOSPI / KOSDAQ)
    reason_tag VARCHAR(40) DEFAULT '비선호/저변동', -- 제외 사유 태그 (은행/금융, 공기업/유틸리티, 저변동/상단막힘, 기타)
    memo TEXT DEFAULT '',                       -- 사용자 메모
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. 통합 관심종목군 (당일 수급 스마트 병합 + 재수급 횟수 누적 + 최종 진입대기 등급 관리)
CREATE TABLE IF NOT EXISTS watchlist_items (
    id BIGSERIAL PRIMARY KEY,
    shcode VARCHAR(6) NOT NULL UNIQUE,          -- 활성 관심종목 종목코드 고유 제약
    hname VARCHAR(100) NOT NULL,
    market VARCHAR(10) DEFAULT '',
    grade VARCHAR(20) NOT NULL DEFAULT 'B_WATCH', -- 'A_READY' (최우선 진입대기) | 'B_WATCH' (일반 관찰)
    first_signal_date DATE NOT NULL,            -- 최초 포착 기준일 (박제)
    first_signal_close INTEGER NOT NULL,        -- 최초 포착일 종가 (박제)
    first_signal_low INTEGER NOT NULL,          -- 최초 포착일 저가 (기준봉 손절 기준선, 박제)
    first_inst_ratio NUMERIC(8, 2) DEFAULT 0,   -- 최초 포착일 순수기관 비중 (%)
    first_inst_amt NUMERIC(14, 2) DEFAULT 0,    -- 최초 포착일 순수기관 순매수 금액 (백만원)
    last_signal_date DATE NOT NULL,             -- 가장 최근 수급 병합 기준일
    last_inst_ratio NUMERIC(8, 2) DEFAULT 0,    -- 최근 병합일 순수기관 비중 (%)
    last_inst_amt NUMERIC(14, 2) DEFAULT 0,     -- 최근 병합일 순수기관 순매수 금액 (백만원)
    signal_count INTEGER NOT NULL DEFAULT 1,    -- 누적 수급 포착(병합) 횟수 (1회, 2회, 3회...)
    recommend_tag VARCHAR(40) DEFAULT '',       -- 포착 유형 ('추세수급', '바닥전환 첫수급', '바닥지지 연속수급', '수동등록')
    signal_mode VARCHAR(40) DEFAULT '',         -- 포착 당시 옵션 ('당일10%', '당일15%', '당일20%', '3일연속5%', '하락추세전환', '직접추가')
    target_entry_price INTEGER,                 -- 사용자 희망 진입가 (선택)
    stop_price INTEGER,                         -- 사용자 지정 손절가 (기본값: first_signal_low)
    memo TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_watchlist_grade_last_date
    ON watchlist_items (grade ASC, last_signal_date DESC);

-- 7. 보유종목 및 청산 매매 히스토리 (A안: 보유중 종목당 1행 고유 + 청산 완료 건별 영구 누적)
CREATE TABLE IF NOT EXISTS portfolio_holdings (
    id BIGSERIAL PRIMARY KEY,
    shcode VARCHAR(6) NOT NULL,
    hname VARCHAR(100) NOT NULL,
    market VARCHAR(10) DEFAULT '',
    status VARCHAR(16) NOT NULL DEFAULT 'HOLDING', -- 'HOLDING' (현재 보유중) | 'CLOSED' (전량 청산 완료)
    buy_date DATE NOT NULL,                     -- 최초 진입(매수)일
    avg_buy_price NUMERIC(14, 2) NOT NULL,      -- 진입 평균매수가 (원)
    quantity BIGINT,                            -- 보유 수량 (주, 선택 입력 — NULL 허용)
    target_1_price INTEGER NOT NULL,            -- 1차 목표가 (기본값: 진입가의 +5% 반올림, 수정 가능)
    target_2_price INTEGER NOT NULL,            -- 2차 목표가 (기본값: 진입가의 +10% 반올림, 수정 가능)
    tp1_done BOOLEAN NOT NULL DEFAULT FALSE,    -- 1차 목표 익절 실행 체크 표시 (수량 분할 입력 불필요)
    tp2_done BOOLEAN NOT NULL DEFAULT FALSE,    -- 2차 목표 익절 실행 체크 표시
    entry_source_tag VARCHAR(40) DEFAULT '',    -- 출신 전략 태그 보존 ('추세수급', '바닥전환 첫수급', '바닥지지 연속수급' 등)
    memo TEXT DEFAULT '',                       -- 매매/복기 메모
    sell_date DATE,                             -- 최종 전량 청산일 ('CLOSED' 전환 시 기록)
    avg_sell_price NUMERIC(14, 2),              -- 최종 실제 평균 청산가 (사용자가 수작업 직접 입력!)
    realized_return_pct NUMERIC(8, 2),          -- 최종 실현 수익률 (%) = ((avg_sell_price - avg_buy_price) / avg_buy_price) * 100
    realized_pnl_krw BIGINT,                    -- 최종 실현 손익금 (원, quantity 입력 시 자동 계산)
    close_reason VARCHAR(50) DEFAULT '',        -- 청산 사유 ('목표가 익절', '20일선 이탈 청산', '수급이탈 정리', '수동 청산' 등)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 현재 보유중('HOLDING') 상태에서는 동일 종목 중복 등록 차단, 청산('CLOSED') 후 재매매 시 신규 행 허용!
CREATE UNIQUE INDEX IF NOT EXISTS idx_holdings_active_shcode
    ON portfolio_holdings (shcode) WHERE status = 'HOLDING';

CREATE INDEX IF NOT EXISTS idx_holdings_status_dates
    ON portfolio_holdings (status, buy_date DESC, sell_date DESC);

ALTER TABLE excluded_stocks DISABLE ROW LEVEL SECURITY;
ALTER TABLE watchlist_items DISABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_holdings DISABLE ROW LEVEL SECURITY;

-- [ISSUE-011] anon(웹 publishable 키) 쓰기 권한 명시 부여 (RLS 재활성화/권한 누락 대비)
GRANT ALL ON TABLE excluded_stocks, watchlist_items, portfolio_holdings TO anon, authenticated, service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;

-- PostgREST 스키마 캐시 즉시 갱신 (신규 테이블이 REST API 에 바로 노출되도록)
NOTIFY pgrst, 'reload schema';
