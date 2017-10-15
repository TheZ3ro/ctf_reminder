#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# pip3 install feedparser python-telegram-bot python-dateutil
import feedparser
import yaml
import telegram
from telegram import *
from telegram.ext import *
from dateutil import parser
from pytz import timezone
import pytz
#from sets import Set

from datetime import datetime, timedelta
import logging
import sys

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

feed_url = 'https://ctftime.org/event/list/upcoming/rss/'
feed_db = './feeds.yaml'
groups_db = './groups.yaml'
events = {}
groups = set()

TOKEN = "308167645:AAHAOc3PYhLDEjrShVPHW7_QTBWNBmBT1Ns" #insert bot token here
group_whitelist = [] #insert group id here
repeatsec = 12*3600
reminded = set()


def loadYamlFile(filename):
    try:
        with open(filename,'r') as f:
            content = f.read()
            if content is not '':
                return yaml.load(content)
    except FileNotFoundError:
        with open(filename,'w+') as f:
            f.write("")


def toCESTtime(utctime):
    utc = pytz.utc
    rome = timezone('Europe/Rome')
    utc_dt = utctime.replace(tzinfo=utc)
    rome_time = utc_dt.astimezone(rome)
    return "{:%d-%m-%Y %H:%M %Z}".format(rome_time)


def CheckGroupWhitelist(bot,update):
    groupId = update.message.chat_id
    if groupId not in group_whitelist:
        return False
    return True

def is_in_db(ctf_id):
    """Helper function to check if a CTF is in the db"""
    if events.get(ctf_id) is None:
        return False      
    else:
        return True

        
def update_data():
    """Function to update the CTF db with new announced CTFs"""
    feed = feedparser.parse(feed_url)

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
        event["finish_date"] = post.finish_date
        event["id"] = post.ctftime_url.split('/')[2]
        
        # if post is already in the database, skip it
        # TODO check the time
        if not is_in_db(event["id"]):
            if event["format"] == 1 and event["onsite"] is False:
                posts_to_print.append(event["id"])
            ctf_id = event["id"]
            events[ctf_id] = event
    
    to_delete = []
    for ctf_id in events:
        ctf = events[ctf_id]
        if parser.parse(ctf["finish_date"]) < datetime.utcnow():
            to_delete.append(ctf_id)
            
    for d in to_delete:
        del events[d]
    
    with open(feed_db, 'w') as f:
        yaml.dump(events, f)

    return posts_to_print


def check_ctfs(bot, job):
    """Job function to check for new announced CTFs"""
    posts_to_print = update_data()

    if posts_to_print is not []:
        message = ""
        for ctf_id in posts_to_print:
            ctf = events.get(ctf_id)
            date = parser.parse(ctf["start_date"])
            message += "[{0}]({1}) ({2})\nStarting Date: *{3}*\n\n".format(ctf["title"], ctf["link"], str(ctf["id"]), toCESTtime(date))
        if message is not "":
            message = "*New CTF announced:*\n" + message
            for element in groups:
                bot.sendMessage(element, text=message, parse_mode='MARKDOWN', disable_web_page_preview=True)


def alarm(bot, job):
    """Function to send the reminder message"""
    message = ""
    
    ctf = events.get(job.context["ctf_id"])
    if ctf is None:
        message = 'Something went wrong with reminder of '+str(job.context["ctf_id"])
    else:
        message = ctf["title"]+' is starting!'
        
    bot.sendMessage(job.context["chat_id"], text=message)


def start(bot, update, job_queue):
    """This function is required. Without this your bot will not load any CTF"""
    groups.add(update.message.chat_id)
    with open(groups_db, 'w') as f:
        yaml.dump(groups, f)

    job = Job(check_ctfs, repeatsec, repeat=True, context=update.message.chat_id)
    job_queue.put(job)
    update.message.reply_text('Hi! I will notify you when new CTFs are announced and let you remind them!')


