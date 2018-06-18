import pyrebase
import config
from time import sleep

global firebase
global auth
global user
global usertoken
global db

firebase = None
auth = None
user = None
usertoken = None
db = None

firebase = pyrebase.initialize_app(config.m_Firebase)
auth = firebase.auth()
user = auth.sign_in_with_email_and_password('redditdiamondbot@gmail.com', 'RedditDiamond44')
usertoken = user['idToken']
db = firebase.database()
tick = 0

while(True):
    tick = tick + 1
    print("Polling firebase...")
    data = { "poll": "yep"}
    db.child("api").child("polltimer").set(data, usertoken)
    sleep(10)
    if (tick > 180):
        refresh = user['refreshToken']
        user = auth.refresh(refresh)
        usertoken = user['idToken']
        print("NEW TOKEN: " + usertoken)
        tick = 0



