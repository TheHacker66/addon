# -*- coding: utf-8 -*-
# ------------------------------------------------------------
# infoplus window with item information
# ------------------------------------------------------------
import xbmc, xbmcgui, json, sys, requests, re
from core import support, tmdb, filetools
from core.item import Item
from platformcode import config, platformtools
from platformcode.logger import log
from core.scrapertools import decodeHtmlentities, htmlclean

PY3 = False
if sys.version_info[0] >= 3: PY3 = True
if PY3: from concurrent import futures
else: from concurrent_py2 import futures

info_list = []
SearchWindows = []
api = 'k_0tdb8a8y'

# Control ID
FANART = 30000
NUMBER = 30001
POSTER_BTN = 30010
TITLE = 30002
TAGLINE = 30003
PLOT = 30004
RATING_ICON = 30005
RATING = 30006
TRAILER = 30007
SEARCH = 30008
BTN_NEXT = 30009
BTN_PREV = 30010
LOADING = 30011
COMMANDS = 30012
RECOMANDED = TRAILERS = 30500
CAST = 30501
CASTMOVIES = 30502

# Actions
LEFT = 1
RIGHT = 2
UP = 3
DOWN = 4
EXIT = 10
BACKSPACE = 92



def Main(item):
    if type(item) == Item:
        item.channel = item.from_channel
        global ITEM
        ITEM = item
        Info = xbmcgui.ListItem(item.infoLabels['title'])
        for key, value in item.infoLabels.items():
            Info.setProperty(key, str(value))
    else:
        Info = item

    main = MainWindow('InfoPlus.xml', config.get_runtime_path())
    add({'class':main, 'info':Info, 'id':RECOMANDED, RECOMANDED:0, CAST:0})
    modal()

class MainWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.items = []
        self.cast = []
        self.ids = {}

    def onInit(self):
        #### Compatibility with Kodi 18 ####
        if config.get_platform(True)['num_version'] < 18:
            self.setCoordinateResolution(2)
        if Info.getProperty('id'):
            for item in get_movies(Info):
                self.items.append(item)
        else:
            for item in get_recomendations(Info):
                self.items.append(item)
        for i, item in enumerate(get_cast(Info)):
            if i == 0: actors_more_info(item)
            self.cast.append(item)
        self.getControl(LOADING).setVisible(False)
        self.getControl(RECOMANDED).addItems(self.items)
        self.getControl(FANART).setImage(Info.getProperty('fanart'))
        self.getControl(CAST).addItems(self.cast)
        if Info.getProperty('rating'):
            self.getControl(RATING).setText(str(Info.getProperty('rating')))
        getFocus(self)

    def onClick(self, control_id):
        setFocus(self)
        if control_id in [SEARCH]:
            title = self.getControl(RECOMANDED).getSelectedItem().getProperty('title')
            mode = self.getControl(RECOMANDED).getSelectedItem().getProperty('mediatype')
            action = 'search'
            # if title == Info.getProperty('title'): action = 'global_search'
            # else: action = 'search'
            self.close()
            if self.getControl(RECOMANDED).getSelectedPosition() > 0:
                Search(ITEM.clone(action=action, search_text=title))
            else:
                Search(ITEM.clone(action=action, search_text=title, mode=mode))
        elif control_id in [TRAILER]:
            info = self.getControl(RECOMANDED).getSelectedItem()
            self.close()
            Trailer(info)
        elif control_id in [CAST]:
            self.close()
            Main(self.getControl(CAST).getSelectedItem())
        elif control_id in [BTN_NEXT]:
            self.setFocusId(CAST)
        elif control_id in [BTN_PREV]:
            self.setFocusId(RECOMANDED)
        elif control_id in [RECOMANDED]:
            self.close()
            Main(self.getControl(RECOMANDED).getSelectedItem())

    def onAction(self, action):
        if self.getFocusId() in [CAST, RECOMANDED]:
            self.ids[self.getFocusId()] = self.getControl(self.getFocusId()).getSelectedPosition()
        if self.getFocusId() in [CAST] and action not in [BACKSPACE, EXIT, UP, DOWN]:
            actors_more_info(self.getControl(self.getFocusId()).getSelectedItem())
        if self.getFocusId() in [RECOMANDED]:
            fanart = self.getControl(self.getFocusId()).getSelectedItem().getProperty('fanart')
            rating = self.getControl(self.getFocusId()).getSelectedItem().getProperty('rating')
            if not rating: rating = 'N/A'
            self.getControl(FANART).setImage(fanart)
            self.getControl(RATING).setText(rating)
            if self.getFocus() > 0:
                cast = []
                self.getControl(CAST).reset()
                for actor in get_cast(self.getControl(self.getFocusId()).getSelectedItem()):
                    cast.append(actor)
                self.getControl(CAST).addItems(cast)
        action = action.getId()
        if action in [BACKSPACE]:
            self.close()
            remove()
            modal()
        elif action in [EXIT]:
            self.close()


