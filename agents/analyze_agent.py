from agency.agent import Agent
from agency.agency_types import Tendencies
from typing import Dict, Any
import json
from logger import logger
from utils.schema_json_parser import SchemaJsonParser, FieldSchema, FieldType


class AnalyzeAgent(Agent):
    def __init__(self, **kwargs):
        self.independent_analysis_schema = [
            FieldSchema(name="value", type=FieldType.NUMBER, required=True),
            FieldSchema(name="range_low", type=FieldType.NUMBER, required=True),
            FieldSchema(name="range_high", type=FieldType.NUMBER, required=True),
            FieldSchema(name="confidence", type=FieldType.NUMBER, required=True),
            FieldSchema(name="explanation", type=FieldType.STRING, required=True),
        ]

        self.review_schema = [
            FieldSchema(
                name="reasoning_assessment", type=FieldType.STRING, required=True
            ),
            FieldSchema(
                name="prediction_assessment", type=FieldType.STRING, required=True
            ),
            FieldSchema(
                name="confidence_assessment", type=FieldType.STRING, required=True
            ),
        ]

        self.comparison_schema = [
            FieldSchema(name="agreement_points", type=FieldType.ARRAY, required=True),
            FieldSchema(
                name="disagreement_points", type=FieldType.ARRAY, required=True
            ),
            FieldSchema(
                name="final_verification_confidence",
                type=FieldType.NUMBER,
                required=True,
            ),
        ]

        self.analyze_agent_schema = [
            FieldSchema(
                name="independent_analysis",
                type=FieldType.OBJECT,
                required=True,
                nested_schema=self.independent_analysis_schema,
            ),
            FieldSchema(
                name="review_of_primary_agent",
                type=FieldType.OBJECT,
                required=True,
                nested_schema=self.review_schema,
            ),
            FieldSchema(
                name="comparison_summary",
                type=FieldType.OBJECT,
                required=True,
                nested_schema=self.comparison_schema,
            ),
        ]

        self.parser = SchemaJsonParser(
            self.analyze_agent_schema,
            default_value={
                "independent_analysis": {
                    "value": None,
                    "range_low": None,
                    "range_high": None,
                    "confidence": 0,
                    "explanation": "Failed to parse analysis",
                },
                "review_of_primary_agent": {
                    "reasoning_assessment": "Failed to parse review",
                    "prediction_assessment": "Failed to parse review",
                    "confidence_assessment": "Failed to parse review",
                },
                "comparison_summary": {
                    "agreement_points": [],
                    "disagreement_points": [],
                    "final_verification_confidence": 0,
                },
            },
        )

        super().__init__(
            name="AnalyzeAgent",
            instructions=(
                "You are an expert NBA analyst acting as a verification layer."
                "You will receive the same data provided to a primary prediction agent AND that agent's prediction output."
                "Your task is to: \n"
                "1. Perform your own independent analysis of the provided data.\n"
                "2. Critically review the primary agent's prediction and reasoning.\n"
                "3. Compare your independent analysis with the primary agent's prediction.\n"
                "4. Provide a final report summarizing your findings, highlighting agreements, disagreements, confidence levels, and any potential overlooked factors."
            ),
            tendencies=analyze_agent_tendencies,
            model="openai-gpt-4.1",
            **kwargs,
        )

    async def execute_task(
        self,
        original_context: Dict[str, Any],
        primary_agent_output: Dict[str, Any],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Analyzes the primary agent's prediction against the original data context.

        Args:
            original_context: The data context originally sent to the primary agent.
            primary_agent_output: The prediction output (dict) from the primary agent.

        Returns:
            A dictionary containing the analysis report.
        """
        logger.info(
            f"AnalyzeAgent received task. Primary agent output: {primary_agent_output}"
        )

        try:
            context_str = json.dumps(original_context, indent=2)
            primary_output_str = json.dumps(primary_agent_output, indent=2)
        except TypeError as e:
            logger.error(f"Error serializing data for AnalyzeAgent: {e}")
            context_str = str(original_context)
            primary_output_str = str(primary_agent_output)

        prompt = f"""
        **Task: Review and Verify NBA Player Prediction**

        You are an expert NBA analyst reviewing a prediction made by another AI agent. Your goal is to provide a second opinion and verification.

        **1. Original Data Context:**
        This is the data the primary agent used:
        ```json
        {context_str}
        ```

        **2. Primary Agent's Prediction Output:**
        This is the prediction and reasoning provided by the primary agent:
        ```json
        {primary_output_str}
        ```

        **3. Your Instructions:**
        a. **Independent Analysis:** Based *only* on the 'Original Data Context', perform your own analysis. Predict the player's performance metric (value, range, confidence) and briefly explain your reasoning.
        b. **Review Primary Agent:** Critically evaluate the 'Primary Agent's Prediction Output'. Assess the quality of its reasoning, the appropriateness of the predicted value and range, and the stated confidence level in light of the data.
        c. **Comparison & Final Report:** Compare your independent analysis with the primary agent's prediction. Highlight key areas of agreement and disagreement. Discuss whether the primary agent potentially overlooked any critical factors or misinterpreted any data points. Conclude with your overall confidence in the primary agent's prediction.

        **4. Output Format:**
        Provide your response as a JSON object with the following structure:
        ```json
        {{
          "independent_analysis": {{
            "value": float,
            "range_low": float,
            "range_high": float,
            "confidence": float, // 0.0 to 1.0
            "explanation": "Your brief reasoning based on the data."
          }},
          "review_of_primary_agent": {{
            "reasoning_assessment": "Your assessment of the primary agent's reasoning.",
            "prediction_assessment": "Your assessment of the primary agent's predicted value/range.",
            "confidence_assessment": "Your assessment of the primary agent's confidence level."
          }},
          "comparison_summary": {{
            "agreement_points": ["List points of agreement."],
            "disagreement_points": ["List points of disagreement or overlooked factors."],
            "final_verification_confidence": float // Your overall confidence (0.0 to 1.0) in the primary agent's prediction after review.
          }}
        }}
        ```
        """

        logger.info("Sending prompt to AnalyzeAgent LLM...")
        response_str = await self.prompt(prompt)
        logger.info(f"AnalyzeAgent received response: {response_str}")

        try:
            analysis_result = self.parser.parse(response_str)
            return analysis_result
        except Exception as e:
            logger.error(
                f"AnalyzeAgent failed to parse LLM response: {e}\nResponse was: {response_str}"
            )
            return {
                "status": "error",
                "message": "Failed to parse analysis response from LLM.",
                "raw_response": response_str,
            }


analyze_agent_tendencies = Tendencies(
    **{
        "emotions": {"emotional_responsiveness": 0.1, "empathy_level": 0.2},
        "passiveness": 0.2,
        "risk_tolerance": 0.5,
        "patience_level": 0.8,
        "decision_making": "analytical",
        "core_values": [
            "objectivity",
            "critical thinking",
            "data integrity",
            "thoroughness",
            "constructive feedback",
        ],
        "goals": [
            "verify the accuracy and reasoning of primary predictions",
            "identify potential biases or errors in the primary analysis",
            "provide a reliable second opinion based purely on data",
            "enhance overall prediction quality through review",
        ],
        "fears": [
            "missing a critical flaw in the primary prediction",
            "introducing own bias during the review",
            "providing superficial analysis",
        ],
    }
)
