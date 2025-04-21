from typing import Optional, Literal
from datetime import datetime, timedelta

from adapters import Adapters
from logger import logger
from models.prediction_models import (
    PredictionMetrics,
    AllTimeframeMetrics,
    KeyMetrics,
    MetricWithChange,
    PlayerInfo,
)


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
            response = self.supabase.table("player_predictions").select("*").execute()
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
                actual = prediction["actual"]
                actual_value: Optional[float] = None
                try:
                    parsed_date = datetime.strptime(game_date, "%Y-%m-%d")
                    formatted_date = parsed_date.strftime("%Y-%m-%d")
                    if actual is None:
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
                    else:
                        logger.info(
                            f"Actual value for {player_name} ({prediction_type}) on {formatted_date}: {actual}"
                        )
                        actual_value = actual
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

    async def evaluate_game_predictions(self):
        """
        Evaluate game predictions by checking if the predicted game winner matches the actual game result.
        Returns a dict with total evaluated and winner accuracy percentage.
        """
        try:
            logger.info("Fetching game predictions from database...")
            response = self.supabase.table("game_predictions").select("*").execute()
            predictions_to_evaluate = response.data
            if not predictions_to_evaluate:
                logger.info("No game predictions found needing evaluation.")
                return
        except Exception as e:
            logger.error(f"Error fetching game predictions: {e}")
            return

        total_evaluated = 0
        winner_correct = 0

        for prediction in predictions_to_evaluate:
            try:
                logger.info(
                    f"Evaluating game prediction for game: {prediction.get('game_date')}, {prediction.get('home_team')} vs {prediction.get('away_team')}"
                )
                predicted_winner = prediction.get("predicted_winner")
                actual_winner = prediction.get("actual")

                if actual_winner is None:
                    try:
                        resp = await self.adapters.nba_analytics.get_game_winner(
                            game_date=prediction.get("game_date"),
                            home_team=prediction.get("home_team"),
                            away_team=prediction.get("away_team"),
                        )
                        logger.info(f"Game winner: {resp}")
                        if resp.get("actual_winner"):
                            self.supabase.table("game_predictions").update(
                                {"actual": resp.get("actual_winner")}
                            ).eq("game_date", prediction.get("game_date")).eq(
                                "home_team", prediction.get("home_team")
                            ).eq(
                                "away_team", prediction.get("away_team")
                            ).execute()
                            actual_winner = resp.get("actual_winner")
                    except Exception as e:
                        logger.error(
                            f"Error getting game winner for game_id {prediction.get('game_date')}, {prediction.get('home_team')} vs {prediction.get('away_team')}: {e}",
                            exc_info=True,
                        )
                        continue

                is_correct = False
                if predicted_winner and actual_winner:
                    is_correct = (
                        predicted_winner.strip().lower()
                        == actual_winner.strip().lower()
                    )

                self.supabase.table("game_predictions").update(
                    {"was_winner_correct": is_correct}
                ).eq("game_date", prediction.get("game_date")).eq(
                    "home_team", prediction.get("home_team")
                ).eq(
                    "away_team", prediction.get("away_team")
                ).execute()

                logger.debug(
                    f"Updated game prediction for game: {prediction.get('game_date')}, {prediction.get('home_team')} vs {prediction.get('away_team')}"
                )
                total_evaluated += 1
                if is_correct:
                    winner_correct += 1
            except Exception as e:
                logger.error(
                    f"Error processing game prediction for game_id {prediction.get('game_id')}: {e}",
                    exc_info=True,
                )

        if total_evaluated == 0:
            logger.info("No game predictions evaluated.")
            return

        accuracy = (winner_correct / total_evaluated) * 100
        logger.info(
            f"Game Predictions Evaluated: {total_evaluated}, Winner Accuracy: {accuracy:.2f}% ({winner_correct}/{total_evaluated})"
        )

        try:
            self.supabase.table("game_model_stats").insert(
                {
                    "total_evaluated": total_evaluated,
                    "winner_accuracy": round(accuracy, 2),
                }
            ).execute()
        except Exception as e:
            logger.error(f"Error inserting game metrics data: {e}", exc_info=True)

        return {
            "total_evaluated": total_evaluated,
            "winner_accuracy": round(accuracy, 2),
        }

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

    async def get_prediction_metrics_by_timeframe(
        self,
        timeframe: Literal["7_days", "14_days", "30_days", "all_time"],
        prediction_type: Optional[str] = None,
    ) -> PredictionMetrics:
        """
        Calculate prediction metrics (accuracy) for a specific timeframe.

        Args:
            timeframe: Time period to calculate metrics for ("7_days", "14_days", "30_days", "all_time")
            prediction_type: Optional filter for prediction type (e.g., "points", "rebounds", etc.)

        Returns:
            PredictionMetrics object containing accuracy metrics for the specified timeframe
        """
        try:
            query = self.supabase.table("player_predictions").select("*")

            if timeframe != "all_time":
                days = int(timeframe.split("_")[0])
                start_date = (datetime.now() - timedelta(days=days)).strftime(
                    "%Y-%m-%d"
                )
                query = query.gte("game_date", start_date)

            if prediction_type:
                query = query.eq("prediction_type", prediction_type)

            query = query.not_.is_("actual", None)

            response = query.execute()
            predictions = response.data

            logger.info(
                f"Found {len(predictions)} evaluated predictions for {timeframe} timeframe"
            )

            total_evaluated = len(predictions)
            exact_correct = sum(
                1 for p in predictions if p.get("was_exactly_correct", False)
            )
            range_correct = sum(
                1 for p in predictions if p.get("was_range_correct", False)
            )

            ou_predictions = [
                p for p in predictions if p.get("was_over_under_correct") is not None
            ]
            ou_evaluable = len(ou_predictions)
            ou_correct = sum(
                1 for p in ou_predictions if p.get("was_over_under_correct", False)
            )

            exact_accuracy = (
                (exact_correct / total_evaluated) * 100 if total_evaluated > 0 else 0
            )
            range_accuracy = (
                (range_correct / total_evaluated) * 100 if total_evaluated > 0 else 0
            )
            ou_accuracy = (ou_correct / ou_evaluable) * 100 if ou_evaluable > 0 else 0

            metrics = PredictionMetrics(
                timeframe=timeframe,
                prediction_type=prediction_type if prediction_type else "all",
                total_evaluated=total_evaluated,
                exact_accuracy=round(exact_accuracy, 2),
                range_accuracy=round(range_accuracy, 2),
                over_under_accuracy=round(ou_accuracy, 2),
                exact_correct=exact_correct,
                range_correct=range_correct,
                over_under_correct=ou_correct,
                over_under_evaluable=ou_evaluable,
            )

            logger.info(f"Metrics for {timeframe}: {metrics}")
            return metrics

        except Exception as e:
            logger.error(
                f"Error calculating metrics for {timeframe}: {e}", exc_info=True
            )
            return PredictionMetrics(
                timeframe=timeframe,
                prediction_type=prediction_type if prediction_type else "all",
                error=str(e),
                total_evaluated=0,
                exact_accuracy=0,
                range_accuracy=0,
                over_under_accuracy=0,
                exact_correct=0,
                range_correct=0,
                over_under_correct=0,
                over_under_evaluable=0,
            )

    async def get_all_timeframe_metrics(
        self, prediction_type: Optional[str] = None
    ) -> AllTimeframeMetrics:
        """
        Get prediction metrics for all standard timeframes (7 days, 14 days, 30 days, all time).

        Args:
            prediction_type: Optional filter for prediction type

        Returns:
            AllTimeframeMetrics object with metrics for each timeframe
        """
        timeframes: list[Literal["7_days", "14_days", "30_days", "all_time"]] = [
            "7_days",
            "14_days",
            "30_days",
            "all_time",
        ]
        results = {}

        for timeframe in timeframes:
            metrics = await self.get_prediction_metrics_by_timeframe(
                timeframe=timeframe, prediction_type=prediction_type
            )
            results[timeframe] = metrics

        return AllTimeframeMetrics(metrics=results)

    async def get_key_metrics(
        self, timeframe: Literal["7_days", "14_days", "30_days", "all_time"]
    ) -> KeyMetrics:
        """
        Get key dashboard metrics with change values from previous period.

        Args:
            timeframe: Time period for metrics calculation

        Returns:
            KeyMetrics object with current values and changes
        """
        current_metrics = await self.get_prediction_metrics_by_timeframe(
            timeframe=timeframe, prediction_type="points"
        )

        previous_metrics = await self._get_previous_period_metrics(timeframe)

        range_accuracy_change = self._calculate_change(
            current_metrics.range_accuracy,
            previous_metrics.range_accuracy if previous_metrics else None,
        )

        over_under_accuracy_change = self._calculate_change(
            current_metrics.over_under_accuracy,
            previous_metrics.over_under_accuracy if previous_metrics else None,
        )

        most_picked_player = await self._get_most_picked_player(timeframe)

        return KeyMetrics(
            prediction_accuracy=MetricWithChange(
                value=f"{current_metrics.range_accuracy}%", change=range_accuracy_change
            ),
            win_rate=MetricWithChange(
                value=f"{current_metrics.over_under_accuracy}%",
                change=over_under_accuracy_change,
            ),
            most_picked_player=most_picked_player,
            timeframe=timeframe,
        )

    async def _get_previous_period_metrics(
        self, timeframe: str
    ) -> Optional[PredictionMetrics]:
        """Get metrics from the previous time period for change calculation."""
        try:
            if timeframe == "all_time":
                logger.info("No previous period for all_time timeframe")
                return None

            days = int(timeframe.split("_")[0])

            end_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=days * 2)).strftime(
                "%Y-%m-%d"
            )

            logger.info(
                f"Looking for previous metrics between {start_date} and {end_date}"
            )

            try:
                table_query = (
                    self.supabase.table("points_model_stats")
                    .select("*")
                    .limit(1)
                    .execute()
                )
                table_has_data = len(table_query.data) > 0
                logger.info(f"Found data in points_model_stats table: {table_has_data}")
            except Exception as e:
                logger.warning(f"Error checking points_model_stats table: {e}")
                table_has_data = False

            if not table_has_data:
                logger.warning("No data in points_model_stats table")
                return await self._calculate_previous_metrics_from_predictions(
                    timeframe
                )

            query = self.supabase.table("points_model_stats").select("*")

            query = query.gte("created_at", start_date)
            query = query.lt("created_at", end_date)

            query = query.order("ƒqu", desc=True).limit(1)

            response = query.execute()
            logger.info(f"Query results: {response.data}")

            if response.data and len(response.data) > 0:
                metrics = PredictionMetrics(
                    timeframe=timeframe,
                    prediction_type="points",
                    total_evaluated=response.data[0].get("total_evaluated", 0),
                    exact_accuracy=response.data[0].get("exact_accuracy", 0),
                    range_accuracy=response.data[0].get("range_accuracy", 0),
                    over_under_accuracy=response.data[0].get("over_under_accuracy", 0),
                    exact_correct=0,
                    range_correct=0,
                    over_under_correct=0,
                    over_under_evaluable=0,
                )
                logger.info(f"Found historical metrics: {metrics}")
                return metrics

            return await self._calculate_previous_metrics_from_predictions(timeframe)

        except Exception as e:
            logger.error(f"Error getting previous period metrics: {e}", exc_info=True)
            return None

    async def _calculate_previous_metrics_from_predictions(
        self, timeframe: str
    ) -> Optional[PredictionMetrics]:
        """Calculate metrics directly from player_predictions for the previous time period."""
        try:
            days = int(timeframe.split("_")[0])

            end_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=days * 2)).strftime(
                "%Y-%m-%d"
            )

            logger.info(
                f"Calculating previous metrics directly from predictions for {start_date} to {end_date}"
            )

            query = self.supabase.table("player_predictions").select("*")
            query = query.gte("game_date", start_date)
            query = query.lt("game_date", end_date)
            query = query.not_.is_("actual", None)
            query = query.eq("prediction_type", "points")

            response = query.execute()
            predictions = response.data

            if not predictions:
                logger.warning(
                    f"No predictions found for previous period ({start_date} to {end_date})"
                )
                return None

            logger.info(f"Found {len(predictions)} predictions for previous period")

            total_evaluated = len(predictions)
            exact_correct = sum(
                1 for p in predictions if p.get("was_exactly_correct", False)
            )
            range_correct = sum(
                1 for p in predictions if p.get("was_range_correct", False)
            )

            ou_predictions = [
                p for p in predictions if p.get("was_over_under_correct") is not None
            ]
            ou_evaluable = len(ou_predictions)
            ou_correct = sum(
                1 for p in ou_predictions if p.get("was_over_under_correct", False)
            )

            exact_accuracy = (
                (exact_correct / total_evaluated) * 100 if total_evaluated > 0 else 0
            )
            range_accuracy = (
                (range_correct / total_evaluated) * 100 if total_evaluated > 0 else 0
            )
            ou_accuracy = (ou_correct / ou_evaluable) * 100 if ou_evaluable > 0 else 0

            metrics = PredictionMetrics(
                timeframe=timeframe,
                prediction_type="points",
                total_evaluated=total_evaluated,
                exact_accuracy=round(exact_accuracy, 2),
                range_accuracy=round(range_accuracy, 2),
                over_under_accuracy=round(ou_accuracy, 2),
                exact_correct=exact_correct,
                range_correct=range_correct,
                over_under_correct=ou_correct,
                over_under_evaluable=ou_evaluable,
            )

            logger.info(f"Calculated previous metrics: {metrics}")
            return metrics

        except Exception as e:
            logger.error(
                f"Error calculating previous metrics from predictions: {e}",
                exc_info=True,
            )
            return None

    def _calculate_change(
        self, current_value: float, previous_value: Optional[float]
    ) -> str:
        """Calculate the percentage change between current and previous values."""
        if previous_value is None or previous_value == 0:
            return "N/A"

        change = current_value - previous_value
        return f"{'+' if change >= 0 else ''}{change:.1f}%"

    async def _get_most_picked_player(self, timeframe: str) -> PlayerInfo:
        """Get the most frequently predicted player in the given timeframe."""
        try:
            query = self.supabase.table("player_predictions").select("*")

            if timeframe != "all_time":
                days = int(timeframe.split("_")[0])
                start_date = (datetime.now() - timedelta(days=days)).strftime(
                    "%Y-%m-%d"
                )
                query = query.gte("game_date", start_date)

            response = query.execute()

            if not response.data:
                return PlayerInfo(name="No Data")

            player_counts = {}
            for prediction in response.data:
                player_name = prediction.get("player_name")
                if player_name:
                    player_counts[player_name] = player_counts.get(player_name, 0) + 1

            if not player_counts:
                return PlayerInfo(name="No Data")

            most_picked_player = max(player_counts.items(), key=lambda x: x[1])
            player_name = most_picked_player[0]
            count = most_picked_player[1]

            accuracy_query = self.supabase.table("player_predictions").select("*")
            accuracy_query = accuracy_query.eq("player_name", player_name)
            accuracy_query = accuracy_query.not_.is_("actual", None)

            if timeframe != "all_time":
                days = int(timeframe.split("_")[0])
                start_date = (datetime.now() - timedelta(days=days)).strftime(
                    "%Y-%m-%d"
                )
                accuracy_query = accuracy_query.gte("game_date", start_date)

            accuracy_response = accuracy_query.execute()

            if accuracy_response.data:
                evaluated = len(accuracy_response.data)
                correct = sum(
                    1
                    for p in accuracy_response.data
                    if p.get("was_range_correct", False)
                )
                accuracy = (
                    f"{(correct / evaluated * 100):.1f}%" if evaluated > 0 else "N/A"
                )
            else:
                accuracy = "N/A"

            return PlayerInfo(name=player_name, count=count, accuracy=accuracy)

        except Exception as e:
            logger.error(f"Error getting most picked player: {e}", exc_info=True)
            return PlayerInfo(name="Error")
