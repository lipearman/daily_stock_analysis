import type { DecisionAction } from '../types/analysis';

export type DecisionActionTone = 'success' | 'warning' | 'danger' | 'default';
export type DecisionActionLabelMap = Record<DecisionAction, string>;
export type DecisionActionLabelTextKey =
  | 'history.actionBuy'
  | 'history.actionAdd'
  | 'history.actionHold'
  | 'history.actionReduce'
  | 'history.actionSell'
  | 'history.actionWatch'
  | 'history.actionAvoid'
  | 'history.actionAlert';
export type DecisionActionLabelTranslator = (key: DecisionActionLabelTextKey) => string;

export const DEFAULT_DECISION_ACTION_LABELS: DecisionActionLabelMap = {
  buy: 'ซื้อ',
  add: 'เพิ่มสถานะ',
  hold: 'ถือครอง',
  reduce: 'ลดตำแหน่ง',
  sell: 'ขาย',
  watch: 'คอยดู',
  avoid: 'หลีกเลี่ยง',
  alert: 'เตือนล่วงหน้า',
};

const resolveActionLabels = (labels?: Partial<DecisionActionLabelMap>): DecisionActionLabelMap => ({
  ...DEFAULT_DECISION_ACTION_LABELS,
  ...labels,
});

export const buildDecisionActionLabelMap = (
  t: DecisionActionLabelTranslator,
): DecisionActionLabelMap => ({
  buy: t('history.actionBuy'),
  add: t('history.actionAdd'),
  hold: t('history.actionHold'),
  reduce: t('history.actionReduce'),
  sell: t('history.actionSell'),
  watch: t('history.actionWatch'),
  avoid: t('history.actionAvoid'),
  alert: t('history.actionAlert'),
});

const toneForAction = (action: DecisionAction): DecisionActionTone => {
  if (action === 'buy' || action === 'add' || action === 'hold') return 'success';
  if (action === 'sell' || action === 'reduce') return 'danger';
  return 'warning';
};

const includesAny = (value: string, phrases: readonly string[]): boolean =>
  phrases.some((phrase) => value.includes(phrase));

const normalizeEnglishAdvice = (value: string): string =>
  value.toLowerCase().replace(/[_-]/g, ' ');

const maskEnglishFinancialCompounds = (value: string): string =>
  value
    .replace(/(^|[^a-z0-9_])buy\s*back(?=$|[^a-z0-9_])/g, '$1financialcompound')
    .replace(/(^|[^a-z0-9_])sell\s*off(?=$|[^a-z0-9_])/g, '$1financialcompound');

const matchesEnglishTerm = (value: string, terms: readonly string[]): boolean =>
  terms.some((term) => new RegExp(`(^|[^a-z0-9_])${term}(?=$|[^a-z0-9_])`).test(value));

const matchesEnglishNegatedAction = (value: string, terms: readonly string[]): boolean => {
  const negationPrefix = String.raw`(?:not\s+(?:a\s+|an\s+|to\s+)?|no\s+(?:need\s+to\s+)?|need\s+not\s+|cannot\s+|can't\s+|cant\s+|do\s+not\s+|don't\s+|dont\s+)`;
  return terms.some((term) =>
    new RegExp(`(^|[^a-z0-9_])${negationPrefix}${term}(?=$|[^a-z0-9_])`).test(value),
  );
};

const hasEnglishAvoidedHoldAction = (value: string): boolean => {
  const terms = String.raw`(?:adding|accumulating|selling|reducing|trimming)`;
  return new RegExp(`(^|[^a-z0-9_])avoid\\s+${terms}(?=$|[^a-z0-9_])`).test(value);
};

const hasEnglishDeferredAction = (value: string): boolean => {
  const terms = String.raw`(?:buy|add|accumulate|sell|reduce|trim)`;
  return (
    new RegExp(`(^|[^a-z0-9_])wait(?:ing)?\\s+to\\s+${terms}(?=$|[^a-z0-9_])`).test(value) ||
    new RegExp(`(^|[^a-z0-9_])waiting\\s+(?:for|until)\\b.*?${terms}(?=$|[^a-z0-9_])`).test(value)
  );
};

