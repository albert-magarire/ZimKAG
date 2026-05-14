# Gmail OAuth credentials

The watcher needs a **`client_secret.json`** file dropped into this folder. It identifies your Google Cloud project to Gmail. Setup takes about five minutes and is a one-time job.

## 1 · Create / select a Google Cloud project

1. Go to <https://console.cloud.google.com/projectcreate>
2. Project name: `ZimKAG Email Watcher` (or anything you like) → **Create**
3. Wait ~30 s, then make sure the project is selected in the top bar.

## 2 · Enable the Gmail API

1. Open <https://console.cloud.google.com/apis/library/gmail.googleapis.com>
2. Click **Enable**.

## 3 · Configure the OAuth consent screen

1. Go to <https://console.cloud.google.com/apis/credentials/consent>
2. **User type:** External → **Create**
3. Fill in:
   - **App name:** `ZimKAG Email Watcher`
   - **User support email:** _your gmail_
   - **Developer contact:** _your gmail_
4. **Save and Continue** through every screen (no need to add scopes here — the app requests them at runtime).
5. **Test users:** add your own gmail address. Click **Save and Continue**.
6. **Back to dashboard**.

> Because the consent screen stays in *Testing* mode, only the test users you added can authorise the app — but you don't need to publish it for personal use.

## 4 · Create OAuth client credentials

1. Go to <https://console.cloud.google.com/apis/credentials>
2. **Create Credentials → OAuth client ID**
3. **Application type:** *Desktop app*
4. **Name:** `ZimKAG Email Watcher Desktop`
5. Click **Create** → click **DOWNLOAD JSON** in the dialog.

## 5 · Drop the file here

Rename the downloaded file to **`client_secret.json`** and place it in this folder:

```
zimkag_email_watcher/credentials/client_secret.json
```

The watcher's first run will open a browser tab, ask you to consent, and save a **`token.json`** here too. Both files are gitignored, so they won't be pushed to GitHub.

## Re-authorise / revoke

- **Wipe local auth:** delete `token.json` — next run will prompt again.
- **Revoke server-side:** <https://myaccount.google.com/permissions> → find *ZimKAG Email Watcher* → Remove access.
