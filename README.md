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

The F3 Nation Slack Bot is in active development, and we welcome any and all help or contributions! Feel free to leave an [Issue](https://github.com/F3-Nation/f3-nation-slack-bot/issues) with bugs or feature requests, or even better leave us a [Pull Request](https://github.com/F3-Nation/f3-nation-slack-bot/pulls).

We've put together a dockerized local development setup that makes it very easy to get going. It utilizes VS Code's Dev Container feature to make it even more seamless.

### Prerequisites

1. Docker installed on your system. If on Windows, this would include Docker Desktop through WSL
2. VS Code with the [Dev Container extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

### Local Setup

1. **Clone the repo**:
  ```bash
  git clone https://github.com/F3-Nation/f3-nation-slack-bot.git
  ```
2. **Initialize and install your local Slack app**: I recommend you use your own private Slack workspace for this. Open [Slack's app console](https://api.slack.com/apps), click Create New App->from manifest, then paste in the contents from `app_manifest.template.json`. After you install to your workspace, gather the Signing Secret from the Basic Information tab and the Bot User OAuth Token from the OAuth & Permissions tab.

2. **Create your `.env` file**:
  ```bash
  cp .env.example .env
   ```
  Replace `SLACK_SIGNING_SECRET` and `SLACK_BOT_TOKEN` from your Slack setup above. You can change some of the other variables if you like, but you don't need to. There are some client secrets you might need from Moneyball if you plan to test certain features.

3. **Create and open the Dev Container**: use the VS Code command `Dev Containers: Open folder in Container...` to build the container and open the project in it. This will take a bit of time the first time it is built.

4. **Start the app**:
  ```bash
  ./app_startup.sh # you may have to run chmod +x app_startup.sh the first time
  ```
  
  This will run a localtunnel to route traffic to your local app. The script will then pick up the dynamic url, and use that to generate `app_manifest.json`. Finally, it will start your app with reload.

5. **Update your app manifest**: in your [Slack app settings on the web console](https://api.slack.com/apps), go to your app, click on App Manifest, and replace what's there with the contents of `app_manifest.json`, and click Save. This will update it to know what url to use for interaction. To make sure your app is indeed able to process requests, you can click the Verify link.


You should be off to the races! Try opening `/f3-nation-settings` to start building a dummy region. Changes you make to python files will trigger a reload of the app. Use Ctrl-C in your terminal to kill the app and localtunnel. Repeat steps 4 and 5 whenever you reopen the project, as the localtunnel url will be different each time.
  
  ### What Happens on Container Build

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
  - **Database**: localhost:5433 (postgres/postgres)
  - **Adminer**: http://localhost:8080 (a lightweight admin WEBUI for the db, though I'm partial to the [Database Client extension in VS Code](https://marketplace.visualstudio.com/items?itemName=cweijan.vscode-database-client2))

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
- **Data Access:** - right now, I use a SQLAlchemy wrapper I built in the `f3-data-models` repo, which has direct db access. However, we've aligned that in the futures we want all db interactions for F3 apps to go through a yet-to-be-built API.
