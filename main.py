import firebase
import praw
import requests
import json
import formatter
from bs4 import BeautifulSoup
import config
import collections

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



global base
global reddit
base = firebase.FireBase()
reddit = praw.Reddit(client_id=config.CLIENT_ID, client_secret=config.SECRET,
                     user_agent="py:redditdiamondbot.com.reddit:v1.0 (by /u/deathfaith, /u/PatrioTech, and /u/cmcjacob)",
                     username=config.USERNAME,password=config.PASSWORD)

def api_handler(message):
    path = message["path"]
    donewithpath = False
    if 'put' in message["event"]:
        api_proc = message["data"]
        print(api_proc)
        if api_proc is not None:
            for call,args in api_proc.items():
                #print("ARGS: " + str(args))
                if 'poll' in call:
                    print("API: Detected poll. Processing")
                    process_new_comments()
                    donewithpath = True
                elif 'validate' in call:
                    print("API: Detected validate. Processing")
                    if args is not None:
                        find_space = args.find(' ')
                        if find_space > -1:
                            split_args = args.split(' ')
                            code = split_args[0]
                            transaction = split_args[1]
                            donator = split_args[2]
                            amount = 0
                            charity = 'None'
                            if code is not None and transaction is not None and donator is not None:
                                if 'override' in transaction:
                                    amount = randint(1, 10)
                                    charity = random.choice(charities)
                                    print("API: Validation override, updating database..")
                                    owner = diamondSuccess_API(amount, donator, code, transaction, charity)
                                    print("API: Database updated for owner:" + owner)
                                    donewithpath = True
                                else:
                                    amount, charity = get_receipt_info(transaction)
                                    if amount > 0:
                                        print("API: Validation succeeded, updating database..")
                                        owner = diamondSuccess_API(amount, donator, code, transaction, charity)
                                        print("API: Database updated for owner:" + owner)
                                        donewithpath = True
                                    else:
                                        print("API: Validation failed. Transaction '" + transaction + "' could not be parsed.")
                            else:
                                print("API: Failed to retrieve arguments for 'validate' call.")
    if donewithpath is True:
        print("Done processing. This call will now be deleted.")
        base.db.child("api").child(path).remove(base.usertoken)
        print("Call deleted, API continuing processing.")




print("Starting API handler for table 'api...")
api_stream = base.db.child("api").stream(api_handler)



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

def process_new_comments():
    print("process_new_comments() called")
    fire_response = requests.get('https://api.pushshift.io/reddit/search/comment/?q=!testdiamond').text
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
                actual_comment = reddit.comment(fullname)
                praw_comment = actual_comment.parent()
                author_parent = str(praw_comment.author)
                parent_id = comment['parent_id']
                instance_type = str(type(praw_comment))
                print("TYPE OF INSTANCE: " + instance_type)
                if 'Submission' in instance_type:
                    parent_comment = praw_comment.selftext
                elif 'Comment' in instance_type:
                    parent_comment = praw_comment.body
                author = comment['author']
                parent = comment['parent_id']
                subreddit = comment['subreddit']
                permalink = comment['permalink']
                print("[stream] add_diamond: " + author_parent + " " + author + " " + fullname + " " + subreddit + "\n" + parent_comment)
                new_diamond = base.add_diamond(author_parent, author, fullname, subreddit, parent_comment, permalink)
                reply = formatter.initial_comment(str(author_parent), str(actual_comment.author), new_diamond)
                actual_comment.reply(reply)
                print(reply)
                base.set_comment_as_processed(fullname)
                print('Comment marked as processed.')
                return True
        except (KeyError, praw.exceptions.APIException) as e:
            return False
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