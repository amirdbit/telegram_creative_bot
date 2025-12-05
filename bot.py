import os
import math
import random

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ===== Conversation states =====
(
    BRAND,
    MARKET,
    FORMAT,
    STYLE,
    GOAL,
    ACTOR,
    LENGTH,
    LANGUAGE,
    IDEA_MODE,
    IDEA_TEXT,
    VARIATIONS,
) = range(11)


# ===== Helpers =====

def infer_native_language(market: str) -> tuple[str, str]:
    """Detect base language from market name."""
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


def compute_segments(length: int) -> list[int]:
    """
    מחלק אורך וידאו (שניות) למקטעים של עד 8 שניות.
    מחזיר רשימה של אורכי מקטעים.
    לדוגמה: 16 -> [8, 8], 20 -> [8, 8, 4]
    """
    length = max(4, min(24, length))  # נגביל ל־4–24 שניות בשביל ההיגיון
    segments: list[int] = []
    remaining = length
    while remaining > 0:
        seg = min(8, remaining)
        segments.append(seg)
        remaining -= seg
    return segments


def generate_concept_auto(settings: dict, variation_index: int) -> dict:
    """מייצר קונספט רנדומלי לגמרי, לפי ההגדרות הכלליות."""
    style = settings.get("style", "")
    brand = settings.get("brand", "")
    market = settings.get("market", "")

    if "UGC selfie" in style:
        locations = [
            "במחצית על הספה כשהחברים צועקים על המסך",
            "במיטה בבוקר לפני שיוצא לעבודה",
            "באוטובוס בדרך למשחק",
            "במטבח בזמן שהוא מכין קפה",
        ]
        angles = [
            "סלפי קרוב לפנים",
            "סלפי קצת מרוחק עם רקע של הבית",
            "סלפי עם רקע של הרחוב בחוץ",
        ]
    elif "Green screen" in style:
        locations = [
            "מול מסך ירוק כשמאחוריו ויז׳ואלים של ליגות ומשחקים",
            "מול מסך ירוק עם גרפים של סטטיסטיקות",
        ]
        angles = [
            "מצלמה בגובה העיניים, שוט אמצעי",
            "שוט כתפיים, המצלמה מעט מעל העיניים",
        ]
    else:
        locations = [
            "בפאב מלא אוהדים",
            "במשרד בזמן הפסקת צהריים",
            "בסלון מול טלוויזיה גדולה",
        ]
        angles = [
            "מצלמה בגובה העיניים כאילו חבר מצלם",
            "מצלמה סטטית על חצובה",
        ]

    hooks = [
        f"\"מאז שהתחלתי להשתמש ב{brand}, הרבה יותר קל לי לעקוב אחרי כל המשחקים.\"",
        f"\"אתמול באמצע המשחק גיליתי את {brand} וזה שינה לי את כל הדרך שאני עוקב אחרי כדורגל.\"",
        f"\"כולם בקבוצה שלי כבר ב{brand} ורק אני נשארתי מאחור – עד עכשיו.\"",
    ]

    ctas = [
        f"\"תורידו את {brand} ותנסו בעצמכם.\"",
        f"\"תורידו עכשיו את {brand} ותהיו מעודכנים לפני כולם.\"",
        f"\"פשוט תורידו את {brand} ותראו לבד כמה זה נוח.\"",
    ]

    concept = {
        "core_idea": f"אוהד כדורגל ב{market} שמראה איך {brand} עושה לו סדר ביום יום",
        "location": random.choice(locations),
        "camera_angle": random.choice(angles),
        "hook_line": random.choice(hooks),
        "cta_line": random.choice(ctas),
        "variation_index": variation_index,
        "mode": "auto",
    }
    return concept


def generate_concept_from_user(settings: dict, idea_text: str, variation_index: int) -> dict:
    """קונספט שמבוסס על רעיון כללי שהמשתמש כתב, עם קצת רנדומליות מסביב."""
    base = generate_concept_auto(settings, variation_index)
    base["core_idea"] = idea_text.strip()
    base["mode"] = "manual"
    return base


def make_veo_segment_script(
    brand: str,
    market: str,
    lang_code: str,
    concept: dict,
    segment_index: int,
    segment_count: int,
) -> str:
    """
    בונה טקסט דיאלוג רק למקטע מסוים (Hook / גוף / CTA).
    שומר על שוני בין וריאציות כי החלקים רנדומליים.
    """
    hook = concept["hook_line"]
    cta = concept["cta_line"]
    location = concept["location"]

    if lang_code.upper() == "ES":
        # גרסה מאוד בסיסית בספרדית; אפשר לחדד אחר כך
        if segment_index == 0:
            return (
                f"{hook} Estoy en {location} y abro la app para ver todos los marcadores "
                f"en vivo en segundos."
            )
        elif segment_index < segment_count - 1:
            return (
                "Miro próximos partidos, estadísticas y lo que juega mi equipo "
                "sin perder tiempo cambiando de apps."
            )
        else:
            return (
                f"Todo desde un solo lugar y sin complicaciones. {cta}"
            )

    # ברירת מחדל – עברית / אנגלית פשוטה
    if segment_index == 0:
        return (
            f"{hook} אני ב{location} ופשוט פותח את האפליקציה ורואה את כל התוצאות בשנייה."
        )
    elif segment_index < segment_count - 1:
        return (
            "אני מדפדף בין משחקים, לייב סקורז ולוח המשחקים – הכל במקום אחד."
        )
    else:
        return (
            f"הכל מסודר וברור, בלי לבזבז זמן. {cta}"
        )


