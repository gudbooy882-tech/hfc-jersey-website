# HFC Jersy Details

A simple Flask + SQLite player registration site.

## Run locally in Termux

```bash
pkg update -y
pkg install python -y
cd ~/hfc_jersey_website
python -m pip install -r requirements.txt
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export ADMIN_PASSWORD='replace-with-a-strong-private-password'
python app.py
```

Open http://127.0.0.1:5000 in your phone browser.
Admin login: http://127.0.0.1:5000/admin

Keep the admin password private. The default password is intentionally not suitable for use.
For online deployment, set SECRET_KEY and ADMIN_PASSWORD as private environment variables and use persistent storage for players.db.
