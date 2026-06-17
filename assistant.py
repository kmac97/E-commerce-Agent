#!/usr/bin/env python3
"""
E-commerce AI Assistant
=======================
Run this file to start the assistant:

    python assistant.py

Requirements:
    pip install openai rich python-dotenv

You also need a .env file in this folder with:
    OPENAI_API_KEY=sk-your-key-here
"""

import os
import sys

# ─────────────────────────────────────────────
# DEPENDENCY CHECK
# Give clear error messages if packages aren't installed.
# ─────────────────────────────────────────────

def check_dependencies():
    missing = []
    try:
        import openai
    except ImportError:
        missing.append("openai")
    try:
        from dotenv import load_dotenv
    except ImportError:
        missing.append("python-dotenv")

    if missing:
        print("\n❌ Missing required packages. Run this command first:\n")
        print(f"    pip install {' '.join(missing)} rich\n")
        sys.exit(1)

check_dependencies()

# ─────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────

from dotenv import load_dotenv
from openai import OpenAI

import config
from utils.formatter import (
    print_welcome,
    print_response,
    print_thinking,
    print_saved,
    print_error,
    print_info,
    print_saved_list,
)
from utils.saver import save_response, list_saved

# ─────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────

# Load .env file (your API key lives here)
load_dotenv()

# Get the API key
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print("\n❌ No API key found.\n")
    print("Create a file called .env in this folder and add:\n")
    print("    OPENAI_API_KEY=sk-your-key-here\n")
    print("Get a key at: https://platform.openai.com\n")
    sys.exit(1)

# Set up the OpenAI client
client = OpenAI(api_key=api_key)

# ─────────────────────────────────────────────
# CONVERSATION MEMORY
# Keeps track of the conversation so the assistant
# remembers what was said earlier in the session.
# ─────────────────────────────────────────────

conversation_history = []
last_question = ""
last_response = ""


def get_ai_response(user_message: str) -> str:
    """
    Send the user's message to the AI and get a response back.
    Keeps conversation history so context is maintained.
    """
    global conversation_history

    # Add the user's message to the history
    conversation_history.append({
        "role": "user",
        "content": user_message,
    })

    # Trim history if it gets too long (saves money and keeps responses fast)
    if len(conversation_history) > config.MAX_HISTORY_MESSAGES:
        # Keep the most recent messages, always drop from the start
        conversation_history = conversation_history[-config.MAX_HISTORY_MESSAGES:]

    # Build the full message list with the system prompt at the top
    messages = [
        {"role": "system", "content": config.SYSTEM_PROMPT}
    ] + conversation_history

    try:
        # Call the OpenAI API
        response = client.chat.completions.create(
            model=config.MODEL,
            messages=messages,
            max_tokens=config.MAX_TOKENS,
            temperature=config.TEMPERATURE,
        )

        # Extract the text response
        assistant_message = response.choices[0].message.content

        # Add it to history for future context
        conversation_history.append({
            "role": "assistant",
            "content": assistant_message,
        })

        return assistant_message

    except Exception as e:
        error_msg = str(e)

        # Give helpful error messages for common problems
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
            return "❌ API key problem. Check your .env file has the correct key."
        elif "rate_limit" in error_msg.lower():
            return "❌ Too many requests. Wait a moment and try again."
        elif "insufficient_quota" in error_msg.lower():
            return "❌ You've run out of OpenAI credits. Add more at platform.openai.com."
        else:
            return f"❌ Something went wrong: {error_msg}"


def extract_topic_from_question(question: str) -> str:
    """
    Pull a short topic name from the question for use as a filename.
    E.g. "Tell me about posture correctors" → "posture correctors"
    """
    # Strip common opener phrases
    openers = [
        "tell me about", "what do you think about", "can you research",
        "help me with", "i want to sell", "i'm thinking about", "what about",
        "research", "analyse", "analyze", "should i sell",
    ]
    q = question.lower().strip()
    for opener in openers:
        if q.startswith(opener):
            q = q[len(opener):].strip()
            break

    # Trim to a reasonable length and clean up
    topic = q[:50].strip(" ?.,!")
    return topic if topic else "research"


# ─────────────────────────────────────────────
# COMMAND HANDLERS
# ─────────────────────────────────────────────

def handle_save():
    """Save the last response to the data folder."""
    global last_question, last_response

    if not last_response:
        print_info("Nothing to save yet. Ask a question first.")
        return

    topic = extract_topic_from_question(last_question)
    filepath = save_response(
        topic=topic,
        question=last_question,
        response=last_response,
        category=config.DEFAULT_SAVE_CATEGORY,
    )
    print_saved(filepath)


def handle_list():
    """Show all saved research."""
    items = list_saved()
    print_saved_list(items)


def handle_clear():
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")
    print_welcome()


# ─────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────

def main():
    global last_question, last_response

    # Clear screen and show welcome banner
    os.system("cls" if os.name == "nt" else "clear")
    print_welcome()

    print_info(f"\nUsing model: {config.MODEL}")
    print_info("Type your question or product idea to get started.\n")

    while True:
        try:
            # Get user input
            user_input = input("\nYou: ").strip()

            # Skip empty input
            if not user_input:
                continue

            # Handle special commands
            command = user_input.lower()

            if command in ("quit", "exit", "q"):
                print_info("\nGoodbye! Good luck with your business. 🚀\n")
                break

            elif command == "save":
                handle_save()
                continue

            elif command == "list":
                handle_list()
                continue

            elif command == "clear":
                handle_clear()
                continue

            elif command == "help":
                print_info(
                    "\nCommands:\n"
                    "  save   → Save the last response to your research folder\n"
                    "  list   → Show all saved research\n"
                    "  clear  → Clear the screen\n"
                    "  quit   → Exit the assistant\n"
                )
                continue

            # Regular question — get AI response
            last_question = user_input
            print_thinking()

            response = get_ai_response(user_input)
            last_response = response

            print_response(response)
            print_info("💡 Tip: type 'save' to save this to your research folder.")

        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            print_info("\n\nGoodbye! 🚀\n")
            break

        except Exception as e:
            print_error(f"Unexpected error: {e}")
            print_info("Try again or type 'quit' to exit.")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    main()
