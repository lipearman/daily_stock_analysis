# -*- coding: utf-8 -*-
"""Translate Chinese market data names (sectors, concepts, indices) for display.

Sources of Chinese names are the A-share data providers (EastMoney/AkShare):
industry sectors, concept themes, and index names.  The web UI, reports, and
notifications render these raw names, which look out of place for non-Chinese
users.  This module maps the common ones via a static dictionary and falls
back to a batched LLM translation (paid once, cached on disk) for anything
unknown, so new sector names keep getting translated without code changes.

Fail-open by design: if the LLM call fails, the original Chinese name is kept.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

_HAS_CJK = re.compile(r"[\u4e00-\u9fff]")
_CACHE_FILE = Path("data") / "cache" / "zh_name_translations.json"
_LLM_BATCH_LIMIT = 60

# zh -> Thai, for the EastMoney industry sectors, hot concepts, and indices.
_ZH_TH_DICT: Dict[str, str] = {
    # --- indices ---
    "上证指数": "ดัชนีเซี่ยงไฮ้ (SSE)",
    "深证成指": "ดัชนีเชินเจิ้น (SZSE)",
    "创业板指": "ดัชนี ChiNext",
    "创业板综": "ดัชนีรวม ChiNext",
    "科创50": "ดัชนี STAR 50",
    "沪深300": "ดัชนี CSI 300",
    "上证50": "ดัชนี SSE 50",
    "中证500": "ดัชนี CSI 500",
    "中证1000": "ดัชนี CSI 1000",
    "北证50": "ดัชนี BSE 50",
    "恒生指数": "ดัชนีฮาเซ็น",
    # --- industry sectors ---
    "集成电路制造": "การผลิตวงจรรวม (IC)",
    "半导体": "เซมิคอนดักเตอร์",
    "半导体材料": "วัสดุเซมิคอนดักเตอร์",
    "半导体设备": "อุปกรณ์เซมิคอนดักเตอร์",
    "电子元件": "ชิ้นส่วนอิเล็กทรอนิกส์",
    "消费电子": "อิเล็กทรอนิกส์เพื่อผู้บริโภค",
    "光学光电子": "ออปติกส์และโอปโตอิเล็กทรอนิกส์",
    "通信设备": "อุปกรณ์โทรคมนาคม",
    "通信服务": "บริการโทรคมนาคม",
    "计算机设备": "อุปกรณ์คอมพิวเตอร์",
    "软件开发": "พัฒนาซอฟต์แวร์",
    "互联网服务": "บริการอินเทอร์เน็ต",
    "游戏": "เกม",
    "银行": "ธนาคาร",
    "证券": "หลักทรัพย์",
    "保险": "ประกันภัย",
    "多元金融": "การเงินหลายรูปแบบ",
    "房地产": "อสังหาริมทรัพย์",
    "房地产开发": "พัฒนาอสังหาริมทรัพย์",
    "汽车": "ยานยนต์",
    "汽车整车": "ผู้ผลิตรถยนต์",
    "汽车零部件": "ชิ้นส่วนยานยนต์",
    "汽车服务": "บริการยานยนต์",
    "电池": "แบตเตอรี่",
    "光伏设备": "อุปกรณ์โซลาร์เซลล์",
    "风电设备": "อุปกรณ์พลังงานลม",
    "电源设备": "อุปกรณ์พลังงานไฟฟ้า",
    "医疗器械": "เครื่องมือแพทย์",
    "医疗服务": "บริการทางการแพทย์",
    "化学制药": "เภสัชเคมี",
    "生物制品": "ผลิตภัณฑ์ชีวภาพ",
    "中药": "ยาจีนแผนโบราณ",
    "白酒": "สุราจีนกลั่น",
    "食品加工": "แปรรูปอาหาร",
    "饮料": "เครื่องดื่ม",
    "休闲食品": "อาหารว่าง",
    "煤炭": "ถ่านหิน",
    "石油": "ปิโตรเลียม",
    "钢铁": "เหล็ก",
    "有色金属": "โลหะอุตสาหกรรม",
    "贵金属": "โลหะมีค่า",
    "工业金属": "โลหะอุตสาหกรรม",
    "能源金属": "โลหะพลังงาน",
    "小金属": "โลหะชนิดเล็ก",
    "铜": "ทองแดง",
    "铝": "อะลูมิเนียม",
    "钼": "โมลิบดินัม",
    "黄金": "ทองคำ",
    "化工": "เคมีภัณฑ์",
    "化学原料": "วัตถุดิบเคมี",
    "化学制品": "ผลิตภัณฑ์เคมี",
    "化肥": "ปุ๋ย",
    "橡胶助剂": "สารเคมีช่วยยาง",
    "橡胶制品": "ผลิตภัณฑ์ยาง",
    "塑料": "พลาสติก",
    "纺织": "สิ่งทอ",
    "服装": "เครื่องแต่งกาย",
    "珠宝": "เครื่องประดับ",
    "造纸": "กระดาษ",
    "包装": "บรรจุภัณฑ์",
    "玻璃": "กระจก",
    "水泥": "ปูนซีเมนต์",
    "装修装饰": "ตกแต่งภายใน",
    "工程建设": "ก่อสร้างวิศวกรรม",
    "机械设备": "เครื่องจักรกล",
    "工程机械": "เครื่องจักรกลก่อสร้าง",
    "船舶": "ต่อเรือ",
    "航空机场": "การบินและท่าอากาศยาน",
    "港口": "ท่าเรือ",
    "航运": "เดินเรือ",
    "铁路": "รถไฟ",
    "电力": "พลังงานไฟฟ้า",
    "燃气": "ก๊าซธรรมชาติ",
    "水务": "ประปา",
    "种植业": "เกษตรกรรมปลูกพืช",
    "养殖业": "ปศุสัลการ",
    "旅游": "ท่องเที่ยว",
    "酒店": "โรงแรม",
    "餐饮": "ภัตตาคาร",
    "零售": "ค้าปลีก",
    "百货": "ห้างสรรพสินค้า",
    "商业地产": "อสังหาริมทรัพย์เพื่อค้า",
    "教育": "การศึกษา",
    "文化传媒": "วัฒนธรรมและสื่อ",
    "通信": "โทรคมนาคม",
    "物流": "โลจิสติกส์",
    "快递": "ขนส่งด่วน",
    "公用事业": "สาธารณูปโภค",
    "其他数字媒体": "สื่อดิจิทัลอื่น ๆ",
    "影视动漫制作": "การผลิตภาพยนตร์และอนิเมะ",
    "影视院线": "โรงภาพยนตร์",
    "文字媒体": "สื่อสิ่งพิมพ์",
    "电视广播Ⅲ": "โทรทัศน์และวิทยุ III",
    "厨房小家电": "เครื่องใช้ไฟฟ้าขนาดเล็กในครัวเรือน",
    "白色家电": "เครื่องใช้ไฟฟ้าในบ้าน",
    "黑色家电": "เครื่องใช้ไฟฟ้า entertainment",
    # --- concepts / themes ---
    "反转股": "หุ้นพลิกฟื้นตัว",
    "昨日首板": "หุ้นขึ้นเพดานแรกเมื่อวาน",
    "光刻胶": "โฟโตเรซิสต์",
    "光刻机": "เครื่องลิโธกราฟี",
    "第四代半导体": "เซมิคอนดักเตอร์รุ่นที่ 4",
    "短剧互动游戏": "เกมซีรีส์สั้นโต้ตอบ",
    "AI视频": "วิดีโอ AI",
    "AI语料": "คลังข้อมูล AI",
    "人工智能": "ปัญญาประดิษฐ์ (AI)",
    "机器人": "หุ่นยนต์",
    "人形机器人": "หุ่นยนต์รูปคน",
    "盲盒经济": "เศรษฐกิจกล่องสุ่ม",
    "华为概念": "กลุ่ม Huawei",
    "新能源汽车": "ยานยนต์พลังงานใหม่",
    "锂电池": "แบตเตอรี่ลิเธียม",
    "芯片": "ชิป",
    "5G": "5G",
    "军工": "กลาโหม",
    "创新药": "ยานวัตกรรม",
    "卫星导航": "นำทางด้วยดาวเทียม",
    "算力": "พลังการประมวลผล",
    "数据中心": "ศูนย์ข้อมูล",
    "云计算": "คลาวด์",
    "元宇宙": "เมตาเวิร์ส",
    "碳中和": "คาร์บอนเป็นกลาง",
}

# zh -> English, used when the report language is en so data tables stay readable.
_ZH_EN_DICT: Dict[str, str] = {
    "上证指数": "Shanghai Composite (SSE)",
    "深证成指": "Shenzhen Component (SZSE)",
    "创业板指": "ChiNext Index",
    "创业板综": "ChiNext Composite",
    "科创50": "STAR 50",
    "沪深300": "CSI 300",
    "上证50": "SSE 50",
    "中证500": "CSI 500",
    "中证1000": "CSI 1000",
    "北证50": "BSE 50",
    "恒生指数": "Hang Seng Index",
    "集成电路制造": "IC Manufacturing",
    "半导体": "Semiconductors",
    "半导体材料": "Semiconductor Materials",
    "半导体设备": "Semiconductor Equipment",
    "电子元件": "Electronic Components",
    "消费电子": "Consumer Electronics",
    "光学光电子": "Optics & Optoelectronics",
    "通信设备": "Telecom Equipment",
    "通信服务": "Telecom Services",
    "计算机设备": "Computer Hardware",
    "软件开发": "Software Development",
    "互联网服务": "Internet Services",
    "游戏": "Gaming",
    "银行": "Banks",
    "证券": "Securities",
    "保险": "Insurance",
    "多元金融": "Diversified Financials",
    "房地产": "Real Estate",
    "房地产开发": "Property Development",
    "汽车": "Automobiles",
    "汽车整车": "Automakers",
    "汽车零部件": "Auto Parts",
    "汽车服务": "Auto Services",
    "电池": "Batteries",
    "光伏设备": "Solar Equipment",
    "风电设备": "Wind Power Equipment",
    "电源设备": "Power Equipment",
    "医疗器械": "Medical Devices",
    "医疗服务": "Medical Services",
    "化学制药": "Chemical Pharma",
    "生物制品": "Biological Products",
    "中药": "Traditional Chinese Medicine",
    "白酒": "Chinese Liquor",
    "食品加工": "Food Processing",
    "饮料": "Beverages",
    "休闲食品": "Snack Foods",
    "煤炭": "Coal",
    "石油": "Petroleum",
    "钢铁": "Steel",
    "有色金属": "Non-ferrous Metals",
    "贵金属": "Precious Metals",
    "工业金属": "Industrial Metals",
    "能源金属": "Energy Metals",
    "小金属": "Minor Metals",
    "铜": "Copper",
    "铝": "Aluminum",
    "钼": "Molybdenum",
    "黄金": "Gold",
    "化工": "Chemicals",
    "化学原料": "Chemical Raw Materials",
    "化学制品": "Chemical Products",
    "化肥": "Fertilizers",
    "橡胶助剂": "Rubber Additives",
    "橡胶制品": "Rubber Products",
    "塑料": "Plastics",
    "纺织": "Textiles",
    "服装": "Apparel",
    "珠宝": "Jewelry",
    "造纸": "Paper",
    "包装": "Packaging",
    "玻璃": "Glass",
    "水泥": "Cement",
    "装修装饰": "Interior Decoration",
    "工程建设": "Engineering & Construction",
    "机械设备": "Machinery",
    "工程机械": "Construction Machinery",
    "船舶": "Shipbuilding",
    "航空机场": "Airlines & Airports",
    "港口": "Ports",
    "航运": "Shipping",
    "铁路": "Railways",
    "电力": "Power",
    "燃气": "Natural Gas",
    "水务": "Water Utilities",
    "种植业": "Crop Farming",
    "养殖业": "Animal Farming",
    "旅游": "Tourism",
    "酒店": "Hotels",
    "餐饮": "Restaurants",
    "零售": "Retail",
    "百货": "Department Stores",
    "商业地产": "Commercial Real Estate",
    "教育": "Education",
    "文化传媒": "Culture & Media",
    "通信": "Telecom",
    "物流": "Logistics",
    "快递": "Express Delivery",
    "公用事业": "Utilities",
    "其他数字媒体": "Other Digital Media",
    "影视动漫制作": "Film & Animation Production",
    "影视院线": "Cinema Chains",
    "文字媒体": "Print Media",
    "电视广播Ⅲ": "TV & Broadcasting III",
    "厨房小家电": "Kitchen Appliances",
    "白色家电": "Home Appliances",
    "黑色家电": "Consumer AV Electronics",
    "反转股": "Reversal Stocks",
    "昨日首板": "Yesterday's First Limit-up",
    "光刻胶": "Photoresist",
    "光刻机": "Lithography Machines",
    "第四代半导体": "4th-gen Semiconductors",
    "短剧互动游戏": "Interactive Short Dramas",
    "AI视频": "AI Video",
    "AI语料": "AI Training Data",
    "人工智能": "Artificial Intelligence (AI)",
    "机器人": "Robotics",
    "人形机器人": "Humanoid Robots",
    "盲盒经济": "Blind-box Economy",
    "华为概念": "Huawei Concept",
    "新能源汽车": "NEV",
    "锂电池": "Lithium Batteries",
    "芯片": "Chips",
    "军工": "Defense",
    "创新药": "Innovative Drugs",
    "卫星导航": "Satellite Navigation",
    "算力": "Computing Power",
    "数据中心": "Data Centers",
    "云计算": "Cloud Computing",
    "元宇宙": "Metaverse",
    "碳中和": "Carbon Neutrality",
}

_DICTS = {"th": _ZH_TH_DICT, "en": _ZH_EN_DICT}


def _load_cache() -> Dict[str, Dict[str, str]]:
    try:
        with open(_CACHE_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return {lang: dict(payload) for lang, payload in data.items() if isinstance(payload, dict)}
    except (OSError, ValueError):
        pass
    return {}


def _save_cache(cache: Dict[str, Dict[str, str]]) -> None:
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_CACHE_FILE, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False, indent=1)
    except OSError as exc:
        logger.warning("[zh-name-translation] Failed to save cache: %s", exc)


def _llm_translate(names: List[str], target_language: str) -> Dict[str, str]:
    """Batch-translate unknown Chinese names via the configured LLM channel.

    Uses the plain OpenAI-compatible env contract (LLM_OPENAI_*), which the
    xKiro channel sets up, so no heavy LLM client machinery is needed here.
    """
    api_key = os.getenv("LLM_OPENAI_API_KEY", "").strip()
    base_url = os.getenv("LLM_OPENAI_BASE_URL", "").strip()
    model = os.getenv("LITELLM_MODEL", "").strip()
    # LITELLM_MODEL carries a LiteLLM provider prefix (e.g. "openai/cohere/command-a");
    # the OpenAI-compatible endpoint itself expects the bare model id.
    if model.startswith("openai/"):
        model = model[len("openai/"):]
    if not (api_key and base_url and model):
        logger.warning("[zh-name-translation] LLM channel not configured; keeping original names")
        return {}

    prompt = (
        "Translate each Chinese stock-market sector/concept/index name into "
        f"{'Thai' if target_language == 'th' else 'English'}. "
        "Return ONLY a JSON object mapping each original name to its translation. "
        "Keep financial terminology natural and concise.\n\n"
        + "\n".join(f"- {name}" for name in names)
    )
    payload = {
        "model": model,
        "max_tokens": 3000,
        "temperature": 0.0,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        import httpx

        response = httpx.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=90,
        )
        response.raise_for_status()
        body = response.json()
        content = (body.get("choices") or [{}])[0].get("message", {}).get("content", "")
        if isinstance(content, list):
            content = "".join(
                block.get("text", "") for block in content if isinstance(block, dict)
            )
        if not content:
            return {}
        import re

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return {}
        parsed = json.loads(match.group(0))
        if not isinstance(parsed, dict):
            return {}
        return {str(k).strip(): str(v).strip() for k, v in parsed.items() if str(v).strip()}
    except Exception as exc:  # fail-open: keep original names
        logger.warning("[zh-name-translation] LLM batch translation failed: %s", exc)
        return {}


def translate_market_names(names: Iterable[str], target_language: str = "th") -> Dict[str, str]:
    """Return zh->target translations for the given names (dict first, LLM fallback).

    Non-Chinese names pass through untouched; failures keep original names so
    callers can apply results with ``translations.get(name, name)`` safely.
    """
    target_language = "th" if str(target_language).lower().startswith("th") else (
        "en" if str(target_language).lower().startswith("en") else "th"
    )
    original_names: List[str] = []
    seen = set()
    for name in names:
        text = str(name or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        original_names.append(text)

    static_dict = _DICTS.get(target_language, _ZH_TH_DICT)
    translations: Dict[str, str] = {}
    unknown: List[str] = []
    for name in original_names:
        mapped = static_dict.get(name)
        if mapped:
            translations[name] = mapped
        elif _HAS_CJK.search(name):
            unknown.append(name)

    if not unknown:
        return translations

    cache = _load_cache()
    lang_cache = cache.setdefault(target_language, {})
    still_unknown: List[str] = []
    for name in unknown:
        cached = lang_cache.get(name)
        if cached:
            translations[name] = cached
        else:
            still_unknown.append(name)

    if still_unknown:
        logger.info(
            "[zh-name-translation] LLM fallback for %d name(s) -> %s",
            len(still_unknown),
            target_language,
        )
        fresh = _llm_translate(still_unknown[:_LLM_BATCH_LIMIT], target_language)
        for name in still_unknown:
            translated = fresh.get(name)
            if translated:
                translations[name] = translated
                lang_cache[name] = translated
        _save_cache(cache)

    return translations