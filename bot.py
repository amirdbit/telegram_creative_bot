import os
import logging
import math
from typing import Dict, Any

from telegram import (
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ----------------- CONFIG & LOGGING -----------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# אל תכתוב את הטוקן בקוד. ברנדר שמים אותו כ TOKEN ב Environment.
TOKEN = os.getenv("TOKEN")

# ----------------- CONVERSATION STATES -----------------

ASK_BRAND, ASK_MARKET, ASK_ASSET_TYPE, ASK_DURATION, ASK_LANGUAGE, ASK_IDEA_MODE, ASK_CUSTOM_IDEA = range(
    7
)


# ----------------- HELPERS -----------------

def split_to_segments(duration_sec: int) -> int:
    """VEO עובד עד 8 שניות לפרומפט. מחזיר כמה פרומפטים צריך."""
    return max(1, math.ceil(duration_sec / 8))


def generate_random_ideas(asset_type: str, market: str) -> Dict[str, str]:
    """
    מחזיר שלושה רעיונות בסיסיים שונים לפי סוג הנכס והמדינה.
    זה רק בסיס, מחר נוכל להעמיק.
    """
    asset_type = asset_type.lower()

    if asset_type == "video":
        return {
            "Idea 1": f"Match day reaction in {market} - fan checking the app during a key moment.",
            "Idea 2": f"Halftime routine in {market} - how the app keeps the fan updated and engaged.",
            "Idea 3": f"On the go in {market} - user checking live scores while commuting or at work.",
        }
    else:
        # image
        return {
            "Idea 1": f"Close up of the phone in {market} with key features highlighted around it.",
            "Idea 2": f"Fan celebrating with subtle app UI elements integrated in the background.",
            "Idea 3": f"Simple hero shot of the phone with brand colors and strong CTA for {market}.",
        }


def build_veo_prompt(
    brand: str,
    market: str,
    asset_type: str,
    duration: int,
    language_note: str,
    idea_title: str,
    idea_description: str,
) -> str:
    """
    בונה פרומפט אחד ל VEO.
    הטקסט עצמו באנגלית, אבל כולל הנחיה לשפה של המותג.
    """
    segments = split_to_segments(duration)
    creative_style = "UGC selfie" if asset_type.lower() == "video" else "Static image"

    header = f"{brand} - VEO {asset_type} prompt ({duration} seconds)\n"
    header += f"Market: {market}\n"
    header += f"Creative style: {creative_style}\n"
    header += f"Brand language: {language_note}\n"
    header += f"Idea: {idea_title}\n\n"

    if asset_type.lower() == "video":
        body = (
            "Concept:\n"
            f"- {idea_description}\n\n"
            "Voice and language:\n"
            f"- All dialog, voiceover and on screen text must be in: {language_note}.\n"
            "- Natural, conversational tone. No Hebrew. No robotic phrasing.\n\n"
        )

        body += "Structure:\n"
        if segments == 1:
            body += "- Create one 8 second video prompt for Google VEO.\n"
        else:
            body += f"- Create {segments} separate VEO prompts. Each prompt is up to 8 seconds.\n"
            for i in range(1, segments + 1):
                body += f"  Prompt {i}: Describe the exact shot, actions and dialog for seconds {(i - 1) * 8 + 1} to {min(i * 8, duration)}.\n"
        body += (
            "\nImportant rules:\n"
            "- The phone screen is never shown directly to the camera unless I say otherwise.\n"
            "- Keep the same actor, outfit and location between all prompts.\n"
            "- Do not use technical words like 'voiceover' or 'scene description' in the dialog.\n"
        )
    else:
        # image
        body = (
            "Concept:\n"
            f"- {idea_description}\n\n"
            "Language:\n"
            f"- Any visible text in the image must be in: {language_note}.\n\n"
            "Composition:\n"
            "- 9:16 mobile first layout.\n"
            "- Strong focus on the brand and CTA, clean and readable.\n"
            "- No real teams or real player faces. Use generic sports visuals only.\n"
        )

    return header + body


# ----------------- HANDLERS -----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "היי, אני בוט שמייצר פרומפטים ל Google VEO.\n"
        "נעבור כמה שלבים קצרים ואז אוציא לך 3 וריאציות שונות.\n\n"
        "קודם כל - מה שם המותג? (לדוגמה: Premier Africa Sports / Betsson וכו')"
    )
    return ASK_BRAND


