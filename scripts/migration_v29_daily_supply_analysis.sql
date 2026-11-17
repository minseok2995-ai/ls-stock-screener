-- =====================================================================
-- v2.9 마이그레이션: 일일 수급 전수 정량 분석 · Top 10 Gemini AI 요약 · 사후 복기 테이블
-- Supabase 대시보드 > SQL Editor 에 전체를 붙여넣고 [Run] 한 번으로 실행하세요.
-- (기존 테이블은 변경하지 않으며, 여러 번 실행해도 안전합니다)
-- =====================================================================

CREATE TABLE IF NOT EXISTS daily_supply_analysis (
    trade_date DATE NOT NULL,
    shcode VARCHAR(6) NOT NULL REFERENCES stocks_master(shcode) ON DELETE CASCADE,
    hname VARCHAR(100) NOT NULL,
    market VARCHAR(10) DEFAULT '',
    market_cap_eok NUMERIC(14, 2) DEFAULT 0,
    avg_val_20d_eok NUMERIC(14, 2) DEFAULT 0,

    -- 순위 · 선정 · 분류
    daily_rank INTEGER NOT NULL,
    is_qualified BOOLEAN NOT NULL DEFAULT FALSE,
    is_top_pick BOOLEAN NOT NULL DEFAULT FALSE,
    signal_type VARCHAR(50) DEFAULT '',
    disqualify_reason VARCHAR(120) DEFAULT '',

    -- 당일 시세 · 수급 스냅샷
    close INTEGER NOT NULL,
    change_rate NUMERIC(8, 2) DEFAULT 0,
    volume BIGINT DEFAULT 0,
    trading_value_eok NUMERIC(14, 2) DEFAULT 0,
    inst_vol_ratio NUMERIC(8, 2) DEFAULT 0,
    real_inst_amt_eok NUMERIC(14, 2) DEFAULT 0,
    frg_vol_ratio NUMERIC(8, 2) DEFAULT 0,
    frg_amt_eok NUMERIC(14, 2) DEFAULT 0,
    inst_consec_5p_days INTEGER DEFAULT 0,
    inst_cum_5d_amt_eok NUMERIC(14, 2) DEFAULT 0,
    inst_cum_20d_amt_eok NUMERIC(14, 2) DEFAULT 0,
    top_inst_buyers JSONB DEFAULT '{}'::jsonb,

    -- 기술적 지표 · 이격도 · 패턴
    ema_5 NUMERIC(14, 2),
    ema_20 NUMERIC(14, 2),
    ema_60 NUMERIC(14, 2),
    ema_120 NUMERIC(14, 2),
    ema_240 NUMERIC(14, 2),
    disp_ema5 NUMERIC(8, 2) DEFAULT 0,
    disp_ema20 NUMERIC(8, 2) DEFAULT 0,
    disp_ema60 NUMERIC(8, 2) DEFAULT 0,
    rsi_14 NUMERIC(6, 2),
    atr_pct_14 NUMERIC(6, 2),
    bb_pctile_60 NUMERIC(6, 2),
    vol_ratio_20d NUMERIC(8, 2) DEFAULT 0,
    ema_alignment VARCHAR(30) DEFAULT '',
    candle_signal VARCHAR(40) DEFAULT '',
    chart_patterns JSONB DEFAULT '[]'::jsonb,

    -- 정량 스코어 (100점)
    total_score NUMERIC(6, 2) NOT NULL DEFAULT 0,
    score_supply NUMERIC(6, 2) DEFAULT 0,
    score_trend NUMERIC(6, 2) DEFAULT 0,
    score_trigger NUMERIC(6, 2) DEFAULT 0,
    score_risk_adj NUMERIC(6, 2) DEFAULT 0,

    -- 매매 가이드 & 유사조건 과거 승률
    is_overheated BOOLEAN DEFAULT FALSE,
    entry_price_ref INTEGER DEFAULT 0,
    entry_band_low INTEGER DEFAULT 0,
    entry_band_high INTEGER DEFAULT 0,
    stop_loss_price INTEGER DEFAULT 0,
    target_price_1 INTEGER DEFAULT 0,
    target_price_2 INTEGER DEFAULT 0,
    risk_reward_ratio NUMERIC(6, 2) DEFAULT 0,
    hist_sample_cnt INTEGER DEFAULT 0,
    hist_win_rate_5d NUMERIC(6, 2),
    hist_avg_ret_5d NUMERIC(6, 2),
    hist_win_rate_10d NUMERIC(6, 2),
    hist_avg_ret_10d NUMERIC(6, 2),

    -- Gemini AI 코멘트
    ai_model VARCHAR(50) DEFAULT '',
    ai_status VARCHAR(20) DEFAULT 'PENDING',
    ai_summary JSONB,
    ai_generated_at TIMESTAMPTZ,

    -- 사후 복기 성적표 (자동 백필)
    ret_5d NUMERIC(7, 2),
    ret_10d NUMERIC(7, 2),
    ret_20d NUMERIC(7, 2),
    max_ret_10d NUMERIC(7, 2),
    min_ret_10d NUMERIC(7, 2),
    outcome_updated_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (trade_date, shcode)
);

CREATE INDEX IF NOT EXISTS idx_dsa_date_rank
    ON daily_supply_analysis (trade_date DESC, daily_rank ASC);
CREATE INDEX IF NOT EXISTS idx_dsa_shcode_date
    ON daily_supply_analysis (shcode, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_dsa_top_pick
    ON daily_supply_analysis (trade_date DESC, is_top_pick)
    WHERE is_top_pick = TRUE;

ALTER TABLE daily_supply_analysis DISABLE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE, DELETE ON daily_supply_analysis TO anon, authenticated;
GRANT ALL ON TABLE daily_supply_analysis TO service_role;

-- PostgREST 스키마 캐시 즉시 갱신 (신규 테이블이 REST API 에 바로 노출되도록)
NOTIFY pgrst, 'reload schema';
