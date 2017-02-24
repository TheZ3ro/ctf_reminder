#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# pip3 install feedparser python-telegram-bot python-dateutil
import feedparser
import json
import telegram
from telegram import *
from telegram.ext import Updater, CommandHandler, Job
from dateutil import parser

from datetime import datetime, timedelta
import logging
import sys

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

feed_name = 'Upcoming CTF'
url = 'https://ctftime.org/event/list/upcoming/rss/'
db = './feeds.json'
TOKEN = ""
repeatsec = 12*3600
running = False

e_db = {}
with open(db,'r') as f:
    content = f.read()
    if content is not '':
        e_db = json.loads(content)


def is_in_db(ctf_id):
    """Helper function to check if a CTF is in the db"""
    if e_db.get(ctf_id) is None:
        return False      
    else:
        return True

        
def check_ctfs(bot, job):
    """Job function to update the CTF db with new announced CTFs"""
    feed = feedparser.parse(url)

    posts_to_print = []

    for post in feed.entries:
        event = {}
        event["title"] = post.title
        event["link"] = post.id
        event["format_text"] = post.format_text
        event["format"] = int(post.format)
        event["onsite"] = not bool(post.onsite)
        event["restrictions"] = post.restrictions
        event["start_date"] = post.start_date
        event["id"] = post.ctftime_url.split('/')[2]
        event["remind"] = False
        
        # if post is already in the database, skip it
        # TODO check the time
        if not is_in_db(event["id"]):
            if event["format"] == 1 and event["onsite"] is False:
                posts_to_print.append(event["id"])
            ctf_id = event["id"]
            e_db[ctf_id] = event
    
    if posts_to_print is not []:
        message = ""
        for ctf_id in posts_to_print:
            ctf = e_db.get(ctf_id)
            message += "New CTF announced: "+ctf["title"]+" ID: "+ctf["id"]+"\n"
        if message is not "":
            bot.sendMessage(job.context, text=message)
    
    to_delete = []
    for ctf_id in e_db:
        ctf = e_db[ctf_id]
        if parser.parse(ctf["start_date"]) < datetime.now():
            to_delete.append(ctf_id)
            
    for d in to_delete:
        del e_db[d]
    
    with open(db, 'w') as f:
        f.write(json.dumps(e_db))


def alarm(bot, job):
    """Function to send the reminder message"""
    message = ""
    
    ctf = e_db.get(job.context["ctf_id"])
    if ctf is None:
        message = 'Something went wrong with reminder of '+str(job.context["ctf_id"])
    else:
        message = ctf["title"]+' is starting!'
        
    bot.sendMessage(job.context["chat_id"], text=message)


def start(bot, update, job_queue):
    """This function is required. Without this your bot will not load any CTF"""
    global running
    running = True
    job = Job(check_ctfs, repeatsec, repeat=True, context=update.message.chat_id)
    job_queue.put(job)
    update.message.reply_text('Hi! I will notify you when new CTFs are announced and let you remind them!')


def ping(bot, update):
    """Classic ping command"""
    global running
    message = "I'm not running! Start me with `/start`"
    if running is True:
        message = "Pong, here is the flag: `PeqNP{NoobsProof}`"
    update.message.reply_text(message,parse_mode='MARKDOWN')
    

def remind(bot, update, args, job_queue, chat_data):
    """Adds a job to the queue"""
    global running
    chat_id = update.message.chat_id
        
    if running is False:
        update.message.reply_text("I'm not running! Start me with `/start`",parse_mode='MARKDOWN')
        return

    try:
        if len(args) != 1 :
            update.message.reply_text('Usage: `/remind <ctf_id>`',parse_mode='MARKDOWN')
            return
        
        ctf = e_db.get(args[0])
        if ctf is None:
            update.message.reply_text('I can\'t find a CTF with this id')
            return
        
        date = parser.parse(ctf["start_date"])
        due = date-datetime.now()
        due = int(due.total_seconds())
        if due < 0:
            update.message.reply_text('Sorry we can not go back to future! Seconds: '+str(due))
            return

        # Add job to queue
        context = {}
        context["chat_id"] = chat_id
        context["ctf_id"] = ctf["id"]
        job = Job(alarm, due, repeat=False, context=context)
        
        if 'job' not in chat_data:
            chat_data['job'] = {}
        ctf_id = ctf["id"]
        chat_data['job'][ctf_id] = job
        job_queue.put(job)

        update.message.reply_text('Timer successfully set! Seconds: '+str(due))

    except (IndexError, ValueError):
        update.message.reply_text('Usage: `/remind <ctf_id>`',parse_mode='MARKDOWN')


def unset(bot, update, args, chat_data):
    """Removes the job if the user changed their mind"""
    if len(args) != 1 :
        update.message.reply_text('Usage: `/unset <ctf_id>`',parse_mode='MARKDOWN')
        return

    if 'job' not in chat_data:
        update.message.reply_text('You have no active timer')
        return
    
    jobs = chat_data['job']
    job = jobs.get(args[0])
    if job is None:
        update.message.reply_text('I can\'t find a Reminder with this id')
        return
        
    job.schedule_removal()
    del chat_data['job'][args[0]]

    update.message.reply_text('Timer successfully unset!')


def listctf(bot, update):
    """List all CTFs in database"""
    message = ""
    for ctf_id in e_db:
        ctf = e_db[ctf_id]
        message += "CTF: "+ctf["title"]+" ID: "+str(ctf["id"])+"\n"
    if message is not "":
        bot.sendMessage(update.message.chat_id, text=message)


def info(bot, update, args):
    """Get info form a given CTFid"""
    if len(args) != 1 :
        update.message.reply_text('Usage: `/info <ctf_id>`',parse_mode='MARKDOWN')
        return
    
    ctf = e_db.get(args[0])
    if ctf is None:
        update.message.reply_text('I can\'t find a CTF with this id')
        return
        
    date = parser.parse(ctf["start_date"])
    
    message = ctf["title"]+"\n"+ctf["link"]+"\n"
    message += "Type: "+ctf["format_text"]+(" On site" if ctf["onsite"] else " Online")+"\n"
    message += "Restriction: "+ctf["restrictions"]+"\n"
    message += "Start Date: {:%Y/%m/%d %H:%M} UTC\n".format(date)
    update.message.reply_text(message)
    

def usage(bot, update):
    message = "*CTF Reminder* will remind your CTF as they start!\n"
    message += "`/start` to start the reminder\n"
    message += "`/list` to list all the upcoming CTFs\n"
    message += "`/info <ctf_id>` to get info for specific CTF\n"
    message += "`/remind <ctf_id>` to set a CTF reminder\n"
    message += "`/unset <ctf_id>` to unset a CTF reminder\n"
    message += "`/ping` to check if the reminder is started\n"
    update.message.reply_text(message,parse_mode='MARKDOWN')
    

def error(bot, update, error):
    logger.warning('Update "%s" caused error "%s"' % (update, error))


def main():
    bot = telegram.Bot(TOKEN)
    updater = Updater(TOKEN)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start, pass_job_queue=True))
    dp.add_handler(CommandHandler("ping", ping))
    dp.add_handler(CommandHandler("help", usage))
    dp.add_handler(CommandHandler("remind", remind,
                                  pass_args=True,
                                  pass_job_queue=True,
                                  pass_chat_data=True))
    dp.add_handler(CommandHandler("unset", unset, pass_args=True, pass_chat_data=True))
    dp.add_handler(CommandHandler("list", listctf))
    dp.add_handler(CommandHandler("info", info, pass_args=True))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling(clean=True)

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()

