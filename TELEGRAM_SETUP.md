# Telegram Notifications Setup

This bot can send real-time trade notifications to your Telegram account, including:
- Trade details (action, symbol, amount, price, fees)
- Balance before/after
- Profit/Loss calculations
- Trading statistics (total trades, win rate)

## Setup Instructions

### Step 1: Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Start a chat with BotFather
3. Send `/newbot` command
4. Follow the prompts to choose a name and username for your bot
5. BotFather will give you an **API token** that looks like:
   ```
   123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
6. Copy this token - you'll need it for Step 3

### Step 2: Get Your Chat ID

1. Start a conversation with your new bot (click the link BotFather provided)
2. Send any message to your bot (e.g., "Hello")
3. Open this URL in your browser, replacing `<YOUR_BOT_TOKEN>` with the token from Step 1:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
4. Look for the `"chat"` object in the JSON response and find the `"id"` field:
   ```json
   {
     "message": {
       "chat": {
         "id": 123456789,  <-- This is your chat ID
         "type": "private"
       }
     }
   }
   ```
5. Copy this chat ID - you'll need it for Step 3

### Step 3: Configure Your Bot

1. Open the `.env` file in your project root
2. Add your bot token and chat ID:
   ```env
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   TELEGRAM_CHAT_ID=123456789
   ```
3. Save the file
4. Restart your trading bot for the changes to take effect

## What You'll Receive

### Buy Trade Notification
```
🟢 💰 LIVE - BUY BTCUSD

📊 Trade Details:
• Amount: 0.01000000 BTC
• Price: $95,234.50
• Gross Value: $952.35
• Fee: $2.48
• Net Value: $954.83

💵 Balance:
• Before: $10,000.00
• After: $9,045.17
• Change: 📉 -$954.83

📈 Stats:
• Total Trades: 15
• Win Rate: 66.7%

💡 Reason: Strong bullish sentiment with high volume

🕐 2025-10-26 00:30:15 UTC
```

### Sell Trade Notification
```
🔴 💰 LIVE - SELL BTCUSD

📊 Trade Details:
• Amount: 0.01000000 BTC
• Price: $97,500.00
• Gross Value: $975.00
• Fee: $2.54
• Net Value: $972.46

💵 Balance:
• Before: $9,045.17
• After: $10,017.63
• Change: 📈 +$972.46

✅ Performance:
• P/L: +$17.63 (+1.85%)

📈 Stats:
• Total Trades: 16
• Win Rate: 68.8%

💡 Reason: Take profit target reached

🕐 2025-10-26 01:45:22 UTC
```

## Troubleshooting

### Not receiving notifications?

1. **Check your bot token and chat ID are correct**
   - Make sure there are no spaces or extra characters
   - Verify the chat ID is a number (not a username)

2. **Make sure you've started a conversation with your bot**
   - You must send at least one message to your bot first
   - The bot cannot initiate conversations

3. **Check the logs for errors**
   - Look for `[Telegram]` entries in your bot's console output
   - Common errors will be logged there

4. **Test the connection manually**
   ```bash
   curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage" \
        -H "Content-Type: application/json" \
        -d '{"chat_id": <YOUR_CHAT_ID>, "text": "Test message"}'
   ```

### Notifications disabled warning

If you see this in your logs:
```
[Telegram] Notifications disabled: Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID
```

This means the bot couldn't find your credentials in the `.env` file. Make sure:
- The `.env` file exists in the project root
- The environment variables are set correctly
- You've restarted the bot after adding the credentials

## Disabling Notifications

To temporarily disable notifications, simply remove or comment out the environment variables in your `.env` file:

```env
# TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
# TELEGRAM_CHAT_ID=123456789
```

The bot will automatically detect that notifications are disabled and skip sending messages.
