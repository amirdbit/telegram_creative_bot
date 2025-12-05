import os
import random
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove

TOKEN = os.getenv("TOKEN")

# Conversation states
BRAND, MARKET, FORMAT, STYLE, IDEA, ACTOR, LENGTH, LANGUAGE, VARIATIONS = range(9)


# -------------------------------------------------
# עזר – יצירת רעיונות (קונספטים) לפי מצב
# -------------------------------------------------
def generate_concepts(session: dict, count: int):
    """
    מחזיר רשימת קונספטים (title + description) באורך count
    לפי:
    - format (veo / whisk)
    - idea_mode (auto/custom)
    - idea_text (אם יש)
    """
    fmt = session.get("format", "whisk")
    mode = session.get("idea_mode", "auto")
    idea_text = (session.get("idea_text") or "").strip()

    concepts: list[dict] = []

    # אם המשתמש נתן רעיון כללי – נשתמש בו כבסיס, אבל נייצר כמה וריאציות
    if mode == "custom" and idea_text:
        for i in range(count):
            concepts.append(
                {
                    "title": f"Custom concept variation {i + 1}",
                    "description": idea_text,
                }
            )
        return concepts

    # אחרת – נבחר רעיונות מובנים לפי סוג הקריאייטיב
    if fmt == "veo":
        pool = [
            {
                "title": "Notification moment",
                "description": "User gets a push notification from the app during work / studies and reacts in real time.",
            },
            {
                "title": "Friends at the bar",
                "description": "Group of friends watching football together, one of them shows the app and explains why he uses it.",
            },
            {
                "title": "Halftime check",
                "description": "User checks live scores and bets during halftime, showing how quick and easy it is.",
            },
            {
                "title": "On the move",
                "description": "User in taxi / bus quickly checks matches and scores on weak network, app works smoothly.",
            },
            {
                "title": "Morning routine",
                "description": "User checks fixtures and odds as part of their morning routine before leaving home.",
            },
        ]
    else:
        # whisk / תמונה
        pool = [
            {
                "title": "Big win reaction",
                "description": "User celebrating a big win, with subtle phone usage and strong brand/CTA.",
            },
            {
                "title": "Match day focus",
                "description": "User preparing for a big match, checking fixtures and odds inside the app.",
            },
            {
                "title": "Multi-league overview",
                "description": "Visual focus on different leagues / matches being followed inside the app.",
            },
            {
                "title": "Chill at home",
                "description": "Relaxed user on the couch checking live scores and bets on their phone.",
            },
            {
                "title": "Office break",
                "description": "User taking a short break at the office to check scores and place a quick bet.",
            },
        ]

    random.shuffle(pool)
    return pool[:count]


# -------------------------------------------------
# עזר – הפעלת כל התהליך בפועל
# -------------------------------------------------
async def run_generation(update: Update, context: ContextTypes.DEFAULT_TYPE, session: dict):
    fmt = session.get("format", "whisk")
    num = int(session.get("variations", 1) or 1)
    if num < 1:
        num = 1
    if num > 3:
        num = 3

    session = dict(session)
    session["variations"] = num

    concepts = generate_concepts(session, num)

    if fmt == "veo":
        # וידאו + reference image
        for i in range(num):
            concept = concepts[i]
            variant_data = dict(session)
            variant_data["variant_index"] = i + 1
            variant_data["concept"] = concept

            whisk_ref = build_whisk_reference_prompt(variant_data)
            veo_prompt = build_veo_prompt(variant_data)

            await update.message.reply_text(
                f"🟩 וריאציה {i + 1} – פרומפט Whisk לפריים ראשון (reference):\n\n{whisk_ref}"
            )
            await update.message.reply_text(
                f"🎥 וריאציה {i + 1} – פרומפט וידאו ל-VEO:\n\n{veo_prompt}"
            )

        await update.message.reply_text(
            "📌 תזכורת: קודם תייצר את התמונות ב-Whisk, ואז תעלה כל תמונה כ-Image Input המתאים ב-VEO."
        )

    else:
        # תמונות בלבד – Whisk
        for i in range(num):
            concept = concepts[i]
            variant_data = dict(session)
            variant_data["variant_index"] = i + 1
            variant_data["concept"] = concept

            whisk_prompt = build_whisk_prompt(variant_data)
            await update.message.reply_text(
                f"🖼️ וריאציה {i + 1} – פרומפט Whisk:\n\n{whisk_prompt}"
            )

    await update.message.reply_text("לקריאייטיב חדש – /start")


