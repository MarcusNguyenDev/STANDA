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
COMMIT_SUMMARY_LIMIT=10

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
    summary: str
    long_summary: str
    changes: List[str]

class Commit(TypedDict):
    id: str
    message: str
    diff: str
    

def build_commit_messages(commit: Commit) -> List[HumanMessage]:
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
        SystemMessage(content="Single sentence summary of the commit:"),
    ]

    return messages

def summarise_commits(commits: List[Commit]) -> CommitSummary:
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

    commit_summary_messages = [
        build_commit_messages(commit) for commit in commits[:COMMIT_SUMMARY_LIMIT]
    ]
    commit_summaries = [generation[0].message.content for generation in chat.generate(commit_summary_messages).generations]

    long_summary = chat([
        SystemMessage(content="Here are some summaries of git commit messages"),
        *[SystemMessage(content=summary) for summary in commit_summaries],
        SystemMessage(content="You are a developer, deliver a short single-paragraph monologue about what you did according to the summaries. Begin with the most important or interesting parts"),
        SystemMessage(content="Do not include a prelude to the monologue, just begin"),
    ]).content

    summary = chat([
        SystemMessage(content="Here is a short monologue from developer describing what they did yesterday"),
        SystemMessage(content=long_summary),
        SystemMessage(content="Speaking as the developer, summarise what you did yesterday in one sentence. Beginning with the most important parts"),
    ]).content

    return {
        "summary": summary,
        "long_summary": long_summary,
        "changes": commit_summaries,
    }

    
def get_commits(since: datetime, until: Optional[datetime]) -> List[Commit]:
    since_timestamp = int(since.timestamp())
    until_timestamp = int(until.timestamp()) if until else int(datetime.now().timestamp())
    response = requests.get(f"{GIT_API_URL}?since={since_timestamp}&until={until_timestamp}")
    return response.json()

def doing_what(message: str, say: FunctionType) -> str:
    say("Let me look...")
    human_time, since = get_since_time(message)
    print(f"{human_time=} {since=}")
    say("I'm reading your git history...")
    commits = get_commits(since, None)
    print(f"{commits=}")
    say("I'm summarising it...")
    summary = summarise_commits(commits)
    print(f"{summary=}")
    changes = "\n".join([f"- {change}" for change in summary['changes']])

    response = []
    response.append(f"Here's what you've been up to since {human_time}:")
    response.append("")
    response.append(f"Short summary: {summary['summary']}")
    response.append("")
    response.append("Long summary:")
    response.append(summary['long_summary'])
    response.append("")
    response.append("Here's a list of changes:")
    response.append(changes)

    say({
        "type": "mrkdown",
        "text": "\n".join(response),
    })

# Initializes your app with your bot token and socket mode handler
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# Listens to incoming messages that contain "hello"
# To learn available listener arguments,
# visit https://slack.dev/bolt-python/api-docs/slack_bolt/kwargs_injection/args.html
@app.message()
def message_hello(message, say):
    # say() sends a message to the channel where the event was triggered
    text = message['text'].lower()
    if "what was i doing" in text:
        doing_what(text, say)
    elif "what am i doing" in text:
        say(get_message_response(message['text']))
    elif "what are my blockers" in text:
        say(get_message_response(message['text']))
    else:
        print("Did not match any of the conditions")
        print(f"{message=} {say=}")

@app.event("app_mention")
def handle_app_mention_events(body, logger):
    # logger.info(body)
    pass

# Start your app
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()