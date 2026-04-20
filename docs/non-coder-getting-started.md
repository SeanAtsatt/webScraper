# Using webscraper with Claude Desktop — a one-page guide

Once someone has set up the webscraper MCP server on your computer, you can ask Claude Desktop to grab data from the web for you.

## Things you can ask

- *"Get the contacts from https://example.com/team"* — pulls names and emails
- *"Save this article to my notes: https://example.com/blog/post"* — gives you clean markdown
- *"Crawl https://docs.example.com/ and find everything about authentication"* — explores the site and reports back
- *"Download the images from https://example.com/gallery"* — puts image files on your computer
- *"I need to log in to https://example.com first"* — opens a browser for you to sign in; Claude remembers for next time

## Tips

- Always include the full URL (with `https://`).
- If a page needs login, Claude will ask — it'll open a browser for you.
- If you want the original data file (for spreadsheets, etc.), Claude will tell you the folder path.
- If something seems stuck, ask Claude to "check the environment" — it'll tell you what's wrong.

## Things Claude won't do

- Scrape sites that actively block automated access (this is by design).
- Ignore the `robots.txt` file a site asks scrapers to follow.
- Download huge files without confirming with you first.

## Where files land

- Single pages: `~/.webscraper/out/<site>/<timestamp>-<page>.json`
- Crawls: `~/.webscraper/out/<site>/<timestamp>/manifest.json` plus one file per page
- Images: `~/.webscraper/out/<site>/images/`

Ask Claude to open the folder if you want to look inside.
