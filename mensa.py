# pylint: disable=import-error
import argparse
import re
import datetime
import asyncio

import aiohttp
from aiohttp import web
from dateutil import rrule
from tabulate import tabulate
import bs4


MENSA_HTML_URL = 'http://www.sw-ka.de/de/essen/'
DATA = {}
LOCK = asyncio.Lock()
META_DATA = {'last_update': None}
HOST = 'mensa-ka.herokuapp.com'
HELP_TEXT = """\033[93m# men.sa\033[0m
Commad line web application for mensa food

\033[93m# Usage\033[0m
Mensa am Adenauerring (default):

    \033[95m$ curl {host}\033[0m

Mensa Schloss Gottesaue:

    \033[95m$ curl {host}/Gottesaue\033[0m
    \033[95m$ curl {host}/G\033[0m

Linie 3 am Adenauerring:

    \033[95m$ curl {host}/A/3\033[0m

JSON output:

    \033[95m$ curl {host}?format=json\033[0m

""".format(host=HOST)
HELP_HTML = """<pre>
    <h1># {host}</h1>
    Commad line web application for mensa food
    <h1># Usage</h1>
    Mensa am Adenauerring (default):
    <code>
    $ curl {host}
    </code>
    Mensa Schloss Gottesaue:
    <code>
    $ curl {host}/Gottesaue
    $ curl {host}/G
    </code>
    Linie 3 am Adenauerring:
    <code>
    $ curl {host}/A/3
    </code>
    JSON output:
    <code>
    $ curl {host}?format=json
    </code>
</pre>""".format(host=HOST)
RESP_TEMPL = """{header}
{content}
For usage info see \033[93mhttp://{domain}/help\033[0m
Found a bug? Open an issue at \033[93mhttps://github.com/frcl/mensa-ka\033[0m
"""
SHORTNAMES = {
    # 'CafeteMoltke': 'Caféteria Moltkestraße 30',
    'Adenauerring': 'Mensa Am Adenauerring',
    'Erzbergerstraße': 'Mensa Erzbergerstraße',
    'Holzgartenstraße': 'Mensa Holzgartenstraße',
    'Moltkestraße': 'Mensa Moltke',
    'Gottesaue': 'Mensa Schloss Gottesaue',
    'Tiefenbronnerstraße': 'Mensa Tiefenbronnerstraße'
}
ICON_TAGS = {
    'vegetarian_2.gif': 'veggi',
    'vegan_2.gif': 'vegan',
    's_2.gif': 'schwein',
    'r_2.gif': 'rind',
    'm_2.gif': 'fisch',
    'bio_2.gif': 'bio',
}


async def update(now):
    async with aiohttp.ClientSession() as session:
        async with session.get(MENSA_HTML_URL) as resp:
            if resp.status < 300:
                strange_bytes = await resp.read()
                # the site is utf8 encoded, except for 2 characters
                # so we cut out the whole div tag containing them
                valid_bytes = strange_bytes[:4930] + strange_bytes[5350:]
                html = valid_bytes.decode('utf8')
            else:
                return # TODO: handle

    data = parse_sw_site(html)

    await LOCK.acquire()
    DATA.update(data)
    META_DATA['last_update'] = now.isoformat()
    LOCK.release()


async def check_for_updates(app):
    await update(datetime.datetime.now())
    for next_dt in rrule.rrule(rrule.DAILY, byhour=1):
        await asyncio.sleep((next_dt-datetime.datetime.now()).seconds)
        await update(next_dt)


