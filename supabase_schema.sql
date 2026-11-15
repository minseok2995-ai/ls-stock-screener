-- =============================================================================
-- LS증권 Open API 기반 수급·기술적 분석 스크리닝 시스템 (Supabase PostgreSQL 스키마)
-- =============================================================================

-- 1. 종목 마스터 테이블 (유니버스 관리: 시총 700억 이상, 20일 평균 거래대금 20억 이상 보통주)
CREATE TABLE IF NOT EXISTS stocks_master (
    shcode VARCHAR(6) PRIMARY KEY,              -- 종목코드 (6자리)
    hname VARCHAR(100) NOT NULL,                -- 종목명
    market VARCHAR(10) NOT NULL,                -- 시장구분 (KOSPI / KOSDAQ)
    shares BIGINT DEFAULT 0,                    -- 상장주식수 (주)
    market_cap_eok NUMERIC(14, 2) DEFAULT 0,    -- 시가총액 (억원)
    avg_vol_20d BIGINT DEFAULT 0,               -- 최근 20일 평균 거래량 (주)
    avg_val_20d_eok NUMERIC(14, 2) DEFAULT 0,   -- 최근 20일 평균 거래대금 (억원)
    is_universe BOOLEAN DEFAULT FALSE,          -- 유니버스(분석 대상) 편입 여부
    last_close INTEGER DEFAULT 0,               -- 최근 종가 (수정주가 변동 감지용)
    updated_at TIMESTAMPTZ DEFAULT NOW()        -- 최종 갱신 시각
);

CREATE INDEX IF NOT EXISTS idx_stocks_master_universe
    ON stocks_master (is_universe, market_cap_eok DESC);

