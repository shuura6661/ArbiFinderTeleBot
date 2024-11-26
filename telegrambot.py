import requests
import time
from datetime import datetime
import asyncio
from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Telegram Bot setup
TELEGRAM_TOKEN = '7922797756:AAHYIgft2Appv1TM8nOYMcsm5mVDlqsYquI'  # Replace with your token
CHAT_ID = '5977807502'  # Replace with your chat ID

bot = Bot(token=TELEGRAM_TOKEN)

# Global variables
is_running = False
threshold_percentage = 2  # Default arbitrage threshold percentage
awaiting_threshold_value = False  # Flag to indicate that we're waiting for a threshold value from the user


# Function to fetch Binance data
def get_binance_data():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return {item['symbol']: item for item in data}
    except requests.RequestException as e:
        print(f"Error fetching Binance data: {e}")
        return {}


# Function to fetch Indodax data
def get_indodax_data():
    url = "https://indodax.com/api/ticker_all"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json().get('tickers', {})
        return data
    except requests.RequestException as e:
        print(f"Error fetching Indodax data: {e}")
        return {}


# Function to find arbitrage opportunity
async def find_arbitrage():
    global threshold_percentage
    binance_data = get_binance_data()
    indodax_data = get_indodax_data()

    # Load symbols from file
    try:
        with open('symbols_to_check.txt', 'r') as f:
            symbols_to_check = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("symbols_to_check.txt file not found.")
        return

    for symbol in symbols_to_check:
        binance_symbol = symbol.replace("/", "")
        indodax_symbol_idr = symbol.lower().replace("/", "_").replace(
            "usdt", "idr")

        if binance_symbol not in binance_data or indodax_symbol_idr not in indodax_data:
            continue

        binance_ask = float(binance_data[binance_symbol].get(
            'askPrice', float('inf')))
        binance_bid = float(binance_data[binance_symbol].get('bidPrice', 0))
        indodax_ask_idr = float(indodax_data[indodax_symbol_idr].get(
            'sell', float('inf')))
        indodax_bid_idr = float(indodax_data[indodax_symbol_idr].get('buy', 0))

        # Convert Indodax prices from IDR to USDT
        usdt_idr_rate = float(indodax_data.get('usdt_idr', {}).get('last', 0))
        if usdt_idr_rate == 0:
            continue

        indodax_ask = indodax_ask_idr / usdt_idr_rate
        indodax_bid = indodax_bid_idr / usdt_idr_rate

        best_buy_price = min(binance_ask, indodax_ask)
        best_sell_price = max(binance_bid, indodax_bid)

        if best_buy_price > 0 and best_sell_price > best_buy_price:
            difference = (
                (best_sell_price - best_buy_price) / best_buy_price) * 100
            if difference > threshold_percentage:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Generate the trade URLs for Binance and Indodax
                binance_url = f"https://www.binance.com/id/trade/{binance_symbol}?type=spot"
                indodax_url = f"https://indodax.com/market/{binance_symbol.replace('USDT', 'IDR')}"

                message = (
                    f"[{current_time}] Arbitrage Opportunity for {symbol}!\n"
                    f"[Buy at Binance]({binance_url}) for {best_buy_price}\n"
                    f"[Sell at Indodax]({indodax_url}) for {best_sell_price}\n"
                    f"Potential Profit: {difference:.2f}%\n"
                    f"If investing 10,000,000 IDR, Potential Profit: {(10000000 * difference) / 100:,.2f} IDR\n"
                )
                await bot.send_message(chat_id=CHAT_ID,
                                       text=message,
                                       parse_mode=ParseMode.MARKDOWN,
                                       disable_web_page_preview=True)


# Command to start the bot
# Command to start the bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Arbitrage Bot Running...")
    await find_arbitrage()  # Run arbitrage check once when starting


# Command to stop the bot
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_running
    if is_running:
        is_running = False
        await update.message.reply_text("Arbitrage Bot Stopped.")
    else:
        await update.message.reply_text("Arbitrage Bot is not running.")


# Command to ask for a new threshold value
async def set_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global awaiting_threshold_value
    awaiting_threshold_value = True
    await update.message.reply_text("Set your percentage value in number!")


# Handler for text messages to receive the threshold value from the user
async def threshold_value_handler(update: Update,
                                  context: ContextTypes.DEFAULT_TYPE):
    global threshold_percentage, awaiting_threshold_value
    if awaiting_threshold_value:
        try:
            new_threshold = float(update.message.text)
            threshold_percentage = new_threshold
            awaiting_threshold_value = False
            await update.message.reply_text(
                f"Threshold percentage set to {new_threshold}%")
        except ValueError:
            await update.message.reply_text(
                "Invalid value. Please enter a valid number.")


# Command to check bot status
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_running
    status_message = "Arbitrage Bot is running." if is_running else "Arbitrage Bot is stopped."
    await update.message.reply_text(status_message)


# Main function to set up the bot and commands
if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("set_threshold", set_threshold))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND,
                       threshold_value_handler))

    application.run_polling()
