import tweepy
import config
import json
import nltk
import random
import sqlite3
from datetime import date
import time

auth = tweepy.OAuthHandler(config.CONSUMER_KEY, config.CONSUMER_SECRET)
auth.set_access_token(config.ACCESS_TOKEN, config.ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

def save_original_user_tweets(usr_id):
	"""
	Given a user's id, get and save all their tweets to a .txt file
	"""
	with open('my_stuff.txt','w') as f:
		for status in tweepy.Cursor(api.user_timeline, id=usr_id).items():
			if not status.retweeted and 'RT @' not in status.text:			
				f.write(status.text+"\n")

def get_user_id(screen_name):
	"""
	Given a users screenname, get their id.
	"""
	user = api.search_users(screen_name)
	for person in user:
		return person.id

def nltkify(path):
	"""
	Using nltk, make a text. We might not really need this,
	as the really only purpose is to find the most common words.
	"""
	with open(path, 'r+') as f:
		line = f.read()
		tokens = nltk.word_tokenize(line)
		text = nltk.Text(tokens)
		return text

def remove_random_crap(user_text):
	"""
	Get rid of common things found on twitter, we won't want our
	sentences to just be gibberish.
	"""
	new_text = []
	remove = ['//', 'http', ':', '\'\'']
	for word in user_text:
		if '//'  not in word and 'http' not in word and ':' not in word:
			new_text.append(word)

	return new_text

def create_word_pairs(text):
	"""
	Go through the supplied text and create our 'word pairs',
	its actually a dictinary of: 'word:[list of words]'' pairs, but you
	get the idea.
	"""
	all_pairs = {}

	for word in range(len(text) - 1):
		if text[word] not in all_pairs:
			all_pairs[text[word]] = [text[word + 1]]
		else:
			all_pairs[text[word]] += [text[word + 1]]

	return all_pairs

def get_next_word(word, pairs):
	"""
	Depending on how many words come after a word,
	either just grab one if it's the only one, or
	randomly select a word if there exists multiples within the list.
	"""
	if len(pairs[word]) == 1:
		return ''.join(pairs[word])
	else:
		_range = len(pairs[word])
		selection = generate_random(_range) 
		return ''.join(pairs[word][selection])

def generate_random(_range=None):
	"""
	Using SystemRandom, generate a random number.
	"""
	sys_rand = random.SystemRandom()
	if not _range:
		return sys_rand.random()
	else:
		return sys_rand.randrange(_range)

def make_sentence(text, pairs, length):
	"""
	Given the text, the pairs of words, and the length, we create a sentence.
	The starting word will be one of most common words the user has used, so
	hopefully it doesn't sound too random.
	"""
	sentence = []
	fd = nltk.FreqDist(text)
	most_common = fd.most_common(75)

	starting_place = generate_random(len(most_common))
	word = text[starting_place]

	sentence.append(text[starting_place])

	for i in range(length):
		word = ''.join(word)
		word = get_next_word(word, pairs)
		sentence.append(word)

	return sentence

def format_sentence(sentence):
	"""
	We iterate through the words and make any modifications needed, namely
	the format of the sentence. This means we put '@' in front of the word, and the
	other puncuation marks behind the words.
	"""
	put_in_front = ['@', '#']
	put_in_back = ['.', ',', '\'re', '\'nt', '\'', '\'t', '\'s', '!', '\'m', '?', '!?','?!']
	for word in range(len(sentence)):
		try:
			if sentence[word] in put_in_front:
				sentence[word + 1] = sentence[word] + sentence[word + 1]
				del sentence[word]

			elif sentence[word] in put_in_back:
				sentence[word - 1] = sentence[word - 1] + sentence[word] 
				del sentence[word]
		except IndexError:
			pass

	return ' '.join(sentence)

def check_mentions():
	"""
	Grab all mentions found one the first page, from there we
	check and see if the mention found was already used and if not,
	we go ahead with posting a tweet.

	*Note, actually grabbing the user's tweets does take a lot of time
	and will reduce our overall available API calls.
	"""
	print('Checking Mentions')
	mentions = api.mentions_timeline(count=1)
	tweet_date = str(date.today())
	for mention in mentions:
		if add_tweet_to_db(config.DB_PATH, mention.user.screen_name, mention.id, tweet_date):
			print('{} mentioned us! Gonna send him some sentances now.'.format(mention.user.screen_name))
			_id = get_user_id(mention.user.screen_name)
			#save_original_user_tweets(_id)
			user_text = nltkify('my_stuff.txt')
			clean_text = remove_random_crap(user_text)
			pairs = create_word_pairs(clean_text)

			sentence = format_sentence(make_sentence(clean_text, pairs, 10))
			print(sentence)
			#tweet_it(mention.user.screen_name, sentence)

		else:
			print('Not going to do it because of some reason')

def tweet_it(username, sentence):
	"""
	Create our tweet with the username passed and the sentence we created.
	"""
	send = "Hey @{0}\n\n {1}".format(username, sentence)
	api.update_status(status=send)

def init_db(path):
	"""
	Connect and create our database if need be.
	"""
	sql = sqlite3.connect(path)
	cur = sql.cursor()

	cur.execute('CREATE TABLE IF NOT EXISTS old_tweets(screenname TEXT, tweetID TEXT, tweet_date TEXT)')
	print('Loaded database')

def add_tweet_to_db(path, screenname, tweet_id, tweet_date):
	"""
	Add the tweet into the db if we don't have it already, also we check
	to see if the time the person requesting a sentence hasn't already made one
	on the same day. Limit it to one per person per day.
	"""
	sql = sqlite3.connect(path)
	cur = sql.cursor()
	date_now = date.today()

	cur.execute('SELECT * FROM old_tweets WHERE screenname=? AND tweetID=? AND tweet_date=?', (screenname, tweet_id,tweet_date,))
	
	if not cur.fetchone():
		if not date_now == tweet_date:
			cur.execute('INSERT INTO old_tweets VALUES(?,?,?)', (screenname, tweet_id,tweet_date,))
	else:
		return False

	# Commit and return True to signify a succesful insert
	sql.commit()
	return True

if __name__ == "__main__":
	init_db(config.DB_PATH)
	check_mentions()
