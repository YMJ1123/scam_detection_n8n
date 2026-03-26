"""
Anti-Fraud Discord Bot
Receives user messages, sends them to n8n webhook for analysis,
and replies with formatted results.
"""

import os
import io
import base64
import json
import logging
from typing import Optional

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/anti-fraud")
BEDROCK_API_KEY = os.getenv("BEDROCK_API_KEY", "")
ANTI_FRAUD_API_KEY = os.getenv("ANTI_FRAUD_API_KEY", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("anti-fraud-bot")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

RISK_COLORS = {
    "SAFE": 0x2ECC71,
    "NO_RISK_FOR_NOW": 0xF1C40F,
    "POTENTIAL_SCAM": 0xE67E22,
    "SCAM": 0xE74C3C,
    "FAILED": 0x95A5A6,
}


def _empty_result(display_text="無分析結果") -> dict:
    return {
        "display_text": display_text,
        "url_results": [],
        "number_results": [],
        "content_result": None,
        "summary": "",
        "original_text": "",
    }


async def call_n8n(text: str) -> dict:
    """Send text to n8n webhook, return parsed response."""
    payload = {
        "text": text,
        "bedrock_api_key": BEDROCK_API_KEY,
        "anti_fraud_api_key": ANTI_FRAUD_API_KEY,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                N8N_WEBHOOK_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                body_text = await resp.text()
                log.info("n8n returned %d: %s", resp.status, body_text[:500])

                if resp.status == 200:
                    try:
                        data = json.loads(body_text)
                    except json.JSONDecodeError:
                        return _empty_result(f"n8n 回傳非 JSON: {body_text[:200]}")

                    if isinstance(data, list):
                        data = data[0] if data else {}
                    if isinstance(data, dict) and "json" in data:
                        data = data["json"]
                    if not isinstance(data, dict):
                        return _empty_result(f"n8n 回傳格式不符: {type(data).__name__}")
                    return data

                return _empty_result(f"n8n 回應錯誤 (HTTP {resp.status})")
    except Exception as e:
        log.exception("Failed to call n8n webhook")
        return _empty_result(f"無法連線 n8n: {e}")


def determine_overall_risk(data: dict) -> str:
    """Pick the highest risk level from all results."""
    if not data or not isinstance(data, dict):
        return "SAFE"

    risk_priority = ["SCAM", "POTENTIAL_SCAM", "NO_RISK_FOR_NOW", "SAFE"]

    levels = set()

    for u in (data.get("url_results") or []):
        score = u.get("score")
        if score is not None:
            if u.get("blacklisted"):
                levels.add("SCAM")
            elif score < 50:
                levels.add("SCAM")
            elif score < 80:
                levels.add("POTENTIAL_SCAM")
            else:
                levels.add("SAFE")

    for n in (data.get("number_results") or []):
        if n.get("spam_category"):
            levels.add("POTENTIAL_SCAM")
        elif n.get("name"):
            levels.add("SAFE")

    cr = data.get("content_result")
    if cr and cr.get("category"):
        levels.add(cr["category"])

    for r in risk_priority:
        if r in levels:
            return r
    return "SAFE"


def build_embed(data: dict) -> discord.Embed:
    """Build a Discord embed from the n8n response in a technical list format."""
    if not data or not isinstance(data, dict):
        data = _empty_result()
    risk = determine_overall_risk(data)
    color = RISK_COLORS.get(risk, 0x95A5A6)

    embed = discord.Embed(
        title=f"Technical Analysis Result: {risk}",
        color=color,
        description="Raw API extracted properties:"
    )

    original = data.get("original_text", "")
    if original:
        embed.add_field(
            name="Original Extracted Text",
            value=original[:200] + ("..." if len(original) > 200 else ""),
            inline=False,
        )

    for u in (data.get("url_results") or []):
        score = u.get("score")
        if score is not None:
            value_lines = [
                f"`Score`: {score}/100",
                f"`Score Status`: {u.get('score_status')}",
                f"`Blacklisted`: {u.get('blacklisted')}",
                f"`Cached Result`: {u.get('cached')}",
                f"`Registration Created`: {u.get('registration_created')}",
                f"`Registrant Country`: {u.get('registrant_country')}",
                f"`Registrar Name`: {u.get('registrar_name')}",
                f"`SSL Valid`: {u.get('ssl_valid')}",
                f"`SSL Issuer`: {u.get('ssl_issuer')}",
                f"`Phishing Count`: {u.get('phishing_count', 0)}",
                f"`Threat Count`: {u.get('threat_count', 0)}",
                f"`Page Views`: {u.get('pageview')}",
                f"`Redirected URLs`: {', '.join(u.get('redirected_urls', [])) if u.get('redirected_urls') else 'None'}"
            ]
            value = "\n".join(value_lines)
        else:
            value = f"Query Failed (HTTP {u.get('http_status', '?')})"
        embed.add_field(name=f"🌐 URL: {u.get('domain', u.get('url', '?'))}", value=value, inline=False)

    for n in (data.get("number_results") or []):
        value_lines = [
            f"`Real Name`: {n.get('name')}",
            f"`Region`: {n.get('region')}",
            f"`Business Categories`: {', '.join(n.get('business_categories', []))}",
            f"`Spam Category`: {n.get('spam_category')}"
        ]
        embed.add_field(name=f"📞 Phone: {n.get('number', '?')}", value="\n".join(value_lines), inline=False)

    if not embed.fields and data.get("display_text"):
        embed.add_field(name="分析結果", value=data["display_text"][:1024], inline=False)

    if data.get("summary"):
        embed.set_footer(text=f"LLM 摘要: {data['summary']}")

    return embed


@bot.event
async def on_ready():
    log.info("Bot is ready: %s (ID: %s)", bot.user.name, bot.user.id)
    try:
        synced = await bot.tree.sync()
        log.info("Synced %d slash commands", len(synced))
    except Exception as e:
        log.error("Failed to sync commands: %s", e)


@bot.tree.command(name="check", description="分析訊息中的網址、電話是否為詐騙")
async def slash_check(interaction: discord.Interaction, text: str):
    """Slash command: /check <text>"""
    await interaction.response.defer(thinking=True)

    try:
        data = await call_n8n(text)
        embed = build_embed(data)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        log.exception("Error processing /check")
        await interaction.followup.send(f"分析時發生錯誤: {e}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Only respond when bot is mentioned or message starts with !check
    is_mentioned = bot.user in message.mentions
    is_command = message.content.startswith("!check")

    if not is_mentioned and not is_command:
        await bot.process_commands(message)
        return

    text = message.content
    if is_command:
        text = text[len("!check"):].strip()
    else:
        text = text.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()

    if not text:
        await message.reply("請提供要分析的文字。用法：`!check <訊息>` 或 `@bot <訊息>`")
        return

    async with message.channel.typing():
        try:
            data = await call_n8n(text)
            embed = build_embed(data)
            await message.reply(embed=embed)
        except Exception as e:
            log.exception("Error processing message")
            await message.reply(f"分析時發生錯誤: {e}")


@bot.command(name="check")
async def cmd_check(ctx: commands.Context, *, text: str = ""):
    """Prefix command: !check <text>"""
    # Handled by on_message for unified logic
    pass


def main():
    if not DISCORD_TOKEN:
        print("ERROR: DISCORD_BOT_TOKEN not set in .env")
        print("Please add your Discord bot token to .env:")
        print('  DISCORD_BOT_TOKEN=your-token-here')
        return

    log.info("Starting Anti-Fraud Discord Bot...")
    log.info("n8n Webhook URL: %s", N8N_WEBHOOK_URL)
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
