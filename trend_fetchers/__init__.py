from .google_trends import GoogleTrends
from .youtube_trending import YouTubeTrending
from .reddit_hot import RedditHot

REGISTRY = {
    "google_trends": GoogleTrends,
    "youtube_trending": YouTubeTrending,
    "reddit_hot": RedditHot,
}
