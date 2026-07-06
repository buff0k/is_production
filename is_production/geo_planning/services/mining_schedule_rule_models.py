# apps/is_production/is_production/geo_planning/services/mining_schedule_rule_models.py

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


DayKey = Literal["weekday", "saturday", "sunday"]
CapacityUnit = Literal["bcm_per_hour", "tonnes_per_hour"]
BlockOrder = Literal["selected_order", "cut_order", "spatial_order", "material_first"]


class DayRule(BaseModel):
    shifts: float = Field(default=0, ge=0)
    production_hours: float = Field(default=0, ge=0)
    working: bool = False


class FleetRule(BaseModel):
    equipment_type: str = Field(default="excavator")
    count: float = Field(default=0, ge=0)
    capacity_per_hour: float = Field(default=0, ge=0)
    unit: CapacityUnit = "bcm_per_hour"

    @field_validator("equipment_type")
    @classmethod
    def clean_equipment_type(cls, value: str) -> str:
        return (value or "").strip().lower().replace(" ", "_")


class SequenceRule(BaseModel):
    block_order: BlockOrder = "selected_order"
    material_order: list[str] = Field(default_factory=list)
    allow_partial_blocks: bool = True


class ConstraintRule(BaseModel):
    max_active_blocks_per_period: Optional[int] = None
    minimum_task_quantity: float = Field(default=0, ge=0)


class ScheduleRules(BaseModel):
    calendar: dict[DayKey, DayRule]
    fleet: list[FleetRule] = Field(default_factory=list)
    availability_percent: float = Field(default=100, ge=0, le=100)
    utilisation_percent: float = Field(default=100, ge=0, le=100)
    sequence: SequenceRule = Field(default_factory=SequenceRule)
    constraints: ConstraintRule = Field(default_factory=ConstraintRule)

    @field_validator("fleet")
    @classmethod
    def validate_fleet(cls, value: list[FleetRule]) -> list[FleetRule]:
        if not value:
            raise ValueError(
                "At least one fleet rule is required, for example: Use 3 excavators at 450 bcm per hour."
            )
        return value