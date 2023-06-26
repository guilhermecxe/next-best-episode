from scrapy.http import FormRequest
from scrapy import signals
import scrapy
from tabulate import tabulate
from imdb import Cinemagoer
from tqdm import tqdm
import logging

logging.disable(logging.WARNING) # enabling just error logging messages

class TvtimeSpider(scrapy.Spider):
    name = "tvtime"
    allowed_domains = ["tvtime.com"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ia = Cinemagoer()
        self.seen_tv_shows = [] # useful in case of visiting home page and then some list like "watch-next"
        self.tv_shows = [] # to display items later

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(TvtimeSpider, cls).from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_closed, signal=signals.spider_closed) 
        return spider

    def start_requests(self):
        login_url = 'https://www.tvtime.com/'
        yield scrapy.Request(login_url, callback=self.login)

    def login(self, response):
        url = f'https://www.tvtime.com/signin?username={self.u}&password={self.p}'
        yield FormRequest(url,
                          formdata={
                            'username': self.u,
                            'password': self.p,
                            'redirect_path': 'https://www.tvtime.com/en/watch-next', # to uncomment any redirect_value, comment the other ones
                            # 'redirect_path': 'https://www.tvtime.com/en/not-watched-for-a-while',
                            # 'redirect_path': 'https://www.tvtime.com/en/not-started-yet',
                          })
        
    def __search_tv_show(self, tv_show_title):
        for result in self.ia.search_movie(tv_show_title):
            if result['kind'] in ['tv series', 'tv series documentary', 'tv mini series']: # to ensure the right media
                return result
        return None # tv show not found

    def __get_episode_rating(self, tv_show_title, episode):
        season_id = int(episode[1:3])
        episode_id = int(episode[4:])
        tv_show = self.__search_tv_show(tv_show_title)
        if not tv_show: return -1

        if season_id == 0: season_id = 1
        self.ia.update_series_seasons(tv_show, season_id)

        tv_show_episodes = tv_show['episodes'][season_id]
        if len(tv_show_episodes) < episode_id: return -1 # episode not found

        rating = tv_show_episodes[episode_id]['rating']
        return round(rating, 2) if rating <= 10 else -1

    def parse(self, response):
        episodes = response.css('div.episode-details')

        for episode in tqdm(episodes, desc="Getting episodes"):
            tv_show_title = episode.css('a.nb-reviews-link::text').get()
            episode_id = episode.css('h2 a::text').get()

            if tv_show_title in self.seen_tv_shows:
                continue

            tv_show = {
                'tv_show': tv_show_title,
                'episode': episode_id,
                'rating': self.__get_episode_rating(tv_show_title, episode_id)
            }

            self.tv_shows.append(list(tv_show.values()))
            self.seen_tv_shows.append(tv_show_title)
            yield tv_show

    def spider_closed(self, reason):
        if reason == 'finished':
            tv_shows = sorted(self.tv_shows, key=lambda i: i[2], reverse=True)
            table = tabulate(tv_shows, headers=['TV Show', 'Episode', 'Rating'], tablefmt='fancy_grid', floatfmt='.2f')
            print(table)