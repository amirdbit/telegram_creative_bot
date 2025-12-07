import logging
import math
import os
import random
from typing import Dict, Any

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# -------------------------------------------------
#  Logging
# -------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# -------------------------------------------------
#  States for ConversationHandler
# -------------------------------------------------
(
    CHOOSING_TYPE,
    ASK_BRAND,
    ASK_MARKET,
    ASK_LANGUAGE,
    ASK_STYLE,
    ASK_ACTOR,
    ASK_SCENE_CONCEPT,
    ASK_VIDEO_LENGTH,
    GENERATE_PROMPTS,
) = range(9)


# -------------------------------------------------
#  Helper Logic: Language and Segmentation
# -------------------------------------------------

def infer_native_language(market: str) -> tuple[str, str] | None:
    """מזהה שפת מקור לפי מדינה, מחזיר (קוד שפה, תיאור)."""
    m = (market or "").strip().lower()

    if "argentina" in m:
        return "ES", "Spanish for Argentina"
    if "peru" in m:
        return "ES", "Spanish for Peru"
    if "israel" in m or "ישראל" in m:
        return "HE", "Hebrew"
    # בראנדים אפריקאיים משתמשים לרוב באנגלית
    if "africa" in m or "malawi" in m or "zambia" in m:
        return "EN", "English for the Market"
    return None

def split_to_segments(duration_sec: int) -> list[int]:
    """מחלק אורך וידאו למקטעים של עד 8 שניות."""
    segments: list[int] = []
    remaining = max(8, min(duration_sec, 32)) # הגבלת מקסימום ל-32 שניות
    while remaining > 0:
        seg = min(8, remaining)
        segments.append(seg)
        remaining -= seg
    return segments

# -------------------------------------------------
#  Idea banks & Dialogs (Example Dialogs in English)
# -------------------------------------------------

def build_example_dialog(language: str, market: str, brand: str):
    """דוגמאות לדיאלוג (טון בלבד) עבור הפרומפט, ה-VEO יתרגם לשפה הנבחרת."""
    templates = [
        [
            f'"Ok, quick check... what are today matches in {market}?"',
            f'"Wow, {brand} has everything in one place."',
            '"I can do this in a few seconds and get back to what I was doing."',
        ],
        [
            '"Hold on, let me see the live score."',
            f'"Nice, the app updated already. {brand} never sleeps."',
            '"Alright, I am ready for the second half now."',
        ],
        [
            '"Why did nobody tell me about this app earlier?"',
            f'"Look at this, even with weak network {brand} still works."',
            '"Ok, this is staying on my phone forever."',
        ],
    ]
    return random.choice(templates)


# -------------------------------------------------
#  Prompt Builders (The "Ready-to-Paste" Output)
# -------------------------------------------------


def build_whisk_frame_prompt(user_data: Dict[str, Any], variation_index: int) -> str:
    """Frame 1 Whisk prompt: תמונה סטטית לפתיחת הסרטון."""
    brand = user_data["brand"]
    market = user_data["market"]
    language = user_data["language"]
    style = user_data["style"]
    scene = user_data.get("scene_concept", f"a fan in {market} looking at a phone in a natural setting.")

    return f"""
Frame 1 Whisk image prompt for variation {variation_index}
Output: Static image (Vertical 9:16)

Goal:
- Generate the first frame of the VEO video.
- The image must match the opening shot of the video exactly.
- NO real teams, NO real players, NO copyrighted logos.

Scene:
- {scene}
- Same actor look, outfit and environment as the VEO video in a natural setting.
- The actor holds a phone but the screen is NEVER visible to the camera.
- Lighting must be clean and realistic (UGC style).

Brand and language:
- All on image text must be written in {language}.
- Include the {brand} logo and a clear CTA (e.g., Download now or Play now).

Instructions for Whisk:
- Describe the visual details of this single frame only.
- Do NOT mention the word "prompt" or technical terms like "frame description".
- Focus on lighting, mood, body language and clear placement of logo and CTA.
""".strip()