def ping(bot, update):
    """Classic ping command"""
    message = "I'm not running in this group! Start me with `/start`"
    if update.message.chat_id in groups:
        message = "Pong, here is the flag: `PeqNP{NoobsProof}`"
    update.message.reply_text(message,parse_mode='MARKDOWN')
    

def remind(bot, update, args, job_queue, chat_data):
    """Adds a job to the queue"""
    if CheckGroupWhitelist(bot,update) is False:
        return

    chat_id = update.message.chat_id

    if chat_id not in groups:
        update.message.reply_text("I'm not running in this group! Start me with `/start`",parse_mode='MARKDOWN')
        return

    try:
        if len(args) != 1 :
            update.message.reply_text('Usage: `/remind <ctf_id>`',parse_mode='MARKDOWN')
            return
        
        ctf = events.get(args[0])
        if ctf is None:
            update.message.reply_text('I can\'t find a CTF with this id')
            return
        
        date = parser.parse(ctf["start_date"])
        due = date-datetime.utcnow()
        due = int(due.total_seconds())
        if due < 0:
            update.message.reply_text('Sorry we can not go back to future! Seconds: '+str(due))
            return

        # Add job to queue
        context = {}
        context["chat_id"] = chat_id
        context["ctf_id"] = ctf["id"]
        job = Job(alarm, due, repeat=False, context=context)

        reminded.add(ctf["id"])
        
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
    if CheckGroupWhitelist(bot,update) is False:
        return

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
    
    try: reminded.remove(args[0])
    except: pass

    update.message.reply_text('Timer successfully unset!')


def listctf(bot, update):
    """List all CTFs in database"""
    message = ""
    for ctf_id in events:
        ctf = events[ctf_id]
        start_date = parser.parse(ctf["start_date"])
        end_date = parser.parse(ctf["finish_date"])
        message += "[{0}]({1}) ({2})\nStart: _{3}_\nEnd: _{4}_\n".format(ctf["title"], ctf["link"], str(ctf["id"]), toCESTtime(start_date), toCESTtime(end_date))

    if message is not "":
        message = "*All future Events:*\n" + message
        bot.sendMessage(update.message.chat_id, text=message, parse_mode='MARKDOWN', disable_web_page_preview=True)
    else:
        bot.sendMessage(update.message.chat_id, text="No CTF present in the DB")


def remindctf(bot, update):
    """List all CTFs that will be reminded"""
    if CheckGroupWhitelist(bot,update) is False:
        return
    
    message = ""
    
    # Get and sort by date list of CTF to remind
    ctf_list = []
    for ctf_id in reminded:
        if is_in_db(ctf_id):
            ctf_list.append(events[ctf_id])
    ctf_list = sorted(ctf_list, key=lambda i: i['start_date'])

    for ctf in ctf_list:
        date = parser.parse(ctf["start_date"])
        message += "[{0}]({1}) ({2})\nStarting Date: *{3}*\n\n".format(ctf["title"], ctf["link"], str(ctf["id"]), toCESTtime(date))

    if message is not "":
        message = "*Events with Reminders:*\n" + message
        bot.sendMessage(update.message.chat_id, text=message, parse_mode='MARKDOWN', disable_web_page_preview=True)
    else:
        bot.sendMessage(update.message.chat_id, text="No CTF reminder set")    


def upcomingctf(bot, update):
    """List 5 upcoming CTFs in database"""
    message = ""

    upcoming_ctfs = []
    for ctf_id in events:
        if parser.parse(events[ctf_id]['start_date']) > datetime.utcnow():
            upcoming_ctfs.append(events[ctf_id])
    upcoming_ctfs = sorted(upcoming_ctfs, key=lambda i: i['start_date'])

    i = 0
    for ctf in upcoming_ctfs:
        if i>=5:
            break
        date = parser.parse(ctf["start_date"])
        message += "[{0}]({1}) ({2})\nStarting Date: *{3}*\n\n".format(ctf["title"], ctf["link"], str(ctf["id"]), toCESTtime(date))
        i+=1

    if message is not "":
        message = "*Upcoming events:*\n" + message
        bot.sendMessage(update.message.chat_id, text=message, parse_mode='MARKDOWN', disable_web_page_preview=True)
    else:
        bot.sendMessage(update.message.chat_id, text="No upcoming CTF")    


