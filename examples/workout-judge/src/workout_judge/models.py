from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Severity(str, Enum):
    positive = "positive"
    minor_issue = "minor_issue"
    major_issue = "major_issue"


class ExerciseObservation(BaseModel):
    timestamp_range: str = Field(description="e.g. '0:15-0:22'")
    body_part: str = Field(description="e.g. 'lower back', 'knees'")
    observation: str
    severity: Severity


class WorkoutAnalysis(BaseModel):
    exercise_name: str
    duration_analyzed: str
    athlete_level: Literal["beginner", "intermediate", "advanced"]
    technique_score: int = Field(ge=1, le=10)
    overall_assessment: str
    observations: list[ExerciseObservation]
    strengths: list[str]
    areas_for_improvement: list[str]
    key_recommendations: list[str]