async def ask_market(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["brand"] = update.message.text.strip()
    await update.message.reply_text(
        "מעולה.\nלאיזה שוק המודעה מיועדת? (לדוגמה: South Africa / Argentina / Italy)"
    )
    return ASK_MARKET


async def ask_asset_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["market"] = update.message.text.strip()
    await update.message.reply_text(
        "סוג הקריאייטיב:\n"
        "כתוב 'video' לסרטון VEO או 'image' לתמונה סטטית."
    )
    return ASK_ASSET_TYPE


async def ask_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    asset_type = update.message.text.strip().lower()
    if asset_type not in {"video", "image"}:
        await update.message.reply_text("תכתוב בבקשה רק 'video' או 'image'.")
        return ASK_ASSET_TYPE

    context.user_data["asset_type"] = asset_type

    if asset_type == "video":
        await update.message.reply_text(
            "מה האורך הכולל של הסרטון בשניות? (לדוגמה: 8, 16, 24)"
        )
    else:
        await update.message.reply_text(
            "לתמונה אין אורך, אבל תכתוב '10' כדי להמשיך (זו רק דרישה טכנית של הבוט)."
        )
    return ASK_DURATION


async def ask_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        duration = int(update.message.text.strip())
        if duration <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("תכתוב מספר שניות חיובי, לדוגמה 8, 16, 24.")
        return ASK_DURATION

    context.user_data["duration"] = duration
    await update.message.reply_text(
        "באיזו שפה הדיאלוג והטקסט של המותג?\n"
        "לדוגמה: 'Neutral English', 'Latin American Spanish', 'South African English'."
    )
    return ASK_LANGUAGE


async def ask_idea_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["language_note"] = update.message.text.strip()
    await update.message.reply_text(
        "עכשיו לגבי הרעיון:\n"
        "- אם אתה רוצה שאני אציע רעיונות - תכתוב 'random'.\n"
        "- אם יש לך כיוון כללי משלך - תכתוב 'custom'."
    )
    return ASK_IDEA_MODE


async def ask_custom_idea(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    mode = update.message.text.strip().lower()
    if mode not in {"random", "custom"}:
        await update.message.reply_text("תכתוב רק 'random' או 'custom'.")
        return ASK_IDEA_MODE

    context.user_data["idea_mode"] = mode

    if mode == "random":
        # יש לנו כבר את כל מה שצריך - נייצר רעיונות
        await generate_prompts(update, context)
        return ConversationHandler.END

    await update.message.reply_text(
        "תתאר לי במשפט או שניים את הרעיון הכללי של הסרטון/תמונה.\n"
        "לדוגמה: 'Fan in Argentina checking scores during halftime with friends at a bar'."
    )
    return ASK_CUSTOM_IDEA


async def finish_with_custom_idea(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["custom_idea"] = update.message.text.strip()
    await generate_prompts(update, context)
    return ConversationHandler.END


async def generate_prompts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data: Dict[str, Any] = context.user_data

    brand = data.get("brand", "Brand")
    market = data.get("market", "Market")
    asset_type = data.get("asset_type", "video")
    duration = int(data.get("duration", 16))
    language_note = data.get("language_note", "Neutral English")

    if data.get("idea_mode") == "custom":
        base_ideas = {
            "Idea 1": data.get("custom_idea", ""),
            "Idea 2": data.get("custom_idea", "") + " - alternative camera angle and slightly different pacing.",
            "Idea 3": data.get("custom_idea", "") + " - same core message but with a different location or moment of the day.",
        }
    else:
        base_ideas = generate_random_ideas(asset_type, market)

    await update.message.reply_text(
        "מעבד את המידע ומייצר 3 וריאציות שונות...\n"
        "שימו לב: כל הווריאציות כתובות באנגלית ומכוונות לשפה שביקשת עבור המותג."
    )

    for title, idea_text in base_ideas.items():
        prompt_text = build_veo_prompt(
            brand=brand,
            market=market,
            asset_type=asset_type,
            duration=duration,
            language_note=language_note,
            idea_title=title,
            idea_description=idea_text,
        )

        # נשלח כל וריאציה בהודעה נפרדת כדי שיהיה נוח להעתיק
        await update.message.reply_text(f"------\n{prompt_text}")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("בוט הופסק. כשתרצה להתחיל מחדש תכתוב /start.")
    return ConversationHandler.END


# ----------------- MAIN -----------------

def main() -> None:
    if not TOKEN:
        raise RuntimeError(
            "TOKEN is not set. In Render, go to Environment and add variable named TOKEN with your bot token."
        )

    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_market)],
            ASK_MARKET: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_asset_type)],
            ASK_ASSET_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_duration)],
            ASK_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_language)],
            ASK_LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_idea_mode)],
            ASK_IDEA_MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_custom_idea)],
            ASK_CUSTOM_IDEA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, finish_with_custom_idea)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("cancel", cancel))

    # שורת הריצה היחידה - ללא asyncio.run וללא main async
    application.run_polling()


if __name__ == "__main__":
    main()
