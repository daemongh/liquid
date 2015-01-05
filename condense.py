import requests
import re
import math
import redis
import json
import arrow
from bs4 import BeautifulSoup


def get_page(page_number, refresh=False):
    r_server = redis.Redis("localhost")
    url = "http://store.steampowered.com/search/?category1=998&specials=1&page="
    #url = "http://store.steampowered.com/search/?sort_order=ASC&specials=1&page="

    page = r_server.get('page' + str(page_number))
    if not page or refresh:
        print 'Fetching from Steam'
        page = requests.get(url + str(page_number)).text
        r_server.set('page' + str(page_number), page)
    else:
        page = page.decode('utf8')

    return BeautifulSoup(page)


def find_page_count(page_soup):
    results = page_soup.find("div", attrs={"class": "search_pagination_left"})
    total_sales = re.search('showing 1 - 25 of (\d+)', results.string.strip(), re.IGNORECASE).group(1)
    page_count = int(math.ceil(float(total_sales) / 25))
    return page_count


def get_all_pages(refresh=False):
    current_page = 1
    pages = []
    pages.append(get_page(current_page, refresh))
    page_count = find_page_count(pages[0])
    while current_page < page_count:
        pages.append(get_page(current_page + 1, refresh))
        current_page += 1

    return pages


def process_pages(pages, refresh=False):
    sales = []

    page_number = 0
    for page in pages:
        page_number += 1
        rows = page.find_all("a", attrs={"class": "search_result_row"})
        row_number = 0
        for row in rows:

            row_number += 1
            try:
                sale = {}
                sale['name'] = row.find("h4").string
                sale['image'] = row.find("img", attrs={"width": "120"})["src"]
                sale['list_price'] = float(row.find('strike').string[1:])
                row.find('strike').clear()
                sale['sale_price'] = float(row.select('.search_price')[0].text[1:])
                date_text = row.select('.search_released')[0].text
                try:
                    date = arrow.get(date_text, 'MMM YYYY').format('YYYY-MM-DD')
                except:
                    try:
                        date = arrow.get(date_text, 'MMM D, YYYY').format('YYYY-MM-DD')
                    except:
                        try:
                            date = arrow.get(date_text, 'MMMM YYYY').format('YYYY-MM-DD')
                        except:
                            date = date_text
                sale['release_date'] = date
                sale['metascore'] = row.select('.search_metascore')[0].string
                sale['discount'] = (1 - (sale['sale_price'] / sale['list_price']))
                sale['platforms'] = {
                    'linux': len(row.select('.linux')) > 0,
                    'windows': len(row.select('.win')) > 0,
                    'mac': len(row.select('.mac')) > 0,
                    'steam': len(row.select('.steamplay')) > 0,
                }
                # http://store.akamai.steamstatic.com/public/images/ico/ico_type_app.gif
                is_app = row.find("img", attrs={"src": "http://store.akamai.steamstatic.com/public/images/ico/ico_type_app.gif"})
                if not is_app:
                    sale['type'] = "app"
                else:
                    sale['type'] = "dlc"

                sale['page'] = page_number
                sale['row'] = row_number
                sale['steam_order'] = page_number * 100 + row_number
                tags_text = row.find('p').text.strip()
                if tags_text.find(' -') != -1:
                    tags_text = tags_text[:tags_text.index(' -')]
                    sale['tags'] = tags_text.split(', ')
                else:
                    sale['tags'] = []

                result = re.search('http://store.steampowered.com/app/(\d+)/?.+', row['href'], re.IGNORECASE)
                if result:
                    sale['steam_id'] = result.group(1)
                else:
                    sale['steam_id'] = "0"

                sale['steam_link'] = 'http://store.steampowered.com/app/' + sale['steam_id']

                duplicate = False
                for existing_sale in sales:
                    if sale['steam_id'] == existing_sale['steam_id']:
                        duplicate = True

                if not duplicate:
                    sales.append(sale)
            except:
                pass

    return sales


def get_sales(refresh=False):
    r_server = redis.Redis("localhost")
    sales = r_server.get('sales')

    if not sales or refresh:
        pages = get_all_pages(refresh)
        sales = process_pages(pages, refresh)
        sales = json.dumps(sales)
        r_server.set('sales', sales)
    else:
        sales = sales.decode('utf8')

    return sales
