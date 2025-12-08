import logging
import os
import random
import json
from typing import Dict, Any, List

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
#  Gemini Imports
# -------------------------------------------------
import google.generativeai as genai
from google.generativeai import types


# -------------------------------------------------
#  Logging & Config
# -------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Environment Variables (MUST be set in Render Dashboard)
TOKEN = os.getenv("TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini Configuration 
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("Gemini client configured successfully.")
    except Exception as e:
        logger.error(f"Error configuring Gemini client: {e}")
else:
    logger.warning("GEMINI_API_KEY not found. Using fallback concepts only.")


# -------------------------------------------------
#  States for ConversationHandler (FIXED: Starting from 100 to avoid 0/1 conflicts)
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
) = range(100, 111)


# -------------------------------------------------
#  Helpers & Idea Generation (All functions needed for the bot)
# -------------------------------------------------

def infer_native_language(market: str) -> tuple[str, str] | None:
    """Detect base language from market name."""
    m = (market or "").strip().lower()

    if "argentina" in m or "peru" in m:
        return "ES", "Spanish"
    if "israel" in m or "ישראל" in m:
        return "HE", "Hebrew"
    if "africa" in m or "malawi" in m or "zambia" in m:
        return "EN", "English for the Market"
    return None


def split_to_segments(duration_sec: int) -> list[int]:
    """Splits video length into VEO segments (max 8s each)."""
    segments: list[int] = []
    remaining = max(8, min(duration_sec, 32))
    while remaining > 0:
        seg = min(8, remaining)
        segments.append(seg)
        remaining -= seg
    return segments


def build_example_dialog(language: str, market: str, brand: str):
    """Provides short example dialog lines for tone consistency."""
    
    # Hebrew HE
    if language.upper() == "HE":
        templates = [
            [
                f'"אוקיי, בדיקה מהירה... מה יש היום בכדורגל?"',
                f'"וואו, {brand} שם לי הכל מסודר במקום אחד."',
                f'"אפשר לעשות את זה בשנייה ולחזור למה שעשיתי."',
            ],
            [
                f'"רגע, בוא נראה מה ה-Live Score."',
                f'"יפה, האפליקציה כבר עדכנה. {brand} פשוט מהיר."',
                f'"טוב, מוכן לחצי השני עכשיו."',
            ],
        ]
        return random.choice(templates)

    # Spanish ES (Genérico)
    if "ES" in language.upper():
        templates = [
            [
                f'"A ver, chequeo rápido... qué hay de fútbol hoy en {market}?"',
                f'"Wow, {brand} me pone todo en un solo lugar."',
                f'"Puedo hacer esto en segundos y volver a lo que estaba haciendo."',
            ],
            [
                f'"Espera, déjame ver el marcador en vivo."',
                f'"Buena, la app ya actualizó. {brand} nunca duerme."',
                f'"Listo, ya estoy para el segundo tiempo."',
            ],
        ]
        return random.choice(templates)
        
    # Default English EN
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


def get_fallback_concepts(mode: str, count: int) -> Dict[int, Dict[str, str]]:
    """Generates simple fallback concepts if Gemini API fails."""
    if mode == "video":
        titles = ["Match day reaction", "Halftime quick check", "On the go update", "Weak network still working"]
    else:
        titles = ["Big league spotlight", "Fan celebration close up", "Clean minimal layout", "Top odds banner"]
        
    return {
        i + 1: {
            "title": titles[i % len(titles)], 
            "concept": f"Fallback concept {i+1}: Cannot reach Gemini API. Using generic concept. Focus on {titles[i % len(titles)]}.",
        } 
        for i in range(count)
    }


def generate_concepts_via_gemini(user_data: Dict[str, Any], count: int = 4) -> Dict[int, Dict[str, str]]:
    """
    Generates creative concepts using the Gemini API.
    """
    if not os.getenv("GEMINI_API_KEY"):
        return get_fallback_concepts(user_data.get("mode", "video"), count)

    market = user_data["market"]
    language = user_data["language"]
    mode = user_data["mode"] 
    style = user_data["style"]

    prompt = f"""
You are a top-tier creative strategist. Your task is to generate {count} unique and compelling creative concepts for an ad campaign, optimized for high user acquisition (UA).

The campaign parameters are:
- Target Market: {market}
- Target Language: {language}
- Creative Type: {mode} (video for VEO, image for Whisk)
- Creative Style: {style} (e.g., UGC selfie, motion graphic, clean banner)
- Constraint: Concepts must NOT violate copyright (no real teams, no real player names).

Generate {count} different creative concepts. For each concept, provide a unique 'title' and a detailed 'concept'.

Return the output as a single JSON object (array of objects) only.
"""

    response_schema = types.Schema(
        type=types.Type.ARRAY,
        items=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "title": types.Schema(type=types.Type.STRING),
                "concept": types.Schema(type=types.Type.STRING),
            },
            required=["title", "concept"],
        ),
    )
    
    try:
        response = genai.GenerativeModel('gemini-2.5-flash').generate_content(
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=0.8,
            )
        )
        
        json_content = json.loads(response.text)
        
        return {i+1: item for i, item in enumerate(json_content[:count])}

    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        return get_fallback_concepts(mode, count)