# -------------------------------------------------
# /start – כולל עבודה עם הגדרות אחרונות
# -------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("last_session"):
        reply_keyboard = [
            ["📂 להשתמש בהגדרות האחרונות", "✨ להתחיל קריאייטיב חדש"],
        ]
        context.user_data["awaiting_entry_choice"] = True

        await update.message.reply_text(
            "היי 👋\nיש לי את הסט האחרון שעבדת איתו.\nמה תרצה לעשות?",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
        )
        return BRAND

    await update.message.reply_text(
        "היי 👋\nבוא נייצר קריאייטיב.\n\n"
        "מה שם הברנד? (לדוגמה: PAS, Betsson, AdmiralBet)",
        reply_markup=ReplyKeyboardRemove(),
    )
    return BRAND


async def brand_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if context.user_data.get("awaiting_entry_choice"):
        context.user_data["awaiting_entry_choice"] = False

        if text.startswith("📂"):
            last_session = context.user_data.get("last_session")
            if not last_session:
                await update.message.reply_text(
                    "לא מצאתי הגדרות אחרונות. נתחיל קריאייטיב חדש.\n\n"
                    "מה שם הברנד?",
                    reply_markup=ReplyKeyboardRemove(),
                )
                return BRAND

            await update.message.reply_text(
                "מעולה, משתמש באותן הגדרות – אבל מייצר רעיונות חדשים. שנייה…",
                reply_markup=ReplyKeyboardRemove(),
            )
            await run_generation(update, context, last_session)
            return ConversationHandler.END

        # התחלה מאפס
        await update.message.reply_text(
            "סבבה, נתחיל מחדש.\n\nמה שם הברנד?",
            reply_markup=ReplyKeyboardRemove(),
        )
        return BRAND

    # זרימה רגילה – קיבלנו brand
    context.user_data["brand"] = text
    await update.message.reply_text(
        "לאיזה מדינה או שוק? (לדוגמה: South Africa, Malawi, Argentina)"
    )
    return MARKET


async def market_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["market"] = update.message.text.strip()

    reply_keyboard = [["VEO - Video", "Whisk - Image"]]
    await update.message.reply_text(
        "מה סוג הקריאייטיב?",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
    )
    return FORMAT


async def format_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "VEO" in text:
        context.user_data["format"] = "veo"
    else:
        context.user_data["format"] = "whisk"

    reply_keyboard = [
        ["UGC selfie", "UGC filmed by friend"],
        ["Motion graphic", "Green screen"],
        ["Free text / custom"],
    ]
    await update.message.reply_text(
        "מה הסגנון (סטייל) של הקריאייטיב?",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
    )
    return STYLE


async def style_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["style"] = update.message.text.strip()

    reply_keyboard = [
        ["🎲 תן לי רעיונות", "✍️ יש לי רעיון כללי (מלל חופשי)"],
    ]
    await update.message.reply_text(
        "עכשיו לגבי הרעיון של הקריאייטיב:\n"
        "אפשר או שאני אציע כמה רעיונות שונים, או שתכתוב רעיון כללי שלך.\n"
        "מה אתה מעדיף?",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
    )
    return IDEA


async def idea_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # אם אנחנו מחכים לרעיון חופשי
    if context.user_data.get("waiting_custom_idea"):
        context.user_data["waiting_custom_idea"] = False
        context.user_data["idea_mode"] = "custom"
        context.user_data["idea_text"] = text
    else:
        # בחירה ראשונית
        if text.startswith("🎲"):
            context.user_data["idea_mode"] = "auto"
            context.user_data["idea_text"] = ""
        elif text.startswith("✍️"):
            context.user_data["waiting_custom_idea"] = True
            await update.message.reply_text(
                "תכתוב לי במלל חופשי את הרעיון הכללי של הסרטון/תמונה.\n"
                "לדוגמה: \"התראה שקופצת בזמן העבודה\", \"חברים בבר\", \"לפני/אחרי (בלי להגיד before/after)\" וכו׳.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return IDEA
        else:
            # אם המשתמש ענה משהו אחר בטעות – נחזיר לשאלה
            reply_keyboard = [
                ["🎲 תן לי רעיונות", "✍️ יש לי רעיון כללי (מלל חופשי)"],
            ]
            await update.message.reply_text(
                "לא הבנתי, תבחר באחת האופציות או תכתוב רעיון חופשי אחרי שתבחר ✍️:",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard,
                    one_time_keyboard=True,
                    resize_keyboard=True,
                ),
            )
            return IDEA

    # אחרי שיש מצב רעיון – ממשיכים לבחירת שחקן
    reply_keyboard = [
        ["Male 18-25 energetic", "Male 25-35 calm"],
        ["Female 18-25 energetic", "Female 25-35 calm"],
        ["Other - I will describe"],
    ]
    await update.message.reply_text(
        "תבחר סוג שחקן (או Other ואז תתאר חופשי):",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
    )
    return ACTOR


