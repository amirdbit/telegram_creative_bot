import asyncio
import logging
import math
import os
import random

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ===== Logging =====
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ===== Conversation states =====
(
    BRAND,
    MARKET,
    LANGUAGE,
    MEDIA_TYPE,
    LENGTH,
    STYLE,
    GOAL,
    IDEA_MODE,
    FREE_IDEA,
    GENERATE,
) = range(10)


# ===== Helper: language mapping =====
LANGUAGE_OPTIONS = {
    "English": "EN",
    "Spanish - Argentina": "ES_AR",
    "Spanish - Peru": "ES_PE",
}


# ===== Start command =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "היי, אני creative_bot. בוא נבנה פרומפטים.\n\n"
        "קודם כל, מה שם הברנד? (לדוגמה: betsson, Premier Africa Sports)",
        reply_markup=ReplyKeyboardRemove(),
    )
    return BRAND


async def brand_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["brand"] = update.message.text.strip()
    await update.message.reply_text(
        "מעולה. באיזה מדינה או שוק אתה עובד? (לדוגמה: Argentina, South Africa)",
    )
    return MARKET


async def market_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["market"] = update.message.text.strip()

    keyboard = [["English"], ["Spanish - Argentina"], ["Spanish - Peru"]]
    await update.message.reply_text(
        "בחר שפת מותג עבור התסריט:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return LANGUAGE


async def language_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text.strip()
    lang_code = LANGUAGE_OPTIONS.get(choice, "EN")
    context.user_data["language"] = lang_code

    keyboard = [["VEO video"], ["Image"]]
    await update.message.reply_text(
        "מה סוג הקריאייטיב שאתה רוצה לייצר?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return MEDIA_TYPE


async def media_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    media = update.message.text.strip()
    context.user_data["media_type"] = "video" if "video" in media.lower() else "image"

    if context.user_data["media_type"] == "video":
        await update.message.reply_text(
            "מה האורך הכולל של הסרטון בשניות? (לדוגמה: 8, 12, 16)",
            reply_markup=ReplyKeyboardRemove(),
        )
        return LENGTH
    else:
        # For image we skip length
        context.user_data["length"] = None
        await update.message.reply_text(
            "איזה סגנון קריאייטיב אתה רוצה? (לדוגמה: UGC selfie, motion graphic, clean promo)",
        )
        return STYLE


async def length_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        total_length = int(text)
        if total_length <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("תכתוב מספר חיובי בשניות, לדוגמה 8 או 16.")
        return LENGTH

    context.user_data["length"] = total_length

    await update.message.reply_text(
        "איזה סגנון קריאייטיב אתה רוצה? (לדוגמה: UGC selfie, green screen, stadium POV)",
    )
    return STYLE


async def style_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["style"] = update.message.text.strip()

    await update.message.reply_text(
        "מה המטרה המרכזית? (לדוגמה: להגדיל הורדות, להסביר איך האפליקציה עובדת, להציג פרומו חדש)",
    )
    return GOAL


async def goal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["goal"] = update.message.text.strip()

    keyboard = [["רעיונות רנדומליים"], ["יש לי רעיון כללי"]]
    await update.message.reply_text(
        "רוצה שאני אביא 3 רעיונות שונים לגמרי, או שיש לך רעיון כללי לסרטון?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return IDEA_MODE


async def idea_mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text.strip()

    if "כללי" in choice:
        context.user_data["idea_mode"] = "free"
        await update.message.reply_text(
            "ספר לי בקצרה את הרעיון הכללי לסרטון או לתמונה.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return FREE_IDEA

    context.user_data["idea_mode"] = "random"
    context.user_data["base_idea"] = None

    return await generate_handler(update, context)


async def free_idea_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["base_idea"] = update.message.text.strip()
    return await generate_handler(update, context)


# ===== Script text by language =====
def build_script_text(brand: str, market: str, lang_code: str, idea: str) -> str:
    code = lang_code.upper()

    if code in ("ES_AR", "ES-AR", "ES"):
        return f"""
[HOOK]
"Desde que uso {brand}, seguir el fútbol en {market} es muchísimo más fácil."

[BODY]
"Abro la app, veo marcadores en vivo, próximos partidos y mis jugadas en segundos.
Todo en un solo lugar, rápido y sin complicaciones."

[CTA]
"Descarga {brand} ahora mismo y pruébala gratis."
Idea principal del video: {idea}
        """.strip()

    if code in ("ES_PE", "ES-PE"):
        return f"""
[HOOK]
"Desde que tengo {brand}, seguir el fútbol en {market} es mucho más simple."

[BODY]
"Reviso resultados en vivo, próximos partidos y mis apuestas en cuestión de segundos.
Todo en un solo lugar, rápido y sin complicaciones."

[CTA]
"Descarga {brand} hoy mismo y pruébala gratis."
Idea principal del video: {idea}
        """.strip()

    if code == "HE":
        return f"""
[HOOK]
"מאז שהתחלתי להשתמש ב {brand}, יותר קל לי לעקוב אחרי הכדורגל ב {market}."

[BODY]
"אני פותח את האפליקציה, רואה תוצאות חיות, משחקים קרובים ומה שמעניין אותי בכמה שניות.
הכל במקום אחד, מהר ובלי כאב ראש."

[CTA]
"תוריד את {brand} עכשיו ותנסה בחינם."
רעיון הסרטון: {idea}
        """.strip()

    # Default English
    return f"""
[HOOK]
"Since I started using {brand}, following football in {market} became much easier."

[BODY]
"I open the app, check live scores, fixtures and my picks in seconds.
Everything is in one place, fast and simple."

[CTA]
"Download {brand} today and try it for free."
Main idea of the video: {idea}
    """.strip()


# ===== Idea generation =====
def generate_ideas(data: dict, base_idea: str | None, num: int = 3) -> list[str]:
    brand = data["brand"]
    market = data["market"]
    media_type = data["media_type"]

    ideas = []

    if base_idea:
        # Variations around user idea
        templates = [
            "POV של משתמש שכבר מכור ל {brand}, מספר בקצרה על {base}",
            "קיצר, חבר מסביר לחבר על {brand} תוך כדי משחק על המסך - {base}",
            "סצנה יומיומית ב {market} שמובילה ברוגע להורדת {brand} - {base}",
        ]
        for i in range(num):
            t = random.choice(templates)
            ideas.append(
                t.format(
                    brand=brand,
                    market=market,
                    base=base_idea,
                )
            )
    else:
        # Fully random concepts
        if media_type == "video":
            pool = [
                "אוהד בודק תוצאות בזמן העבודה וקולט שהוא תמיד מקבל התראות לפני כולם עם האפליקציה",
                "חבורה של חברים בחדר צפייה, אחד מהם מנהל את כל ההימורים שלו מהטלפון בקלות",
                "פתיחת יום של אוהד: קפה, טלפון, לוח משחקים באפליקציה ומעקב אחרי הטיקר של המשחקים",
                "נהג מונית בפקק שומר על קשר עם המשחקים דרך האפליקציה בלי לפספס לקוחות",
                "סטודנט לומד בספריה ומציץ מדי פעם באפליקציה כדי לעקוב אחרי הטופס שלו",
            ]
        else:
            pool = [
                "תמונה של מסך טלפון עם לוח משחקים מלא ואוהד מחייך ברקע",
                "קלוז אפ על יד שמחזיקה טלפון עם תוצאות חיות ואפקט ניאון סביב המספרים",
                "קולאז של אייקוני ליגות גדולות עם לוגו של האפליקציה במרכז",
                "רקע של אצטדיון חשוך עם מסך טלפון שמאיר במרכז ומציג את הפרומו",
            ]

        random.shuffle(pool)
        ideas = pool[:num]

    return ideas


# ===== Prompt builders =====
def build_veo_prompt(data: dict, idea: str, variation_index: int) -> str:
    brand = data["brand"]
    market = data["market"]
    style = data["style"]
    goal = data["goal"]
    total_length = data["length"]
    lang_code = data["language"]

    script_text = build_script_text(brand, market, lang_code, idea)

    # Split into segments of max 8 seconds
    segment_length = 8
    num_segments = max(1, math.ceil(total_length / segment_length))

    header = f"""
Google VEO video generation prompt.
Brand: "{brand}"
Market: "{market}"
Variation {variation_index}
Total length: {total_length} seconds
Creative style: {style}
Objective: {goal}

Concept:
{idea}

General rules:
- Vertical 9:16 UGC friendly video.
- Natural handheld feeling.
- Environment, outfits and phone usage must fit {market}.
- Never show the phone screen directly to camera.
- Dialog must be written in the correct language for this market.
- Dialog must fit inside the timing of each segment.

Example script in target language:
{script_text}
    """.strip()

    segments_text = []

    for seg in range(num_segments):
        start_t = seg * segment_length
        end_t = min(total_length, (seg + 1) * segment_length)
        seg_len = end_t - start_t

        segments_text.append(
            f"""
Segment {seg + 1} - from {start_t} to {end_t} seconds (about {seg_len} seconds):

1. Describe camera framing, movement and environment in detail.
2. Describe actor actions and expressions.
3. Write the exact spoken dialog for this segment in the target language.
4. Keep the dialog short and realistic so it comfortably fits inside {seg_len} seconds.
5. Do not mention "voiceover" or "scene description" inside the dialog.
            """.strip()
        )

    full = header + "\n\n" + "\n\n".join(segments_text)
    return full


def build_image_prompt(data: dict, idea: str, variation_index: int) -> str:
    brand = data["brand"]
    market = data["market"]
    style = data["style"]
    goal = data["goal"]
    lang_code = data["language"]

    script_text = build_script_text(brand, market, lang_code, idea)

    prompt = f"""
Image generation prompt.
Brand: "{brand}"
Market: "{market}"
Variation {variation_index}
Creative style: {style}
Objective: {goal}

Concept:
{idea}

Visual rules:
- Design must look native for {market}.
- Use colors and typography that fit a modern sports or betting app.
- Do not use real club logos or real player faces.
- Make the brand name and main CTA big and readable.

Text language:
- All on-image text must be in the correct language for this market.
- Use short and punchy copy that matches this example tone:

Example copy in target language:
{script_text}

Now describe:
1. The full scene: background, foreground, props, lighting.
2. The main subject or focal point.
3. The exact on-image text: headline and CTA in the target language.
    """.strip()

    return prompt


# ===== Generate handler =====
async def generate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    data = context.user_data
    brand = data["brand"]
    market = data["market"]
    media_type = data["media_type"]
    lang_code = data["language"]

    base_idea = data.get("base_idea")
    ideas = generate_ideas(data, base_idea, num=3)

    prompts = []
    for idx, idea in enumerate(ideas, start=1):
        if media_type == "video":
            p = build_veo_prompt(data, idea, idx)
        else:
            p = build_image_prompt(data, idea, idx)
        prompts.append(p)

    header = (
        f"סיימתי לבנות פרומפטים עבור הברנד {brand} בשוק {market} "
        f"ובשפה {lang_code}. קיבלת 3 וריאציות שונות.\n\n"
        "מומלץ להעתיק כל וריאציה בנפרד לכלי היצירה."
    )

    await update.message.reply_text(header)

    for idx, p in enumerate(prompts, start=1):
        # כדי לא להיתקע על הודעות ארוכות מדי, אפשר לפצל אם תרצה.
        await update.message.reply_text(f"וריאציה {idx}:\n\n{p}")

    await update.message.reply_text(
        "אם תרצה להשתמש באותן הגדרות ולקבל רעיונות חדשים לגמרי, שלח /again.\n"
        "כדי להתחיל הגדרות חדשות, שלח /start.",
    )

    return ConversationHandler.END


# ===== /again - reuse last settings =====
async def again(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.get("brand"):
        await update.message.reply_text("אין הגדרות קודמות בזיכרון. שלח /start כדי להתחיל מחדש.")
        return

    # כשעושים /again, נביא רעיונות רנדומליים חדשים עם אותן הגדרות
    data = context.user_data.copy()
    data["idea_mode"] = "random"
    data["base_idea"] = None

    brand = data["brand"]
    market = data["market"]

    await update.message.reply_text(
        f"מייצר עכשיו רעיונות ופרומפטים חדשים עבור {brand} ב {market} על בסיס אותן הגדרות...",
    )

    ideas = generate_ideas(data, None, num=3)

    prompts = []
    for idx, idea in enumerate(ideas, start=1):
        if data["media_type"] == "video":
            p = build_veo_prompt(data, idea, idx)
        else:
            p = build_image_prompt(data, idea, idx)
        prompts.append(p)

    for idx, p in enumerate(prompts, start=1):
        await update.message.reply_text(f"וריאציה {idx}:\n\n{p}")


# ===== /cancel =====
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("בוטל. אם תרצה להתחיל מחדש שלח /start.")
    return ConversationHandler.END


# ===== Main =====
async def main() -> None:
    token = os.environ.get("TOKEN")
    if not token:
        raise RuntimeError("You must set the TOKEN environment variable with your bot token")

    application = ApplicationBuilder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, brand_handler)],
            MARKET: [MessageHandler(filters.TEXT & ~filters.COMMAND, market_handler)],
            LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, language_handler)],
            MEDIA_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, media_type_handler)],
            LENGTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, length_handler)],
            STYLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, style_handler)],
            GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_handler)],
            IDEA_MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, idea_mode_handler)],
            FREE_IDEA: [MessageHandler(filters.TEXT & ~filters.COMMAND, free_idea_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("again", again))

    logger.info("Bot is starting with polling...")
    await application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    asyncio.run(main())
