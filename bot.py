import logging
import math
import os
import random
from typing import Dict, Any

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
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
    ASK_CONCEPT_MODE,
    INPUT_CONCEPT,
    CHOOSE_IDEA_FROM_LIST,
    ASK_VIDEO_LENGTH,
    GENERATE_PROMPTS,
) = range(10)

# -------------------------------------------------
#  Helpers: random idea banks
# -------------------------------------------------


def get_random_video_ideas(market: str) -> Dict[int, Dict[str, str]]:
    """
    Returns 3 random video ideas for VEO.
    """
    base_ideas = [
        {
            "title": "Match day reaction",
            "concept": f"Fan in {market} reacting live to a big moment while using the app.",
        },
        {
            "title": "Halftime quick check",
            "concept": f"User checks live scores and bets on the app during halftime.",
        },
        {
            "title": "On the go update",
            "concept": f"Fan in {market} gets an app notification while in a taxi or at work and celebrates.",
        },
        {
            "title": "Group chat vibes",
            "concept": "Friends teasing the main character in the group chat until he finally downloads the app.",
        },
        {
            "title": "Before the match starts",
            "concept": "User opens the app to check fixtures and prepare predictions before kick off.",
        },
        {
            "title": "Weak network, still working",
            "concept": "User is in a place with bad reception but the app keeps working and updating.",
        },
    ]

    # Choose 3 unique ideas
    ideas = random.sample(base_ideas, 3)
    return {i + 1: ideas[i] for i in range(3)}


def get_random_image_ideas(market: str) -> Dict[int, Dict[str, str]]:
    """
    Returns 3 random image concepts for Whisk.
    """
    base_ideas = [
        {
            "title": "Big league spotlight",
            "concept": f"Focus on top leagues that fans in {market} love, with bold app branding and clear CTA.",
        },
        {
            "title": "Fan celebration close up",
            "concept": f"Close up on a happy fan face, stadium background, strong light on the phone hand, but screen not visible.",
        },
        {
            "title": "Multi match overview",
            "concept": "Dynamic layout with several match score cards around the main logo and big CTA button.",
        },
        {
            "title": "Notification moment",
            "concept": "Phone on a table with a bright notification bubble from the app and strong brand elements.",
        },
        {
            "title": "Clean minimal layout",
            "concept": "Simple background in brand colors, strong logo, one clear benefit line and big CTA.",
        },
        {
            "title": "Promo highlight",
            "concept": "Large promo numbers in the center, subtle football elements around, with logo and CTA at the bottom.",
        },
    ]

    ideas = random.sample(base_ideas, 3)
    return {i + 1: ideas[i] for i in range(3)}


# -------------------------------------------------
#  Prompt generation
# -------------------------------------------------


def build_veo_prompts(user_data: Dict[str, Any]) -> str:
    brand = user_data["brand"]
    market = user_data["market"]
    language = user_data["language"]
    style = user_data["style"]
    concept = user_data["concept"]
    length = user_data["video_length"]

    segments = max(1, math.ceil(length / 8))
    variations = 3

    lines = []
    for v in range(1, variations + 1):
        lines.append("-----")
        lines.append(f"{brand} - VEO video generation prompt")
        lines.append(f"Market: {market}")
        lines.append(f"Creative style: {style}")
        lines.append(f"Brand language: {language}")
        lines.append(f"Variation: {v}")
        lines.append(f"Total length: {length} seconds")
        lines.append("")

        # Concept wording
        if user_data.get("concept_mode") == "random":
            idea_title = user_data["ideas"][user_data["chosen_idea"]]["title"]
            base_concept = user_data["ideas"][user_data["chosen_idea"]]["concept"]
            lines.append("Concept:")
            lines.append(f"- Title: {idea_title}")
            lines.append(f"- Description: {base_concept}")
            lines.append(
                "- This variation should keep the same core idea but change the dialog, pacing and small details.",
            )
        else:
            lines.append("Concept:")
            lines.append(f"- General idea: {concept}")
            lines.append(
                "- This variation should use a slightly different point of view and dialog compared to the others.",
            )

        lines.append("")
        lines.append("Voice and language:")
        lines.append(f"- All dialog, voiceover and on screen text must be written in {language}.")
        lines.append("- Do not use Hebrew.")
        lines.append("- Natural, conversational tone that fits real fans.")
        lines.append("- No robotic phrasing.")
        lines.append("")

        lines.append("Camera and character guidelines:")
        lines.append("- Vertical 9:16 UGC style with natural handheld motion.")
        lines.append(
            "- Keep the same main actor, outfit, setting and lighting between all prompts in this variation.",
        )
        lines.append("- The actor holds a phone but the screen is never shown directly to camera.")
        lines.append("")

        lines.append("Structure:")
        lines.append(
            f"- Create {segments} separate VEO prompts. Each prompt is for a clip up to 8 seconds.",
        )
        for s in range(segments):
            start_s = s * 8 + 1
            end_s = min((s + 1) * 8, length)

            focus_options = [
                "strong emotional reaction",
                "smooth product focus on the app",
                "clear call to action",
                "natural fan behavior and small details in the background",
                "funny or relatable moment",
                "build up and payoff in the same micro scene",
            ]
            focus = random.choice(focus_options)

            example_dialog = build_example_dialog(language, market, brand)

            lines.append("")
            lines.append(f"Prompt {s + 1}: seconds {start_s} to {end_s}")
            lines.append(
                f"- Describe the exact framing, movement and actions for this part of the video. The focus here is {focus}.",
            )
            lines.append(
                "- Write the full spoken dialog line by line for this segment. Make sure the timing fits the number of seconds.",
            )
            lines.append(
                f"- Example of the kind of dialog you can use (write it properly in {language}):",
            )
            for d in example_dialog:
                lines.append(f"  {d}")

        lines.append("")
        lines.append("Important rules:")
        lines.append("- Never show the phone screen directly to the camera unless I say otherwise.")
        lines.append("- Avoid technical words like voiceover or scene description in the dialog text.")
        lines.append("- Keep everything in one consistent scene per prompt.")
        lines.append("- Make sure the final second of the last prompt has a strong and clear CTA.")
        lines.append("")

    return "\n".join(lines)


