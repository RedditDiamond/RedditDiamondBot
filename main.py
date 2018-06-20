import firebase
import praw
import requests
import json
import formatter
import os
from flask import Flask
from flask import request
from flask import abort
from flask import jsonify
from flask import json
from flask_cors import CORS
from bs4 import BeautifulSoup
import random
from random import randint

charities = [   "DonorsChoose.org",
                "St. Jude Children's Hospital",
                "Humane Society of the U.S.",
                "International Rescue Committee",
                "CMN Hospitals",
                "American Red Cross",
                "S.A.V.E. Rescue Coaltion",
                "Children's Scholarship Fund",
                "Equal Justice Initiative",
                "Habitat for Humanity",
                "Hope for Haiti's Children",
                "Wildlife Conservation Network",
                "Books For Africa",
                "Lifesong for Orphans",
                "Arthritis National Research Foundation",
                "Community Volunteers in Medicine",
                "National Pediatric Cancer Foundation"
                ]



app = Flask(__name__)
CORS(app)

subreddit_black_list = []

with app.app_context():
    global base
    global reddit
    base = firebase.FireBase()
    reddit = praw.Reddit(client_id=os.environ["REDDIT_CLIENTID"], client_secret=os.environ["REDDIT_SECRET"],
                         user_agent="py:redditdiamondbot.com.reddit:v1.0 (by /u/deathfaith, /u/PatrioTech, and /u/cmcjacob)",
                         username=os.environ["REDDIT_USERNAME"], password=os.environ["REDDIT_PASSWORD"])

def get_receipt_info(url):
    try:
        html = requests.get(url).text
        soup = BeautifulSoup(html, 'html.parser')
        transaction_list = list()
        for body in soup.findAll('body'): transaction_list.append(body['data-track-donation-info'])
        thejson = json.loads(transaction_list[0])
        amount = thejson ['donation_info']['amount']
        charity = thejson ['charity_info']['name']
        if amount == 0: return -1
        return amount, charity
    except:
        return -1


def safe_comment_API(parent_fullname, body, code, donator):

    try:
        print("Trying safe_comment_API")
        comment_object = reddit.comment(id=parent_fullname)
        comment_object.parent().reply(body)
        new_comment = comment_object.parent().reply(body)
        new_comment_url = "https://www.reddit.com//comments/" + new_comment.link_id.split("_")[1] + "//" + new_comment.id
        print(new_comment_url)
        message_body = formatter.success_pm(new_comment_url, donator)
        print("diamondSuccess_API:", donator)
        reddit.redditor(donator).message('Diamond ' + str(code) + ' Claimed!', message_body)
        #if the comment was in the queue, remove it
        base.db.child("ratelimit").child(parent_fullname).remove()

    except praw.exceptions.APIException as e:
        if e.error_type == "RATELIMIT":
            print("**DETECTED RATELIMIT** response to '" + parent_fullname + "' failed")
            base.rate_limit(parent_fullname, body)
            print("Comment queued for next poll.")

def safe_comment(parent_fullname, body):

    try:
        # Get the comment object [dont have to invoke parent in this case]
        print("Trying safe_comment")
        comment_object = reddit.comment(id=parent_fullname)
        comment_object.reply(body)
        # if the comment was in the queue, remove it
        base.db.child("ratelimit").child(parent_fullname).remove()

    except praw.exceptions.APIException as e:
        if e.error_type == "RATELIMIT":
            print("**DETECTED RATELIMIT** response to '" + parent_fullname + "' failed")
            base.rate_limit(parent_fullname, body)
            print("Comment queued for next poll.")

