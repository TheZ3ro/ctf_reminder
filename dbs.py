import yaml

from dateutil import parser
from datetime import datetime

from utils import time_remaining, to_ita_tz


class CTFDb(object):
    starting_template = "[{0}]({1}) ({2})\nStarting Date: *{3}*\n\n"
    finishing_template = "[{0}]({1}) ({2})\nFinishing Date: *{3}*\n\n"

    def __init__(self):
        self.events = {}

    def is_in_db(self, id):
        """Helper function to check if a CTF is in the db"""
        if self.events.get(id) is None:
            return False
        else:
            return True

    def is_past(self, event):
        """Helper function to check if an event is finished"""
        finish_date = parser.parse(event["finish_date"])
        if finish_date < datetime.utcnow():
            return True
        return False

    def is_ongoing(self, event):
        """Helper function to check if an event is finished"""
        start_date = parser.parse(event["start_date"])
        if start_date < datetime.utcnow():
            return True
        return False

    def add_events(self, events):
        """Add an array of events to the DB and delete past events"""
        new = []
        for event in events:
            r = self.add_event(event)
            if r is not None:
                new.append(r)

        self.delete_past_events()
        return new

    def add_event(self, event):
        """Add a single event to the database, performing checks"""
        if self.is_past(event):
            return

        if self.is_in_db(event["id"]):
            # Update the db with new info but don't emit message
            self.events[event["id"]] = event
            return
        else:
            self.events[event["id"]] = event
            return event

    def delete_past_events(self):
        """Delete past events from the db"""
        to_delete = []
        for id in self.events:
            if self.is_past(self.events[id]):
                to_delete.append(id)

        # Can't delete directly
        for id in to_delete:
            del self.events[id]

    def starting_ctf(self, delta=24):
        """
        Return CTF that start in delta hours
        This function should be repeated every hour
        """
        starting = []
        for id in self.events:
            start_date = parser.parse(self.events[id]["start_date"])
            hours_remaining = time_remaining(start_date) // (60 * 60)
            if hours_remaining == delta:
                starting.append(self.events[id])

        return starting

    def upcoming(self, count=5):
        """Return first `count` CTF that are starting soon"""
        self.delete_past_events()

        upcoming = []
        for id in self.events:
            if not self.is_ongoing(self.events[id]):
                upcoming.append(self.events[id])
        upcoming = sorted(upcoming, key=lambda i: i["start_date"])

        return upcoming[:count]

    def running(self):
        """Return currently running CTF"""
        self.delete_past_events()

        running = []
        for id in self.events:
            if self.is_ongoing(self.events[id]):
                running.append(self.events[id])
        running = sorted(running, key=lambda i: i["finish_date"])

        return running

    def starting_message(self, ctf):
        """Format a message for a starting event"""
        date = parser.parse(ctf["start_date"])

        m = CTFDb.starting_template
        m = m.format(ctf["title"], ctf["link"],
                     str(ctf["id"]), to_ita_tz(date))
        return m

    def finishing_message(self, ctf):
        """Format a message for a starting event"""
        date = parser.parse(ctf["finish_date"])

        m = CTFDb.finishing_template
        m = m.format(ctf["title"], ctf["link"],
                     str(ctf["id"]), to_ita_tz(date))
        return m

    def get_info_message(self, id):
        if not self.is_in_db(id):
            return "I can\'t find a CTF with this id"

        ctf = self.events[id]

        start = parser.parse(ctf["start_date"])
        finish = parser.parse(ctf["finish_date"])
        onsite = "On site" if ctf["onsite"] else "Online"

        message = "[{0}]({1})\n".format(ctf["title"], ctf["link"])
        message += "Type: *{} {}*\n".format(ctf["format_text"], onsite)
        message += "Restriction: *{}*\n".format(ctf["restrictions"])
        message += "Url: {}\n".format(ctf["url"])
        message += "Weight: {}\n".format(ctf["weight"])
        message += "Start Date: *{}*\n".format(to_ita_tz(start))
        message += "Finish Date: *{}*\n".format(to_ita_tz(finish))
        return message


class GroupDb(object):
    groups_db = "./groups.yaml"

    def __init__(self):
        self.load()
        if self.groups is None:
            self.groups = set()

    def load(self):
        """Load groups from backup file"""
        try:
            with open(GroupDb.groups_db, 'r') as f:
                content = f.read()
                self.groups = yaml.load(content)
        except FileNotFoundError:
            self.commit()

    def commit(self):
        """Write group changes to backup file"""
        with open(GroupDb.groups_db, 'w') as f:
            yaml.dump(self.groups, f)

    def add(self, id):
        """Add a new group"""
        self.groups.add(id)
        self.commit()

    def remove(self, id):
        """Add a new group"""
        self.groups.remove(id)
        self.commit()