export const getLegacyDecisionActionLabel = (
  advice?: string | null,
  labels?: Partial<DecisionActionLabelMap>,
): string | null => {
  const action = getLegacyDecisionAction(advice);
  if (!action) return null;
  return resolveActionLabels(labels)[action];
};

export const getLegacyDecisionAction = (advice?: string | null): DecisionAction | null => {
  const normalized = advice?.trim();
  if (!normalized) return null;
  const lower = maskEnglishFinancialCompounds(normalizeEnglishAdvice(normalized));

  if (hasEnglishDeferredAction(lower)) {
    return null;
  }

  if (
    includesAny(normalized, [
      'ยังไม่ซื้อ',
      'อย่าซื้อ',
      'ไม่ควรซื้อ',
      'อย่าซื้อก่อน',
      'ไม่จำเป็นต้องซื้อ',
      'ไม่จำเป็นต้องซื้อ',
      'ไม่แนะนำให้เปิดตำแหน่ง',
      'ยังไม่เปิดตำแหน่ง',
      'อย่าเปิดตำแหน่ง',
      'ไม่ควรเปิดตำแหน่ง',
      'อย่าเปิดตำแหน่งก่อน',
      'ไม่จำเป็นต้องเปิดตำแหน่ง',
      'ไม่จำเป็นต้องเปิดตำแหน่ง',
      'ไม่แนะนำให้วางแผน',
      'ยังไม่วางแผน',
      'ไม่ควรวางแผน',
      'ไม่เหมาะสมที่จะวางแผน',
      'ควรหยุดวางแผนก่อน',
      'ไม่จำเป็นต้องวางแผน',
      'ไม่จำเป็นต้องวางแผน',
    ]) ||
    matchesEnglishNegatedAction(lower, ['buy'])
  ) {
    return 'avoid';
  }
  if (
    includesAny(normalized, [
      'ไม่แนะนำให้เพิ่มตำแหน่ง',
      'ไม่จำเป็นต้องเพิ่มตำแหน่ง',
      'ไม่จำเป็นต้องเพิ่มตำแหน่ง',
      'ไม่ควรเพิ่มตำแหน่ง',
      'ไม่เหมาะสมที่จะเพิ่มตำแหน่ง',
      'ควรหยุดเพิ่มตำแหน่งก่อน',
      'ไม่แนะนำให้เพิ่มสินทรัพย์',
      'ไม่จำเป็นต้องเพิ่มสินทรัพย์',
      'ไม่จำเป็นต้องเพิ่มสินทรัพย์',
      'ไม่ควรเพิ่มสินทรัพย์',
      'ไม่เหมาะสมที่จะเพิ่มสินทรัพย์',
      'ควรหยุดเพิ่มสินทรัพย์ก่อน',
      'ไม่แนะนำให้ขาย',
      'ไม่จำเป็นต้องขาย',
      'ไม่จำเป็นต้องขาย',
      'ไม่ควรขาย',
      'ไม่เหมาะสมที่จะขาย',
      'ควรหยุดขายก่อน',
      'ไม่แนะนำให้ลดตำแหน่ง',
      'ไม่จำเป็นต้องลดตำแหน่ง',
      'ไม่จำเป็นต้องลดตำแหน่ง',
      'ไม่ควรลดตำแหน่ง',
      'ไม่เหมาะสมที่จะลดตำแหน่ง',
      'ควรหยุดลดตำแหน่งก่อน',
      'ไม่แนะนำให้ขายทั้งหมด',
      'ไม่จำเป็นต้องขายทั้งหมด',
      'ไม่จำเป็นต้องขายทั้งหมด',
      'ไม่ควรขายทั้งหมด',
      'ไม่เหมาะสมที่จะขายทั้งหมด',
      'ควรหยุดขายทั้งหมดก่อน',
    ]) ||
    hasEnglishAvoidedHoldAction(lower) ||
    matchesEnglishNegatedAction(lower, ['add', 'accumulate', 'sell', 'reduce', 'trim'])
  ) {
    return 'hold';
  }
  const guardMatches = new Set<DecisionAction>();
  if (
    normalized.includes('ไม่แนะนำให้ซื้อ') ||
    normalized.includes('ควรหลีกเลี่ยงการซื้อ') ||
    normalized.includes('หลีกเลี่ยง') ||
    normalized.includes('หลีกเลี่ยง') ||
    matchesEnglishTerm(lower, ['avoid'])
  ) {
    guardMatches.add('avoid');
  }
  if (
    normalized.includes('คำเตือนเกี่ยวกับความเสี่ยง') ||
    normalized.includes('การแจ้งเตือน') ||
    normalized.includes('ระวัง') ||
    lower.includes('risk alert') ||
    matchesEnglishTerm(lower, ['alert'])
  ) {
    guardMatches.add('alert');
  }
  if (guardMatches.size === 1) {
    return Array.from(guardMatches)[0];
  }
  if (guardMatches.size > 1) {
    return null;
  }

  const matches = new Set<DecisionAction>();
  if (normalized.includes('เพิ่มสถานะ') || normalized.includes('เพิ่มสินทรัพย์') || matchesEnglishTerm(lower, ['add', 'accumulate'])) {
    matches.add('add');
  }
  if (normalized.includes('ลดตำแหน่ง') || matchesEnglishTerm(lower, ['reduce', 'trim'])) {
    matches.add('reduce');
  }
  if (normalized.includes('ขายทันที') || normalized.includes('ขาย') || normalized.includes('ขายทั้งหมด') || matchesEnglishTerm(lower, ['sell'])) {
    matches.add('sell');
  }
  if (normalized.includes('ถือครอง') || normalized.includes('ติดตามการซื้อขาย') || matchesEnglishTerm(lower, ['hold'])) {
    matches.add('hold');
  }
  if (normalized.includes('คอยดู') || normalized.includes('รอคอย') || matchesEnglishTerm(lower, ['watch', 'wait'])) {
    matches.add('watch');
  }
  if (normalized.includes('ซื้อทันที') || normalized.includes('ซื้อ') || normalized.includes('วางแผน') || normalized.includes('สร้างตำแหน่ง') || matchesEnglishTerm(lower, ['buy'])) {
    matches.add('buy');
  }

  if (matches.size === 1) {
    return Array.from(matches)[0];
  }
  return null;
};

