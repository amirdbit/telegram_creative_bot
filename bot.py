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
    INPUT_CONCEPT, 
    CHOOSE_IDEA_FROM_LIST, 
) = range(11)


# -------------------------------------------------
#  Helpers: random idea banks and continuity logic
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


def get_random_video_ideas(market: str) -> Dict[int, Dict[str, str]]:
    """מחזיר 3 רעיונות רנדומליים לוידאו VEO."""
    base_ideas = [
        {
            "title": "Match day reaction",
            "concept": f"Fan in {market} reacting live to a key football moment while using the app.",
        },
        {
            "title": "Halftime quick check",
            "concept": f"User checks live scores and bets on the app during halftime to see what changed.",
        },
        {
            "title": "On the go update",
            "concept": f"Fan in {market} gets a loud notification from the app in a taxi or at work and celebrates.",
        },
        {
            "title": "Group chat pressure",
            "concept": "Friends tease the main character in the group chat until he finally downloads and opens the app.",
        },
        {
            "title": "Weak network still working",
            "concept": "User is in a place with bad reception but the app keeps updating scores without freezing.",
        },
    ]
    ideas = random.sample(base_ideas, 3)
    return {i + 1: ideas[i] for i in range(3)}


def get_random_image_ideas(market: str) -> Dict[int, Dict[str, str]]:
    """מחזיר 3 רעיונות רנדומליים לתמונת Whisk."""
    base_ideas = [
        {
            "title": "Big league spotlight",
            "concept": f"Focus on top leagues that fans in {market} love, with bold app branding and a strong CTA.",
        },
        {
            "title": "Fan celebration close up",
            "concept": "Close up on a happy fan face with a stadium background. The fan holds a phone but the screen is not visible.",
        },
        {
            "title": "Clean minimal layout",
            "concept": "Simple background in brand colors, strong logo, one clear benefit line and a big CTA.",
        },
    ]
    ideas = random.sample(base_ideas, 3)
    return {i + 1: ideas[i] for i in range(3)}


def split_to_segments(duration_sec: int) -> list[int]:
    """מחלק אורך וידאו למקטעים של עד 8 שניות."""
    segments: list[int] = []
    remaining = max(8, min(duration_sec, 32)) 
    while remaining > 0:
        seg = min(8, remaining)
        segments.append(seg)
        remaining -= seg
    return segments


def build_example_dialog(language: str, market: str, brand: str):
    """דוגמאות לדיאלוג (טון בלבד) עבור הפרומפט."""
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
    ]
    return random.choice(templates)


# -------------------------------------------------
# Prompt Builders (The "Ready-to-Paste" Output)
# -------------------------------------------------


