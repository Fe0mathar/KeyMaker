"""
trinity.py

A single-file module (Tweepy-based) to:
 - Post tweets (optionally with images)
 - Send direct messages
 - Track/stream activity on Twitter (hashtags, retweets, etc.)
 - (Optional) Post feed-based articles (from your old approach)
 - Potential usage for meme coin / NFT campaigns
"""

import os
import time
import random
import pyshorteners
import pytz
import feedparser
import tweepy
from datetime import datetime, timedelta
from dateutil import parser
from dotenv import load_dotenv

# ------------------------------------------------------------------------
# Article Class (optional, from old feed-based approach)
# ------------------------------------------------------------------------
class Article:
    """
    Minimal structure to store feed entry data:
     - author
     - link
     - published (string date)
     - summary
     - title
    """
    def __init__(self, author, link, published, summary, title):
        self.author = author
        self.link = link
        self.published = published
        self.summary = summary
        self.title = title

# ------------------------------------------------------------------------
# State Class (optional, for storing posted links)
# ------------------------------------------------------------------------
class State:
    """
    Tracks which links have been posted to avoid duplicates.
    Loads/saves from a local file (e.g. 'state.txt').
    """
    def __init__(self, filename="state.txt"):
        self.filename = filename
        self.posted_links = set()

    def load(self):
        if os.path.exists(self.filename):
            with open(self.filename, "r", encoding="utf-8") as f:
                for line in f:
                    link = line.strip()
                    if link:
                        self.posted_links.add(link)
            print(f"[State] Loaded. {len(self.posted_links)} links found.")
        else:
            print("[State] No file found. Starting fresh.")

    def save(self):
        with open(self.filename, "w", encoding="utf-8") as f:
            for link in self.posted_links:
                f.write(link + "\n")
        print(f"[State] Saved. {len(self.posted_links)} links recorded.")

    def is_posted(self, link):
        return link in self.posted_links

    def add_link(self, link):
        self.posted_links.add(link)

# ------------------------------------------------------------------------
# Trinity Class
# ------------------------------------------------------------------------
class Trinity:
    """
    Main class for:
      - Twitter client (via tweepy)
      - Posting tweets / images
      - Sending DMs
      - Tracking hashtags/cashtags via streaming
      - (Optional) posting feed-based articles
    """

    def __init__(self):
        load_dotenv()

        # Initialize shortener if we want shorter links
        self.shortener = pyshorteners.Shortener()

        # Create Tweepy client from environment variables
        self.client = tweepy.Client(
            consumer_key=os.getenv("CONSUMER_KEY"),
            consumer_secret=os.getenv("CONSUMER_SECRET"),
            access_token=os.getenv("ACCESS_TOKEN"),
            access_token_secret=os.getenv("ACCESS_TOKEN_SECRET")
        )

        # We might also create a streaming client to track hashtags:
        bearer_token = os.getenv("BEARER_TOKEN")  # for streaming usage
        self.streaming_client = None
        if bearer_token:
            self.streaming_client = TrinityStreamingClient(bearer_token, self)

    # ----------------------------------------
    # 1) Post Tweet (text only)
    # ----------------------------------------
    def post_tweet(self, text: str):
        """
        Posts a simple text tweet to the authorized Twitter account.
        """
        try:
            self.client.create_tweet(text=text)
            print("[Trinity] Tweet posted successfully.")
        except tweepy.TweepyException as e:
            print(f"[Trinity] Error posting tweet: {e}")

    # ----------------------------------------
    # 2) Post Tweet with an Image
    # ----------------------------------------
    def post_tweet_with_image(self, text: str, image_path: str):
        """
        Uploads an image, then posts a tweet with that image attached.
        """
        # For v2 or v1.1, we might need different endpoints. 
        # If you want simpler approach: 
        #   - create an OAuth1.0 client for media upload or 
        #   - or we do a separate approach for the media_id.
        # This is a placeholder approach:
        try:
            # example => we might need an OAuth1.0 client for media upload:
            # you can adapt this code if you're using tweepy.API (v1.1)
            # We'll do a partial snippet:
            auth = tweepy.OAuth1UserHandler(
                consumer_key=os.getenv("CONSUMER_KEY"),
                consumer_secret=os.getenv("CONSUMER_SECRET"),
                access_token=os.getenv("ACCESS_TOKEN"),
                access_token_secret=os.getenv("ACCESS_TOKEN_SECRET")
            )
            api = tweepy.API(auth)
            media = api.media_upload(image_path)
            media_id = [media.media_id]

            # now post the tweet via v1.1 or v2 approach
            api.update_status(status=text, media_ids=media_id)
            print("[Trinity] Tweet with image posted successfully.")
        except tweepy.TweepyException as e:
            print(f"[Trinity] Error posting tweet with image: {e}")

    # ----------------------------------------
    # 3) Send Direct Message
    # ----------------------------------------
    def send_direct_message(self, user_id: str, text: str):
        """
        Sends a direct message (DM) to user_id with given text.
        user_id must be the numeric ID, not the screen name.
        """
        # For v2 direct message, or we fallback to v1.1
        # For v1.1:
        try:
            auth = tweepy.OAuth1UserHandler(
                consumer_key=os.getenv("CONSUMER_KEY"),
                consumer_secret=os.getenv("CONSUMER_SECRET"),
                access_token=os.getenv("ACCESS_TOKEN"),
                access_token_secret=os.getenv("ACCESS_TOKEN_SECRET")
            )
            api = tweepy.API(auth)
            # in v1.1 => send DM
            # DM endpoint might differ, here's a placeholder:
            api.send_direct_message(recipient_id=user_id, text=text)
            print(f"[Trinity] Sent DM to user {user_id}.")
        except tweepy.TweepyException as e:
            print(f"[Trinity] Error sending DM: {e}")

    # ----------------------------------------
    # 4) Track Hashtag / Cashtag via Streaming
    # ----------------------------------------
    def track_hashtag(self, tag: str):
        """
        Adds a stream rule for hashtag or cashtag (# or $).
        Then the streaming client can watch for tweets matching that rule
        to track retweets, likes, etc.
        """
        if not self.streaming_client:
            print("[Trinity] No streaming client available (missing BEARER_TOKEN?).")
            return
        try:
            # Clear old rules if needed
            existing_rules = self.streaming_client.get_rules().data
            if existing_rules:
                rule_ids = [r.id for r in existing_rules]
                self.streaming_client.delete_rules(rule_ids)
            
            # Add new rule
            query = f"#{tag} OR ${tag}"
            self.streaming_client.add_rules(tweepy.StreamRule(query))
            print(f"[Trinity] Tracking hashtag/cashtag: #{tag} / ${tag}")

            # Start streaming => indefinite blocking call
            self.streaming_client.filter(expansions=["author_id"])
        except tweepy.TweepyException as e:
            print(f"[Trinity] Error setting up stream: {e}")

    # ----------------------------------------
    # 5) (Optional) Post feed-based articles
    # ----------------------------------------
    def post_feed_articles(self, feed_url: str, state):
        """
        Example from old feed-based approach: parse feed, 
        tweet new articles if within last hour & not posted.
        """
        import feedparser
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:
            author = getattr(entry, "author", "Unknown")
            link = getattr(entry, "link", "")
            published = getattr(entry, "published", "")
            summary = getattr(entry, "summary", "")
            title = getattr(entry, "title", "")

            article = Article(author, link, published, summary, title)
            self._create_article_tweet(article, state)

    def _create_article_tweet(self, article, state):
        link = self.shortener.tinyurl.short(article.link)
        if not self._is_within_last_hour(article.published):
            print("[Trinity] Article is older than 1 hour, skipping.")
            return
        if state.is_posted(link):
            print("[Trinity] Link already posted:", link)
            return

        tweet_text = f"Title: {article.title}\nAuthor: {article.author}\n\n{link}"
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                self.client.create_tweet(text=tweet_text)
                state.add_link(link)
                print("[Trinity] Successfully posted feed article.")
                delay = random.randint(30, 120)
                time.sleep(delay)
                return
            except tweepy.TweepyException as e:
                print(f"[Trinity] Error posting feed article (attempt {attempt+1}/{max_attempts}): {e}")
                if attempt < max_attempts - 1:
                    sleep_time = 4 * (2**attempt)
                    time.sleep(sleep_time)

    def _is_within_last_hour(self, date_string):
        from dateutil import parser
        parsed_date = parser.parse(date_string)
        if parsed_date.tzinfo is None:
            import pytz
            parsed_date = parsed_date.replace(tzinfo=pytz.UTC)
        now_utc = datetime.now(pytz.UTC)
        return (now_utc - parsed_date) < timedelta(hours=1)

