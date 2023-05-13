import os
import re

from typing import List, Optional, TypedDict
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
COMMIT_SUMMARY_LIMIT=3

chat = ChatOpenAI(temperature=0)
CHAT_CONTEXT = [
    SystemMessage(content="You are a helpful assistant named STANDA, that tells people what they were doing before stand-up meetings"),
]

def get_since_time(human_string: str) -> datetime:
    messages = [
        SystemMessage(content="Convert a human-readable string to a python timedelta. Example:"),
        SystemMessage(content="yesterday"),
        SystemMessage(content="timedelta(days=1)"),
        HumanMessage(content=human_string[:17]),
    ]

    response = chat(messages)

    delta = eval(response.content) if re.match(r"timedelta\(.+\)", response.content) else timedelta(days=1)
    return datetime.now() - delta
    

# def get_since_time(message: str) -> datetime:
#     # TODO parse the message to get the time
#     return datetime.now() - timedelta(days=1)

def get_message_response(message_text):
    response = chat(CHAT_CONTEXT + [HumanMessage(content=message_text)])
    print(f"{response=}")
    return response.content

# Initializes your app with your bot token and socket mode handler
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# Listens to incoming messages that contain "hello"
# To learn available listener arguments,
# visit https://slack.dev/bolt-python/api-docs/slack_bolt/kwargs_injection/args.html
@app.message()
def message_hello(message, say):
    # say() sends a message to the channel where the event was triggered
    if "what was I doing" in message['text']:
        say(get_message_response(message['text']))
    elif "what am I doing" in message['text']:
        say(get_message_response(message['text']))
    elif "what are my blockers" in message['text']:
        say(get_message_response(message['text']))
    else:
        print("Did not match any of the conditions")
        print(f"{message=} {say=}")

# Start your app
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()