def build_whisk_frame_prompt(user_data: Dict[str, Any], variation_index: int) -> str:
    """Frame 1 Whisk prompt: תמונה סטטית לפתיחת הסרטון."""
    brand = user_data["brand"]
    market = user_data["market"]
    language = user_data["language"]
    style = user_data["style"]
    scene = user_data.get("scene_concept", f"a fan in {market} looking at a phone in a natural setting.")

    return f"""
Frame 1 Whisk image prompt for VEO video - Variation {variation_index}
Output: Static image (Vertical 9:16)

Goal:
- Generate the first frame of the VEO video. The image must match the opening shot of the video exactly.
- NO real teams, NO real players, NO copyrighted logos.

Scene:
- A realistic portrait shot of the main actor described in the video prompt, in a setting that matches the video's opening scene: {scene}
- Same actor look, outfit and environment as the VEO video in a natural setting.
- The actor holds a phone but the screen is NEVER visible to the camera.
- Lighting must be clean and realistic (UGC style).

Brand and language:
- All on image text must be written in {language}.
- Include the {brand} logo and a clear CTA (e.g., Download now or Play now).

Instructions for Whisk:
- Describe the visual details of this single frame only. Do NOT mention the word "prompt" or technical terms.
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
        full_output_lines.append(f"Brand: {brand} | Market: {market} | Style: {style} | Language: {language}")
        full_output_lines.append("="*50)
        full_output_lines.append("")
        
        # Concept and General Rules Block
        if user_data.get("concept_mode") == "random":
            # הגרלה מחדש של רעיון רנדומלי שונה לכל וריאציה (אם נבחר "Random")
            ideas = get_random_video_ideas(market)
            idea = random.choice(list(ideas.values()))
            full_output_lines.append(f"Creative Concept: {idea['title']} - {idea['concept']}")
        else:
            full_output_lines.append(f"Creative Concept: {scene}")

        full_output_lines.append("")
        full_output_lines.append("--- VEO GENERATION INSTRUCTIONS ---")
        full_output_lines.append("General Rules:")
        full_output_lines.append(f"- Output must be {len(segments)} separate VEO prompts. Each prompt is for a clip of up to 8 seconds.")
        full_output_lines.append("- All visuals must maintain actor, outfit, lighting, and scene consistency across all segments.")
        full_output_lines.append("- The actor holds a phone but the screen is NEVER shown directly to the camera.")
        full_output_lines.append(f"- The final spoken dialog must be written entirely in {language}.")
        full_output_lines.append("")

        # Segment Prompts (VEO)
        for s_idx, seg_len in enumerate(segments):
            start_s = sum(segments[:s_idx]) + 1
            end_s = start_s + seg_len - 1

            focus = random.choice([
                "strong emotional reaction to a football moment", 
                "clear call to action that invites the viewer to download or play",
                "natural fan behavior and small realistic details in the background",
            ])
            example_dialog = build_example_dialog(language, market, brand)

            full_output_lines.append(f"--- VEO SEGMENT {s_idx + 1} of {len(segments)}: Seconds {start_s} to {end_s} ---")
            full_output_lines.append(f"1. VISUAL: Vertical 9:16. Describe exact framing, movement, and scene actions for seconds {start_s} to {end_s}. Focus on: {focus}.")
            full_output_lines.append(f"2. DIALOG: Write the full spoken script for this {seg_len} second segment, line by line, in {language}. The script must fit comfortably in {seg_len} seconds.")
            full_output_lines.append(f"   Dialogue Tone Example (must be written in {language} in final prompt):")
            for d in example_dialog:
                full_output_lines.append(f"   {d}")
            full_output_lines.append("")

        # Whisk Frame 1 Prompt
        full_output_lines.append("--- WHISK FRAME 1 PROMPT (Ready-to-Paste for Image Input) ---")
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
        full_output_lines.append(f"Brand: {brand} | Market: {market} | Style: {style} | Language: {language}")
        full_output_lines.append("="*50)
        full_output_lines.append("")

        # Concept
        if user_data.get("concept_mode") == "random":
            ideas = get_random_image_ideas(market)
            idea = random.choice(list(ideas.values()))
            full_output_lines.append(f"Creative Concept: {idea['title']} - {idea['concept']}")
        else:
            full_output_lines.append(f"Creative Concept: {scene}")

        full_output_lines.append("")
        full_output_lines.append("--- WHISK GENERATION INSTRUCTIONS ---")
        
        # Layout and Composition
        layout_focus = random.choice([
            "big central logo and CTA button",
            "strong promo numbers with a smaller logo",
            "phone held in a hand with clear brand elements around it",
            "clean background in brand colors with simple icons",
        ])

        full_output_lines.append(f"1. VISUAL: Vertical 9:16 format for mobile placement. Focus on: {layout_focus}.")
        full_output_lines.append("2. SCENE: Describe the image contents, actor (if any), and setting. Must feel native to the market.")
        full_output_lines.append("3. BRANDING: Use official brand colors and logo. Never use real teams or copyrighted player images.")
        full_output_lines.append(f"4. TEXT: All visible text must be in {language}. Include a short, bold headline, one supporting line, and a clear CTA (e.g., Download now).")
        full_output_lines.append("--- END PROMPT ---")
        full_output_lines.append("")

    return "\n".join(full_output_lines)


# -------------------------------------------------
# Telegram bot handlers
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
    
    native_lang_info = infer_native_language(market)
    
    keyboard = [
        ["English"],
    ]
    if native_lang_info and native_lang_info[0] != "EN":
        keyboard.insert(0, [f"Native Language ({native_lang_info[1]})"])
    
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
    
    await update.message.reply_text("OK. Please describe the creative style (UGC selfie, motion graphic, clean banner, etc.)", 
                                    reply_markup=ReplyKeyboardRemove())
    return ASK_STYLE


async def ask_actor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["style"] = update.message.text.strip()
    
    await update.message.reply_text("Please describe the actor/characters (e.g., young excited African male, 3 friends watching the game, etc.)", 
                                    reply_markup=ReplyKeyboardRemove())
    return ASK_ACTOR


async def ask_scene_concept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["actor_desc"] = update.message.text.strip()
    
    keyboard = [
        [InlineKeyboardButton("Give me random ideas", callback_data="concept_random")],
        [InlineKeyboardButton("I will describe my idea", callback_data="concept_custom")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if context.user_data["mode"] == "video":
        await update.message.reply_text("Do you want me to suggest 3 random concepts or do you want to describe the general idea yourself?", 
                                        reply_markup=reply_markup)
    else:
        await update.message.reply_text("Do you want me to suggest 3 random image concepts or do you want to describe the general idea yourself?", 
                                        reply_markup=reply_markup)
        
    return ASK_SCENE_CONCEPT


async def ask_video_length_or_generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # טיפול ב-Inline keyboard של בחירת Concept Mode
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        mode = query.data
        
        if mode == "concept_random":
            context.user_data["concept_mode"] = "random"
            return await handle_random_concept_selection(query, context)
        elif mode == "concept_custom":
            context.user_data["concept_mode"] = "custom"
            await query.edit_message_text(
                "Perfect. Send me a short description of the general idea for the creative (this will be the core concept)."
            )
            return INPUT_CONCEPT

    # טיפול בהזנת טקסט (Concept Mode Custom)
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


async def handle_random_concept_selection(query: Any, context: ContextTypes.DEFAULT_TYPE) -> int:
    market = context.user_data["market"]
    mode = context.user_data["mode"]
    
    if mode == "video":
        ideas = get_random_video_ideas(market)
    else:
        ideas = get_random_image_ideas(market)
    
    context.user_data["ideas"] = ideas
    
    text_lines = ["I generated 3 ideas. Choose one of the buttons below.\n"]
    for idx, idea in ideas.items():
        text_lines.append(f"{idx}. {idea['title']}: {idea['concept']}")
    text = "\n".join(text_lines)
    
    keyboard = [
        [
            InlineKeyboardButton("Idea 1", callback_data="idea_1"),
            InlineKeyboardButton("Idea 2", callback_data="idea_2"),
            InlineKeyboardButton("Idea 3", callback_data="idea_3"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=text, reply_markup=reply_markup)
    return CHOOSE_IDEA_FROM_LIST


async def choose_idea_from_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    chosen = int(query.data.split("_")[1])
    context.user_data["scene_concept"] = context.user_data["ideas"][chosen]["concept"]
    
    if context.user_data["mode"] == "video":
        await query.edit_message_text(
            "Nice, we will work with that idea.\n\nWhat is the total video length in seconds? (8, 16, 24, or 32)",
        )
        keyboard = [["8", "16"], ["24", "32"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await query.message.reply_text("Choose length:", reply_markup=reply_markup)
        
        return ASK_VIDEO_LENGTH
    else:
        await query.edit_message_text("Nice, we will work with that idea. Generating 4 Whisk image prompts...")
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
    
    await update.message.reply_text("Great. Creating 4 VEO variations now...", 
                                    reply_markup=ReplyKeyboardRemove())
    
    return await generate_prompts(update, context)


async def generate_prompts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data
    mode = user_data["mode"]
    
    if update.callback_query:
        effective_message = update.callback_query.message
    else:
        effective_message = update.message

    if mode == "video":
        result_text = build_veo_prompts(user_data)
    else:
        result_text = build_whisk_prompts(user_data)

    await send_long_message(effective_message, context, result_text)
    
    await effective_message.reply_text(
        "Done. Your 4 creative variations are ready. Send /start to begin a new creative.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def send_long_message(message: Any, context: ContextTypes.DEFAULT_TYPE, text: str):
    """שולח הודעה ארוכה במספר מקטעים."""
    chunk_size = 3500
    for i in range(0, len(text), chunk_size):
        chunk = text[i: i + chunk_size]
        await message.reply_text(chunk)


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
        raise RuntimeError("TOKEN environment variable is not set") 

    application = ApplicationBuilder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_TYPE: [CallbackQueryHandler(choose_type)],
            ASK_BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_market)], 
            ASK_MARKET: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_language)],
            ASK_LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_style)],
            ASK_STYLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_actor)],
            ASK_ACTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_scene_concept)],
            ASK_SCENE_CONCEPT: [CallbackQueryHandler(ask_video_length_or_generate), 
                                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_video_length_or_generate)],
            INPUT_CONCEPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_video_length_or_generate)],
            CHOOSE_IDEA_FROM_LIST: [CallbackQueryHandler(choose_idea_from_list)],
            ASK_VIDEO_LENGTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_video_length_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    application.add_handler(conv_handler)
    
    logger.info("Bot is starting with quiet polling...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        poll_interval=2.0, 
        timeout=20,
        drop_pending_updates=True, 
    )


if __name__ == "__main__":
    main()
