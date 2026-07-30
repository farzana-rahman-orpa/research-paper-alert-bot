import asyncio
import os

from dotenv import load_dotenv
from telegram import BotCommand, LinkPreviewOptions, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from database import (
    add_subscription,
    delete_subscription,
    get_all_subscriptions,
    get_initialized_sources,
    get_subscriptions,
    initialize_database,
    mark_sources_initialized,
    save_existing_papers,
    save_seen_paper,
)
from paper_sources import search_all_sources


load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

SEMANTIC_SCHOLAR_KEY = os.getenv(
    "SEMANTIC_SCHOLAR_API_KEY",
    "",
).strip()

SEARCH_LIMIT_PER_SOURCE = 10
DISPLAY_LIMIT = 4

CHECK_INTERVAL_SECONDS = 24 * 60 * 60
ALERT_DELAY_SECONDS = 3

NO_LINK_PREVIEW = LinkPreviewOptions(
    is_disabled=True,
)


def active_source_names() -> list[str]:
    """Return the currently active sources."""

    sources = [
        "arXiv",
        "Crossref",
        "Europe PMC",
    ]

    if SEMANTIC_SCHOLAR_KEY:
        sources.append("Semantic Scholar")

    return sources


def format_authors(authors: list[str]) -> str:
    """Create a short author list."""

    if not authors:
        return "Unknown"

    author_text = ", ".join(authors[:3])

    if len(authors) > 3:
        author_text += ", and others"

    return author_text


def choose_diverse_papers(
    papers: list[dict],
    limit: int,
) -> list[dict]:
    """Select papers from different sources where possible."""

    selected: list[dict] = []
    selected_keys = set()
    used_sources = set()

    for paper in papers:
        source = paper.get(
            "source",
            "Unknown",
        )

        if source in used_sources:
            continue

        selected.append(paper)
        used_sources.add(source)

        selected_keys.add(
            paper.get("paper_key")
            or paper.get("url")
        )

        if len(selected) >= limit:
            return selected

    for paper in papers:
        paper_identifier = (
            paper.get("paper_key")
            or paper.get("url")
        )

        if paper_identifier in selected_keys:
            continue

        selected.append(paper)
        selected_keys.add(paper_identifier)

        if len(selected) >= limit:
            break

    return selected


def format_paper_notification(
    research_topic: str,
    paper: dict,
) -> str:
    """Create a notification for one new paper."""

    return (
        "🆕 New research paper found!\n\n"
        f"{paper['title']}\n\n"
        "Authors: "
        f"{format_authors(paper['authors'])}\n"
        f"Published: {paper['published']}\n"
        f"Source: {paper['source']}\n"
        f"Matched topic: {research_topic}\n\n"
        f"Link: {paper['url']}"
    )


async def set_bot_commands(
    application: Application,
) -> None:
    """Register commands in Telegram's command menu."""

    commands = [
        BotCommand(
            "start",
            "Show the welcome message and instructions",
        ),
        BotCommand(
            "watch",
            "Create a research-paper alert",
        ),
        BotCommand(
            "list",
            "Show your saved alerts",
        ),
        BotCommand(
            "checknow",
            "Check your saved alerts now",
        ),
        BotCommand(
            "delete",
            "Delete a saved alert by its ID",
        ),
        BotCommand(
            "sources",
            "Show available academic sources",
        ),
    ]

    await application.bot.set_my_commands(commands)

    print(
        "Telegram command menu registered successfully."
    )


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Show the welcome message and all available commands."""

    del context

    message = update.effective_message

    if message is None:
        return

    user = update.effective_user

    first_name = (
        user.first_name
        if user and user.first_name
        else "Researcher"
    )

    sources_text = "\n".join(
        f"• {source}"
        for source in active_source_names()
    )

    welcome_text = (
        f"👋 Welcome, {first_name}!\n\n"
        "📚 I am the Research Paper Alert Bot.\n"
        "I monitor academic sources and notify you "
        "when unseen papers are found for your topics.\n\n"
        f"🌐 Active sources:\n{sources_text}\n\n"
        "📌 Available commands\n\n"
        "🔎 /watch <topic>\n"
        "Create and save a research-paper alert.\n"
        "Example:\n"
        "/watch pharmaceutical drug delivery systems\n\n"
        "📋 /list\n"
        "Show all your saved alerts and alert IDs.\n\n"
        "🔄 /checknow\n"
        "Check all your saved topics immediately.\n\n"
        "🗑️ /delete <alert_id>\n"
        "Permanently delete a saved alert.\n"
        "Example:\n"
        "/delete 1\n\n"
        "🌐 /sources\n"
        "Show the academic sources currently available.\n\n"
        "ℹ️ /start\n"
        "Show this welcome message again.\n\n"
        "Saved alerts are checked automatically "
        "once per day while the bot is running.\n\n"
        "To begin, send:\n"
        "/watch your research topic"
    )

    await message.reply_text(
        welcome_text,
        link_preview_options=NO_LINK_PREVIEW,
    )


async def sources_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Show active paper sources."""

    del context

    message = update.effective_message

    if message is None:
        return

    source_lines = [
        "📚 Active research-paper sources:"
    ]

    for source in active_source_names():
        source_lines.append(
            f"✅ {source}"
        )

    if not SEMANTIC_SCHOLAR_KEY:
        source_lines.append(
            "⏳ Semantic Scholar: waiting "
            "for API key"
        )

    await message.reply_text(
        "\n".join(source_lines)
    )