def build_whisk_prompt(data: dict, concept: dict) -> str:
    brand = data["brand"]
    market = data["market"]
    style = data["style"]
    goal = data["goal"]
    actor = data.get("actor", f"young football fan from {market}")
    variant = data.get("variant_index")

    variant_label = f"Variation {variant}" if variant else "Single version"

    prompt = f"""
Static ad image for Whisk.
Brand: "{brand}"
Market: "{market}"
{variant_label}
Creative style: {style}
Objective: {goal}

Concept:
- Core idea: {concept['core_idea']}
- Location: {concept['location']}
- Camera angle: {concept['camera_angle']}

Scene:
- Show {actor} in a setting that feels natural for {market}, matching the concept location.
- Vertical or 4:5 mobile friendly composition.
- The person may hold a phone, but if the phone appears the screen must not face the camera.
- Background should be clean but with enough context (home, street, office, taxi etc).

Branding:
- Use {brand} colors strongly in UI elements, accents or clothing.
- Include clear brand name and a big readable CTA such as "Free Download" or "Sign up now".

Restrictions:
- Do not use real football teams or real player faces.
- Instructions are for the generator only and must not appear as visible text.
""".strip()

    return prompt


def build_veo_prompts(data: dict, concept: dict) -> list[str]:
    """
    מחזיר רשימת פרומפטים – אחד לכל מקטע של עד 8 שניות.
    """
    brand = data["brand"]
    market = data["market"]
    style = data["style"]
    goal = data["goal"]
    length = int(data.get("length", 8))
    lang_code = data["language"]
    actor = data.get("actor", f"young football fan from {market}")
    variant = data.get("variant_index")

    segments = compute_segments(length)
    segment_count = len(segments)

    prompts: list[str] = []

    for idx, seg_len in enumerate(segments):
        script_text = make_veo_segment_script(
            brand=brand,
            market=market,
            lang_code=lang_code,
            concept=concept,
            segment_index=idx,
            segment_count=segment_count,
        )

        variant_label = f"Variation {variant}" if variant else "Single version"

        prompt = f"""
Google VEO video generation prompt.
Brand: "{brand}"
Market: "{market}"
{variant_label}
Segment: {idx + 1}/{segment_count}
Target duration: {seg_len} seconds
Creative style: {style}
Objective: {goal}

Concept:
- Core idea: {concept['core_idea']}
- Location: {concept['location']}
- Camera angle: {concept['camera_angle']}
- Hook: {concept['hook_line']}
- CTA: {concept['cta_line']}

Reference image usage:
- Use the provided reference image as frame 1 for this segment.
- Frame 1 must match the reference image exactly:
  same actor style, clothing, lighting, background and camera angle.
- Do NOT redesign the actor. Continue naturally from the still into motion.

Scene and camera:
- Vertical 9:16 UGC style with slight handheld motion.
- Show {actor} as the main subject.
- Environment should match {market} and the concept location.
- The actor holds a phone but the screen is never shown to the camera.

Voice:
- Young African male if relevant to {market}.
- Warm, conversational tone, medium energy.
- Dialog must comfortably fit inside {seg_len} seconds.

Dialog for THIS segment only (spoken, no stage directions):
{script_text}

Do NOT include technical words like "voiceover" or "scene description" inside the dialog.
""".strip()

        prompts.append(prompt)

    return prompts


# ===== Conversation handlers =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "היי 👋\nבוא נייצר קריאייטיב.\n\n"
        "קודם כל, מה שם הברנד? (לדוגמה: PAS, Betsson, AdmiralBet)"
    )
    return BRAND


async def brand_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["brand"] = update.message.text.strip()
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
        "מה הסגנון?",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
    )
    return STYLE


async def style_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["style"] = update.message.text.strip()

    await update.message.reply_text(
        "מה המטרה העיקרית של הקריאייטיב? (למשל: להורדות, רישום, הפעלת משתמשים וכו׳)",
        reply_markup=ReplyKeyboardRemove(),
    )
    return GOAL


async def goal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["goal"] = update.message.text.strip()

    reply_keyboard = [
        ["Male 18-25 energetic", "Male 25-35 calm"],
        ["Female 18-25 energetic", "Female 25-35 calm"],
        ["Other - I will describe"],
    ]
    await update.message.reply_text(
        "תבחר סוג שחקן (או בחר Other ותכתוב לי אחר כך מה אתה רוצה):",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
    )
    return ACTOR


