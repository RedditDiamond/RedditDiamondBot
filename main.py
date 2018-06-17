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
import config
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
                "Equal Justice Initiative" ]



app = Flask(__name__)
CORS(app)

subreddit_black_list = []

with app.app_context():
    global base
    global reddit
    base = firebase.FireBase()
    reddit = praw.Reddit(client_id=os.environ["REDDIT_CLIENTID"],
client_secret=os.environ["REDDIT_SECRET"],
user_agent="py:redditdiamondbot.com.reddit:v1.0 (by /u/deathfaith, /u/PatrioTech, and /u/cmcjacob)",
username=os.environ["REDDIT_USERNAME"],
password=os.environ["REDDIT_PASSWORD"])

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

def stream_comments():
    print("stream_comments() called")
    fire_response = requests.get('https://api.pushshift.io/reddit/search/comment/?q=!redditdiamond').text
    fire_json = json.loads(fire_response)['data']
    queue = base.get_processed_comments()
    for comment in fire_json:
        fullname = comment['id']
        # print("is_processed: " + str(base.is_comment_processed(id)))
        fix_fullname = fullname.find('_')
        if fix_fullname > -1:
            split_full = fullname.split('_')
            fixed_fullname = split_full[1]
        else:
            fixed_fullname = fullname
        try:
            if fixed_fullname not in queue:
                praw_comment = reddit.comment(fullname).parent()
                actual_comment = reddit.comment(fullname)
                if "!redditdiamond" in str(actual_comment.body).lower():
                    author_parent = str(praw_comment.author)
                    parent_id = comment['parent_id']
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
                    author = comment['author']
                    parent = comment['parent_id']
                    subreddit = comment['subreddit']
                    permalink = comment['permalink']
                    print("[stream] add_diamond: " + author_parent + " " + author + " " + fullname + " " + subreddit + "\n" + parent_comment)
                    new_diamond = base.add_diamond(author_parent, author, fullname, subreddit, parent_comment, permalink)
                    print(new_diamond)
                    reply = formatter.initial_comment(str(author_parent), str(actual_comment.author), new_diamond)
                    print(reply)
                    actual_comment.reply(reply)
                    base.set_comment_as_processed(fullname)
        except (KeyError, praw.exceptions.APIException) as e:
            print(e)


def diamondSuccess_API(amount, donator, code, paypal_url, charity):
    print("[API] Verifying diamond with:", code, amount, donator, paypal_url)
    base.validate_diamond(code, amount, donator, paypal_url, charity)
    verified_diamond = base.get_diamond(code)
    reddit.subreddit("redditdiamond").contributor.add(verified_diamond["owner"])
    user_donations, user_received = base.calculate_user_totals(verified_diamond["owner"])
    sub_info = base.calculate_sub_totals(verified_diamond["sub"])
    sub_info["name"] = verified_diamond["sub"]
    invoke_comment = reddit.comment(id=verified_diamond["fullname"])
    new_comment_body = formatter.success_comment(donator, user_received["count"], code, sub_info, charity)
    print(new_comment_body)
    new_comment = invoke_comment.parent().reply(new_comment_body)
    new_comment_url = "https://www.reddit.com//comments/" + new_comment.link_id.split("_")[1] + "//" + new_comment.id
    print(new_comment_url)
    message_body = formatter.success_pm(new_comment_url, donator)
    print("diamondSuccess_API:", donator)
    theperson = reddit.redditor(donator).message('Diamond ' + str(code) + ' Claimed!', message_body)
    return verified_diamond["owner"]


@app.route('/')
def root():
    abort(500, "No Request Specified")


@app.route('/<name>')
def func_proc(name):

    if "poll" in name:
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
                amount = randint(1,5)
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
    app.run(use_reloader=False)