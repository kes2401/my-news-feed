import os
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from datetime import datetime

def get_processed_urls():
    if not os.path.exists('processed_urls.txt'):
        return set()
    with open('processed_urls.txt', 'r') as f:
        return set(line.strip() for line in f)

def add_processed_url(url):
    with open('processed_urls.txt', 'a') as f:
        f.write(f"{url}\n")

def get_article_content(url):
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = soup.find_all('p')
        return ' '.join([p.get_text() for p in paragraphs])
    except Exception as e:
        print(f"Error fetching article {url}: {e}")
        return None

def get_gemini_response(prompt):
    genai.configure(api_key=os.environ['GEMINI_API_KEY'])
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    return response.text.strip()

def main():
    with open('sites.txt', 'r') as f:
        sites = [line.strip() for line in f]

    processed_urls = get_processed_urls()
    all_articles = []

    for site in sites:
        try:
            response = requests.get(site, headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(response.content, 'html.parser')
            links = soup.find_all('a')

            for link in links:
                href = link.get('href')
                if href and href.startswith('http') and href not in processed_urls:
                    article_content = get_article_content(href)
                    if article_content:
                        category_prompt = f"Analyze the following article and classify it into one of these categories: News, Sport, Culture, Technology, Business, Lifestyle, Opinion. Respond with only the single category name.\n\n{article_content[:2000]}"
                        category = get_gemini_response(category_prompt)

                        summary_prompt = f"Summarize the following article in no more than 200 words.\n\n{article_content}"
                        summary = get_gemini_response(summary_prompt)

                        all_articles.append({
                            'url': href,
                            'title': link.get_text(strip=True),
                            'summary': summary,
                            'category': category,
                            'site': site
                        })
                        add_processed_url(href)
        except Exception as e:
            print(f"Error fetching site {site}: {e}")

    # Generate HTML
    with open('index.html', 'w') as f:
        f.write('<!DOCTYPE html>\n')
        f.write('<html>\n<head>\n<title>My News Feed</title>\n<link rel="stylesheet" href="style.css">\n</head>\n<body>\n')
        f.write(f'<h1>Today\'s News</h1>\n<p><em>Last updated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}</em></p>\n<hr>\n')

        # Create tabs
        f.write('<div class="tab">\n')
        for i, site in enumerate(sites):
            f.write(f'<button class="tablinks" onclick="openSite(event, \'{i}\')">{site}</button>\n')
        f.write('</div>\n')

        for i, site in enumerate(sites):
            f.write(f'<div id="{i}" class="tabcontent">\n')
            site_articles = [article for article in all_articles if article['site'] == site]
            categories = sorted(list(set([article['category'] for article in site_articles])))

            for category in categories:
                f.write(f'<h2>{category}</h2>\n')
                for article in site_articles:
                    if article['category'] == category:
                        f.write('<div class="article">\n')
                        f.write(f'<h3>{article["title"]}</h3>\n')
                        f.write(f'<p>{article["summary"]}</p>\n')
                        f.write(f'<a href="{article["url"]}" target="_blank">Read full article</a>\n')
                        f.write('</div>\n')
            f.write('</div>\n')

        f.write('<script src="script.js"></script>\n')
        f.write('</body>\n</html>')

if __name__ == '__main__':
    main()