async def actor_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # במידה וזה המשך של "Other"
    if context.user_data.get("waiting_custom_actor"):
        context.user_data["waiting_custom_actor"] = False
        context.user_data["actor"] = text
    elif text.startswith("Other"):
        context.user_data["waiting_custom_actor"] = True
        await update.message.reply_text(
            "תכתוב במדויק את סוג השחקן (גיל, מגדר, וייב, לדוגמה: "
            '"young South African male, early 20s, funny and energetic").',
            reply_markup=ReplyKeyboardRemove(),
        )
        return ACTOR
    else:
        context.user_data["actor"] = text

    # ממשיכים – אם זה וידאו, שואלים אורך; אם תמונה – ישר לשפה
    if context.user_data.get("format") == "veo":
        await update.message.reply_text(
            "מה אורך הוידאו בשניות? (לדוגמה: 8, 16, 24)",
            reply_markup=ReplyKeyboardRemove(),
        )
        return LENGTH

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
        await update.message.reply_text("תכתוב מספר שניות תקין, לדוגמה 8 או 16.")
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
            "נא לבחור באחת מהאפשרויות: Native language או English."
        )
        return LANGUAGE

    context.user_data["language"] = lang_code

    reply_keyboard = [
        ["🎲 תביא לי רעיונות בשבילי", "✏️ אני אכתוב רעיון כללי"],
    ]
    await update.message.reply_text(
        "איך אתה רוצה לבחור את רעיון הסרטון/תמונה?\n"
        "1. שאביא לך רעיונות שונים אוטומטית.\n"
        "2. שתכתוב רעיון כללי ואני אייצר כמה וריאציות סביבו.",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
    )
    return IDEA_MODE


async def idea_mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if "רעיונות" in text or "🎲" in text:
        context.user_data["idea_mode"] = "auto"
        # אין צורך בטקסט חופשי – עוברים ישר לכמות וריאציות
        await update.message.reply_text(
            "מעולה, אביא רעיונות אוטומטית.\n"
            "כמה וריאציות אתה רוצה? (1 עד 3)",
            reply_markup=ReplyKeyboardRemove(),
        )
        return VARIATIONS

    context.user_data["idea_mode"] = "manual"
    await update.message.reply_text(
        "תכתוב לי רעיון כללי לסרטון / לתמונה (POV, סיטואציה, מה הקטע המרכזי):",
        reply_markup=ReplyKeyboardRemove(),
    )
    return IDEA_TEXT


async def idea_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["idea_text"] = update.message.text.strip()
    await update.message.reply_text(
        "מעולה. כמה וריאציות אתה רוצה שאייצר? (1 עד 3)"
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
    fmt = context.user_data["format"]
    idea_mode = context.user_data.get("idea_mode", "auto")
    idea_text = context.user_data.get("idea_text", "")

    base_settings = dict(context.user_data)

    # ניצור וריאציות
    if fmt == "veo":
        for i in range(1, num + 1):
            variant_data = dict(base_settings)
            variant_data["variant_index"] = i

            if idea_mode == "auto":
                concept = generate_concept_auto(variant_data, i)
            else:
                concept = generate_concept_from_user(variant_data, idea_text, i)

            veo_prompts = build_veo_prompts(variant_data, concept)

            for idx, vp in enumerate(veo_prompts, start=1):
                await update.message.reply_text(
                    f"🎥 וריאציה {i} – פרומפט וידאו {idx}/{len(veo_prompts)}:\n\n{vp}"
                )

        await update.message.reply_text("ליצירת קריאייטיב חדש – /start")
        return ConversationHandler.END

    # פורמט תמונות – Whisk
    for i in range(1, num + 1):
        variant_data = dict(base_settings)
        variant_data["variant_index"] = i

        if idea_mode == "auto":
            concept = generate_concept_auto(variant_data, i)
        else:
            concept = generate_concept_from_user(variant_data, idea_text, i)

        whisk_prompt = build_whisk_prompt(variant_data, concept)
        await update.message.reply_text(
            f"🖼️ וריאציה {i} – פרומפט Whisk:\n\n{whisk_prompt}"
        )

    await update.message.reply_text("ליצירת קריאייטיב חדש – /start")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ביטלתי את תהליך יצירת הקריאייטיב. אפשר להתחיל מחדש עם /start.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


def main():
    token = os.environ.get("TOKEN")
    if not token:
        raise RuntimeError(
            "Environment variable TOKEN is not set. "
            "אתה צריך להגדיר TOKEN עם הטוקן של הבוט ב־Render / מקומית."
        )

    app = ApplicationBuilder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, brand_handler)],
            MARKET: [MessageHandler(filters.TEXT & ~filters.COMMAND, market_handler)],
            FORMAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, format_handler)],
            STYLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, style_handler)],
            GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_handler)],
            ACTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, actor_handler)],
            LENGTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, length_handler)],
            LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, language_handler)],
            IDEA_MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, idea_mode_handler)],
            IDEA_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, idea_text_handler)],
            VARIATIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, variations_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)

    app.run_polling()


if __name__ == "__main__":
    main()
