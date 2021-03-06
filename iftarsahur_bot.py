import json
import re
import threading
from datetime import datetime, timedelta
from os import environ
from typing import Dict, List

import aiohttp
import pytz
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram import filters as f
from pyrogram import types
from unidecode import unidecode

load_dotenv('config.env')

BOT_TOKEN: str = environ.get('BOT_TOKEN', None)
API_ID: int = int(environ.get('API_ID', None))
API_HASH: str = environ.get('API_HASH', None)
BOT_USERNAME: str = environ.get('BOT_USERNAME', None)
SUDO: list = list(map(int, environ.get('SUDO', '0').split(' ')))

PREFIX: list = ["/", "!", ".", "-", ">"]
CACHE_LOCK = threading.Lock()
CHATS_LOCK = threading.Lock()

app = Client("iftarsahur_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, parse_mode="markdown")


def dump_users(data: dict) -> None:
    with CACHE_LOCK:
        json.dump(data, open('cache.json', 'w'), indent=4)


def load(file: str) -> dict:
    try:
        data = json.load(open(file))
        return {int(key): value for key, value in data.items()}
    except:
        return {}


def dump_chats(data: dict) -> None:
    with CHATS_LOCK:
        json.dump(data, open('chats.json', 'w'), indent=4)


users: Dict[int, List[str]] = load('cache.json')
chats: Dict[int, str] = load('chats.json')

idjson: Dict[str, Dict[str, str]] = json.load(open('ilceid.json'))
tz = pytz.timezone("Europe/Istanbul")

_cache: Dict[str, Dict[str, List[str]]] = {}


async def get_data(ilceid: str) -> Dict[str, List[str]]:
    bugun = datetime.now(tz).strftime("%d.%m.%Y")
    yarin = (datetime.now(tz) + timedelta(days=1)).strftime("%d.%m.%Y")
    if _cache.get(ilceid) and _cache[ilceid].get(bugun) and _cache[ilceid].get(yarin):
        return {'bugun': _cache[ilceid][bugun], 'yarin': _cache[ilceid][yarin]}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://namazvakitleri.diyanet.gov.tr/tr-TR/{ilceid}/ilce-icin-namaz-vakti") as response:
            data = await response.text()
            response = data.split('<tbody>')[1].split('</tbody>')[0]
            resp_bugun = response.split('<tr>')[1].split('</tr>')[0]
            row_bugun = re.findall('<td>(.*?)</td>', resp_bugun)
            resp_yarin = response.split('<tr>')[2].split('</tr>')[0]
            row_yarin = re.findall('<td>(.*?)</td>', resp_yarin)
            _cache[ilceid] = {}
            _cache[ilceid][bugun] = [row_bugun[1], row_bugun[5]]
            _cache[ilceid][yarin] = [row_yarin[1], row_yarin[5]]
            return {'bugun': [row_bugun[1], row_bugun[5]], 'yarin': [row_yarin[1], row_yarin[5]]}


@app.on_message(f.command(['start', f'start{BOT_USERNAME}'], PREFIX))
async def start(client: Client, msg: types.Message):
    await msg.reply_text('/sahur \n/iftar')


@app.on_message(f.command(['iftar', f'iftar{BOT_USERNAME}'], PREFIX))
async def iftar(client: Client, msg: types.Message):
    global users

    uid = msg.from_user.id
    tmp = unidecode(msg.text).upper().split()

    if len(tmp) == 1:
        if uid in users.keys():
            if users[uid] == []:
                return await msg.reply_text('??lk kullan??m: \n`/iftar <il> <il??e (zorunlu de??il)>` \nSonraki kullan??mlar??n??zda il il??e ismi yazman??za gerek yoktur. Sadece `/iftar` yazarak kullanabilirsiniz.\n\nT??rkiye\'de ya??amayan kullan??c??lar i??in kullan??m: `/iftar <??lke> <??ehir>`\nT??rkiye d??????nda desteklenen ??lkeler: `Azerbaycan`')
            else:
                il = users[uid][0]
                ilce = users[uid][1]
        else:
            return await msg.reply_text('??lk kullan??m: \n`/iftar <il> <il??e (zorunlu de??il)>` \nSonraki kullan??mlar??n??zda il il??e ismi yazman??za gerek yoktur. Sadece `/iftar` yazarak kullanabilirsiniz.\n\nT??rkiye\'de ya??amayan kullan??c??lar i??in kullan??m: `/iftar <??lke> <??ehir>`\nT??rkiye d??????nda desteklenen ??lkeler: `Azerbaycan`')
    elif len(tmp) == 2:
        il = tmp[1]
        ilce = tmp[1]
        users[uid] = [il, ilce]

    elif len(tmp) == 3:
        il = tmp[1]
        ilce = tmp[2]
        users[uid] = [il, ilce]

    elif len(tmp) > 3:
        il = tmp[1]
        ilce = ' '.join(tmp[2:])
        users[uid] = [il, ilce]

    else:
        return await msg.reply_text('Girilen il/il??e bulunamad??.')

    if il in idjson:  # girilen il, il listemizde varsa
        if ilce in idjson[il]:  # girilen ilce, ilce listemizde varsa
            bugun_t = datetime.now(tz).timestamp()  # ??u an??n timestamp'i (utc+3)
            bugun = datetime.fromtimestamp(bugun_t, tz).strftime('%d.%m.%Y')
            vakitler = await get_data(idjson[il][ilce])
            ezan_saat = vakitler['bugun'][1]  # bug??n??n ezan vakti
            ezan_t = datetime.strptime(f'{ezan_saat} {bugun} +0300', '%H:%M %d.%m.%Y %z').timestamp()  # bug??nk?? ezan saatinin timestamp'i
            if ezan_t < bugun_t:  # ezan vakti ge??mi??se
                tmp_t = bugun_t + 24*60*60  # bir sonraki g??ne ge??mek i??in
                yarin = datetime.fromtimestamp(tmp_t, tz).strftime('%d.%m.%Y')
                ezan_saat = vakitler['yarin'][1]  # yar??n??n ezan vakti
                ezan_t = datetime.strptime(f'{ezan_saat} {yarin} +0300', '%H:%M %d.%m.%Y %z').timestamp()  # yar??nki ezan saatinin timestamp'i
            kalan = ezan_t - bugun_t  # kalan s??reyi hesaplayal??m
            h = int(kalan / 3600)  # kalan saat
            m = int((kalan % 3600) / 60)  # kalan dakika
            _kalan = f'{h} saat, {m} dakika'

            mesaj = f'{ilce}\nS??radaki ??ftar Saati: `{ezan_saat}`\nS??radaki iftara kalan s??re: `{_kalan}`'
            await msg.reply_text(mesaj)
        else:
            await msg.reply_text(f'{ilce} bulunamad??.')
            users[uid] = [il, il]  # ilce bulunamad??ysa ilce yerine de ili kaydediyoruz
    else:
        if il == ilce:
            il_ilce = f'{il}'
        else:
            il_ilce = f'{il} {ilce}'
        await msg.reply_text(f'{il_ilce} bulunamad??.')
        users[uid] = []  # kar??????kl??k olmamas?? i??in
    dump_users(users)


@app.on_message(f.command(['sahur', f'sahur{BOT_USERNAME}'], PREFIX))
async def iftar(client: Client, msg: types.Message):
    global users

    uid = msg.from_user.id
    tmp = unidecode(msg.text).upper().split()

    if len(tmp) == 1:
        if uid in users.keys():
            if users[uid] == []:
                return await msg.reply_text('??lk kullan??m: \n`/sahur <il> <il??e (zorunlu de??il)>` \nSonraki kullan??mlar??n??zda il il??e ismi yazman??za gerek yoktur. Sadece `/sahur` yazarak kullanabilirsiniz.\n\nT??rkiye\'de ya??amayan kullan??c??lar i??in kullan??m: `/iftar <??lke> <??ehir>`\nT??rkiye d??????nda desteklenen ??lkeler: `Azerbaycan`')
            else:
                il = users[uid][0]
                ilce = users[uid][1]
        else:
            return await msg.reply_text('??lk kullan??m: \n`/sahur <il> <il??e (zorunlu de??il)>` \nSonraki kullan??mlar??n??zda il il??e ismi yazman??za gerek yoktur. Sadece `/sahur` yazarak kullanabilirsiniz.\n\nT??rkiye\'de ya??amayan kullan??c??lar i??in kullan??m: `/iftar <??lke> <??ehir>`\nT??rkiye d??????nda desteklenen ??lkeler: `Azerbaycan`')
    elif len(tmp) == 2:
        il = tmp[1]
        ilce = tmp[1]
        users[uid] = [il, ilce]

    elif len(tmp) == 3:
        il = tmp[1]
        ilce = tmp[2]
        users[uid] = [il, ilce]

    elif len(tmp) > 3:
        il = tmp[1]
        ilce = ' '.join(tmp[2:])
        users[uid] = [il, ilce]

    else:
        return await msg.reply_text('Girilen il/il??e bulunamad??.')

    if il in idjson:  # girilen il, il listemizde varsa
        if ilce in idjson[il]:  # girilen ilce, ilce listemizde varsa
            bugun_t = datetime.now(tz).timestamp()  # ??u an??n timestamp'i (utc+3)
            bugun = datetime.fromtimestamp(bugun_t, tz).strftime('%d.%m.%Y')
            vakitler = await get_data(idjson[il][ilce])
            ezan_saat = vakitler['bugun'][0]
            ezan_t = datetime.strptime(f'{ezan_saat} {bugun} +0300', '%H:%M %d.%m.%Y %z').timestamp()  # bug??nk?? ezan saatinin timestamp'i
            if ezan_t < bugun_t:  # ezan vakti ge??mi??se
                tmp_t = bugun_t + 24*60*60  # bir sonraki g??ne ge??mek i??in
                yarin = datetime.fromtimestamp(tmp_t, tz).strftime('%d.%m.%Y')
                ezan_saat = vakitler['yarin'][0]  # yar??n??n ezan vaktini ??ekelim
                ezan_t = datetime.strptime(f'{ezan_saat} {yarin} +0300', '%H:%M %d.%m.%Y %z').timestamp()  # yar??nki ezan saatinin timestamp'i
            kalan = ezan_t - bugun_t  # kalan s??reyi hesaplayal??m
            h = int(kalan / 3600)  # kalan saat
            m = int((kalan % 3600) / 60)  # kalan dakika
            _kalan = f'{h} saat, {m} dakika'

            mesaj = f'{ilce}\nS??radaki Sahur Saati: `{ezan_saat}`\nS??radaki sahura kalan s??re: `{_kalan}`'
            await msg.reply_text(mesaj)
        else:
            await msg.reply_text(f'{ilce} bulunamad??.')
            users[uid] = [il, il]  # ilce bulunamad??ysa ilce yerine de ili kaydediyoruz
    else:
        if il == ilce:
            il_ilce = f'{il}'
        else:
            il_ilce = f'{il} {ilce}'
        await msg.reply_text(f'{il_ilce} bulunamad??.')
        users[uid] = []  # kar??????kl??k olmamas?? i??in
    dump_users(users)


@app.on_inline_query(f.regex(r'^(sahur|iftar)'))
async def inline(client: Client, query: types.InlineQuery):
    global users

    uid = query.from_user.id
    tmp = unidecode(query.query).upper().split()
    vakit = query.query[:5]

    if len(tmp) == 1:
        if uid in users.keys():
            if users[uid] == []:
                return await query.answer(
                    [
                        types.InlineQueryResultArticle(
                            '??l ve il??e giriniz.',
                            types.InputTextMessageContent(
                                f'??lk kullan??m: \n`{BOT_USERNAME} <iftar|sahur> <il> <il??e (zorunlu de??il)>` \nSonraki kullan??mlar??n??zda il il??e ismi yazman??za gerek yoktur.'
                            ),
                            description=f'Kullan??m: {BOT_USERNAME} <iftar|sahur> <il> <il??e (zorunlu de??il)>'
                        )
                    ],
                    cache_time=0)
            else:
                il = users[uid][0]
                ilce = users[uid][1]
        else:
            return await query.answer(
                [
                    types.InlineQueryResultArticle(
                        '??l ve il??e giriniz.',
                        types.InputTextMessageContent(
                            f'??lk kullan??m: \n`{BOT_USERNAME} <iftar|sahur> <il> <il??e (zorunlu de??il)>` \nSonraki kullan??mlar??n??zda il il??e ismi yazman??za gerek yoktur. Sadece `/sahur` yazarak kullanabilirsiniz.'
                        ),
                        description=f'Kullan??m: {BOT_USERNAME} <iftar|sahur> <il> <il??e (zorunlu de??il)>'
                    )
                ],
                cache_time=0)
    elif len(tmp) == 2:
        il = tmp[1]
        ilce = tmp[1]
        users[uid] = [il, ilce]

    elif len(tmp) == 3:
        il = tmp[1]
        ilce = tmp[2]
        users[uid] = [il, ilce]

    elif len(tmp) > 3:
        il = tmp[1]
        ilce = ' '.join(tmp[2:])
        users[uid] = [il, ilce]

    else:
        return await query.answer(
            [
                types.InlineQueryResultArticle(
                    'Girilen il/il??e bulunamad??.',
                    types.InputTextMessageContent(
                        'Girilen il/il??e bulunamad??.'
                    )
                )
            ],
            cache_time=0)

    if il in idjson:  # girilen il, il listemizde varsa
        if ilce in idjson[il]:  # girilen ilce, ilce listemizde varsa
            bugun_t = datetime.now(tz).timestamp()  # ??u an??n timestamp'i (utc+3)
            bugun = datetime.fromtimestamp(bugun_t, tz).strftime('%d.%m.%Y')
            vakitler = await get_data(idjson[il][ilce])
            ezan_saat = vakitler['bugun'][0 if vakit == 'sahur' else 1]
            ezan_t = datetime.strptime(f'{ezan_saat} {bugun} +0300', '%H:%M %d.%m.%Y %z').timestamp()  # bug??nk?? ezan saatinin timestamp'i
            if ezan_t < bugun_t:  # ezan vakti ge??mi??se
                tmp_t = bugun_t + 24*60*60  # bir sonraki g??ne ge??mek i??in
                yarin = datetime.fromtimestamp(tmp_t, tz).strftime('%d.%m.%Y')
                ezan_saat = vakitler['yarin'][0 if vakit == 'sahur' else 1]  # yar??n??n ezan vaktini ??ekelim
                ezan_t = datetime.strptime(f'{ezan_saat} {yarin} +0300', '%H:%M %d.%m.%Y %z').timestamp()  # yar??nki ezan saatinin timestamp'i
            kalan = ezan_t - bugun_t  # kalan s??reyi hesaplayal??m
            h = int(kalan / 3600)  # kalan saat
            m = int((kalan % 3600) / 60)  # kalan dakika
            _kalan = f'{h} saat, {m} dakika'

            mesaj = f'{ilce}\nS??radaki {vakit.capitalize()} Saati: `{ezan_saat}`\nS??radaki {vakit}a kalan s??re: `{_kalan}`'
            await query.answer(
                [
                    types.InlineQueryResultArticle(
                        ilce,
                        types.InputTextMessageContent(
                            mesaj
                        )
                    )
                ],
                cache_time=0)
        else:
            await query.answer(
                [
                    types.InlineQueryResultArticle(
                        f'{ilce} bulunumad??.',
                        types.InputTextMessageContent(
                            f'{ilce} bulunumad??.'
                        )
                    )
                ],
                cache_time=0)
            users[uid] = [il, il]  # ilce bulunamad??ysa ilce yerine de ili kaydediyoruz
    else:
        if il == ilce:
            il_ilce = f'{il}'
        else:
            il_ilce = f'{il} {ilce}'
        await query.answer(
            [
                types.InlineQueryResultArticle(
                    f'{il_ilce} bulunumad??.',
                    types.InputTextMessageContent(
                        f'{il_ilce} bulunumad??.'
                    )
                )
            ],
            cache_time=0)
        users[uid] = []  # kar??????kl??k olmamas?? i??in
    dump_users(users)


@app.on_message(group=1)
async def save_chats(client: Client, msg: types.Message):
    global chats

    try:
        chats[msg.chat.id] = msg.chat.type
    except:
        pass
    dump_chats(chats)


@app.on_message(f.command('istatistik', PREFIX) & f.user(SUDO))
async def stat(client: Client, msg: types.Message):
    global chats

    private = 0
    group = 0
    for chat_type in chats.values():
        if chat_type == 'private':
            private += 1
        elif chat_type in ['group', 'supergroup']:
            group += 1
    await msg.reply_text(f'**Gruplar: **`{group}`\n**??zel Mesajlar: **`{private}`')


@app.on_message(f.command('duyuru', PREFIX) & f.user(SUDO))
async def duyuru(client: Client, msg: types.Message):
    global chats

    if msg.reply_to_message:
        duyuru = msg.reply_to_message
        chat_ids = list(chats.keys())
        for chat_id in chat_ids:
            try:
                await duyuru.copy(chat_id)
            except:
                del chats[chat_id]
                dump_chats(chats)
    else:
        await msg.reply_text('Duyuru yapmak i??in bir mesaj yan??tlay??n.')

app.run()
