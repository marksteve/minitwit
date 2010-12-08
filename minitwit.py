import sqlite3
import hashlib
import time
import os
import sys

from datetime import datetime
from datetime import timedelta

from mako.template import Template
from mako.lookup import TemplateLookup
import cherrypy
import simplejson as json
from BeautifulSoup import BeautifulSoup

# TEMPLATES

templates = TemplateLookup(directories=[os.path.realpath(os.path.dirname(sys.argv[0])) + '/templates'])

# HELPERS

def md5sum(s):
	return hashlib.md5(s).hexdigest()

def get_date(s):
	dt = datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
	dt -= timedelta(seconds=time.timezone)
	# sqlite seems to save at GMT... ata :P
	return pretty_date(dt) # found this online

def pretty_date(time=False):
	"""
	Get a datetime object or a int() Epoch timestamp and return a
	pretty string like 'an hour ago', 'Yesterday', '3 months ago',
	'just now', etc
	"""
	now = datetime.now()
	diff = None
	if type(time) is int:
		diff = now - datetime.fromtimestamp(time)
	else:
		diff = now - time
	
	second_diff = diff.seconds
	day_diff = diff.days

	if day_diff < 0:
		return ''

	if day_diff == 0:
		if second_diff < 10:
			return "just now"
		if second_diff < 60:
			return str(second_diff) + " seconds ago"
		if second_diff < 120:
			return  "a minute ago"
		if second_diff < 3600:
			return str( second_diff / 60 ) + " minutes ago"
		if second_diff < 7200:
			return "an hour ago"
		if second_diff < 86400:
			return str( second_diff / 3600 ) + " hours ago"
	if day_diff == 1:
		return "Yesterday"
	if day_diff < 7:
		return str(day_diff) + " days ago"
	if day_diff < 31:
		return str(day_diff/7) + " weeks ago"
	if day_diff < 365:
		return str(day_diff/30) + " months ago"
	return str(day_diff/365) + " years ago"

def clean_html( fragment ):
	
	acceptable_elements = ['a', 'b', 'code', 'em', 'i', 'strike', 'strong', 'sub', 'sup', 'u']
	acceptable_attributes = ['href']

	while True:
		soup = BeautifulSoup( fragment )
		removed = False
		for tag in soup.findAll(True): # find all tags
			if tag.name not in acceptable_elements:
				tag.extract() # remove the bad ones
				removed = True
			else: # it might have bad attributes
				# a better way to get all attributes?
				for attr in tag._getAttrMap().keys():
					if attr not in acceptable_attributes:
						del tag[attr]

		# turn it back to html
		fragment = unicode(soup)

		if removed:
			# we removed tags and tricky can could exploit that!
			# we need to reparse the html until it stops changing
			continue # next round

		return fragment

# DATABASE

class DB:

	def connect(self, thread_index):
		cherrypy.thread_data.db = sqlite3.connect('minitwit.sqlite')
		self.conn = cherrypy.thread_data.db
		self.c = self.conn.cursor()
	
	def fetchone(self, query, args=()):
		self.c.execute(query, args)
		return self.c.fetchone()
	
	def fetchall(self, query, args=()):
		self.c.execute(query, args)
		return self.c.fetchalll()
	
	def query(self, query, args=()):
		self.c.execute(query, args)
		self.conn.commit()

cherrypy.engine.subscribe('start_thread', DB().connect)

# CONTROLLERS

# Saw session_auth after writing this so hindi ko na ginamit yung tool...
class Session:
	
	def login(self, username='', password='', redirect='/'):
		message = None
		if len(username) > 0 and len(password) > 0:	
			logged_in = DB().fetchone("select rowid from users where username = ? and password = ?", (username, md5sum(password)))
			if logged_in is not None:
				cherrypy.session['logged_in'] = logged_in[0]
				raise cherrypy.HTTPRedirect(redirect)
			else:
				message = 'Invalid username/password'
		return templates.get_template('login.html').render(username=username, password=password, message=message)
		
	def logout(self, redirect='/'):
		cherrypy.lib.sessions.expire()
		raise cherrypy.HTTPRedirect(redirect)
		
	def get_logged_in(self):
		try:
			rowid = cherrypy.session.get('logged_in')
			r = DB().fetchone('select rowid, username from users where rowid = ?', (rowid,))
			return {'id': r[0], 'username': r[1]}
		except:
			return None
	
	logout.exposed = True
	login.exposed = True

class Post:
	
	def default(self, id=None, text=None):
		logged_in = Session().get_logged_in()
		m = cherrypy.request.method

		cherrypy.response.headers['Content-Type'] = 'application/json'

		# Ugly attempt for a RESTful controller
		# Di ko kasi mapagana yung Method Dispatcher

		if id is not None:
			try:
				id = int(id)
			except ValueError:
				raise cherrypy.HTTPError(404)
			if m == 'GET' and id > 0:
				try:
					r = DB().fetchone('select rowid, text, date from posts where rowid = ?', (id,))
					return json.dumps({'id': r[0], 'text': r[1], 'date': r[2]})
				except:
					raise cherrypy.HTTPError(404)
			if logged_in is not None:
				if m == 'DELETE':
					# TODO: Delete
					pass
		else:
			if logged_in is not None:
				if m == 'PUT':
					text = clean_html(text)
					if len(text) > 0 and len(text) <= 120:
						DB().query('insert into posts values (?, ?, datetime("now"))', (logged_in['id'], text))
					else:
						raise cherrypy.HTTPError(400) # Bad request
			try:
				posts = DB().fetchall('select posts.rowid, text, date, username from posts join users on posts.user = users.rowid order by date desc limit 10')
				return json.dumps([{'id': r[0], 'text': r[1], 'date': get_date(r[2]), 'username': r[3]} for r in posts])
			except:
				raise cherrypy.HTTPError(404)

	default.exposed = True

# ROOT

class Minitwit:

	session = Session()
	post = Post()

	def index(self):
		logged_in = Session().get_logged_in()
		posts = DB().fetchall('select posts.rowid, text, date, username from posts join users on posts.user = users.rowid order by date desc limit 10')
		posts = [{'id': r[0], 'text': r[1], 'date': get_date(r[2]), 'username': r[3]} for r in posts]
		return templates.get_template('dashboard.html').render(logged_in=logged_in, posts=posts)

	def register(self, username='', password='', conf_password=''):
		message = None
		if len(username) > 0 and len(password) > 0 and password == conf_password:
			DB().query('insert into users values (?, ?)', username, md5sum(password))
			raise cherrypy.HTTPRedirect('/session/login')
		elif password != conf_password:
			message = "Passwords don't match"
		return templates.get_template('register.html').render(username=username, password=password, conf_password=conf_password, message=message)

	def install(self):
		DB().query("drop table if exists users")
		DB().query("drop table if exists posts")
		DB().query("create table users (username text, password text)")
		DB().query("create unique index username on users (username)")
		DB().query("create table posts (user int, text text, date text)")
		DB().query("create index user on posts (user)")
		DB().query("insert into users values (?, ?)",  ('demo', md5sum('demo')))
		DB().query("insert into posts values (?, ?, datetime('now'))",  (1, 'Hello world'))
		return "Tables created!"

	index.exposed = True
	register.exposed = True
	install.exposed = True

# START

def start():
	cherrypy.tree.mount(Minitwit(), '/', 'dev.conf')
	cherrypy.server.socket_port = 9101
	cherrypy.engine.start()

if __name__ == '__main__':
	start()