def Search(item):
    if item.action == 'findvideos': XML = 'ServersWindow.xml'
    else: XML = 'SearchWindow.xml'
    global Info
    Info = item
    main = SearchWindow(XML, config.get_runtime_path())
    add({'class':main, 'info':item, 'id':RECOMANDED})
    modal()

class SearchWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.items = []
        self.itemlist = []
        self.commands = []
        self.ids = {}
        self.channel = None

    def onInit(self):
        #### Compatibility with Kodi 18 ####
        if config.get_platform(True)['num_version'] < 18:
            self.setCoordinateResolution(2)
        if not self.items:
            if Info.action == 'search' and Info.mode:
                from specials.search import new_search
                itemlist = new_search(Info)
            elif Info.action == 'channel_search':
                from specials.search import channel_search
                itemlist = channel_search(Info)
            else:
                self.channel = __import__('channels.%s' % Info.channel, fromlist=["channels.%s" % Info.channel])
                if Info.action == 'search': itemlist = getattr(self.channel, 'search')(Info, Info.search_text)
                else: itemlist = getattr(self.channel, Info.action)(Info)
            if not itemlist:
                if platformtools.dialog_yesno(config.get_localized_string(60473), config.get_localized_string(70820) % Info.channel):
                    remove()
                    self.close()
                    return Search(Info.clone(mode=Info.infoLabels['mediatype']))
                else:
                    remove()
                    self.close()
                    modal()
            for item in itemlist:
                if item.action not in ['save_download', 'add_pelicula_to_library', 'add_serie_to_library', ''] and item.infoLabels['title']:
                    if item.action == 'findvideos' and item.contentType in ['episode', 'tvshow']:
                        it = xbmcgui.ListItem(re.sub(r'\[[^\]]+\]', '', item.title))
                    else:
                        it = xbmcgui.ListItem(item.infoLabels['title'])
                    it.setProperty('channel', item.channel)
                    it.setProperty('action', item.action)
                    it.setProperty('server', item.server)
                    it.setProperty('url', item.url)
                    for key, value in item.infoLabels.items():
                        it.setProperty(key, str(value))
                    if item.action == 'play':
                        it.setProperty('thumbnail', "https://raw.githubusercontent.com/kodiondemand/media/master/resources/servers/%s.png" % item.server.lower())
                    self.items.append(it)
                    self.itemlist.append(item)
            if itemlist[0].contentType == 'movie':
                if not itemlist[0].server:
                    self.commands.append(itemlist[0].clone(action='add_pelicula_to_library',  thumbnail=support.thumb('add_to_videolibrary')))
                    self.commands.append(itemlist[0].clone(channel='downloads', action='save_download', from_channel=itemlist[0].channel, from_action=itemlist[0].action, thumbnail=support.thumb('downloads')))
                else:
                    self.commands.append(Info.clone(channel='downloads', action='save_download', from_channel=Info.channel, from_action=Info.action, thumbnail=support.thumb('downloads')))
            if itemlist[0].contentType in ['tvshow', 'episode']:
                if not itemlist[0].server:
                    self.commands.append(itemlist[0].clone(action='add_serie_to_library',  thumbnail=support.thumb('add_to_videolibrary')))
                    self.commands.append(itemlist[0].clone(channel='downloads', action='save_download', from_channel=itemlist[0].channel, from_action=itemlist[0].action, thumbnail=support.thumb('downloads')))
                else:
                    self.commands.append(Info.clone(channel='downloads', action='save_download', from_channel=Info.channel, from_action=Info.action, thumbnail=support.thumb('downloads')))

            if self.commands:
                commands = []
                for command in self.commands:
                    it = xbmcgui.ListItem(command.title)
                    path = filetools.join(config.get_runtime_path(),'resources','skins','Default','media','Infoplus',command.thumbnail.split('/')[-1].replace('thumb_',''))
                    it.setProperty('thumbnail',path)
                    commands.append(it)
                self.getControl(COMMANDS).addItems(commands)
            if self.items:
                self.getControl(FANART).setImage(self.items[0].getProperty('fanart'))

        self.getControl(RECOMANDED).addItems(self.items)
        self.getControl(LOADING).setVisible(False)
        getFocus(self)

    def onClick(self, control_id):
        setFocus(self)
        if control_id == COMMANDS:
            from platformcode.launcher import run
            pos = self.getControl(COMMANDS).getSelectedPosition()
            if self.commands[pos].action =='save_download' and self.commands[pos].contentType == 'tvshow':
                actions = [self.commands[-1].clone(), self.commands[-1].clone(download='season')]
                options = [config.get_localized_string(60355),config.get_localized_string(60357)]
                run(actions[platformtools.dialog_select(config.get_localized_string(60498),options)])
            else:
                run(self.commands[pos])
        else:
            action = self.getControl(RECOMANDED).getSelectedItem().getProperty('action')
            channel = self.getControl(RECOMANDED).getSelectedItem().getProperty('channel')
            url = self.getControl(RECOMANDED).getSelectedItem().getProperty('url')
            item = Item(channel=channel, action=action, url=url)
            if action == 'play':
                item.server = self.getControl(RECOMANDED).getSelectedItem().getProperty('server')
                self.close()
                platformtools.play_video(item)
                xbmc.sleep(500)
                while xbmc.Player().isPlaying():
                    xbmc.sleep(500)
                modal()
            elif config.get_setting('autoplay'):
                item.quality = self.getControl(RECOMANDED).getSelectedItem().getProperty('quality')
                getattr(self.channel, item.action)(item)
                self.close()
                xbmc.sleep(500)
                while xbmc.Player().isPlaying():
                    xbmc.sleep(500)
                modal()
            else:
                pos = self.getControl(RECOMANDED).getSelectedPosition()
                self.close()
                if self.itemlist[pos].mode: remove()
                Search(self.itemlist[pos])

    def onAction(self, action):
        if self.getFocusId() in [RECOMANDED]:
            fanart = self.getControl(self.getFocusId()).getSelectedItem().getProperty('fanart')
            self.getControl(FANART).setImage(fanart)
        action = action.getId()
        if action in [BACKSPACE]:
            self.close()
            remove()
            modal()
        elif action in [EXIT]:
            self.close()


