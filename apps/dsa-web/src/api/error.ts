import axios from 'axios';

export type ApiErrorCategory =
  | 'agent_disabled'
  | 'missing_params'
  | 'llm_not_configured'
  | 'model_tool_incompatible'
  | 'invalid_tool_call'
  | 'portfolio_oversell'
  | 'portfolio_busy'
  | 'upstream_llm_400'
  | 'upstream_timeout'
  | 'upstream_network'
  | 'local_connection_failed'
  | 'http_error'
  | 'unknown';

export interface ParsedApiError {
  title: string;
  message: string;
  rawMessage: string;
  status?: number;
  category: ApiErrorCategory;
  code?: string;
}

type ResponseLike = {
  status?: number;
  data?: unknown;
  statusText?: string;
};

type ErrorCarrier = {
  response?: ResponseLike;
  code?: string;
  message?: string;
  parsedError?: ParsedApiError;
  cause?: unknown;
};

type CreateParsedApiErrorOptions = {
  title: string;
  message: string;
  rawMessage?: string;
  status?: number;
  category?: ApiErrorCategory;
  code?: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function pickString(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return null;
}

function stringifyValue(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }

  if (typeof value === 'string') {
    return value.trim() || null;
  }

  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }

  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function getResponse(error: unknown): ResponseLike | undefined {
  if (!isRecord(error)) {
    return undefined;
  }

  const response = (error as ErrorCarrier).response;
  return response && typeof response === 'object' ? response : undefined;
}

function getErrorCode(error: unknown): string | undefined {
  return isRecord(error) && typeof (error as ErrorCarrier).code === 'string'
    ? (error as ErrorCarrier).code
    : undefined;
}

function getErrorMessage(error: unknown): string | null {
  if (typeof error === 'string') {
    return error.trim() || null;
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message.trim();
  }

  if (isRecord(error) && typeof (error as ErrorCarrier).message === 'string') {
    const message = (error as ErrorCarrier).message?.trim();
    return message || null;
  }

  return null;
}

function getCauseMessage(error: unknown): string | null {
  if (!isRecord(error)) {
    return null;
  }

  return getErrorMessage((error as ErrorCarrier).cause);
}

function buildMatchText(parts: Array<string | undefined | null>): string {
  return parts
    .filter((part): part is string => typeof part === 'string' && part.trim().length > 0)
    .join(' | ')
    .toLowerCase();
}

function includesAny(haystack: string, needles: string[]): boolean {
  return needles.some((needle) => haystack.includes(needle.toLowerCase()));
}

function extractValidationDetail(detail: unknown): string | null {
  if (!Array.isArray(detail)) {
    return null;
  }

  const parts = detail
    .map((item) => {
      if (!isRecord(item)) {
        return stringifyValue(item);
      }

      const location = Array.isArray(item.loc)
        ? item.loc.map((segment) => String(segment)).join('.')
        : null;
      const message = pickString(item.msg, item.message, item.error);
      if (!location && !message) {
        return stringifyValue(item);
      }
      return [location, message].filter(Boolean).join(': ');
    })
    .filter((entry): entry is string => Boolean(entry));

  return parts.length > 0 ? parts.join('; ') : null;
}

function extractErrorCode(data: unknown): string | null {
  if (!isRecord(data)) {
    return null;
  }

  const detail = data.detail;
  if (isRecord(detail)) {
    return pickString(detail.error, detail.code, data.error, data.code);
  }

  return pickString(data.error, data.code);
}

function extractConfigValidationIssues(data: unknown): string | null {
  if (!isRecord(data)) return null;
  const payload = isRecord(data.detail) ? data.detail : data;
  if (!Array.isArray(payload.issues)) return null;
  const messages = payload.issues.filter(isRecord).map((issue) => {
    const key = pickString(issue.key);
    let message = pickString(issue.message);
    if (issue.code === 'missing_api_key') message = 'โปรดกรอก API Key ของช่องทางนี้';
    if (issue.code === 'missing_models') message = 'โปรดกรอกโมเดลที่บัญชีใช้ได้';
    if (issue.code === 'unknown_model') message = 'โปรดเลือกโมเดลจากช่องทางที่เปิดใช้งาน หรือลบตัวเลือกโมเดลที่ไม่ถูกต้อง';
    return message ? [key, message].filter(Boolean).join('：') : null;
  }).filter((message): message is string => Boolean(message));
  return messages.length ? messages.join('\n') : null;
}