-- 2. 일봉 차트 및 지수이동평균(EMA) 테이블 (최근 2년치 약 500영업일 보관)
CREATE TABLE IF NOT EXISTS daily_chart (
    shcode VARCHAR(6) NOT NULL REFERENCES stocks_master(shcode) ON DELETE CASCADE,
    trade_date DATE NOT NULL,                   -- 거래일자 (YYYY-MM-DD)
    open INTEGER NOT NULL,                      -- 시가 (수정주가 기준)
    high INTEGER NOT NULL,                      -- 고가
    low INTEGER NOT NULL,                       -- 저가
    close INTEGER NOT NULL,                     -- 종가
    change_rate NUMERIC(8, 2) DEFAULT 0,        -- 전일대비 등락률 (%)
    volume BIGINT NOT NULL,                     -- 일 거래량 (주)
    trading_value_m NUMERIC(16, 2) DEFAULT 0,   -- 일 거래대금 (백만원)
    ema_5 NUMERIC(14, 2),                       -- 5일 지수이동평균
    ema_20 NUMERIC(14, 2),                      -- 20일 지수이동평균
    ema_60 NUMERIC(14, 2),                      -- 60일 지수이동평균
    ema_120 NUMERIC(14, 2),                     -- 120일 지수이동평균
    ema_240 NUMERIC(14, 2),                     -- 240일 지수이동평균
    PRIMARY KEY (shcode, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_chart_date
    ON daily_chart (trade_date DESC, shcode);

-- 3. 일별 투자주체별 수급 테이블 (수량: 주, 금액: 백만원)
-- 순수 기관(real_inst) = 투신(itc) + 사모펀드(pef) + 연기금(pen) + 보험(ins) + 기타금융(etc_fin) + 은행(bank) (금융투자 제외)
CREATE TABLE IF NOT EXISTS daily_investor_supply (
    shcode VARCHAR(6) NOT NULL REFERENCES stocks_master(shcode) ON DELETE CASCADE,
    trade_date DATE NOT NULL,                   -- 거래일자 (YYYY-MM-DD)
    
    -- 핵심 가공 지표: 순수 기관 (투신+사모+연기금+보험+기타금융+은행)
    real_inst_vol BIGINT DEFAULT 0,             -- 순수기관 순매수 수량 (주)
    real_inst_amt NUMERIC(14, 2) DEFAULT 0,     -- 순수기관 순매수 금액 (백만원)
    inst_vol_ratio NUMERIC(8, 2) DEFAULT 0,     -- 당일 거래량 대비 순수기관 순매수 비중 (%)

    -- 외국인
    frg_vol BIGINT DEFAULT 0,                   -- 외국인 순매수 수량 (주)
    frg_amt NUMERIC(14, 2) DEFAULT 0,           -- 외국인 순매수 금액 (백만원)
    frg_vol_ratio NUMERIC(8, 2) DEFAULT 0,      -- 당일 거래량 대비 외국인 순매수 비중 (%)

    -- 개인 및 금융투자 (금융투자는 순수기관 합산에서 제외하되 별도 보관)
    ind_vol BIGINT DEFAULT 0,                   -- 개인 순매수 수량 (주)
    ind_amt NUMERIC(14, 2) DEFAULT 0,           -- 개인 순매수 금액 (백만원)
    fn_inv_vol BIGINT DEFAULT 0,                -- 금융투자 순매수 수량 (주)
    fn_inv_amt NUMERIC(14, 2) DEFAULT 0,        -- 금융투자 순매수 금액 (백만원)

    -- 순수 기관 구성 6대 주체 세부 내역
    itc_vol BIGINT DEFAULT 0,                   -- 투신 순매수 수량 (주)
    itc_amt NUMERIC(14, 2) DEFAULT 0,           -- 투신 순매수 금액 (백만원)
    pef_vol BIGINT DEFAULT 0,                   -- 사모펀드 순매수 수량 (주)
    pef_amt NUMERIC(14, 2) DEFAULT 0,           -- 사모펀드 순매수 금액 (백만원)
    pen_vol BIGINT DEFAULT 0,                   -- 연기금 순매수 수량 (주)
    pen_amt NUMERIC(14, 2) DEFAULT 0,           -- 연기금 순매수 금액 (백만원)
    ins_vol BIGINT DEFAULT 0,                   -- 보험 순매수 수량 (주)
    ins_amt NUMERIC(14, 2) DEFAULT 0,           -- 보험 순매수 금액 (백만원)
    etc_fin_vol BIGINT DEFAULT 0,               -- 기타금융 순매수 수량 (주)
    etc_fin_amt NUMERIC(14, 2) DEFAULT 0,       -- 기타금융 순매수 금액 (백만원)
    bank_vol BIGINT DEFAULT 0,                  -- 은행 순매수 수량 (주)
    bank_amt NUMERIC(14, 2) DEFAULT 0,          -- 은행 순매수 금액 (백만원)

    -- 기타주체
    etc_corp_vol BIGINT DEFAULT 0,              -- 기타법인 순매수 수량 (주)
    etc_corp_amt NUMERIC(14, 2) DEFAULT 0,      -- 기타법인 순매수 금액 (백만원)

    PRIMARY KEY (shcode, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_supply_date_ratio
    ON daily_investor_supply (trade_date DESC, inst_vol_ratio DESC);

-- 3-1. 배치 스크립트(Publishable Key) 및 웹 대시보드에서 조회/적재가 가능하도록 RLS 비활성화
ALTER TABLE stocks_master DISABLE ROW LEVEL SECURITY;
ALTER TABLE daily_chart DISABLE ROW LEVEL SECURITY;
ALTER TABLE daily_investor_supply DISABLE ROW LEVEL SECURITY;

-- 4. N일 누적 수급 및 EMA 스크리닝 조회용 RPC 함수 (Supabase에서 웹앱이 직접 호출 가능)
CREATE OR REPLACE FUNCTION get_screened_stocks(
    p_days INTEGER DEFAULT 1,
    p_min_inst_ratio NUMERIC DEFAULT 10.0,
    p_min_mcap_eok NUMERIC DEFAULT 700.0,
    p_min_val_20d_eok NUMERIC DEFAULT 0.0
)
RETURNS TABLE (
    shcode VARCHAR(6),
    hname VARCHAR(100),
    market VARCHAR(10),
    market_cap_eok NUMERIC,
    avg_val_20d_eok NUMERIC,
    trade_date DATE,
    close INTEGER,
    change_rate NUMERIC,
    period_volume BIGINT,
    real_inst_vol BIGINT,
    real_inst_amt NUMERIC,
    inst_vol_ratio NUMERIC,
    frg_vol BIGINT,
    frg_amt NUMERIC,
    frg_vol_ratio NUMERIC,
    itc_amt NUMERIC,
    pef_amt NUMERIC,
    pen_amt NUMERIC,
    ins_amt NUMERIC,
    etc_fin_amt NUMERIC,
    bank_amt NUMERIC,
    ema_5 NUMERIC,
    ema_20 NUMERIC,
    ema_60 NUMERIC,
    ema_120 NUMERIC,
    ema_240 NUMERIC
) LANGUAGE sql STABLE AS $$
    WITH recent_dates AS (
        SELECT DISTINCT d.trade_date
        FROM daily_chart d
        ORDER BY d.trade_date DESC
        LIMIT p_days
    ),
    latest_date AS (
        SELECT MAX(r.trade_date) AS max_date FROM recent_dates r
    ),
    agg_supply AS (
        SELECT
            c.shcode,
            SUM(c.volume)::BIGINT AS period_volume,
            SUM(s.real_inst_vol)::BIGINT AS real_inst_vol,
            ROUND(SUM(s.real_inst_amt), 2) AS real_inst_amt,
            CASE WHEN SUM(c.volume) > 0
                 THEN ROUND((SUM(s.real_inst_vol)::NUMERIC / SUM(c.volume)::NUMERIC) * 100, 2)
                 ELSE 0 END AS inst_vol_ratio,
            SUM(s.frg_vol)::BIGINT AS frg_vol,
            ROUND(SUM(s.frg_amt), 2) AS frg_amt,
            CASE WHEN SUM(c.volume) > 0
                 THEN ROUND((SUM(s.frg_vol)::NUMERIC / SUM(c.volume)::NUMERIC) * 100, 2)
                 ELSE 0 END AS frg_vol_ratio,
            ROUND(SUM(s.itc_amt), 2) AS itc_amt,
            ROUND(SUM(s.pef_amt), 2) AS pef_amt,
            ROUND(SUM(s.pen_amt), 2) AS pen_amt,
            ROUND(SUM(s.ins_amt), 2) AS ins_amt,
            ROUND(SUM(s.etc_fin_amt), 2) AS etc_fin_amt,
            ROUND(SUM(s.bank_amt), 2) AS bank_amt
        FROM daily_chart c
        JOIN daily_investor_supply s
          ON c.shcode = s.shcode AND c.trade_date = s.trade_date
        WHERE c.trade_date IN (SELECT r.trade_date FROM recent_dates r)
        GROUP BY c.shcode
    )
    SELECT
        m.shcode,
        m.hname,
        m.market,
        m.market_cap_eok,
        m.avg_val_20d_eok,
        lc.trade_date,
        lc.close,
        lc.change_rate,
        a.period_volume,
        a.real_inst_vol,
        a.real_inst_amt,
        a.inst_vol_ratio,
        a.frg_vol,
        a.frg_amt,
        a.frg_vol_ratio,
        a.itc_amt,
        a.pef_amt,
        a.pen_amt,
        a.ins_amt,
        a.etc_fin_amt,
        a.bank_amt,
        lc.ema_5,
        lc.ema_20,
        lc.ema_60,
        lc.ema_120,
        lc.ema_240
    FROM agg_supply a
    JOIN stocks_master m ON m.shcode = a.shcode
    JOIN latest_date ld ON TRUE
    JOIN daily_chart lc ON lc.shcode = a.shcode AND lc.trade_date = ld.max_date
    WHERE m.is_universe = TRUE
      AND m.market_cap_eok >= p_min_mcap_eok
      AND m.avg_val_20d_eok >= p_min_val_20d_eok
      AND a.inst_vol_ratio >= p_min_inst_ratio
    ORDER BY a.inst_vol_ratio DESC;
$$;

-- =====================================================================
-- v2.4 신규 테이블 3종 (scripts/migration_v24_watchlist_holdings.sql 과 동일)
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

-- [ISSUE-011] anon 쓰기 권한 명시 부여
GRANT ALL ON TABLE excluded_stocks, watchlist_items, portfolio_holdings TO anon, authenticated, service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;
