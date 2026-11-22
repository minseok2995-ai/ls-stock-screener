-- =============================================================================
-- v3.0 무중단 마이그레이션: 양극 추세 사이클(16단계·63세부현황) DB 스키마 확장
-- (Supabase SQL Editor에서 기존 데이터 손실 없이 즉시 실행 가능)
-- =============================================================================

-- 1. daily_supply_analysis 추세 사이클 컬럼 확장
ALTER TABLE daily_supply_analysis
    ADD COLUMN IF NOT EXISTS trend_camp VARCHAR(10) DEFAULT 'BEAR',
    ADD COLUMN IF NOT EXISTS trend_stage_code VARCHAR(10) DEFAULT '',
    ADD COLUMN IF NOT EXISTS trend_stage_name VARCHAR(40) DEFAULT '',
    ADD COLUMN IF NOT EXISTS trend_detail_code VARCHAR(10) DEFAULT '',
    ADD COLUMN IF NOT EXISTS trend_detail_name VARCHAR(60) DEFAULT '',
    ADD COLUMN IF NOT EXISTS trend_full_label VARCHAR(110) DEFAULT '',
    ADD COLUMN IF NOT EXISTS prob_7p_10d NUMERIC(5, 2) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS prob_10p_10d NUMERIC(5, 2) DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_dsa_date_camp_stage
    ON daily_supply_analysis (trade_date DESC, trend_camp, trend_stage_code, daily_rank ASC);

-- 2. stocks_master 전 종목 최신 추세 현황 스냅샷 컬럼 확장 (로컬 미니 HTS 전 종목 조회용)
ALTER TABLE stocks_master
    ADD COLUMN IF NOT EXISTS trend_camp VARCHAR(10) DEFAULT '',
    ADD COLUMN IF NOT EXISTS trend_stage_code VARCHAR(10) DEFAULT '',
    ADD COLUMN IF NOT EXISTS trend_detail_code VARCHAR(10) DEFAULT '',
    ADD COLUMN IF NOT EXISTS trend_full_label VARCHAR(110) DEFAULT '',
    ADD COLUMN IF NOT EXISTS trend_updated_date DATE;

CREATE INDEX IF NOT EXISTS idx_sm_trend_stage
    ON stocks_master (is_universe, trend_camp, trend_stage_code);

NOTIFY pgrst, 'reload schema';
