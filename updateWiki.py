#!/usr/bin/env python
# coding: utf-8

# updateWiki.py
# Version 1.2

# HISTORY
# Version 1.2
    # added episode title quality check via sanitizeTitle function
    # TODO: send alert via email if title breaks in an unexpected way
    
# Version 1.1
    # implemented config file with username & password info

# Version 1.0
    # initial version. Uses information from pgenpod rss feed to update pgenpod wiki.


from bs4 import BeautifulSoup
import configparser
import feedparser
import mwclient
import time
# DOCS
# beautifulsoup: https://www.crummy.com/software/BeautifulSoup/bs4/doc/#
# feedparser: https://pythonhosted.org/feedparser/basic.html
# mwclient: https://mwclient.readthedocs.io/en/latest/user/index.html


def main():
    #GRAB RSS FEED
    d = feedparser.parse('https://pgenpod.com/updates?format=rss')

    #CONNECT TO WIKI & LOG IN
    site = mwclient.Site('perfectlygeneric.fandom.com', path = '/')
    config = configparser.ConfigParser()
    config.read_file(open('pgenbot.ini'))
    user = config['PGEN']['User']
    password = config['PGEN']['Pass']
    site.login(user, password)

    #FIND LAST EPISODE ALREADY ON WIKI
    lastOldIndex = 0
    for i in range(len(d.entries)):
        pageTitle = sanitizeTitle(d.entries[i])
        try:
            site.pages[pageTitle].exists
        except mwclient.errors.InvalidPageTitle:
            print("Episode title is invalid:\n\t{}".format(pageTitle))
            return
            # TODO: SEND EMAIL ABOUT THIS
        
        
        if site.pages[pageTitle].exists:
            lastOldIndex = i
            break

    print("Newest episode is {}".format(sanitizeTitle(d.entries[0])))
    print("Wiki has every episode through {}".format(sanitizeTitle(d.entries[lastOldIndex])))

    #for each new episode, from oldest to newest
    for i in reversed(range(lastOldIndex)):
        print("Adding episode to wiki: {}".format(sanitizeTitle(d.entries[i])))

        #COLLECT METADATA
        epdata = metadata(d,i)

        #UPLOAD IMAGE
        #...if it's not already there
        fn = epdata['image'].split('/')[-1]
        if site.images[fn].imageinfo == {}:
            site.upload(url=epdata['image'], filename=epdata['image'].split('/')[-1])

        #UPDATE PREVIOUS EPISODE'S WIKI PAGE
        #...if that's not already done
        prevpage = site.pages[epdata['previous'][2:-2]].text()
        if epdata['title'] not in prevpage:
            splitpage = prevpage.split('|next=')
            newPreviousPage = '|next=[[{}]]'.format(epdata['title']).join(splitpage)
            site.pages[epdata['previous'][2:-2]].edit(newPreviousPage,'Added next episode')

        #CREATE PAGE ON WIKI
        #...if that's not already done
        if not site.pages[epdata['title']].exists:
            epwiki = wikiformat(epdata)
            site.pages[epdata['title']].edit(epwiki,'Created page')

        #UPDATE WIKI PAGE OF PODCAST ITSELF
        #...if that's not already done
        episodeListPage = site.pages['Perfectly Generic Podcast'].text()
        if epdata['title'] not in episodeListPage:
            newEpisodeListPage = mainpagetext(episodeListPage,epdata)
            site.pages['Perfectly Generic Podcast'].edit(newEpisodeListPage,'Updated episode list')

    print("done")
    ########


def sanitizeTitle(episode: feedparser.FeedParserDict) -> str:
    # Sanitize title: remove junk before episode titles
        # This includes "[I]ntermission/" for Bonus Episodes
        # This also includes, for example, "[CORRECTED]" for Episode 94
        
    rawTitle = episode.title

    if "bonus" in episode.link:
        okTitle = rawTitle[rawTitle.find("Bonus"):]
        #return okTitle
    else:
        okTitle = rawTitle[rawTitle.find("Episode"):]
    
    return okTitle