# ------------------------------------------------------------------------
# Trinity StreamingClient for real-time hashtag tracking
# ------------------------------------------------------------------------
class TrinityStreamingClient(tweepy.StreamingClient):
    """
    Extended Tweepy StreamingClient to handle tweets matching our rules 
    (e.g. #tag or $tag). We pass reference to Trinity so we can do logic 
    (like logging retweets, or awarding meme coins).
    """
    def __init__(self, bearer_token, trinity_ref):
        super().__init__(bearer_token=bearer_token, wait_on_rate_limit=True)
        self.trinity_ref = trinity_ref  # Access to methods or data in Trinity if needed

    def on_tweet(self, tweet):
        """
        Called when we get a matching tweet from the stream.
        We can do logic here like awarding coins for retweets, or collecting tweet info.
        """
        print(f"[TrinityStream] New tweet matched rule => ID: {tweet.id}, text: {tweet.text}")
        # Example: We could track user activity or mention awarding coins, 
        # or call an external method to handle it.

    def on_includes(self, includes):
        # optional: handle expansions => author info, etc.
        pass

    def on_connection_error(self):
        print("[TrinityStream] Connection error, sleeping for 10s.")
        time.sleep(10)

    def on_errors(self, errors):
        print(f"[TrinityStream] Errors: {errors}")

    def on_exception(self, exception):
        print(f"[TrinityStream] Exception: {exception}")
        return super().on_exception(exception)

# ------------------------------------------------------------------------
# Example usage if run as main
# ------------------------------------------------------------------------
def run_trinity_example():
    """
    Example function: 
    - load state
    - create Trinity
    - optionally post a campaign tweet
    - track a #tag
    """
    # load or create state
    s = State()
    s.load()

    trinity = Trinity()

    # Example: post a tweet about "GDP coin" a meme coin
    text = "Announcing GDP coin! Retweet this for a chance to receive #GdpCoin. #meme #n3"
    trinity.post_tweet(text)

    # Start tracking hashtag "GdpCoin" => indefinite streaming
    # caution: it blocks. So you might do it in a separate thread.
    # trinity.track_hashtag("GdpCoin")

    # Save state at the end
    s.save()

if __name__ == "__main__":
    run_trinity_example()