def Trailer(info):
    global info_list, trailers
    trailers = []
    trailers_list = []
    Type = info.getProperty('mediatype')
    if Type != "movie": Type = "tv"
    trailers_list = tmdb.Tmdb(id_Tmdb=info.getProperty('tmdb_id'), tipo=Type).get_videos()
    if trailers_list:
        for i, trailer in enumerate(trailers_list):
            item = xbmcgui.ListItem(trailer['name'])
            item.setProperties({'tile':trailer['name'],
                                'url': trailer['url'],
                                'thumbnail': 'http://img.youtube.com/vi/' + trailer['url'].split('=')[-1] + '/0.jpg',
                                'fanart':info.getProperty('fanart'), 
                                'position':'%s/%s' % (i + 1, len(trailers_list))})
            trailers.append(item)
    else: # TRY youtube search
        patron  = r'thumbnails":\[\{"url":"(https://i.ytimg.com/vi[^"]+).*?'
        patron += r'text":"([^"]+).*?'
        patron += r'simpleText":"[^"]+.*?simpleText":"([^"]+).*?'
        patron += r'url":"([^"]+)'
        matches = support.match('https://www.youtube.com/results?search_query=' + info.getProperty('title').replace(' ','+') + '+trailer+ita', patron = patron).matches
        i = 0
        for thumb, title, text, url in matches:
            i += 1
            item = xbmcgui.ListItem(title + ' - '+ text)
            item.setProperties({'tile':title + ' - '+ text, 'url': url, 'thumbnail': thumb, 'fanart':info.getProperty('fanart'), 'position':'%s/%s' % (i, len(matches))})
            trailers.append(item)
    main = TrailerWindow('TrailerWindow.xml', config.get_runtime_path())
    add({'class':main, 'info':trailers, 'id':RECOMANDED, TRAILERS:0})
    modal()

class TrailerWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.ids = {}

    def onInit(self):
        #### Compatibility with Kodi 18 ####
        if config.get_platform(True)['num_version'] < 18:
            self.setCoordinateResolution(2)
        self.getControl(FANART).setImage(trailers[0].getProperty('fanart'))
        self.getControl(NUMBER).setText(trailers[0].getProperty('position'))
        self.getControl(TRAILERS).addItems(trailers)
        self.setFocusId(TRAILERS)
        getFocus(self)

    def onClick(self, control_id):
        setFocus(self)
        if control_id in [TRAILERS]:
            selected = self.getControl(TRAILERS).getSelectedItem()
            platformtools.play_video(Item(title=selected.getProperty('title'), action='play', url=selected.getProperty('url'), server='youtube'))
            while not xbmc.Player().isPlaying():
                xbmc.sleep(100)
            self.close()
            while xbmc.Player().isPlaying():
                xbmc.sleep(100)
            modal()

    def onAction(self, action):
        if self.getFocusId() in [TRAILERS]:
            self.ids[self.getFocusId()] = self.getControl(self.getFocusId()).getSelectedPosition()
            fanart = self.getControl(TRAILERS).getSelectedItem().getProperty('fanart')
            position = self.getControl(TRAILERS).getSelectedItem().getProperty('position')
            self.getControl(FANART).setImage(fanart)
            self.getControl(NUMBER).setText(position)
        action = action.getId()
        global info_list
        if action in [BACKSPACE]:
            self.close()
            remove()
            modal()
        elif action in [EXIT]:
            self.close()


def get_recomendations(info):
    recommendations = [info]
    Type = info.getProperty('mediatype')
    if Type != "movie": Type = "tv"
    search = {'url': '%s/%s/recommendations' % (Type, info.getProperty('tmdb_id')), 'language': 'it', 'page': 1}
    tmdb_res = tmdb.Tmdb(discover=search, tipo=Type, idioma_Search='it').results
    for result in tmdb_res:
        if Type == 'movie':
            title = result.get("title", '')
            original_title = result.get("original_title", "")
        else:
            title = result.get("name", '')
            original_title  = result.get("original_name", '')
        thumbnail ='http://image.tmdb.org/t/p/w342' + result.get("poster_path", "") if result.get("poster_path", "") else imagepath(Type)
        fanart = 'http://image.tmdb.org/t/p/original' + result.get("backdrop_path", "") if result.get("backdrop_path", "") else ''
        item = xbmcgui.ListItem(title)
        item.setProperties({'title': title,
                            'original_title': original_title,
                            'mediatype': info.getProperty('mediatype'),
                            'tmdb_id': result.get('id', 0),
                            'imdb_id': info.getProperty('imdb_id'),
                            'rating': result.get('vote_average', 0),
                            'plot': result.get('overview', ''),
                            'year': result.get('release_date', '').split('-')[0],
                            'thumbnail': thumbnail,
                            'fanart': fanart})
        recommendations.append(item)
    return recommendations


