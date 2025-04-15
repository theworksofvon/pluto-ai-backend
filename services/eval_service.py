from typing import Optional
from datetime import datetime

from adapters import Adapters
from logger import logger


class EvaluationService:
    def __init__(self):
        self.adapters = Adapters()
        self.supabase = self.adapters.supabase.get_supabase_client()

    async def evaluate_points_predictions(self):
        """
        Fetches player points predictions, gets actual results, updates correctness flags,
        and calculates overall evaluation metrics.
        """
        all_predictions = []
        evaluated_count = 0
        fetch_errors = 0
        update_errors = 0

        try:
            logger.info("Fetching player predictions from database...")
            response = (
                self.supabase.table("player_predictions")
                .select("*")
                .is_("actual", None)
                .execute()
            )
            predictions_to_evaluate = response.data

            logger.info(
                f"Found {len(predictions_to_evaluate)} predictions to evaluate."
            )
            if not predictions_to_evaluate:
                logger.info("No predictions found needing evaluation.")
                return

        except Exception as e:
            logger.error(f"Error fetching predictions: {e}")
            return

        for prediction in predictions_to_evaluate:
            if (
                prediction["was_exactly_correct"] is not None
                or prediction["was_range_correct"] is not None
                or prediction["was_over_under_correct"] is not None
            ):
                continue
            try:
                logger.debug(f"Evaluating prediction ID: {prediction['prediction_id']}")

                player_name = prediction["player_name"]
                game_date = prediction["game_date"]
                prediction_type = prediction["prediction_type"]
                predicted_value = prediction["predicted_value"]
                range_low = prediction["range_low"]
                range_high = prediction["range_high"]
                prizepicks_prediction = prediction["prizepicks_prediction"]
                prizepicks_line = prediction["prizepicks_line"]
                prizepicks_reason = prediction["prizepicks_reason"]

                actual_value: Optional[float] = None
                try:
                    parsed_date = datetime.strptime(game_date, "%Y-%m-%d")
                    formatted_date = parsed_date.strftime("%Y-%m-%d")
                    actual_value = (
                        await self.adapters.nba_analytics.get_player_actual_stats(
                            player_name=player_name,
                            game_date=formatted_date,
                            stat_type=prediction_type,
                        )
                    )
                    logger.info(
                        f"Actual value for {player_name} ({prediction_type}) on {formatted_date}: {actual_value}"
                    )
                    if actual_value:
                        self.supabase.table("player_predictions").update(
                            {"actual": actual_value}
                        ).eq("prediction_id", prediction["prediction_id"]).execute()
                    logger.debug(
                        f"Actual value for {player_name} ({prediction_type}) on {formatted_date}: {actual_value}"
                    )
                except AttributeError:
                    logger.error(
                        "`get_player_actual_stats` method not found in nba_analytics adapter. Skipping actual value fetching."
                    )
                    fetch_errors += 1
                    continue
                except Exception as e:
                    logger.warning(
                        f"Could not fetch actual result for prediction {prediction['prediction_id']}: {e}"
                    )
                    fetch_errors += 1
                    continue

                is_exact = (
                    predicted_value is not None
                    and abs(actual_value - predicted_value) < 1e-6
                )
                is_range = (
                    range_low is not None
                    and range_high is not None
                    and range_low <= actual_value <= range_high
                )

                is_over_under = None
                if prizepicks_line and prizepicks_prediction:
                    logger.info(
                        f"Evaluating O/U for {prediction['prediction_id']}...direction: {prizepicks_prediction} line: {prizepicks_line}"
                    )
                    direction = prizepicks_prediction.lower().strip()
                    if "over" in direction:
                        is_over_under = actual_value > prizepicks_line
                    elif "under" in direction:
                        is_over_under = actual_value < prizepicks_line
                    else:
                        logger.warning(
                            f"Unrecognized prizepicks_line '{prizepicks_line}' for prediction {prediction['prediction_id']}"
                        )
                else:
                    logger.debug(
                        f"Skipping O/U eval for {prediction['prediction_id']}: line='{prizepicks_line}', reason='{prizepicks_reason}'"
                    )

                response = (
                    self.supabase.table("player_predictions")
                    .update(
                        {
                            "was_exactly_correct": is_exact,
                            "was_range_correct": is_range,
                            "was_over_under_correct": is_over_under,
                        }
                    )
                    .eq("prediction_id", prediction["prediction_id"])
                    .execute()
                )

                logger.debug(f"Updated prediction ID: {prediction['prediction_id']}")

                evaluated_count += 1
                prediction["was_exactly_correct"] = is_exact
                prediction["was_range_correct"] = is_range
                prediction["was_over_under_correct"] = is_over_under

            except Exception as e:
                logger.error(
                    f"Error processing prediction ID {prediction['prediction_id']}: {e}",
                    exc_info=True,
                )
                update_errors += 1

        logger.info(
            f"Evaluation loop finished. Evaluated: {evaluated_count}, Fetch Errors: {fetch_errors}, Update Errors: {update_errors}"
        )

        try:
            all_predictions = (
                self.supabase.table("player_predictions").select("*").execute()
            )
            all_predictions = all_predictions.data
            logger.info(
                f"Recalculating metrics based on {len(all_predictions)} total predictions."
            )
        except Exception as e:
            logger.error(f"Error refetching all predictions for final metrics: {e}")
            logger.warning("Calculating metrics based on potentially stale data.")

        total_evaluated = 0
        exact_correct = 0
        range_correct = 0
        ou_correct = 0
        ou_evaluable = 0

        for p in all_predictions:
            if (
                p["was_exactly_correct"] is not None
                or p["was_range_correct"] is not None
                or p["was_over_under_correct"] is not None
            ):
                total_evaluated += 1
                if p["was_exactly_correct"]:
                    exact_correct += 1
                if p["was_range_correct"]:
                    range_correct += 1
                if p["was_over_under_correct"] is not None:
                    ou_evaluable += 1
                    if p["was_over_under_correct"]:
                        ou_correct += 1

        if total_evaluated == 0:
            logger.info("No predictions have been evaluated yet.")
            return

        logger.info("--- Evaluation Results ---")
        exact_accuracy = (
            (exact_correct / total_evaluated) * 100 if total_evaluated > 0 else 0
        )
        range_accuracy = (
            (range_correct / total_evaluated) * 100 if total_evaluated > 0 else 0
        )
        ou_accuracy = (ou_correct / ou_evaluable) * 100 if ou_evaluable > 0 else 0

        logger.info(f"Total Predictions Evaluated: {total_evaluated}")
        logger.info(
            f"Exact Match Accuracy: {exact_accuracy:.2f}% ({exact_correct}/{total_evaluated})"
        )
        logger.info(
            f"Range Accuracy: {range_accuracy:.2f}% ({range_correct}/{total_evaluated})"
        )
        logger.info(
            f"Over/Under Accuracy: {ou_accuracy:.2f}% ({ou_correct}/{ou_evaluable})"
        )
        logger.info("--------------------------")

        self.supabase.table("points_model_stats").insert(
            {
                "total_evaluated": total_evaluated,
                "exact_accuracy": exact_accuracy,
                "range_accuracy": range_accuracy,
                "over_under_accuracy": ou_accuracy,
            }
        ).execute()

        return {
            "total_evaluated": total_evaluated,
            "exact_accuracy": exact_accuracy,
            "range_accuracy": range_accuracy,
            "ou_accuracy": ou_accuracy,
        }

    async def evaluate_rebounds_predictions(self):
        pass

    async def evaluate_assists_predictions(self):
        pass

    async def get_and_fill_actual_values(self):
        response = (
            self.supabase.table("player_predictions")
            .select("*")
            .is_("actual", None)
            .execute()
        )
        predictions_to_fill = response.data

        for prediction in predictions_to_fill:
            player_name = prediction["player_name"]
            game_date = prediction["game_date"]
            prediction_type = prediction["prediction_type"]

            actual_value = await self.adapters.nba_analytics.get_player_actual_stats(
                player_name=player_name,
                game_date=game_date,
                stat_type=prediction_type,
            )
            self.supabase.table("player_predictions").update(
                {"actual": actual_value}
            ).eq("prediction_id", prediction["prediction_id"]).execute()

        logger.info(f"All actual values filled....")
