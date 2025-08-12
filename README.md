# F3 Nation Slack Bot

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

F3 Nation is a Slack bot you can install to your workspace to help you with all things F3, including scheduling, region / AO managment, attendance tracking, and more. This bot is meant to eventually replace paxminer/slackblast, qsignups, and weaselbot.

Installation is as simple as a [simple link click](#getting-started-) (with eventual addition to the official Slack app directory?)

# Getting started

Installation to your Slack workspace is simple:
1. Click TBD link from a desktop computer
2. Make sure to select your region in the upper right if you are signed into multiple spaces

To get started, use the `/f3-nation-settings` command to start setting your schedule and preferences.
                                                                         
# Calendar

To set your schedule, use the calendar menu in `/f3-nation-settings`. Once your schedule is up, you can visit the calendar by using the `/calendar` command.

# Contributing

The F3 Nation Slack Bot is in active development, and I welcome any and all help or contributions! Feel free to leave an [Issue](https://github.com/F3-Nation/f3-nation-slack-bot/issues) with bugs or feature requests, or even better leave us a [Pull Request](https://github.com/F3-Nation/f3-nation-slack-bot/pulls).

## Local Development

If you'd like to contribute to the F3 Nation Slack Bot, I highly recommend setting up a local development environment for testing. This is super easy to spin up thanks to @weshayutin for the Docker configuration!

### Project setup

1. Clone the repo:
  ```bash
  git clone https://github.com/F3-Nation/f3-nation-slack-bot.git
  ```
2. Run Ngrok with the following command from your terminal and copy the forwarding URL ID (the part before `ngrok-free.app`):
  ```bash
  ngrok http 3000
  ```
3. Create your development Slack bot: 
    1. Navigate to [api.slack.com]()
    2. Click "Create an app"
    3. Click "From a manifest", select your workspace
    4. Export the YOUR_URL variable, and generate a manifest, and paste in the contents to manifest window.
       ```
       export YOUR_URL=myuniqueurl
       ```
       ```
       ./generate_app_manifest.sh 
        Generated app_manifest.yaml with URL: weshayutinfoo.ngrok-free.app
        Converting YAML to JSON using yq...
        Generated app_manifest.json
       ```
       ```
       cat app_manifest.yaml # or .json if the website manifest validation is finicky 
       ```
    5. After creating the app, you will need a couple of items: first, copy and save the Signing Secret from Basic Information. Second, copy and save the Bot User OAuth Token from OAuth & Permissions


4. **Create your `.env` file** with your Slack credentials:
  ```bash
  cp .env.example .env  # if available
   # Edit .env with your values
   ```
  Replace `SLACK_SIGNING_SECRET` and `SLACK_BOT_TOKEN` from your Slack setup above. There are several secrets you will need from Moneyball that you may need as well.

5. **Build your development environment:**
   ```bash
   # Start all services including the app container
   docker-compose --profile app up --build
   ```

  That's it! The F3-Data-Models repository is automatically cloned and set up during the Docker build process.
  
  ### What Happens

  1. **Database Service** (`db`): PostgreSQL 16 starts up
  2. **Database Initialization** (`db-init`): 
    - Built from `./db-init/Dockerfile`
    - Automatically clones the F3-Data-Models repository
    - Waits for database to be ready (5-second intervals)
    - Creates the database if it doesn't exist
    - Installs Poetry dependencies for migrations
    - Runs Alembic migrations to create all tables
    - Sets up the complete F3 database schema
  3. **App Service** (`app`): 
    - Starts the F3 Nation Slack Bot
    - Connects to the initialized database
    - Runs with hot-reloading for development

  ### Services

  - **App**: http://localhost:3000
  - **Database**: localhost:5432 (postgres/postgres)
  - **Adminer**: http://localhost:8080 (admin WEBUI for the db)

> [!NOTE]
> if you add or change packages via `poetry add ...`, you will need to also add it to `f3-nation-slack-bot/requirements.txt`. You can make sure that this file fully reflects the poetry virtual environment via: `poetry export -f requirements.txt -o requirements.txt --without-hashes`

## Codebase Structure and Design Notes

This codebase utilizes the slack-bolt python sdk throughout, and auto-deploys to the Google Cloud Run function. Here is a high-level walkthrough of the most important components:

- `main.py` - this is the sole entrypoint. When any event is received, it will attept to look up the appropriate feature function to call via `utilities/routing.py`. If the route has not been set up, it will do nothing
- `utilities/routing.py` - this is a mapping of action id to a particular feature function. These functions must all take the same arguments, and are not expected to return anything
- `utilities/slack/actions.py` - this is where I store the constant values of the various action ids used throughout. Eventually I'd like to move these to the feature modules
- `features/` - this is where the meat of the functionality lives. Functions are generally either "building" a Slack form / modal, and / or responding "handling" an action or submission of a form. The design pattern I've used is including the build function, the handle function, and the UI form layout for a particular menu / feature in a single file. In the future I'd like to make this more modular
- `utilities/slack/orm.py` - this is where I've defined most of the Slack API UI elements in python class form, that is then used throughout. The ORM defines "blocks", that can then be converted to Slack's required json format via the `.as_form_field()` method. I'd eventually like to use the ORM directly from the Slack SDK, as it has some validation features I like
- See `features/calendar/event_tag.py` for an example of the design pattern I'd like to refactor to (more modular, uses the Slack SDK ORM, etc.)
- **Data Access:** - right now, I use a SQLAlchemy wrapper I built in the `f3-data-models` repo, which has direct db access. However, we've aligned that we want all db interactions for F3 apps to go through a yet-to-be-built API.
