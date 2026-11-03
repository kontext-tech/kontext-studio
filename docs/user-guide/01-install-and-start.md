# Install and start Kontext

Kontext runs on your own machine. The local server, the data engine, and the web
app all start together, and everything you create stays in a workspace directory
on disk.

## Before you start

You need Python 3.12 or newer and [`uv`](https://docs.astral.sh/uv/). Install the
wheel from the project's
[releases page](https://github.com/kontext-labs/kontext-labs/releases), or use
the command below with a release tag.

## Install

```bash
uv tool install "kontext-labs @ https://github.com/kontext-labs/kontext-labs/releases/download/v<version>/kontext_labs-<version>-py3-none-any.whl"
```

Replace `<version>` with the version number, for example `0.261.0`.

## Start the server

Run the server from the directory that should hold your workspace:

```bash
kontext-labs serve
```

The first start creates a workspace in `.kontext/` and prints the URL to open.
Kontext seeds a placeholder profile called **Local Admin** and one project
called **Local Project**, so you can start working immediately.

## Replace the placeholder profile

The placeholder profile is enough to get started, but it is worth replacing
before you add data. The setup page is available at `/setup` on the same address
as the app, for example <http://localhost:8000/setup>.

<!-- docs:capture 01-install-and-start hash=2b1d05217f0f -->
1. Kontext starts with a placeholder profile. Open `/setup` before you add any data to replace it with your own name and email.
   ![Kontext starts with a placeholder profile. Open /setup before you add any data to replace it with your own name and email.](assets/01-install-and-start/setup-page.png)
2. Enter a first name, an optional last name, and an email address.
   ![Enter a first name, an optional last name, and an email address.](assets/01-install-and-start/profile.png)
3. Select **Create local profile**. Kontext stores the profile on this machine and signs you in.
   ![Select Create local profile. Kontext stores the profile on this machine and signs you in.](assets/01-install-and-start/finish.png)
4. Kontext opens your workspace with one project and the local profile you created.
   ![Kontext opens your workspace with one project and the local profile you created.](assets/01-install-and-start/landing.png)
<!-- /docs:capture -->