async def actor_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if context.user_data.get("waiting_custom_actor"):
        context.user_data["waiting_custom_actor"] = False
        context.user_data["actor"] = text

    elif text.startswith("Other"):
        context.user_data["waiting_custom_actor"] = True
        await update.message.reply_text(
            "תתאר במדויק את השחקן (גיל, מגדר, וייב, לדוגמה:\n"
            '"young South African male, early 20s, funny and energetic").',
            reply_markup=ReplyKeyboardRemove(),
        )
        return ACTOR

    else:
        context.user_data["actor"] = text

    if context.user_data.get("format") == "veo":
        await update.message.reply_text(
            "מה אורך הווידאו בשניות? (לדוגמה: 8, 16, 24)",
            reply_markup=ReplyKeyboardRemove(),
        )
        return LENGTH
    else:
        market = context.user_data.get("market", "")
        native_code, native_label = infer_native_language(market)
        reply_keyboard = [["Native language", "English"]]
        await update.message.reply_text(
            f"הטקסט של התמונה יהיה ב:\n"
            f"- שפת המקור של {market} ({native_label})\n"
            f"- או English?",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
        )
        return LANGUAGE


async def length_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        length = int(text)
    except ValueError:
        await update.message.reply_text("תכתוב מספר שניות תקין, לדוגמה 8.")
        return LENGTH

    context.user_data["length"] = length

    market = context.user_data.get("market", "")
    native_code, native_label = infer_native_language(market)

    reply_keyboard = [["Native language", "English"]]
    await update.message.reply_text(
        f"הטקסט של הסרטון יהיה ב:\n"
        f"- שפת המקור של {market} ({native_label})\n"
        f"- או English?",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
    )
    return LANGUAGE


async def language_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()

    market = context.user_data.get("market", "")
    native_code, native_label = infer_native_language(market)

    if "native" in text:
        lang_code = native_code
    elif "english" in text:
        lang_code = "EN"
    else:
        await update.message.reply_text(
            "נא לבחור: Native language או English."
        )
        return LANGUAGE

    context.user_data["language"] = lang_code

    await update.message.reply_text(
        f"אחלה, נשתמש בשפה: {lang_code}.\n"
        "כמה וריאציות אתה רוצה? (1–3)",
        reply_markup=ReplyKeyboardRemove(),
    )
    return VARIATIONS


async def variations_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        num = int(text)
    except ValueError:
        await update.message.reply_text("תכתוב מספר בין 1 ל-3.")
        return VARIATIONS

    if num < 1:
        num = 1
    if num > 3:
        num = 3

    context.user_data["variations"] = num

    # נשמור את הסשן האחרון – בלי last_session עצמו
    last_session = {
        k: v
        for k, v in context.user_data.items()
        if k != "last_session"
    }
    context.user_data["last_session"] = last_session

    await run_generation(update, context, last_session)
    return ConversationHandler.END


# -------------------------------------------------
# זיהוי שפה לפי שוק
# -------------------------------------------------
def infer_native_language(market: str) -> tuple[str, str]:
    m = (market or "").strip().lower()

    if "argentina" in m:
        return "ES", "Spanish for Argentina"
    if "peru" in m:
        return "ES", "Spanish for Peru"
    if "israel" in m or "ישראל" in m:
        return "HE", "Hebrew"
    if "south africa" in m:
        return "EN", "English for South Africa"
    if "malawi" in m:
        return "EN", "English for Malawi"
    if "zambia" in m:
        return "EN", "English for Zambia"

    return "EN", "English"


# -------------------------------------------------
# בניית פרומפטים
# -------------------------------------------------
def build_whisk_prompt(data: dict) -> str:
    brand = data["brand"]
    market = data["market"]
    style = data["style"]
    actor = data.get("actor", f"young football fan from {market}")
    variant = data.get("variant_index")
    concept = data.get("concept", {})
    idea_title = concept.get("title", "Generic performance concept")
    idea_desc = concept.get("description", "")

    variant_label = f"Variation {variant}" if variant else "Single version"

    prompt = f"""
Static ad image for Whisk.
Brand: "{brand}"
Market: "{market}"
{variant_label}
Creative style: {style}

Concept:
- Title: {idea_title}
- Description: {idea_desc}

Scene:
- Show {actor} in a setting that feels natural for {market}, matching this concept.
- Vertical or 4:5 mobile friendly composition.
- The person may hold a phone, but if the phone appears the screen must NOT face the camera.
- Background should be clean but with enough context (home, street, office, taxi etc).

Branding:
- Use {brand} colors strongly in UI elements, accents or clothing.
- Include clear brand name and a big readable CTA such as "Free Download" or "Sign up now".

Restrictions:
- Do not use real football teams or real player faces.
- Instructions are for the generator only and must NOT appear as visible text.
""".strip()

    return prompt


