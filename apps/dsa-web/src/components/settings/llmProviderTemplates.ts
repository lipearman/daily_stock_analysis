export type ChannelProtocol = 'openai' | 'deepseek' | 'gemini' | 'anthropic' | 'vertex_ai' | 'ollama';
export type LLMProviderCapability =
  | 'openai-compatible'
  | 'aggregator'
  | 'official-api'
  | 'model-discovery'
  | 'vision'
  | 'local-runtime';

/** Filter recommendations only; saved and hand-typed model IDs stay in channel state. */
export function filterDiscoveredTextModels(models: string[]): string[] {
  const miniMaxId = (model: string) => model.split('/').at(-1)?.toLowerCase() || '';
  const current = (model: string) => /^minimax-m(?:3|3\.1-flash)(?::free|-free|-discount)?$/.test(miniMaxId(model));
  const filtered = models.filter((model) => !/^minimax-(?:m\d|(?:text|vl)-01)/.test(miniMaxId(model)) || current(model));
  const miniMaxModels = filtered.filter(current).sort((left, right) => (
    Number(miniMaxId(right).startsWith('minimax-m3.1-flash'))
    - Number(miniMaxId(left).startsWith('minimax-m3.1-flash'))
  ));
  let index = 0;
  return filtered.map((model) => current(model) ? miniMaxModels[index++] : model);
}

export const MODELFLARE_APP_REGISTRATION_URL =
  'https://modelflare.dev/sign-up?utm_source=daily_stock_analysis&utm_campaign=app';
export const X6AI_REGISTRATION_URL = 'https://console.x6pro.io/register?code=zJ2qSdns';
export const MODELFLARE_DEFAULT_MODEL = 'gpt-6.1-sol';

export interface LLMProviderTemplate {
  channelId: string;
  label: string;
  protocol: ChannelProtocol;
  baseUrl: string;
  placeholderModels: string;
  capabilities: LLMProviderCapability[];
  configHint?: string;
  registration?: { label: string; url: string };
  officialSources: Array<{
    label: string;
    url: string;
  }>;
}

export const LLM_PROVIDER_CAPABILITY_LABELS: Record<LLMProviderCapability, { label: string; hint: string }> = {
  'openai-compatible': {
    label: 'OpenAI เข้ากันได้',
    hint: 'กำหนด Base URL ตามจุดสิ้นสุดที่เข้ากันได้กับ OpenAI ไม่ต้องเชื่อมต่อ /chat/completions เพิ่มเติม',
  },
  aggregator: {
    label: 'แพลตฟอร์มรวม',
    hint: 'การมองเห็นโมเดล เส้นทาง และราคาอาจเปลี่ยนแปลงไปพร้อมกับสิทธิ์ของบัญชีและนโยบายแพลตฟอร์ม',
  },
  'official-api': {
    label: 'API อย่างเป็นทางการ',
    hint: 'ใช้โปรโตคอลทางการหรือจุดเข้าถึงที่เข้ากันได้ทางการของผู้ให้บริการ',
  },
  'model-discovery': {
    label: 'โมเดลที่สามารถได้รับ',
    hint: 'สนับสนุนการลองขอรายการโมเดลผ่าน /models ผลลัพธ์ที่แท้จริงยังขึ้นอยู่กับสิทธิ์ของบัญชีและ API Key',
  },
  vision: {
    label: 'แจ้งเตือน Vision',
    hint: 'แม่แบบแจ้งเตือนว่า provider นี้ใช้บ่อยในฉาก Vision ความสามารถของโมเดลเฉพาะยังขึ้นอยู่กับบัญชีและรายการโมเดล',
  },
  'local-runtime': {
    label: 'การทำงานในท้องถิ่น',
    hint: 'ต้องการสภาพแวดล้อมการทำงนปัจจุบันที่สามารถเข้าถึงบริการท้องถิ่นที่สอดคล้องกัน',
  },
};

