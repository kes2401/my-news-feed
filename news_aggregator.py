import os
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from datetime import datetime
import re

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
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        response.raise_for_status() # Raise an exception for HTTP errors
        soup = BeautifulSoup(response.content, 'html.parser')

        # Try to find common article content containers
        content_div = soup.find('div', class_=re.compile(r'article|content|body|post', re.I))
        if content_div:
            paragraphs = content_div.find_all('p')
        else:
            paragraphs = soup.find_all('p') # Fallback to all paragraphs

        return ' '.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
    except requests.exceptions.RequestException as e:
        print(f"Network error fetching article {url}: {e}")
        return None
    except Exception as e:
        print(f"Error parsing article {url}: {e}")
        return None

def get_gemini_response(prompt):
    try:
        genai.configure(api_key=os.environ['GEMINI_API_KEY'])
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini API error: {e}")
        return "Error generating content."

def main():
    with open('sites.txt', 'r') as f:
        sites = [line.strip() for line in f]

    processed_urls = get_processed_urls()
    all_articles = []
    site_processing_status = {} # To store if a site was processed successfully

    for site in sites:
        site_articles_found = False
        try:
            response = requests.get(site, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # More targeted link finding (heuristic)
            # Look for links that might be articles, avoiding common navigation/social links
            links = soup.find_all('a', href=True)
            article_links = []
            for link in links:
                href = link['href']
                # Basic filtering for common article URL patterns
                if (href.startswith('http') and
                    not any(ext in href for ext in ['.pdf', '.jpg', '.png', '.gif']) and
                    not any(nav_word in href for nav_word in ['/tag/', '/category/', '/author/', '#', '?']) and
                    re.search(r'/\d{4}/\d{2}/\d{2}/|/news/|/article/|/sport/', href)): # Look for date patterns or common article paths
                    article_links.append(link)

            for link in article_links:
                href = link.get('href')
                if href and href not in processed_urls:
                    article_title = link.get_text(strip=True)
                    if not article_title: # Skip links with no visible text
                        continue

                    article_content = get_article_content(href)
                    if article_content and len(article_content) > 100: # Ensure content is substantial
                        category_prompt = f"Analyze the following article and classify it into one of these categories: News, Sport, Culture, Technology, Business, Lifestyle, Opinion, Other. Respond with only the single category name.\n\n{article_content[:2000]}"
                        category = get_gemini_response(category_prompt)

                        summary_prompt = f"Summarize the following article in no more than 200 words. The article title is: '{article_title}'.\n\n{article_content}"
                        summary = get_gemini_response(summary_prompt)

                        all_articles.append({
                            'url': href,
                            'title': article_title,
                            'summary': summary,
                            'category': category,
                            'site': site
                        })
                        add_processed_url(href)
                        site_articles_found = True
            site_processing_status[site] = "success" if site_articles_found else "no_articles"
        except requests.exceptions.RequestException as e:
            print(f"Network error fetching site {site}: {e}")
            site_processing_status[site] = f"network_error: {e}"
        except Exception as e:
            print(f"Error processing site {site}: {e}")
            site_processing_status[site] = f"processing_error: {e}"

    # Generate HTML
    with open('index.html', 'w') as f:
        f.write('<!DOCTYPE html>\n')
        f.write('<html>\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>My News Feed</title>\n<link rel="stylesheet" href="style.css">\n</head>\n<body>\n')
        f.write(f'<h1>Today\'s News</h1>\n<p><em>Last updated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}</em></p>\n<hr>\n')

        # Create tabs
        f.write('<div class="tab">\n')
        for i, site in enumerate(sites):
            display_site_name = site.replace('https://www.', '').replace('https://', '').replace('/', '')
            f.write(f'<button class="tablinks" onclick="openSite(event, \'site-{i}\')">{display_site_name}</button>\n')
        f.write('</div>\n')

        for i, site in enumerate(sites):
            display_site_name = site.replace('https://www.', '').replace('https://', '').replace('/', '')
            f.write(f'<div id="site-{i}" class="tabcontent">\n')
            
            status = site_processing_status.get(site, "unknown_error")
            if status.startswith("network_error") or status.startswith("processing_error"):
                f.write(f'<p>Error processing articles from {display_site_name}: {status}</p>\n')
            elif status == "no_articles":
                f.write(f'<p>No new articles found for {display_site_name} in this run.</p>\n')
            else:
                site_articles = [article for article in all_articles if article['site'] == site]
                if site_articles:
                    # Group articles by category
                    articles_by_category = {}
                    for article in site_articles:
                        articles_by_category.setdefault(article['category'], []).append(article)
                    
                    # Sort categories for consistent display
                    sorted_categories = sorted(articles_by_category.keys())

                    for category in sorted_categories:
                        f.write(f'<h2>{category}</h2>\n')
                        for article in articles_by_category[category]:
                            f.write('<div class="article">\n')
                            f.write(f'<h3>{article["title"]}</h3>\n')
                            f.write(f'<p>{article["summary"]}</p>\n')
                            f.write(f'<a href="{article["url"]}" target="_blank">Read full article on {display_site_name}</a>\n')
                            f.write('</div>\n')
                else:
                    f.write(f'<p>No articles processed for {display_site_name} in this run.</p>\n') # Fallback if status is success but no articles

            f.write('</div>\n')

        f.write('<script>\n')
        f.write('function openSite(evt, siteName) {\n')
        f.write('    var i, tabcontent, tablinks;\n')
        f.write('    tabcontent = document.getElementsByClassName("tabcontent");\n')
        f.write('    for (i = 0; i < tabcontent.length; i++) {\n')
        f.write('        tabcontent[i].style.display = "none";\n')
        f.write('    }\n')
        f.write('    tablinks = document.getElementsByClassName("tablinks");\n')
        f.write('    for (i = 0; i < tablinks.length; i++) {\n')
        f.write('        tablinks[i].className = tablinks[i].className.replace(" active", "");\n')
        f.write('    }\n')
        f.write('    document.getElementById(siteName).style.display = "block";\n')
        f.write('    evt.currentTarget.className += " active";\n')
        f.write('}\n\n')
        f.write('// Get the element with id="defaultOpen" and click on it\n')
        f.write('document.getElementsByClassName(\'tablinks\')[0].click();\n')
        f.write('</script>\n')
        f.write('</body>\n</html>')

if __name__ == '__main__':
    main()