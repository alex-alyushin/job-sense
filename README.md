## Job Sense

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
* the results are then ranked, and the 3–5 most relevant jobs are selected.

The search query is saved and automatically executed once a day to find only jobs posted within the last 24 hours.

### Interface

Users interact with the system through one of the supported messengers - Telegram or WhatsApp.

The choice of messenger depends on its popularity in the target market. Using a messenger instead of a dedicated website also makes user acquisition easier, as users can access the service through a platform they already use on a daily basis.

> Only Telegram is implemented in the first version.

### Architecture

The system consists of three independent components:

* **TelegramGateway** — handles communication with the Telegram API and forwards messages to the system.
* **LLMService** — handles interaction with the OpenAI API and processes user messages.
* **SearchService** *(coming soon)* — searches for job postings and performs the final ranking.

All three components run independently and synchronize through PostgreSQL using the **LISTEN/NOTIFY** pattern.

### Local Setup

#### Requirements

* Python **3.14+**
* [uv](https://docs.astral.sh/uv/) — package manager
* Docker — used to run PostgreSQL and Grafana

#### External APIs

You will need:

* An OpenAI account, or an OpenAI-compatible provider such as Groq, Gemini, or Ollama
* A Telegram bot token
* A Bright Data token

### Running Locally

There is currently no single command to start everything. `main.py` is still a placeholder, so the services need to be started separately.

Start PostgreSQL:

   ```bash
   make postgres
   ```

Initialize the database schema:

   ```bash
   uv run python store/db_init.py
   ```

   This creates the `messages` table. **Warning:** the script drops the table first if it already exists.

Start the Telegram gateway in a separate terminal:

   ```bash
   make telegram
   ```

Start the LLM service in another terminal:

   ```bash
   make llm
   ```

Optionally, start Grafana for monitoring:

   ```bash
   make monitoring
   ```

Alternatively, you can start everything with a single command:

```bash
make up
```
