from datetime import datetime
from pytz import timezone, utc


def time_remaining(target):
    due = target - datetime.utcnow()
    return int(due.total_seconds())


def to_ita_tz(utctime):
    rome = timezone('Europe/Rome')
    utc_dt = utctime.replace(tzinfo=utc)
    rome_time = utc_dt.astimezone(rome)
    return "{:%d-%m-%Y %H:%M %Z}".format(rome_time)