def build_example_dialog(language: str, market: str, brand: str):
    """
    Returns a small example dialog list. It is only for flavor inside the prompt.
    We keep it in English but instruct the model to write in the target language.
    """
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


def build_whisk_prompts(user_data: Dict[str, Any]) -> str:
    brand = user_data["brand"]
    market = user_data["market"]
    language = user_data["language"]
    style = user_data["style"]
    concept = user_data["concept"]

    variations = 3
    lines = []

    for v in range(1, variations + 1):
        lines.append("-----")
        lines.append(f"{brand} - Whisk image generation prompt")
        lines.append(f"Market: {market}")
        lines.append(f"Creative style: {style}")
        lines.append(f"Brand language: {language}")
        lines.append(f"Variation: {v}")
        lines.append("")

        if user_data.get("concept_mode") == "random":
            idea_title = user_data["ideas"][user_data["chosen_idea"]]["title"]
            base_concept = user_data["ideas"][user_data["chosen_idea"]]["concept"]
            lines.append("Concept:")
            lines.append(f"- Title: {idea_title}")
            lines.append(f"- Description: {base_concept}")
            lines.append(
                "- This variation should keep the same core idea but use a different composition and small details.",
            )
        else:
            lines.append("Concept:")
            lines.append(f"- General idea: {concept}")
            lines.append(
                "- This variation should use a different camera angle, layout or moment while keeping the same message.",
            )

        lines.append("")
        lines.append("Brand and language rules:")
        lines.append(f"- All text in the image must be in {language}.")
        lines.append("- Do not use Hebrew.")
        lines.append("- Show the app or brand as the main hero, not real teams or real players.")
        lines.append("")

        layout_focus_options = [
            "big central logo and CTA button",
            "strong promo numbers with smaller logo",
            "phone held in a hand with clear brand elements around it",
            "clean background in brand colors with simple icons",
        ]
        layout_focus = random.choice(layout_focus_options)

        lines.append("Layout and composition:")
        lines.append(f"- The layout focus for this variation is {layout_focus}.")
        lines.append("- Keep the design in vertical 9:16 format for mobile placement.")
        lines.append("- Use clear visual hierarchy so that logo and CTA are easy to read.")
        lines.append("- Avoid clutter and tiny unreadable text.")
        lines.append("")

        lines.append("Brand elements:")
        lines.append("- Use the official brand colors, logo and typography where possible.")
        lines.append("- Make sure the promo or key benefit is visible without zooming.")
        lines.append("- Never use photos of real teams or copyrighted logos.")
        lines.append("")

        lines.append("Text and CTA:")
        lines.append(f"- Main headline in {language} that is short, bold and easy to read.")
        lines.append("- One supporting line explaining the benefit.")
        lines.append("- Clear CTA like Download now or Play now at the bottom.")
        lines.append("")

    return "\n".join(lines)


