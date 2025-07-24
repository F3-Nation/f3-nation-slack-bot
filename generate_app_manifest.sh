#!/bin/bash

# Set your URL variable here - can be overridden by environment variable
YOUR_URL="${YOUR_URL:-your-ngrok-url-here}"

# Generate the app manifest YAML file
cat > app_manifest.yaml << EOF
display_information:
  name: f3-nation-dev
  description: An invokable form to produce properly-formatted backblasts and preblasts
  background_color: "#000000"
features:
  bot_user:
    display_name: f3-Nation-Dev
    always_online: true
  slash_commands:
    - command: /preblast
      url: https://${YOUR_URL}.ngrok-free.app/slack/events # You'll be editing this
      description: Launch preblast template
      should_escape: false
    - command: /f3-nation-settings
      url: https://${YOUR_URL}.ngrok-free.app/slack/events # You'll be editing this
      description: Managers your region's settings for F3 Nation, including your schedule
      should_escape: false
    - command: /backblast
      url: https://${YOUR_URL}.ngrok-free.app/slack/events # You'll be editing this
      description: Launch backblast template
      should_escape: false
    - command: /tag-achievement
      url: https://${YOUR_URL}.ngrok-free.app/slack/events # You'll be editing this
      description: Lauches a form for manually tagging Weaselbot achievements
      should_escape: false
    - command: /send-announcement
      url: https://${YOUR_URL}.ngrok-free.app/slack/events # You'll be editing this
      description: Triggers a announcement send
      should_escape: false
    - command: /calendar
      url: https://${YOUR_URL}.ngrok-free.app/slack/events
      description: Opens the event calendar
      should_escape: false
oauth_config:
  redirect_urls:
    - https://${YOUR_URL}.ngrok-free.app/slack/install # You'll be editing this
  scopes:
    user:
      - files:write
    bot:
      - app_mentions:read
      - channels:history
      - channels:join
      - channels:read
      - chat:write
      - chat:write.customize
      - chat:write.public
      - commands
      - files:read
      - files:write
      - im:history
      - im:read
      - im:write
      - incoming-webhook
      - reactions:read
      - reactions:write
      - team:read
      - users.profile:read
      - users:read
      - users:read.email
      - canvases:write
      - canvases:read
settings:
  event_subscriptions:
    request_url: https://${YOUR_URL}.ngrok-free.app/slack/events # You'll be editing this
    bot_events:
      - team_join
  interactivity:
    is_enabled: true
    request_url: https://${YOUR_URL}.ngrok-free.app/slack/events # You'll be editing this
  org_deploy_enabled: false
  socket_mode_enabled: false
  token_rotation_enabled: false
EOF

echo "Generated app_manifest.yaml with URL: ${YOUR_URL}.ngrok-free.app"

# this may be overkill
# Convert YAML to JSON using yq
if command -v yq &> /dev/null; then
    echo "Converting YAML to JSON using yq..."
    yq eval -o=json '.' app_manifest.yaml > app_manifest.json
    echo "Generated app_manifest.json"
else
    echo "Warning: yq not found. Could not convert to JSON."
    echo "Please install yq to enable JSON conversion."
fi 