def build_veo_prompts(user_data: Dict[str, Any]) -> str:
    """Video mode: 4 וריאציות VEO + Whisk Frame 1."""
    brand = user_data["brand"]
    market = user_data["market"]
    language = user_data["language"]
    style = user_data["style"]
    scene = user_data.get("scene_concept", "Natural fan reaction to a match moment.")
    actor = user_data.get("actor_desc", "a young, excited football fan.")
    length = user_data["video_length"]

    segments = split_to_segments(length)
    variations = 4
    full_output_lines: list[str] = []

    for v in range(1, variations + 1):
        full_output_lines.append("="*50)
        full_output_lines.append(f"VEO VIDEO PROMPT - VARIATION {v} (Total Length: {length} seconds)")
        full_output_lines.append(f"Brand: {brand} | Market: {market} | Language: {language}")
        full_output_lines.append(f"Creative Style: {style}")
        full_output_lines.append(f"Actor/Characters: {actor}")
        full_output_lines.append("="*50)
        full_output_lines.append("")
        
        # General Rules Block
        full_output_lines.append("General Rules for Continuity:")
        full_output_lines.append("- Output must be {segments} separate VEO prompts. Each prompt is for a clip of up to 8 seconds.")
        full_output_lines.append("- Keep the same main actor, outfit, setting and lighting across ALL prompts in this variation.")
        full_output_lines.append("- Vertical 9:16 UGC style with natural handheld motion.")
        full_output_lines.append("- The actor holds a phone but the screen is NEVER shown directly to the camera.")
        full_output_lines.append(f"- All spoken dialog must be written entirely in {language}.")
        full_output_lines.append("")

        # Segment Prompts (VEO)
        for s_idx, seg_len in enumerate(segments):
            start_s = sum(segments[:s_idx]) + 1
            end_s = start_s + seg_len - 1

            focus_options = [
                "strong emotional reaction to a football moment",
                "smooth product focus on the app without showing the phone screen",
                "clear call to action that invites the viewer to download or play",
                "natural fan behavior and small realistic details in the background",
            ]
            focus = random.choice(focus_options)

            example_dialog = build_example_dialog(language, market, brand)

            full_output_lines.append(f"--- Prompt {s_idx + 1}/{len(segments)}: Seconds {start_s} to {end_s} ---")
            full_output_lines.append(f"SCENE DESCRIPTION (Focus: {focus}):")
            full_output_lines.append(f"- This is segment {s_idx + 1} of the {length} second video.")
            
            # Use the user's concept as the core scene
            full_output_lines.append(f"- Core Concept: {scene}")
            
            full_output_lines.append(f"SPOKEN DIALOGUE (in {language}):")
            full_output_lines.append(f"- Write the full spoken script for this {seg_len} second segment, line by line.")
            full_output_lines.append("- Dialogue must sound realistic and fit the scene and timing.")
            full_output_lines.append("- Example of dialogue tone to be translated and adapted:")
            for d in example_dialog:
                full_output_lines.append(f"  {d}")
            full_output_lines.append("")

        # Whisk Frame 1 Prompt
        full_output_lines.append("--- WHISK FRAME 1 PROMPT (for Image Input) ---")
        full_output_lines.append(build_whisk_frame_prompt(user_data, v))
        full_output_lines.append("")

    return "\n".join(full_output_lines)