export const LLM_PROVIDER_TEMPLATES: LLMProviderTemplate[] = [
  {
    channelId: 'modelflare',
    registration: { label: 'ลงทะเบียน Modelflare', url: MODELFLARE_APP_REGISTRATION_URL },
    label: 'Modelflare (แพลตฟอร์มรวม)',
    protocol: 'openai',
    baseUrl: 'https://modelflare.dev/v1',
    placeholderModels: MODELFLARE_DEFAULT_MODEL,
    capabilities: ['openai-compatible', 'aggregator', 'model-discovery'],
    configHint:
      'กลุ่มเส้นทางของ API Key ต้องสนับสนุนโมเดลที่เลือก โปรดใช้ ID โมเดลจากคอนโซลหรือผลลัพธ์การรับโมเดล Base URL ของช่องทาง modelflare ใช้ที่อยู่ /v1 ปกติเมื่อว่างเปล่า สามารถเขียนทับตามความต้องการ ไม่ต้องเชื่อมต่อ /chat/completions เพิ่มเติม',
    officialSources: [
      { label: 'ลงทะเบียน Modelflare เฉพาะ', url: MODELFLARE_APP_REGISTRATION_URL },
      { label: 'Modelflare Docs', url: 'https://docs.modelflare.dev/' },
      { label: 'Modelflare Models & Pricing', url: 'https://modelflare.dev/pricing' },
    ],
  },
  {
    channelId: 'x6ai',
    registration: { label: 'ลงทะเบียน x6.ai', url: X6AI_REGISTRATION_URL },
    label: 'x6.ai (แพลตฟอร์มรวม)',
    protocol: 'openai',
    baseUrl: 'https://api.x6.ai/v1',
    placeholderModels: '',
    capabilities: ['openai-compatible', 'aggregator', 'model-discovery'],
    configHint: 'โปรดค้นหา ID โมเดลที่ใช้งานได้ของบัญชีผ่าน \'รับโมเดล\' จากนั้นเลือกโมเดลและทดสอบการเชื่อมต่อ ความสามารถและราคาที่แท้จริงอยู่ที่คอนโซล x6.ai',
    officialSources: [
      { label: 'ลงทะเบียน x6.ai เฉพาะ', url: X6AI_REGISTRATION_URL },
      { label: 'เอกสาร API x6.ai', url: 'https://x6.ai/zh/docs' },
      { label: 'รายการโมเดล x6.ai', url: 'https://x6.ai/zh/models' },
    ],
  },
  {
    channelId: 'aihubmix',
    label: 'AIHubmix (แพลตฟอร์มรวม)',
    protocol: 'openai',
    baseUrl: 'https://aihubmix.com/v1',
    placeholderModels: 'gpt-6.1-sol,claude-sonnet-4-6,gemini-3.6-flash',
    capabilities: ['openai-compatible', 'aggregator'],
    officialSources: [{ label: 'AIHubmix', url: 'https://inferera.com/?aff=CfMq' }],
  },
  {
    channelId: 'deepseek',
    label: 'DeepSeek อย่างเป็นทางการ',
    protocol: 'deepseek',
    baseUrl: 'https://api.deepseek.com',
    placeholderModels: 'deepseek-v4-flash,deepseek-v4-pro',
    capabilities: ['official-api', 'openai-compatible'],
    officialSources: [{ label: 'DeepSeek API Docs', url: 'https://api-docs.deepseek.com/' }],
  },
  {
    channelId: 'dashscope',
    label: 'Tongyi Qianwen (Dashscope)',
    protocol: 'openai',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    placeholderModels: 'qwen3.6-plus,qwen3.6-flash',
    capabilities: ['openai-compatible', 'model-discovery'],
    officialSources: [
      { label: 'DashScope Text Generation', url: 'https://help.aliyun.com/zh/model-studio/text-generation-model/' },
    ],
  },
  {
    channelId: 'zhipu',
    label: 'Zhipu GLM',
    protocol: 'openai',
    baseUrl: 'https://open.bigmodel.cn/api/paas/v4',
    placeholderModels: 'glm-5.1,glm-4.7-flash',
    capabilities: ['openai-compatible'],
    officialSources: [{ label: 'Zhipu Model Overview', url: 'https://docs.bigmodel.cn/cn/guide/start/model-overview' }],
  },
  {
    channelId: 'moonshot',
    label: 'Moonshot (ด้านมืดของจันทร์)',
    protocol: 'openai',
    baseUrl: 'https://api.moonshot.cn/v1',
    placeholderModels: 'kimi-k2.6,kimi-k2.5',
    capabilities: ['openai-compatible'],
    officialSources: [{ label: 'Kimi Platform Docs', url: 'https://platform.kimi.com/docs/models' }],
  },
  {
    channelId: 'minimax',
    label: 'MiniMax อย่างเป็นทางการ',
    protocol: 'openai',
    baseUrl: 'https://api.minimax.io/v1',
    placeholderModels: 'MiniMax-M3.1-Flash,MiniMax-M3',
    capabilities: ['openai-compatible'],
    officialSources: [
      { label: 'MiniMax OpenAI API', url: 'https://platform.minimax.io/docs/api-reference/text-chat' },
      { label: 'MiniMax Models', url: 'https://platform.minimax.io/docs/api-reference/models/openai/list-models' },
    ],
  },
  {
    channelId: 'volcengine',
    label: 'Volcano Ark (เตา)',
    protocol: 'openai',
    baseUrl: 'https://ark.cn-beijing.volces.com/api/v3',
    placeholderModels: 'doubao-seed-1-6-251015,doubao-seed-1-6-thinking-251015',
    capabilities: ['openai-compatible'],
    configHint: 'ยืนยันว่าจุดสิ้นสุด / ภูมิภาคการสรุปออนไลน์และจุดเข้าถึงเฉพาะ Coding Plan ไม่ควรผสมผสานกัน',
    officialSources: [
      { label: 'Volcengine Ark Inference', url: 'https://www.volcengine.com/docs/82379/2121998' },
      { label: 'Volcengine Ark Models', url: 'https://www.volcengine.com/docs/82379/1949118' },
    ],
  },
  {
    channelId: 'siliconflow',
    label: 'SiliconFlow ฐานซิลิคอน',
    protocol: 'openai',
    baseUrl: 'https://api.siliconflow.cn/v1',
    placeholderModels: 'deepseek-ai/DeepSeek-V3.2,Qwen/Qwen3-235B-A22B-Thinking-2507',
    capabilities: ['openai-compatible', 'model-discovery'],
    configHint: 'รายการโมเดลและการมองเห็นโมเดลขึ้นอยู่กับสิทธิ์ของบัญชีและ API Key',
    officialSources: [{ label: 'SiliconFlow Models', url: 'https://docs.siliconflow.cn/quickstart/models' }],
  },
  {
    channelId: 'openrouter',
    label: 'OpenRouter',
    protocol: 'openai',
    baseUrl: 'https://openrouter.ai/api/v1',
    placeholderModels: '~anthropic/claude-sonnet-latest,~openai/gpt-latest',
    capabilities: ['openai-compatible', 'aggregator', 'model-discovery'],
    configHint: 'รายการโมเดลและการมองเห็นโมเดลขึ้นอยู่กับสิทธิ์ของบัญชีและ API Key',
    officialSources: [
      { label: 'OpenRouter Models API', url: 'https://openrouter.ai/docs/api/api-reference/models/get-models' },
    ],
  },
  {
    channelId: 'requesty',
    label: 'Requesty',
    protocol: 'openai',
    baseUrl: 'https://router.requesty.ai/v1',
    placeholderModels: 'claude-sonnet-4-6,gpt-6.1-sol',
    capabilities: ['openai-compatible', 'aggregator', 'model-discovery'],
    configHint: 'รายการโมเดลและการมองเห็นโมเดลขึ้นอยู่กับสิทธิ์ของบัญชีและ API Key สำหรับภูมิภาค EU สามารถเปลี่ยน Base URL เป็น https://router.eu.requesty.ai/v1',
    officialSources: [
      { label: 'Requesty Models API', url: 'https://docs.requesty.ai/api-reference/endpoint/models-list' },
    ],
  },
  {
    channelId: 'gemini',
    label: 'Gemini อย่างเป็นทางการ',
    protocol: 'gemini',
    baseUrl: '',
    placeholderModels: 'gemini-3.6-flash,gemini-3.5-flash-lite',
    capabilities: ['official-api', 'vision'],
    officialSources: [{ label: 'Gemini Models', url: 'https://ai.google.dev/gemini-api/docs/models' }],
  },
  {
    channelId: 'anthropic',
    label: 'Anthropic อย่างเป็นทางการ',
    protocol: 'anthropic',
    baseUrl: '',
    placeholderModels: 'claude-sonnet-4-6,claude-opus-4-7',
    capabilities: ['official-api'],
    officialSources: [
      { label: 'Anthropic Models', url: 'https://docs.anthropic.com/en/docs/about-claude/models/all-models' },
    ],
  },
  {
    channelId: 'openai',
    label: 'OpenAI อย่างเป็นทางการ',
    protocol: 'openai',
    baseUrl: 'https://api.openai.com/v1',
    placeholderModels: 'gpt-6.1-sol,gpt-6.1-terra',
    capabilities: ['official-api', 'openai-compatible', 'model-discovery'],
    officialSources: [{ label: 'OpenAI Models', url: 'https://platform.openai.com/docs/models' }],
  },
  {
    channelId: 'ollama',
    label: 'Ollama (ท้องถิ่น)',
    protocol: 'ollama',
    baseUrl: 'http://127.0.0.1:11434',
    placeholderModels: 'llama3.2,qwen2.5',
    capabilities: ['local-runtime'],
    configHint: 'ต้องการเครื่องปัจจุบัน Docker หรือ self-hosted runner เพื่อเข้าถึงบริการ Ollama',
    officialSources: [{ label: 'Ollama API', url: 'https://github.com/ollama/ollama/blob/main/docs/api.md' }],
  },
  {
    channelId: 'anspire',
    label: 'Anspire Open',
    protocol: 'openai',
    baseUrl: 'https://open-gateway.anspire.cn/v6',
    placeholderModels: 'Doubao-Seed-2.0-lite,Doubao-Seed-2.0-pro,qwen3.5-flash',
    capabilities: ['openai-compatible'],
    configHint:
      'สามารถใช้ ANSPIRE_API_KEYS เดียวกันในช่องทางการค้นหาและ LLM โมเดลและเกตเวย์ด้านล่างเป็นตัวอย่างการกำหนดค่า ความสามารถในการใช้งานที่แท้จริงขึ้นอยู่กับสิทธิ์ของบัญชีและคอนโซล แนะนำให้คลิก \'ทดสอบการเชื่อมต่อ\' เพื่อยืนยัน',
    officialSources: [
      { label: 'Anspire Open', url: 'https://open.anspire.cn/dsa?share_code=QFBC0FYC' },
      {
        label: 'LiteLLM OpenAI-compatible',
        url: 'https://docs.litellm.ai/docs/providers/openai_compatible',
      },
    ],
  },
  {
    channelId: 'custom',
    label: 'ช่องทางที่กำหนดเอง',
    protocol: 'openai',
    baseUrl: '',
    placeholderModels: 'model-name-1,model-name-2',
    capabilities: [],
    officialSources: [],
  },
];

export const LLM_PROVIDER_TEMPLATE_BY_ID: Record<string, LLMProviderTemplate> = Object.fromEntries(
  LLM_PROVIDER_TEMPLATES.map((template) => [template.channelId, template]),
);

export function getProviderTemplate(channelId: string): LLMProviderTemplate | undefined {
  if (!Object.prototype.hasOwnProperty.call(LLM_PROVIDER_TEMPLATE_BY_ID, channelId)) {
    return undefined;
  }
  return LLM_PROVIDER_TEMPLATE_BY_ID[channelId];
}

export function isKnownProviderTemplate(channelId: string): boolean {
  return channelId !== 'custom' && Boolean(getProviderTemplate(channelId));
}

export const MODEL_PLACEHOLDERS_BY_PROTOCOL: Record<ChannelProtocol, string> = {
  openai: 'gpt-6.1-sol,qwen3.6-plus',
  deepseek: 'deepseek-v4-flash,deepseek-v4-pro',
  gemini: 'gemini-3.6-flash,gemini-3.5-flash-lite',
  anthropic: 'claude-sonnet-4-6,claude-opus-4-7',
  vertex_ai: 'gemini-3.6-flash',
  ollama: 'llama3.2,qwen2.5',
};
