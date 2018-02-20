import feedparser


class CTFTimeClient(object):
    feed_url = 'https://ctftime.org/event/list/upcoming/rss/'

    def fetch_data():
        """Function to update the CTF db with new announced CTFs"""
        feed = feedparser.parse(CTFTimeClient.feed_url)

        events = []
        for post in feed.entries:
            event = {}
            event["title"] = post.title
            event["link"] = post.id
            event["url"] = post.url
            event["weight"] = post.weight
            event["format_text"] = post.format_text
            event["format"] = int(post.format)
            event["onsite"] = not bool(post.onsite)
            event["restrictions"] = post.restrictions
            event["start_date"] = post.start_date
            event["finish_date"] = post.finish_date
            event["id"] = post.ctftime_url.split('/')[2]
            events.append(event)

        return events