export function extractErrorPayloadText(data: unknown): string | null {
  if (typeof data === 'string') {
    return data.trim() || null;
  }

  if (Array.isArray(data)) {
    return extractValidationDetail(data) ?? stringifyValue(data);
  }

  if (!isRecord(data)) {
    return stringifyValue(data);
  }

  const detail = data.detail;
  if (isRecord(detail)) {
    return (
      pickString(detail.message, detail.error)
      ?? extractValidationDetail(detail.detail)
      ?? stringifyValue(detail)
    );
  }

  return (
    pickString(
      detail,
      data.message,
      data.error,
      data.title,
      data.reason,
      data.description,
      data.msg,
    )
    ?? extractValidationDetail(detail)
    ?? stringifyValue(data)
  );
}

export function createParsedApiError(options: CreateParsedApiErrorOptions): ParsedApiError {
  return {
    title: options.title,
    message: options.message,
    rawMessage: options.rawMessage?.trim() || options.message,
    status: options.status,
    category: options.category ?? 'unknown',
    ...(options.code ? { code: options.code } : {}),
  };
}

export function isParsedApiError(value: unknown): value is ParsedApiError {
  return isRecord(value)
    && typeof value.title === 'string'
    && typeof value.message === 'string'
    && typeof value.rawMessage === 'string'
    && typeof value.category === 'string';
}

export function isApiRequestError(
  value: unknown,
): value is Error & ErrorCarrier & { parsedError: ParsedApiError } {
  return value instanceof Error
    && isRecord(value)
    && isParsedApiError((value as ErrorCarrier).parsedError);
}

export function formatParsedApiError(parsed: ParsedApiError): string {
  if (!parsed.title.trim()) {
    return parsed.message;
  }
  if (parsed.title === parsed.message) {
    return parsed.title;
  }
  return `${parsed.title}：${parsed.message}`;
}

export function getParsedApiError(error: unknown): ParsedApiError {
  if (isParsedApiError(error)) {
    return error;
  }
  if (isRecord(error) && isParsedApiError((error as ErrorCarrier).parsedError)) {
    return (error as ErrorCarrier).parsedError as ParsedApiError;
  }
  return parseApiError(error);
}

export function createApiError(
  parsed: ParsedApiError,
  extra: { response?: ResponseLike; code?: string; cause?: unknown } = {},
): Error & ErrorCarrier & { status?: number; category: ApiErrorCategory; rawMessage: string } {
  const apiError = new Error(formatParsedApiError(parsed)) as Error & ErrorCarrier & {
    status?: number;
    category: ApiErrorCategory;
    rawMessage: string;
  };
  apiError.name = 'ApiRequestError';
  apiError.parsedError = parsed;
  apiError.response = extra.response;
  apiError.code = extra.code ?? parsed.code;
  apiError.status = parsed.status;
  apiError.category = parsed.category;
  apiError.rawMessage = parsed.rawMessage;
  if (extra.cause !== undefined) {
    apiError.cause = extra.cause;
  }
  return apiError;
}

export function attachParsedApiError(error: unknown): ParsedApiError {
  const parsed = parseApiError(error);
  if (isRecord(error)) {
    const carrier = error as ErrorCarrier;
    carrier.parsedError = parsed;
  }
  if (error instanceof Error) {
    error.name = 'ApiRequestError';
    error.message = formatParsedApiError(parsed);
  }
  return parsed;
}

export function isLocalConnectionFailure(error: unknown): boolean {
  return parseApiError(error).category === 'local_connection_failed';
}