# -------------------------------------------------
#  Telegram bot handlers
# -------------------------------------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    context.user_data.clear()

    keyboard = [
        [
            InlineKeyboardButton("VEO video prompts", callback_data="mode_video"),
        ],
        [
            InlineKeyboardButton("Whisk image prompts", callback_data="mode_image"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Hi {user.first_name}, I will help you build ready to use prompts.\n"
        "Choose what you want to create:",
        reply_markup=reply_markup,
    )
    return CHOOSING_TYPE


async def choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "mode_video":
        context.user_data["mode"] = "video"
        await query.edit_message_text(
            "Selected: VEO video prompts.\n\nFirst, send me the brand name."
        )
    else:
        context.user_data["mode"] = "image"
        await query.edit_message_text(
            "Selected: Whisk image prompts.\n\nFirst, send me the brand name."
        )

    return ASK_BRAND


async def ask_market(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["brand"] = update.message.text.strip()
    await update.message.reply_text("Great. What is the market? (example: argentina, south africa, italy)")
    return ASK_MARKET


async def ask_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["market"] = update.message.text.strip()
    await update.message.reply_text(
        "What is the brand language for scripts and text? (example: english, spanish, italian)",
    )
    return ASK_LANGUAGE


async def ask_style(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["language"] = update.message.text.strip()
    await update.message.reply_text(
        "What is the creative style? (example: UGC selfie, motion graphic, clean static banner)",
    )
    return ASK_STYLE


async def ask_concept_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["style"] = update.message.text.strip()

    keyboard = [
        [
            InlineKeyboardButton("Give me random ideas", callback_data="concept_random"),
        ],
        [
            InlineKeyboardButton("I want to describe my idea", callback_data="concept_custom"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Do you want me to suggest 3 random concepts or do you want to describe the general idea yourself?",
        reply_markup=reply_markup,
    )
    return ASK_CONCEPT_MODE


async def handle_concept_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    mode = context.user_data["mode"]
    market = context.user_data["market"]

    if query.data == "concept_random":
        context.user_data["concept_mode"] = "random"

        if mode == "video":
            ideas = get_random_video_ideas(market)
        else:
            ideas = get_random_image_ideas(market)

        context.user_data["ideas"] = ideas

        text_lines = ["I generated 3 ideas. Reply by pressing one of the buttons below.\n"]
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

    else:
        context.user_data["concept_mode"] = "custom"
        await query.edit_message_text(
            "Perfect. Send me a short description of the general idea for the creative."
        )
        return INPUT_CONCEPT


async def choose_idea_from_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    chosen = int(query.data.split("_")[1])
    context.user_data["chosen_idea"] = chosen
    context.user_data["concept"] = context.user_data["ideas"][chosen]["concept"]

    if context.user_data["mode"] == "video":
        await query.edit_message_text(
            "Nice, we will work with that idea.\n\nHow many seconds should the video be? "
            "For example: 8, 12, 16 or 24."
        )
        return ASK_VIDEO_LENGTH
    else:
        await query.edit_message_text("Nice, we will work with that idea. Generating Whisk prompts...")
        return await generate_prompts(update, context)


async def save_custom_concept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["concept"] = update.message.text.strip()

    if context.user_data["mode"] == "video":
        await update.message.reply_text(
            "Got it. How many seconds should the video be? For example: 8, 12, 16 or 24."
        )
        return ASK_VIDEO_LENGTH
    else:
        await update.message.reply_text("Got it. Generating Whisk prompts...")
        return await generate_prompts(update, context)


async def ask_video_length_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        length = int(text)
        if length <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please send a valid number of seconds, for example 8, 12, 16 or 24.")
        return ASK_VIDEO_LENGTH

    context.user_data["video_length"] = length
    await update.message.reply_text("Great. I am creating the full VEO prompts now...")
    return await generate_prompts(update, context)


async def generate_prompts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data
    mode = user_data["mode"]

    if mode == "video":
        result_text = build_veo_prompts(user_data)
    else:
        result_text = build_whisk_prompts(user_data)

    # Some prompts can be long, so we split them into smaller messages
    await send_long_message(update, context, result_text)

    await update.effective_message.reply_text(
        "Done. If you want to start again, send /start."
    )
    return ConversationHandler.END


async def send_long_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    chunk_size = 3500
    for i in range(0, len(text), chunk_size):
        chunk = text[i : i + chunk_size]
        await update.effective_message.reply_text(chunk)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Conversation cancelled. Send /start to begin again.")
    return ConversationHandler.END


# -------------------------------------------------
#  Main
# -------------------------------------------------


async def main():
    token = os.environ.get("TOKEN")
    if not token:
        raise RuntimeError("TOKEN environment variable is not set")

    application: Application = ApplicationBuilder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_TYPE: [CallbackQueryHandler(choose_type)],
            ASK_BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_market)],
            ASK_MARKET: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_language)],
            ASK_LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_style)],
            ASK_STYLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_concept_mode)],
            ASK_CONCEPT_MODE: [CallbackQueryHandler(handle_concept_mode)],
            INPUT_CONCEPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_custom_concept)],
            CHOOSE_IDEA_FROM_LIST: [CallbackQueryHandler(choose_idea_from_list)],
            ASK_VIDEO_LENGTH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_video_length_handler)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    application.add_handler(conv_handler)

    logger.info("Bot is starting with polling...")
    await application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

