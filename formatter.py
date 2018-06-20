import re


paypal_url = "https://www.paypal.com/fundraiser/hub"
instructions_url = "https://www.reddit.com/r/RedditDiamondBot/wiki/index#wiki_how_does_it_work.3F"
about_page = "https://www.redditdiamond.com/about"
sub_url = "https://www.reddit.com/r/RedditDiamondBot/"
optout_url = "https://www.reddit.com/message/compose?to=RedditDiamondBot&subject=Opt-out&message=remove"
faq_url = "https://www.reddit.com/r/RedditDiamondBot/wiki/index/faq"
credits_url = "https://www.reddit.com/r/RedditDiamondBot/wiki/index/credits"
reddit_diamond_url = "https://www.redditdiamond.com/"

class Colour:
    Green, Red, White, Yellow = '\033[92m', '\033[91m', '\033[0m', '\033[93m'

# Used to reply to !RedditDiamond invocation
def initial_comment(receiver, donator, diamond_code):
    message_template = 'https://redditdiamond.com/verify/code=' + str(diamond_code) + '&donator=' + donator
    return ("It appears you'd like to gift u/" + receiver + " a Reddit Diamond 💎\n\n" +
        "To give this Diamond, please proceed to the [Paypal Charities](" + paypal_url + ") page, then [click here](" + message_template + ") to finalize the Diamond transfer.\n\n"
        "[**^(WHAT IS THIS?)**](" + about_page + ") ^(|) [^(OPT-OUT)](" + optout_url + ") ^(|) ^(Diamond) ^(#)^(" + str(diamond_code) + ")")

# After successful verification, the following is posted in response to user being rewarded with Diamond
def success_comment(donator, user_total, diamond_code, sub_info, charity):
    return ("# u/" + donator + " gifted you 💎 Reddit Diamond\n\n"
        "*Thank you, u/" + donator + ", for donating to " + charity + ".*\n\n"
       "[**^(WHAT IS THIS?)**](" + about_page + ") ^(|) [^(OPT-OUT)](" + optout_url + ") ^(|) ^(Diamond) ^(#)^(" + str(diamond_code) + ")")

# After successful verification, the following is PM'd to the user who fulfilled the Diamond
def success_pm(permalink, donator):
    return ("Thank you, " + donator + ", for donating and giving a Reddit Diamond!\n"
            "Your rewarded Diamond can be seen [here](" + permalink + ")!")

# If verification is failed, the following message is sent to the user who attempted to fulfill the Diamond
def failure_pm():
    return ("It appears you did not format your verification correctly or we could not successfully verify your donation.\n"
            "Please ensure your message was formatted as such and try again:\n\n"
            "Diamond Code: <Your Diamond Code>\n"
            "Verification: <Your Paypal Verification Link>\n\n"
            "If you have followed these steps and are still having problems verifying, please submit [a report](" + sub_url + ").\n"
            "Thank you!")

# This will always extract the 6 digit code from any string
# even one with URLs with digits
def extract_code(message):
    regex_results = str(re.findall('\d{7}', message))
    extracted_text = re.search('''(?<=')\s*[^']+?\s*(?=')''', regex_results)
    if extracted_text is not None: return extracted_text.group().strip()
    else: return 0

# Gets absolute url from any string (includes error-checking)
def extract_link(message):
    regex_results = re.search("(?P<url>https?://[^\s]+)", message).group("url")
    if regex_results is not None: return regex_results
    else: return 'INVALID'