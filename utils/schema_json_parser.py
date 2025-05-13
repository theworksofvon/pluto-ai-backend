import json
import re
from enum import Enum
from typing import Any, Dict, List, Optional
from models import BaseSchema

from logger import logger


class FieldType(Enum):
    """Enum representing the possible field types for regex extraction."""

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"


class FieldSchema(BaseSchema):
    """Schema definition for a field to be extracted."""

    name: str
    type: FieldType
    required: bool
    nested_schema: Optional[List["FieldSchema"]] = None


class SchemaJsonParser:
    """
    A schema-based JSON parser that can extract structured data from
    text responses using multiple parsing strategies.

    This parser first attempts standard JSON parsing methods, then falls back
    to field-by-field regex extraction based on the provided schema.

    Example:
        ```python
        from utils.schema_json_parser import FieldType, SchemaJsonParser, FieldSchema

        # Define the schema for player predictions
        player_schema = [
            FieldSchema(name="value", type=FieldType.NUMBER, required=True),
            FieldSchema(name="range_low", type=FieldType.NUMBER, required=False),
            FieldSchema(name="range_high", type=FieldType.NUMBER, required=False),
            FieldSchema(name="confidence", type=FieldType.NUMBER, required=True),
            FieldSchema(name="explanation", type=FieldType.STRING, required=True),
        ]

        # Create a parser with this schema
        parser = SchemaJsonParser(player_schema)

        # Sample response from an AI agent
        response = '''
        I think the player will score 25.5 points.

        ```json
        {
          "value": 25.5,
          "range_low": 22.0,
          "range_high": 28.0,
          "confidence": 0.8,
          "explanation": "The player has been averaging 24 points in the last 5 games."
        }
        ```
        '''

        # Parse the response
        result = parser.parse(response)
        print(result)

        # Example with nested objects
        analysis_schema = [
            FieldSchema(
                name="independent_analysis",
                type=FieldType.OBJECT,
                required=True,
                nested_schema=[
                    FieldSchema(name="value", type=FieldType.NUMBER, required=True),
                    FieldSchema(name="confidence", type=FieldType.NUMBER, required=True),
                    FieldSchema(name="explanation", type=FieldType.STRING, required=True),
                ]
            ),
            FieldSchema(
                name="review",
                type=FieldType.OBJECT,
                required=True,
                nested_schema=[
                    FieldSchema(name="assessment", type=FieldType.STRING, required=True),
                ]
            )
        ]

        # Create nested parser
        nested_parser = SchemaJsonParser(analysis_schema)
        nested_result = nested_parser.parse(complex_response)
        ```
    """

    JSON_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
    DICT_STRUCTURE_RE = re.compile(r"\{(.*?)\}", re.DOTALL)

    def __init__(
        self, schema: List[FieldSchema], default_value: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the parser with a schema and optional default value.

        Args:
            schema: A list of field definitions specifying names, types, and whether they're required
            default_value: Default value to return if parsing fails completely
        """
        self.schema = schema
        self.default_value = default_value if default_value is not None else {}
        self.field_regexes = {}

        for field in schema:
            self.field_regexes[field.name] = self._create_field_regex(
                field.name, field.type
            )

    def _create_field_regex(self, field_name: str, field_type: FieldType) -> re.Pattern:
        """
        Create a regex pattern for extracting a specific field based on its name and type.

        Args:
            field_name: The name of the field to extract
            field_type: The expected data type of the field

        Returns:
            A compiled regex pattern for the specified field
        """
        name_pattern = rf"[\"']{field_name}[\"']\s*:\s*"

        if field_type == FieldType.STRING:
            # capture everything (including newlines, commas, apostrophes)
            # non‑greedy up to the next closing quote
            value_pattern = r"\"([\s\S]+?)\""
        elif field_type == FieldType.NUMBER:
            value_pattern = r"([0-9.]+)"
        elif field_type == FieldType.BOOLEAN:
            value_pattern = r"(true|false|True|False)"
        elif field_type == FieldType.OBJECT:
            value_pattern = r"(\{.*?\})"
        elif field_type == FieldType.ARRAY:
            value_pattern = r"(\[.*?\])"
        else:
            value_pattern = r"(.*?)"

        full_pattern = name_pattern + value_pattern
        return re.compile(full_pattern, re.DOTALL)

    def _try_direct_json_parsing(self, response: str) -> Optional[Dict[str, Any]]:
        """Attempt to parse the entire response as valid JSON."""
        try:
            parsed_data = json.loads(response)
            logger.info("Successfully parsed JSON directly.")
            return self._extract_schema_fields(parsed_data)
        except json.JSONDecodeError:
            logger.warning("Direct JSON parsing failed.")
            return None

    def _try_code_block_extraction(self, response: str) -> Optional[Dict[str, Any]]:
        """Attempt to extract and parse JSON from a code block."""
        json_block_match = self.JSON_CODE_BLOCK_RE.search(response)
        if not json_block_match:
            return None

        json_text = json_block_match.group(1)
        normalized_json = self._normalize_json_string(json_text)

        try:
            parsed_data = json.loads(normalized_json)
            logger.info("Successfully parsed JSON from code block.")
            return self._extract_schema_fields(parsed_data)
        except json.JSONDecodeError:
            logger.error("Failed to parse JSON from code block.")
            return None

    def _try_dict_structure_extraction(self, response: str) -> Optional[Dict[str, Any]]:
        """Attempt to extract and parse a dictionary-like structure."""
        dict_match = self.DICT_STRUCTURE_RE.search(response)
        if not dict_match:
            return None

        dict_text = "{" + dict_match.group(1) + "}"
        normalized_json = self._normalize_json_string(dict_text)

        try:
            parsed_data = json.loads(normalized_json)
            logger.info("Successfully parsed JSON from dictionary structure.")
            return self._extract_schema_fields(parsed_data)
        except json.JSONDecodeError:
            logger.error("Failed to parse JSON from dictionary structure.")
            return None

    def _try_field_by_field_extraction(self, response: str) -> Dict[str, Any]:
        """Extract each field individually using regex patterns."""
        logger.info("Attempting field-by-field regex extraction.")
        result = {field.name: None for field in self.schema}

        for field in self.schema:
            pattern = self.field_regexes[field.name]
            match = pattern.search(response)

            if match:
                raw_value = match.group(1)
                result[field.name] = self._convert_value(
                    raw_value, field.type, field.nested_schema
                )

        # Check if we found any fields
        if all(value is None for value in result.values()):
            logger.error("Field-by-field extraction failed to find any fields.")
            return {}

        # Filter out None values for non-required fields
        final_result = {}
        for field in self.schema:
            if result[field.name] is not None or field.required:
                final_result[field.name] = result[field.name]
        return final_result

    def _normalize_json_string(self, json_str: str) -> str:
        """Convert Python syntax to valid JSON syntax."""
        return (
            json_str.replace("'", '"')
            .replace("True", "true")
            .replace("False", "false")
            .replace("None", "null")
        )

    def _convert_value(
        self,
        raw_value: str,
        field_type: FieldType,
        nested_schema: Optional[List[FieldSchema]] = None,
    ) -> Any:
        """Convert extracted string values to their appropriate Python types."""
        if field_type == FieldType.NUMBER:
            try:
                if "." in raw_value:
                    return float(raw_value)
                else:
                    return int(raw_value)
            except ValueError:
                return None
        elif field_type == FieldType.BOOLEAN:
            return raw_value.lower() in ("true", "True")
        elif field_type == FieldType.OBJECT:
            try:
                json_str = self._normalize_json_string(raw_value)
                parsed_object = json.loads(json_str)

                if nested_schema:
                    nested_parser = SchemaJsonParser(nested_schema)
                    return nested_parser._extract_schema_fields(parsed_object)
                return parsed_object
            except json.JSONDecodeError:
                return raw_value
        elif field_type == FieldType.ARRAY:
            try:
                json_str = self._normalize_json_string(raw_value)
                return json.loads(json_str)
            except json.JSONDecodeError:
                return raw_value
        else:
            return raw_value

    def _extract_schema_fields(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract fields from parsed data according to the schema."""
        result = {}

        for field in self.schema:
            if field.name in parsed_data:
                value = parsed_data[field.name]

                if (
                    field.type == FieldType.OBJECT
                    and field.nested_schema
                    and isinstance(value, dict)
                ):
                    nested_parser = SchemaJsonParser(field.nested_schema)
                    result[field.name] = nested_parser._extract_schema_fields(value)
                else:
                    result[field.name] = value
            elif field.required:
                result[field.name] = None

        return result

    def parse(self, response: Any) -> Dict[str, Any]:
        """
        Parse a response using the schema.

        This method tries multiple parsing strategies in sequence:
        1. If response is a Pydantic model, return it directly
        2. Direct JSON parsing
        3. Extracting JSON from code blocks
        4. Extracting dictionary-like structures
        5. Field-by-field regex extraction

        Args:
            response: The response to parse (can be string, dict, or Pydantic model)

        Returns:
            A dictionary with the extracted values according to the schema
        """
        # If response is a Pydantic model, return it directly
        if hasattr(response, "model_dump"):
            logger.info("Response is a Pydantic model, returning directly")
            return response

        # If response is already a dict, extract schema fields
        if isinstance(response, dict):
            logger.info("Response is a dict, extracting schema fields")
            return self._extract_schema_fields(response)

        # If response is a string, try parsing strategies
        if isinstance(response, str):
            result = (
                self._try_direct_json_parsing(response)
                or self._try_code_block_extraction(response)
                or self._try_dict_structure_extraction(response)
                or self._try_field_by_field_extraction(response)
            )

            if not result:
                logger.error("All parsing strategies failed. Using default value.")
                return self.default_value

        logger.info(f"Result after parsing: {result}")
        return result