def parse_sw_site(html):
    """
    input: html string
    output: dict of form
        {'mensa 1': {
            'line 1': [
                {
                    'name': 'meal 1',
                    'note': 'with extra stuff',
                    'price': '2.60 €',
                    'tags': ['vegan', 'bio', ...],
                }
                ...],
            ...},
        ...}
    """
    soup = bs4.BeautifulSoup(html, 'html.parser')
    canteen_divs = soup.findAll('div', {'id': re.compile(r'canteen_place_\d')})
    canteens = {div.attrs['id'][-1]:div.findAll('h1')[0].text
                for div in canteen_divs}
    menu_divs = soup.findAll('div', {'id': re.compile(r'fragment-c\d-1')})

    mensen = {}
    for div in menu_divs:
        line_trs = div.findAll('tr', {'class': None})
        lines = {}
        for ltr in line_trs:
            nametd = ltr.find('td', {'class': 'mensatype'})
            if nametd:
                name = nametd.contents[0].text
                meals = []
                for mtr in ltr.findAll('tr', {'class': re.compile(r'mt-\d')}):
                    td = mtr.find('td', {'class': 'first'})
                    note = td.find('span', {'class': None})
                    tagnames = [ICON_TAGS.get(img['src'].split('/')[-1]) for img in
                                mtr.findAll('img', {'class': 'mealicon_2'})]
                    meals.append({
                        'name': mtr.find('b').text,
                        'note': note.text if note else '',
                        'price': mtr.find('span', {'class': 'bgp price_1'}).text,
                        'tags': [tag for tag in tagnames if tag]
                    })
                lines[name] = meals
        mensen[canteens[div.attrs['id'][-3]]] = lines
    return mensen


async def handle_meta_request(request):
    return web.json_response(META_DATA)


def get_mensa(query):
    matches = [name for short, name in SHORTNAMES.items()
               if short.startswith(query)]

    if not matches:
        raise ValueError('Unkown Mensa')
    elif len(matches) == 1:
        return DATA[matches[0]]
    else:
        raise ValueError('Ambiguous short name')


def get_line(mquery, lquery):
    mdata = get_mensa(mquery)
    matches = [line for line in mdata
               if line.endswith(lquery)] #TODO: generalize

    if not matches:
        raise ValueError('Unkown Line')
    elif len(matches) == 1:
        return mdata[matches[0]]
    else:
        raise ValueError('Ambiguous short name')


def format_mensa(data):
    names, food = zip(*data.items())
    return '\n'.join(map('{}:\n{}'.format, names, map(format_line, food)))


def format_line(data):
    return tabulate([format_meal(meal) for meal in data],
                    tablefmt='fancy_grid') + '\n'


def format_meal(data):
    desc = data['name']+(' ({})'.format(data['note']) if data['note'] else '')
    return [desc, ','.join(data['tags']), data['price']]


def get_resp_text(content, header=None):
    return RESP_TEMPL.format(content=content,
                             header=header if header else '',
                             domain=HOST)

async def req2resp(request, data_getter, args, formatter):
    await LOCK.acquire()

    try:
        data = data_getter(*args)
    except ValueError as exc:
        resp = web.Response(text=get_resp_text('\033[31mERROR: {}\033[0m\n---'
                                               .format(exc.args[0])),
                            content_type='text/plain')
    else:
        resp = data2resp(data, request, formatter)
    finally:
        LOCK.release()

    return resp


def data2resp(data, request, formatter):
    if 'format' in request.query and 'json' in request.query['format']:
        resp = web.json_response(data)
    else:
        resp = web.Response(text=get_resp_text(formatter(data)),
                            content_type='text/plain')
    return resp


async def handle_mensa_request(request):
    args = [request.match_info['mensa']]
    return await req2resp(request, get_mensa, args, format_mensa)


async def handle_line_request(request):
    args = [request.match_info['mensa'], request.match_info['linie']]
    return await req2resp(request, get_line, args, format_line)


async def handle_default_request(request):
    await LOCK.acquire()
    resp = data2resp(DATA['Mensa Am Adenauerring'], request, format_mensa)
    LOCK.release()
    return resp


async def start_background_tasks(app):
    app['update_checker'] = app.loop.create_task(check_for_updates(app))


async def usage(request):
    if any(browser in request.headers['user-agent']
           for browser in ('Chrome', 'Safari', 'Mozilla')):
        return web.Response(text=HELP_HTML, content_type='text/html')
    else:
        return web.Response(text=HELP_TEXT, content_type='text/plain')


if __name__ == '__main__':
    argp = argparse.ArgumentParser()
    argp.add_argument('-p', '--port', default=80)
    args = argp.parse_args()
    app = web.Application()
    app.on_startup.append(start_background_tasks)
    app.add_routes([web.get('/help', usage),
                    web.get('/meta', handle_meta_request),
                    web.get('/', handle_default_request),
                    web.get('/{mensa}', handle_mensa_request),
                    web.get('/{mensa}/{linie}', handle_line_request)])
    web.run_app(app, port=args.port)