export function parseApiError(error: unknown): ParsedApiError {
  const response = getResponse(error);
  const status = response?.status;
  const payloadText = extractErrorPayloadText(response?.data);
  const errorCode = extractErrorCode(response?.data);
  const errorMessage = getErrorMessage(error);
  const causeMessage = getCauseMessage(error);
  const code = getErrorCode(error);
  const rawMessage = pickString(payloadText, response?.statusText, errorMessage, causeMessage, code)
    ?? 'คำขอไม่สำเร็จ โปรดลองอีกครั้งภายหลัง';
  const matchText = buildMatchText([rawMessage, errorMessage, causeMessage, code, errorCode, response?.statusText]);

  if (errorCode === 'validation_failed') {
    const issues = extractConfigValidationIssues(response?.data);
    const message = issues
      ? `请修正以下配置后重试：\n${issues}`
      : 'โปรดตรวจ API Key, โมเดล และพารามิเตอร์การรันของช่องทางแล้วลองใหม่';
    return createParsedApiError({
      title: 'ต้องปรับการตั้งค่า',
      message,
      rawMessage: message,
      status,
      category: 'http_error',
      code: errorCode,
    });
  }

  if (errorCode === 'backend_removed') {
    return createParsedApiError({
      title: 'ระบบถาม-ตอบหุ้นถูกถอดออกแล้ว', message: rawMessage,
      rawMessage, status, code: 'backend_removed', category: 'http_error',
    });
  }

  if (errorCode === 'session_state_conflict' || code === 'session_state_conflict') {
    return createParsedApiError({
      title: 'เซสชันถูกอัปเดตแล้ว', message: 'โปรดรีเฟรชเซสชันแล้วลองใหม่ ข้อความที่พิมพ์ไว้ยังไม่ถูกรับ โปรดเก็บคำถามและตัวเลือกไว้',
      rawMessage, status, code: 'session_state_conflict', category: 'http_error',
    });
  }

  if (includesAny(matchText, ['agent mode is not enabled', 'agent_mode'])) {
    return createParsedApiError({
      title: 'ยังไม่ได้เปิดโหมด Agent',
      message: 'ฟีเจอร์นี้ต้องใช้โหมด Agent โปรดเปิดก่อนแล้วลองใหม่',
      rawMessage,
      status,
      category: 'agent_disabled',
    });
  }

  const hasStockCodeField = includesAny(matchText, ['stock_code', 'stock_codes']);
  const hasMissingParamText = includesAny(matchText, ['必须提供 stock_code 或 stock_codes', 'missing', 'required']);
  if (hasStockCodeField && hasMissingParamText) {
    return createParsedApiError({
      title: 'คำขอขาดพารามิเตอร์ที่จำเป็น',
      message: 'โปรดกรอกรหัสหุ้นหรือข้อมูลที่จำเป็นก่อนแล้วลองใหม่',
      rawMessage,
      status,
      category: 'missing_params',
    });
  }

  if (errorCode === 'portfolio_oversell' || includesAny(matchText, ['oversell detected'])) {
    return createParsedApiError({
      title: 'จำนวนขายเกินสถานะที่ถืออยู่',
      message: 'จำนวนขายเกินสถานะที่มีอยู่ โปรดลบหรือแก้รายการขายที่เกี่ยวข้องแล้วลองใหม่',
      rawMessage,
      status,
      category: 'portfolio_oversell',
    });
  }

  if (errorCode === 'portfolio_busy' || includesAny(matchText, ['portfolio ledger is busy'])) {
    return createParsedApiError({
      title: 'บัญชีสถานะการถือครองกำลังติดงาน',
      message: 'บัญชีสถานะกำลังประมวลผลรายการอื่นอยู่ โปรดลองอีกครั้งภายหลัง',
      rawMessage,
      status,
      category: 'portfolio_busy',
    });
  }

  if (errorCode === 'screening_unavailable' || includesAny(matchText, ['内建选股引擎初始化失败', '选股功能初始化失败'])) {
    return createParsedApiError({
      title: 'ระบบคัดกรองหุ้นยังไม่พร้อม',
      message: 'ระบบคัดกรองหุ้นใช้ไม่ได้ชั่วคราว โปรดตรวจการตั้งค่ากลยุทธ์ ข้อมูลที่ต้องใช้ และ log ของเซอร์วิส',
      rawMessage,
      status,
      category: 'http_error',
      code: 'screening_unavailable',
    });
  }

  if (errorCode === 'screening_screen_task_not_found') {
    return createParsedApiError({
      title: 'งานคัดกรองหุ้นกู้คืนไม่ได้',
      message: 'เซิร์ฟเวอร์ไม่พบงานคัดกรองครั้งนี้ อาจเพราะ backend รีสตาร์ทหรือรายการถูกเคลียร์ โปรดรันคัดกรองใหม่',
      rawMessage,
      status,
      category: 'http_error',
      code: 'screening_screen_task_not_found',
    });
  }

  if (errorCode === 'screening_screen_failed') {
    return createParsedApiError({
      title: 'คัดกรองหุ้นไม่สำเร็จ',
      message: 'การเข้าถึงข้อมูลราคา สแนปช็อต หรือโมเดลล้มเหลว โปรดลองอีกครั้ง หรือตรวจเครือข่ายและ proxy',
      rawMessage,
      status,
      category: 'upstream_network',
      code: 'screening_screen_failed',
    });
  }

  const noConfiguredLlm = (
    includesAny(matchText, ['all llm models failed']) && includesAny(matchText, ['last error: none'])
  ) || includesAny(matchText, [
    'no llm configured',
    'no effective primary model configured',
    'litellm_model not configured',
    'ai analysis will be unavailable',
  ]);
  if (noConfiguredLlm) {
    return createParsedApiError({
      title: 'ระบบยังไม่มีโมเดล LLM ที่ตั้งค่าไว้',
      message: 'โปรดตั้งค่าโมเดลหลัก ช่องทางที่ใช้ได้ หรือ API Key ที่เกี่ยวข้องในหน้าตั้งค่าก่อนแล้วลองใหม่',
      rawMessage,
      status,
      category: 'llm_not_configured',
    });
  }

  if (includesAny(matchText, [
    'tool call',
    'function call',
    'does not support tools',
    'tools is not supported',
    'reasoning',
  ])) {
    return createParsedApiError({
      title: 'โมเดลปัจจุบันไม่รองรับ tool calling',
      message: 'โมเดลปัจจุบันไม่เหมาะกับงาน Agent/tool calling โปรดเปลี่ยนเป็นโมเดลที่รองรับแล้วลองใหม่',
      rawMessage,
      status,
      category: 'model_tool_incompatible',
    });
  }

  if (includesAny(matchText, [
    'thought_signature',
    'missing function',
    'missing tool',
    'invalid tool call',
    'invalid function call',
  ])) {
    return createParsedApiError({
      title: 'โครงสร้างข้อมูลที่โมเดลต้นทางส่งกลับไม่ครบถ้วน',
      message: 'โครงสร้าง tool call ที่โมเดลต้นทางส่งกลับไม่ตรงรูปแบบ โปรดเปลี่ยนโมเดลหรือปิดโหมด reasoning ที่เกี่ยวข้องแล้วลองใหม่',
      rawMessage,
      status,
      category: 'invalid_tool_call',
    });
  }

  if (includesAny(matchText, ['timeout', 'timed out', 'read timeout', 'connect timeout']) || code === 'ECONNABORTED') {
    return createParsedApiError({
      title: 'การเชื่อมต่อบริการต้นทางหมดเวลา',
      message: 'เซิร์ฟเวอร์เข้าถึงบริการภายนอกไม่สำเร็จภายในเวลาที่กำหนด โปรดลองอีกครั้ง หรือตรวจเครือข่ายและ proxy',
      rawMessage,
      status,
      category: 'upstream_timeout',
    });
  }

  if (
    status === 502
    || status === 503
    || includesAny(matchText, [
      'dns',
      'enotfound',
      'name or service not known',
      'temporary failure in name resolution',
      'proxy',
      'tunnel',
      '502',
      '503',
    ])
  ) {
    return createParsedApiError({
      title: 'เซิร์ฟเวอร์เข้าถึงบริการภายนอกไม่ได้',
      message: 'หน้าเว็บเชื่อมต่อเซิร์ฟเวอร์ในเครื่องได้ แต่เซิร์ฟเวอร์เข้าถึงโมเดลภายนอกหรือ API ข้อมูลไม่สำเร็จ โปรดตรวจ proxy, DNS หรือการตั้งค่า outbound',
      rawMessage,
      status,
      category: 'upstream_network',
    });
  }

  const hasLlmProviderHint = includesAny(matchText, [
    'chat/completions',
    'generativelanguage',
    'openai',
    'gemini',
  ]);
  if (status === 400 && hasLlmProviderHint) {
    return createParsedApiError({
      title: 'โมเดลต้นทางปฏิเสธคำขอนี้',
      message: 'เซิร์ฟเวอร์ในเครื่องทำงานปกติ แต่โมเดลต้นทางปฏิเสธคำขอ โปรดตรวจชื่อโมเดล รูปแบบพารามิเตอร์ หรือความเข้ากันได้ของ tool calling',
      rawMessage,
      status,
      category: 'upstream_llm_400',
    });
  }

  const localConnectionFailed = !response && (
    includesAny(matchText, ['fetch failed', 'failed to fetch', 'network error', 'connection refused', 'econnrefused'])
    || code === 'ERR_NETWORK'
    || code === 'ECONNREFUSED'
  );
  if (localConnectionFailed) {
    return createParsedApiError({
      title: 'เชื่อมต่อเซิร์ฟเวอร์ในเครื่องไม่ได้',
      message: 'เบราว์เซอร์เชื่อมต่อ Web server ในเครื่องไม่ได้ โปรดตรวจว่าเซิร์ฟเวอร์เริ่มทำงานแล้ว ที่อยู่ถูกต้อง และพอร์ตเปิดอยู่',
      rawMessage,
      status,
      category: 'local_connection_failed',
    });
  }

  if (payloadText || status) {
    return createParsedApiError({
      title: 'คำขอไม่สำเร็จ',
      message: payloadText ?? `请求未成功完成（HTTP ${status}）。`,
      rawMessage,
      status,
      category: 'http_error',
    });
  }

  return createParsedApiError({
    title: 'คำขอไม่สำเร็จ',
    message: rawMessage,
    rawMessage,
    status,
    category: 'unknown',
  });
}

export function toApiErrorMessage(error: unknown, fallback = 'คำขอไม่สำเร็จ โปรดลองอีกครั้งภายหลัง'): string {
  const parsed = getParsedApiError(error);
  const message = formatParsedApiError(parsed);
  return message.trim() || fallback;
}

export function isAxiosApiError(error: unknown): boolean {
  return axios.isAxiosError(error);
}