def build_whisk_prompts(user_data: Dict[str, Any]) -> str:
    """Image mode: 4 וריאציות Whisk שונות."""
    brand = user_data["brand"]
    market = user_data["market"]
    language = user_data["language"]
    style = user_data["style"]
    scene = user_data.get("scene_concept", "Simple promo image.")
    actor = user_data.get("actor_desc", "a young fan.")

    variations = 4
    full_output_lines: list[str] = []

    for v in range(1, variations + 1):
        full_output_lines.append("="*50)
        full_output_lines.append(f"WHISK IMAGE PROMPT - VARIATION {v}")
        full_output_lines.append(f"Brand: {brand} | Market: {market} | Language: {language}")
        full_output_lines.append(f"Creative Style: {style}")
        full_output_lines.append(f"Actor/Characters: {actor}")
        full_output_lines.append("="*50)
        full_output_lines.append("")

        layout_focus_options = [
            "big central logo and CTA button",
            "strong promo numbers with a smaller logo",
            "phone held in a hand with clear brand elements around it",
            "clean background in brand colors with simple icons",
        ]
        layout_focus = random.choice(layout_focus_options)

        full_output_lines.append("Visual Composition:")
        full_output_lines.append(f"- The layout focus for this variation is: {layout_focus}.")
        full_output_lines.append("- Keep the design in vertical 9:16 format for mobile placements.")
        full_output_lines.append("- Use clear visual hierarchy so that logo, promo and CTA are easy to read.")
        full_output_lines.append("")

        full_output_lines.append("Core Scene:")
        full_output_lines.append(f"- Scene: {scene}")
        full_output_lines.append(f"- Show {actor} in a natural setting that feels native to {market}.")
        full_output_lines.append("- The person may hold a phone, but the screen must NOT face the camera.")
        full_output_lines.append("")

        full_output_lines.append("Brand and Language Rules:")
        full_output_lines.append(f"- All text on the image must be written in {language}.")
        full_output_lines.append("- NO Hebrew. NO real teams, NO copyrighted logos.")
        full_output_lines.append("- Main headline, supporting line, and CTA must be written in {language}.")
        full_output_lines.append("")

    return "\n".join(full_output_lines)


