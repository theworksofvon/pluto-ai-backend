import json
import re
from typing import Any, Dict, Optional

import asyncio
from logger import logger

# Precompile regex patterns for efficiency.
JSON_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
DICT_STRUCTURE_RE = re.compile(r"\{(.*?'value'.*?'explanation'.*?)\}", re.DOTALL)
VALUE_RE = re.compile(r"[\"']value[\"']\s*:\s*([0-9.]+)")
RANGE_LOW_RE = re.compile(r"[\"']range_low[\"']\s*:\s*([0-9.]+)")
RANGE_HIGH_RE = re.compile(r"[\"']range_high[\"']\s*:\s*([0-9.]+)")
CONFIDENCE_RE = re.compile(r"[\"']confidence[\"']\s*:\s*([0-9.]+)")
EXPLANATION_RE = re.compile(r"[\"']explanation[\"']\s*:\s*[\"'](.+?)[\"']", re.DOTALL)

DEFAULT_PREDICTION = {
    "value": None,
    "range_low": None,
    "range_high": None,
    "confidence": 0,
    "explanation": "Failed to parse prediction",
}


def parse_prediction_response(response: str) -> Dict[str, Any]:
    """
    Attempt to parse the prediction response as JSON.
    If direct parsing fails, use regex extraction.
    Returns a dictionary with prediction data merged with DEFAULT_PREDICTION.
    """
    prediction_data = {}
    try:
        # Try to load the response directly as JSON.
        prediction_data = json.loads(response)
        logger.info("Successfully parsed JSON directly.")
    except json.JSONDecodeError:
        logger.warning("Direct JSON parsing failed. Attempting to extract JSON via regex.")
        # Try to extract JSON from a code block.
        json_block_match = JSON_CODE_BLOCK_RE.search(response)
        if json_block_match:
            json_str = json_block_match.group(1)
            json_str = (
                json_str.replace("'", '"')
                .replace("True", "true")
                .replace("False", "false")
                .replace("None", "null")
            )
            try:
                prediction_data = json.loads(json_str)
                logger.info("Successfully parsed JSON from code block.")
            except json.JSONDecodeError:
                logger.error("Failed to parse JSON from code block.")
        
        # If that didn't work, try to extract a dictionary-like structure.
        if not prediction_data:
            dict_match = DICT_STRUCTURE_RE.search(response)
            if dict_match:
                dict_str = "{" + dict_match.group(1) + "}"
                dict_str = (
                    dict_str.replace("'", '"')
                    .replace("True", "true")
                    .replace("False", "false")
                    .replace("None", "null")
                )
                try:
                    prediction_data = json.loads(dict_str)
                    logger.info("Successfully parsed JSON from dictionary structure.")
                except json.JSONDecodeError:
                    logger.error("Failed to parse JSON from dictionary structure.")
        
        # If still not parsed, try to extract individual fields.
        if not prediction_data or prediction_data.get("value") is None:
            prediction_data = {}
            value_match = VALUE_RE.search(response)
            range_low_match = RANGE_LOW_RE.search(response)
            range_high_match = RANGE_HIGH_RE.search(response)
            confidence_match = CONFIDENCE_RE.search(response)
            explanation_match = EXPLANATION_RE.search(response)

            if value_match:
                prediction_data["value"] = float(value_match.group(1))
            if range_low_match:
                prediction_data["range_low"] = float(range_low_match.group(1))
            if range_high_match:
                prediction_data["range_high"] = float(range_high_match.group(1))
            if confidence_match:
                prediction_data["confidence"] = float(confidence_match.group(1))
            if explanation_match:
                prediction_data["explanation"] = explanation_match.group(1)
            logger.info("Extracted fields via regex extraction.")

    # Merge with default values to ensure all keys are present.
    return {**DEFAULT_PREDICTION, **prediction_data}