async def watch(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Create an alert and show matching papers."""

    message = update.effective_message
    chat = update.effective_chat

    if message is None or chat is None:
        return

    if not context.args:
        await message.reply_text(
            "Please write a research topic "
            "after /watch.\n\n"
            "Example:\n"
            "/watch machine learning for "
            "cancer diagnosis"
        )
        return

    research_topic = " ".join(
        context.args
    ).strip()

    chat_id = chat.id

    status_message = await message.reply_text(
        "🔎 Searching available sources for:\n"
        f"{research_topic}"
    )

    try:
        (
            papers,
            successful_sources,
        ) = await search_all_sources(
            research_topic,
            max_results_per_source=(
                SEARCH_LIMIT_PER_SOURCE
            ),
        )

    except Exception as error:
        print(f"Paper search error: {error}")

        await status_message.edit_text(
            "❌ All paper sources failed.\n"
            "Please try again later.",
            link_preview_options=NO_LINK_PREVIEW,
        )
        return

    if not papers:
        await status_message.edit_text(
            "No matching papers were found.\n\n"
            "Try using fewer or more general "
            "keywords."
        )
        return

    alert_id = add_subscription(
        chat_id,
        research_topic,
    )

    if alert_id is None:
        saving_message = (
            "ℹ️ This topic is already "
            "in your watch list."
        )

    else:
        baseline_count = save_existing_papers(
            alert_id,
            papers,
        )

        if successful_sources:
            mark_sources_initialized(
                alert_id,
                successful_sources,
            )

        saving_message = (
            "✅ Topic saved successfully!\n"
            f"Alert ID: {alert_id}\n"
            "Existing unique papers recorded: "
            f"{baseline_count}"
        )

    display_papers = choose_diverse_papers(
        papers,
        DISPLAY_LIMIT,
    )

    response_parts = [
        saving_message,
        f"🔎 Topic: {research_topic}",
        "📚 Matching papers:",
    ]

    for number, paper in enumerate(
        display_papers,
        start=1,
    ):
        response_parts.append(
            f"{number}. {paper['title']}\n"
            "Authors: "
            f"{format_authors(paper['authors'])}\n"
            f"Published: {paper['published']}\n"
            f"Source: {paper['source']}\n"
            f"Link: {paper['url']}"
        )

    response_parts.append(
        "Current results were recorded. "
        "Only unseen papers will be "
        "notified later."
    )

    await status_message.edit_text(
        "\n\n".join(response_parts),
        link_preview_options=NO_LINK_PREVIEW,
    )


async def list_topics(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Display saved alerts."""

    del context

    message = update.effective_message
    chat = update.effective_chat

    if message is None or chat is None:
        return

    subscriptions = get_subscriptions(
        chat.id
    )

    if not subscriptions:
        await message.reply_text(
            "You do not have any saved alerts.\n\n"
            "Create one using:\n"
            "/watch your research topic"
        )
        return

    response_lines = [
        "📋 Your saved research alerts:"
    ]

    for subscription in subscriptions:
        response_lines.append(
            f"{subscription['id']}. "
            f"{subscription['research_topic']}"
        )

    response_lines.append(
        "\nDelete an alert using:\n"
        "/delete alert_id"
    )

    await message.reply_text(
        "\n\n".join(response_lines)
    )


async def delete_topic(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Delete an alert permanently."""

    message = update.effective_message
    chat = update.effective_chat

    if message is None or chat is None:
        return

    if (
        len(context.args) != 1
        or not context.args[0].isdigit()
    ):
        await message.reply_text(
            "Please provide one numeric ID.\n\n"
            "Example:\n"
            "/delete 2"
        )
        return

    alert_id = int(
        context.args[0]
    )

    deleted = delete_subscription(
        chat.id,
        alert_id,
    )

    if deleted:
        await message.reply_text(
            f"🗑️ Alert {alert_id} was deleted.\n"
            "No more notifications will be "
            "sent for that topic."
        )

    else:
        await message.reply_text(
            "I could not find that alert.\n"
            "Use /list to see your alert IDs."
        )


async def process_subscriptions(
    bot,
    subscriptions,
) -> tuple[int, int, int]:
    """
    Check subscriptions for new papers.

    Newly enabled research sources are initialized first so
    their older papers are not incorrectly sent as new.
    """

    new_count = 0
    initialized_alert_count = 0
    failed_count = 0

    for index, subscription in enumerate(
        subscriptions
    ):
        alert_id = int(
            subscription["id"]
        )

        chat_id = int(
            subscription["chat_id"]
        )

        topic = str(
            subscription["research_topic"]
        )

        try:
            (
                papers,
                successful_sources,
            ) = await search_all_sources(
                topic,
                max_results_per_source=(
                    SEARCH_LIMIT_PER_SOURCE
                ),
            )

        except Exception as error:
            print(
                f"Alert {alert_id} failed: {error}"
            )

            failed_count += 1
            papers = []
            successful_sources = set()

        if papers or successful_sources:
            initialized_sources = (
                get_initialized_sources(
                    alert_id
                )
            )

            new_sources = (
                successful_sources
                - initialized_sources
            )

            # Record old papers from a newly enabled source
            # without sending them as new notifications.
            if new_sources:
                baseline_papers = [
                    paper
                    for paper in papers
                    if str(
                        paper.get("source", "")
                    ) in new_sources
                ]

                save_existing_papers(
                    alert_id,
                    baseline_papers,
                )

                mark_sources_initialized(
                    alert_id,
                    new_sources,
                )

                initialized_alert_count += 1

            for paper in reversed(papers):
                source = str(
                    paper.get("source", "")
                )

                if source in new_sources:
                    continue

                paper_url = str(
                    paper.get("url", "")
                ).strip()

                paper_title = str(
                    paper.get("title", "")
                ).strip()

                if not paper_url or not paper_title:
                    continue

                is_new = save_seen_paper(
                    alert_id=alert_id,
                    paper_url=paper_url,
                    paper_title=paper_title,
                )

                if not is_new:
                    continue

                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=format_paper_notification(
                            topic,
                            paper,
                        ),
                        link_preview_options=(
                            NO_LINK_PREVIEW
                        ),
                    )

                    new_count += 1

                except Exception as error:
                    print(
                        "Telegram notification failed: "
                        f"{error}"
                    )

        if index < len(subscriptions) - 1:
            await asyncio.sleep(
                ALERT_DELAY_SECONDS
            )

    return (
        new_count,
        initialized_alert_count,
        failed_count,
    )


async def check_now(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Manually check the user's alerts."""

    message = update.effective_message
    chat = update.effective_chat

    if message is None or chat is None:
        return

    subscriptions = get_subscriptions(
        chat.id
    )

    if not subscriptions:
        await message.reply_text(
            "You do not have alerts to check.\n\n"
            "Create one using:\n"
            "/watch your research topic"
        )
        return

    status_message = await message.reply_text(
        f"🔄 Checking "
        f"{len(subscriptions)} alert(s)..."
    )

    (
        new_count,
        initialized_count,
        failed_count,
    ) = await process_subscriptions(
        context.bot,
        subscriptions,
    )

    summary = [
        "✅ Paper check complete.",
        f"New papers found: {new_count}",
    ]

    if initialized_count:
        summary.append(
            "New sources initialized: "
            f"{initialized_count}"
        )

    if failed_count:
        summary.append(
            "Alerts that failed: "
            f"{failed_count}"
        )

    if new_count == 0:
        summary.append(
            "No unseen papers were found."
        )

    await status_message.edit_text(
        "\n".join(summary)
    )


async def automatic_check(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Automatically check all saved alerts."""

    subscriptions = (
        get_all_subscriptions()
    )

    if not subscriptions:
        print(
            "Automatic check: no alerts."
        )
        return

    print(
        "Automatic check started for "
        f"{len(subscriptions)} alert(s)."
    )

    results = await process_subscriptions(
        context.bot,
        subscriptions,
    )

    print(
        "Automatic check finished. "
        f"New: {results[0]}; "
        f"initialized: {results[1]}; "
        f"failed: {results[2]}."
    )


def main() -> None:
    """Create and run the Telegram bot."""

    if not BOT_TOKEN:
        raise RuntimeError(
            "Telegram token was not found. "
            "Add TELEGRAM_BOT_TOKEN to your .env file."
        )

    initialize_database()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(set_bot_commands)
        .build()
    )

    if application.job_queue is None:
        raise RuntimeError(
            "JobQueue is unavailable."
        )

    application.job_queue.run_repeating(
        automatic_check,
        interval=CHECK_INTERVAL_SECONDS,
        first=CHECK_INTERVAL_SECONDS,
        name="automatic-paper-check",
    )

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "sources",
            sources_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "watch",
            watch,
        )
    )

    application.add_handler(
        CommandHandler(
            "list",
            list_topics,
        )
    )

    application.add_handler(
        CommandHandler(
            "delete",
            delete_topic,
        )
    )

    application.add_handler(
        CommandHandler(
            "checknow",
            check_now,
        )
    )

    print(
        "Research Paper Alert Bot is running..."
    )

    print(
        "Active sources: "
        + ", ".join(
            active_source_names()
        )
    )

    application.run_polling()


if __name__ == "__main__":
    main()
