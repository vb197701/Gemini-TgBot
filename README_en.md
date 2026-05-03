# Gemini_Telegram_Bot
Interact with the Gemini API via Telegram.
# Demo
[Click here](https://t.me/gemini_telegram_demo_bot)

# How to Install
## (1) On Linux
1. Install dependencies
```
pip install -r requirements.txt
```
2. Obtain Telegram Bot API at [BotFather](https://t.me/BotFather)
3. Get Gemini API keys from [Google AI Studio](https://makersuite.google.com/app/apikey)
4. Get your Telegram user id to use as the administrator id.
5. To run the bot, execute:
```
export TELEGRAM_BOT_API_KEY={Telegram Bot API}
export GEMINI_API_KEYS={Gemini API keys}
export ADMIN_USER_IDS={Your Telegram user id}
python src/main.py
```
By default, the bot stores selected models and recent chat history in `data/bot.db`. You can override this with `--db-path`.

## (2)Deploy Using Docker
### Use the built image
```
docker run -d --restart=always -v $(pwd)/data:/app/data -e TELEGRAM_BOT_API_KEY={Telegram Bot API} -e GEMINI_API_KEYS={Gemini API Key} -e ADMIN_USER_IDS={Your Telegram user id} qwqhthqwq/gemini-telegram-bot:main
```
### build by yourself
1. Get Telegram Bot API at [BotFather](https://t.me/BotFather)
2. Get Gemini API keys on [Google AI Studio](https://makersuite.google.com/app/apikey)
3. Clone repository
```
git clone https://github.com/H-T-H/Gemini-Telegram-Bot.git
```
4. Enter repository directory.
```
cd Gemini-Telegram-Bot
```
5. Build images
```
docker build -t gemini_tg_bot .
```
6. run
```
docker run -d --restart=always -v $(pwd)/data:/app/data -e TELEGRAM_BOT_API_KEY={Telegram Bot API} -e GEMINI_API_KEYS={Gemini API Key} -e ADMIN_USER_IDS={Your Telegram user id} gemini_tg_bot
```

# How to Use
1. Send your questions directly in a private chat.
2. In a group chat, use **/gemini** + your question. Photo is supported.
3. You can use the **/clear** command to delete the current conversation history.
4. You can use the **/model** command to choose or switch the model.
5. Unauthorized users automatically submit an access request on first use. Administrators can approve or reject requests with private chat buttons.
6. Administrators can use **/access** to list approved users, then revoke access with buttons.
7. Administrators can use **/accessrequest** to toggle new access requests.


# Reference
1. [https://github.com/yihong0618/tg_bot_collections](https://github.com/yihong0618/tg_bot_collections)
2. [https://github.com/yym68686/md2tgmd](https://github.com/yym68686/md2tgmd)
