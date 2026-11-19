import type { BacktestPhaseFilter } from '../types/backtest';
import type { AlertTargetScope, AlertType, MarketLightStatus, MarketRegion, PortfolioStopLossMode } from '../types/alerts';
import type { PortfolioCashDirection, PortfolioCorporateActionType, PortfolioSide } from '../types/portfolio';
import type { UiLanguage } from '../i18n/uiText';

type Option<T extends string = string> = { value: T; label: string };
const alertTypes: AlertType[] = ['price_cross', 'price_change_percent', 'volume_spike', 'ma_price_cross', 'rsi_threshold', 'macd_cross', 'kdj_cross', 'cci_threshold', 'portfolio_stop_loss', 'portfolio_concentration', 'portfolio_drawdown', 'portfolio_price_stale', 'market_light_status', 'market_light_score_drop'];
const symbolAlertTypes = alertTypes.slice(0, 8);
const portfolioAlertTypes = alertTypes.slice(8, 12);
const marketAlertTypes = alertTypes.slice(12);

export const BACKTEST_TEXT = {
    en: { documentTitle: 'Strategy Backtest - DSA', codePlaceholder: 'Filter by stock code (leave empty for all)', filter: 'Filter', evalWindow: 'Evaluation window', phase: 'Phase', startDate: 'Start date', startDateAria: 'Analysis start date', endDate: 'End date', endDateAria: 'Analysis end date', oneDayValidation: '1D validation', forceRerun: 'Force rerun', running: 'Backtesting...', runBacktest: 'Run backtest', oneDayModeDescription: '1D validation checks AI predictions against the next trading day close.', windowModeDescription: 'Set the evaluation window to 1 to compare AI predictions with the next trading day close.', overallPerformance: 'Overall performance', noMetricsTitle: 'No metrics', noMetricsDescription: 'Portfolio-level performance metrics appear after a backtest runs.', loadingResults: 'Loading results...', noResultsTitle: 'No results', noResultsDescription: 'Run a backtest to evaluate historical analysis accuracy.', nextDayValidation: 'Next-day validation', resultSet: 'Result set', allStocks: 'All stocks', filteredStock: 'Filtered {code}', dayWindow: '{days}-day window', fromDate: 'from {date}', toDate: 'to {date}', scrollHint: 'Scroll horizontally on small screens', stock: 'Stock', analysisDate: 'Analysis date', aiPrediction: 'AI prediction', actualPerformance: 'Actual performance', windowReturn: 'Window return', accuracy: 'Accuracy', directionMatch: 'Direction match', result: 'Result', status: 'Status', totalPage: '{total} results · Page {page} / {pages}', directionAccuracy: 'Direction accuracy', winRate: 'Win rate', avgSimulatedReturn: 'Avg simulated return', avgStockReturn: 'Avg stock return', stopLossTriggerRate: 'Stop-loss trigger rate', takeProfitTriggerRate: 'Take-profit trigger rate', avgDaysToFirstHit: 'Avg days to first hit', evaluationCount: 'Evaluations', outcomeSummary: 'Win / Loss / Neutral', phaseDistribution: 'Phase breakdown: {text}', processed: 'Processed:', saved: 'Saved:', completed: 'Completed:', insufficient: 'Insufficient:', errors: 'Errors:', yes: 'Yes', no: 'No', unknown: 'Unknown' }, th: { documentTitle: 'ทดสอบกลยุทธ์ย้อนหลัง - DSA', codePlaceholder: 'กรองตามรหัสหุ้น (เว้นว่าง = ทั้งหมด)', filter: 'กรอง', evalWindow: 'หน้าต่างประเมินผล', phase: 'เฟส', startDate: 'วันเริ่มต้น', startDateAria: 'วันเริ่มวิเคราะห์', endDate: 'วันสิ้นสุด', endDateAria: 'วันสิ้นสุดการวิเคราะห์', oneDayValidation: 'ยืนยัน 1 วัน', forceRerun: 'บังคับรันใหม่', running: 'กำลังทดสอบย้อนหลัง...', runBacktest: 'รันการทดสอบย้อนหลัง', oneDayModeDescription: 'โหมดยืนยัน 1 วันจะตรวจคาดการณ์ของ AI กับราคาปิดของวันทำการถัดไป', windowModeDescription: 'ตั้งหน้าต่างประเมินเป็น 1 เพื่อดูความตรงกันระหว่างคาดการณ์ AI กับราคาปิดวันทำการถัดไป', overallPerformance: 'ผลงานโดยรวม', noMetricsTitle: 'ยังไม่มีตัวชี้วัด', noMetricsDescription: 'รันการทดสอบย้อนหลังแล้วจะได้ตัวชี้วัดระดับพอร์ตโฟลิโอ', loadingResults: 'กำลังโหลดผลลัพธ์...', noResultsTitle: 'ยังไม่มีผลลัพธ์', noResultsDescription: 'หลังรันการทดสอบย้อนหลังจะประเมินความแม่นยำของการวิเคราะห์ย้อนหลังได้', nextDayValidation: 'ยืนยันวันถัดไป', resultSet: 'ชุดผลลัพธ์', allStocks: 'ทุกหุ้น', filteredStock: 'กรอง {code}', dayWindow: 'หน้าต่าง {days} วัน', fromDate: 'จาก {date}', toDate: 'ถึง {date}', scrollHint: 'หน้าจอเล็กเลื่อนแนวนอนได้', stock: 'หุ้น', analysisDate: 'วันที่วิเคราะห์', aiPrediction: 'คาดการณ์ AI', actualPerformance: 'ผลงานจริง', windowReturn: 'ผลตอบแทนในหน้าต่าง', accuracy: 'ความแม่นยำ', directionMatch: 'ทิศทางตรงกัน', result: 'ผลลัพธ์', status: 'สถานะ', totalPage: 'รวม {total} ผลลัพธ์ · หน้า {page} / {pages}', directionAccuracy: 'อัตราทิศทางถูกต้อง', winRate: 'อัตราชนะ', avgSimulatedReturn: 'ผลตอบแทนจำลองเฉลี่ย', avgStockReturn: 'ผลตอบแทนเฉลี่ยต่อหุ้น', stopLossTriggerRate: 'อัตราตัดขาดทุนถูกเรียก', takeProfitTriggerRate: 'อัตราทำกำไรถูกเรียก', avgDaysToFirstHit: 'จำนวนวันถึงเป้าเฉลี่ย', evaluationCount: 'จำนวนครั้งที่ประเมิน', outcomeSummary: 'กำไร / ขาดทุน / เท่ากัน', phaseDistribution: 'การกระจายเฟส: {text}', processed: 'ดำเนินการแล้ว:', saved: 'บันทึกแล้ว:', completed: 'เสร็จสิ้น:', insufficient: 'ข้อมูลไม่พอ:', errors: 'ผิดพลาด:', yes: 'ใช่', no: 'ไม่', unknown: 'ไม่ทราบ' },
} as const;