# -------------------------------------------------
#  Telegram bot handlers (updated for new flow)
# -------------------------------------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()

    keyboard = [
        [InlineKeyboardButton("VEO video prompts", callback_data="mode_video")],
        [InlineKeyboardButton("Whisk image prompts", callback_data="mode_image")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Hi! Choose what you want to create:",
        reply_markup=reply_markup,
    )
    return CHOOSING_TYPE


async def choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "mode_video":
        context.user_data["mode"] = "video"
        await query.edit_message_text(
            "Selected: VEO video prompts.\n\nSend me the brand name (e.g., betsson, Premier Africa Sports)."
        )
    else:
        context.user_data["mode"] = "image"
        await query.edit_message_text(
            "Selected: Whisk image prompts.\n\nSend me the brand name (e.g., betsson, Premier Africa Sports)."
        )

    return ASK_BRAND


async def ask_market(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["brand"] = update.message.text.strip()
    
    # אם הברנד מזוהה נדלג על שאלת המדינה ונגדיר אותה כאן

    # כפתורים לדוגמה
    keyboard = [
        ["south africa", "argentina"],
        ["peru", "italy"],
    ]
    reply_markup = ReplyKeyboardMarkup(
        keyboard, resize_keyboard=True, one_time_keyboard=True
    )
    
    await update.message.reply_text(
        "What is the market? (Tap a button or type any market)",
        reply_markup=reply_markup,
    )
    return ASK_MARKET


async def ask_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["market"] = update.message.text.strip()
    market = context.user_data["market"]
    
    # זיהוי שפת מקור
    native_lang_info = infer_native_language(market)
    
    keyboard = [
        ["English"],
    ]
    if native_lang_info and native_lang_info[0] != "EN":
        keyboard.insert(0, [f"Native Language ({native_lang_info[1]})"])
    
    # אם אין זיהוי, ניתן כפתורי ברירת מחדל
    if not native_lang_info:
        keyboard.append(["Spanish", "Portuguese"])
    
    reply_markup = ReplyKeyboardMarkup(
        keyboard, resize_keyboard=True, one_time_keyboard=True
    )

    await update.message.reply_text(
        "What is the brand language for scripts/text? (Tap an option or type your own)",
        reply_markup=reply_markup,
    )
    return ASK_LANGUAGE


async def ask_style(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["language"] = update.message.text.strip()

    # הסרת המקלדת כי אנחנו רוצים טקסט חופשי (מלל חופשי בסוג קריאייטיב)
    await update.message.reply_text("OK. Please describe the creative style (UGC selfie, motion graphic, clean banner, etc.)", 
                                    reply_markup=ReplyKeyboardRemove())
    return ASK_STYLE


async def ask_actor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["style"] = update.message.text.strip()
    
    # הסרת המקלדת כי אנחנו רוצים טקסט חופשי (מלל חופשי בשחקנים)
    await update.message.reply_text("Please describe the actor/characters (e.g., young excited African male, 3 friends watching the game, etc.)", 
                                    reply_markup=ReplyKeyboardRemove())
    return ASK_ACTOR


async def ask_scene_concept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["actor_desc"] = update.message.text.strip()
    
    # הסרת המקלדת כי אנחנו רוצים טקסט חופשי (מלל חופשי לקונספט)
    if context.user_data["mode"] == "video":
        await update.message.reply_text("Please write the core concept / full spoken script for the video (e.g., a fan gets a notification and celebrates, a friend shows the app to another friend, etc.)", 
                                        reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text("Please describe the main visual elements for the image (e.g., close-up on a phone screen showing live scores, fan celebrating in front of a stadium, etc.)", 
                                        reply_markup=ReplyKeyboardRemove())
        
    return ASK_SCENE_CONCEPT


async def ask_video_length_or_generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["scene_concept"] = update.message.text.strip()
    
    if context.user_data["mode"] == "video":
        # וידאו - עוברים לבחירת אורך
        keyboard = [["8", "16"], ["24", "32"]]
        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=True
        )

        await update.message.reply_text(
            "What is the total video length in seconds? (8, 16, 24, or 32)",
            reply_markup=reply_markup,
        )
        return ASK_VIDEO_LENGTH
    else:
        # תמונה - עוברים ישר ליצירה
        await update.message.reply_text("Got all details. Generating 4 Whisk image prompts...")
        return await generate_prompts(update, context)


async def ask_video_length_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        length = int(text)
        if length not in [8, 16, 24, 32]:
             raise ValueError
    except ValueError:
        await update.message.reply_text("Please choose a valid length (8, 16, 24, or 32).")
        return ASK_VIDEO_LENGTH

    context.user_data["video_length"] = length
    
    await update.message.reply_text("Great. Creating 4 VEO variations now, split into 8-second segments, including the Whisk Frame 1 prompts...", 
                                    reply_markup=ReplyKeyboardRemove())
    
    return await generate_prompts(update, context)


async def generate_prompts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data
    mode = user_data["mode"]

    if mode == "video":
        result_text = build_veo_prompts(user_data)
    else:
        result_text = build_whisk_prompts(user_data)

    await send_long_message(update, context, result_text)
    
    # לאחר יצירת הפרומפטים - סיום השיחה
    await update.effective_message.reply_text(
        "Done. Your 4 creative variations are ready. Send /start to begin a new creative."
    )
    return ConversationHandler.END


async def send_long_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """שולח הודעה ארוכה במספר מקטעים."""
    chunk_size = 3500
    for i in range(0, len(text), chunk_size):
        chunk = text[i: i + chunk_size]
        await update.effective_message.reply_text(chunk)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Conversation cancelled. Send /start to begin again.",
                                    reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# -------------------------------------------------
# Main Function
# -------------------------------------------------

def main():
    token = os.environ.get("TOKEN")
    if not token:
        # זה יזרוק שגיאה ב-Render אם הטוקן לא הוגדר
        raise RuntimeError("TOKEN environment variable is not set") 

    application = ApplicationBuilder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_TYPE: [CallbackQueryHandler(choose_type)],
            ASK_BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_market)], # דלגנו על ASK_MARKET אם הברנד מזוהה
            ASK_MARKET: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_language)],
            ASK_LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_style)],
            ASK_STYLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_actor)],
            ASK_ACTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_scene_concept)],
            ASK_SCENE_CONCEPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_video_length_or_generate)],
            ASK_VIDEO_LENGTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_video_length_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    application.add_handler(conv_handler)
    
    # הגדרת Polling שקט יותר כדי להפחית רעש בלוגים
    logger.info("Bot is starting with quiet polling...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        poll_interval=2.0, # הפסקה של 2 שניות
        timeout=20,
    )


if __name__ == "__main__":
    main()
