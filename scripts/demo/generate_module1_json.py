#!/usr/bin/env python3
"""
Synthetic Module 1 output generator — for testing and demos without Module 1.

Module 1 (scanner/device file parsing) is not part of this repository. This
script produces JSON in the shape Module 2 consumes (see
src/module_2_reasoning/filter.py), filled with plausible, scenario-driven
measurements. All patients and values are fictional.

Usage:
    uv run python scripts/demo/generate_module1_json.py [--scenario NAME] [--seed N] ...
    uv run python scripts/demo/generate_module1_json.py --list

Output (default): data/json_exports/{timestamp}_{patient_code}.json
which scripts/module2/run_pipeline.py picks up automatically as the latest export.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUT_DIR = _PROJECT_ROOT / "data" / "json_exports"

GENDERS = {"male": "Чоловік", "female": "Жінка"}
ACTIVITY_LEVELS = ("elite", "recreational", "low")


# ---------------------------------------------------------------------------
# Test catalog
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Param:
    id: str
    name_uk: str
    unit: str | None
    norm: tuple[float, float] | None
    bilateral: bool = False
    asym_max: float | None = None  # max acceptable L/R asymmetry, %
    decimals: int = 0


@dataclass(frozen=True)
class TestDef:
    key: str
    label: str
    table_title: str
    params: tuple[Param, ...]


TESTS: dict[str, TestDef] = {
    t.key: t
    for t in (
        TestDef(
            "cervical_goniometry",
            "Cervical Goniometry",
            "Амплітуда рухів шийного відділу",
            (
                Param("neck_flex", "Згинання шиї", "°", (45, 65)),
                Param("neck_ext", "Розгинання шиї", "°", (55, 75)),
                Param("neck_latflex", "Бічний нахил шиї", "°", (40, 50), True, 15),
                Param("neck_rot", "Ротація шиї", "°", (70, 90), True, 10),
            ),
        ),
        TestDef(
            "leg_goniometry",
            "Leg Goniometry",
            "Амплітуда рухів нижніх кінцівок",
            (
                Param("hip_flex", "Згинання стегна", "°", (110, 130), True, 10),
                Param("hip_ir", "Внутрішня ротація стегна", "°", (30, 45), True, 15),
                Param("hip_er", "Зовнішня ротація стегна", "°", (40, 60), True, 15),
                Param("knee_flex", "Згинання коліна", "°", (130, 150), True, 10),
                Param("ankle_df", "Тильне згинання гомілковостопного суглоба", "°", (15, 25), True, 15),
            ),
        ),
        TestDef(
            "leg_dynamometry",
            "Leg Dynamometry",
            "Ізометрична сила м'язів нижніх кінцівок",
            (
                Param("quad_str", "Сила розгиначів коліна", "Н", (400, 700), True, 10),
                Param("ham_str", "Сила згиначів коліна", "Н", (250, 450), True, 10),
                Param("hip_abd_str", "Сила відвідних м'язів стегна", "Н", (200, 350), True, 10),
                Param("hip_add_str", "Сила привідних м'язів стегна", "Н", (200, 350), True, 10),
                Param("hq_ratio", "Співвідношення H/Q", None, (0.55, 0.8), decimals=2),
            ),
        ),
        TestDef(
            "arm_goniometry",
            "Arm Goniometry",
            "Амплітуда рухів плечового суглоба",
            (
                Param("sh_flex", "Згинання плеча", "°", (160, 180), True, 10),
                Param("sh_abd", "Відведення плеча", "°", (160, 180), True, 10),
                Param("sh_ir", "Внутрішня ротація плеча", "°", (60, 80), True, 15),
                Param("sh_er", "Зовнішня ротація плеча", "°", (80, 100), True, 15),
            ),
        ),
        TestDef(
            "arm_dynamometry",
            "Arm Dynamometry",
            "Ізометрична сила м'язів верхніх кінцівок",
            (
                Param("sh_ir_str", "Сила внутрішніх ротаторів плеча", "Н", (120, 220), True, 10),
                Param("sh_er_str", "Сила зовнішніх ротаторів плеча", "Н", (100, 180), True, 10),
                Param("grip", "Сила хвату", "кг", (35, 55), True, 10, 1),
                Param("er_ir_ratio", "Співвідношення ER/IR", None, (0.66, 0.9), decimals=2),
            ),
        ),
        TestDef(
            "shoulder_test",
            "Shoulder Test (Y/T/I)",
            "Тест Y/T/I — пікова сила",
            (
                Param("ytI_y", "Позиція Y", "Н", (60, 110), True, 12),
                Param("ytI_t", "Позиція T", "Н", (70, 120), True, 12),
                Param("ytI_i", "Позиція I", "Н", (80, 130), True, 12),
            ),
        ),
        TestDef(
            "mccall_hamstrings",
            "McCall Hamstrings",
            "Тест МакКола — сила задньої поверхні стегна",
            (
                Param("mccall_90", "Сила при 90° згинання", "Н", (250, 400), True, 10),
                Param("mccall_30", "Сила при 30° згинання", "Н", (220, 360), True, 10),
            ),
        ),
        TestDef(
            "counter_movement_jump",
            "Counter Movement Jump",
            "Стрибок з контррухом",
            (
                Param("cmj_height", "Висота стрибка", "см", (30, 45), decimals=1),
                Param("cmj_power", "Пікова потужність", "Вт/кг", (45, 60), decimals=1),
                Param("cmj_landing", "Пікова сила приземлення", "Н", (1200, 2000), True, 10),
            ),
        ),
        TestDef(
            "single_leg_balance",
            "Single Leg Balance",
            "Баланс на одній нозі (30 с)",
            (
                Param("sway_area", "Площа коливань ЦТ", "мм²", (0, 350), True, 20),
                Param("sway_vel", "Швидкість коливань ЦТ", "мм/с", (0, 25), True, 20, 1),
            ),
        ),
        TestDef(
            "baropodometry",
            "Static Baropodometry",
            "Статична баропедометрія",
            (
                Param("load", "Розподіл навантаження", "%", (45, 55), True, 10, 1),
                Param("forefoot", "Навантаження на передній відділ стопи", "%", (35, 45), decimals=1),
                Param("rearfoot", "Навантаження на задній відділ стопи", "%", (55, 65), decimals=1),
                Param("arch_index", "Індекс склепіння стопи", None, (0.21, 0.26), True, 15, 2),
            ),
        ),
    )
}

# Text-only tests: Module 2 keeps only the interpretation when there is no norm data.
TEXT_TESTS = {
    "postural": "Postural",
    "spine3d": "Spine 3D",
    "dental": "Dental",
}

TEXT_NORMAL = {
    "postural": (
        "Постава без виражених відхилень. Положення голови, плечового поясу та таза "
        "симетричне, фізіологічні вигини хребта збережені.",
        "Підтримувальні вправи для м'язів кору, контроль постави протягом дня.",
    ),
    "spine3d": (
        "Фізіологічні вигини хребта в межах норми. Бічних викривлень та ротації "
        "хребців не виявлено.",
        None,
    ),
    "dental": (
        "Оклюзія без особливостей. Ознак дисфункції скронево-нижньощелепного суглоба "
        "не виявлено.",
        None,
    ),
}


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------
# `deficits`: param id -> multiplier applied to an in-norm value, per side.
#   "left"/"right" for bilateral params, "value" for single-value params.
#   <1 lowers the value (weakness, limited ROM); >1 raises it (e.g. more sway).
# `texts`: overrides for text-only tests — (interpretation, recommendations).


@dataclass(frozen=True)
class Scenario:
    description: str
    tests: tuple[str, ...]
    deficits: dict[str, dict[str, float]]
    texts: dict[str, tuple[str, str | None]]
    defaults: dict[str, object]


SCENARIOS: dict[str, Scenario] = {
    "acl_left": Scenario(
        description="6 months after left ACL reconstruction: quad weakness, reduced knee flexion, "
        "poor single-leg control and load shifted to the right leg.",
        tests=(
            "leg_goniometry", "leg_dynamometry", "mccall_hamstrings", "counter_movement_jump",
            "single_leg_balance", "baropodometry", "postural",
        ),
        deficits={
            "quad_str": {"left": 0.72},
            "ham_str": {"left": 0.85},
            "hq_ratio": {"value": 1.25},
            "knee_flex": {"left": 0.88},
            "ankle_df": {"left": 0.8},
            "mccall_90": {"left": 0.82},
            "cmj_height": {"value": 0.8},
            "cmj_landing": {"left": 0.8},
            "sway_area": {"left": 1.9},
            "sway_vel": {"left": 1.7},
            "load": {"left": 0.88, "right": 1.1},
        },
        texts={
            "postural": (
                "Перенесення ваги тіла на праву нижню кінцівку. Легка зовнішня ротація лівої "
                "стопи, зниження тонусу лівого чотириголового м'яза стегна.",
                "Відновлення симетричного навантаження, зміцнення чотириголового м'яза лівого стегна.",
            ),
        },
        defaults={"age": 24, "gender": "male", "activity_level": "recreational"},
    ),
    "shoulder_right": Scenario(
        description="Right shoulder impingement in an overhead athlete: rotator cuff weakness, "
        "limited internal rotation (GIRD), scapular dyskinesis and forward head posture.",
        tests=(
            "arm_goniometry", "arm_dynamometry", "shoulder_test", "cervical_goniometry", "postural",
            "spine3d",
        ),
        deficits={
            "sh_ir": {"right": 0.7},
            "sh_er": {"right": 1.08},
            "sh_flex": {"right": 0.93},
            "sh_er_str": {"right": 0.7},
            "sh_ir_str": {"right": 0.9},
            "er_ir_ratio": {"value": 0.85},
            "ytI_y": {"right": 0.68},
            "ytI_t": {"right": 0.78},
            "neck_rot": {"left": 0.88},
        },
        texts={
            "postural": (
                "Протракція плечового поясу, більш виражена справа. Праве плече опущене на 1,5 см. "
                "Крилоподібне відстовбурчення правої лопатки. Антепозиція голови.",
                "Корекція положення лопатки, зміцнення нижньої частини трапецієподібного м'яза "
                "та переднього зубчастого м'яза, розтягнення малого грудного м'яза.",
            ),
            "spine3d": (
                "Посилення грудного кіфозу (52°). Згладжений шийний лордоз.",
                None,
            ),
        },
        defaults={"age": 29, "gender": "female", "activity_level": "elite"},
    ),
    "low_back_posture": Scenario(
        description="Low-activity office worker with chronic low back pain: anterior pelvic tilt, "
        "tight hip flexors and hamstrings, weak glutes, mild scoliosis and flat feet.",
        tests=(
            "leg_goniometry", "leg_dynamometry", "mccall_hamstrings", "baropodometry", "postural",
            "spine3d", "dental",
        ),
        deficits={
            "hip_flex": {"left": 0.85, "right": 0.87},
            "hip_ir": {"left": 0.78, "right": 0.8},
            "hip_abd_str": {"left": 0.75, "right": 0.82},
            "mccall_90": {"left": 0.85, "right": 0.88},
            "mccall_30": {"left": 0.8, "right": 0.84},
            "forefoot": {"value": 1.2},
            "rearfoot": {"value": 0.88},
            "arch_index": {"left": 1.25, "right": 1.3},
        },
        texts={
            "postural": (
                "Передній нахил таза, посилений поперековий лордоз. Ліве плече вище правого на 1 см. "
                "Плоско-вальгусна установка обох стоп.",
                "Зміцнення сідничних м'язів та глибоких м'язів кору, розтягнення згиначів стегна.",
            ),
            "spine3d": (
                "Сколіотична постава: S-подібне бічне викривлення, грудний відділ 8° вправо, "
                "поперековий 6° вліво. Посилений поперековий лордоз (58°).",
                None,
            ),
            "dental": (
                "Порушення оклюзії II класу. Девіація нижньої щелепи вліво при відкриванні рота.",
                "Консультація стоматолога-ортодонта.",
            ),
        },
        defaults={"age": 41, "gender": "male", "activity_level": "low"},
    ),
    "healthy": Scenario(
        description="Baseline athlete with all measurements within norms — useful as a control.",
        tests=(
            "cervical_goniometry", "leg_goniometry", "leg_dynamometry", "arm_goniometry",
            "arm_dynamometry", "counter_movement_jump", "single_leg_balance", "baropodometry",
            "postural",
        ),
        deficits={},
        texts={},
        defaults={"age": 22, "gender": "female", "activity_level": "elite"},
    ),
    "random": Scenario(
        description="Random selection of tests and random deficits (use --seed for reproducibility).",
        tests=(),
        deficits={},
        texts={},
        defaults={},
    ),
}

DEMO_NAMES = {
    "male": ["Коваленко Андрій", "Шевчук Максим", "Бондар Олег", "Ткаченко Дмитро"],
    "female": ["Мельник Олена", "Кравченко Ірина", "Савчук Марія", "Литвин Анна"],
}


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def _in_norm(norm: tuple[float, float], rng: random.Random) -> float:
    lo, hi = norm
    span = hi - lo
    return rng.uniform(lo + 0.25 * span, hi - 0.15 * span)


def _round(x: float, decimals: int) -> float | int:
    return round(x, decimals) if decimals else int(round(x))


def _make_row(p: Param, deficit: dict[str, float], rng: random.Random) -> dict:
    row: dict = {"parameter": p.name_uk, "unit": p.unit}
    if p.bilateral:
        base = _in_norm(p.norm, rng)
        left = base * rng.uniform(0.97, 1.03) * deficit.get("left", 1.0)
        right = base * rng.uniform(0.97, 1.03) * deficit.get("right", 1.0)
        left, right = _round(left, p.decimals), _round(right, p.decimals)
        row["left"], row["right"] = left, right
        if p.asym_max is not None:
            hi = max(abs(left), abs(right))
            row["asymmetry_percent"] = round(abs(left - right) / hi * 100, 1) if hi else 0.0
            row["asymmetry_norm_max"] = p.asym_max
    else:
        row["value"] = _round(_in_norm(p.norm, rng) * deficit.get("value", 1.0), p.decimals)
    row["norm"] = list(p.norm) if p.norm else None
    return row


def _random_scenario(rng: random.Random) -> Scenario:
    tests = rng.sample(sorted(TESTS), k=rng.randint(4, 7)) + ["postural"]
    deficits: dict[str, dict[str, float]] = {}
    for key in tests:
        if key not in TESTS:
            continue
        for p in rng.sample(TESTS[key].params, k=rng.randint(1, 2)):
            factor = rng.uniform(0.55, 0.78)
            if p.bilateral:
                deficits[p.id] = {rng.choice(("left", "right")): factor}
            else:
                deficits[p.id] = {"value": factor}
    return Scenario("random", tuple(tests), deficits, {}, {})


def build_patient(
    scenario_name: str,
    rng: random.Random,
    age: int | None,
    gender: str | None,
    activity_level: str | None,
    name: str | None,
    patient_code: str | None,
) -> dict:
    scenario = SCENARIOS[scenario_name]
    if scenario_name == "random":
        scenario = _random_scenario(rng)

    gender = gender or scenario.defaults.get("gender") or rng.choice(list(GENDERS))
    patient_info = {
        "name": name or rng.choice(DEMO_NAMES[gender]),
        "patient_code": patient_code or f"DEMO{rng.randint(1000, 9999)}",
        "age": age or scenario.defaults.get("age") or rng.randint(18, 55),
        "gender": GENDERS[gender],
        "activity_level": activity_level
        or scenario.defaults.get("activity_level")
        or rng.choice(ACTIVITY_LEVELS),
    }

    test_results = []
    for key in scenario.tests:
        if key in TEXT_TESTS:
            interpretation, recommendations = scenario.texts.get(key, TEXT_NORMAL[key])
            test_results.append(
                {
                    "test_name": TEXT_TESTS[key],
                    "test_type": key,
                    "interpretation": interpretation,
                    "recommendations": recommendations,
                    "results": {"tables": []},
                }
            )
            continue
        test = TESTS[key]
        rows = [_make_row(p, scenario.deficits.get(p.id, {}), rng) for p in test.params]
        test_results.append(
            {
                "test_name": test.label,
                "test_type": key,
                "interpretation": None,
                "recommendations": None,
                "results": {"tables": [{"title": test.table_title, "rows": rows}]},
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "synthetic": True,
        "scenario": scenario_name,
        "patient_info": patient_info,
        "test_results": test_results,
    }


def _count_out_of_norm(data: dict) -> int:
    n = 0
    for tr in data["test_results"]:
        for table in tr["results"]["tables"]:
            for row in table["rows"]:
                lo, hi = row["norm"]
                vals = [row[k] for k in ("value", "left", "right") if k in row]
                asym = row.get("asymmetry_percent", 0) > (row.get("asymmetry_norm_max") or 1e9)
                n += any(v < lo or v > hi for v in vals) or asym
    return n


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic Module 1 JSON exports.")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="acl_left")
    parser.add_argument("--list", action="store_true", help="List scenarios and exit.")
    parser.add_argument("--count", type=int, default=1, help="Number of patients to generate.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible output.")
    parser.add_argument("--age", type=int)
    parser.add_argument("--gender", choices=sorted(GENDERS))
    parser.add_argument("--activity-level", choices=ACTIVITY_LEVELS)
    parser.add_argument("--name", help="Patient display name (fictional).")
    parser.add_argument("--code", help="Patient code.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    if args.list:
        for name, sc in SCENARIOS.items():
            print(f"{name:18} {sc.description}")
        return

    rng = random.Random(args.seed)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for i in range(args.count):
        data = build_patient(
            args.scenario, rng, args.age, args.gender, args.activity_level, args.name, args.code
        )
        code = data["patient_info"]["patient_code"]
        suffix = f"_{i + 1}" if args.count > 1 else ""
        out_path = args.out_dir / f"{stamp}_{code}{suffix}.json"
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            f"Wrote {out_path.relative_to(_PROJECT_ROOT) if out_path.is_relative_to(_PROJECT_ROOT) else out_path}"
            f"  [{args.scenario}] {len(data['test_results'])} tests, "
            f"{_count_out_of_norm(data)} out-of-norm rows"
        )


if __name__ == "__main__":
    main()
