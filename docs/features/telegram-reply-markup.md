### Quick Replies [Telegram]

**Product description:**

Some LLM messages can now contain multiple reply options (up to 3; this limit is required for WhatsApp compatibility), displayed as buttons.

When the user clicks a button, a message containing the selected option's text is sent to the bot on behalf of the user.

**Technical implementation:**

1. **Prompt.** For questions that require predefined reply options, we ask the LLM to respond using a simple JSON format:

```json
{
    "type": "reply_markup",
    "content": "<question text>",
    "reply_markup": ["option 1", "option 2", "option 3"]
}
```

*Maximum 3 options — the ones the LLM considers most likely.*

2. **Database.** Added a `reply_markup` column to the `messages` table: `TEXT[]` (migration `0002_add_reply_markup.sql`). PostgreSQL physically adds new columns at the end of the table, but I moved it to the middle for aesthetic reasons.

3. **LLM service.** When the LLM responds with `type=reply_markup`, `llm_service` parses the JSON into `text_content` (the question itself) and `reply_markup` (the list of options) and stores them in the corresponding columns in a single row.

4. **TelegramGateway.** `reply_markup` is converted into a `ReplyKeyboardMarkup` (a regular reply keyboard, not inline buttons) and passed as the `reply_markup` argument to `bot.send_message`. For now, this is supported only for `send_message`; it is not added to `send_document`.

5. **Click handling.** No separate click handling is required. When the user taps a `ReplyKeyboardMarkup` button, Telegram sends a regular text message to the bot containing the button's text.
