import os
import re
from types import FunctionType

from typing import List, Optional, Tuple, TypedDict
from datetime import datetime, timedelta
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from langchain.chat_models import ChatOpenAI
from langchain import PromptTemplate, LLMChain
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    AIMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain.schema import (
    AIMessage,
    HumanMessage,
    SystemMessage
)

import requests

GIT_API_URL = "https://marcusnguyen-developer.com/commits"
CALENDAR_API_URL = "https://marcusnguyen-developer.com/cal"
COMMIT_SUMMARY_LIMIT=50

LAST_SUMMARY = ""

chat = ChatOpenAI(temperature=0)
CHAT_CONTEXT = [
    SystemMessage(content="You are a helpful assistant named STANDA, that tells people what they were doing before stand-up meetings"),
]

def get_since_time(human_string: str) -> Tuple[str, datetime]:
    human_time = human_string[32:-1]
    messages = [
        SystemMessage(content="Convert a human-readable string to a python timedelta. Example:"),
        SystemMessage(content="yesterday"),
        SystemMessage(content="timedelta(days=1)"),
        HumanMessage(content=human_time),
    ]

    response = chat(messages)

    delta = eval(response.content) if re.match(r"timedelta\(.+\)", response.content) else timedelta(days=1)
    return human_time, datetime.now() - delta
    

# def get_since_time(message: str) -> datetime:
#     # TODO parse the message to get the time
#     return datetime.now() - timedelta(days=1)

def get_message_response(message_text):
    response = chat(CHAT_CONTEXT + [HumanMessage(content=message_text)])
    print(f"{response=}")
    return response.content

class CommitSummary(TypedDict):
    doing: str
    summary: str
    long_summary: str
    changes: List[str]

class Commit(TypedDict):
    id: str
    message: str
    diff: str
    

def build_commit_messages(commit: Commit) -> List[SystemMessage]:
    messages = [
        SystemMessage(content="Here is a git commit message"),
        SystemMessage(content=commit['message']),
    ]

    if commit['diff'].count("\n") < 200:
        messages += [
            SystemMessage(content="Here is the diff"),
            SystemMessage(content=commit['diff']),
        ]

    messages += [
        SystemMessage(content="Now return a single-sentence in the style of a commit message:"),
    ]

    return messages

def summarise_commits(commits: List[Commit], say: FunctionType) -> CommitSummary:
    """
    Take a list of commits, and generate a summary using langchain.
    Commits are in the following format:
    ```json
    {
        "id": "abcdefghijklmnopqrstuvwxyz0123456789abcd",
        "message": "Add a new feature",
        "diff": "diff --git a/README.md b/README.md\nindex 2e65efe..d5f9c5c 100644\n--- a/README.md\n+++ b/README.md\n@@ -1,2 +1,3 @@\n # My Project\n\n+This is a new feature\n",
    }
    ```
    The chat should return three different summaries:
    1. A single-sentence summary of the commits
    2. A longer paragraph explaining the commits in more detail
    3. An itemised list of changes made
    """

    say("Summarising each commit...")
    commit_summary_messages = [
        build_commit_messages(commit) for commit in commits[:COMMIT_SUMMARY_LIMIT]
    ]
    commit_summaries = [generation[0].message.content for generation in chat.generate(commit_summary_messages).generations]

    say("Summarising the summaries....")
    long_summary = chat([
        SystemMessage(content="Here are some summaries of git commit messages"),
        *[SystemMessage(content=summary) for summary in commit_summaries],
        SystemMessage(content="You are a developer, deliver a short single-paragraph monologue about what you did according to the summaries. Begin with the most important or interesting parts"),
        SystemMessage(content="Do not include a prelude to the monologue, just begin with I..."),
    ]).content

    say("Summarising that summary.....")
    summary = chat([
        SystemMessage(content="Here is a short monologue from developer describing what they did yesterday"),
        SystemMessage(content=long_summary),
        SystemMessage(content="Speaking as the developer, summarise what you did yesterday in one sentence. Beginning with what the developer would consider the most important or interesting parts. Don't include trivial details"),
    ]).content

    say("Now I'm trying to figure out what you were _actually_ doing :stuck_out_tongue:")

    doing = chat([
        SystemMessage(content="Here is a summary of what a developer has done"),
        SystemMessage(content=summary),
        SystemMessage(content="Speaking as the developer, descirbe what you actually did in one short sentence. Be honest with some tongue-in-cheek humor"),
    ]).content

    say("Done :sweat_smile:")

    return {
        "summary": summary,
        "long_summary": long_summary,
        "changes": commit_summaries,
        "doing": doing,
    }

    
def get_commits(since: datetime, until: Optional[datetime]) -> List[Commit]:
    since_timestamp = int(since.timestamp())
    until_timestamp = int(until.timestamp()) if until else int(datetime.now().timestamp())
    response = requests.get(f"{GIT_API_URL}?since={since_timestamp}&until={until_timestamp}")
    return response.json()

