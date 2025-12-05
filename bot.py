from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove

TOKEN = "8399449783:AAFGCKApaN3WzX4jpmuKL3VDGIJQT5PtbNo"

# Conversation states
BRAND, MARKET, FORMAT, STYLE, GOAL, ACTOR, LENGTH, LANGUAGE, VARIATIONS = range(9)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "היי 👋\nבוא נייצר קריאייטיב.\n\n"
        "קודם כל, מה שם הברנד? (לדוגמה: PAS, Betsson, AdmiralBet)"
    )
    return BRAND


async def brand_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["brand"] = update.message.text.strip()
    await update.message.reply_text("לאיזה מדינה או שוק? (לדוגמה: South Africa, Malawi, Argentina)")
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
    text = update.message.text.strip()

    # אם אנחנו בשלב של טקסט חופשי לסגנון
    if context.user_data.get("waiting_custom_style"):
        context.user_data["waiting_custom_style"] = False
        context.user_data["style"] = text

    # אם בחרת בכפתור free text
    elif text.lower().startswith("free text") or "custom" in text.lower():
        context.user_data["waiting_custom_style"] = True
        await update.message.reply_text(
            "תכתוב עכשיו במילים שלך מה סוג הקריאייטיב שאתה רוצה.\n"
            'לדוגמה: "POV TikTok בסלפי במונית", '
            '"Motion graphic עם לוח תוצאות", '
            '"סרטון ריאליסטי בסלון עם חברים".',
            reply_markup=ReplyKeyboardRemove(),
        )
        return STYLE

    # אחרת, אחד מהסטיילים המוכנים
    else:
        context.user_data["style"] = text

    # אחרי הסגנון, שואלים על היעד
    reply_keyboard = [["Install", "Reg", "FTD", "Brand awareness"]]
    await update.message.reply_text(
        "מה המטרה של הקריאייטיב?",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
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

    # אם זה המשך של Other ואנחנו מקבלים עכשיו תיאור חופשי
    if context.user_data.get("waiting_custom_actor"):
        context.user_data["waiting_custom_actor"] = False
        context.user_data["actor"] = text

    # אם בחרת עכשיו באופציה Other - I will describe
    elif text.lower().startswith("other"):
        context.user_data["waiting_custom_actor"] = True
        await update.message.reply_text(
            "תכתוב במדויק את סוג השחקן (גיל, מגדר, וייב, לדוגמה: "
            '"young South African male, early 20s, funny and energetic".',
            reply_markup=ReplyKeyboardRemove(),
        )
        return ACTOR

    # כל מקרה אחר: אחת מהאופציות המוכנות
    else:
        context.user_data["actor"] = text

    # אחרי שיש שחקן, אם זה וידאו שואלים על האורך, אחרת על שפה
    if context.user_data.get("format") == "veo":
        await update.message.reply_text(
            "מה אורך הוידאו בשניות? (לדוגמה: 8, 16, 24)",
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
                reply_keyboard,
                one_time_keyboard=True,
                resize_keyboard=True,
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
            "נא לבחור באחת מהאפשרויות: Native language או English."
        )
        return LANGUAGE

    context.user_data["language"] = lang_code

    await update.message.reply_text(
        f"אחלה, אשתמש בשפה: {lang_code}. עכשיו כמה וריאציות אתה רוצה? (1 עד 3)",
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
    fmt = context.user_data.get("format", "veo")

    if fmt == "veo":
        for i in range(1, num + 1):
            variant_data = dict(context.user_data)
            variant_data["variant_index"] = i

            whisk_ref = build_whisk_reference_prompt(variant_data)
            veo_prompt = build_veo_prompt(variant_data)

            await update.message.reply_text(
                f"🟩 וריאציה {i} - פרומפט Whisk לפריים ראשון:\n\n{whisk_ref}"
            )
            await update.message.reply_text(
                f"🎥 וריאציה {i} - פרומפט וידאו ל-VEO:\n\n{veo_prompt}"
            )

        await update.message.reply_text(
            "📌 חשוב: תייצר קודם את התמונות ב-Whisk, ואז תעלה כל תמונה כ-Image Input תואם ב-VEO."
        )

    else:
        for i in range(1, num + 1):
            variant_data = dict(context.user_data)
            variant_data["variant_index"] = i
            whisk_prompt = build_whisk_prompt(variant_data)
            await update.message.reply_text(
                f"🖼️ וריאציה {i} - פרומפט Whisk:\n\n{whisk_prompt}"
            )

    await update.message.reply_text("ליצירת קריאייטיב חדש - /start")
    return ConversationHandler.END


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


def build_whisk_prompt(data: dict) -> str:
    brand = data.get("brand", "Brand")
    market = data.get("market", "Market")
    style = data.get("style", "UGC style")
    goal = data.get("goal", "Install")
    actor = data.get("actor", f"young football fan from {market}")
    variant = data.get("variant_index")
    lang = data.get("language", "EN")

    variant_label = f"Variation {variant}" if variant else "Single version"

    if lang == "ES":
        text_lang = f"Spanish for {market}"
    elif lang == "HE":
        text_lang = "Hebrew"
    else:
        text_lang = "English"

    prompt = f"""
Static ad image for Whisk.
Brand: "{brand}"
Market: "{market}"
{variant_label}
Creative style: {style}
Objective: {goal}

Scene:
- Show {actor} in a setting that feels natural for {market}.
- Vertical or 4:5 mobile friendly composition.
- The person may hold a phone, but if the phone appears the screen must not face the camera.
- Background should be clean but with enough context (home, street, office, taxi etc).

On screen text:
- Headline and subline must be written in {text_lang}.
- Include clear brand name.
- Add a big readable CTA such as "Free Download" or "Sign up now" translated to {text_lang}.

Branding:
- Use {brand} colors strongly in UI elements, accents or clothing.

Restrictions:
- Do not use real football teams or real player faces.
- Instructions are for the generator only and must not appear as visible text.
""".strip()

    return prompt


def build_whisk_reference_prompt(data: dict) -> str:
    brand = data.get("brand", "Brand")
    market = data.get("market", "Market")
    style = data.get("style", "UGC style")
    goal = data.get("goal", "Install")
    actor = data.get("actor", f"young football fan from {market}")
    variant = data.get("variant_index")

    variant_label = f"Variation {variant}" if variant else "Single version"

    prompt = f"""
Reference image for FIRST FRAME of a Google VEO video.
Brand: "{brand}"
Market: "{market}"
{variant_label}
Video creative style: {style}
Objective: {goal}

Purpose:
- This is not an ad layout. This is a clean still frame that looks like frame 1 of a UGC vertical video.

Visual:
- Show {actor}, realistic and natural.
- Vertical 9:16 framing, chest-up or waist-up.
- Environment should clearly match {market} (choose one: home, street, office or taxi).
- Actor holds a phone, but the phone screen is not visible to the camera.
- Lighting should be soft and realistic.
- No text, no logos, no CTA, no graphic overlays.

This image must look exactly like the first frame of a real UGC TikTok style video.
""".strip()

    return prompt


def build_script_text(brand: str, market: str, lang: str, length: int) -> str:
    if lang == "ES":
        return f"""
[HOOK]
"Desde que uso {brand}, seguir el fútbol en {market} se volvió mucho más fácil."

[BODY]
"Veo marcadores en vivo, fixture y resultados en segundos, todo en una sola app. Funciona incluso con mala señal."

[CTA]
"Descargá {brand} hoy y probala gratis."
""".strip()

    if lang == "HE":
        return f"""
[HOOK]
"מאז שהתחלתי להשתמש ב-{brand}, הרבה יותר קל לי לעקוב אחרי כדורגל ב-{market}."

[BODY]
"במקום לקפוץ בין אתרים ואפליקציות, אני רואה בלייב תוצאות, משחקים קרובים וטבלאות, הכל במקום אחד."

[CTA]
"תוריד את {brand} היום ותנסה בחינם."
""".strip()

    return f"""
[HOOK]
"Since I started using {brand}, following football in {market} became much easier."

[BODY]
"I check live scores, fixtures and results in seconds, all in one simple app. It even works on weak network."

[CTA]
"Download {brand} today and try it free."
""".strip()


def build_veo_prompt(data: dict) -> str:
    brand = data.get("brand", "Brand")
    market = data.get("market", "Market")
    style = data.get("style", "UGC style")
    goal = data.get("goal", "Install")
    length = data.get("length", 8)
    lang = data.get("language", "EN")
    actor = data.get("actor", f"young football fan from {market}")
    variant = data.get("variant_index")

    variant_label = f"Variation {variant}" if variant else "Single version"

    if lang == "ES":
        dialog_language = f"Spanish for {market}"
    elif lang == "HE":
        dialog_language = "Hebrew"
    else:
        dialog_language = "English"

    script_text = build_script_text(brand, market, lang, length)

    prompt = f"""
Google VEO video generation prompt.
Brand: "{brand}"
Market: "{market}"
{variant_label}
Length: {length} seconds
Creative style: {style}
Objective: {goal}

Reference image usage:
- Use the provided reference image as frame 1.
- Frame 1 must match the reference image exactly:
  same actor style, clothing, lighting, background and camera angle.
- Do not redesign the actor. Continue naturally from the still into motion.

Scene and camera:
- Vertical 9:16 UGC style with slight handheld motion.
- Show {actor} as the main subject.
- Environment should match {market} and the reference image.
- The actor holds a phone but the screen is never shown to the camera.

Voice:
- Dialog language: {dialog_language}.
- Young African male if relevant to {market}.
- Warm, conversational tone, medium energy.
- Dialog must comfortably fit inside {length} seconds.

Example script:
{script_text}

Now create:
1. A second by second breakdown of camera and actor actions for the full {length} seconds.
2. Natural movement from the still reference frame into the first motion frames.
3. A final spoken dialog that sounds like real speech and stays close to the example.
4. Do not include technical words like "voiceover" or "scene description" inside the dialog.
""".strip()

    return prompt


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ביטלתי את תהליך יצירת הקריאייטיב. אפשר להתחיל מחדש עם /start.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


def main():
    app = ApplicationBuilder().token(TOKEN).build()

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
            VARIATIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, variations_handler)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),  # מאפשר להתחיל מחדש גם באמצע שיחה
        ],
        allow_reentry=True,  # מאפשר כניסה מחדש ל-conversation עם /start
    )

    app.add_handler(conv_handler)
    app.run_polling()



if __name__ == "__main__":
    main()