export const BACKTEST_PHASE_FILTER_OPTIONS: Record<UiLanguage, Array<Option<BacktestPhaseFilter>>> = {
    en: [{ value: 'all', label: 'All phases' }, { value: 'premarket', label: 'Pre-market' }, { value: 'intraday', label: 'Intraday' }, { value: 'postmarket', label: 'Post-market' }, { value: 'unknown', label: 'Unknown' }], th: [{ value: 'all', label: 'ทุกเฟส' }, { value: 'premarket', label: 'ก่อนเปิดตลาด' }, { value: 'intraday', label: 'ระหว่างซื้อขาย' }, { value: 'postmarket', label: 'หลังปิดตลาด' }, { value: 'unknown', label: 'ไม่ทราบ' }],
};
export const BACKTEST_PHASE_LABELS: Record<UiLanguage, Record<string, string>> = { en: { premarket: 'Pre-market', intraday: 'Intraday', postmarket: 'Post-market', unknown: 'Unknown' }, th: { premarket: 'ก่อนเปิดตลาด', intraday: 'ระหว่างซื้อขาย', postmarket: 'หลังปิดตลาด', unknown: 'ไม่ทราบ' } };
export const BACKTEST_OUTCOME_LABELS: Record<UiLanguage, Record<string, string>> = { en: { win: 'Win', loss: 'Loss', neutral: 'Neutral' }, th: { win: 'กำไร', loss: 'ขาดทุน', neutral: 'เท่ากัน' } };
export const BACKTEST_STATUS_LABELS: Record<UiLanguage, Record<string, string>> = { en: { completed: 'Completed', insufficient: 'Insufficient data', insufficient_data: 'Insufficient data', error: 'Error' }, th: { completed: 'เสร็จสิ้น', insufficient: 'ข้อมูลไม่พอ', insufficient_data: 'ข้อมูลไม่พอ', error: 'ผิดพลาด' } };
export const BACKTEST_MOVEMENT_LABELS: Record<UiLanguage, Record<string, string>> = { en: { up: 'Up', down: 'Down', flat: 'Flat' }, th: { up: 'ขึ้น', down: 'ลง', flat: 'ทรงตัว' } };
export const BACKTEST_DIRECTION_EXPECTED_LABELS: Record<UiLanguage, Record<string, string>> = { en: { long: 'Long', cash: 'Cash', up: 'Bullish', down: 'Bearish', not_down: 'Not bearish', flat: 'Flat' }, th: { long: 'ฝั่งซื้อ (Long)', cash: 'ไม่มีสถานะ', up: 'คาดขาขึ้น', down: 'คาดขาลง', not_down: 'ไม่คาดขาลง', flat: 'ทรงตัว' } };

