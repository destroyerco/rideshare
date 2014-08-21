import webapp2
from simpleauth import SimpleAuthHandler
from app.base_handler import BaseHandler

# testing
from app.controllers.test_account import email_test
# end testing

import app.secrets as secrets

from app.model import *

app_config = {
    'webapp2_extras.sessions': {
        'cookie_name': '_simpleauth_sess',
        'secret_key': secrets.SESSION_KEY
    },
    'webapp2_extras.auth': {
        'user_attributes': []
    }
}

import wsgiref.handlers
import datetime
from datetime import date
from google.appengine.api import mail

import jinja2
from google.appengine.ext import db

import logging
import urllib
import random
import os.path

from app.controllers.circles import *
from app.controllers.events import *
from app.controllers.rides import *
from app.controllers.comments import *
from app.controllers.users import *
from app.controllers.invites import *
from app.controllers.alert import *
from app.controllers.accounts import *

from app.common.toolbox import doRender, split_address, grab_json

import csv

class Marketing(BaseHandler):
    def get(self):
        doRender(self, 'marketing/home.html')

class GetStarted(BaseHandler):
    def get(self):
        doRender(self, 'marketing/get_started.html')
    
class MapHandler(BaseHandler):
    def get(self):
        self.auth()
        user = self.current_user()

        circle = self.circle()

        doRender(self, 'map.html', {
            'user': user,
            'circle': circle
        })

class HomeHandler(BaseHandler):
    def get(self):
        self.auth()
        user = self.current_user()

        notis = Notification.all().filter('user = ', user.key()).fetch(5)

        today = datetime.date.today()
        upcoming = Ride.all().filter('date > ', today).fetch(20)

        for up in upcoming:
            up.dest_add = split_address(up.dest_add)
            if user.key() in up.passengers:
                up.is_pass = True
            else:
                up.is_pass = False

            up.is_driver = False
            if up.driver:
                if user.key() == up.driver.key():
                    up.is_driver = True

            up.date_str = up.date.strftime('%B %dth, %Y')

        for noti in notis:
            noti.ride.orig = split_address(noti.ride.origin_add)
            noti.ride.dest = split_address(noti.ride.dest_add)

        circles = Circle.all().fetch(100)

        for circle in circles:
            if circle.key() in user.circles:
                circle.user = True
            else:
                circle.user = False

        doRender(self, 'home.html', { 
            'user': user,
            'notis': notis,
            'upcoming': upcoming,
            'circles': circles
        })

class IncorrectHandler(BaseHandler):
    def get(self):
        self.redirect('/')

class HelpHandler(BaseHandler):
    def get(self):
        user = self.current_user()

        doRender(self, 'help.html', {
            'user': user
        })

class DetailHandler(BaseHandler):
    def get(self):
        self.auth()
        user = self.current_user()

        properties = ['name', 'email', 'phone', 'zip']

        user_json = grab_json(user, properties)

        doRender(self, 'details.html', {
            'user': user,
            'user_json': user_json
        })
    def post(self):
        self.auth()
        json_str = self.request.body
        data = json.loads(json_str)

        self.auth()
        user = self.current_user()

        user.name = data['name']
        user.email = data['email']
        user.phone = data['phone']
        user.zip = int(data['zip'])

        circle_match = Circle.all().filter('zip =', data['zip']).get()

        if circle_match:
            user.circles.append(circle_match.key())
        else:
            zip_row = None
            with open('app/common/zip_db.csv') as zip_db:
                zip_data = csv.reader(zip_db, delimiter=',')
                for row in zip_data:
                    if data['zip'] in row:
                        zip_row = row
                        break
            if zip_row:
                city = zip_row[2]
                circle = Circle()
                circle.name = 'Open ' + city + ' Circle'
                circle.description = 'An open circle for residents of ' + city + '.'
                circle.permission = 'public'
                circle.zip = int(data['zip'])
                circle.color = '#607d8b'
                circle.put()
                user.circles.append(circle.key())

        user.put()

        resp = {
            'message': 'Information updated'
        }

        self.response.write(json.dumps(resp))

app = webapp2.WSGIApplication([
    ('/', Marketing),
    ('/get_started', GetStarted),
    ('/map', MapHandler),

    # controllers/accounts.py
    ('/login', LoginHandler),
    ('/register', RegisterHandler),

    # controllers/rides.py
    ('/rides', RideHandler),
    ('/ride/(\d+)', GetRideHandler),
    ('/ride/(\d+)/edit', EditRide),
    ('/ride/(\d+)/driver', JoinDriver),
    ("/newride", NewRideHandler),
    ('/home', HomeHandler),
    ('/filter', FilterRides),
    ('/event/(\d+)/(\w+)', RideEvent),
    # end rides

    # controllers/users.py
    ('/user/(\d+)', GetUserHandler),
    ('/user/edit/(\d+)', EditUserHandler),
    ('/user/notification/(\d+)', NotificationUserHandler),
    ('/user', UserHandler),
    ('/user/photo/(\d+)', GetImage),
    # end users

    # controllers/comments.py
    ('/comment', CommentHandler),
    ('/comments', FetchComments),
    ('/comment/(\d+)', GetComment),
    # end comments

    # controllers/circles.py
    ('/circle/(\d+)', GetCircleHandler),
    ('/circle/(\d+)/invite', GetCircleInvite),
    ('/circle/(\d+)/invited', CircleInvited),
    ('/circle/(\d+)/change', ChangeCircle),
    ('/circle/(\d+)/edit', EditCircle),
    ('/circle/(\d+)/kick', KickMember),
    ('/circle/(\d+)/promote', PromoteMember),
    ('/circle/(\d+)/request', RequestJoin),
    ('/circle/(\d+)/accept', RequestAccept),
    ('/newCircle', NewCircleHandler),
    ('/circles', CircleHandler),
    ('/join_circle', JoinCircle),
    # end circles

    # controllers/invites.py
    ('/invite/(\d+)', SendInvite),
    ('/invite/(\d+)/name', SendInviteName),
    ('/invite/(\d+)/email', SendInviteEmail),
    ('/invite/names', GetNames),
    ('/invites', ViewInvites),
    # end invite

    # controllers/events.py
    ('/event/(\d+)', GetEventHandler),
    ('/events', EventHandler),
    ('/newevent', NewEventHandler),
    # end events

    # controllers/alert.py
    ('/alert/(\d+)/dismiss', DismissAlert),
    # end alert

    # auth routes
    webapp2.Route(
        '/auth/<provider>',
        handler='app.auth_handler.AuthHandler:_simple_auth',
        name='auth_login'
    ),
    webapp2.Route(
        '/auth/<provider>/callback', 
        handler='app.auth_handler.AuthHandler:_auth_callback',
        name='auth_callback'
    ),
    webapp2.Route(
        '/logout',
        handler='app.auth_handler.AuthHandler:logout',
        name='logout'
    ),
    ('/details', DetailHandler),
    # end auth routes
    ('/email_test', email_test),
    ('/help', HelpHandler),
    ('/.*', IncorrectHandler)
],
    config = app_config,
    debug = True
)