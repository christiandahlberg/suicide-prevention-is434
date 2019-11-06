import tweepy
import json
import pandas as pd
from datetime import datetime, timedelta
from tweepy import OAuthHandler, TweepError
from nltk.tokenize import word_tokenize
from nltk.stem import PorterStemmer
from statistics import median
from nltk.sentiment.vader import SentimentIntensityAnalyzer as SIA

def get_table():
    # Get appropriate table depending on subreddit

    with open(f'tweets/twitter_tweets.csv', encoding="utf8") as file:
        df = pd.read_csv(file)
    return df

def get_api_authentication():
     # Open json file with credentials (predetermined)
    with open("twitter_credentials.json", "r") as file:
        creds = json.load(file)

    # Declare credentials
    auth = OAuthHandler(creds['CONSUMER_KEY'], creds['CONSUMER_SECRET'])
    auth.set_access_token(creds['ACCESS_TOKEN'], creds['ACCESS_SECRET'])

    # Auth
    return tweepy.API(auth, wait_on_rate_limit=True)

def main():

    # Authenticate (Tweepy)
    api = get_api_authentication()

    # Instantiation
    ps = PorterStemmer()
    sia = SIA()

    # Scoring
    time_scoring = {'01': -1, '02': -1, '03': -1, '04': -1, '05': -0.8, '06': -0.8, '07': -0.6, '08': -0.6,
                '09': -0.4, '10': -0.4, '11': -0.2, '12': -0.2, '13': 0, '14': 0, '15': 0, '16': 0,
                '17': -0.2, '18': -0.2, '19': -0.4, '20': -0.4, '21': -0.6, '22': -0.6, '23': -0.8, '24': -0.8, '00': -0.8}

    keyword_scoring = {1: -0.5,
                    2: -0.6,
                    3: -0.7,
                    4: -0.8,
                    5: -0.9,
                    6: -1
                    }

    # Tables
    _tweets = {'keywords': [],
                'user_id': [],
                'tweet_id': [],
                'throwaway': [],
                'percentage': [],
                'retweet': [],
                'created': [],
                'sentiment': [],
                'likes': [],
                'score': []
                }

    keywords = ['kill', 'hate', 'depress', 'die', 'suicid', 'anxieti']
    table = get_table()

    for index, row in table.iterrows():

        is_affected = False
        k_count = 0
        k_values = []
        hashtags = []

        try:
            current_tweet = api.get_status(row['tweet_id'])
        except TweepError:
            print('Error: Account not found.')
            continue

        tok_tweet = word_tokenize(current_tweet.text)
        stem_tweet = [ps.stem(w) for w in tok_tweet if w.isalpha()]

        for word in keywords:
            if word in stem_tweet:
                is_affected = True
                k_count += 1
                k_values.append(word)
        
        if is_affected:
            print(f'Tweet #{index} affected ({k_count} keywords found): {current_tweet.text}')
            print(f'    Keywords found: {k_values} (Score: {keyword_scoring[k_count]})')

            # Time
            time = row['created'][11:16]
            time_score = time_scoring[row['created'][11:13]]
            print(f'    TIME SCORE: {time_score} ({time})') 

            # TODO Hashtags
            if hasattr(current_tweet, "entities"):
                if "hashtags" in current_tweet.entities:
                    tags = [ent["text"] for ent in current_tweet.entities["hashtags"] if "text" in ent and ent is not None]
                    if tags is not None:
                        hashtags = tags
                        print(f'    HASHTAGS ({len(hashtags)}): {hashtags}')

            # Sentiment
            pol_score = sia.polarity_scores(row['tweet'])
            sa_scoring = pol_score['compound']
            print(f'    SENTIMENT: {sa_scoring}')

            # Retweet
            is_retweet = -0.2
            retweets = 0
            if hasattr(current_tweet, 'retweeted_status'):
                is_retweet = -0.6
                retweets = current_tweet.retweet_count
                print(f'    RT: True (# of RT\'s: {retweets})')

            # TODO Likes
            likes = current_tweet.favorite_count
            print(f'    LIKES: {likes}')

            # Throwaway
            tweet_user = api.get_user(row['user_id'])
            tweet_user_created = str(tweet_user.created_at)

            is_throwaway = -0.25
            margin = timedelta(days=30)
            today = datetime.today().date()
            date = f'{tweet_user_created[5:7]}-{tweet_user_created[8:10]}-{tweet_user_created[:4]}'
            acc_date = datetime.strptime(date, '%m-%d-%Y').date()
            diff = today - acc_date
            print(f'    ACC DATE: {acc_date}')

            if (today - margin <= acc_date <= today + margin):
                is_throwaway = -1
            print(f'    THROWAWAY: {is_throwaway} (difference: {diff})')

            # User submissions
            count = 0
            _user_tweets = tweepy.Cursor(api.user_timeline, screen_name=tweet_user.screen_name, tweet_mode='extended').items(100)
            _user_tweets_total = 0
            for status in _user_tweets:
                _user_tweets_total += 1
                for k in keywords:
                    if k in status.full_text:
                        count += 1
            print(f'        TOTAL SUBMISSIONS: {_user_tweets_total}')

            # Percentage (replies) 
            try:
                percentage = count / _user_tweets_total
            except ZeroDivisionError:
                percentage = 0
                print("        Error: User hasn't made any submissions.")
            perc_2dm = round(percentage, 2)

            perc_score = 0
            if round(perc_2dm, 1) > 0.8:
                perc_score = -1
            elif perc_2dm > 0.6 and perc_2dm < 0.8:
                perc_score = -0.8
            elif perc_2dm > 0.4 and perc_2dm < 0.6:
                perc_score = -0.6
            elif perc_2dm > 0.2 and perc_2dm < 0.4:
                perc_score = -0.4
            elif perc_2dm < 0.2:
                perc_score = -0.1
            print(f'        SUBMISSIONS: {count} / {_user_tweets_total} affected ({perc_2dm}%,, score: {perc_score})')

            # Median scoring
            score = median([time_score, sa_scoring, is_retweet, is_throwaway, perc_score, keyword_scoring[k_count]])
            print(f' = FINAL SCORE: {score}')

            # Tweets saved to table
            if current_tweet.id not in _tweets['tweet_id']:
                _tweets['user_id'].append(tweet_user.id)                # -
                _tweets['tweet_id'].append(current_tweet.id)            # -    
                _tweets['throwaway'].append(is_throwaway)               # DONE
                _tweets['percentage'].append(perc_score)                # DONE
                _tweets['retweet'].append(is_retweet)                   # DONE
                _tweets['created'].append(time_score)                   # DONE
                _tweets['sentiment'].append(sa_scoring)                 # DONE
                _tweets['likes'].append(likes)                          # TODO
                _tweets['score'].append(score)                          # DONE
                print('Tweet added! Onto next...')

            print("--------------------------------")
        
    # Plot dataframe
    tweet_data = pd.DataFrame(_tweets)

    # Write entry to csv

if __name__ == "__main__":
    main()