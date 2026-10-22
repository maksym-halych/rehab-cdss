import random
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from ..dependencies import get_current_user
from ..services.synthetic_module1 import SCENARIOS, build_patient

router = APIRouter(dependencies=[Depends(get_current_user)])

Scenario = Enum("Scenario", {name: name for name in SCENARIOS}, type=str)


@router.get("/demo/module1-json")
async def synthetic_module1_json(
    scenario: Scenario = Query(default="random"),
    seed: Optional[int] = Query(default=None),
) -> JSONResponse:
    """A synthetic Module 1 export for JSON mode (POST /jobs/from-json).

    All patients and values are fictional. The same seed gives the same values.
    """
    data = build_patient(scenario.value, random.Random(seed), None, None, None, None, None)
    file_name = f"synthetic_{scenario.value}_{data['patient_info']['patient_code']}.json"
    return JSONResponse(
        data, headers={"Content-Disposition": f'attachment; filename="{file_name}"'}
    )
