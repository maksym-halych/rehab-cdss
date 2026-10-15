from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..dependencies import verify_api_key

router = APIRouter(dependencies=[Depends(verify_api_key)])


class TestTypeInfo(BaseModel):
    key: str
    label: str
    accepts: list[Literal["pdf", "csv"]]
    category: Literal["pdf", "csv"]
    variant_family: Optional[str] = None


class VariantChoice(BaseModel):
    label: str
    value: str


class VariantFamily(BaseModel):
    choices: list[VariantChoice]
    default: str


class ActivityLevel(BaseModel):
    value: str
    label: str


class ConfigResponse(BaseModel):
    test_types: list[TestTypeInfo]
    variant_families: dict[str, VariantFamily]
    activity_levels: list[ActivityLevel]
    gender_choices: list[str]


_TEST_TYPES = [
    TestTypeInfo(key="dental", label="Dental", accepts=["pdf"], category="pdf"),
    TestTypeInfo(key="postural", label="Postural", accepts=["pdf"], category="pdf"),
    TestTypeInfo(key="baropodometry", label="Static Baropodometry", accepts=["pdf"], category="pdf"),
    TestTypeInfo(key="dynamic_baropodometry", label="Dynamic Baropodometry", accepts=["pdf"], category="pdf"),
    TestTypeInfo(key="spine3d", label="Spine 3D", accepts=["pdf"], category="pdf"),
    TestTypeInfo(key="cervical_goniometry", label="Cervical Goniometry", accepts=["csv"], category="csv"),
    TestTypeInfo(key="leg_goniometry", label="Leg Goniometry", accepts=["csv"], category="csv"),
    TestTypeInfo(key="leg_dynamometry", label="Leg Dynamometry", accepts=["csv"], category="csv"),
    TestTypeInfo(key="arm_goniometry", label="Arm Goniometry", accepts=["csv"], category="csv"),
    TestTypeInfo(key="arm_dynamometry", label="Arm Dynamometry", accepts=["csv"], category="csv"),
    TestTypeInfo(key="single_leg_balance", label="Single Leg Balance", accepts=["csv"], category="csv"),
    TestTypeInfo(key="single_leg_landing", label="Single Leg Landing", accepts=["csv"], category="csv"),
    TestTypeInfo(key="mccall_hamstrings", label="McCall Hamstrings", accepts=["csv"], category="csv"),
    TestTypeInfo(key="shoulder_test", label="Shoulder Test (Y/T/I)", accepts=["csv"], category="csv"),
    TestTypeInfo(key="push_up", label="Push Up", accepts=["csv"], category="csv", variant_family="push_up_family"),
    TestTypeInfo(key="handstand_push_up", label="Handstand Push Up", accepts=["csv"], category="csv", variant_family="push_up_family"),
    TestTypeInfo(key="counter_movement_jump", label="Counter Movement Jump", accepts=["csv"], category="csv"),
    TestTypeInfo(key="single_leg_counter_movement_jump", label="Single Leg CMJ", accepts=["csv"], category="csv"),
    TestTypeInfo(key="drop_jump", label="Drop Jump", accepts=["csv"], category="csv"),
    TestTypeInfo(key="imtp", label="IMTP", accepts=["csv"], category="csv"),
    TestTypeInfo(key="bipodal_stance", label="Bipodal Stance", accepts=["csv"], category="csv"),
    TestTypeInfo(key="bipodal_landing", label="Bipodal Landing", accepts=["csv"], category="csv"),
    TestTypeInfo(key="skipping", label="Skipping", accepts=["csv"], category="csv"),
    TestTypeInfo(key="squats_advanced_analysis", label="Squats Advanced Analysis", accepts=["csv"], category="csv"),
]

_VARIANT_FAMILIES = {
    "push_up_family": VariantFamily(
        choices=[
            VariantChoice(label="Push Up", value="push_up"),
            VariantChoice(label="Handstand Push Up", value="handstand_push_up"),
        ],
        default="push_up",
    )
}

_ACTIVITY_LEVELS = [
    ActivityLevel(value="elite", label="Елітний спорт"),
    ActivityLevel(value="recreational", label="Рекреаційний спорт"),
    ActivityLevel(value="low", label="Низька активність"),
]

_GENDER_CHOICES = ["Чоловік", "Жінка"]


@router.get("/config/test-types", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    return ConfigResponse(
        test_types=_TEST_TYPES,
        variant_families=_VARIANT_FAMILIES,
        activity_levels=_ACTIVITY_LEVELS,
        gender_choices=_GENDER_CHOICES,
    )