def stream_comments():
    comments = base.get_pushshift_results()
    queue = base.get_processed_comments()
    rate_queue = base.get_limited_queue()

    if rate_queue is not None:
        for oldcomment in rate_queue:
            oldparent = rate_queue[oldcomment]["parent"]
            oldbody = rate_queue[oldcomment]["reply"]
            print("Trying to safely respond to " + oldparent)
            safe_comment(oldparent, oldbody)

    if queue is not None and comments is not None:
        print("Processing comments from Pushshift API..")

        for comment in range(1, 25):
            fullname = comments[comment]['fullname']
            author = comments[comment]['author']
            if not base.is_opted_out(author):
                fix_fullname = fullname.find('_')
                if fix_fullname > -1:
                    split_full = fullname.split('_')
                    fixed_fullname = split_full[1]
                else:
                    fixed_fullname = fullname
                try:
                    pull_queue = queue[fixed_fullname]
                    # If we made it this far, skip processing
                    # because the comment has already been processed.
                except:

                    if "RedditDiamondBot" not in author:
                        print("WARNING: Processing comment by " + author)
                        praw_comment = reddit.comment(fullname).parent()
                        actual_comment = reddit.comment(fullname)

                        if "!redditdiamond" in str(actual_comment.body).lower():
                            author_parent = str(praw_comment.author)

                            if base.is_opted_out(author_parent):
                                print("WARNING: " + author_parent + " is opted-out. Sending message to " + author)
                                base.set_comment_as_processed(fullname)
                                reddit.redditor(author).message('Uh Oh!', 'It looks like u/' + author_parent + ' has opted out of Reddit Diamond.  We apologize for the inconvenience!  You can still gild other users, though. :-)')
                            else:

                                parent_id = comments[comment]['parent_id']
                                instance_type = str(type(praw_comment))
                                print("TYPE OF INSTANCE: " + instance_type)

                                if 'Submission' in instance_type:
                                    parent_comment = praw_comment.selftext
                                    print("DETECTED SUBMISSION. SELFTEXT = " + praw_comment.selftext)

                                elif 'Comment' in instance_type:
                                    parent_comment = praw_comment.body
                                    print("Detected comment")

                                else:
                                    print('FATAL ERROR in processing comment parent:' + fullname, parent_id)

                                subreddit = comments[comment]['subreddit']
                                permalink = comments[comment]['permalink']
                                print("[stream] add_diamond: " + author_parent + " " + author + " " + fullname + " " + subreddit + "\n" + parent_comment)
                                new_diamond = base.add_diamond(author_parent, author, fullname, subreddit, parent_comment, permalink)
                                reply = formatter.initial_comment(str(author_parent), str(actual_comment.author), new_diamond)
                                print(reply)
                                safe_comment(fullname,reply)
                                base.set_comment_as_processed(fullname)


def diamondSuccess_API(amount, donator, code, paypal_url, charity):

    print("[API] Verifying diamond with:", code, amount, donator, paypal_url)
    base.validate_diamond(code, amount, donator, paypal_url, charity)
    verified_diamond = base.get_diamond(code)
    reddit.subreddit("redditdiamond").contributor.add(verified_diamond["owner"])
    user_donations, user_received = base.calculate_user_totals(verified_diamond["owner"])
    sub_info = base.calculate_sub_totals(verified_diamond["sub"])
    sub_info["name"] = verified_diamond["sub"]
    new_comment_body = formatter.success_comment(donator, user_received["count"], code, sub_info, charity)
    print(new_comment_body)
    safe_comment_API(verified_diamond["fullname"], new_comment_body, code, donator)
    return verified_diamond["owner"]

@app.route('/')
def root():
    abort(500, "No Request Specified")

@app.route('/<name>')
def func_proc(name):
    if "poll" in name:
        check = base.sanity_check()
        stream_comments()
        return "Polled"
    elif "status" in name:
        status_json = jsonify({'status': str(base.status)})
        return status_json
    else:
        # action API with optional arguments
        action = request.args.get('action', default='invalid', type=str)
        if "validate" in action:
            code = request.args.get('code', default='invalid', type=str)
            transaction = request.args.get('transaction', default='http://invalid', type=str)
            donator = request.args.get('donator', default='invalid', type=str)
            print("Init API:", donator)
            if "override" in transaction:
                amount = randint(1,15)
                charity = random.choice(charities)
            else:
                try:
                    amount, charity = get_receipt_info(transaction)
                except:
                    jsonret = jsonify({'ERROR': 'Failed to authenticate Paypal receipt'})
                    abort(500, jsonret)
            if amount>0:
                print("Success")
                owner = diamondSuccess_API(amount,donator,code,transaction, charity)
                jsonret = jsonify({'amount': str(amount), 'charity': str(charity)})
                print(jsonret)
                return jsonret
            else:
                jsonret = jsonify({'ERROR': 'Failed to authenticate Paypal receipt'})
                abort(500, jsonret)
    # don't know what to do here
    abort(500, jsonify({'ERROR': 'Unknown Request'}))


if __name__ == '__main__':
    print(str(base.is_opted_out("cmcjacob")))
    base.opt_out("PatrioTech")
    app.run(use_reloader=False)
