from enum import Enum

from pydantic import BaseModel, field_validator as validator
from typing import Optional, List, Callable, Union, Any, Literal


# TODO: REFINE TYPES


class Genders(str, Enum):
    MALE = "male"
    FEMALE = "female"
    GOD = "god"
    GODDESS = "goddess"


# may end up removing these
class Tones(str, Enum):
    FORMAL = "formal"
    CASUAL = "casual"
    AGGRESSIVE = "aggressive"
    FUNNY = "funny"


class Emotions(BaseModel):
    emotional_responsiveness: float  # Scale 0-1 (reactive vs. calm)
    empathy_level: float  # Scale 0-1 (low empathy vs. high empathy)

    trigger_words: List[str] = (
        []
    )  # Words that will trigger aggressive responses from the model

    @validator("trigger_words", mode="before")
    def validate_single_word(cls, word):
        if " " in word:
            raise ValueError(f"'{word}' contains spaces and is not a single word.")
        return word


Responsibilities = Callable[[], Union[str, None, Any]]


# Here Pilot is the leader in the agent to agent relationship and crew members look to the pilot for approval on tasks/actions
Roles = Literal["pilot", "crew"]


# A class to go deeper into the "mind" of the model and adjust specific things that aren't included in its instructions
class Tendencies(BaseModel):
    emotions: Emotions

    # Communication styles
    tone: Optional[Tones] = Tones.CASUAL
    passiveness: float  # Scale 0-1 (not passive to extremely passive) Determines the amount of resistance an agent will give to a suggestion from another agent

    # Behavioral Traits
    risk_tolerance: float  # Scale 0-1 (risk-averse vs. risk-taking)
    patience_level: float  # Scale 0-1 (impatient vs. patient)
    decision_making: str  # "impulsive", "deliberate", "balanced", etc.

    # Values and Motivations
    core_values: List[str]
    goals: List[str]
    fears: List[str]

    # extra things one may want to add to the model
    custom_traits: Optional[dict] = None