def build_whisk_reference_prompt(data: dict) -> str:
    brand = data["brand"]
    market = data["market"]
    style = data["style"]
    actor = data.get("actor", f"young football fan from {market}")
    variant = data.get("variant_index")
    concept = data.get("concept", {})
    idea_title = concept.get("title", "Generic performance video concept")
    idea_desc = concept.get("description", "")

    variant_label = f"Variation {variant}" if variant else "Single version"

    prompt = f"""
Reference image for the FIRST FRAME of a Google VEO video.
Brand: "{brand}"
Market: "{market}"
{variant_label}
Video creative style: {style}

Concept:
- Title: {idea_title}
- Description: {idea_desc}

Purpose:
- This is NOT an ad layout. This is a clean still frame that looks like frame 1 of a UGC vertical video.

Visual:
- Show {actor}, realistic and natural, matching the concept above.
- Vertical 9:16 framing, chest-up or waist-up.
- Environment should clearly match {market} (home, street, office or taxi).
- Actor holds a phone, but the phone screen is NOT visible to the camera.
- Lighting should be soft and realistic.
- No text, no logos, no CTA, no graphic overlays.

This image must look exactly like the first frame of a real UGC TikTok style video.
""".strip()

    return prompt


def build_veo_prompt(data: dict) -> str:
    brand = data["brand"]
    market = data["market"]
    style = data["style"]
    length = data.get("length", 8)
    lang = data["language"]
    actor = data.get("actor", f"young football fan from {market}")
    variant = data.get("variant_index")
    concept = data.get("concept", {})
    idea_title = concept.get("title", "Performance video concept")
    idea_desc = concept.get("description", "")

    variant_label = f"Variation {variant}" if variant else "Single version"

    prompt = f"""
Google VEO video generation prompt.
Brand: "{brand}"
Market: "{market}"
{variant_label}
Length: {length} seconds
Creative style: {style}

Concept:
- Title: {idea_title}
- Description: {idea_desc}
- This variation should use the same overall idea but with different dialog, actions and camera flow
  compared to other variations.

Reference image usage:
- Use the provided reference image as frame 1.
- Frame 1 must match the reference image exactly:
  same actor style, clothing, lighting, background and camera angle.
- Do NOT redesign the actor. Continue naturally from the still into motion.

Scene and camera:
- Vertical 9:16 UGC style with slight handheld motion.
- Show {actor} as the main subject.
- Environment should match {market} and the reference image.
- The actor holds a phone but the screen is NEVER shown to the camera.

Voice:
- Natural {lang} speech for {market}.
- Young voice, medium energy, conversational, not over-acted.
- Dialog must comfortably fit inside {length} seconds.

Now create:
1. A second-by-second breakdown of camera and actor actions for the full {length} seconds.
2. Natural movement from the still reference frame into the first motion frames.
3. Final spoken dialog in {lang} that fits the concept and timing.
4. Do NOT include technical words like "voiceover" or "scene description" inside the dialog.
""".strip()

    return prompt


# -------------------------------------------------
# /last – שימוש בהגדרות האחרונות, עם רעיונות חדשים
# -------------------------------------------------
async def last_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    last_session = context.user_data.get("last_session")
    if not last_session:
        await update.message.reply_text(
            "אין עדיין הגדרות אחרונות. תתחיל עם /start פעם אחת 😊"
        )
        return

    await update.message.reply_text(
        "משתמש באותן הגדרות – ומגריל רעיונות חדשים…",
        reply_markup=ReplyKeyboardRemove(),
    )
    await run_generation(update, context, last_session)


# -------------------------------------------------
# /cancel
# -------------------------------------------------
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ביטלתי את התהליך. אפשר להתחיל מחדש עם /start.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# -------------------------------------------------
# main
# -------------------------------------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), CommandHandler("new", start)],
        states={
            BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, brand_handler)],
            MARKET: [MessageHandler(filters.TEXT & ~filters.COMMAND, market_handler)],
            FORMAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, format_handler)],
            STYLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, style_handler)],
            IDEA: [MessageHandler(filters.TEXT & ~filters.COMMAND, idea_handler)],
            ACTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, actor_handler)],
            LENGTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, length_handler)],
            LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, language_handler)],
            VARIATIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, variations_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("last", last_command))

    app.run_polling()


if __name__ == "__main__":
    main()