def get_cast(info):
    actors_list = []
    Type = "movie" if info.getProperty('mediatype') == 'movie' else 'tv'
    otmdb = tmdb.Tmdb(id_Tmdb=info.getProperty('tmdb_id'), tipo=Type)
    actors = otmdb.result.get("credits", {}).get("cast", [])
    cast = otmdb.result.get("credits", {}).get("crew", []) if Type == 'movie' else otmdb.result.get("created_by", [])
    for crew in cast:
        if crew.get('job', '') == 'Director' or Type != "movie": actors.insert(0, crew)
    for actor in actors:
        res = xbmcgui.ListItem(actor.get('name', ''))
        res.setProperties({'title': actor.get('name', ''),
                           'job': actor.get('job', '') if actor.get('job', '') else actor.get('character',''),
                           'thumbnail': "https://image.tmdb.org/t/p/w342" + actor.get('profile_path', '') if actor.get('profile_path', '')  else imagepath('no_photo'),
                           'type': Type,
                           'id': actor.get('id', ''),
                           'mediatype': info.getProperty('mediatype')})
        actors_list.append(res)
    return actors_list

def imagepath(image):
    if len(image.split('.')) == 1: image += '.png'
    path = filetools.join(config.get_runtime_path(), 'resources', 'skins' , 'Default', 'media', 'Infoplus', image)
    return path

def actors_more_info(ListItem):
    api = 'k_0tdb8a8y'
    Type = ListItem.getProperty('type')
    actor_id = ListItem.getProperty('id')
    more = tmdb.Tmdb(discover={'url': 'person/' + str(actor_id), 'language': 'it', 'append_to_response': Type + '_credits'}).results
    imdb = requests.get('https://imdb-api.com/it/API/Name/%s/%s' % (api, more['imdb_id'])).json()
    ListItem.setProperty('bio', imdb['summary'])


def get_movies(info):
    Type = info.getProperty('mediatype') if info.getProperty('mediatype') == 'movie' else 'tv'
    more = tmdb.Tmdb(discover={'url': 'person/' + str(info.getProperty('id')), 'language': 'it', 'append_to_response': Type + '_credits'}).results
    movies = []
    for movie in more.get(Type + '_credits', {}).get('cast',[]) + more.get(Type + '_credits', {}).get('crew',[]):
        ret = {}
        ret['mediatype'] = info.getProperty('mediatype')
        thumbnail = movie.get('poster_path','')
        ret['thumbnail'] = "https://image.tmdb.org/t/p/w342" + thumbnail if thumbnail else imagepath(Type)
        ret['title'] = movie.get('title','') if Type == 'movie' else movie.get('name','')
        ret['original_title'] = movie.get('original_title','') if Type == 'movie' else movie.get("original_name", '')
        ret['tmdb_id'] = movie.get('id',0)
        if ret not in movies: movies.append(ret)
    itemlist = []
    with futures.ThreadPoolExecutor() as executor:
        List = [executor.submit(add_infoLabels, movie) for movie in movies]
        for res in futures.as_completed(List):
            if res.result():
                itemlist.append(res.result())
        itemlist = sorted(itemlist, key=lambda it: (it.getProperty('year'),it.getProperty('title')))
    return itemlist

def add_infoLabels(movie):
    it = Item(title=movie['title'], infoLabels=movie, contentType=movie['mediatype'])
    tmdb.set_infoLabels_item(it, True)
    movie=it.infoLabels
    item = xbmcgui.ListItem(movie['title'])
    for key, value in movie.items():
        item.setProperty(key, str(value))
    return item


def add(Dict):
    global info_list
    info_list.append(Dict)

def remove():
    global info_list
    info_list = info_list[:-1]

def modal():
    global Info
    global info_list
    if info_list:
        Info = info_list[-1]['info']
        info_list[-1]['class'].doModal()

def getFocus(self):
    global info_list
    for key, value in info_list[-1].items():
        if key not in ['class', 'info', 'id']:
            self.getControl(int(key)).selectItem(value)
    self.setFocusId(info_list[-1]['id'])

def setFocus(self):
    global info_list
    info_list[-1]['id'] = self.getFocusId()
    for key, values in self.ids.items():
        info_list[-1][key] = values