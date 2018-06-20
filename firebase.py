import time, os
from random import randint
import pyrebase

def throw_error(err):
    print("THROW ERROR: {0}".format(str(err.args[0])).encode("utf-8"))

class FireBase:
    # internal
    print("Base Instance has been called. You should only see this once.")
    firebase = None
    auth = None
    user = None
    usertoken = None
    db = None
    status = False
    ticker = 0
    # some stats (deprecated)
    count = 0
    totaldonated = 0
    topdonor = None
    topsub = None

    m_Firebase = {
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
            self.firebase = pyrebase.initialize_app(self.m_Firebase)
            self.auth = self.firebase.auth()
            self.user = self.auth.sign_in_with_email_and_password(os.environ["FIREBASE_EMAIL"], os.environ["FIREBASE_PASSWORD"])
            self.usertoken = self.user['idToken']
            self.db = self.firebase.database()
            print("FireBase loaded with token: " + str(self.usertoken))
            return True

        except Exception as e:
            print("FATAL: Pyrebase failed to connect!")
            throw_error(e)
            return False


    # The user token needs to be refreshed once every hour
    def refresh_token(self):
        refresh = self.user['refreshToken']
        #print("Previous token: " + self.usertoken)
        self.user = self.auth.refresh(refresh)
        self.usertoken = self.user['idToken']
        print("NEW TOKEN: " + self.usertoken)


    # this is how we know exactly when to refresh the token
    # IF YOU DELETE THE SANITY TABLE, YOU ARE FIRED!!!1
    def sanity_check(self):
        try:
            sanity = self.db.child("sanity").get(self.usertoken).val()
            if sanity is not None:
                return True
            else:
                print("WARNING: Failed sanity check, refreshing token..")
                self.refresh_token()
                return False
        except:
            print("WARNING: Failed sanity check, refreshing token..")
            self.refresh_token()
            return False


    # gets pushshift results from diamond-auto-api
    def get_pushshift_results(self):
        children = self.db.child("pushshift").get(self.usertoken).val()
        return children


    # checks if a user is opted-out
    def is_opted_out(self, username):
        try:
            children = self.db.child("optout").child(str(username)).get(self.usertoken).val()
            print(str(children))
            if children is not None:
                return True
            else:
                return False
        except:
            return False


    # opts a user out from processing
    def opt_out(self, username):
        data = {'opt':'out'}
        self.db.child("optout").child(str(username)).set(data, self.usertoken)


    # Returns total # of validated diamonds
    def get_diamond_count(self):
        try:
            children = self.db.child("validated").get(self.usertoken).val()
            return len(children)
        except Exception as e:
            print("FAILED TO RETURN DIAMOND COUNT")
            throw_error(e)
            return 0


    # returns a list of rate-limited comments from the database
    def get_limited_queue(self):
        try:
            data = self.db.child("ratelimit").get(self.usertoken).val()
            return data
        except:  # nothing in queue
            return None


    # inserts a rate-limited comment into the database to be posted later
    def rate_limit(self, parent_fullname, the_reply):
        limited_data = {'parent': parent_fullname, 'reply': the_reply}
        self.db.child("ratelimit").child(parent_fullname).set(limited_data, self.usertoken)


    # Sets topic as processed
    def set_comment_as_processed(self, fullname):
        try:
            ddata = {"processed": True}
            self.db.child("queue").child(fullname).set(ddata, self.usertoken)

            return True
        except Exception as e:
            print("FAILED TO SET COMMENT AS PROCESSED")
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
            pull_db = self.db.child("queue").child(fixed_fullname).get(self.usertoken).val()
            isproc = pull_db["processed"]
            if isproc is not None:
                return isproc
        except Exception as e:
            return False

    def get_processed_comments(self):
        try:
            pull_db = self.db.child("queue").get(self.usertoken).val()
            return pull_db
        except Exception as e:
            print("FAILURE GETTING PROCESSED COMMENTS:")
            print(str(e))
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


    # Gets a diamond's information from the database
    def get_diamond(self, code):
        try:
            pull_db = self.db.child("validated").child(code).get(self.usertoken).val()
            return pull_db
        except Exception as e:
            print("FAILED TO GET DIAMOND " + code)
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
        donations = self.db.child("validated").order_by_child("donator").equal_to(username).get(self.usertoken)
        try:
            donations = donations.val()
        except IndexError:
            donations = []

        received = self.db.child("validated").order_by_child("owner").equal_to(username).get(self.usertoken)
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
            diamonds = self.db.child("validated").get(self.usertoken)
        else:
            diamonds = self.db.child("validated").order_by_child("sub").equal_to(sub_name).get(self.usertoken)

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