export const ALERT_TYPE_LABELS: Record<UiLanguage, Record<AlertType, string>> = {
    en: { price_cross: 'Price crossing', price_change_percent: 'Price change', volume_spike: 'Volume spike', ma_price_cross: 'Price/MA crossing', rsi_threshold: 'RSI threshold', macd_cross: 'MACD cross', kdj_cross: 'KDJ cross', cci_threshold: 'CCI threshold', portfolio_stop_loss: 'Portfolio stop loss', portfolio_concentration: 'Portfolio concentration', portfolio_drawdown: 'Portfolio drawdown', portfolio_price_stale: 'Portfolio price status', market_light_status: 'Market traffic light status', market_light_score_drop: 'Market traffic light score drop' }, th: { price_cross: 'ราคาทะลุแนว', price_change_percent: '% เปลี่ยนแปลง', volume_spike: 'วอลุ่มที่พุ่ง', ma_price_cross: 'ราคาตัดเส้น MA', rsi_threshold: 'เกณฑ์ RSI', macd_cross: 'MACD ตัดขึ้น/ลง', kdj_cross: 'KDJ ตัดขึ้น/ลง', cci_threshold: 'CCI ถึงเกณฑ์', portfolio_stop_loss: 'ตัดขาดทุนพอร์ต', portfolio_concentration: 'ความเข้มข้นพอร์ต', portfolio_drawdown: 'การย่อของพอร์ต', portfolio_price_stale: 'สถานะราคาพอร์ต', market_light_status: 'สถานะไฟจราจรตลาด', market_light_score_drop: 'คะแนนไฟจราจรตลาดลดลง' },
};
export const ALERT_SEVERITY_LABELS: Record<UiLanguage, Record<string, string>> = { en: { info: 'Info', warning: 'Warning', critical: 'Critical' }, th: { info: 'แจ้งทราบ', warning: 'เตือน', critical: 'รุนแรง' } };
export const ALERT_SCOPE_LABELS: Record<UiLanguage, Record<AlertTargetScope, string>> = { en: { single_symbol: 'Single symbol', watchlist: 'Watchlist', portfolio_holdings: 'Portfolio holdings', portfolio_account: 'Portfolio account', market: 'Market' }, th: { single_symbol: 'หุ้นเดี่ยว', watchlist: 'รายการเฝ้าดู', portfolio_holdings: 'หุ้นในพอร์ต', portfolio_account: 'บัญชีในพอร์ต', market: 'ภาพตลาดรวม' } };
export const ALERT_MARKET_REGION_LABELS: Record<UiLanguage, Record<MarketRegion, string>> = { en: { cn: 'A-shares', hk: 'Hong Kong', us: 'US' }, th: { cn: 'หุ้น A-share', hk: 'หุ้นฮ่องกง', us: 'หุ้นสหรัฐ' } };
export const ALERT_MARKET_LIGHT_STATUS_LABELS: Record<UiLanguage, Record<MarketLightStatus, string>> = { en: { yellow: 'Yellow', red: 'Red' }, th: { yellow: 'ไฟเหลือง', red: 'ไฟแดง' } };
export const ALERT_DIRECTION_LABELS = {
    en: { abovePrice: 'above', belowPrice: 'below', upChange: 'up', downChange: 'down', aboveThreshold: 'above', belowThreshold: 'below', bullishCross: 'bullish cross', bearishCross: 'bearish cross', stopLossNear: 'Near stop loss', stopLossBreach: 'Stop loss breached' }, th: { abovePrice: 'ทะลุขึ้น', belowPrice: 'ทะลุลง', upChange: 'ขึ้น', downChange: 'ลง', aboveThreshold: 'ตัดขึ้น', belowThreshold: 'ตัดลง', bullishCross: 'ทองตัดขึ้น', bearishCross: 'ตัดขึ้นเหนือแบบขาลง', stopLossNear: 'ใกล้จุดตัดขาดทุน', stopLossBreach: 'ตัดขาดทุนแล้ว' },
} as const;
export const ALERT_LIST_TEXT = {
    en: { title: 'Alert rules', subtitle: '{total} rules', enabledFilter: 'Status', alertTypeFilter: 'Rule type', loadingRules: 'Loading rules', emptyTitle: 'No alert rules', emptyDescription: 'After rules are created, background evaluation processes enabled alerts on the polling schedule.', rule: 'Rule', target: 'Target', type: 'Type', parameters: 'Parameters', status: 'Status', cooldown: 'Cooldown', updatedAt: 'Updated', action: 'Actions', source: 'Source: {source}', allAccounts: 'All accounts', accountTarget: 'Account {target}', enabled: 'Enabled', disabled: 'Disabled', coolingDown: 'Cooling down', notCoolingDown: 'Not cooling down', childTargetCooldown: 'Per-target cooldowns are in trigger history', test: 'Test', testing: 'Testing', disabling: 'Disabling', enabling: 'Enabling', disable: 'Disable', enable: 'Enable', delete: 'Delete', cancel: 'Cancel', scoreDropAtLeast: 'Score drop >= {value}', deleteAria: 'Delete {name}', deleteTitle: 'Delete alert rule', deleteMessage: 'Delete "{name}"? Existing trigger history will be kept.' }, th: { title: 'กฎการแจ้งเตือน', subtitle: '{total} กฎ', enabledFilter: 'สถานะเปิด/ปิด', alertTypeFilter: 'ประเภทกฎ', loadingRules: 'กำลังโหลดกฎ', emptyTitle: 'ยังไม่มีกฎการแจ้งเตือน', emptyDescription: 'หลังสร้างกฎ งานประเมินเบื้องหลังจะตรวจกฎที่เปิดใช้งานตามรอบการ poll', rule: 'กฎ', target: 'เป้าหมาย', type: 'ประเภท', parameters: 'พารามิเตอร์', status: 'สถานะ', cooldown: 'คูลดาวน์', updatedAt: 'อัปเดตเมื่อ', action: 'จัดการ', source: 'แหล่งที่มา: {source}', allAccounts: 'ทุกบัญชี', accountTarget: 'บัญชี {target}', enabled: 'เปิดใช้งาน', disabled: 'ปิดใช้งาน', coolingDown: 'อยู่ระหว่างคูลดาวน์', notCoolingDown: 'ไม่อยู่ระหว่างคูลดาวน์', childTargetCooldown: 'ดูประวัติการแจ้งของเป้าหมายย่อย', test: 'ทดสอบ', testing: 'กำลังทดสอบ', disabling: 'กำลังปิด', enabling: 'กำลังเปิด', disable: 'ปิดใช้งาน', enable: 'เปิดใช้งาน', delete: 'ลบ', cancel: 'ยกเลิก', scoreDropAtLeast: 'คะแนนลดลง >= {value}', deleteAria: 'ลบ {name}', deleteTitle: 'ลบกฎการแจ้งเตือน', deleteMessage: 'ยืนยันลบ “{name}” ไหม? การนี้จะไม่ลบประวัติการแจ้งเตือนที่มีอยู่' },
} as const;
export const ALERT_ENABLED_FILTER_OPTIONS: Record<UiLanguage, Array<Option<'all' | 'enabled' | 'disabled'>>> = { en: [{ value: 'all', label: 'All statuses' }, { value: 'enabled', label: 'Enabled' }, { value: 'disabled', label: 'Disabled' }], th: [{ value: 'all', label: 'ทุกสถานะ' }, { value: 'enabled', label: 'เปิดใช้งาน' }, { value: 'disabled', label: 'ปิดใช้งาน' }] };
export const ALERT_TYPE_FILTER_OPTIONS: Record<UiLanguage, Array<Option<'all' | AlertType>>> = { en: [{ value: 'all', label: 'All types' }, ...alertTypes.map((value) => ({ value, label: ALERT_TYPE_LABELS.en[value] }))], th: [{ value: 'all', label: 'ทุกประเภท' }, ...alertTypes.map((value) => ({ value, label: ALERT_TYPE_LABELS.th[value] }))] };
export const ALERT_FORM_TEXT = {
  en: {
    accountLoadFailed: 'Account loading failed',
    allAccounts: 'All accounts',
    cardTitle: 'Create alert rule',
    cardSubtitle: 'Web alert center',
    ruleName: 'Rule name',
    ruleNamePlaceholder: 'Optional, e.g. Moutai price crossing',
    targetScope: 'Target scope',
    targetCode: 'Symbol',
    target: 'Target',
    marketRegion: 'Market region',
    account: 'Account',
    ruleType: 'Rule type',
    severity: 'Severity',
    direction: 'Direction',
    priceThreshold: 'Price threshold',
    changePctThreshold: 'Change threshold (%)',
    volumeMultiplier: 'Volume multiplier',
    crossDirection: 'Cross direction',
    thresholdDirection: 'Threshold direction',
    maDirection: 'Cross direction',
    maWindow: 'MA window',
    rsiPeriod: 'RSI period',
    rsiThreshold: 'RSI threshold',
    fastPeriod: 'Fast period',
    slowPeriod: 'Slow period',
    signalPeriod: 'Signal period',
    kdjPeriod: 'KDJ period',
    kPeriod: 'K smoothing period',
    dPeriod: 'D smoothing period',
    cciPeriod: 'CCI period',
    cciThreshold: 'CCI threshold',
    stopLossMode: 'Stop-loss mode',
    triggerStatus: 'Trigger status',
    scoreDropThreshold: 'Score drop threshold',
    enableAfterCreate: 'Enable immediately',
    creating: 'Creating...',
    create: 'Create rule',
    positiveNumber: '{label} must be a number greater than 0',
    integerRange: '{label} must be an integer from {min} to {max}',
    required: '{label} is required',
    finiteNumber: '{label} must be a valid number',
    rsiRange: 'RSI threshold must be between 0 and 100',
    requiredBarsLimit: '{label} requires {requiredBars} daily bars, up to {max} are supported',
    fastLessThanSlow: 'Fast period must be less than slow period',
    noMarketStatus: 'Select at least one traffic light status',
    invalidStockCode: 'Invalid stock code format',
  },
  th: {
    accountLoadFailed: 'โหลดบัญชีไม่สำเร็จ',
    allAccounts: 'ทุกบัญชี',
    cardTitle: 'สร้างกฎการแจ้งเตือน',
    cardSubtitle: 'ศูนย์การแจ้งเตือนเว็บ',
    ruleName: 'ชื่อกฎ',
    ruleNamePlaceholder: 'ไม่บังคับ เช่น ราคาทะลุแนวรับ',
    targetScope: 'ขอบเขตเป้าหมาย',
    targetCode: 'รหัสหุ้น',
    target: 'เป้าหมาย',
    marketRegion: 'ตลาด',
    account: 'บัญชี',
    ruleType: 'ประเภทกฎ',
    severity: 'ระดับความรุนแรง',
    direction: 'ทิศทาง',
    priceThreshold: 'ราคาเกณฑ์',
    changePctThreshold: 'เกณฑ์ % เปลี่ยนแปลง',
    volumeMultiplier: 'ตัวคูณวอลุ่ม',
    crossDirection: 'ทิศทางการตัด',
    thresholdDirection: 'ทิศทางเกณฑ์',
    maDirection: 'Cross direction',
    maWindow: 'ช่วงเวลา MA',
    rsiPeriod: 'ช่วงเวลา RSI',
    rsiThreshold: 'เกณฑ์ RSI',
    fastPeriod: 'ช่วงเวลาเส้นเร็ว',
    slowPeriod: 'ช่วงเวลาเส้นช้า',
    signalPeriod: 'ช่วงเวลาสัญญาณ',
    kdjPeriod: 'ช่วงเวลา KDJ',
    kPeriod: 'ช่วงเวลา K เรียบ',
    dPeriod: 'ช่วงเวลา D เรียบ',
    cciPeriod: 'ช่วงเวลา CCI',
    cciThreshold: 'เกณฑ์ CCI',
    stopLossMode: 'โหมดตัดขาดทุน',
    triggerStatus: 'สถานะการแจ้ง',
    scoreDropThreshold: 'เกณฑ์คะแนนลดลง',
    enableAfterCreate: 'เปิดใช้งานทันทีหลังสร้าง',
    creating: 'กำลังสร้าง...',
    create: 'สร้างกฎ',
    positiveNumber: '{label} ต้องเป็นตัวเลขมากกว่า 0',
    integerRange: '{label} ต้องเป็นจำนวนเต็มระหว่าง {min} ถึง {max}',
    required: '{label} ห้ามว่าง',
    finiteNumber: '{label} ต้องเป็นตัวเลขที่ถูกต้อง',
    rsiRange: 'เกณฑ์ RSI ต้องอยู่ระหว่าง 0 ถึง 100',
    requiredBarsLimit: '{label} ต้องใช้ข้อมูลรายวัน {requiredBars} แท่ง รองรับสูงสุด {max} แท่ง',
    fastLessThanSlow: 'เส้นเร็วต้องสั้นกว่าเส้นช้า',
    noMarketStatus: 'เลือกสถานะไฟจราจรอย่างน้อย 1 แบบ',
    invalidStockCode: 'รูปแบบรหัสหุ้นไม่ถูกต้อง',
  },
} as const;
export const ALERT_SYMBOL_TYPE_OPTIONS: Record<UiLanguage, Array<Option<AlertType>>> = { en: symbolAlertTypes.map((value) => ({ value, label: ALERT_TYPE_LABELS.en[value] })), th: symbolAlertTypes.map((value) => ({ value, label: ALERT_TYPE_LABELS.th[value] })) };
export const ALERT_PORTFOLIO_TYPE_OPTIONS: Record<UiLanguage, Array<Option<AlertType>>> = { en: portfolioAlertTypes.map((value) => ({ value, label: ALERT_TYPE_LABELS.en[value] })), th: portfolioAlertTypes.map((value) => ({ value, label: ALERT_TYPE_LABELS.th[value] })) };
export const ALERT_MARKET_TYPE_OPTIONS: Record<UiLanguage, Array<Option<AlertType>>> = { en: marketAlertTypes.map((value) => ({ value, label: ALERT_TYPE_LABELS.en[value] })), th: marketAlertTypes.map((value) => ({ value, label: ALERT_TYPE_LABELS.th[value] })) };
export const ALERT_TARGET_SCOPE_OPTIONS: Record<UiLanguage, Array<Option<AlertTargetScope>>> = { en: Object.entries(ALERT_SCOPE_LABELS.en).map(([value, label]) => ({ value: value as AlertTargetScope, label })), th: Object.entries(ALERT_SCOPE_LABELS.th).map(([value, label]) => ({ value: value as AlertTargetScope, label })) };
export const ALERT_SEVERITY_OPTIONS: Record<UiLanguage, Array<Option<'info' | 'warning' | 'critical'>>> = { en: Object.entries(ALERT_SEVERITY_LABELS.en).map(([value, label]) => ({ value: value as 'info' | 'warning' | 'critical', label })), th: Object.entries(ALERT_SEVERITY_LABELS.th).map(([value, label]) => ({ value: value as 'info' | 'warning' | 'critical', label })) };
export const ALERT_PRICE_DIRECTION_OPTIONS: Record<UiLanguage, Array<Option<'above' | 'below'>>> = { en: [{ value: 'above', label: 'Crosses above' }, { value: 'below', label: 'Crosses below' }], th: [{ value: 'above', label: 'ทะลุขึ้น' }, { value: 'below', label: 'ทะลุลง' }] };
export const ALERT_CHANGE_DIRECTION_OPTIONS: Record<UiLanguage, Array<Option<'up' | 'down'>>> = { en: [{ value: 'up', label: 'Rises by' }, { value: 'down', label: 'Falls by' }], th: [{ value: 'up', label: 'ขึ้นถึงระดับ' }, { value: 'down', label: 'ลงถึงระดับ' }] };
export const ALERT_THRESHOLD_DIRECTION_OPTIONS: Record<UiLanguage, Array<Option<'above' | 'below'>>> = { en: [{ value: 'above', label: 'Crosses above' }, { value: 'below', label: 'Crosses below' }], th: [{ value: 'above', label: 'ตัดขึ้น' }, { value: 'below', label: 'ตัดลง' }] };
export const ALERT_CROSS_DIRECTION_OPTIONS: Record<UiLanguage, Array<Option<'bullish_cross' | 'bearish_cross'>>> = { en: [{ value: 'bullish_cross', label: 'Bullish cross' }, { value: 'bearish_cross', label: 'Bearish cross' }], th: [{ value: 'bullish_cross', label: 'ทองตัดขึ้น' }, { value: 'bearish_cross', label: 'ตัดขึ้นเหนือแบบขาลง' }] };
export const ALERT_STOP_LOSS_MODE_OPTIONS: Record<UiLanguage, Array<Option<PortfolioStopLossMode>>> = { en: [{ value: 'near', label: 'Near stop loss' }, { value: 'breach', label: 'Stop loss breached' }], th: [{ value: 'near', label: 'ใกล้จุดตัดขาดทุน' }, { value: 'breach', label: 'ตัดขาดทุนแล้ว' }] };
export const ALERT_MARKET_REGION_OPTIONS: Record<UiLanguage, Array<Option<MarketRegion>>> = { en: [{ value: 'cn', label: 'A-shares (cn)' }, { value: 'hk', label: 'Hong Kong (hk)' }, { value: 'us', label: 'US (us)' }], th: [{ value: 'cn', label: 'หุ้น A-share (cn)' }, { value: 'hk', label: 'หุ้นฮ่องกง (hk)' }, { value: 'us', label: 'หุ้นสหรัฐ (us)' }] };
export const ALERT_MARKET_LIGHT_STATUS_OPTIONS: Record<UiLanguage, Array<Option<MarketLightStatus>>> = { en: [{ value: 'red', label: 'Red' }, { value: 'yellow', label: 'Yellow' }], th: [{ value: 'red', label: 'ไฟแดง' }, { value: 'yellow', label: 'ไฟเหลือง' }] };