def currentctf(bot, update):
    """List current running CTFs in database"""
    message = ""

    running_ctfs = []
    for ctf_id in events:
        ctf = events[ctf_id]
        start_date = parser.parse(ctf["start_date"])
        due = start_date-datetime.utcnow()
        due = int(due.total_seconds())
        if due < 0:
            finish_date = parser.parse(ctf["finish_date"])
            due = finish_date-datetime.utcnow()
            due = int(due.total_seconds())
            if due > 0:
                running_ctfs.append(ctf)
    running_ctfs = sorted(running_ctfs, key=lambda i: i['finish_date'])
    # sort by finish_date, first the CTF that will finish sooner

    for ctf in running_ctfs:
        date = parser.parse(ctf["finish_date"])
        message += "[{0}]({1}) ({2})\nFinishing Date: *{3}*\n\n".format(ctf["title"], ctf["link"], str(ctf["id"]), toCESTtime(date))

    if message is not "":
        message = "*Now running events:*\n" + message
        bot.sendMessage(update.message.chat_id, text=message, parse_mode='MARKDOWN', disable_web_page_preview=True)    
    else:
        bot.sendMessage(update.message.chat_id, text="No CTF is currently running")    


def info(bot, update, args):
    """Get info form a given CTFid"""
    if len(args) != 1 :
        update.message.reply_text('Usage: `/info <ctf_id>`', parse_mode='MARKDOWN')
        return
    
    ctf = events.get(args[0])
    if ctf is None:
        update.message.reply_text('I can\'t find a CTF with this id')
        return
        
    start_date = parser.parse(ctf["start_date"])
    finish_date = parser.parse(ctf["finish_date"])
    
    message = "[{0}]({1})\n".format(ctf["title"], ctf["link"])
    message += "Type: *"+ctf["format_text"]+(" On site" if ctf["onsite"] else " Online")+"*\n"
    message += "Restriction: *"+ctf["restrictions"]+"*\n"
    message += "Url: "+ctf["url"]+"\n"
    message += "Weight: "+ctf["weight"]+"\n"
    message += "Start Date: *{0}*\n".format(toCESTtime(start_date))
    message += "Finish Date: *{0}*\n".format(toCESTtime(finish_date))
    update.message.reply_text(message, parse_mode='MARKDOWN', disable_web_page_preview=True)
    

def usage(bot, update):
    message = "*CTF Reminder* will remind your CTF as they start!\n"
    message += "`/start` to start the reminder\n"
    message += "`/upcoming` to list all the upcoming CTFs\n"
    message += "`/toremind` to list all the CTFs with reminder\n"
    message += "`/list` to list all the future CTFs\n"
    message += "`/info <ctf_id>` to get info for specific CTF\n"
    message += "`/remind <ctf_id>` to set a CTF reminder\n"
    message += "`/unset <ctf_id>` to unset a CTF reminder\n"
    message += "`/ping` to check if the reminder is started\n"
    update.message.reply_text(message,parse_mode='MARKDOWN')
    

def error(bot, update, error):
    logger.warning('Update "%s" caused error "%s"' % (update, error))


def main():
    events = loadYamlFile(feed_db)
    groups = loadYamlFile(groups_db)

    update_data()

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
    dp.add_handler(CommandHandler("upcoming", upcomingctf))
    dp.add_handler(CommandHandler("now", currentctf))
    dp.add_handler(CommandHandler("current", currentctf))
    dp.add_handler(CommandHandler("toremind", remindctf))
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