def build_whisk_frame_prompt(user_data: Dict[str, Any], variation_index: int) -> str:
    """Frame 1 Whisk prompt: תמונה סטטית לפתיחת הסרטון."""
    brand = user_data["brand"]
    market = user_data["market"]
    language = user_data["language"]
    style = user_data["style"]
    scene = user_data.get("scene_concept", f"a fan in {market} looking at a phone in a natural setting.")
    actor = user_data.get("actor_desc", "a young, excited football fan.")


    return f"""
Frame 1 Whisk image prompt for VEO video - Variation {variation_index}
Output: Static image (Vertical 9:16)

GOAL: Generate the first frame of the VEO video. The image must match the opening shot of the video exactly.
CONCEPT: {scene} (Must be the core visual element)

VISUAL INSTRUCTIONS:
- A realistic portrait shot of the main actor ({actor}) in a setting that matches the video's opening scene: {scene}
- Same actor look, outfit and environment as the VEO video in a natural setting.
- The actor holds a phone but the screen is NEVER visible to the camera.
- Lighting must be clean and realistic (UGC style).

BRANDING AND TEXT:
- All on image text must be written in {language}.
- Include the {brand} logo and a clear CTA (e.g., Download now or Play now) in the image design.

RESTRICTIONS:
- NO real teams, NO real players, NO copyrighted logos.
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
        full_output_lines.append(f"Creative Concept: {scene}") 
        full_output_lines.append(f"Style: {style} | Market: {market} | Actor: {actor} | Language: {language}")
        full_output_lines.append("="*50)
        full_output_lines.append("")
        
        # --- תבנית המוכנה להעתקה מתחילה כאן ---
        full_output_lines.append("--- VEO VIDEO GENERATION PROMPT (READY-TO-COPY) ---")
        
        full_output_lines.append(f"GOAL: Create a vertical 9:16 UGC video for UA, focusing on the concept: '{scene}'.")
        full_output_lines.append(f"VISUAL STYLE: {style}. Use {actor} in a typical {market} setting.")
        full_output_lines.append("CONTENT RESTRICTIONS: NO real teams, NO real players, NO copyrighted logos.")
        full_output_lines.append("")

        # Segment Prompts (VEO)
        for s_idx, seg_len in enumerate(segments):
            start_s = sum(segments[:s_idx]) + 1
            end_s = start_s + seg_len - 1

            focus = random.choice([
                "strong emotional reaction to a football moment and quickly checks the score on the phone", 
                "a clear call to action inviting the viewer to download or play with the brand name {brand} visible on screen",
                "natural fan behavior, using a quick, dynamic camera movement in the background",
            ])
            example_dialog = build_example_dialog(language, market, brand)

            full_output_lines.append(f"--- CLIP {s_idx + 1} of {len(segments)} ({seg_len} SECONDS) ---")
            full_output_lines.append(f"1. VISUAL: Vertical 9:16. The {actor} in the {market} setting. Action should focus on: {focus}.")
            full_output_lines.append(f"2. DIALOG ({language}): Write the full spoken script for this clip. Must fit in {seg_len} seconds.")
            full_output_lines.append(f"   Example script lines for tone:")
            for d in example_dialog:
                full_output_lines.append(f"   {d}")
            full_output_lines.append("")

        # Whisk Frame 1 Prompt
        full_output_lines.append("--- WHISK FRAME 1 PROMPT (READY-TO-PASTE FOR IMAGE INPUT) ---")
        full_output_lines.append(build_whisk_frame_prompt(user_data, v))
        full_output_lines.append("--- END OF VARIATION ---")
        full_output_lines.append("\n\n")

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
        full_output_lines.append(f"Creative Concept: {scene}") 
        full_output_lines.append(f"Style: {style} | Market: {market} | Language: {language}")
        full_output_lines.append("="*50)
        full_output_lines.append("")

        # --- תבנית המוכנה להעתקה מתחילה כאן ---
        full_output_lines.append("--- WHISK IMAGE GENERATION PROMPT (READY-TO-COPY) ---")
        
        layout_focus = random.choice([
            "big central logo and CTA button placed in the middle, dark cinematic lighting",
            "strong promo numbers with a smaller logo, minimalist graphic banner style",
            "phone held in a hand showing the app interface (DO NOT SHOW SCREEN), clean brand elements around it",
            "clean background in brand colors with simple icons and bold text overlay",
        ])
        
        full_output_lines.append(f"GOAL: Create a vertical 9:16 mobile ad focused on the concept: '{scene}'.")
        full_output_lines.append(f"VISUAL INSTRUCTIONS: {style} style, focused on {layout_focus}. Scene should include elements relevant to {market}. Use a fan (defined as: {actor}).")
        full_output_lines.append(f"BRANDING: Include the {brand} logo prominently. Use official brand colors (e.g., black and orange).")
        full_output_lines.append(f"TEXT INSTRUCTIONS: All text must be in {language}. Include a short, bold headline, one supporting line, and a clear CTA (e.g., Download now).")
        full_output_lines.append("CONTENT RESTRICTIONS: NO real teams, NO real players, NO copyrighted logos.")
        full_output_lines.append("--- END OF VARIATION ---")
        full_output_lines.append("\n\n")

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
        ["peru", "italy", "israel"],
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
    
    keyboard: List[List[str]] = [
        ["English"],
    ]
    if native_lang_info and native_lang_info[0] != "EN":
        # Uses the native language name from the helper function
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
    # Handle language input: if user chose "Native Language (X)", extract only X
    text_input = update.message.text.strip()
    if text_input.startswith("Native Language ("):
        context.user_data["language"] = text_input.split("(")[1].split(")")[0].strip()
    else:
        context.user_data["language"] = text_input
    
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
    
    await update.message.reply_text("Do you want me to suggest 4 random concepts (via Gemini) or do you want to describe the general idea yourself?", 
                                    reply_markup=reply_markup)
        
    return ASK_SCENE_CONCEPT


async def ask_video_length_or_generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Handler for Inline Keyboard (Choosing Concept Mode)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        mode = query.data
        
        if mode == "concept_random":
            context.user_data["concept_mode"] = "random"
            
            # Calls Gemini to generate 4 concepts
            concepts = generate_concepts_via_gemini(context.user_data, count=4)
            context.user_data["ideas"] = concepts

            text_lines = ["I generated 4 fresh ideas via Gemini. Choose one of the buttons below.\n"]
            for idx, idea in concepts.items():
                text_lines.append(f"{idx}. **{idea['title']}**: {idea['concept']}")
            text = "\n".join(text_lines)
            
            keyboard = [
                [InlineKeyboardButton("Idea 1", callback_data="idea_1"),
                 InlineKeyboardButton("Idea 2", callback_data="idea_2")],
                [InlineKeyboardButton("Idea 3", callback_data="idea_3"),
                 InlineKeyboardButton("Idea 4", callback_data="idea_4")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='Markdown')
            return CHOOSE_IDEA_FROM_LIST
            
        elif mode == "concept_custom":
            context.user_data["concept_mode"] = "custom"
            await query.edit_message_text(
                "Perfect. Send me a short description of the general idea for the creative (this will be the core concept)."
            )
            return INPUT_CONCEPT

    # Handler for Message (Custom Concept Input)
    context.user_data["scene_concept"] = update.message.text.strip()

    if context.user_data["mode"] == "video":
        # Video - Move to length selection
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
        # Image - Generate directly
        await update.message.reply_text("Got all details. Generating 4 Whisk image prompts...")
        return await generate_prompts(update, context)


async def choose_idea_from_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    chosen = int(query.data.split("_")[1])
    # Use the chosen idea's concept as the core scene_concept
    context.user_data["scene_concept"] = context.user_data["ideas"][chosen]["concept"] 
    
    if context.user_data["mode"] == "video":
        keyboard = [["8", "16"], ["24", "32"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await query.edit_message_text(
            "Nice, we will work with that idea. What is the total video length in seconds? (8, 16, 24, or 32)",
            reply_markup=reply_markup,
        )
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

    # Ensure scene_concept is set before calling build functions
    if "scene_concept" not in user_data:
        user_data["scene_concept"] = "General marketing concept." 

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
    """Sends a long message in multiple chunks to bypass Telegram limits."""
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
    token = os.getenv("TOKEN")
    if not token:
        # In a production environment like Render, TOKEN should be set
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
            
            ASK_SCENE_CONCEPT: [CallbackQueryHandler(ask_video_length_or_generate)],
            INPUT_CONCEPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_video_length_or_generate)],
            CHOOSE_IDEA_FROM_LIST: [CallbackQueryHandler(choose_idea_from_list)],
            
            ASK_VIDEO_LENGTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_video_length_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    application.add_handler(conv_handler)
    
    logger.info("Bot is starting with quiet polling...")
    # FIX: Removed close_bot_session=True (Type Error)
    # FIX for Conflict Error (drop_pending_updates=True)
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        poll_interval=2.0, 
        timeout=20,
        drop_pending_updates=True, 
    )


if __name__ == "__main__":
    main()
