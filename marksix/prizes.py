"""Official HKJC Mark Six prize rules (獲獎資格)."""

from __future__ import annotations

# Unit bet is HK$10. Multiple/banker can use half-unit HK$5 with pro-rated prizes.
UNIT_BET_HKD = 10
HALF_UNIT_BET_HKD = 5

PRIZE_RULES = (
    {
        "tier": 1,
        "name_zh": "頭獎",
        "name_en": "1st Division",
        "main_hits": 6,
        "need_special": False,
        "fixed_prize_hkd": None,
        "note_zh": "獎金因中獎注數而異；每期頭獎獎金基金不少於港幣800萬元",
        "note_en": "Varies by winners; jackpot fund at least HK$8,000,000 each draw",
    },
    {
        "tier": 2,
        "name_zh": "二獎",
        "name_en": "2nd Division",
        "main_hits": 5,
        "need_special": True,
        "fixed_prize_hkd": None,
        "note_zh": "獎金因該期獲中二獎注數而有所不同",
        "note_en": "Varies by number of 2nd division winners",
    },
    {
        "tier": 3,
        "name_zh": "三獎",
        "name_en": "3rd Division",
        "main_hits": 5,
        "need_special": False,
        "fixed_prize_hkd": None,
        "note_zh": "獎金因該期獲中三獎注數而有所不同",
        "note_en": "Varies by number of 3rd division winners",
    },
    {
        "tier": 4,
        "name_zh": "四獎",
        "name_en": "4th Division",
        "main_hits": 4,
        "need_special": True,
        "fixed_prize_hkd": 9600,
        "note_zh": "固定獎金港幣9,600元",
        "note_en": "Fixed prize HK$9,600",
    },
    {
        "tier": 5,
        "name_zh": "五獎",
        "name_en": "5th Division",
        "main_hits": 4,
        "need_special": False,
        "fixed_prize_hkd": 640,
        "note_zh": "固定獎金港幣640元",
        "note_en": "Fixed prize HK$640",
    },
    {
        "tier": 6,
        "name_zh": "六獎",
        "name_en": "6th Division",
        "main_hits": 3,
        "need_special": True,
        "fixed_prize_hkd": 320,
        "note_zh": "固定獎金港幣320元",
        "note_en": "Fixed prize HK$320",
    },
    {
        "tier": 7,
        "name_zh": "七獎",
        "name_en": "7th Division",
        "main_hits": 3,
        "need_special": False,
        "fixed_prize_hkd": 40,
        "note_zh": "固定獎金港幣40元",
        "note_en": "Fixed prize HK$40",
    },
)

_PRIZE_BY_TIER = {rule["tier"]: rule for rule in PRIZE_RULES}


def prize_tier(main_hits: int, special_hit: bool) -> int | None:
    """Return prize division 1–7, or None if no prize."""
    if main_hits == 6:
        return 1
    if main_hits == 5 and special_hit:
        return 2
    if main_hits == 5:
        return 3
    if main_hits == 4 and special_hit:
        return 4
    if main_hits == 4:
        return 5
    if main_hits == 3 and special_hit:
        return 6
    if main_hits == 3:
        return 7
    return None


def prize_info(tier: int | None) -> dict | None:
    if tier is None:
        return None
    rule = _PRIZE_BY_TIER.get(tier)
    if rule is None:
        return None
    return {
        "tier": rule["tier"],
        "name_zh": rule["name_zh"],
        "name_en": rule["name_en"],
        "fixed_prize_hkd": rule["fixed_prize_hkd"],
        "note_zh": rule["note_zh"],
        "note_en": rule["note_en"],
    }


def public_prize_table() -> list[dict]:
    return [
        {
            "tier": rule["tier"],
            "name_zh": rule["name_zh"],
            "name_en": rule["name_en"],
            "requirement_zh": (
                f"選中{rule['main_hits']}個攪出號碼"
                + (" + 特別號碼" if rule["need_special"] else "")
            ),
            "requirement_en": (
                f"{rule['main_hits']} drawn number(s)"
                + (" + extra number" if rule["need_special"] else "")
            ),
            "fixed_prize_hkd": rule["fixed_prize_hkd"],
            "note_zh": rule["note_zh"],
            "note_en": rule["note_en"],
        }
        for rule in PRIZE_RULES
    ]