#{"summary":"Team Scrum meeting","description":"Weekly team scrum meeting","location":"Standa HQ","startDate":"2023-05-13T09:00:00","endDate":"2023-05-13T10:00:00"}
class CalendarEvent(TypedDict):
    summary: str
    description: str
    location: str
    startDate: str
    endDate: str

def get_calendar() -> List[CalendarEvent]:
    response = requests.get(CALENDAR_API_URL)
    return response.json()

def build_event_message(event: CalendarEvent) -> List[SystemMessage]:
    messages = [
        SystemMessage(content="Here is a calendar event"),
        SystemMessage(content=f"Summary: {event['summary']}"),
        SystemMessage(content=f"Description: {event['description']}"),
        SystemMessage(content=f"Location: {event['location']}"),
        SystemMessage(content=f"Start: {event['startDate']}"),
        SystemMessage(content=f"End: {event['endDate']}"),
        SystemMessage(content="Now return a single-sentence in the style of a calendar event:"),
    ]

    return messages

def summarise_events(events: List[CalendarEvent], say: FunctionType) -> str:
    event_summary_messages = [
        build_event_message(event) for event in events
    ]
    event_summaries = [generation[0].message.content for generation in chat.generate(event_summary_messages).generations]

    say("Summarising what you did....")
    return chat([
        SystemMessage(content="Here are some summaries of calendar events"),
        *[SystemMessage(content=summary) for summary in event_summaries],
        SystemMessage(content="You are a developer, deliver a short single-paragraph monologue about what you did according to the summaries. Begin with the most important or interesting parts"),
        SystemMessage(content="Do not include a prelude to the monologue, just begin with I..."),
    ]).content


def did_what(message: str, say: FunctionType) -> str:
    say("Let's see...")
    human_time, since = get_since_time(message)
    print(f"{human_time=} {since=}")

    say("Reading your calendar...")
    events = get_calendar()
    print(f"{events=}")
    event_summary = summarise_events(events, say)

    say("Reading your git history...")
    commits = get_commits(since, None)
    print(f"{commits=}")
    git_summary = summarise_commits(commits, say)
    print(f"{git_summary=}")
    changes = "\n".join([f"- {change}" for change in git_summary['changes']])

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Here's what you've been up to since {human_time}:",
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Short summary*: {git_summary['summary']}",
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Some more details*: \n" + git_summary['long_summary'],
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*List of changes*: \n" + changes,
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Calendar summary*: {event_summary}",
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*What you were actually doing*: {git_summary['doing']}",
            }
        },
    ]

    flattened_blocks = [block["text"]["text"] for block in blocks]
    global LAST_SUMMARY
    LAST_SUMMARY = "\n".join(flattened_blocks)

    say(blocks=blocks)

def do_what(message: str, say: FunctionType):
    say("Well, based on what you did yesterday...")
    print(f"{LAST_SUMMARY=}")
    doing = chat([
        SystemMessage(content="Here is a summary of what a developer did yesterday"),
        SystemMessage(content=LAST_SUMMARY),
        SystemMessage(content="Speaking as the developer, what will you do today?"),
    ]).content

    say("Got it :smile:")

    say("Now, what should you _really_ do :smiling_imp:")
    actually_doing = chat([
        SystemMessage(content="Here is a summary of what a developer did yesterday"),
        SystemMessage(content=LAST_SUMMARY),
        SystemMessage(content="Speaking as the developer, describe what will you _actually_ do today in one sentence. Be honest with some tongue-in-cheek humor"),
    ]).content

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*What you should be doing*: {doing}",
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*What you should _actually_ be doing*: {actually_doing}",
            }
        },
    ]

    say(blocks=blocks)

def my_blockers(message: str, say: FunctionType):
    say("Let's see...")
    global LAST_SUMMARY
    print(f"{LAST_SUMMARY=}")

    blocked = chat([
        SystemMessage(content="Here is a summary of what a developer did yesterday"),
        SystemMessage(content=LAST_SUMMARY),
        SystemMessage(content="Speaking as the developer, is there anything you were blocked on? If so, what"),
    ]).content

    say("Got it :smile:")

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Blockers*: {blocked}",
            }
        },
    ]

    say(blocks=blocks)

# Initializes your app with your bot token and socket mode handler
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# Listens to incoming messages that contain "hello"
# To learn available listener arguments,
# visit https://slack.dev/bolt-python/api-docs/slack_bolt/kwargs_injection/args.html
@app.message()
def message_hello(message, say):
    text = message['text'].lower()
    try:
        if "what was i doing" in text:
            did_what(text, say)
        elif "what am i doing" in text:
            do_what(text, say)
        elif "what are my blockers" in text:
            my_blockers(text, say)
        else:
            print("Did not match any of the conditions")
            print(f"{message=} {say=}")
    except Exception as e:
        print(f"{e=}")
        print(f"{message=} {say=}")
        say("Sorry, something went wrong :(")

@app.event("app_mention")
def handle_app_mention_events(body, logger):
    # logger.info(body)
    pass

# Start your app
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()