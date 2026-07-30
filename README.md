# Research Paper Alert Bot

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Telegram](https://img.shields.io/badge/Telegram-Open%20Bot-26A5E4?logo=telegram&logoColor=white)](https://t.me/cee_paper_alert_bot)
[![License](https://img.shields.io/badge/License-Not%20specified-lightgrey)](#license)
[![Status](https://img.shields.io/badge/Status-Active%20Development-orange)](#project-status)

A multi-source Telegram bot that helps researchers monitor newly published papers by topic. It searches academic databases, removes duplicate results, stores alert history, and sends notifications when previously unseen papers are found.

## Telegram Bot

**Bot username:** [@cee_paper_alert_bot](https://t.me/cee_paper_alert_bot)

[Open the bot on Telegram](https://t.me/cee_paper_alert_bot)

> The bot responds while the application is running on a local computer or a deployed server.

## Key Features

- Create topic-based research alerts
- Search multiple scholarly sources
- Combine and deduplicate paper results
- Store subscriptions and seen-paper history in SQLite
- Prevent repeated notifications for the same paper
- Run checks manually or automatically
- Display available commands when a user starts the bot
- Keep API keys and credentials outside the source code

## Supported Sources

| Source | Status |
|---|---|
| arXiv | Active |
| Crossref | Active |
| Europe PMC | Active |
| Semantic Scholar | Optional API key required |

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Display the welcome message and command guide |
| `/watch <topic>` | Create a research-paper alert |
| `/list` | Show saved alerts |
| `/checknow` | Check saved topics immediately |
| `/delete <alert_id>` | Delete an alert |
| `/sources` | Show available academic sources |

### Example

```text
/watch pharmaceutical drug delivery systems
```

## How It Works

```text
Telegram User
      │
      │  /watch <research topic>
      ▼
Research Paper Alert Bot
      │
      ├── arXiv
      ├── Crossref
      ├── Europe PMC
      └── Semantic Scholar (optional)
      │
      ▼
Merge and deduplicate results
      │
      ▼
SQLite database
      │
      ├── subscriptions
      ├── seen_papers
      └── alert_sources
      │
      ▼
Notify the user about unseen papers
```

## Project Structure

```text
research-paper-alert-bot/
├── app.py
├── arxiv_client.py
├── crossref_client.py
├── database.py
├── europe_pmc_client.py
├── paper_link_utils.py
├── paper_sources.py
├── semantic_scholar_client.py
├── requirements.txt
├── railway.json
├── .python-version
├── .env.example
├── .gitignore
└── README.md
```

## Local Installation

### 1. Clone the repository

```bash
git clone https://github.com/farzana-rahman-orpa/research-paper-alert-bot.git
cd research-paper-alert-bot
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Create the environment file

```bash
cp .env.example .env
```

Add your private values to `.env`:

```env
TELEGRAM_BOT_TOKEN=your_botfather_token
CROSSREF_CONTACT_EMAIL=your_email@example.com
SEMANTIC_SCHOLAR_API_KEY=
DATABASE_PATH=paperwatch.db
```

### 5. Run the application

```bash
python app.py
```

## Database

The project uses SQLite. By default, local data is stored in:

```text
paperwatch.db
```

The database contains lightweight metadata such as:

- Telegram chat ID
- Research topic
- Alert ID
- Paper title
- Paper URL
- Academic source
- Date recorded

The project does not download or store full research-paper PDFs.

## Security

Sensitive and machine-specific files are excluded through `.gitignore`, including:

```text
.env
.venv/
paperwatch.db
__pycache__/
```

Never commit:

- Telegram bot tokens
- API keys
- Private `.env` files
- Local database files

## Deployment

For continuous availability, run the application on a server or cloud platform.

When running locally, the Python process must remain active. Closing the terminal, shutting down the computer, or interrupting the process will stop the bot temporarily. Saved alerts remain in the SQLite database.

## Planned Improvements

- 24/7 cloud deployment
- Improved relevance scoring
- Daily and weekly digest options
- User-selected notification schedules
- AI-generated paper summaries
- Web dashboard
- PostgreSQL support for larger deployments

## Author

**Farzana Rahman**

- GitHub: [farzana-rahman-orpa](https://github.com/farzana-rahman-orpa)
- Telegram Bot: [@cee_paper_alert_bot](https://t.me/cee_paper_alert_bot)

## Project Status

This project is under active development and is intended for research support, learning, and portfolio use.

## License

No open-source license has been added yet.
