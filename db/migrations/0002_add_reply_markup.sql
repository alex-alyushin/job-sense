-- migrate:up

ALTER TABLE messages ADD COLUMN reply_markup TEXT[];

-- migrate:down

ALTER TABLE messages DROP COLUMN reply_markup;
