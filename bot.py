import os
import logging

from telegram import *
from telegram.ext import *

from ctftime_client import CTFTimeClient
from dbs import CTFDb, GroupDb

db = CTFDb()
groups = GroupDb()

TOKEN = os.environ['BOT_TOKEN']

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - \
                            %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)


def error(bot, update, error):
    logger.warning('Update "%s" caused error "%s"' % (update, error))


def start(bot, update):
    """Start the bot reminder about starting and announced CTF"""
    groups.add(update.message.chat_id)
    update.message.reply_text('Hi! I will notify you when new CTFs \
are announced and remind them!')


def stop(bot, update):
    """Start the bot reminder about starting and announced CTF"""
    groups.remove(update.message.chat_id)
    update.message.reply_text('Stopped')


def fetch(bot, job):
    """Job function to check for newly announced CTFs"""
    to_print = db.add_events(CTFTimeClient.fetch_data())
    if to_print is []:
        return

    message = ""
    for ctf in to_print:
        message += db.starting_message(ctf)

    if message is not "":
        message = "*New CTF announced:*\n" + message
        for element in groups.groups:
            bot.sendMessage(element,
                            text=message,
                            parse_mode='MARKDOWN',
                            disable_web_page_preview=True)


def starting(bot, job):
    """Job function to check for newly announced CTFs"""
    to_print = db.starting_ctf()
    if to_print is []:
        return

    message = ""
    for ctf in to_print:
        message += db.starting_message(ctf)

    if message is not "":
        message = "*The following CTF are starting in less than 24 hours:*\n" + message
        for element in groups.groups:
            bot.sendMessage(element,
                            text=message,
                            parse_mode='MARKDOWN',
                            disable_web_page_preview=True)


def upcoming(bot, update):
    """List 5 upcoming CTFs in database"""
    message = ""
    for ctf in db.upcoming():
        message += db.starting_message(ctf)

    if message is not "":
        message = "*Upcoming events:*\n" + message
        bot.sendMessage(update.message.chat_id,
                        text=message,
                        parse_mode='MARKDOWN',
                        disable_web_page_preview=True)
    else:
        bot.sendMessage(update.message.chat_id,
                        text="No upcoming CTF")


def current(bot, update):
    """List current running CTFs in database"""
    message = ""
    for ctf in db.running():
        message += db.finishing_message(ctf)

    if message is not "":
        message = "*Now running events:*\n" + message
        bot.sendMessage(update.message.chat_id,
                        text=message,
                        parse_mode='MARKDOWN',
                        disable_web_page_preview=True)
    else:
        bot.sendMessage(update.message.chat_id,
                        text="No CTF is currently running")


def info(bot, update, args):
    """Get info form a given CTFid"""
    if len(args) != 1:
        update.message.reply_text('Usage: `/info <ctf_id>`',
                                  parse_mode='MARKDOWN')
        return

    update.message.reply_text(db.get_info_message(args[0]),
                              parse_mode='MARKDOWN',
                              disable_web_page_preview=True)


def ping(bot, update):
    """Classic ping command"""
    message = "Pong. I'm not running in this group! Start me with `/start`"
    if update.message.chat_id in groups.groups:
        message = "Pong."

    update.message.reply_text(message, parse_mode='MARKDOWN')


def usage(bot, update):
    message = "*CTF Reminder* will remind your CTF as they start!\n"
    message += "`/start` to start the reminder\n"
    message += "`/stop` to stop the reminder\n"
    message += "`/upcoming` to list all the upcoming CTFs\n"
    message += "`/now` or `/current` to list all the currently running CTFs\n"
    message += "`/info <ctf_id>` to get info for specific CTF\n"
    message += "`/ping` to check if the reminder is started\n"
    message += "\nGet the bot [Source Code]"
    message += "(https://github.com/TheZ3ro/ctf_reminder)"
    update.message.reply_text(message, parse_mode='MARKDOWN',
                              disable_web_page_preview=True)


def main():
    db.add_events(CTFTimeClient.fetch_data())

    updater, bot = Updater(TOKEN), Bot(TOKEN)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CommandHandler("upcoming", upcoming))
    dp.add_handler(CommandHandler("now", current))
    dp.add_handler(CommandHandler("current", current))
    dp.add_handler(CommandHandler("info", info, pass_args=True))
    dp.add_handler(CommandHandler("ping", ping))
    dp.add_handler(CommandHandler("help", usage))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling(clean=True)

    job_queue = updater.job_queue
    job_queue.run_repeating(fetch, 6 * 60 * 60)
    job_queue.run_repeating(starting, 1 * 60 * 60)

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