export const PORTFOLIO_TEXT = {
    en: { documentTitle: 'Portfolio Analysis - DSA', title: 'Portfolio management', description: 'Portfolio snapshots, manual entries, CSV import, and risk analysis with full-portfolio or single-account views', accountView: 'Account view', allAccounts: 'All accounts', costMethod: 'Cost method', fifo: 'FIFO', avg: 'Average cost', collapseCreate: 'Collapse', createAccount: 'New account', deleteAccount: 'Delete account', deletingAccount: 'Deleting...', deleteAccountTitle: 'Delete portfolio account', deleteAccountConfirm: 'Delete account', deleteAccountMessage: 'Delete account {name} (#{id})? It will be hidden from default lists, snapshots, risk views, and entry forms; historical ledger rows are not physically deleted.', refreshing: 'Refreshing...', refreshData: 'Refresh data', noAccounts: 'No accounts are available. Create an account before entering trades or importing CSV files.', riskDegraded: 'Risk module degraded', operationHint: 'Operation hint', analysisTask: 'Analysis task', snapshotPartialTitle: 'Portfolio valuation limitations', totalEquity: 'Total equity', totalMarketValue: 'Total market value', totalCash: 'Total cash', fxStatus: 'FX status', refreshFx: 'Refresh FX', stale: 'Stale', latest: 'Current', fxRefreshResult: 'FX refresh result', positionsTitle: 'Positions', countItems: '{count} items', noPositionsTitle: 'No positions', noPositionsDescription: 'After you enter trades or import CSV data, account-level positions appear here.', account: 'Account', code: 'Code', quantity: 'Quantity', avgCost: 'Avg cost', lastPrice: 'Last price', marketValue: 'Market value', unrealizedPnl: 'Unrealized P/L', returnPct: 'Return', action: 'Action', submitting: 'Submitting', analyze: 'Analyze', sectorConcentration: 'Sector concentration', positionConcentrationFallback: 'Sector data unavailable; showing position concentration', noConcentrationTitle: 'No concentration data', noConcentrationDescription: 'Sector or position concentration appears after the risk module finishes.', displayScope: 'Display scope', sectorDimension: 'Sector', positionDimensionFallback: 'Position fallback', sectorAlert: 'Sector concentration alert', topWeight: 'Top1 weight', yes: 'Yes', no: 'No', writeBlocked: 'You are viewing all accounts. Select a specific account before manual entry or CSV submission to avoid writing to the wrong scope.', drawdownMonitor: 'Drawdown monitor', maxDrawdown: 'Max drawdown', currentDrawdown: 'Current drawdown', alert: 'Alert', stopLossWarning: 'Stop-loss proximity warning', triggeredCount: 'Triggered', nearCount: 'Near', scope: 'Scope', accountCount: 'Accounts', currency: 'Quote currency', costMethodShort: 'Cost method', aiRiskSignals: 'AI risk signals', aiRiskUnavailable: 'Signal risk unavailable', aiRiskTotal: 'Risk signals', sellSignals: 'Sell', reduceSignals: 'Reduce', alertSignals: 'Alert', noAiRiskSignals: 'No defensive signals' }, th: { documentTitle: 'วิเคราะห์พอร์ต - DSA', title: 'จัดการพอร์ต', description: 'ภาพพอร์ต บันทึกมือ CSV import และวิเคราะห์ความเสี่ยง (สลับทั้งพอร์ต/รายบัญชีได้)', accountView: 'มุมมองรายบัญชี', allAccounts: 'ทุกบัญชี', costMethod: 'วิธีต้นทุน', fifo: 'เข้าก่อน-ออกก่อน (FIFO)', avg: 'ต้นทุนเฉลี่ย (AVG)', collapseCreate: 'ย่อฟอร์มสร้าง', createAccount: 'สร้างบัญชีใหม่', deleteAccount: 'ลบบัญชี', deletingAccount: 'กำลังลบ...', deleteAccountTitle: 'ลบบัญชีพอร์ต', deleteAccountConfirm: 'ยืนยันการลบ', deleteAccountMessage: 'ยืนยันลบบัญชี {name} (#{id}) ไหม? หลังลบ บัญชีจะหายจากรายการเริ่มต้น ภาพพอร์ต ความเสี่ยง และหน้าบันทึก ข้อมูลย้อนหลังจะไม่ถูกลบจริง', refreshing: 'กำลังรีเฟรช...', refreshData: 'รีเฟรชข้อมูล', noAccounts: 'ยังไม่มีบัญชีที่ใช้ได้ โปรดสร้างบัญชีก่อนจึงจะบันทึกการซื้อขายหรือ import CSV ได้', riskDegraded: 'โมดูลความเสี่ยงทำงานแบบลดรูป', operationHint: 'ข้อแนะนำการใช้งาน', analysisTask: 'งานวิเคราะห์', snapshotPartialTitle: 'ข้อจำกัดการประเมินมูลค่าพอร์ต', totalEquity: 'มูลค่าสุทธิรวม', totalMarketValue: 'มูลค่าตลาดรวม', totalCash: 'เงินสดรวม', fxStatus: 'สถานะอัตราแลกเปลี่ยน', refreshFx: 'รีเฟรชอัตราแลกเปลี่ยน', stale: 'ล้าสมัย', latest: 'ล่าสุด', fxRefreshResult: 'ผลการรีเฟรชอัตราแลกเปลี่ยน', positionsTitle: 'รายละเอียดสถานะ', countItems: 'รวม {count} รายการ', noPositionsTitle: 'ยังไม่มีข้อมูลสถานะการถือครอง', noPositionsDescription: 'หลังบันทึกการซื้อขายหรือ import CSV ตรงนี้จะแสดงสถานะรวมตามบัญชี', account: 'บัญชี', code: 'รหัส', quantity: 'จำนวน', avgCost: 'ต้นทุนเฉลี่ย', lastPrice: 'ราคาปัจจุบัน', marketValue: 'มูลค่าตลาด', unrealizedPnl: 'กำไร/ขาดทุนที่ยังไม่ได้รับรู้', returnPct: 'อัตราผลตอบแทน', action: 'จัดการ', submitting: 'กำลังส่ง', analyze: 'วิเคราะห์', sectorConcentration: 'การกระจายความเข้มข้นตามอุตสาหกรรม', positionConcentrationFallback: 'ข้อมูลอุตสาหกรรมยังใช้ไม่ได้ จึงแสดงความเข้มข้นรายหุ้นแทน', noConcentrationTitle: 'ยังไม่มีข้อมูลความเข้มข้น', noConcentrationDescription: 'เมื่อโมดูลความเสี่ยงคำนวณเสร็จ ตรงนี้จะแสดงการกระจายความเข้มข้นตามอุตสาหกรรมหรือรายหุ้น', displayScope: 'มุมมองการแสดงผล', sectorDimension: 'มุมมองอุตสาหกรรม', positionDimensionFallback: 'มุมมองรายหุ้น (โหมดลดรูป)', sectorAlert: 'แจ้งเตือนความเข้มข้นกลุ่มอุตสาหกรรม', topWeight: 'น้ำหนักอันดับ 1', yes: 'ใช่', no: 'ไม่', writeBlocked: 'อยู่ในมุมมอง “ทุกบัญชี” เพื่อกันบันทึกผิดพลาด โปรดเลือกบัญชีเฉพาะก่อนบันทึกมือหรือส่ง CSV', drawdownMonitor: 'ติดตามการย่อตัว', maxDrawdown: 'การย่อตัวสูงสุด', currentDrawdown: 'การย่อตัวปัจจุบัน', alert: 'แจ้งเตือน', stopLossWarning: 'เตือนใกล้จุดตัดขาดทุน', triggeredCount: 'จำนวนครั้งที่แจ้ง', nearCount: 'จำนวนครั้งที่ใกล้เกณฑ์', scope: 'มาตรฐานการนับ', accountCount: 'จำนวนบัญชี', currency: 'สกุลเงินที่ใช้นับ', costMethodShort: 'วิธีต้นทุน', aiRiskSignals: 'สัญญาณความเสี่ยงจาก AI', aiRiskUnavailable: 'สัญญาณความเสี่ยงยังใช้ไม่ได้ชั่วคราว', aiRiskTotal: 'สัญญาณความเสี่ยง', sellSignals: 'ขาย', reduceSignals: 'ลดสัดส่วน', alertSignals: 'เตือนล่วงหน้า', noAiRiskSignals: 'ยังไม่มีสัญญาณแนวรับความเสี่ยง' },
} as const;
export const PORTFOLIO_SIDE_LABELS: Record<UiLanguage, Record<PortfolioSide, string>> = { en: { buy: 'Buy', sell: 'Sell' }, th: { buy: 'ซื้อ', sell: 'ขาย' } };
export const PORTFOLIO_CASH_DIRECTION_LABELS: Record<UiLanguage, Record<PortfolioCashDirection, string>> = { en: { in: 'Inflow', out: 'Outflow' }, th: { in: 'เงินเข้า', out: 'เงินออก' } };
export const PORTFOLIO_CORPORATE_ACTION_LABELS: Record<UiLanguage, Record<PortfolioCorporateActionType, string>> = { en: { cash_dividend: 'Cash dividend', split_adjustment: 'Split adjustment' }, th: { cash_dividend: 'ปันผลเงินสด', split_adjustment: 'ปรับผลแบ่งคืน/รวมหุ้น' } };
