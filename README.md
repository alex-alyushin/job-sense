## Job Sense

Analyzes your CV and finds the most relevant job opportunities for you.

### Problem Description

Imagine you are looking for a new job. The process can be quite tedious because you have to:

* visit multiple platforms such as LinkedIn, Glassdoor, Indeed, and others;
* configure search parameters on each platform;
* manually review a large number of often similar job postings;
* repeat the process regularly as new jobs are constantly being posted.

**Job Sense** automates this process:

* the user uploads their resume;
* an LLM clarifies their requirements and generates a search query;
* the query is sent to a job provider that collects job postings from multiple sources;
* the results are ranked, and the 3–5 most relevant jobs are selected.

The search query is saved and automatically executed once a day to find only jobs posted within the last 24 hours.

### Interface

Users interact with the system through one of the supported messengers Telegram or WhatsApp  *(whatsapp coming soon)* .

The choice of messenger depends on its popularity in the target market. Using a messenger instead of a dedicated website also makes user acquisition easier, as users can access the service through a platform they already use on a daily basis.

### Architecture

The system consists of three independent components:

* **TelegramGateway** — handles communication with the Telegram API and forwards messages to the system.
* **LLMService** — handles interaction with the OpenAI API and processes user messages.
* **SearchService** — searches for job postings and performs the final ranking.
* **ReportService** — formats the selected job postings and delivers them back to the user.

All four components run independently and synchronize through PostgreSQL using the **LISTEN / NOTIFY** pattern.

### Local Run

#### Prepare the Environment

Create a new Telegram bot with [@BotFather](https://t.me/botfather) and store the authentication token in `.env`:

```env
TELEGRAM_TOKEN=<token>
```

Create an [OpenAI API key](https://openai.com/api) if you don't already have one. Choose a model and store both the API key and model name in `.env`:

```env
OPENAI_TOKEN=<token>
OPENAI_MODEL=gpt-5.4-mini
```

[Bright Data](https://docs.brightdata.com/api-reference/authentication) is used to retrieve job postings. The free tier includes 5,000 searches per month and does not require a credit card. Create an API key and store it in `.env`:

```env
BRIGHT_DATA_TOKEN=<token>
```

Configure the `POSTGRES_*` variables: host, database name, username, and password.

Finally, set `GRAFANA_ADMIN_PASSWORD` for the Grafana dashboard.

#### Software Requirements

You must have the following software installed:

* Python **3.14+**
* [uv](https://docs.astral.sh/uv/) — package manager
* Docker — used to run PostgreSQL and Grafana

#### Install Dependencies

```bash
uv sync
```

#### Initialize PostgreSQL Tables

To initialize the PostgreSQL database, run the following command:

```bash
make db
```

> **Warning:** This command will delete all existing data and recreate the database tables. Make sure you don't have any important data before running it.

#### Run

Everything can be started with a single command:

```bash
make up
```

This command starts PostgreSQL and Grafana containers in the background and runs all application services **TelegramGateway**, **LLMService**, **SearchService**, and **ReportService** in a single terminal.

The logs of each service are color-coded, making it easy to distinguish between them.

### Deployment

Job Sense is deployed and available on Telegram: [@job_sense_bot](https://t.me/job_sense_bot).

### Using Job Sense

Start a conversation with the Telegram bot. Upload your resume, ask for advice, and describe your job preferences. Finally, ask Job Sense to find the job postings that are most relevant to your requirements.