def metadata(feed: feedparser.FeedParserDict, item: int) -> dict:
    #Create a dict with the relevant metadata for the wiki, from a given feed and index, of the item at that index.
    
    episode = feed.entries[item]
    
    md = {}

    #TITLE
    md['title'] = sanitizeTitle(episode)

    #IMAGE LINK
    md['image'] = episode.image.href

    #NUMBER
    if "bonus" in episode.link:
        md['number'] = "Bonus {}".format(episode.link.split("/")[-1])
    else:
        #md['number'] = episode.itunes_episode
        md['number'] = episode.link.split("/")[-1]
    
    #FEATURING
    md['featuring'] = [t['term'] for t in episode.tags]

    #RELEASE DATE
    md['date'] = time.strftime("%b %d, %Y",episode.published_parsed)

    #DURATION
    try:
        md['duration'] = episode.itunes_duration
    except:
        md['duration'] = ""
        
    #PREVIOUS
    if item == len(feed.entries)-1:
        prev_ep = ""
    else:
        prevTitle = sanitizeTitle(feed.entries[item+1])
        prev_ep = "[[{}]]".format(prevTitle)
    md['previous'] = prev_ep
    
    #NEXT
    if item == 0:
        next_ep = ""
    else:
        nextTitle = sanitizeTitle(feed.entries[item-1])
        next_ep = "[[{}]]".format(nextTitle)
    md['next'] = next_ep    
    
    #SUMMARY
    s = BeautifulSoup(episode.summary)
    md['summary'] = s.p.contents[0]

    #LINK
    md['link'] = episode.link

    return md


def wikiformat(md: dict) -> str:
    # Generate source for a new episode's page, from the episode's metadata.
    
    pagetext = "{{Podcast episode"
    pagetext += "\n |title1={}".format(md['title'])
    pagetext += "\n |image1={}".format(md['image'].split('/')[-1])
    pagetext += "\n |caption1={}".format(md['link'])
    pagetext += "\n |episode={}".format(md['number'])
    pagetext += "\n |featuring=[[{}]] (host)<br>".format(md['featuring'][0])
    for i in md['featuring'][1:]:
        pagetext += "[[{}]]<br>".format(i)
    pagetext += "\n |release_date={}".format(md['date'])
    pagetext += "\n |duration={}".format(md['duration'])
    pagetext += "\n |transcriber=\n |intro_music=\n |outro_music=\n |other_music="
    pagetext += "\n |previous={}".format(md['previous'])
    pagetext += "\n |next={}".format(md['next'])
    pagetext += "\n}}"

    pagetext += "\n\n{}".format(md['summary'])
    pagetext += "\n\nListen to this episode at {}".format(md['link'])
    pagetext += "\n\n== Transcript ==\n\n''This episode has not yet been transcribed.''"
    pagetext += "\n\n[[Category:Episodes]]\n[[Category:Perfectly Generic Podcast]]"

    return pagetext


def mainpagetext(pg: str, md: dict) -> str:
    
    #UPDATE EPISODES SECTION
    
    #format line for new episode
    newEpisode = ''
    newEpisode += '* [[{}]] with [[{}]]'.format(md['title'],md['featuring'][0])
    for i in md['featuring'][1:-1]:
        newEpisode += ', [[{}]]'.format(i)
    if len(md['featuring']) > 2:
        newEpisode += ','
    newEpisode += ' and [[{}]] **'.format(md['featuring'][-1])

    #split page into lines
    splitpage = pg.split('\n')
    
    #find line containing prev episode
    prevline = [s for s in splitpage if md['previous'] in s][0]
    prevind = splitpage.index(prevline)

    #insert new episode after that line
    splitpage.insert(prevind+1,newEpisode)
    
    
    #UPDATE PANEL SECTION
    
    #isolate panel
    panelstart = splitpage.index('== Panel ==')+1
    panelend = panelstart + splitpage[panelstart:].index('')
    panel = splitpage[panelstart:panelend]
    
    #for each panelist:
    for i in md['featuring']:
        #if panelist is not in panel list, add them:
        if not any('[[{}]]'.format(i) in s for s in panel):
            panel.append('* [[{}]]'.format(i))
            panel = sorted(panel, key=lambda s: s.lower())
        
        #if host is not indicated as a host, change that:
        if md['featuring'].index(i) == 0:
            if ']] (host)' not in [s for s in panel if '[[{}]]'.format(i) in s][0]:
                panel[panel.index('* [[{}]]'.format(i))] += ' (host)'
    
    #insert updated panel
    splitpage[panelstart:panelend] = panel
    return '\n'.join(splitpage)


main()