export const getDecisionActionLabel = (
  action?: DecisionAction | null,
  actionLabel?: string | null,
  legacyAdvice?: string | null,
  emptyLabel: string | null = 'แนะนำ',
  labels?: Partial<DecisionActionLabelMap>,
): string | null => {
  const actionLabels = resolveActionLabels(labels);
  if (action) return actionLabels[action];
  const explicitLabel = actionLabel?.trim();
  if (explicitLabel) return explicitLabel;
  return getLegacyDecisionActionLabel(legacyAdvice, actionLabels) || emptyLabel;
};

export const getDecisionActionTone = (
  action?: DecisionAction | null,
  actionLabel?: string | null,
  legacyAdvice?: string | null,
): DecisionActionTone => {
  if (action) return toneForAction(action);

  const label = actionLabel?.trim() || '';
  if (label) {
    const lowerLabel = normalizeEnglishAdvice(label);
    if (label.includes('ซื้อ') || label.includes('เพิ่มสถานะ') || label.includes('ถือครอง')) return 'success';
    if (label.includes('ขาย') || label.includes('ลดตำแหน่ง') || label.includes('ขายทั้งหมด')) return 'danger';
    if (label.includes('คอยดู') || label.includes('รอคอย') || label.includes('หลีกเลี่ยง') || label.includes('เตือนล่วงหน้า')) {
      return 'warning';
    }
    if (matchesEnglishTerm(lowerLabel, ['buy', 'add', 'hold'])) return 'success';
    if (matchesEnglishTerm(lowerLabel, ['sell', 'reduce', 'trim'])) return 'danger';
    if (matchesEnglishTerm(lowerLabel, ['watch', 'wait', 'avoid', 'alert'])) return 'warning';
    return 'default';
  }

  const legacyAction = getLegacyDecisionAction(legacyAdvice);
  if (legacyAction) return toneForAction(legacyAction);

  return 'default';
};
