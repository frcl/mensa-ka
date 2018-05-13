# pylint: disable=import-error
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
HELP_TEXT = """# men.sa
Commad line web application for mensa food

# Usage
Mensa am Adenauerring (default):

    $ curl {host}

Mensa Schloss Gottesaue:

    $ curl {host}/Gottesaue
    $ curl {host}/G

Linie 3 am Adenauerring:

    $ curl {host}/A/3

""".format(host='men.sa')
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
</pre>""".format(host='men.sa')
SHORTNAMES = {
    # 'CafeteMoltke': 'Caféteria Moltkestraße 30',
    'Adenauerring': 'Mensa Am Adenauerring',
    'Erzbergerstraße': 'Mensa Erzbergerstraße',
    'Holzgartenstraße': 'Mensa Holzgartenstraße',
    'Moltkestraße': 'Mensa Moltke',
    'Gottesaue': 'Mensa Schloss Gottesaue',
    'Tiefenbronnerstraße': 'Mensa Tiefenbronnerstraße'
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
                    'name'; 'meal 1',
                    'note': 'with extra stuff',
                    'price': '2.60 €',
                    # (soon:) 'tags': ['vegan', 'gluten', ...],
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
        for tr in line_trs:
            name = tr.find('td', {'class': 'mensatype'}).contents[0].text
            meals = []
            for td in tr.findAll('td', {'class': 'first'}):
                note = td.find('span', {'class': None})
                meals.append({
                    'name': td.find('b').text,
                    'note': note.text if note else '',
                    'price': tr.find('span', {'class': 'bgp price_1'}).text,
                    # 'tags': TODO
                })
            lines[name] = meals
        mensen[canteens[div.attrs['id'][-3]]] = lines
    return mensen


async def handle_meta_request(request):
    resp = web.json_response(META_DATA)
    return resp


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


async def handle_mensa_request(request):
    await LOCK.acquire()

    try:
        data = get_mensa(request.match_info['mensa'])
        resp = web.Response(text=format_mensa(data))
    except ValueError as exc:
        resp = web.Response(text=exc.args[0])

    LOCK.release()
    return resp


def format_mensa(data):
    names, food = zip(*data.items())
    return '\n\n'.join(map('{}:\n{}'.format, names, map(format_line, food)))


def format_line(data):
    return tabulate([meal.values() for meal in data], tablefmt='fancy_grid')


async def handle_line_request(request):
    await LOCK.acquire()

    try:
        data = get_line(request.match_info['mensa'],
                        request.match_info['linie'])
        resp = web.Response(text=format_line(data))
    except ValueError as exc:
        resp = web.Response(text=exc.args[0])

    LOCK.release()
    return resp


async def handle_default_request(request):
    await LOCK.acquire()
    resp = web.Response(text=format_mensa(DATA['Mensa Am Adenauerring']))
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
    app = web.Application()
    app.on_startup.append(start_background_tasks)
    app.add_routes([web.get('/help', usage),
                    web.get('/meta', handle_meta_request),
                    web.get('/', handle_default_request),
                    web.get('/{mensa}', handle_mensa_request),
                    web.get('/{mensa}/{linie}', handle_line_request)])
    web.run_app(app, port=80)
