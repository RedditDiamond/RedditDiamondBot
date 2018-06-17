import time, os
from random import randint
import pyrebase
import config

def throw_error(err):
    print("Error: {0}".format(str(err.args[0])).encode("utf-8"))

class FireBase:
    # internal
    print("Base Instance has been called. You should only see this once.")
    firebase = None
    auth = None
    user = None
    usertoken = None
    db = None
    status = False
    # some stats
    count = 0
    totaldonated = 0
    topdonor = None
    topsub = None

    m_dbconfig = {
        "apiKey": os.environ["FIREBASE_API"],
        "authDomain": os.environ["FIREBASE_DOMAIN"],
        "databaseURL": os.environ["FIREBASE_DB_URL"],
        "projectId": os.environ["FIREBASE_PROJ_ID"],
        "storageBucket": os.environ["FIREBASE_STORAGE"],
        "messagingSenderId": os.environ["FIREBASE_SENDER_ID"]
    }

    # Connects to firebase server and sets required local vars
    def connect(self):
        try:
            self.firebase = pyrebase.initialize_app(self.m_dbconfig)
            self.auth = self.firebase.auth()
            self.auth.create_custom_token
            self.user = self.auth.sign_in_with_email_and_password('redditdiamondbot@gmail.com', 'RedditDiamond44')
            self.usertoken = self.user['idToken']
            self.db = self.firebase.database()
            print("FireBase loaded with token: " + str(self.usertoken))
            return True

        except:
            print('FATAL: Failed to connect')
            return False

    # The user token needs to be refreshed once every hour
    def refresh_token(self, thetoken):
        self.user = self.auth.refresh(thetoken)
        self.usertoken = self.user['idToken']

    # Returns total # of validated diamonds
    def get_diamond_count(self):
        try:
            children = self.db.child("validated").get(self.usertoken).val()
            return len(children)
        except Exception as e:
            throw_error(e)
            return 0

    # Sets topic as processed
    def set_comment_as_processed(self, fullname):
        try:
            ddata = {"processed": True}
            self.db.child("queue").child(fullname).set(ddata, self.usertoken)
            return True
        except Exception as e:
            throw_error(e)
            return False


    # Checks if topic has been processed
    def is_comment_processed(self, fullname):
        try:
            fix_fullname = fullname.find('_')
            if fix_fullname > -1:
                split_full = fullname.split('_')
                fixed_fullname = split_full[1]
            else:
                fixed_fullname = fullname
            pull_db = self.db.child("queue").child(fixed_fullname).get().val()
            isproc = pull_db["processed"]
            if isproc is not None:
                return isproc
        except Exception as e:
            return False

    def get_processed_comments(self):
        try:
            pull_db = self.db.child("queue").get().val()
            return pull_db
        except Exception as e:
            return False

    def get_user_total_in_sub(self, user, sub):
        try:
            total = self.db.child("stats").child("subs").child(sub).child(user).get(self.usertoken).val()
            if len(total) != 0:
                return total["total_donated"]
            else:
                return 0
        except:
            return 0

    # Pulls an unvalidated diamond, and transfers it to validated with updated fields
    # Also updates important local statistic variables 
    def validate_diamond(self, code, amount, donator, paypalreceipt, charity):
        pull_db = self.db.child("unvalidated").get(self.usertoken)
        try:
            pull_db = pull_db.val()
        except:
            print("Fatal database error: " + str(pull_db))
        theinitiator = pull_db[str(code)]['initiator']
        thefullname = pull_db[str(code)]['fullname']
        thecomment = pull_db[str(code)]['comment']
        theowner = pull_db[str(code)]['owner']
        thetime = pull_db[str(code)]['timestamp']
        thesub = pull_db[str(code)]['sub']

        if theinitiator is None or thecomment is None or theowner is None or thetime is None or thesub is None:
            print('Fatal database error: check vars')
            return False
        data = {"amount": amount, "fullname": thefullname, "owner": theowner, "initiator": theinitiator,
                "donator": donator, "paypal_receipt": paypalreceipt, "sub": thesub, "timestamp": thetime,
                "charity": charity, "comment": thecomment, "code": code}


        self.db.child("unvalidated").child(code).remove()
        self.db.child("validated").child(code).set(data, self.usertoken)
        user_sub_total = self.get_user_total_in_sub(donator, thesub)
        user_sub_total = user_sub_total + int(amount)
        data = {"total_donated" : user_sub_total }
        self.db.child("stats").child("subs").child(thesub).child(donator).set(data, self.usertoken)
        return theowner



    # Adds an unvalidated Diamond to database, updates totaldonated $
    # Returns diamond code if success (no reason this should really ever fail though)
    def add_diamond(self, owner, initiator, fullname, sub, comment, permalink):
        try:
            fix_fullname = fullname.find('_')
            if fix_fullname > -1:
                split_full = fullname.split('_')
                fixed_fullname = split_full[1]
            else:
                fixed_fullname = fullname

            dcode = int(self.generate_diamond_code())
            data = {
                "code": dcode,
                "fullname": fixed_fullname,
                "initiator": initiator,
                "owner": owner,
                "sub": sub,
                "comment": comment,
                "permalink": permalink,
                "timestamp": time.time(),
            }

            self.db.child("unvalidated").child(str(dcode)).set(data, self.usertoken)
            return dcode
        except:
            throw_error('add_diamond failed for ' + owner)
            return 0


    def get_diamond(self, code):
        try:
            pull_db = self.db.child("validated").child(code).get().val()
            return pull_db
        except Exception as e:
            throw_error(e)
            return None

    # Generates a unique diamond code
    def generate_diamond_code(self):
        randomcode = randint(1000000, 9999999)
        return randomcode

    # Returns true if hash is in 'unvalidated'
    def code_in_unvalidated(self, code):
        try:
            pull_db = self.db.child("unvalidated").get(self.usertoken).val()
            if pull_db[code] is None:
                return False
            else:
                return True
        except:
            print("Fatal db error: code_in_unvalidated: couldn't pull code " + code)
            return False


    # Returns true if hash is in 'unvalidated'
    def code_in_validated(self, code):
        try:
            pull_db = self.db.child("validated").get(self.usertoken).val()
            if pull_db[code] is None:
                return False
            else:
                return True
        except:
            print("Fatal db error: code_in_validated: couldn't pull code " + code)
            return False

    # Checks for code in both validated and unvalidated tables
    def code_exists(self, thecode):
        if self.code_in_validated(thecode):
            return True
        elif self.code_in_unvalidated(thecode):
            return True
        return False

    # gets totals
    def calculate_user_totals(self, username):
        donations = self.db.child("validated").order_by_child("donator").equal_to(username).get()
        try:
            donations = donations.val()
        except IndexError:
            donations = []

        received = self.db.child("validated").order_by_child("owner").equal_to(username).get()
        try:
            received = received.val()
        except IndexError:
            received = []

        donations_total = {"count": len(donations), "amount": 0}
        received_total = {"count": len(received), "amount": 0}

        for donation in donations:
            donations_total["amount"] = donations_total["amount"] + int(donations[donation]["amount"])

        for item in received:
            received_total["amount"] = received_total["amount"] + int(received[item]["amount"])

        return donations_total, received_total

    # gets other totals
    def calculate_sub_totals(self, sub_name):
        if not self.status: return 0
        if sub_name == "all":
            diamonds = self.db.child("validated").get()
        else:
            diamonds = self.db.child("validated").order_by_child("sub").equal_to(sub_name).get()

        try:
            diamonds = diamonds.val()
        except IndexError:
            diamonds = []

        diamonds_total = {"count": len(diamonds), "amount": 0}

        for diamond in diamonds:
            if diamond == "stats":
                continue
            diamonds_total["amount"] = diamonds_total["amount"] + diamonds[diamond]["amount"]

        return diamonds_total

    # constructor
    def __init__(self):
        self.status = self.connect()

#print("Validate = " + str(diamond))
#FB_Object = FireBase()
#diamond = FB_Object.add_diamond("cmcjacob", "PatrioTech", "e0l8785", "CatsBeingCats", "This is my awesome comment!")
#print(str(diamond))
#print('Validation: ' + FB_Object.validate_diamond(diamond, 50, "deathfaith", "override", "Water.org"))
#get_diamond = FB_Object.get_diamond('3614710')
#print(str(get_diamond))
#diamond_obj = FB_Object.get_diamond(str(diamond))
#diamond = FB_Object.add_diamond( 'cmcjacob', 'PatrioTech', e0kzm0d, 'CatsBeingCats', "Here's my amazing cat. You'll love it!")
#print("add_diamond = " + diamond)

object = FireBase()