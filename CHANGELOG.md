# CHANGELOG

<!-- version list -->

## v1.6.0 (2026-04-23)

### Documentation

- Added new snarky responses for HC and un-HC events; enhance welcome message templates
  ([#197](https://github.com/F3-Nation/f3-nation-slack-bot/pull/197),
  [`11a2172`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/11a2172659f047a3f07bda5b6940e0a3fcbb6507))

### Features

- Added option to only announce HCs or unHCs in preblast and preventing thread spamming
  ([`bd4e272`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/bd4e2722e4a51194a963abb228c0e943df41de32))


## v1.5.2 (2026-04-22)

### Bug Fixes

- Logic on when to run the home region nudge script
  ([`3c90e8e`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/3c90e8e1c8d4882639b070ef9f1a38c1ffaca773))


## v1.5.1 (2026-04-22)

### Bug Fixes

- Fixed divide by zero error on home region nudge script
  ([`ea10c90`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/ea10c90869cfc7640cc8dcdbc40a2845b1d8f47c))


## v1.5.0 (2026-04-21)

### Features

- Added script for nudging users about their home region when it looks like they joined a new one
  ([`cb2f798`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/cb2f798defc1017f4c90ab28568d67a84f855ecd))


## v1.4.2 (2026-04-21)

### Bug Fixes

- Fixed downrange region selector not working for non-admin
  ([`8d53263`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/8d53263423686e4765b5c2e95d43db531672aae9))


## v1.4.1 (2026-04-20)

### Bug Fixes

- Added direct email method and surfacing region contact info on downrange search
  ([`b411e93`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/b411e93e597c6787162e57ce041c5312f2113bbe))

- Fixed user mention and other formatting for downrange posts
  ([`e9dc680`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/e9dc68080bab2b54f70d6064d11c83d923a99ea9))


## v1.4.0 (2026-04-20)

### Bug Fixes

- Fixed query which was preventing preblast reminders from generating
  ([`0ed3404`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/0ed3404286ddf5f974b59d12ad5ce9bf8d4d52e6))

### Features

- Added a downrange feature for automated DR posts and requesting Slack space invites
  ([`a71008d`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/a71008d125ee9af8767e2ff2b15540d98360e16d))


## v1.3.0 (2026-04-18)

### Features

- Feat: added HC / unHC thread callout functionality
  ([`3b36a60`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/3b36a60a38b309773845cf5d98a875d90b5c13e0))


## v1.2.0 (2026-04-18)

### Features

- Added optional location to unscheduled backblast form
  ([`18bd74f`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/18bd74f8702523dbddcc2c17f48ee64bf2b7ab62))


## v1.1.1 (2026-04-15)

### Bug Fixes

- More cleanup
  ([`61e8bbe`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/61e8bbef6c31ac4b102a5b1a4da52977321f35f4))

- Removed leftover PaxMiner migration bits
  ([#192](https://github.com/F3-Nation/f3-nation-slack-bot/pull/192),
  [`f1d283a`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/f1d283a53d065f6f710f26637c33f63478590d31))

### Refactoring

- Removed all legacy paxminer functionality
  ([`61e8bbe`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/61e8bbef6c31ac4b102a5b1a4da52977321f35f4))


## v1.1.0 (2026-04-11)

### Bug Fixes

- Improved user search to sort by relevance and optionally include home region
  ([`adba213`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/adba2139c3a7cb818e863631685d88d7fd1431f7))

### Features

- Added new fields to user form: who brought you, f3 name origin story, and my f3why
  ([`b809f50`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/b809f50d50e0ec42c0fff2e95a8a2caf468c8abb))


## v1.0.3 (2026-04-10)

### Bug Fixes

- Fixed calendar list showing all regions' locations when group by location used
  ([#189](https://github.com/F3-Nation/f3-nation-slack-bot/pull/189),
  [`f8b69dc`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/f8b69dcc26520e93f5c863a5fa11198640cf418a))


## v1.0.2 (2026-04-08)

### Bug Fixes

- Added a better backblast error message for channel not found
  ([`fbc789f`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/fbc789faf298bbe62170e277a420b2b40827a27c))

- Addressed common IntegrityErrors from backblasts and HC calendar events
  ([`210e180`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/210e1806b9e3fc1489730f17d0d2d66cf20945fd))

- Fixed preblast send default behavior to 'send now' for day before event
  ([`12ccbb6`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/12ccbb657a70efa4c61ae4958dc90ca8eb318f35))

- Preventing re-deployment on staging when automerging back to main
  ([`f852377`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/f85237785a3214059fed6f234ff82a9264a6e7dc))


## v1.0.1 (2026-04-08)

### Bug Fixes

- Added CHANGELOG.md and version automation
  ([#188](https://github.com/F3-Nation/f3-nation-slack-bot/pull/188),
  [`7fa0b75`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/7fa0b756e23de1ba1371fb8e673aac8d31b4ba17))

- Removed poetry build step from release automation
  ([`fdddfcb`](https://github.com/F3-Nation/f3-nation-slack-bot/commit/fdddfcb94108a1789860379f7e6da00823e4d536))


## v1.0.0 (2026-04-08)

- Initial Release
