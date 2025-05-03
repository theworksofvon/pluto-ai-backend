import os
from adapters import Adapters
import resend
from datetime import datetime
from config import config
import asyncio


class UserService:
    def __init__(self):
        self.adapters = Adapters()
        self.supabase = self.adapters.supabase.get_supabase_client()
        resend.api_key = config.RESEND_API_KEY

    async def send_prediction_notifs(self):
        response = self.supabase.auth.admin.list_users()
        emails = [user.email for user in response]

        today = datetime.now().strftime("%B %d, %Y")

        for email in emails:
            if email:
                html_content = self._get_daily_html_template(date_str=today)
                message = {
                    "from": "Pluto Predicts <no-reply@plutopredicts.com>",
                    "to": email,
                    "subject": f"🧠 Your {today} Predictions Are In!",
                    "html": html_content,
                }
                resend.Emails.send(message)
                await asyncio.sleep(0.5)  # api rate limit of 2 emails per second
        return {"status": "Prediction notifications sent"}

    async def send_game_prediction_notifs(self):
        """Fetch users from Supabase and send game prediction notification emails using Resend."""
        response = self.supabase.auth.admin.list_users()
        emails = [user["email"] for user in response["users"]]
        for email in emails:
            if email:
                message = {
                    "from": "no-reply@example.com",
                    "to": email,
                    "subject": "Your game predictions are in",
                    "html": "<p>Game predictions have been updated. Check them out!</p>",
                }
                resend.Emails.send(message)
        return {"status": "Game prediction notifications sent"}

    def _get_daily_html_template(
        self, date_str: str, unsubscribe_link: str = "#"
    ) -> str:
        return f"""
        <!DOCTYPE html>
        <html lang="en" style="font-family: sans-serif; background-color: #f5f7fa;">
        <head><meta charset="UTF-8" /><title>Pluto Predicts - Daily Predictions</title></head>
        <body style="margin: 0; padding: 0; background-color: #f5f7fa;">
            <table align="center" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden;">
                <tr>
                    <td style="padding: 24px; background-color: #121826; text-align: center; color: white;">
                        <h1 style="margin: 0; font-size: 24px;">🚀 Pluto Predicts</h1>
                        <p style="margin: 4px 0 0;">Your daily edge in the NBA playoffs</p>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 24px; color: #333;">
                        <h2 style="margin-top: 0;">Today's Predictions Are In 🧠</h2>
                        <p style="line-height: 1.6;">
                            The AI has crunched the latest data — predictions for <strong>{date_str}</strong> are now live on your dashboard.
                        </p>
                        <ul style="padding-left: 20px;">
                            <li>🔥 Player points projections</li>
                            <li>🏆 Game winner picks</li>
                            <li>💡 Confidence levels and insights</li>
                        </ul>
                        <p>Tap below to view your picks before the lines shift:</p>
                        <div style="text-align: center; margin: 24px 0;">
                            <a href="https://plutopredicts.com/dashboard" target="_blank" style="display: inline-block; background-color: #6366f1; color: white; text-decoration: none; padding: 12px 24px; border-radius: 6px; font-weight: bold;">
                                View Predictions →
                            </a>
                        </div>
                        <p style="font-size: 12px; color: #777;">
                            This message was sent to you by Pluto Predicts.<br>
                            Unsubscribe <a href="{unsubscribe_link}" style="color: #6366f1;">here</a> if you'd prefer not to receive daily emails.
                        </p>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

    def get_favored_pick_html_template(
        self,
        player_name: str,
        prediction_type: str,
        predicted_value: str,
        confidence: str,
        line: str,
        over_or_under: str,
        unsubscribe_link: str = "#",
    ) -> str:
        return f"""
        <!DOCTYPE html>
        <html lang="en" style="font-family: sans-serif; background-color: #f5f7fa;">
        <head>
            <meta charset="UTF-8" />
            <title>Pluto Predicts - Favored Pick</title>
        </head>
        <body style="margin: 0; padding: 0; background-color: #f5f7fa;">
            <table align="center" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden;">
                <tr>
                    <td style="padding: 24px; background-color: #121826; text-align: center; color: white;">
                        <h1 style="margin: 0; font-size: 24px;">🚀 Pluto Predicts</h1>
                        <p style="margin: 4px 0 0;">Today's Favored Pick</p>
                    </td>
                </tr>

                <tr>
                    <td style="padding: 24px; color: #333;">
                        <h2 style="margin-top: 0;">🔥 Pick of the Day</h2>
                        <p style="font-size: 16px; line-height: 1.6;">
                            Our AI models have analyzed today's matchups and identified the top edge on the board:
                        </p>

                        <div style="background-color: #f1f5f9; border-left: 4px solid #6366f1; padding: 16px; margin: 16px 0; border-radius: 8px;">
                            <h3 style="margin: 0 0 8px 0;">{player_name} – {prediction_type}</h3>
                            <p style="margin: 0;">
                                🔢 Projected: <strong>{predicted_value}</strong><br />
                                📈 Confidence: <strong>{confidence}</strong><br />
                                📊 PrizePicks Line: <strong>{line}</strong><br />
                                ✅ Suggested: <strong>{over_or_under}</strong>
                            </p>
                        </div>

                        <p>Want the full slate? Hit your dashboard below 👇</p>

                        <div style="text-align: center; margin: 24px 0;">
                            <a href="https://plutopredicts.com/dashboard" target="_blank" style="display: inline-block; background-color: #6366f1; color: white; text-decoration: none; padding: 12px 24px; border-radius: 6px; font-weight: bold;">
                                View Full Predictions →
                            </a>
                        </div>

                        <p style="font-size: 12px; color: #777;">
                            This message was sent by Pluto Predicts.<br />
                            Unsubscribe <a href="{unsubscribe_link}" style="color: #6366f1;">here</a> if you'd prefer not to receive daily pick emails.
                        </p>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
