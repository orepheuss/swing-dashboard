# Publishing the dashboard with a shareable link

You need two free accounts: **GitHub** (stores the code) and **Streamlit Community
Cloud** (runs the website and gives you the link). No credit card is needed for either
as far as the free plans go, but read each signup page before entering payment details.

## Part 1: Put the code on GitHub

1. Go to github.com and sign up. Confirm your email.
2. Click the **+** at the top right, then **New repository**.
3. Repository name: `swing-dashboard`. Choose **Public** (see the note below), then
   click **Create repository**.
4. On the new page, click **uploading an existing file**.
5. Unzip the downloaded repository folder on your computer. Select **all the files inside it**
   (not the folder itself, and not the ZIP) and drag them into the GitHub page.
   Make sure `.gitignore` is included. If your file explorer hides files that start with a dot,
   turn on "Show hidden items".
6. Scroll down and click **Commit changes**.
7. Check the file list on your repository page. `swing_live.py` and `requirements.txt` must
   be visible at the top level, and **`keys.txt` must not be there**.

Public or private? A public repository makes the code readable by anyone and the app public.
A private repository makes the app private by default. Streamlit allows only one private app
at a time, and you can make it public later in the app settings. The code holds no secrets
as long as you never upload `keys.txt`.

## Part 2: Deploy on Streamlit Community Cloud

1. Go to **share.streamlit.io** and choose **Continue with GitHub**. Approve the access it asks for.
2. Click **Create app** (or **New app**), then choose to deploy from an existing repository.
3. Fill in:
   - Repository: `your-username/swing-dashboard`
   - Branch: `main`
   - Main file path: `swing_live.py`
   - App URL: pick a name, for example `swing-dashboard-yourname`
4. Open **Advanced settings** and choose Python 3.12 or 3.13.
5. Click **Deploy**. The first build takes a few minutes while it installs the libraries.
6. When it finishes you get a link like `https://swing-dashboard-yourname.streamlit.app`.

## Part 3: Share the link

- **Public app:** anyone with the link can open it. Copy the address from your browser.
- **Private app:** click **Share** at the top right of the app, choose "Only specific people can
  view this app", and enter the email addresses of the people you want to invite.
- You can switch between public and private from the **Share** button.

## Part 4: Updating the app later

Streamlit redeploys automatically whenever the files in your GitHub repository change.

1. Open the file on GitHub, or click **Add file, Upload files** to upload a new copy with the
   same name (it replaces the old one).
2. Click **Commit changes**.
3. Wait a minute or two and refresh the app.

If you change `requirements.txt`, Streamlit reinstalls the libraries automatically, which takes longer.

## Good to know

- **Sleeping:** apps with no visitors for 12 hours go to sleep. The next visitor clicks a button
  to wake it, which takes a few seconds.
- **Yahoo may block shared servers.** Yahoo Finance is unofficial and sometimes rate-limits cloud
  servers. If the app shows "Could not fetch data", wait a minute and refresh. The app caches
  each ticker for 60 seconds to keep requests low. If it keeps failing, run the app on your own
  computer instead (see the README).
- **Resource limits:** the free platform has limited CPU and memory. The dashboard is light, but
  the backtest scripts (`swing_backtest.py`, `rs_ranker.py --backtest`) are meant to run on your
  own computer, not on the website.
- **Logs:** if the app fails to start, click **Manage app** in the bottom-right corner to read the
  logs. Pasting the last few lines to Claude is the fastest way to get help.
- **Keys:** if you later add API keys, store them in the Streamlit app's **Secrets** settings,
  never in a file in the repository.
